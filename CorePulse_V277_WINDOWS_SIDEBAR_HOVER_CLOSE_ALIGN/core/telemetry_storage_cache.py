"""Mantiene una caché segura para consultas costosas de almacenamiento sin fabricar SMART."""
from __future__ import annotations
# Código refactorizado: nombres estables y documentación en español.
import copy
import threading
import time
from core import telemetry_full as _telemetry_full
CACHE_SECONDS = 60.0
ERROR_BACKOFF_SECONDS = 30.0
_lock = threading.RLock()
_refresh_lock = threading.Lock()
_cached_disks = None
_cached_at = 0.0
_last_attempt_at = 0.0
_last_error = None
_last_quality = 'UNAVAILABLE'

def get_system_telemetry():
    """Obtiene la operación `get_system_telemetry` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
    return _telemetry_full.get_system_telemetry()

def _call_original_disks():
    fn = getattr(_telemetry_full, 'get_all_disks_data', None)
    if not callable(fn):
        return []
    return fn()

def get_all_disks_data(force_refresh=False):
    """Obtiene la operación `get_all_disks_data` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
    global _cached_disks
    global _cached_at
    global _last_attempt_at
    global _last_error
    global _last_quality
    now = time.monotonic()
    with _lock:
        if not force_refresh and _cached_disks is not None and (now - _cached_at < CACHE_SECONDS):
            return copy.deepcopy(_cached_disks)
        if not force_refresh and _last_error is not None and (now - _last_attempt_at < ERROR_BACKOFF_SECONDS):
            return copy.deepcopy(_cached_disks or [])
    if not _refresh_lock.acquire(blocking=False):
        with _lock:
            return copy.deepcopy(_cached_disks or [])
    try:
        with _lock:
            _last_attempt_at = time.monotonic()
        try:
            result = _call_original_disks()
            if not isinstance(result, list):
                result = list(result or [])
            with _lock:
                _cached_disks = copy.deepcopy(result)
                _cached_at = time.monotonic()
                _last_error = None
                _last_quality = 'VALID' if result else 'PARTIAL'
            return copy.deepcopy(result)
        except Exception as exc:
            with _lock:
                _last_error = f'{type(exc).__name__}: {exc}'
                _last_quality = 'STALE' if _cached_disks is not None else 'UNAVAILABLE'
                return copy.deepcopy(_cached_disks or [])
    finally:
        _refresh_lock.release()

def get_storage_cache_status():
    with _lock:
        age = None
        if _cached_disks is not None and _cached_at:
            age = max(0.0, time.monotonic() - _cached_at)
        return {'cache_seconds': CACHE_SECONDS, 'error_backoff_seconds': ERROR_BACKOFF_SECONDS, 'cached': _cached_disks is not None, 'cached_device_count': len(_cached_disks or []), 'cache_age_seconds': round(age, 2) if age is not None else None, 'quality': _last_quality, 'last_error': _last_error}

def invalidate_storage_cache():
    global _cached_at
    with _lock:
        _cached_at = 0.0
