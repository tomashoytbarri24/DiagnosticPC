"""Controla el muestreo real de CPU y la frescura temporal de sus lecturas."""
from __future__ import annotations
from core.version import VERSION_LABEL as VERSION
# Código refactorizado: nombres estables y documentación en español.
import copy, threading, time
import psutil
from core import telemetry_consistency as _base
CPU_MIN_WINDOW_SECONDS = 0.25
CPU_SAMPLE_INTERVAL_SECONDS = 1.0
CPU_MAX_AGE_SECONDS = 2.5
calculate_preliminary_score = _base.calculate_preliminary_score
get_all_disks_data = _base.get_all_disks_data
for _name in ('get_storage_cache_status', 'invalidate_storage_cache', 'get_hardware_names', 'get_system_chassis_and_bios', 'force_background_refresh'):
    if hasattr(_base, _name):
        globals()[_name] = getattr(_base, _name)
_cpu_lock = threading.RLock()
_cpu_stop = threading.Event()
_cpu_ready = threading.Event()
_cpu_thread = None
_cpu_state = {'status': 'WARMING_UP', 'value': None, 'timestamp': None, 'monotonic': None, 'window_seconds': None, 'source': 'psutil.cpu_percent', 'quality': 'UNAVAILABLE', 'error': None, 'sample_count': 0, 'real_zero_valid': False}

def _safe_cpu_percent():
    try:
        v = psutil.cpu_percent(interval=None)
        if isinstance(v, bool):
            return None
        v = float(v)
        if not 0.0 <= v <= 100.0:
            return None
        return round(v, 1)
    except Exception:
        return None

def _publish(status, value, window, error=None):
    now_wall = time.time()
    now_mono = time.monotonic()
    with _cpu_lock:
        _cpu_state.update({'status': status, 'value': value, 'timestamp': now_wall if value is not None else None, 'monotonic': now_mono if value is not None else None, 'window_seconds': window, 'source': 'psutil.cpu_percent', 'quality': 'VALID' if status == 'VALID' else 'UNAVAILABLE', 'error': error, 'real_zero_valid': bool(status == 'VALID' and value == 0.0)})
        if status == 'VALID':
            _cpu_state['sample_count'] += 1
    if status == 'VALID':
        _cpu_ready.set()

def _cpu_sampler_loop():
    previous_call_at = time.monotonic()
    _safe_cpu_percent()
    if _cpu_stop.wait(CPU_MIN_WINDOW_SECONDS):
        return
    while not _cpu_stop.is_set():
        call_at = time.monotonic()
        window = call_at - previous_call_at
        value = _safe_cpu_percent()
        if window < CPU_MIN_WINDOW_SECONDS:
            _publish('WARMING_UP', None, window)
        elif value is None:
            _publish('UNAVAILABLE', None, window, 'psutil.cpu_percent returned no valid sample')
        else:
            _publish('VALID', value, window)
        previous_call_at = call_at
        if _cpu_stop.wait(CPU_SAMPLE_INTERVAL_SECONDS):
            break

def start_cpu_usage_sampler():
    global _cpu_thread
    with _cpu_lock:
        if _cpu_thread is not None and _cpu_thread.is_alive():
            return _cpu_thread
        _cpu_stop.clear()
        _cpu_ready.clear()
        _cpu_state.update({'status': 'WARMING_UP', 'value': None, 'timestamp': None, 'monotonic': None, 'window_seconds': None, 'source': 'psutil.cpu_percent', 'quality': 'UNAVAILABLE', 'error': None, 'sample_count': 0, 'real_zero_valid': False})
        _cpu_thread = threading.Thread(target=_cpu_sampler_loop, name='CorePulse-CPUUsageSampler', daemon=True)
        _cpu_thread.start()
        return _cpu_thread

def stop_cpu_usage_sampler(timeout=1.5):
    _cpu_stop.set()
    t = _cpu_thread
    if t is not None and t.is_alive():
        try:
            t.join(timeout=max(0.0, float(timeout)))
        except Exception:
            pass

def _cpu_sample_for_display():
    with _cpu_lock:
        state = dict(_cpu_state)
    mono = state.get('monotonic')
    age = None if mono is None else max(0.0, time.monotonic() - float(mono))
    state['age_seconds'] = None if age is None else round(age, 3)
    if state.get('status') != 'VALID':
        state['display_value'] = None
        state['display_status'] = 'N/A'
        return state
    if age is None or age > CPU_MAX_AGE_SECONDS:
        state['display_value'] = None
        state['display_status'] = 'STALE'
        state['quality'] = 'STALE'
        return state
    state['display_value'] = state.get('value')
    state['display_status'] = 'REAL'
    return state

def _apply_certified_cpu_usage(snapshot):
    result = copy.deepcopy(snapshot) if isinstance(snapshot, dict) else {}
    state = _cpu_sample_for_display()
    value = state.get('display_value')
    result['cpu_usage'] = value
    result['_cpu_usage_sampling'] = {'version': VERSION, 'status': state.get('status'), 'display_status': state.get('display_status'), 'value': value, 'last_real_value': state.get('value'), 'source': 'psutil.cpu_percent', 'quality': state.get('quality'), 'timestamp': state.get('timestamp'), 'age_seconds': state.get('age_seconds'), 'window_seconds': state.get('window_seconds'), 'minimum_window_seconds': CPU_MIN_WINDOW_SECONDS, 'sample_count': state.get('sample_count'), 'real_zero_valid': state.get('real_zero_valid'), 'synthetic_adjustment': False, 'interpolation': False, 'smoothing': False, 'offset_applied': 0.0, 'error': state.get('error')}
    metrics = result.get('_metrics') if isinstance(result.get('_metrics'), dict) else {}
    result['_metrics'] = metrics
    metrics['cpu_usage'] = {'value': value, 'unit': '%', 'source': 'psutil.cpu_percent', 'quality': 'VALID' if value is not None else 'STALE' if state.get('display_status') == 'STALE' else 'UNAVAILABLE', 'sensor': None, 'timestamp': state.get('timestamp'), 'error': None if value is not None else state.get('error') or state.get('display_status')}
    return result

def get_system_telemetry(wait_for_first=True):
    start_cpu_usage_sampler()
    snapshot = _base.get_system_telemetry(wait_for_first=wait_for_first)
    if wait_for_first and (not _cpu_ready.is_set()):
        _cpu_ready.wait(CPU_MIN_WINDOW_SECONDS + 0.35)
    return _apply_certified_cpu_usage(snapshot)

def stop_background_worker():
    stop_cpu_usage_sampler()
    if hasattr(_base, 'stop_background_worker'):
        return _base.stop_background_worker()

def get_cpu_usage_sampling_state():
    return _cpu_sample_for_display()
