"""Inventario y administración conservadora de elementos de inicio de Windows.

Sólo permite deshabilitar entradas de usuario que CorePulse puede restaurar con
exactitud (HKCU Run/RunOnce y carpeta Startup del usuario). Entradas de sistema,
Microsoft, seguridad, controladores y ámbitos HKLM quedan en modo observación.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
from typing import Any, Dict

import psutil

from core.runtime_paths import state_path

STATE_FILE = state_path('startup_disabled.json')
DISABLED_DIR = state_path('startup_disabled_files')


def _now():
    return datetime.now(timezone.utc).isoformat()


def _read_state() -> dict:
    try:
        if STATE_FILE.is_file():
            data = json.loads(STATE_FILE.read_text(encoding='utf-8'))
            return data if isinstance(data, dict) else {'items': {}}
    except Exception:
        pass
    return {'schema': 'corepulse.startup.disabled.v1', 'items': {}}


def _write_state(data: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(STATE_FILE)


def _extract_exe(command: str) -> str | None:
    text = os.path.expandvars(str(command or '').strip())
    if not text:
        return None
    m = re.match(r'^\s*"([^"]+)"', text)
    candidate = m.group(1) if m else None
    if not candidate:
        m = re.search(r'(?i)([A-Z]:\\[^\r\n]*?\.(?:exe|com|bat|cmd))(?=\s|$)', text)
        candidate = m.group(1).strip('"') if m else text.split()[0].strip('"')
    try:
        return str(Path(candidate).expanduser())
    except Exception:
        return candidate


def _shortcut_targets(paths: list[str]) -> dict[str, str]:
    """Resuelve accesos directos .lnk del Startup del usuario en una sola consulta."""
    unique = [str(p) for p in paths if p and str(p).lower().endswith('.lnk') and Path(p).is_file()]
    if not unique or platform.system() != 'Windows':
        return {}
    literals = ','.join("'" + p.replace("'", "''") + "'" for p in unique)
    script = (
        "[Console]::OutputEncoding=[Text.Encoding]::UTF8; "
        "$w=New-Object -ComObject WScript.Shell; "
        f"$paths=@({literals}); $r=@(); foreach($p in $paths){{ try{{$s=$w.CreateShortcut($p); $r += [pscustomobject]@{{Path=$p;Target=$s.TargetPath}}}}catch{{}}}}; "
        "$r | ConvertTo-Json -Compress"
    )
    try:
        cp = subprocess.run(['powershell.exe','-NoLogo','-NoProfile','-NonInteractive','-Command',script], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10, creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if cp.returncode != 0 or not cp.stdout.strip():
            return {}
        data = json.loads(cp.stdout); rows = data if isinstance(data, list) else [data]
        return {os.path.normcase(str(x.get('Path'))): str(x.get('Target') or '') for x in rows if isinstance(x, dict) and x.get('Path')}
    except Exception:
        return {}


def _companies(paths: list[str]) -> dict[str, str]:
    unique = []
    seen = set()
    for p in paths:
        if not p:
            continue
        key = os.path.normcase(p)
        if key not in seen and Path(p).is_file():
            seen.add(key); unique.append(p)
    if not unique or platform.system() != 'Windows':
        return {}
    literals = ','.join("'" + p.replace("'", "''") + "'" for p in unique)
    script = (
        "[Console]::OutputEncoding=[Text.Encoding]::UTF8; "
        f"$paths=@({literals}); $r=@(); foreach($p in $paths){{ try{{$v=(Get-Item -LiteralPath $p -ErrorAction Stop).VersionInfo; "
        "$r += [pscustomobject]@{Path=$p;Company=$v.CompanyName;Description=$v.FileDescription}}catch{}}}; "
        "$r | ConvertTo-Json -Compress"
    )
    try:
        cp = subprocess.run(['powershell.exe','-NoLogo','-NoProfile','-NonInteractive','-Command',script], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10, creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if cp.returncode != 0 or not cp.stdout.strip():
            return {}
        data = json.loads(cp.stdout)
        rows = data if isinstance(data, list) else [data]
        out = {}
        for row in rows:
            if isinstance(row, dict) and row.get('Path'):
                out[os.path.normcase(str(row['Path']))] = str(row.get('Company') or '').strip()
        return out
    except Exception:
        return {}


def _registry_rows() -> list[dict]:
    if platform.system() != 'Windows':
        return []
    try:
        import winreg
    except Exception:
        return []
    defs = [
        ('HKCU', winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Run', 'Run'),
        ('HKCU', winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\RunOnce', 'RunOnce'),
        ('HKLM', winreg.HKEY_LOCAL_MACHINE, r'Software\Microsoft\Windows\CurrentVersion\Run', 'Run'),
        ('HKLM', winreg.HKEY_LOCAL_MACHINE, r'Software\Microsoft\Windows\CurrentVersion\RunOnce', 'RunOnce'),
    ]
    rows = []
    for hive_name, hive, key_path, label in defs:
        try:
            with winreg.OpenKey(hive, key_path, 0, winreg.KEY_READ) as key:
                index = 0
                while True:
                    try:
                        name, value, reg_type = winreg.EnumValue(key, index); index += 1
                    except OSError:
                        break
                    cmd = str(value or '')
                    rows.append({
                        'source_id': f'registry:{hive_name}:{key_path}:{name}',
                        'source_type': 'registry', 'scope': hive_name, 'registry_path': key_path,
                        'value_name': str(name), 'registry_type': int(reg_type),
                        'name': str(name), 'command': cmd, 'location': f'{hive_name}\\{key_path}',
                        'user': os.environ.get('USERNAME') if hive_name == 'HKCU' else 'Todos los usuarios',
                        'executable': _extract_exe(cmd), 'enabled': True,
                    })
        except OSError:
            continue
    return rows


def _folder_rows() -> list[dict]:
    if platform.system() != 'Windows':
        return []
    folders = []
    appdata = os.environ.get('APPDATA')
    programdata = os.environ.get('PROGRAMDATA')
    if appdata:
        folders.append(('USER', Path(appdata) / r'Microsoft\Windows\Start Menu\Programs\Startup'))
    if programdata:
        folders.append(('ALL', Path(programdata) / r'Microsoft\Windows\Start Menu\Programs\StartUp'))
    rows = []
    for scope, folder in folders:
        try:
            for item in folder.iterdir():
                if not item.is_file():
                    continue
                rows.append({
                    'source_id': f'file:{scope}:{str(item)}', 'source_type': 'startup_file',
                    'scope': scope, 'name': item.stem, 'command': str(item), 'location': str(folder),
                    'user': os.environ.get('USERNAME') if scope == 'USER' else 'Todos los usuarios',
                    'executable': str(item) if item.suffix.lower() in {'.exe','.bat','.cmd','.com'} else None,
                    'file_path': str(item), 'enabled': True,
                })
        except Exception:
            continue
    return rows


def _safe_rule(row: dict, company: str) -> tuple[bool, str]:
    scope = str(row.get('scope') or '').upper()
    source = str(row.get('source_type') or '')
    blob = ' '.join(str(row.get(k) or '') for k in ('name','command','executable')).casefold()
    company_low = str(company or '').casefold()
    protected_tokens = (
        'windows defender','securityhealth','security health','antivirus','endpoint','firewall',
        'microsoft\\windows','system32','syswow64','driver','audio service','corepulse',
    )
    if source == 'registry' and scope != 'HKCU':
        return False, 'Entrada global del sistema (HKLM): CorePulse sólo la observa.'
    if source == 'registry' and str(row.get('registry_path') or '').casefold().endswith('runonce'):
        return False, 'RunOnce puede completar instalaciones/actualizaciones; CorePulse no lo deshabilita.'
    if source == 'startup_file' and scope != 'USER':
        return False, 'Carpeta de inicio para todos los usuarios: CorePulse sólo la observa.'
    if source == 'startup_file' and str(row.get('file_path') or '').lower().endswith('.lnk') and not row.get('executable'):
        return False, 'El destino del acceso directo no pudo verificarse; CorePulse sólo lo observa.'
    if 'microsoft' in company_low or any(tok in blob for tok in protected_tokens):
        return False, 'Componente de sistema/seguridad o ámbito protegido.'
    if source not in {'registry','startup_file'}:
        return False, 'Origen no reversible de forma segura.'
    return True, 'Entrada de usuario reversible; CorePulse guardará el valor/ruta exactos antes de deshabilitar.'


def collect_startup_items() -> Dict[str, Any]:
    if platform.system() != 'Windows':
        return {'items': [], 'count': 0, 'disabled_count': 0, 'error': 'Windows requerido', 'policy': 'USER_REVERSIBLE_ONLY'}
    rows = _registry_rows() + _folder_rows()
    shortcut_targets = _shortcut_targets([str(x.get('file_path') or '') for x in rows if x.get('source_type') == 'startup_file'])
    for row in rows:
        file_path = str(row.get('file_path') or '')
        if file_path.lower().endswith('.lnk'):
            target = shortcut_targets.get(os.path.normcase(file_path))
            if target:
                row['executable'] = target
                row['shortcut_target'] = target
    companies = _companies([str(x.get('executable') or '') for x in rows])
    running = {}
    try:
        for p in psutil.process_iter(['name','memory_info']):
            name = str(p.info.get('name') or '').lower()
            if name and name not in running:
                running[name] = p.info
    except Exception:
        pass
    for row in rows:
        exe = str(row.get('executable') or '')
        company = companies.get(os.path.normcase(exe), '') if exe else ''
        row['publisher'] = company or 'N/A'
        basename = Path(exe).name.lower() if exe else ''
        pinfo = running.get(basename)
        mem = None
        if pinfo and pinfo.get('memory_info') is not None:
            try: mem = pinfo['memory_info'].rss / (1024*1024)
            except Exception: pass
        row['running_memory_mb'] = mem
        row['impact'] = 'MEDIO' if mem is not None and mem >= 150 else 'BAJO' if mem is not None else 'NO_MEDIDO'
        safe, reason = _safe_rule(row, company)
        row['safe_to_disable'] = safe
        row['action_reason'] = reason
        row['state'] = 'Habilitado'

    state = _read_state(); disabled = state.get('items') if isinstance(state.get('items'), dict) else {}
    for source_id, saved in disabled.items():
        if not isinstance(saved, dict):
            continue
        rows.append({
            'source_id': source_id, 'source_type': saved.get('source_type'), 'scope': saved.get('scope'),
            'name': saved.get('name') or saved.get('value_name') or 'Elemento',
            'command': saved.get('command') or saved.get('original_path') or '',
            'location': saved.get('location') or '', 'publisher': saved.get('publisher') or 'N/A',
            'running_memory_mb': None, 'impact': 'NO_MEDIDO', 'enabled': False, 'state': 'Deshabilitado',
            'safe_to_disable': False, 'can_restore': True,
            'action_reason': 'CorePulse conserva una copia reversible de esta entrada.',
        })
    impact_rank = {'ALTO (evento de degradación)': 3, 'MEDIO': 2, 'BAJO': 1, 'NO_MEDIDO': 0}
    rows.sort(key=lambda x: (not bool(x.get('enabled')), -impact_rank.get(str(x.get('impact')), 0), str(x.get('name') or '').casefold()))
    return {
        'items': rows, 'count': len(rows), 'enabled_count': sum(1 for x in rows if x.get('enabled')),
        'disabled_count': sum(1 for x in rows if not x.get('enabled')),
        'error': None, 'source': 'Registro Run/RunOnce + carpetas Startup + psutil + metadatos de archivo',
        'policy': 'USER_REVERSIBLE_ONLY_NO_SYSTEM_AUTO_DISABLE',
    }


def disable_startup_item(source_id: str) -> Dict[str, Any]:
    items = collect_startup_items().get('items') or []
    row = next((x for x in items if x.get('source_id') == source_id and x.get('enabled')), None)
    if not row:
        return {'success': False, 'message': 'El elemento ya no está disponible o ya fue deshabilitado.'}
    if not row.get('safe_to_disable'):
        return {'success': False, 'message': row.get('action_reason') or 'CorePulse no permite deshabilitar esta entrada.'}
    state = _read_state(); state.setdefault('items', {})
    saved = dict(row); saved['disabled_at'] = _now()
    try:
        if row.get('source_type') == 'registry':
            import winreg
            hive = winreg.HKEY_CURRENT_USER if row.get('scope') == 'HKCU' else None
            if hive is None:
                raise PermissionError('Ámbito global no permitido')
            with winreg.OpenKey(hive, row['registry_path'], 0, winreg.KEY_QUERY_VALUE | winreg.KEY_SET_VALUE) as key:
                value, reg_type = winreg.QueryValueEx(key, row['value_name'])
                saved['registry_value'] = value; saved['registry_type'] = int(reg_type)
                winreg.DeleteValue(key, row['value_name'])
        elif row.get('source_type') == 'startup_file':
            src = Path(row['file_path'])
            DISABLED_DIR.mkdir(parents=True, exist_ok=True)
            dest = DISABLED_DIR / f"{abs(hash(source_id))}_{src.name}"
            shutil.move(str(src), str(dest))
            saved['original_path'] = str(src); saved['backup_path'] = str(dest)
        else:
            return {'success': False, 'message': 'Origen no compatible.'}
        state['items'][source_id] = saved; _write_state(state)
        return {'success': True, 'message': f"{row.get('name') or 'Elemento'} fue deshabilitado del inicio. Puedes restaurarlo desde CorePulse.", 'source_id': source_id}
    except Exception as exc:
        return {'success': False, 'message': f'No se pudo deshabilitar: {type(exc).__name__}: {exc}'}


def restore_startup_item(source_id: str) -> Dict[str, Any]:
    state = _read_state(); items = state.get('items') if isinstance(state.get('items'), dict) else {}
    saved = items.get(source_id)
    if not isinstance(saved, dict):
        return {'success': False, 'message': 'No existe una copia reversible para este elemento.'}
    try:
        if saved.get('source_type') == 'registry':
            import winreg
            hive = winreg.HKEY_CURRENT_USER if saved.get('scope') == 'HKCU' else None
            if hive is None:
                raise PermissionError('Ámbito global no permitido')
            with winreg.CreateKeyEx(hive, saved['registry_path'], 0, winreg.KEY_QUERY_VALUE | winreg.KEY_SET_VALUE) as key:
                try:
                    current, _current_type = winreg.QueryValueEx(key, saved['value_name'])
                    return {'success': False, 'message': 'La entrada volvió a existir fuera de CorePulse. No se sobrescribirá un cambio externo.'}
                except FileNotFoundError:
                    pass
                winreg.SetValueEx(key, saved['value_name'], 0, int(saved.get('registry_type') or winreg.REG_SZ), saved.get('registry_value'))
        elif saved.get('source_type') == 'startup_file':
            src = Path(saved['backup_path']); dest = Path(saved['original_path'])
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                return {'success': False, 'message': 'Ya existe un archivo con el mismo nombre en la carpeta de inicio.'}
            shutil.move(str(src), str(dest))
        else:
            return {'success': False, 'message': 'Origen no compatible.'}
        items.pop(source_id, None); _write_state(state)
        return {'success': True, 'message': f"{saved.get('name') or 'Elemento'} fue restaurado al inicio de Windows.", 'source_id': source_id}
    except Exception as exc:
        return {'success': False, 'message': f'No se pudo restaurar: {type(exc).__name__}: {exc}'}


__all__ = ['collect_startup_items','disable_startup_item','restore_startup_item','STATE_FILE']
