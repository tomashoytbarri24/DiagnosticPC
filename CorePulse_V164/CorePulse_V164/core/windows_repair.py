"""Centro seguro de reparación de Windows para CorePulse.

V127

Principios:
- nunca confundir DISM/SFC con rollback de Tweaks;
- ninguna reparación se ejecuta automáticamente;
- las acciones online requieren Windows + privilegios de administrador; la UI V127 puede elevar sólo la consola PowerShell mediante UAC;
- conservar stdout/stderr real y clasificar sólo cuando la salida lo permite;
- si la salida no es concluyente, informar COMPLETED_UNCLASSIFIED en vez de inventar NORMAL/REPAIRED.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
from core.runtime_paths import log_dir
import re
import time
from typing import Callable, Iterable, Optional

from core.windows_commands import CommandResult, is_admin, run_hidden

LOG_DIR = log_dir()
IS_WINDOWS = os.name == 'nt'

POLICY = 'EXPLICIT_USER_ACTION_ONLY'
ROLLBACK_POLICY = 'NOT_A_TWEAK_ROLLBACK'


@dataclass(frozen=True)
class RepairStep:
    key: str
    label: str
    args: tuple[str, ...]
    timeout: float
    mutating: bool


DIAGNOSTIC_STEPS = (
    RepairStep(
        'dism_checkhealth',
        'DISM · CheckHealth',
        ('dism.exe', '/Online', '/Cleanup-Image', '/CheckHealth'),
        120.0,
        False,
    ),
    RepairStep(
        'dism_scanhealth',
        'DISM · ScanHealth',
        ('dism.exe', '/Online', '/Cleanup-Image', '/ScanHealth'),
        1800.0,
        False,
    ),
    RepairStep(
        'sfc_verifyonly',
        'SFC · VerifyOnly',
        ('sfc.exe', '/verifyonly'),
        1800.0,
        False,
    ),
)

REPAIR_STEPS = (
    RepairStep(
        'dism_restorehealth',
        'DISM · RestoreHealth',
        ('dism.exe', '/Online', '/Cleanup-Image', '/RestoreHealth'),
        3600.0,
        True,
    ),
    RepairStep(
        'sfc_scannow',
        'SFC · ScanNow',
        ('sfc.exe', '/scannow'),
        3600.0,
        True,
    ),
    RepairStep(
        'dism_post_checkhealth',
        'DISM · verificación posterior',
        ('dism.exe', '/Online', '/Cleanup-Image', '/CheckHealth'),
        120.0,
        False,
    ),
)


VISIBLE_CONSOLE_POLICY = 'VISIBLE_ELEVATED_POWERSHELL'


def _ps_quote(value: object) -> str:
    """Literal PowerShell de comillas simples para rutas/argumentos controlados."""
    return "'" + str(value).replace("'", "''") + "'"


def _write_visible_powershell_script(kind: str, steps: tuple[RepairStep, ...], job_dir: Path) -> Path:
    """Crea un script temporal que muestra DISM/SFC en una consola PowerShell real.

    La consola elevada es la fuente visual del progreso. Cada etapa conserva la
    salida real y su código de retorno en archivos UTF-8 que CorePulse importa al
    finalizar; no se sintetizan porcentajes ni estados.
    """
    job_dir.mkdir(parents=True, exist_ok=True)
    script_path = job_dir / f'corepulse_windows_{kind}.ps1'
    session_path = job_dir / 'session.json'
    lines = [
        "$ErrorActionPreference = 'Continue'",
        "$ProgressPreference = 'Continue'",
        "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8",
        "[Console]::InputEncoding = [System.Text.Encoding]::UTF8",
        "$OutputEncoding = [System.Text.Encoding]::UTF8",
        "chcp.com 65001 | Out-Null",
        "$Host.UI.RawUI.WindowTitle = 'CorePulse · DISM / SFC · Administrador'",
        "function Write-CorePulseUtf8([string]$Path, [string]$Text) {",
        "    $utf8 = New-Object System.Text.UTF8Encoding($false)",
        "    [System.IO.File]::WriteAllText($Path, $Text, $utf8)",
        "}",
        "function Invoke-CorePulseRepairStep {",
        "    param([string]$Key, [string]$Label, [string]$Exe, [string[]]$Args, [string]$OutputPath, [string]$MetaPath)",
        "    Write-Host ''",
        "    Write-Host ('=' * 78) -ForegroundColor DarkCyan",
        "    Write-Host ('CorePulse > ' + $Label) -ForegroundColor Cyan",
        "    Write-Host ('Comando: ' + $Exe + ' ' + ($Args -join ' ')) -ForegroundColor Gray",
        "    Write-Host ('=' * 78) -ForegroundColor DarkCyan",
        "    $sw = [System.Diagnostics.Stopwatch]::StartNew()",
        "    $captured = @()",
        "    try {",
        "        & $Exe @Args 2>&1 | Tee-Object -Variable captured | Out-Host",
        "        $rc = $LASTEXITCODE",
        "        if ($null -eq $rc) { $rc = 0 }",
        "    } catch {",
        "        $captured = @($captured) + @($_ | Out-String)",
        "        Write-Host ($_ | Out-String) -ForegroundColor Red",
        "        $rc = 1",
        "    }",
        "    $sw.Stop()",
        "    $text = ((@($captured) | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine)",
        "    Write-CorePulseUtf8 -Path $OutputPath -Text $text",
        "    $meta = [ordered]@{ key=$Key; label=$Label; returncode=[int]$rc; duration_s=[Math]::Round($sw.Elapsed.TotalSeconds,2); finished_at=(Get-Date).ToString('o') } | ConvertTo-Json -Compress",
        "    Write-CorePulseUtf8 -Path $MetaPath -Text $meta",
        "    if ($rc -eq 0) { Write-Host ('Finalizado: ' + $Label + ' (código 0)') -ForegroundColor Green } else { Write-Host ('Finalizado: ' + $Label + ' (código ' + $rc + ')') -ForegroundColor Yellow }",
        "    return [int]$rc",
        "}",
        "$identity = [Security.Principal.WindowsIdentity]::GetCurrent()",
        "$principal = New-Object Security.Principal.WindowsPrincipal($identity)",
        "$isAdmin = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)",
        "$session = [ordered]@{ admin=[bool]$isAdmin; pid=$PID; started_at=(Get-Date).ToString('o'); kind=" + _ps_quote(kind) + " } | ConvertTo-Json -Compress",
        "Write-CorePulseUtf8 -Path " + _ps_quote(session_path) + " -Text $session",
        "Clear-Host",
        "Write-Host 'CorePulse · Reparación de Windows' -ForegroundColor Cyan",
        "Write-Host 'Esta consola muestra la ejecución REAL de DISM/SFC.' -ForegroundColor Gray",
        "Write-Host ('Administrador: ' + $isAdmin) -ForegroundColor Gray",
        "$batchExit = 0",
    ]
    for idx, step in enumerate(steps, start=1):
        out_path = job_dir / f'{idx:02d}_{step.key}.out.txt'
        meta_path = job_dir / f'{idx:02d}_{step.key}.meta.json'
        exe = step.args[0]
        args = list(step.args[1:])
        ps_args = '@(' + ','.join(_ps_quote(x) for x in args) + ')'
        lines.extend([
            "$stepRc = Invoke-CorePulseRepairStep -Key " + _ps_quote(step.key) + " -Label " + _ps_quote(step.label) + " -Exe " + _ps_quote(exe) + " -Args " + ps_args + " -OutputPath " + _ps_quote(out_path) + " -MetaPath " + _ps_quote(meta_path),
            "if ($stepRc -ne 0) { $batchExit = 1 }",
        ])
    lines.extend([
        "Write-Host ''",
        "Write-Host ('=' * 78) -ForegroundColor DarkCyan",
        "Write-Host 'CorePulse recibió los resultados. Esta ventana se cerrará automáticamente.' -ForegroundColor Cyan",
        "Write-Host 'Puedes revisar la salida completa dentro de la pestaña Reparación.' -ForegroundColor Gray",
        "Start-Sleep -Seconds 4",
        "exit $batchExit",
    ])
    script_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return script_path


def _launch_visible_elevated_powershell(script_path: Path) -> dict:
    """Abre PowerShell visible usando UAC y espera a que finalice.

    ShellExecuteEx permite elevar únicamente la consola de reparación; CorePulse
    puede seguir ejecutándose como usuario estándar y luego leer los resultados.
    """
    if not IS_WINDOWS:
        return {'started': False, 'exit_code': None, 'error': 'Windows requerido', 'cancelled': False}
    try:
        from ctypes import wintypes

        class SHELLEXECUTEINFOW(ctypes.Structure):
            _fields_ = [
                ('cbSize', wintypes.DWORD),
                ('fMask', wintypes.ULONG),
                ('hwnd', wintypes.HWND),
                ('lpVerb', wintypes.LPCWSTR),
                ('lpFile', wintypes.LPCWSTR),
                ('lpParameters', wintypes.LPCWSTR),
                ('lpDirectory', wintypes.LPCWSTR),
                ('nShow', ctypes.c_int),
                ('hInstApp', wintypes.HINSTANCE),
                ('lpIDList', ctypes.c_void_p),
                ('lpClass', wintypes.LPCWSTR),
                ('hkeyClass', wintypes.HKEY),
                ('dwHotKey', wintypes.DWORD),
                ('hIcon', wintypes.HANDLE),
                ('hProcess', wintypes.HANDLE),
            ]

        shell32 = ctypes.WinDLL('shell32', use_last_error=True)
        kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        shell32.ShellExecuteExW.argtypes = [ctypes.POINTER(SHELLEXECUTEINFOW)]
        shell32.ShellExecuteExW.restype = wintypes.BOOL
        kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel32.WaitForSingleObject.restype = wintypes.DWORD
        kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel32.GetExitCodeProcess.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL

        SEE_MASK_NOCLOSEPROCESS = 0x00000040
        SW_SHOWNORMAL = 1
        INFINITE = 0xFFFFFFFF
        params = f'-NoLogo -NoProfile -ExecutionPolicy Bypass -File "{script_path}"'
        sei = SHELLEXECUTEINFOW()
        sei.cbSize = ctypes.sizeof(SHELLEXECUTEINFOW)
        sei.fMask = SEE_MASK_NOCLOSEPROCESS
        sei.hwnd = None
        sei.lpVerb = 'runas'
        sei.lpFile = 'powershell.exe'
        sei.lpParameters = params
        sei.lpDirectory = str(script_path.parent)
        sei.nShow = SW_SHOWNORMAL
        if not shell32.ShellExecuteExW(ctypes.byref(sei)):
            code = ctypes.get_last_error()
            return {
                'started': False,
                'exit_code': None,
                'cancelled': code == 1223,
                'error': 'El usuario canceló la solicitud de administrador.' if code == 1223 else f'Windows no pudo abrir PowerShell elevado (código {code}).',
            }
        if not sei.hProcess:
            return {'started': False, 'exit_code': None, 'cancelled': False, 'error': 'Windows abrió PowerShell sin entregar un identificador de proceso.'}
        try:
            kernel32.WaitForSingleObject(sei.hProcess, INFINITE)
            code = wintypes.DWORD(0)
            if not kernel32.GetExitCodeProcess(sei.hProcess, ctypes.byref(code)):
                return {'started': True, 'exit_code': None, 'cancelled': False, 'error': 'No se pudo leer el código de salida de PowerShell.'}
            return {'started': True, 'exit_code': int(code.value), 'cancelled': False, 'error': None}
        finally:
            kernel32.CloseHandle(sei.hProcess)
    except Exception as exc:
        return {'started': False, 'exit_code': None, 'cancelled': False, 'error': f'{type(exc).__name__}: {exc}'}


def _read_json_utf8(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding='utf-8-sig'))
    except Exception:
        return {}


def _run_steps_visible_powershell(
    kind: str,
    steps: tuple[RepairStep, ...],
    *,
    progress: Optional[Callable[[dict], None]] = None,
) -> dict:
    """Ejecuta DISM/SFC en PowerShell visible y elevado, luego importa la salida."""
    started = time.time()
    base = {
        'kind': kind,
        'started_at': started,
        'started_at_iso': datetime.now().isoformat(timespec='seconds'),
        'windows': IS_WINDOWS,
        'admin': is_admin(),
        'policy': POLICY,
        'rollback_policy': ROLLBACK_POLICY,
        'execution_mode': VISIBLE_CONSOLE_POLICY,
        'powershell_visible': True,
        'powershell_admin': None,
        'steps': [],
    }
    if not IS_WINDOWS:
        base.update({
            'ok': False, 'overall_state': 'UNAVAILABLE',
            'summary': 'Esta herramienta sólo está disponible en Windows.',
            'error': 'Windows requerido', 'duration_s': 0.0, 'log_path': None,
        })
        return base

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    job_dir = LOG_DIR / f'windows_repair_console_{kind}_{stamp}'
    try:
        script_path = _write_visible_powershell_script(kind, steps, job_dir)
    except Exception as exc:
        base.update({
            'ok': False, 'overall_state': 'ATTENTION_REQUIRED',
            'summary': 'No se pudo preparar la consola de reparación.',
            'error': f'{type(exc).__name__}: {exc}',
            'duration_s': round(time.time() - started, 2), 'log_path': None,
        })
        return base

    if progress:
        try:
            progress({
                'event': 'console', 'index': 1, 'total': len(steps),
                'label': 'PowerShell administrador abierto · progreso visible en la consola',
            })
        except Exception:
            pass

    launched = _launch_visible_elevated_powershell(script_path)
    base['launcher_exit_code'] = launched.get('exit_code')
    if not launched.get('started'):
        state = 'ADMIN_REQUIRED' if launched.get('cancelled') else 'ATTENTION_REQUIRED'
        base.update({
            'ok': False,
            'overall_state': state,
            'summary': launched.get('error') or 'No se pudo abrir PowerShell.',
            'error': launched.get('error'),
            'duration_s': round(time.time() - started, 2),
            'finished_at_iso': datetime.now().isoformat(timespec='seconds'),
            'job_dir': str(job_dir),
        })
        try:
            base['log_path'] = _write_log(kind, base)
        except Exception:
            base['log_path'] = None
        return base

    session = _read_json_utf8(job_dir / 'session.json')
    if isinstance(session.get('admin'), bool):
        base['powershell_admin'] = session.get('admin')
    base['powershell_pid'] = session.get('pid')
    base['job_dir'] = str(job_dir)

    for index, step in enumerate(steps, start=1):
        out_path = job_dir / f'{index:02d}_{step.key}.out.txt'
        meta_path = job_dir / f'{index:02d}_{step.key}.meta.json'
        meta = _read_json_utf8(meta_path)
        try:
            raw = out_path.read_text(encoding='utf-8-sig', errors='replace') if out_path.exists() else ''
        except Exception as exc:
            raw = ''
            meta = dict(meta)
            meta['read_error'] = f'{type(exc).__name__}: {exc}'
        rc_value = meta.get('returncode')
        try:
            rc = int(rc_value) if rc_value is not None else None
        except Exception:
            rc = None
        missing = not meta_path.exists()
        result = CommandResult(
            ok=(rc == 0 and not missing),
            args=tuple(step.args),
            returncode=rc,
            stdout=raw,
            stderr='',
            error='PowerShell no devolvió el resultado de esta etapa.' if missing else None,
            timed_out=False,
        )
        classified = classify_output(step.key, result)
        duration = meta.get('duration_s')
        try:
            duration_s = round(float(duration), 2)
        except Exception:
            duration_s = 0.0
        row = {
            'key': step.key,
            'label': step.label,
            'command': list(step.args),
            'mutating': step.mutating,
            'ok': bool(result.ok),
            'returncode': result.returncode,
            'timed_out': False,
            'duration_s': duration_s,
            'state': classified['state'],
            'severity': classified['severity'],
            'message': classified['message'],
            'restart_maybe_required': _needs_restart(raw),
            'stdout': raw,
            'stderr': '',
            'error': result.error,
            'capture': 'POWERSHELL_VISIBLE_MERGED_STREAM',
        }
        base['steps'].append(row)
        if progress:
            try:
                progress({'event': 'done', 'index': index, 'total': len(steps), **row})
            except Exception:
                pass

    state, summary = _overall(base['steps'], mutating=any(x.mutating for x in steps))
    if base.get('powershell_admin') is False:
        state = 'ATTENTION_REQUIRED'
        summary = 'PowerShell no confirmó privilegios de administrador; revisa la salida real.'
    base.update({
        'ok': state in ('CLEAN', 'COMPLETED', 'REPAIRED'),
        'overall_state': state,
        'summary': summary,
        'restart_maybe_required': any(bool(x.get('restart_maybe_required')) for x in base['steps']),
        'duration_s': round(time.time() - started, 2),
        'finished_at_iso': datetime.now().isoformat(timespec='seconds'),
    })
    try:
        base['log_path'] = _write_log(kind, base)
    except Exception as exc:
        base['log_path'] = None
        base['log_error'] = f'{type(exc).__name__}: {exc}'
    return base


def run_integrity_diagnostic_visible(progress: Optional[Callable[[dict], None]] = None) -> dict:
    """Diagnóstico DISM/SFC en PowerShell visible con elevación UAC independiente."""
    return _run_steps_visible_powershell('diagnostic', DIAGNOSTIC_STEPS, progress=progress)


def run_windows_repair_visible(progress: Optional[Callable[[dict], None]] = None) -> dict:
    """Reparación DISM/SFC en PowerShell visible con elevación UAC independiente."""
    return _run_steps_visible_powershell('repair', REPAIR_STEPS, progress=progress)


def _normalize(text: str) -> str:
    value = str(text or '').lower()
    value = value.replace('\r', ' ').replace('\n', ' ')
    return re.sub(r'\s+', ' ', value).strip()


def _combined(result: CommandResult) -> str:
    return '\n'.join(x for x in (result.stdout, result.stderr, result.error or '') if x).strip()


def _contains_any(text: str, tokens: Iterable[str]) -> bool:
    low = _normalize(text)
    return any(_normalize(token) in low for token in tokens)


def classify_output(step_key: str, result: CommandResult) -> dict:
    """Clasifica sólo frases conocidas de DISM/SFC en inglés/español.

    La clasificación nunca sustituye el return code ni el log crudo. Ante una
    salida desconocida pero rc=0 se usa COMPLETED_UNCLASSIFIED.
    """
    raw = _combined(result)
    low = _normalize(raw)

    if result.timed_out:
        return {'state': 'TIMEOUT', 'severity': 'ERROR', 'message': 'La operación superó el tiempo límite.'}
    if result.error and result.returncode is None:
        return {'state': 'FAILED', 'severity': 'ERROR', 'message': result.error}
    if result.returncode not in (0, None):
        return {
            'state': 'FAILED',
            'severity': 'ERROR',
            'message': f'Windows devolvió el código {result.returncode}.',
        }

    # DISM: sin corrupción.
    clean_dism = (
        'no component store corruption detected',
        'the component store corruption was repaired',
        'no se detectó ningún daño en el almacén de componentes',
        'no se detecto ningun daño en el almacen de componentes',
        'la corrupción del almacén de componentes se reparó',
        'la corrupcion del almacen de componentes se reparo',
    )
    repairable_dism = (
        'the component store is repairable',
        'component store corruption detected',
        'el almacén de componentes se puede reparar',
        'el almacen de componentes se puede reparar',
        'se detectó corrupción en el almacén de componentes',
        'se detecto corrupcion en el almacen de componentes',
    )
    nonrepairable_dism = (
        'the component store cannot be repaired',
        'el almacén de componentes no se puede reparar',
        'el almacen de componentes no se puede reparar',
    )
    dism_repaired = (
        'the restore operation completed successfully',
        'the operation completed successfully',
        'la operación de restauración se completó correctamente',
        'la operacion de restauracion se completo correctamente',
        'la operación se completó correctamente',
        'la operacion se completo correctamente',
    )

    # SFC: frases oficiales habituales.
    sfc_clean = (
        'windows resource protection did not find any integrity violations',
        'protección de recursos de windows no encontró ninguna infracción de integridad',
        'proteccion de recursos de windows no encontro ninguna infraccion de integridad',
    )
    sfc_repaired = (
        'windows resource protection found corrupt files and successfully repaired them',
        'protección de recursos de windows encontró archivos dañados y los reparó correctamente',
        'proteccion de recursos de windows encontro archivos dañados y los reparo correctamente',
    )
    sfc_unrepaired = (
        'windows resource protection found corrupt files but was unable to fix some of them',
        'protección de recursos de windows encontró archivos dañados pero no pudo corregir algunos',
        'proteccion de recursos de windows encontro archivos dañados pero no pudo corregir algunos',
    )
    sfc_corruption_found = (
        'windows resource protection found integrity violations',
        'integrity violations were found',
        'se encontraron infracciones de integridad',
        'encontró infracciones de integridad',
        'encontro infracciones de integridad',
    )

    if step_key.startswith('dism_'):
        if step_key == 'dism_restorehealth' and _contains_any(low, dism_repaired):
            return {'state': 'REPAIRED', 'severity': 'OK', 'message': 'DISM completó la restauración del almacén de componentes.'}
        if _contains_any(low, nonrepairable_dism):
            return {'state': 'NOT_REPAIRABLE', 'severity': 'ERROR', 'message': 'DISM informa que el almacén no puede repararse con esta operación.'}
        # Comprobar CLEAN antes de REPAIRABLE: la frase oficial
        # "No component store corruption detected" contiene literalmente
        # "component store corruption detected" y produciría un falso positivo.
        if _contains_any(low, clean_dism):
            return {'state': 'CLEAN', 'severity': 'OK', 'message': 'DISM no informa corrupción pendiente.'}
        if _contains_any(low, repairable_dism):
            return {'state': 'REPAIRABLE', 'severity': 'WARNING', 'message': 'Windows detectó corrupción reparable en el almacén de componentes.'}

    if step_key.startswith('sfc_'):
        if _contains_any(low, sfc_unrepaired):
            return {'state': 'UNREPAIRED', 'severity': 'ERROR', 'message': 'SFC encontró archivos dañados que no pudo reparar por completo.'}
        if _contains_any(low, sfc_repaired):
            return {'state': 'REPAIRED', 'severity': 'OK', 'message': 'SFC encontró archivos dañados y los reparó.'}
        if _contains_any(low, sfc_clean):
            return {'state': 'CLEAN', 'severity': 'OK', 'message': 'SFC no encontró infracciones de integridad.'}
        if _contains_any(low, sfc_corruption_found):
            return {'state': 'REPAIRABLE', 'severity': 'WARNING', 'message': 'SFC detectó infracciones de integridad.'}

    if result.ok:
        return {
            'state': 'COMPLETED_UNCLASSIFIED',
            'severity': 'INFO',
            'message': 'Windows completó el comando, pero CorePulse no clasificará una salida no reconocida.',
        }
    return {'state': 'FAILED', 'severity': 'ERROR', 'message': 'La operación no se completó correctamente.'}


def _needs_restart(text: str) -> bool:
    return _contains_any(text, (
        'restart windows', 'restart your computer', 'reboot',
        'reinicie windows', 'reiniciar el equipo', 'reinicie el equipo', 'reinicio',
    ))


def _write_log(kind: str, payload: dict) -> str:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    path = LOG_DIR / f'windows_repair_{kind}_{stamp}.json'
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)
    return str(path)


def _overall(steps: list[dict], *, mutating: bool) -> tuple[str, str]:
    states = [str(x.get('state') or '') for x in steps]
    if any(x in ('FAILED', 'TIMEOUT', 'NOT_REPAIRABLE', 'UNREPAIRED') for x in states):
        return 'ATTENTION_REQUIRED', 'Hay una etapa que no pudo completarse o que requiere revisión.'
    if any(x == 'REPAIRABLE' for x in states):
        return 'REPAIR_RECOMMENDED', 'Se detectó corrupción o una infracción de integridad reparable.'
    if mutating and any(x == 'REPAIRED' for x in states):
        return 'REPAIRED', 'Windows informó que al menos una reparación se completó correctamente.'
    if states and all(x == 'CLEAN' for x in states):
        return 'CLEAN', 'No se detectaron problemas de integridad en las comprobaciones reconocidas.'
    if all(x in ('CLEAN', 'REPAIRED', 'COMPLETED_UNCLASSIFIED') for x in states):
        return 'COMPLETED', 'Las operaciones terminaron sin un error técnico confirmado.'
    return 'UNKNOWN', 'No hay evidencia suficiente para clasificar el estado global.'


def _run_steps(
    kind: str,
    steps: tuple[RepairStep, ...],
    *,
    progress: Optional[Callable[[dict], None]] = None,
) -> dict:
    started = time.time()
    base = {
        'kind': kind,
        'started_at': started,
        'started_at_iso': datetime.now().isoformat(timespec='seconds'),
        'windows': IS_WINDOWS,
        'admin': is_admin(),
        'policy': POLICY,
        'rollback_policy': ROLLBACK_POLICY,
        'steps': [],
    }

    if not IS_WINDOWS:
        base.update({
            'ok': False,
            'overall_state': 'UNAVAILABLE',
            'summary': 'Esta herramienta sólo está disponible en Windows.',
            'error': 'Windows requerido',
            'duration_s': 0.0,
            'log_path': None,
        })
        return base

    if not base['admin']:
        base.update({
            'ok': False,
            'overall_state': 'ADMIN_REQUIRED',
            'summary': 'DISM y SFC online requieren privilegios de administrador.',
            'error': 'Se requieren privilegios de administrador',
            'duration_s': 0.0,
            'log_path': None,
        })
        return base

    for index, step in enumerate(steps, start=1):
        if progress:
            try:
                progress({'event': 'start', 'index': index, 'total': len(steps), 'key': step.key, 'label': step.label})
            except Exception:
                pass
        t0 = time.time()
        result = run_hidden(step.args, timeout=step.timeout, category='WINDOWS_REPAIR')
        classified = classify_output(step.key, result)
        raw = _combined(result)
        row = {
            'key': step.key,
            'label': step.label,
            'command': list(step.args),
            'mutating': step.mutating,
            'ok': bool(result.ok),
            'returncode': result.returncode,
            'timed_out': bool(result.timed_out),
            'duration_s': round(time.time() - t0, 2),
            'state': classified['state'],
            'severity': classified['severity'],
            'message': classified['message'],
            'restart_maybe_required': _needs_restart(raw),
            'stdout': result.stdout,
            'stderr': result.stderr,
            'error': result.error,
        }
        base['steps'].append(row)
        if progress:
            try:
                progress({'event': 'done', 'index': index, 'total': len(steps), **row})
            except Exception:
                pass

        # Fail-closed: si DISM RestoreHealth falla, no afirmar una reparación completa.
        # SFC puede seguir aportando evidencia, por eso no abortamos el lote.

    state, summary = _overall(base['steps'], mutating=any(x.mutating for x in steps))
    base.update({
        'ok': state in ('CLEAN', 'COMPLETED', 'REPAIRED'),
        'overall_state': state,
        'summary': summary,
        'restart_maybe_required': any(bool(x.get('restart_maybe_required')) for x in base['steps']),
        'duration_s': round(time.time() - started, 2),
        'finished_at_iso': datetime.now().isoformat(timespec='seconds'),
    })
    try:
        base['log_path'] = _write_log(kind, base)
    except Exception as exc:
        base['log_path'] = None
        base['log_error'] = f'{type(exc).__name__}: {exc}'
    return base


def run_integrity_diagnostic(progress: Optional[Callable[[dict], None]] = None) -> dict:
    """Diagnóstico explícito: DISM CheckHealth + ScanHealth + SFC VerifyOnly."""
    return _run_steps('diagnostic', DIAGNOSTIC_STEPS, progress=progress)


def run_windows_repair(progress: Optional[Callable[[dict], None]] = None) -> dict:
    """Reparación explícita: DISM RestoreHealth + SFC ScanNow + comprobación DISM final."""
    return _run_steps('repair', REPAIR_STEPS, progress=progress)


def repair_capabilities() -> dict:
    admin_now = is_admin()
    return {
        'windows': IS_WINDOWS,
        'admin': admin_now,
        'diagnostic_available': IS_WINDOWS,
        'repair_available': IS_WINDOWS,
        'visible_console_available': IS_WINDOWS,
        'elevation_mode': 'ALREADY_ADMIN' if admin_now else ('UAC_POWERSHELL' if IS_WINDOWS else 'UNAVAILABLE'),
        'diagnostic_steps': [x.label for x in DIAGNOSTIC_STEPS],
        'repair_steps': [x.label for x in REPAIR_STEPS],
        'policy': POLICY,
        'rollback_policy': ROLLBACK_POLICY,
        'visible_console_policy': VISIBLE_CONSOLE_POLICY,
    }
