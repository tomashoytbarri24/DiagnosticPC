"""Centro seguro de reparación de Windows para CorePulse.

V0.10.2.33w

Principios:
- nunca confundir DISM/SFC con rollback de Tweaks;
- ninguna reparación se ejecuta automáticamente;
- las acciones online requieren Windows + privilegios de administrador;
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
    return {
        'windows': IS_WINDOWS,
        'admin': is_admin(),
        'diagnostic_available': IS_WINDOWS,
        'repair_available': IS_WINDOWS and is_admin(),
        'diagnostic_steps': [x.label for x in DIAGNOSTIC_STEPS],
        'repair_steps': [x.label for x in REPAIR_STEPS],
        'policy': POLICY,
        'rollback_policy': ROLLBACK_POLICY,
    }
