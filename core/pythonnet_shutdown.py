"""Libera de forma ordenada recursos Python.NET y proveedores de sensores antes de cerrar la aplicación."""
from __future__ import annotations
from core.version import VERSION_LABEL as VERSION
# Código refactorizado: nombres estables y documentación en español.
import gc
import importlib
import sys
import threading
import time
from typing import Any, Dict, List
def _safe_call(obj: Any, method: str, *args, **kwargs) -> bool:
    fn = getattr(obj, method, None)
    if not callable(fn):
        return False
    try:
        fn(*args, **kwargs)
        return True
    except Exception:
        return False

def _join_thread(thread: Any, timeout: float) -> bool:
    if not isinstance(thread, threading.Thread):
        return False
    if thread is threading.current_thread():
        return False
    try:
        if thread.is_alive():
            thread.join(timeout=max(0.0, float(timeout)))
        return not thread.is_alive()
    except Exception:
        return False

def _looks_like_sensor_provider(name: str, obj: Any) -> bool:
    n = str(name or '').lower()
    t = type(obj).__name__.lower()
    markers = ('computer', 'hardware', 'monitor', 'sensor', 'librehardware', 'lhm', 'provider')
    return any((x in n or x in t for x in markers))

def _close_provider_object(obj: Any) -> List[str]:
    actions: List[str] = []
    for method in ('stop', 'Stop', 'shutdown', 'Shutdown'):
        if _safe_call(obj, method):
            actions.append(method)
    for method in ('close', 'Close'):
        if _safe_call(obj, method):
            actions.append(method)
    for method in ('dispose', 'Dispose'):
        if _safe_call(obj, method):
            actions.append(method)
    return actions

def shutdown_telemetry_provider(*, join_timeout: float=3.0, verbose: bool=False) -> Dict[str, Any]:
    """Detiene la operación `shutdown_telemetry_provider` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
    result: Dict[str, Any] = {'version': VERSION, 'module_loaded': False, 'hooks_called': [], 'objects_closed': [], 'threads_joined': [], 'threads_still_alive': [], 'forced_runtime_shutdown': False, 'ok': True}
    try:
        mod = sys.modules.get('core.telemetry_background')
        if mod is None:
            try:
                mod = importlib.import_module('core.telemetry_background')
            except Exception as exc:
                result['ok'] = False
                result['error'] = f'{type(exc).__name__}: {exc}'
                return result
        result['module_loaded'] = True
        for hook_name in ('stop_background_worker', 'shutdown_telemetry', 'shutdown', 'close', 'stop', 'cleanup', 'dispose'):
            hook = getattr(mod, hook_name, None)
            if callable(hook):
                try:
                    hook()
                    result['hooks_called'].append(hook_name)
                except Exception as exc:
                    result.setdefault('hook_errors', []).append(f'{hook_name}: {type(exc).__name__}: {exc}')
        try:
            lhm_mod = sys.modules.get('core.lhm_provider')
            if lhm_mod is None:
                lhm_mod = importlib.import_module('core.lhm_provider')
            provider = getattr(lhm_mod, '_PROVIDER', None)
            if provider is not None:
                actions = _close_provider_object(provider)
                if actions:
                    result['objects_closed'].append({'name': 'core.lhm_provider._PROVIDER', 'type': type(provider).__name__, 'actions': actions})
                try:
                    setattr(lhm_mod, '_PROVIDER', None)
                except Exception:
                    pass
                provider = None
        except Exception as exc:
            result.setdefault('hook_errors', []).append(f'lhm_provider: {type(exc).__name__}: {exc}')
        module_dict = dict(vars(mod))
        for name, obj in module_dict.items():
            if name.startswith('__'):
                continue
            if isinstance(obj, threading.Thread):
                continue
            if not _looks_like_sensor_provider(name, obj):
                continue
            actions = _close_provider_object(obj)
            if actions:
                result['objects_closed'].append({'name': name, 'type': type(obj).__name__, 'actions': actions})
        deadline = time.monotonic() + max(0.2, float(join_timeout))
        candidates = []
        for thread in threading.enumerate():
            lname = thread.name.lower()
            if any((x in lname for x in ('telemetry', 'hardware', 'sensor', 'libre', 'lhm'))):
                if thread is not threading.current_thread():
                    candidates.append(thread)
        for thread in candidates:
            remaining = max(0.0, deadline - time.monotonic())
            if _join_thread(thread, remaining):
                result['threads_joined'].append(thread.name)
            elif thread.is_alive():
                result['threads_still_alive'].append(thread.name)
        module_dict.clear()
        gc.collect()
        time.sleep(0.05)
        gc.collect()
        if verbose:
            print('[CorePulse] telemetry teardown:', result)
        return result
    except Exception as exc:
        result['ok'] = False
        result['error'] = f'{type(exc).__name__}: {exc}'
        return result

def wait_for_named_threads(names=('CorePulse-Telemetry',), timeout: float=3.0) -> Dict[str, Any]:
    wanted = {str(x) for x in names}
    deadline = time.monotonic() + max(0.0, float(timeout))
    joined = []
    alive = []
    for thread in list(threading.enumerate()):
        if thread.name not in wanted:
            continue
        remaining = max(0.0, deadline - time.monotonic())
        if _join_thread(thread, remaining):
            joined.append(thread.name)
        elif thread.is_alive():
            alive.append(thread.name)
    return {'joined': joined, 'still_alive': alive, 'ok': not alive}
