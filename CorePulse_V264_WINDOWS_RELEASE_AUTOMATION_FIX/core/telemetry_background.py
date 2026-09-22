"""Mantiene un trabajador en segundo plano para adquirir telemetría sin bloquear la interfaz."""
from __future__ import annotations
# Código refactorizado: nombres estables y documentación en español.
import copy
import threading
import time
import psutil
from core.runtime_logging import get_logger
logger = get_logger('telemetry_background')
from core import telemetry_full as _telemetry_full
from core.hardware_policy import select_active_gpu
from core.telemetry_storage_cache import get_all_disks_data, get_storage_cache_status, invalidate_storage_cache
calculate_preliminary_score = _telemetry_full.calculate_preliminary_score
get_hardware_names = _telemetry_full.get_hardware_names
get_system_chassis_and_bios = _telemetry_full.get_system_chassis_and_bios
WORKER_INTERVAL_SECONDS = 1.0
FIRST_SNAPSHOT_TIMEOUT_SECONDS = 6.0
_state_lock = threading.RLock()
_worker_stop = threading.Event()
_first_snapshot_ready = threading.Event()
_snapshot = None
_snapshot_at = 0.0
_last_refresh_started = 0.0
_last_refresh_finished = 0.0
_last_refresh_duration = None
_last_error = None
_refresh_count = 0
_worker_thread = None
_last_error_log_at = 0.0

def _number(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None

def _round(value, digits=1):
    value = _number(value)
    return round(value, digits) if value is not None else None

def _metric(value, unit, source, sensor=None, error=None):
    return {'value': value, 'unit': unit, 'source': source, 'quality': 'VALID' if value is not None else 'UNAVAILABLE', 'sensor': sensor, 'timestamp': time.time(), 'error': error}

def _primary_gpu(gpus):
    return select_active_gpu(gpus)

def _collect_snapshot():
    started = time.perf_counter()
    cpu_usage = _round(psutil.cpu_percent(interval=None), 1)
    memory = psutil.virtual_memory()
    ram_usage = _round(memory.percent, 1)
    ram_total_gb = round(memory.total / 1024 ** 3, 2)
    ram_used_gb = round(memory.used / 1024 ** 3, 2)
    ram_available_gb = round(memory.available / 1024 ** 3, 2)
    provider, sensors = _telemetry_full._sensors()
    cpu = _telemetry_full._cpu_details(sensors)
    gpus = _telemetry_full._gpu_details(sensors)
    storage = _telemetry_full._storage_details(sensors)
    battery = _telemetry_full._battery_details(sensors)
    primary_gpu = _primary_gpu(gpus)
    cpu_name = cpu.get('hardware') or 'CPU no identificado'
    cpu_temp = _round(cpu.get('package_temp_c'), 1)
    cpu_ghz = _round(cpu.get('clock_avg_ghz'), 3)
    gpu_name = primary_gpu.get('name') or 'GPU no identificada'
    gpu_usage = _round(primary_gpu.get('usage_percent'), 1)
    gpu_temp = _round(primary_gpu.get('temperature_c'), 1)
    gpu_vram_gb = None
    memory_total_mb = _number(primary_gpu.get('memory_total_mb'))
    if memory_total_mb is not None:
        gpu_vram_gb = round(memory_total_mb / 1024.0, 2)
    duration_ms = round((time.perf_counter() - started) * 1000.0, 2)
    snapshot = {'_telemetry_version': '0.8.4.2', '_background_worker': True, '_worker_refresh_duration_ms': duration_ms, '_snapshot_timestamp': time.time(), 'cpu_name': cpu_name, 'cpu_usage': cpu_usage, 'cpu_ghz': cpu_ghz, 'cpu_temp': cpu_temp, 'ram_usage': ram_usage, 'ram_total_gb': ram_total_gb, 'ram_used_gb': ram_used_gb, 'ram_available_gb': ram_available_gb, 'gpu_name': gpu_name, 'gpu_usage': gpu_usage, 'gpu_temp': gpu_temp, 'gpu_vram_gb': gpu_vram_gb, '_cpu': cpu, '_gpus': gpus, '_storage_devices': storage, '_battery': battery, '_metrics': {'cpu_usage': _metric(cpu_usage, '%', 'psutil.cpu_percent'), 'cpu_ghz': _metric(cpu_ghz, 'GHz', 'LibreHardwareMonitorLib', sensor=f'{cpu_name} / clocks'), 'cpu_temp': _metric(cpu_temp, '°C', 'LibreHardwareMonitorLib', sensor=f'{cpu_name} / CPU Package'), 'ram_usage': _metric(ram_usage, '%', 'psutil.virtual_memory'), 'gpu_usage': _metric(gpu_usage, '%', 'LibreHardwareMonitorLib', sensor=f'{gpu_name} / GPU Core'), 'gpu_temp': _metric(gpu_temp, '°C', 'LibreHardwareMonitorLib', sensor=f'{gpu_name} / GPU Core'), 'gpu_vram_gb': _metric(gpu_vram_gb, 'GB', 'LibreHardwareMonitorLib', sensor=f'{gpu_name} / GPU Memory Total')}, '_sensor_summary': {'provider': 'LibreHardwareMonitorLib', 'provider_available': provider.available, 'provider_error': provider.error, 'sensor_count': len(sensors), 'cpu_detected': bool(cpu.get('hardware')), 'gpu_count': len(gpus), 'storage_count': len(storage), 'battery_detected': battery is not None, 'timestamp': time.time(), 'background_worker': True}}
    return snapshot

def _worker_loop():
    global _snapshot
    global _last_error_log_at
    global _snapshot_at
    global _last_refresh_started
    global _last_refresh_finished
    global _last_refresh_duration
    global _last_error
    global _refresh_count
    try:
        psutil.cpu_percent(interval=None)
    except Exception:
        logger.debug('No se pudo cebar psutil.cpu_percent', exc_info=True)
    while not _worker_stop.is_set():
        started_monotonic = time.monotonic()
        with _state_lock:
            _last_refresh_started = started_monotonic
        try:
            started_perf = time.perf_counter()
            fresh = _collect_snapshot()
            duration = time.perf_counter() - started_perf
            with _state_lock:
                _snapshot = fresh
                _snapshot_at = time.monotonic()
                _last_refresh_finished = _snapshot_at
                _last_refresh_duration = duration
                _last_error = None
                _refresh_count += 1
            _first_snapshot_ready.set()
        except Exception as exc:
            now = time.monotonic()
            with _state_lock:
                _last_error = f'{type(exc).__name__}: {exc}'
                _last_refresh_finished = now
            if now - _last_error_log_at >= 30.0:
                _last_error_log_at = now
                logger.exception('Fallo en el worker de telemetría; se conserva REAL_OR_NA')
        elapsed = time.monotonic() - started_monotonic
        wait_time = max(0.05, WORKER_INTERVAL_SECONDS - elapsed)
        _worker_stop.wait(wait_time)

def start_background_worker():
    global _worker_thread
    with _state_lock:
        if _worker_thread is not None and _worker_thread.is_alive():
            return _worker_thread
        _worker_stop.clear()
        _worker_thread = threading.Thread(target=_worker_loop, daemon=True, name='CorePulse-TelemetryWorker')
        _worker_thread.start()
        return _worker_thread

def stop_background_worker():
    _worker_stop.set()
    thread = _worker_thread
    if thread and thread.is_alive():
        try:
            thread.join(timeout=2.0)
        except Exception:
            logger.debug('No se pudo esperar el cierre del worker de telemetría', exc_info=True)

def get_system_telemetry(wait_for_first=True):
    """Obtiene la operación `get_system_telemetry` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
    start_background_worker()
    with _state_lock:
        if _snapshot is not None:
            result = copy.deepcopy(_snapshot)
            result['_snapshot_age_seconds'] = round(max(0.0, time.monotonic() - _snapshot_at), 3)
            return result
    if wait_for_first:
        _first_snapshot_ready.wait(FIRST_SNAPSHOT_TIMEOUT_SECONDS)
    with _state_lock:
        if _snapshot is not None:
            result = copy.deepcopy(_snapshot)
            result['_snapshot_age_seconds'] = round(max(0.0, time.monotonic() - _snapshot_at), 3)
            return result
        return {'_telemetry_version': '0.8.4.2', '_background_worker': True, '_snapshot_pending': True, '_worker_error': _last_error, 'cpu_name': 'CPU no identificado', 'cpu_usage': None, 'cpu_ghz': None, 'cpu_temp': None, 'ram_usage': None, 'ram_total_gb': None, 'ram_used_gb': None, 'ram_available_gb': None, 'gpu_name': 'GPU no identificada', 'gpu_usage': None, 'gpu_temp': None, 'gpu_vram_gb': None, '_cpu': {}, '_gpus': [], '_storage_devices': [], '_battery': None, '_metrics': {}, '_sensor_summary': {'provider': 'LibreHardwareMonitorLib', 'provider_available': False, 'provider_error': _last_error, 'sensor_count': 0, 'cpu_detected': False, 'gpu_count': 0, 'storage_count': 0, 'battery_detected': False, 'timestamp': time.time(), 'background_worker': True}}

def force_background_refresh():
    """Gestiona la operación `force_background_refresh` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
    global _last_refresh_finished
    with _state_lock:
        _last_refresh_finished = 0.0
    return True

def get_background_telemetry_status():
    with _state_lock:
        age = None
        if _snapshot is not None and _snapshot_at:
            age = max(0.0, time.monotonic() - _snapshot_at)
        return {'version': '0.8.4.2', 'worker_alive': bool(_worker_thread is not None and _worker_thread.is_alive()), 'worker_interval_seconds': WORKER_INTERVAL_SECONDS, 'snapshot_ready': _snapshot is not None, 'snapshot_age_seconds': round(age, 3) if age is not None else None, 'refresh_count': _refresh_count, 'last_refresh_duration_ms': round(_last_refresh_duration * 1000.0, 2) if _last_refresh_duration is not None else None, 'last_error': _last_error, 'storage_cache': get_storage_cache_status()}
start_background_worker()
