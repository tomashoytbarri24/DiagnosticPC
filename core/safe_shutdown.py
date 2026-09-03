"""Centraliza el cierre idempotente de agentes, hilos, RTSS y proveedores de sensores."""
from __future__ import annotations
# Código refactorizado: nombres estables y documentación en español.
import atexit
import gc
import threading
import time
_shutdown_lock = threading.RLock()
_shutdown_done = False

def _call_first(obj, method_names):
    if obj is None:
        return (False, None)
    for name in method_names:
        method = getattr(obj, name, None)
        if callable(method):
            try:
                method()
                return (True, None)
            except Exception as exc:
                return (False, f'{type(exc).__name__}: {exc}')
    return (False, None)

def _stop_telemetry_worker(report):
    try:
        from core import telemetry_background as telemetry
        stop = getattr(telemetry, 'stop_background_worker', None)
        if callable(stop):
            stop()
            report.append('telemetry worker: stopped')
        else:
            report.append('telemetry worker: no stop function')
    except Exception as exc:
        report.append(f'telemetry worker: {type(exc).__name__}: {exc}')

def _close_rtss_instances(report):
    try:
        from core import realtime_agent
        report.append('RTSS: owned instances handled by services')
    except Exception as exc:
        report.append(f'RTSS: {type(exc).__name__}: {exc}')

def _dispose_lhm_objects(report):
    """Gestiona la operación `dispose_lhm_objects` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
    try:
        from core import telemetry_full as telemetry
        candidates = []
        for name, value in vars(telemetry).items():
            lowered = name.lower()
            if any((token in lowered for token in ('provider', 'computer', 'monitor', 'hardware', 'lhm'))):
                candidates.append((name, value))
        seen = set()
        for name, obj in candidates:
            if obj is None:
                continue
            ident = id(obj)
            if ident in seen:
                continue
            seen.add(ident)
            called, error = _call_first(obj, ('Close', 'Dispose', 'close', 'dispose', 'shutdown', 'stop'))
            if called:
                report.append(f'LHM object closed: {name}')
            elif error:
                report.append(f'LHM object {name}: {error}')
    except Exception as exc:
        report.append(f'LHM cleanup: {type(exc).__name__}: {exc}')

def shutdown_corepulse_services(agent=None, tray=None, overlay=None, *, verbose=False):
    """Detiene la operación `shutdown_corepulse_services` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
    global _shutdown_done
    with _shutdown_lock:
        if _shutdown_done:
            return {'already_shutdown': True, 'steps': []}
        _shutdown_done = True
    report = []
    if agent is not None:
        called, error = _call_first(agent, ('stop', 'close', 'shutdown'))
        if called:
            report.append('realtime agent: stopped')
        elif error:
            report.append(f'realtime agent: {error}')
    if overlay is not None:
        called, error = _call_first(overlay, ('stop', 'close', 'shutdown'))
        if called:
            report.append('overlay service: stopped')
        elif error:
            report.append(f'overlay service: {error}')
    if tray is not None:
        called, error = _call_first(tray, ('stop', 'close', 'shutdown'))
        if called:
            report.append('tray: stopped')
        elif error:
            report.append(f'tray: {error}')
    _stop_telemetry_worker(report)
    _close_rtss_instances(report)
    _dispose_lhm_objects(report)
    time.sleep(0.1)
    try:
        gc.collect()
        report.append('gc: collected')
    except Exception as exc:
        report.append(f'gc: {type(exc).__name__}: {exc}')
    if verbose:
        print('[CorePulse Safe Shutdown]')
        for item in report:
            print(' -', item)
    return {'already_shutdown': False, 'steps': report}

def _atexit_shutdown():
    try:
        shutdown_corepulse_services(verbose=False)
    except Exception:
        pass
atexit.register(_atexit_shutdown)
