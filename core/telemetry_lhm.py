"""Integra las lecturas reales de LibreHardwareMonitor con la telemetría base."""
from __future__ import annotations
# Código refactorizado: nombres estables y documentación en español.
import time
from core import telemetry_reliable as _telemetry_base
from core.lhm_provider import get_lhm_provider
get_all_disks_data = _telemetry_base.get_all_disks_data
calculate_preliminary_score = _telemetry_base.calculate_preliminary_score
get_hardware_names = _telemetry_base.get_hardware_names
get_system_chassis_and_bios = _telemetry_base.get_system_chassis_and_bios

def _set_metric(telemetry, key, value, unit, source, quality, error=None, sensor=None):
    telemetry[key] = value
    metrics = telemetry.setdefault('_metrics', {})
    metrics[key] = {'value': value, 'unit': unit, 'source': source, 'quality': quality, 'timestamp': time.time(), 'error': error}
    if sensor:
        metrics[key]['sensor'] = sensor

def get_system_telemetry():
    telemetry = _telemetry_base.get_system_telemetry()
    telemetry['_telemetry_version'] = '0.5.1'
    provider = get_lhm_provider()
    telemetry['_sensor_provider'] = {'name': 'LibreHardwareMonitorLib', 'available': provider.available, 'error': provider.error}
    cpu = provider.cpu_temperature()
    if cpu is not None:
        _set_metric(telemetry, 'cpu_temp', cpu['value'], '°C', cpu['source'], 'VALID', sensor=f"{cpu['hardware']} / {cpu['sensor']}")
    else:
        old = telemetry.get('_metrics', {}).get('cpu_temp', {})
        if old.get('quality') != 'VALID':
            _set_metric(telemetry, 'cpu_temp', None, '°C', 'LibreHardwareMonitorLib', 'UNAVAILABLE', error=provider.error or 'No se encontró un sensor CPU real.')
    gpu_temp_metric = telemetry.get('_metrics', {}).get('gpu_temp', {})
    if gpu_temp_metric.get('quality') != 'VALID':
        gpu_temp = provider.gpu_temperature()
        if gpu_temp is not None:
            _set_metric(telemetry, 'gpu_temp', gpu_temp['value'], '°C', gpu_temp['source'], 'VALID', sensor=f"{gpu_temp['hardware']} / {gpu_temp['sensor']}")
    gpu_usage_metric = telemetry.get('_metrics', {}).get('gpu_usage', {})
    if gpu_usage_metric.get('quality') != 'VALID':
        gpu_load = provider.gpu_load()
        if gpu_load is not None:
            _set_metric(telemetry, 'gpu_usage', gpu_load['value'], '%', gpu_load['source'], 'VALID', sensor=f"{gpu_load['hardware']} / {gpu_load['sensor']}")
    storage_temps = provider.storage_temperatures()
    telemetry['_storage_temperature_sensors'] = storage_temps
    return telemetry
