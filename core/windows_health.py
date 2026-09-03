"""Analizadores de Windows para inicio, servicios, eventos, drivers, cambios y restore.

Todas las operaciones degradan a N/A fuera de Windows y ninguna desactiva servicios
ni controladores automáticamente.
"""
from __future__ import annotations

import ctypes
import json
import os
import platform
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List

import psutil

ROOT = Path(__file__).resolve().parents[1]
HW_STATE = ROOT / 'data' / 'hardware_baseline.json'


def _ps(script: str, timeout: int = 25):
    if platform.system() != 'Windows':
        return None, 'Windows requerido'
    cmd = ['powershell.exe', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-Command', script]
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if cp.returncode != 0:
            return None, (cp.stderr or cp.stdout or f'PowerShell exit {cp.returncode}').strip()
        return (cp.stdout or '').strip(), None
    except Exception as exc:
        return None, str(exc)


def _json_ps(script: str, timeout: int = 30):
    out, err = _ps(f"$ErrorActionPreference='Stop'; {script} | ConvertTo-Json -Depth 5 -Compress", timeout=timeout)
    if err: return [], err
    if not out: return [], None
    try:
        obj = json.loads(out)
        return obj if isinstance(obj, list) else [obj], None
    except Exception as exc:
        return [], f'JSON PowerShell inválido: {exc}'


def is_admin():
    if platform.system() != 'Windows': return False
    try: return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception: return False


def analyze_startup() -> Dict[str, Any]:
    script = r"""
    Get-CimInstance Win32_StartupCommand | Select-Object Name,Command,Location,User
    """
    rows, err = _json_ps(script)
    # Windows Diagnostics-Performance Event 101 registra aplicaciones que degradaron el arranque.
    perf_script = r"""
    $start=(Get-Date).AddDays(-30);
    Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-Diagnostics-Performance/Operational'; Id=101; StartTime=$start} -ErrorAction SilentlyContinue |
      Select-Object -First 80 TimeCreated,Message
    """
    perf_rows, _perf_err = _json_ps(perf_script, timeout=20)
    perf_text = '\n'.join(str(x.get('Message') or '') for x in perf_rows if isinstance(x, dict)).lower()
    procs = {p.info.get('name','').lower(): p.info for p in psutil.process_iter(['name','memory_info'])}
    items = []
    for row in rows:
        if not isinstance(row, dict): continue
        cmd = str(row.get('Command') or '')
        exe = Path(cmd.strip('"').split('"')[0].split()[0]).name.lower() if cmd else ''
        pinfo = procs.get(exe)
        mem = None
        if pinfo and pinfo.get('memory_info') is not None:
            try: mem = pinfo['memory_info'].rss / (1024*1024)
            except Exception: pass
        name = str(row.get('Name') or '')
        degraded = bool((exe and exe in perf_text) or (name and name.lower() in perf_text))
        impact = 'ALTO (evento de degradación)' if degraded else 'MEDIO' if mem is not None and mem >= 150 else 'BAJO' if mem is not None else 'NO_MEDIDO'
        items.append({
            'name': row.get('Name'), 'command': cmd, 'location': row.get('Location'), 'user': row.get('User'),
            'running_memory_mb': mem, 'impact': impact, 'degradation_event_seen': degraded,
            'impact_basis': 'Evento 101 de Diagnostics-Performance cuando existe; RAM actual sólo como contexto secundario',
        })
    items.sort(key=lambda x: (bool(x.get('degradation_event_seen')), x.get('running_memory_mb') or 0), reverse=True)
    return {'items': items, 'count': len(items), 'error': err, 'source': 'Win32_StartupCommand + Diagnostics-Performance 101 + psutil', 'policy': 'NO_AUTO_DISABLE'}


def analyze_services(limit: int = 250) -> Dict[str, Any]:
    script = rf"""
    Get-CimInstance Win32_Service | Select-Object Name,DisplayName,State,StartMode,PathName,ProcessId | Select-Object -First {int(limit)}
    """
    rows, err = _json_ps(script, timeout=35)
    items = []
    for row in rows:
        if not isinstance(row, dict): continue
        pid = row.get('ProcessId')
        mem = None
        if pid:
            try: mem = psutil.Process(int(pid)).memory_info().rss / (1024*1024)
            except Exception: pass
        path = str(row.get('PathName') or '')
        windows_component = ('\\windows\\system32' in path.lower() or path.lower().startswith('c:\\windows'))
        items.append({**row, 'memory_mb': mem, 'windows_component': windows_component,
                      'load_flag': 'PESADO' if mem is not None and mem >= 300 else 'NORMAL' if mem is not None else 'N/A',
                      'action_policy': 'OBSERVE_ONLY_CRITICAL_SERVICES_NEVER_AUTO_DISABLED'})
    items.sort(key=lambda x: (x.get('memory_mb') is not None, x.get('memory_mb') or 0), reverse=True)
    return {'items': items, 'count': len(items), 'error': err, 'source': 'Win32_Service + psutil', 'policy': 'ANALYZE_ONLY'}


def analyze_crashes(days: int = 7, max_events: int = 120) -> Dict[str, Any]:
    days = max(1, min(90, int(days)))
    script = rf"""
    $start=(Get-Date).AddDays(-{days});
    $sys=@(Get-WinEvent -FilterHashtable @{{LogName='System'; StartTime=$start; Id=41,18,19,20,46,6008,1001}} -ErrorAction SilentlyContinue);
    $app=@(Get-WinEvent -FilterHashtable @{{LogName='Application'; StartTime=$start; Id=1000,1002}} -ErrorAction SilentlyContinue);
    @($sys+$app) | Sort-Object TimeCreated -Descending | Select-Object -First {int(max_events)} TimeCreated,Id,ProviderName,LevelDisplayName,Message
    """
    rows, err = _json_ps(script, timeout=45)
    items = []
    counts = {'bsod_bugcheck':0,'whea':0,'kernel_power':0,'app_error':0,'app_hang':0,'unexpected_shutdown':0}
    for row in rows:
        if not isinstance(row, dict): continue
        eid = int(row.get('Id') or 0); provider = str(row.get('ProviderName') or '')
        kind = 'other'
        if eid == 1001 or 'bugcheck' in provider.lower() or 'systemerrorreporting' in provider.lower(): kind='bsod_bugcheck'; counts[kind]+=1
        elif 'whea' in provider.lower() or eid in (18,19,20,46): kind='whea'; counts[kind]+=1
        elif eid == 41: kind='kernel_power'; counts[kind]+=1
        elif eid == 1000: kind='app_error'; counts[kind]+=1
        elif eid == 1002: kind='app_hang'; counts[kind]+=1
        elif eid == 6008: kind='unexpected_shutdown'; counts[kind]+=1
        items.append({**row, 'kind':kind, 'Message': str(row.get('Message') or '')[:800]})
    severity = 'CRITICAL' if counts['whea'] or counts['bsod_bugcheck'] else 'WARNING' if counts['kernel_power'] or counts['unexpected_shutdown'] else 'INFO' if counts['app_error'] or counts['app_hang'] else 'NORMAL'
    return {'items': items, 'counts': counts, 'severity': severity, 'days': days, 'error': err, 'source': 'Windows Event Log / Get-WinEvent'}


def analyze_drivers(limit: int = 400) -> Dict[str, Any]:
    script = r"""
    $dev=@{}; Get-CimInstance Win32_PnPEntity -ErrorAction SilentlyContinue | ForEach-Object { if($_.PNPDeviceID){$dev[$_.PNPDeviceID]=$_.Status.ToString()+'|'+$_.ConfigManagerErrorCode} };
    Get-CimInstance Win32_PnPSignedDriver | Select-Object -First __LIMIT__ | ForEach-Object {
      $st=$dev[$_.DeviceID]; $parts=if($st){$st -split '\|'}else{@('N/A','')};
      [pscustomobject]@{DeviceName=$_.DeviceName;DeviceClass=$_.DeviceClass;DriverVersion=$_.DriverVersion;DriverProviderName=$_.DriverProviderName;DriverDate=$_.DriverDate;IsSigned=$_.IsSigned;InfName=$_.InfName;DeviceID=$_.DeviceID;DeviceStatus=$parts[0];ConfigManagerErrorCode=if($parts.Count -gt 1){$parts[1]}else{$null}}
    }
    """.replace('__LIMIT__', str(int(limit)))
    rows, err = _json_ps(script, timeout=50)
    now = time.time(); items=[]; unsigned=0; old=0; problems=0
    for row in rows:
        if not isinstance(row, dict): continue
        signed = row.get('IsSigned')
        if signed is False: unsigned += 1
        date = str(row.get('DriverDate') or '')
        age_years = None
        m = re.search(r'Date\((\d+)', date)
        if m:
            try: age_years=(now-(int(m.group(1))/1000.0))/(365.25*86400)
            except Exception: pass
        elif date:
            try:
                from datetime import datetime
                parsed = datetime.fromisoformat(date.replace('Z','+00:00'))
                age_years = (now - parsed.timestamp()) / (365.25*86400)
            except Exception:
                pass
        if age_years is not None and age_years > 5: old += 1
        code = row.get('ConfigManagerErrorCode')
        try: code_num=int(code) if code not in (None,'') else 0
        except Exception: code_num=0
        device_bad = code_num != 0 or str(row.get('DeviceStatus') or '').upper() not in ('OK','N/A','')
        if signed is False or device_bad: problems += 1
        status = 'DEVICE_PROBLEM' if device_bad else 'UNSIGNED' if signed is False else 'OLD' if age_years is not None and age_years > 5 else 'OK'
        items.append({**row, 'age_years': age_years, 'status': status})
    items.sort(key=lambda x: (x.get('status') in ('DEVICE_PROBLEM','UNSIGNED'), x.get('status')=='OLD', x.get('age_years') or 0), reverse=True)
    return {'items': items, 'count': len(items), 'unsigned': unsigned, 'device_problems': problems, 'older_than_5y': old, 'error': err, 'source': 'Win32_PnPSignedDriver + Win32_PnPEntity', 'note': 'Antigüedad no implica por sí sola un problema.'}


def _stable_inventory(inv: Dict[str, Any]):
    if not isinstance(inv, dict): return {}
    cpu = inv.get('cpu') if isinstance(inv.get('cpu'), dict) else {}
    ram = inv.get('ram') if isinstance(inv.get('ram'), dict) else {}
    storage = inv.get('storage') if isinstance(inv.get('storage'), list) else []
    gpus = inv.get('gpus') if isinstance(inv.get('gpus'), list) else []
    ident = inv.get('identity') if isinstance(inv.get('identity'), dict) else {}
    bios = ident.get('bios') if isinstance(ident.get('bios'), dict) else {}
    board = ident.get('motherboard') if isinstance(ident.get('motherboard'), dict) else {}
    return {
        'identity': {
            'manufacturer': ident.get('manufacturer'), 'model': ident.get('model'),
            'bios_version': bios.get('version'), 'bios_release_date': bios.get('release_date'),
            'motherboard_manufacturer': board.get('manufacturer'), 'motherboard_model': board.get('model'),
        },
        'cpu': {'name': cpu.get('name')},
        'ram': {
            'module_total_gb': ram.get('module_total_gb'), 'module_count': ram.get('module_count'),
            'modules': [{k:m.get(k) for k in ('capacity_gb','manufacturer','part_number','slot','bank','configured_speed_mhz','speed_mhz')} for m in ram.get('modules',[]) if isinstance(m,dict)]
        },
        'gpus': [{k:g.get(k) for k in ('name','driver_version','pnp_device_id')} for g in gpus if isinstance(g,dict)],
        'storage': [{k:s.get(k) for k in ('name','model','serial','serial_number','firmware','capacity_gb','total_space_gb')} for s in storage if isinstance(s,dict)],
    }


def compare_hardware_inventory(inventory: Dict[str, Any], save_if_missing=True) -> Dict[str, Any]:
    current = _stable_inventory(inventory)
    previous = None
    try:
        if HW_STATE.exists(): previous = json.loads(HW_STATE.read_text(encoding='utf-8'))
    except Exception: previous = None
    if previous is None:
        if save_if_missing:
            HW_STATE.parent.mkdir(parents=True, exist_ok=True); HW_STATE.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding='utf-8')
        return {'baseline_exists': False, 'changes': [], 'current': current}
    changes=[]
    for key in ('identity','cpu','ram','gpus','storage'):
        if previous.get(key) != current.get(key): changes.append({'component': key.upper(), 'before': previous.get(key), 'after': current.get(key)})
    return {'baseline_exists': True, 'changes': changes, 'current': current, 'previous': previous}


def save_hardware_baseline(inventory: Dict[str, Any]):
    current = _stable_inventory(inventory)
    HW_STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp=HW_STATE.with_suffix('.tmp'); tmp.write_text(json.dumps(current,ensure_ascii=False,indent=2),encoding='utf-8'); tmp.replace(HW_STATE)
    return current


def restore_point_status() -> Dict[str, Any]:
    if platform.system() != 'Windows': return {'available': False, 'admin': False, 'reason': 'Windows requerido'}
    script = r"Get-ComputerRestorePoint -ErrorAction Stop | Sort-Object SequenceNumber -Descending | Select-Object -First 5 SequenceNumber,Description,CreationTime,RestorePointType"
    rows, err = _json_ps(script, timeout=20)
    return {'available': err is None, 'admin': is_admin(), 'points': rows, 'error': err, 'source': 'System Restore'}


def create_restore_point(description='CorePulse - antes de cambios') -> Dict[str, Any]:
    if platform.system() != 'Windows': return {'ok': False, 'error': 'Windows requerido'}
    if not is_admin(): return {'ok': False, 'error': 'Se requieren privilegios de administrador'}
    safe = str(description).replace("'", "''")[:120]
    out, err = _ps(f"Checkpoint-Computer -Description '{safe}' -RestorePointType 'MODIFY_SETTINGS' -ErrorAction Stop; 'OK'", timeout=90)
    return {'ok': err is None and 'OK' in (out or ''), 'error': err, 'description': description, 'source': 'Checkpoint-Computer'}
