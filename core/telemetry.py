"""Expone la canalización certificada de telemetría REAL_OR_NA utilizada por toda la aplicación."""
from __future__ import annotations
from core.version import VERSION_LABEL as VERSION
from core.hardware_policy import select_active_gpu
# Código refactorizado: nombres estables y documentación en español.
import atexit
import copy
import gc
import json
import math
import re
import subprocess
import platform
import threading
import time
from collections import defaultdict
from core import telemetry_sampling as _base
from core import telemetry_full as _telemetry_full
from core.lhm_provider import LibreHardwareSensorProvider
import core.lhm_provider as _lhm_module
PIPELINE_ID = 'COREPULSE_CERTIFIED_TELEMETRY'
LHM_VALID_MAX_AGE_SECONDS = 3.5
LHM_STALE_TIMEOUT_SECONDS = 10.0
SNAPSHOT_VALID_MAX_AGE_SECONDS = 3.5
calculate_preliminary_score = _base.calculate_preliminary_score
get_all_disks_data = _base.get_all_disks_data
for _name in ('get_storage_cache_status', 'invalidate_storage_cache', 'get_hardware_names', 'get_system_chassis_and_bios', 'force_background_refresh', 'get_background_telemetry_status', 'get_cpu_usage_sampling_state'):
    if hasattr(_base, _name):
        globals()[_name] = getattr(_base, _name)

def _finite(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except Exception:
        return None
    return number if math.isfinite(number) else None

def _safe_lhm_value(value):
    """Gestiona la operación `safe_lhm_value` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
    return _finite(value)
LibreHardwareSensorProvider._safe_value = staticmethod(_safe_lhm_value)

def _sensor_timestamp(sensor):
    if not isinstance(sensor, dict):
        return None
    return _finite(sensor.get('timestamp'))

def _sensor_label(sensor):
    if not isinstance(sensor, dict):
        return None
    hw = str(sensor.get('hardware_name') or '').strip()
    sn = str(sensor.get('sensor_name') or '').strip()
    if hw and sn:
        return f'{hw} / {sn}'
    return sn or hw or None

def _raw_meta(sensor, unit=None, derived=False, contributors=None):
    if sensor is None and (not contributors):
        return {'unit': unit, 'source': 'LibreHardwareMonitorLib', 'sensor': None, 'sensor_timestamp': None, 'derived_from_real': bool(derived), 'contributors': []}
    sensors = [s for s in contributors or [sensor] if isinstance(s, dict)]
    timestamps = [t for t in (_sensor_timestamp(s) for s in sensors) if t is not None]
    return {'unit': unit, 'source': 'LibreHardwareMonitorLib', 'sensor': _sensor_label(sensor) if sensor else 'multiple real sensors', 'sensor_timestamp': min(timestamps) if timestamps else None, 'derived_from_real': bool(derived), 'contributors': [{'sensor': _sensor_label(s), 'identifier': s.get('identifier'), 'sensor_timestamp': _sensor_timestamp(s)} for s in sensors]}

def _matching(items, hw_type=None, sensor_type=None):
    result = []
    for s in items:
        if hw_type is not None and str(s.get('hardware_type', '')).lower() != hw_type.lower():
            continue
        if sensor_type is not None and str(s.get('sensor_type', '')).lower() != sensor_type.lower():
            continue
        result.append(s)
    return result

def _pick_named(items, names):
    lowered = [(str(s.get('sensor_name', '')).lower(), s) for s in items]
    for wanted in names:
        wanted = wanted.lower()
        exact = [s for name, s in lowered if name == wanted]
        if exact:
            return exact[0]
        contains = [s for name, s in lowered if wanted in name]
        if contains:
            return contains[0]
    return None

def _sensor_unit(sensor_type):
    return {
        'temperature': '°C',
        'clock': 'MHz',
        'load': '%',
        'power': 'W',
        'voltage': 'V',
        'current': 'A',
    }.get(str(sensor_type or '').lower(), '')


def _cert_cpu_details(sensors):
    """Construye la vista CPU certificada preservando también el inventario de sensores.

    V0.9.20.1w corrige una regresión: la capa certificada sustituía a
    ``telemetry_full._cpu_details`` y descartaba la lista ``sensors`` que consumía
    la página CPU avanzada. Los valores siguen siendo exclusivamente lecturas LHM
    reales; esta función no sintetiza ni estima métricas ausentes.
    """
    cpu = _matching(sensors, 'Cpu')
    temps = [s for s in cpu if str(s.get('sensor_type', '')).lower() == 'temperature']
    clocks = [s for s in cpu if str(s.get('sensor_type', '')).lower() == 'clock']
    loads = [s for s in cpu if str(s.get('sensor_type', '')).lower() == 'load']
    power = [s for s in cpu if str(s.get('sensor_type', '')).lower() == 'power']
    voltages = [s for s in cpu if str(s.get('sensor_type', '')).lower() == 'voltage']

    package = _pick_named(temps, ['CPU Package', 'Package', 'Tctl/Tdie'])
    core_max = _pick_named(temps, ['Core Max'])
    core_avg = _pick_named(temps, ['Core Average'])
    distance = [s for s in temps if 'distance to tjmax' in str(s.get('sensor_name', '')).lower()]
    core_clocks = [s for s in clocks if str(s.get('sensor_name', '')).lower().startswith('cpu core #')]
    package_power = _pick_named(power, ['CPU Package', 'Package'])
    total_load = _pick_named(loads, ['CPU Total', 'Total'])
    bus_clock = _pick_named(clocks, ['Bus Speed', 'Bus Clock'])
    core_voltage = _pick_named(voltages, ['CPU Core', 'Core', 'VCore'])

    clock_values = [_finite(s.get('value')) for s in core_clocks]
    clock_values = [v for v in clock_values if v is not None and v > 0]

    allowed = {'temperature', 'clock', 'load', 'power', 'voltage', 'current'}
    sensor_rows = []
    for index, sensor in enumerate(cpu):
        sensor_type = str(sensor.get('sensor_type') or '').lower()
        value = _finite(sensor.get('value'))
        if sensor_type not in allowed or value is None:
            continue
        sensor_rows.append({
            'name': str(sensor.get('sensor_name') or 'Sensor'),
            'type': sensor_type,
            'value': round(value, 4),
            'unit': _sensor_unit(sensor_type),
            'identifier': str(sensor.get('identifier') or '') or None,
            'hardware': str(sensor.get('hardware_name') or '') or None,
            'source': str(sensor.get('source') or 'LibreHardwareMonitorLib'),
            'quality': 'VALID',
            'timestamp': _sensor_timestamp(sensor),
            'raw_index': index,
        })
    sensor_rows.sort(key=lambda item: (str(item.get('type') or '').casefold(), str(item.get('name') or '').casefold()))

    result = {
        'package_temp_c': round(package['value'], 1) if package else None,
        'core_max_temp_c': round(core_max['value'], 1) if core_max else None,
        'core_average_temp_c': round(core_avg['value'], 1) if core_avg else None,
        'distance_to_tjmax_min_c': round(min((s['value'] for s in distance)), 1) if distance else None,
        'clock_avg_ghz': round(sum(clock_values) / len(clock_values) / 1000.0, 3) if clock_values else None,
        'clock_max_ghz': round(max(clock_values) / 1000.0, 3) if clock_values else None,
        'bus_clock_mhz': round(bus_clock['value'], 2) if bus_clock else None,
        'package_power_w': round(package_power['value'], 2) if package_power else None,
        'total_load_percent': round(total_load['value'], 1) if total_load else None,
        'core_voltage_v': round(core_voltage['value'], 4) if core_voltage else None,
        'hardware': package['hardware_name'] if package else cpu[0]['hardware_name'] if cpu else None,
        'source': 'LibreHardwareMonitorLib' if cpu else None,
        'sensor_count': len(sensor_rows),
        'sensors': sensor_rows,
    }
    result['_metrics'] = {
        'package_temp_c': _raw_meta(package, '°C'),
        'core_max_temp_c': _raw_meta(core_max, '°C'),
        'core_average_temp_c': _raw_meta(core_avg, '°C'),
        'distance_to_tjmax_min_c': _raw_meta(distance[0] if distance else None, '°C', derived=len(distance) > 1, contributors=distance),
        'clock_avg_ghz': _raw_meta(core_clocks[0] if core_clocks else None, 'GHz', derived=True, contributors=core_clocks),
        'clock_max_ghz': _raw_meta(core_clocks[0] if core_clocks else None, 'GHz', derived=True, contributors=core_clocks),
        'bus_clock_mhz': _raw_meta(bus_clock, 'MHz'),
        'package_power_w': _raw_meta(package_power, 'W'),
        'total_load_percent': _raw_meta(total_load, '%'),
        'core_voltage_v': _raw_meta(core_voltage, 'V'),
    }
    timestamps = [m.get('sensor_timestamp') for m in result['_metrics'].values() if m.get('sensor_timestamp') is not None]
    result['timestamp'] = min(timestamps) if timestamps else None
    result['quality'] = 'VALID' if cpu else 'UNAVAILABLE'
    return result

def _cert_gpu_details(sensors):
    grouped = defaultdict(list)
    for s in sensors:
        if str(s.get('hardware_type', '')).lower().startswith('gpu'):
            grouped[s['hardware_type'], s['hardware_name']].append(s)
    result = []
    unit_map = {
        'temperature': '°C', 'clock': 'MHz', 'load': '%', 'power': 'W',
        'voltage': 'V', 'current': 'A', 'fan': 'RPM', 'control': '%',
        'smalldata': 'MB', 'throughput': 'B/s',
    }
    allowed_sensor_types = set(unit_map)
    for (hw_type, hw_name), items in grouped.items():
        temps = [s for s in items if str(s.get('sensor_type', '')).lower() == 'temperature']
        clocks = [s for s in items if str(s.get('sensor_type', '')).lower() == 'clock']
        loads = [s for s in items if str(s.get('sensor_type', '')).lower() == 'load']
        power = [s for s in items if str(s.get('sensor_type', '')).lower() == 'power']
        small = [s for s in items if str(s.get('sensor_type', '')).lower() == 'smalldata']
        fans = [s for s in items if str(s.get('sensor_type', '')).lower() == 'fan']
        controls = [s for s in items if str(s.get('sensor_type', '')).lower() == 'control']
        voltages = [s for s in items if str(s.get('sensor_type', '')).lower() == 'voltage']
        core_temp = _pick_named(temps, ['GPU Core', 'Core'])
        hotspot = _pick_named(temps, ['GPU Hot Spot', 'Hot Spot', 'Hotspot'])
        core_clock = _pick_named(clocks, ['GPU Core', 'Core'])
        mem_clock = _pick_named(clocks, ['GPU Memory', 'Memory'])
        core_load = _pick_named(loads, ['GPU Core', 'D3D 3D', '3D'])
        mem_load = _pick_named(loads, ['GPU Memory', 'Memory'])
        package_power = _pick_named(power, ['GPU Package', 'GPU Power', 'Package'])
        mem_total = _pick_named(small, ['GPU Memory Total', 'D3D Dedicated Memory Total'])
        mem_used = _pick_named(small, ['GPU Memory Used', 'D3D Dedicated Memory Used'])
        fan = _pick_named(fans, ['GPU Fan', 'Fan'])
        fan_control = _pick_named(controls, ['GPU Fan', 'Fan'])
        core_voltage = _pick_named(voltages, ['GPU Core', 'Core'])

        sensor_rows = []
        for sensor in items:
            sensor_type = str(sensor.get('sensor_type') or '')
            kind = sensor_type.lower()
            if kind not in allowed_sensor_types:
                continue
            value = _finite(sensor.get('value'))
            if value is None:
                continue
            sensor_rows.append({
                'name': sensor.get('sensor_name') or 'Sensor',
                'type': sensor_type,
                'value': round(float(value), 3),
                'unit': unit_map.get(kind, ''),
                'identifier': sensor.get('identifier') or None,
                'hardware': sensor.get('hardware_name') or hw_name,
                'source': 'LibreHardwareMonitorLib',
                'quality': 'VALID',
                'timestamp': sensor.get('timestamp'),
            })
        sensor_rows.sort(key=lambda item: (str(item.get('type') or '').casefold(), str(item.get('name') or '').casefold(), str(item.get('identifier') or '').casefold()))

        gpu = {
            'name': hw_name,
            'hardware_type': hw_type,
            'temperature_c': round(core_temp['value'], 1) if core_temp else None,
            'hotspot_c': round(hotspot['value'], 1) if hotspot else None,
            'usage_percent': round(core_load['value'], 1) if core_load else None,
            'memory_usage_percent': round(mem_load['value'], 1) if mem_load else None,
            'core_clock_mhz': round(core_clock['value'], 1) if core_clock else None,
            'memory_clock_mhz': round(mem_clock['value'], 1) if mem_clock else None,
            'power_w': round(package_power['value'], 2) if package_power else None,
            'memory_total_mb': round(mem_total['value'], 1) if mem_total else None,
            'memory_used_mb': round(mem_used['value'], 1) if mem_used else None,
            'fan_rpm': round(fan['value'], 1) if fan else None,
            'fan_control_percent': round(fan_control['value'], 1) if fan_control else None,
            'core_voltage_v': round(core_voltage['value'], 4) if core_voltage else None,
            'source': 'LibreHardwareMonitorLib',
            'sensor_count': len(sensor_rows),
            'sensors': sensor_rows,
        }
        gpu['_metrics'] = {
            'temperature_c': _raw_meta(core_temp, '°C'),
            'hotspot_c': _raw_meta(hotspot, '°C'),
            'usage_percent': _raw_meta(core_load, '%'),
            'memory_usage_percent': _raw_meta(mem_load, '%'),
            'core_clock_mhz': _raw_meta(core_clock, 'MHz'),
            'memory_clock_mhz': _raw_meta(mem_clock, 'MHz'),
            'power_w': _raw_meta(package_power, 'W'),
            'memory_total_mb': _raw_meta(mem_total, 'MB'),
            'memory_used_mb': _raw_meta(mem_used, 'MB'),
            'fan_rpm': _raw_meta(fan, 'RPM'),
            'fan_control_percent': _raw_meta(fan_control, '%'),
            'core_voltage_v': _raw_meta(core_voltage, 'V'),
        }
        timestamps = [m['sensor_timestamp'] for m in gpu['_metrics'].values() if m.get('sensor_timestamp') is not None]
        gpu['timestamp'] = min(timestamps) if timestamps else None
        gpu['quality'] = 'VALID'
        result.append(gpu)
    result.sort(key=lambda x: str(x.get('name') or '').casefold())
    return result

def _cert_storage_details(sensors):
    grouped = defaultdict(list)
    for s in sensors:
        if str(s.get('hardware_type', '')).lower() == 'storage':
            grouped[s['hardware_name']].append(s)
    result = []
    for hw_name, items in grouped.items():
        temps = [s for s in items if str(s.get('sensor_type', '')).lower() == 'temperature']
        levels = [s for s in items if str(s.get('sensor_type', '')).lower() == 'level']
        factors = [s for s in items if str(s.get('sensor_type', '')).lower() == 'factor']
        data = [s for s in items if str(s.get('sensor_type', '')).lower() == 'data']
        loads = [s for s in items if str(s.get('sensor_type', '')).lower() == 'load']
        actual_temps = [s for s in temps if 'warning' not in str(s.get('sensor_name', '')).lower() and 'critical' not in str(s.get('sensor_name', '')).lower()]
        warning = _pick_named(temps, ['Warning Temperature'])
        critical = _pick_named(temps, ['Critical Temperature'])
        primary_temp = _pick_named(actual_temps, ['Temperature'])
        if primary_temp is None and actual_temps:
            primary_temp = actual_temps[0]
        life = _pick_named(levels, ['Life', 'Remaining Life', 'Health'])
        power_hours = _pick_named(factors, ['Power On Hours'])
        power_count = _pick_named(factors, ['Power On Count', 'Power Cycle Count'])
        data_read = _pick_named(data, ['Data Read'])
        data_written = _pick_named(data, ['Data Written'])
        free_space = _pick_named(data, ['Free Space'])
        total_space = _pick_named(data, ['Total Space'])
        used_space = _pick_named(loads, ['Used Space'])
        disk = {'name': hw_name, 'temperature_c': round(primary_temp['value'], 1) if primary_temp else None, 'temperature_sensors_c': [{'name': s['sensor_name'], 'value': round(s['value'], 1), 'sensor_timestamp': _sensor_timestamp(s), 'source': 'LibreHardwareMonitorLib'} for s in actual_temps], 'warning_temperature_c': round(warning['value'], 1) if warning else None, 'critical_temperature_c': round(critical['value'], 1) if critical else None, 'life_percent': round(life['value'], 1) if life else None, 'power_on_hours': int(power_hours['value']) if power_hours else None, 'power_on_count': int(power_count['value']) if power_count else None, 'data_read': round(data_read['value'], 3) if data_read else None, 'data_written': round(data_written['value'], 3) if data_written else None, 'used_space_percent': round(used_space['value'], 1) if used_space else None, 'free_space_gb': round(free_space['value'], 2) if free_space else None, 'total_space_gb': round(total_space['value'], 2) if total_space else None, 'source': 'LibreHardwareMonitorLib'}
        disk['_metrics'] = {'temperature_c': _raw_meta(primary_temp, '°C'), 'warning_temperature_c': _raw_meta(warning, '°C'), 'critical_temperature_c': _raw_meta(critical, '°C'), 'life_percent': _raw_meta(life, '%'), 'power_on_hours': _raw_meta(power_hours, 'h'), 'power_on_count': _raw_meta(power_count, 'count'), 'data_read': _raw_meta(data_read, 'GB'), 'data_written': _raw_meta(data_written, 'GB'), 'used_space_percent': _raw_meta(used_space, '%'), 'free_space_gb': _raw_meta(free_space, 'GB'), 'total_space_gb': _raw_meta(total_space, 'GB')}
        timestamps = [m['sensor_timestamp'] for m in disk['_metrics'].values() if m.get('sensor_timestamp') is not None]
        disk['timestamp'] = min(timestamps) if timestamps else None
        disk['quality'] = 'VALID'
        result.append(disk)
    return result

def _cert_battery_details(sensors):
    battery = _matching(sensors, 'Battery')
    if not battery:
        return None
    energy = [s for s in battery if str(s.get('sensor_type', '')).lower() == 'energy']
    levels = [s for s in battery if str(s.get('sensor_type', '')).lower() == 'level']
    voltage = [s for s in battery if str(s.get('sensor_type', '')).lower() == 'voltage']
    current = [s for s in battery if str(s.get('sensor_type', '')).lower() == 'current']
    power = [s for s in battery if str(s.get('sensor_type', '')).lower() == 'power']
    designed = _pick_named(energy, ['Designed Capacity'])
    full = _pick_named(energy, ['Fully-Charged Capacity', 'Full Charged Capacity'])
    remaining = _pick_named(energy, ['Remaining Capacity'])
    degradation = _pick_named(levels, ['Degradation Level'])
    charge = _pick_named(levels, ['Charge Level'])
    volt = _pick_named(voltage, ['Voltage'])
    curr = _pick_named(current, ['Charge/Discharge Current'])
    rate = _pick_named(power, ['Charge/Discharge Rate'])
    result = {'designed_capacity_mwh': round(designed['value'], 1) if designed else None, 'full_charge_capacity_mwh': round(full['value'], 1) if full else None, 'remaining_capacity_mwh': round(remaining['value'], 1) if remaining else None, 'degradation_percent': round(degradation['value'], 2) if degradation else None, 'charge_percent': round(charge['value'], 2) if charge else None, 'voltage_v': round(volt['value'], 3) if volt else None, 'current_ma': round(curr['value'], 2) if curr else None, 'charge_discharge_rate_w': round(rate['value'], 2) if rate else None, 'source': 'LibreHardwareMonitorLib'}
    result['_metrics'] = {'designed_capacity_mwh': _raw_meta(designed, 'mWh'), 'full_charge_capacity_mwh': _raw_meta(full, 'mWh'), 'remaining_capacity_mwh': _raw_meta(remaining, 'mWh'), 'degradation_percent': _raw_meta(degradation, '%'), 'charge_percent': _raw_meta(charge, '%'), 'voltage_v': _raw_meta(volt, 'V'), 'current_ma': _raw_meta(curr, 'mA'), 'charge_discharge_rate_w': _raw_meta(rate, 'W')}
    timestamps = [m['sensor_timestamp'] for m in result['_metrics'].values() if m.get('sensor_timestamp') is not None]
    result['timestamp'] = min(timestamps) if timestamps else None
    result['quality'] = 'VALID'
    return result
_telemetry_full._cpu_details = _cert_cpu_details
_telemetry_full._gpu_details = _cert_gpu_details
_telemetry_full._storage_details = _cert_storage_details
_telemetry_full._battery_details = _cert_battery_details

def _range_for(key):
    """Gestiona la operación `range_for` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
    ranges = {'cpu_usage': (0.0, 100.0), 'ram_usage': (0.0, 100.0), 'gpu_usage': (0.0, 100.0), 'usage_percent': (0.0, 100.0), 'memory_usage_percent': (0.0, 100.0), 'life_percent': (0.0, 100.0), 'used_space_percent': (0.0, 100.0), 'charge_percent': (0.0, 100.0), 'degradation_percent': (0.0, 100.0), 'cpu_temp': (-40.0, 150.0), 'gpu_temp': (-40.0, 150.0), 'temperature_c': (-40.0, 150.0), 'hotspot_c': (-40.0, 175.0), 'warning_temperature_c': (-40.0, 200.0), 'critical_temperature_c': (-40.0, 220.0), 'core_max_temp_c': (-40.0, 150.0), 'core_average_temp_c': (-40.0, 150.0), 'package_temp_c': (-40.0, 150.0), 'distance_to_tjmax_min_c': (-100.0, 200.0), 'cpu_ghz': (0.0, 10.0), 'clock_avg_ghz': (0.0, 10.0), 'clock_max_ghz': (0.0, 10.0), 'bus_clock_mhz': (0.0, 1000.0), 'total_load_percent': (0.0, 100.0), 'core_voltage_v': (0.0, 10.0), 'fan_rpm': (0.0, 100000.0), 'fan_control_percent': (0.0, 100.0), 'core_clock_mhz': (0.0, 12000.0), 'memory_clock_mhz': (0.0, 60000.0), 'gpu_vram_gb': (0.0, 1024.0), 'memory_total_mb': (0.0, 2097152.0), 'memory_used_mb': (0.0, 2097152.0), 'power_w': (-10000.0, 10000.0), 'package_power_w': (-1000.0, 5000.0), 'voltage_v': (0.0, 1000.0), 'current_ma': (-1000000.0, 1000000.0), 'charge_discharge_rate_w': (-10000.0, 10000.0), 'designed_capacity_mwh': (0.0, 5000000.0), 'full_charge_capacity_mwh': (0.0, 5000000.0), 'remaining_capacity_mwh': (0.0, 5000000.0), 'power_on_hours': (0.0, 10000000.0), 'power_on_count': (0.0, 1000000000.0), 'free_space_gb': (0.0, 10000000.0), 'total_space_gb': (0.0, 10000000.0), 'data_read': (0.0, 1e+18), 'data_written': (0.0, 1e+18)}
    return ranges.get(key)

def _physical_anomaly(key, value):
    """Gestiona la operación `physical_anomaly` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
    if value is None:
        return None
    if isinstance(value, bool):
        return 'BOOLEAN_NOT_NUMERIC'
    number = _finite(value)
    if number is None:
        return 'NON_FINITE_OR_NON_NUMERIC'
    limits = _range_for(key)
    if limits and (not limits[0] <= number <= limits[1]):
        return f'OUT_OF_RANGE:{limits[0]}..{limits[1]}'
    return None

def _cross_metric_anomalies(obj, kind):
    """Gestiona la operación `cross_metric_anomalies` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
    anomalies = []

    def number(name):
        return _finite(obj.get(name)) if isinstance(obj, dict) else None
    if kind == 'gpu':
        used = number('memory_used_mb')
        total = number('memory_total_mb')
        if used is not None and total is not None and (total >= 0) and (used > total):
            anomalies.append({'metric': 'memory_used_mb', 'reason': 'VRAM_USED_EXCEEDS_TOTAL', 'observed': used, 'reference': total})
    elif kind == 'storage':
        free = number('free_space_gb')
        total = number('total_space_gb')
        used = number('used_space_percent')
        if free is not None and total is not None and (free > total):
            anomalies.append({'metric': 'free_space_gb', 'reason': 'FREE_SPACE_EXCEEDS_TOTAL', 'observed': free, 'reference': total})
        if used is not None and (not 0.0 <= used <= 100.0):
            anomalies.append({'metric': 'used_space_percent', 'reason': 'PERCENT_OUT_OF_RANGE', 'observed': used, 'reference': 100.0})
    elif kind == 'battery':
        full = number('full_charge_capacity_mwh')
        design = number('designed_capacity_mwh')
        remaining = number('remaining_capacity_mwh')
        if full is not None and design is not None and (design > 0) and (full > design * 1.5):
            anomalies.append({'metric': 'full_charge_capacity_mwh', 'reason': 'FULL_CAPACITY_GROSSLY_EXCEEDS_DESIGN', 'observed': full, 'reference': design})
        if remaining is not None and full is not None and (full > 0) and (remaining > full * 1.25):
            anomalies.append({'metric': 'remaining_capacity_mwh', 'reason': 'REMAINING_GROSSLY_EXCEEDS_FULL_CAPACITY', 'observed': remaining, 'reference': full})
    elif kind == 'cpu':
        avg = number('clock_avg_ghz')
        maxv = number('clock_max_ghz')
        if avg is not None and maxv is not None and (avg > maxv + 0.05):
            anomalies.append({'metric': 'clock_avg_ghz', 'reason': 'AVERAGE_CLOCK_EXCEEDS_MAX_CLOCK', 'observed': avg, 'reference': maxv})
    return anomalies

def _mark_metric_anomaly(obj, metric_name, reason, snapshot_timestamp):
    if not isinstance(obj, dict):
        return
    certs = obj.setdefault('_certified_metrics', {})
    cert = certs.get(metric_name)
    if not isinstance(cert, dict):
        cert = {'value': None, 'last_real_value': obj.get(metric_name), 'source': obj.get('source'), 'sensor': None, 'sensor_timestamp': obj.get('timestamp'), 'snapshot_timestamp': snapshot_timestamp, 'age_seconds': None, 'quality': 'ERROR', 'reason': reason, 'derived_from_real': False, 'synthetic_adjustment': False, 'interpolation': False, 'offset_applied': 0.0}
        certs[metric_name] = cert
    else:
        cert['last_real_value'] = cert.get('last_real_value', obj.get(metric_name))
        cert['value'] = None
        cert['quality'] = 'ERROR'
        cert['reason'] = reason
    obj[metric_name] = None

def _apply_cross_metric_guards(obj, kind, snapshot_timestamp):
    anomalies = _cross_metric_anomalies(obj, kind)
    for anomaly in anomalies:
        _mark_metric_anomaly(obj, anomaly['metric'], anomaly['reason'], snapshot_timestamp)
    if isinstance(obj, dict):
        obj['_physical_anomalies'] = anomalies
    return anomalies

def _certify_metric(key, value, unit, source, sensor, sensor_timestamp, snapshot_timestamp, derived_from_real=False, error=None):
    raw_value = value
    number = _finite(value)
    anomaly = _physical_anomaly(key, value)
    if value is None:
        quality, reason, display = ('UNAVAILABLE', error or 'NO_REAL_VALUE', None)
    elif anomaly is not None:
        quality, reason, display = ('ERROR', anomaly, None)
    else:
        ts = _finite(sensor_timestamp)
        age = None if ts is None else max(0.0, time.time() - ts)
        if ts is None:
            quality, reason, display = ('ERROR', 'MISSING_SENSOR_TIMESTAMP', None)
        elif age <= LHM_VALID_MAX_AGE_SECONDS:
            quality, reason, display = ('VALID', None, raw_value)
        elif age <= LHM_STALE_TIMEOUT_SECONDS:
            quality, reason, display = ('STALE', 'SENSOR_SAMPLE_OLD', None)
        else:
            quality, reason, display = ('UNAVAILABLE', 'STALE_TIMEOUT', None)
    ts = _finite(sensor_timestamp)
    age = None if ts is None else round(max(0.0, time.time() - ts), 3)
    return {'value': display, 'last_real_value': raw_value if number is not None else None, 'unit': unit, 'source': source, 'sensor': sensor, 'sensor_timestamp': ts, 'snapshot_timestamp': _finite(snapshot_timestamp), 'age_seconds': age, 'quality': quality, 'reason': reason, 'derived_from_real': bool(derived_from_real), 'synthetic_adjustment': False, 'interpolation': False, 'offset_applied': 0.0}

def _meta_from_nested(obj, field):
    if not isinstance(obj, dict):
        return {}
    metrics = obj.get('_metrics')
    if not isinstance(metrics, dict):
        return {}
    meta = metrics.get(field)
    return meta if isinstance(meta, dict) else {}

def _apply_nested_certification(obj, fields, snapshot_timestamp):
    if not isinstance(obj, dict):
        return obj
    statuses = []
    for field, unit in fields.items():
        meta = _meta_from_nested(obj, field)
        certified = _certify_metric(field, obj.get(field), unit or meta.get('unit'), meta.get('source') or obj.get('source') or 'LibreHardwareMonitorLib', meta.get('sensor'), meta.get('sensor_timestamp'), snapshot_timestamp, meta.get('derived_from_real', False))
        obj.setdefault('_certified_metrics', {})[field] = certified
        statuses.append(certified['quality'])
        if certified['quality'] != 'VALID':
            obj[field] = None
    if statuses and all((x == 'VALID' for x in statuses)):
        obj['quality'] = 'VALID'
    elif any((x == 'VALID' for x in statuses)):
        obj['quality'] = 'PARTIAL'
    elif any((x == 'STALE' for x in statuses)):
        obj['quality'] = 'STALE'
    elif any((x == 'ERROR' for x in statuses)):
        obj['quality'] = 'ERROR'
    else:
        obj['quality'] = 'UNAVAILABLE'
    return obj

def _primary_gpu(gpus):
    return select_active_gpu(gpus)
_ENUM_CACHE = {'ts': 0.0, 'gpu': [], 'storage': []}
_ENUM_CACHE_SECONDS = 30.0

def _norm_hw_name(value):
    text = str(value or '').strip().lower()
    text = re.sub('\\(r\\)|\\(tm\\)|™|®', '', text)
    text = re.sub('[^a-z0-9]+', ' ', text)
    return ' '.join(text.split())

def _powershell_cim(class_name, properties):
    """Gestiona la operación `powershell_cim` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
    if platform.system() != 'Windows':
        return []
    prop = ','.join(properties)
    script = f'Get-CimInstance {class_name} | Select-Object {prop} | ConvertTo-Json -Depth 4 -Compress'
    try:
        cp = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script], capture_output=True, text=True, errors='replace', timeout=8, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if cp.returncode != 0 or not cp.stdout.strip():
            return []
        data = json.loads(cp.stdout)
        if isinstance(data, dict):
            return [data]
        return data if isinstance(data, list) else []
    except Exception:
        return []

def _windows_gpu_inventory():
    rows = _powershell_cim('Win32_VideoController', ['Name', 'PNPDeviceID', 'AdapterRAM', 'DriverVersion', 'VideoProcessor', 'AdapterCompatibility', 'Status', 'CurrentHorizontalResolution', 'CurrentVerticalResolution', 'CurrentRefreshRate', 'VideoModeDescription'])
    result = []
    for row in rows:
        name = str(row.get('Name') or '').strip()
        if not name:
            continue
        ram = _finite(row.get('AdapterRAM'))
        result.append({'name': name, 'normalized_name': _norm_hw_name(name), 'pnp_device_id': row.get('PNPDeviceID'), 'adapter_ram_bytes_os': int(ram) if ram is not None and ram >= 0 else None, 'driver_version': row.get('DriverVersion'), 'video_processor': row.get('VideoProcessor'), 'vendor': row.get('AdapterCompatibility'), 'os_status': row.get('Status'), 'current_horizontal_resolution': row.get('CurrentHorizontalResolution'), 'current_vertical_resolution': row.get('CurrentVerticalResolution'), 'current_refresh_rate': row.get('CurrentRefreshRate'), 'video_mode_description': row.get('VideoModeDescription'), 'inventory_source': 'Win32_VideoController'})
    return result

def _windows_storage_inventory():
    rows = _powershell_cim('Win32_DiskDrive', ['Index', 'Model', 'SerialNumber', 'FirmwareRevision', 'PNPDeviceID', 'DeviceID', 'InterfaceType', 'MediaType', 'Size', 'Status'])
    result = []
    for row in rows:
        model = str(row.get('Model') or '').strip()
        device_id = str(row.get('DeviceID') or '').strip()
        if not model and (not device_id):
            continue
        size = _finite(row.get('Size'))
        serial = str(row.get('SerialNumber') or '').strip() or None
        result.append({'name': model or device_id, 'model': model or None, 'normalized_name': _norm_hw_name(model or device_id), 'serial_number': serial, 'firmware_revision': str(row.get('FirmwareRevision') or '').strip() or None, 'pnp_device_id': row.get('PNPDeviceID'), 'device_id': device_id or None, 'disk_index': row.get('Index'), 'interface_type': row.get('InterfaceType'), 'media_type_os': row.get('MediaType'), 'size_bytes_os': int(size) if size is not None and size >= 0 else None, 'os_status': row.get('Status'), 'inventory_source': 'Win32_DiskDrive'})
    return result

def _enum_cached():
    now = time.time()
    if now - _ENUM_CACHE['ts'] <= _ENUM_CACHE_SECONDS and (_ENUM_CACHE['gpu'] or _ENUM_CACHE['storage']):
        return copy.deepcopy(_ENUM_CACHE)
    _ENUM_CACHE['gpu'] = _windows_gpu_inventory()
    _ENUM_CACHE['storage'] = _windows_storage_inventory()
    _ENUM_CACHE['ts'] = now
    return copy.deepcopy(_ENUM_CACHE)

def _name_match(a, b):
    a = _norm_hw_name(a)
    b = _norm_hw_name(b)
    if not a or not b:
        return False
    if a == b:
        return True
    at = set(a.split())
    bt = set(b.split())
    common = at & bt
    return len(common) >= 2 and len(common) / max(1, min(len(at), len(bt))) >= 0.6

def _gpu_kind(name, hw_type=None):
    """No infiere si una GPU es integrada/dedicada a partir de la marca o el nombre."""
    return 'UNKNOWN'

def _merge_gpu_inventory(lhm_gpus, os_gpus):
    merged = []
    used_os = set()
    for lhm in lhm_gpus:
        entry = copy.deepcopy(lhm)
        entry['telemetry_available'] = True
        entry['inventory_sources'] = ['LibreHardwareMonitorLib']
        entry['gpu_kind'] = _gpu_kind(entry.get('name'), entry.get('hardware_type'))
        entry['os_inventory'] = None
        for idx, os_gpu in enumerate(os_gpus):
            if idx in used_os:
                continue
            if _name_match(entry.get('name'), os_gpu.get('name')):
                entry['os_inventory'] = copy.deepcopy(os_gpu)
                entry['inventory_sources'].append('Win32_VideoController')
                used_os.add(idx)
                break
        merged.append(entry)
    for idx, os_gpu in enumerate(os_gpus):
        if idx in used_os:
            continue
        merged.append({'name': os_gpu.get('name'), 'hardware_type': None, 'gpu_kind': _gpu_kind(os_gpu.get('name')), 'telemetry_available': False, 'inventory_sources': ['Win32_VideoController'], 'os_inventory': copy.deepcopy(os_gpu), 'source': 'Win32_VideoController', 'quality': 'INVENTORY_ONLY', '_certified_metrics': {}, 'temperature_c': None, 'hotspot_c': None, 'usage_percent': None, 'memory_usage_percent': None, 'core_clock_mhz': None, 'memory_clock_mhz': None, 'power_w': None, 'memory_total_mb': None, 'memory_used_mb': None})
    for i, entry in enumerate(merged):
        entry['inventory_index'] = i
    return merged

def _storage_serial(value):
    return re.sub(r'\s+', '', str(value or '')).strip().casefold()


def _storage_identity_match(lhm, os_disk):
    """Comprueba identidad sin permitir que el modelo contradiga un serial real."""
    lserial = _storage_serial(lhm.get('serial_number'))
    oserial = _storage_serial(os_disk.get('serial_number'))
    if lserial and oserial:
        return lserial == oserial
    return _name_match(
        lhm.get('model') or lhm.get('name'),
        os_disk.get('model') or os_disk.get('name'),
    )


def _attach_os_storage(entry, os_disk):
    entry['os_inventory'] = copy.deepcopy(os_disk)
    if 'Win32_DiskDrive' not in entry['inventory_sources']:
        entry['inventory_sources'].append('Win32_DiskDrive')
    entry['identity_ambiguous'] = False
    entry['os_inventory_candidates_count'] = 1


def _merge_storage_inventory(lhm_disks, os_disks):
    """Fusiona LHM + Win32_DiskDrive sin adivinar entre discos idénticos.

    Serial exacto tiene prioridad. Una coincidencia por modelo se acepta solo si
    existe un único candidato en ambos sentidos. Si dos unidades tienen el mismo
    modelo y no hay serial suficiente para diferenciarlas, CorePulse conserva la
    telemetría de cada entrada LHM pero deja ``os_inventory=None``; así tampoco
    consulta SMART de un PhysicalDrive arbitrario.
    """
    merged = []
    used_os = set()

    for lhm in lhm_disks:
        entry = copy.deepcopy(lhm)
        entry['telemetry_available'] = True
        entry['inventory_sources'] = ['LibreHardwareMonitorLib']
        entry['os_inventory'] = None
        entry['identity_ambiguous'] = False
        entry['os_inventory_candidates_count'] = 0
        merged.append(entry)

    # 1) Serial exacto e inequívoco.
    for entry in merged:
        lserial = _storage_serial(entry.get('serial_number'))
        if not lserial:
            continue
        candidates = [
            idx for idx, os_disk in enumerate(os_disks)
            if idx not in used_os
            and _storage_serial(os_disk.get('serial_number')) == lserial
        ]
        if len(candidates) == 1:
            idx = candidates[0]
            _attach_os_storage(entry, os_disks[idx])
            used_os.add(idx)
        elif len(candidates) > 1:
            entry['identity_ambiguous'] = True
            entry['os_inventory_candidates_count'] = len(candidates)

    # 2) Modelo/nombre solo si el emparejamiento es uno-a-uno.
    for entry_index, entry in enumerate(merged):
        if isinstance(entry.get('os_inventory'), dict):
            continue
        candidates = [
            idx for idx, os_disk in enumerate(os_disks)
            if idx not in used_os
            and _name_match(
                entry.get('model') or entry.get('name'),
                os_disk.get('model') or os_disk.get('name'),
            )
        ]
        entry['os_inventory_candidates_count'] = len(candidates)
        if len(candidates) != 1:
            if len(candidates) > 1:
                entry['identity_ambiguous'] = True
            continue

        candidate_index = candidates[0]
        candidate = os_disks[candidate_index]
        contenders = [
            idx for idx, other in enumerate(merged)
            if idx != entry_index
            and not isinstance(other.get('os_inventory'), dict)
            and _name_match(
                other.get('model') or other.get('name'),
                candidate.get('model') or candidate.get('name'),
            )
        ]
        if contenders:
            entry['identity_ambiguous'] = True
            for idx in contenders:
                merged[idx]['identity_ambiguous'] = True
                merged[idx]['os_inventory_candidates_count'] = max(
                    int(merged[idx].get('os_inventory_candidates_count') or 0),
                    1,
                )
            continue

        _attach_os_storage(entry, candidate)
        used_os.add(candidate_index)

    # 3) Win32-only: se agrega si no parece ser la contraparte ambigua de LHM.
    # Evita duplicar dos veces el mismo disco cuando falta información para mapearlo.
    for idx, os_disk in enumerate(os_disks):
        if idx in used_os:
            continue
        unresolved_lhm = [
            entry for entry in merged
            if not isinstance(entry.get('os_inventory'), dict)
            and _name_match(
                entry.get('model') or entry.get('name'),
                os_disk.get('model') or os_disk.get('name'),
            )
        ]
        if unresolved_lhm:
            for entry in unresolved_lhm:
                entry['identity_ambiguous'] = True
            continue

        merged.append({
            'name': os_disk.get('model') or os_disk.get('name'),
            'model': os_disk.get('model'),
            'serial_number': os_disk.get('serial_number'),
            'device_id': os_disk.get('device_id'),
            'disk_index': os_disk.get('disk_index'),
            'interface_type': os_disk.get('interface_type'),
            'media_type_os': os_disk.get('media_type_os'),
            'size_bytes_os': os_disk.get('size_bytes_os'),
            'telemetry_available': False,
            'inventory_sources': ['Win32_DiskDrive'],
            'os_inventory': copy.deepcopy(os_disk),
            'identity_ambiguous': False,
            'os_inventory_candidates_count': 1,
            'source': 'Win32_DiskDrive',
            'quality': 'INVENTORY_ONLY',
            '_certified_metrics': {},
            'temperature_c': None,
            'life_percent': None,
            'power_on_hours': None,
            'power_on_count': None,
        })

    for i, entry in enumerate(merged):
        entry['inventory_index'] = i
    return merged


def get_universal_hardware_inventory(force_refresh=False):
    """Obtiene la operación `get_universal_hardware_inventory` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
    if force_refresh:
        _ENUM_CACHE['ts'] = 0.0
    raw = _base.get_system_telemetry(wait_for_first=True)
    cert = _certify_snapshot_without_inventory(raw)
    os_inv = _enum_cached()
    return {'version': VERSION, 'policy': 'REAL_OR_NA_ONLY', 'gpus': _merge_gpu_inventory(cert.get('_gpus') or [], os_inv.get('gpu') or []), 'storage': _merge_storage_inventory(cert.get('_storage_devices') or [], os_inv.get('storage') or []), 'timestamp': time.time()}

def _certify_snapshot_without_inventory(snapshot):
    s = copy.deepcopy(snapshot) if isinstance(snapshot, dict) else {}
    snapshot_ts = _finite(s.get('_snapshot_timestamp')) or time.time()
    cpu = s.get('_cpu') if isinstance(s.get('_cpu'), dict) else {}
    gpus = s.get('_gpus') if isinstance(s.get('_gpus'), list) else []
    storage = s.get('_storage_devices') if isinstance(s.get('_storage_devices'), list) else []
    battery = s.get('_battery') if isinstance(s.get('_battery'), dict) else None
    _apply_nested_certification(cpu, {'package_temp_c': '°C', 'core_max_temp_c': '°C', 'core_average_temp_c': '°C', 'distance_to_tjmax_min_c': '°C', 'clock_avg_ghz': 'GHz', 'clock_max_ghz': 'GHz', 'bus_clock_mhz': 'MHz', 'package_power_w': 'W', 'total_load_percent': '%', 'core_voltage_v': 'V'}, snapshot_ts)
    for gpu in gpus:
        _apply_nested_certification(gpu, {'temperature_c': '°C', 'hotspot_c': '°C', 'usage_percent': '%', 'memory_usage_percent': '%', 'core_clock_mhz': 'MHz', 'memory_clock_mhz': 'MHz', 'power_w': 'W', 'memory_total_mb': 'MB', 'memory_used_mb': 'MB', 'fan_rpm': 'RPM', 'fan_control_percent': '%', 'core_voltage_v': 'V'}, snapshot_ts)
    for disk in storage:
        _apply_nested_certification(disk, {'temperature_c': '°C', 'warning_temperature_c': '°C', 'critical_temperature_c': '°C', 'life_percent': '%', 'power_on_hours': 'h', 'power_on_count': 'count', 'data_read': None, 'data_written': None, 'used_space_percent': '%', 'free_space_gb': 'GB', 'total_space_gb': 'GB'}, snapshot_ts)
    if battery is not None:
        _apply_nested_certification(battery, {'designed_capacity_mwh': 'mWh', 'full_charge_capacity_mwh': 'mWh', 'remaining_capacity_mwh': 'mWh', 'degradation_percent': '%', 'charge_percent': '%', 'voltage_v': 'V', 'current_ma': 'mA', 'charge_discharge_rate_w': 'W'}, snapshot_ts)
    anomaly_events = []
    anomaly_events.extend([{'device': 'CPU', **a} for a in _apply_cross_metric_guards(cpu, 'cpu', snapshot_ts)])
    for gpu in gpus:
        anomaly_events.extend([{'device': gpu.get('name') or 'GPU', **a} for a in _apply_cross_metric_guards(gpu, 'gpu', snapshot_ts)])
    for disk in storage:
        anomaly_events.extend([{'device': disk.get('name') or 'STORAGE', **a} for a in _apply_cross_metric_guards(disk, 'storage', snapshot_ts)])
    if battery is not None:
        anomaly_events.extend([{'device': 'BATTERY', **a} for a in _apply_cross_metric_guards(battery, 'battery', snapshot_ts)])
    metrics = s.get('_metrics') if isinstance(s.get('_metrics'), dict) else {}
    old_cpu_usage = metrics.get('cpu_usage') if isinstance(metrics.get('cpu_usage'), dict) else {}
    cpu_usage_ts = old_cpu_usage.get('timestamp')
    cpu_usage_cert = _certify_metric('cpu_usage', s.get('cpu_usage'), '%', 'psutil.cpu_percent', None, cpu_usage_ts, snapshot_ts)
    ram_usage_cert = _certify_metric('ram_usage', s.get('ram_usage'), '%', 'psutil.virtual_memory', None, snapshot_ts, snapshot_ts)
    cpu_temp_meta = _meta_from_nested(cpu, 'package_temp_c')
    cpu_clock_meta = _meta_from_nested(cpu, 'clock_avg_ghz')
    primary = _primary_gpu(gpus)
    gpu_usage_meta = _meta_from_nested(primary, 'usage_percent')
    gpu_temp_meta = _meta_from_nested(primary, 'temperature_c')
    gpu_vram_meta = _meta_from_nested(primary, 'memory_total_mb')
    top = {'cpu_usage': cpu_usage_cert, 'cpu_temp': _certify_metric('cpu_temp', (cpu.get('_certified_metrics') or {}).get('package_temp_c', {}).get('last_real_value'), '°C', 'LibreHardwareMonitorLib', cpu_temp_meta.get('sensor'), cpu_temp_meta.get('sensor_timestamp'), snapshot_ts), 'cpu_ghz': _certify_metric('cpu_ghz', (cpu.get('_certified_metrics') or {}).get('clock_avg_ghz', {}).get('last_real_value'), 'GHz', 'LibreHardwareMonitorLib', cpu_clock_meta.get('sensor'), cpu_clock_meta.get('sensor_timestamp'), snapshot_ts, derived_from_real=True), 'ram_usage': ram_usage_cert, 'gpu_usage': _certify_metric('gpu_usage', (primary.get('_certified_metrics') or {}).get('usage_percent', {}).get('last_real_value'), '%', 'LibreHardwareMonitorLib', gpu_usage_meta.get('sensor'), gpu_usage_meta.get('sensor_timestamp'), snapshot_ts), 'gpu_temp': _certify_metric('gpu_temp', (primary.get('_certified_metrics') or {}).get('temperature_c', {}).get('last_real_value'), '°C', 'LibreHardwareMonitorLib', gpu_temp_meta.get('sensor'), gpu_temp_meta.get('sensor_timestamp'), snapshot_ts), 'gpu_vram_gb': _certify_metric('gpu_vram_gb', None if (primary.get('_certified_metrics') or {}).get('memory_total_mb', {}).get('last_real_value') is None else round(float((primary.get('_certified_metrics') or {})['memory_total_mb']['last_real_value']) / 1024.0, 2), 'GB', 'LibreHardwareMonitorLib', gpu_vram_meta.get('sensor'), gpu_vram_meta.get('sensor_timestamp'), snapshot_ts)}
    s['_metrics'] = top
    for key, cert in top.items():
        s[key] = cert['value']
    if cpu.get('hardware'):
        s['cpu_name'] = cpu.get('hardware')
    if primary.get('name'):
        s['gpu_name'] = primary.get('name')
    s['_cpu'] = cpu
    s['_gpus'] = gpus
    s['_storage_devices'] = storage
    s['_battery'] = battery
    s['_telemetry_version'] = '0.9.16.6'
    s['_telemetry_pipeline'] = PIPELINE_ID
    s['_telemetry_certification'] = {'version': VERSION, 'pipeline': PIPELINE_ID, 'clean_shutdown_contract': True, 'policy': 'REAL_OR_NA_ONLY', 'quality_states': ['VALID', 'STALE', 'UNAVAILABLE', 'ERROR'], 'sensor_timestamp_preserved': True, 'snapshot_timestamp_separate': True, 'cached_sample_never_retimestamped': True, 'nan_inf_rejected': True, 'out_of_range_rejected_not_clamped': True, 'synthetic_adjustment': False, 'interpolation': False, 'offset_applied': 0.0, 'snapshot_timestamp': snapshot_ts, 'snapshot_age_seconds': _finite(s.get('_snapshot_age_seconds'))}
    s['_physical_anomaly_events'] = list(anomaly_events)
    return s

def _certify_snapshot(snapshot):
    s = _certify_snapshot_without_inventory(snapshot)
    os_inv = _enum_cached()
    s['_gpu_inventory'] = _merge_gpu_inventory(s.get('_gpus') or [], os_inv.get('gpu') or [])
    s['_storage_inventory'] = _merge_storage_inventory(s.get('_storage_devices') or [], os_inv.get('storage') or [])
    s['_hardware_enumeration'] = {'version': VERSION, 'policy': 'REAL_OR_NA_ONLY', 'gpu_count': len(s['_gpu_inventory']), 'storage_count': len(s['_storage_inventory']), 'gpu_sources': ['LibreHardwareMonitorLib', 'Win32_VideoController'], 'storage_sources': ['LibreHardwareMonitorLib', 'Win32_DiskDrive'], 'inventory_only_devices_keep_sensor_values_na': True, 'deduplication_uses_real_identity_fields': True, 'active_gpu_not_assumed': True}
    s['_hardware_capability_matrix'] = _build_device_capability_matrix(s)
    s['_per_metric_certification'] = {'version': VERSION, 'policy': 'REAL_OR_NA_ONLY', 'per_metric_quality': True, 'capability_matrix': True, 'unavailable_reason_explicit': True, 'inventory_only_devices_never_receive_fake_metrics': True, 'synthetic_adjustment': False, 'interpolation': False, 'offset_applied': 0.0}
    s['_cross_pc_validation'] = {'version': VERSION, 'pipeline': PIPELINE_ID, 'audit_api_available': True, 'machine_specific_certificate': True, 'universal_claim': False, 'real_or_na_preserved': True, 'warmup_reliability_fix': True}
    anomaly_events = list(s.get('_physical_anomaly_events') or [])
    s['_physical_validation'] = {'version': VERSION, 'policy': 'REJECT_ANOMALY_NEVER_CLAMP', 'nan_inf_rejected': True, 'range_validation': True, 'cross_metric_validation': True, 'anomaly_scope_fix': True, 'anomaly_count': len(anomaly_events), 'anomalies': anomaly_events, 'synthetic_adjustment': False, 'interpolation': False, 'offset_applied': 0.0}
    s['_runtime_capability'] = {'version': VERSION, 'pipeline': PIPELINE_ID, 'pawnio_certification_available': True, 'lhm_runtime_certification_available': True, 'real_or_na_preserved': True}
    s['_evidence_pack'] = {'version': VERSION, 'pipeline': PIPELINE_ID, 'evidence_bundle_api': True, 'machine_specific_only': True, 'real_or_na_preserved': True}
    return s

def _capability_reason(certified_metric):
    if not isinstance(certified_metric, dict):
        return 'SENSOR_NOT_EXPOSED'
    q = certified_metric.get('quality')
    reason = certified_metric.get('reason')
    if q == 'VALID':
        return None
    if q == 'STALE':
        return reason or 'SENSOR_SAMPLE_OLD'
    if q == 'ERROR':
        return reason or 'SENSOR_ERROR'
    if q == 'UNAVAILABLE':
        return reason or 'SENSOR_NOT_EXPOSED'
    return 'SENSOR_NOT_EXPOSED'

def _metric_capability(name, certified_metric):
    meta = certified_metric if isinstance(certified_metric, dict) else {}
    return {'metric': name, 'available': meta.get('quality') == 'VALID', 'quality': meta.get('quality') or 'UNAVAILABLE', 'reason': _capability_reason(meta), 'source': meta.get('source'), 'sensor': meta.get('sensor'), 'unit': meta.get('unit'), 'sensor_timestamp': meta.get('sensor_timestamp'), 'snapshot_timestamp': meta.get('snapshot_timestamp'), 'age_seconds': meta.get('age_seconds'), 'derived_from_real': bool(meta.get('derived_from_real')), 'synthetic_adjustment': False, 'interpolation': False, 'offset_applied': 0.0}

def _build_device_capability_matrix(snapshot):
    """Construye la operación `build_device_capability_matrix` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
    matrix = {'version': VERSION, 'policy': 'REAL_OR_NA_ONLY', 'generated_at': time.time(), 'cpu': {}, 'gpus': [], 'storage': [], 'battery': None}
    cpu = snapshot.get('_cpu') if isinstance(snapshot.get('_cpu'), dict) else {}
    cpu_metrics = cpu.get('_certified_metrics') if isinstance(cpu.get('_certified_metrics'), dict) else {}
    matrix['cpu'] = {'name': cpu.get('hardware') or snapshot.get('cpu_name'), 'inventory_available': bool(cpu.get('hardware') or snapshot.get('cpu_name')), 'metrics': {key: _metric_capability(key, cpu_metrics.get(key)) for key in ('package_temp_c', 'core_max_temp_c', 'core_average_temp_c', 'distance_to_tjmax_min_c', 'clock_avg_ghz', 'clock_max_ghz', 'package_power_w')}}
    gpu_inventory = snapshot.get('_gpu_inventory') if isinstance(snapshot.get('_gpu_inventory'), list) else []
    for gpu in gpu_inventory:
        cert = gpu.get('_certified_metrics') if isinstance(gpu.get('_certified_metrics'), dict) else {}
        metrics = {}
        for key in ('temperature_c', 'hotspot_c', 'usage_percent', 'memory_usage_percent', 'core_clock_mhz', 'memory_clock_mhz', 'power_w', 'memory_total_mb', 'memory_used_mb'):
            metrics[key] = _metric_capability(key, cert.get(key))
            if not gpu.get('telemetry_available'):
                metrics[key]['available'] = False
                metrics[key]['quality'] = 'UNAVAILABLE'
                metrics[key]['reason'] = 'SENSOR_NOT_EXPOSED'
                metrics[key]['source'] = None
                metrics[key]['sensor'] = None
        matrix['gpus'].append({'name': gpu.get('name'), 'gpu_kind': gpu.get('gpu_kind'), 'inventory_available': True, 'telemetry_available': bool(gpu.get('telemetry_available')), 'inventory_sources': gpu.get('inventory_sources') or [], 'metrics': metrics})
    storage_inventory = snapshot.get('_storage_inventory') if isinstance(snapshot.get('_storage_inventory'), list) else []
    for disk in storage_inventory:
        cert = disk.get('_certified_metrics') if isinstance(disk.get('_certified_metrics'), dict) else {}
        metrics = {}
        for key in ('temperature_c', 'warning_temperature_c', 'critical_temperature_c', 'life_percent', 'power_on_hours', 'power_on_count', 'data_read', 'data_written', 'used_space_percent', 'free_space_gb', 'total_space_gb'):
            metrics[key] = _metric_capability(key, cert.get(key))
            if not disk.get('telemetry_available'):
                metrics[key]['available'] = False
                metrics[key]['quality'] = 'UNAVAILABLE'
                metrics[key]['reason'] = 'SENSOR_NOT_EXPOSED'
                metrics[key]['source'] = None
                metrics[key]['sensor'] = None
        matrix['storage'].append({'name': disk.get('name'), 'inventory_available': True, 'telemetry_available': bool(disk.get('telemetry_available')), 'inventory_sources': disk.get('inventory_sources') or [], 'os_inventory': disk.get('os_inventory'), 'metrics': metrics})
    battery = snapshot.get('_battery') if isinstance(snapshot.get('_battery'), dict) else None
    if battery is not None:
        cert = battery.get('_certified_metrics') if isinstance(battery.get('_certified_metrics'), dict) else {}
        matrix['battery'] = {'inventory_available': True, 'metrics': {key: _metric_capability(key, cert.get(key)) for key in ('designed_capacity_mwh', 'full_charge_capacity_mwh', 'remaining_capacity_mwh', 'degradation_percent', 'charge_percent', 'voltage_v', 'current_ma', 'charge_discharge_rate_w')}}
    else:
        matrix['battery'] = {'inventory_available': False, 'metrics': {}, 'reason': 'NOT_PRESENT_OR_NOT_EXPOSED'}
    return matrix

def get_hardware_capability_matrix(wait_for_first=True):
    snapshot = get_system_telemetry(wait_for_first=wait_for_first)
    return copy.deepcopy(snapshot.get('_hardware_capability_matrix') or {})

def _platform_architecture():
    try:
        return platform.architecture()[0]
    except Exception:
        return None

def _is_admin_windows():
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False

def _detect_pawnio():
    """Gestiona la operación `detect_pawnio` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
    if platform.system() != 'Windows':
        return {'detected': False, 'reason': 'NON_WINDOWS'}
    try:
        import winreg
        roots = [(winreg.HKEY_LOCAL_MACHINE, 'SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall'), (winreg.HKEY_LOCAL_MACHINE, 'SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall')]
        for hive, root_path in roots:
            try:
                with winreg.OpenKey(hive, root_path) as root:
                    count = winreg.QueryInfoKey(root)[0]
                    for i in range(count):
                        try:
                            subname = winreg.EnumKey(root, i)
                            with winreg.OpenKey(root, subname) as sub:
                                try:
                                    display = str(winreg.QueryValueEx(sub, 'DisplayName')[0])
                                except OSError:
                                    continue
                                if 'pawnio' in display.lower():
                                    try:
                                        ver = str(winreg.QueryValueEx(sub, 'DisplayVersion')[0])
                                    except OSError:
                                        ver = None
                                    return {'detected': True, 'source': 'Windows Registry', 'display_name': display, 'version': ver}
                        except OSError:
                            continue
            except OSError:
                continue
    except Exception:
        pass
    try:
        windir = Path(os.environ.get('WINDIR', 'C:\\Windows'))
        driver = windir / 'System32' / 'drivers' / 'PawnIO.sys'
        if driver.exists():
            return {'detected': True, 'source': 'Driver file', 'path': str(driver)}
    except Exception:
        pass
    return {'detected': False, 'reason': 'NOT_DETECTED'}

def _device_metric_summary(metrics):
    summary = {'VALID': 0, 'STALE': 0, 'UNAVAILABLE': 0, 'ERROR': 0, 'OTHER': 0}
    for meta in (metrics or {}).values():
        q = str((meta or {}).get('quality') or 'OTHER').upper()
        if q not in summary:
            q = 'OTHER'
        summary[q] += 1
    return summary

def _compatibility_grade(snapshot):
    """Gestiona la operación `compatibility_grade` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
    matrix = snapshot.get('_hardware_capability_matrix') or {}
    critical = []
    top = snapshot.get('_metrics') or {}
    for key in ('cpu_usage', 'cpu_temp', 'cpu_ghz', 'ram_usage'):
        meta = top.get(key) or {}
        critical.append(meta.get('quality') == 'VALID')
    gpus = matrix.get('gpus') or []
    storage = matrix.get('storage') or []
    gpu_any_real = any((any(((m or {}).get('quality') == 'VALID' for m in (g.get('metrics') or {}).values())) for g in gpus))
    storage_any_real = any((any(((m or {}).get('quality') == 'VALID' for m in (d.get('metrics') or {}).values())) for d in storage))
    critical.extend([gpu_any_real or not gpus, storage_any_real or not storage])
    if all(critical):
        return 'FULL_CORE_COVERAGE'
    if any(critical):
        return 'PARTIAL_CORE_COVERAGE'
    return 'INSUFFICIENT_CORE_COVERAGE'

def _get_cross_pc_compatibility_audit_once(wait_for_first=True):
    """Obtiene la operación `get_cross_pc_compatibility_audit_once` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
    s = get_system_telemetry(wait_for_first=wait_for_first)
    matrix = s.get('_hardware_capability_matrix') or {}
    enum = s.get('_hardware_enumeration') or {}
    gpus = []
    for gpu in matrix.get('gpus') or []:
        gpus.append({'name': gpu.get('name'), 'gpu_kind': gpu.get('gpu_kind'), 'inventory_available': gpu.get('inventory_available'), 'telemetry_available': gpu.get('telemetry_available'), 'inventory_sources': gpu.get('inventory_sources') or [], 'metric_summary': _device_metric_summary(gpu.get('metrics') or {}), 'metrics': copy.deepcopy(gpu.get('metrics') or {})})
    storage = []
    for disk in matrix.get('storage') or []:
        storage.append({'name': disk.get('name'), 'inventory_available': disk.get('inventory_available'), 'telemetry_available': disk.get('telemetry_available'), 'inventory_sources': disk.get('inventory_sources') or [], 'metric_summary': _device_metric_summary(disk.get('metrics') or {}), 'metrics': copy.deepcopy(disk.get('metrics') or {})})
    battery = matrix.get('battery') or {}
    audit = {'version': VERSION, 'pipeline': PIPELINE_ID, 'policy': 'REAL_OR_NA_ONLY', 'generated_at': time.time(), 'host': {'os': platform.system(), 'os_release': platform.release(), 'os_version': platform.version(), 'architecture': _platform_architecture(), 'python_version': platform.python_version(), 'admin': _is_admin_windows()}, 'runtime_dependencies': {'pawnio': _detect_pawnio(), 'lhm_provider': {'available': bool(s.get('_cpu') or s.get('_gpus') or s.get('_storage_devices')), 'source': 'LibreHardwareMonitorLib'}}, 'hardware': {'cpu': copy.deepcopy(matrix.get('cpu') or {}), 'gpus': gpus, 'storage': storage, 'battery': copy.deepcopy(battery), 'gpu_count': len(gpus), 'storage_count': len(storage), 'enumeration': copy.deepcopy(enum)}, 'core_metrics': {key: copy.deepcopy((s.get('_metrics') or {}).get(key) or {}) for key in ('cpu_usage', 'cpu_temp', 'cpu_ghz', 'ram_usage', 'gpu_usage', 'gpu_temp', 'gpu_vram_gb')}, 'compatibility_grade': _compatibility_grade(s), 'universal_claim': False, 'universal_validation_note': 'Este informe certifica solo el equipo actual. La compatibilidad universal debe validarse repitiendo la misma auditoría en múltiples arquitecturas, fabricantes, equipos portátiles/escritorio y configuraciones multi-GPU/multi-almacenamiento.', 'integrity': {'real_or_na': True, 'per_metric_quality': True, 'original_sensor_timestamp': True, 'freshness_states': ['VALID', 'STALE', 'UNAVAILABLE', 'ERROR'], 'inventory_only_devices_never_receive_fake_metrics': True, 'no_synthetic_adjustment': True, 'no_interpolation': True, 'no_artificial_offset': True}}
    return audit
AUDIT_WARMUP_TIMEOUT_SECONDS = 8.0
AUDIT_WARMUP_INTERVAL_SECONDS = 0.45
AUDIT_MIN_STABLE_SNAPSHOTS = 2

def _quality(meta):
    return str((meta or {}).get('quality') or '').upper()

def _snapshot_readiness(snapshot):
    """Gestiona la operación `snapshot_readiness` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
    metrics = snapshot.get('_metrics') or {}
    snapshot_age = _finite(snapshot.get('_snapshot_age_seconds'))
    snapshot_fresh = snapshot_age is None or snapshot_age <= SNAPSHOT_VALID_MAX_AGE_SECONDS
    psutil_ready = _quality(metrics.get('cpu_usage')) == 'VALID' and _quality(metrics.get('ram_usage')) == 'VALID'
    lhm_devices_exist = bool(snapshot.get('_cpu') or snapshot.get('_gpus') or snapshot.get('_storage_devices') or snapshot.get('_battery'))
    lhm_core_keys = ('cpu_temp', 'cpu_ghz', 'gpu_usage', 'gpu_temp', 'gpu_vram_gb')
    lhm_valid_count = sum((_quality(metrics.get(k)) == 'VALID' for k in lhm_core_keys))
    nested_valid_count = 0
    for obj in [snapshot.get('_cpu')]:
        if isinstance(obj, dict):
            nested_valid_count += sum((_quality(m) == 'VALID' for m in (obj.get('_certified_metrics') or {}).values()))
    for collection_name in ('_gpus', '_storage_devices'):
        for obj in snapshot.get(collection_name) or []:
            if isinstance(obj, dict):
                nested_valid_count += sum((_quality(m) == 'VALID' for m in (obj.get('_certified_metrics') or {}).values()))
    battery = snapshot.get('_battery')
    if isinstance(battery, dict):
        nested_valid_count += sum((_quality(m) == 'VALID' for m in (battery.get('_certified_metrics') or {}).values()))
    lhm_ready = not lhm_devices_exist or (lhm_valid_count > 0 or nested_valid_count > 0)
    return {'ready': bool(snapshot_fresh and psutil_ready and lhm_ready), 'snapshot_fresh': bool(snapshot_fresh), 'psutil_ready': bool(psutil_ready), 'lhm_devices_exist': bool(lhm_devices_exist), 'lhm_valid_core_metrics': int(lhm_valid_count), 'lhm_valid_nested_metrics': int(nested_valid_count), 'snapshot_age_seconds': snapshot_age}

def _snapshot_score(snapshot):
    """Gestiona la operación `snapshot_score` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
    readiness = _snapshot_readiness(snapshot)
    metrics = snapshot.get('_metrics') or {}
    valid_top = sum((_quality(m) == 'VALID' for m in metrics.values()))
    nested_valid = readiness['lhm_valid_nested_metrics']
    inventory_count = len(snapshot.get('_gpu_inventory') or []) + len(snapshot.get('_storage_inventory') or [])
    return (1000 if readiness['ready'] else 0, valid_top, nested_valid, inventory_count, -float(readiness['snapshot_age_seconds'] or 0.0))

def _collect_audit_ready_snapshot():
    """Recopila la operación `collect_audit_ready_snapshot` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
    started = time.time()
    samples = []
    stable_ready = 0
    best = None
    best_score = None
    while True:
        snap = get_system_telemetry(wait_for_first=True)
        readiness = _snapshot_readiness(snap)
        samples.append({'index': len(samples) + 1, 'timestamp': snap.get('_snapshot_timestamp'), 'snapshot_age_seconds': snap.get('_snapshot_age_seconds'), 'readiness': readiness, 'core_quality': {key: _quality((snap.get('_metrics') or {}).get(key)) for key in ('cpu_usage', 'cpu_temp', 'cpu_ghz', 'ram_usage', 'gpu_usage', 'gpu_temp', 'gpu_vram_gb')}})
        score = _snapshot_score(snap)
        if best is None or score > best_score:
            best = snap
            best_score = score
        if readiness['ready']:
            stable_ready += 1
        else:
            stable_ready = 0
        elapsed = time.time() - started
        if stable_ready >= AUDIT_MIN_STABLE_SNAPSHOTS:
            break
        if elapsed >= AUDIT_WARMUP_TIMEOUT_SECONDS:
            break
        time.sleep(AUDIT_WARMUP_INTERVAL_SECONDS)
    selected_ready = _snapshot_readiness(best or {})
    return (best or {}, {'warmup_seconds': round(time.time() - started, 3), 'sample_count': len(samples), 'stable_ready_snapshots': stable_ready, 'selected_ready': bool(selected_ready.get('ready')), 'selected_readiness': selected_ready, 'samples': samples, 'timeout_seconds': AUDIT_WARMUP_TIMEOUT_SECONDS, 'min_stable_snapshots': AUDIT_MIN_STABLE_SNAPSHOTS, 'selection_policy': 'BEST_SINGLE_REAL_SNAPSHOT_NO_AVERAGING_NO_INTERPOLATION'})

def get_cross_pc_compatibility_audit(wait_for_first=True):
    """Obtiene la operación `get_cross_pc_compatibility_audit` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
    snapshot, warmup = _collect_audit_ready_snapshot()
    matrix = snapshot.get('_hardware_capability_matrix') or {}
    enum = snapshot.get('_hardware_enumeration') or {}
    gpus = []
    for gpu in matrix.get('gpus') or []:
        gpus.append({'name': gpu.get('name'), 'gpu_kind': gpu.get('gpu_kind'), 'inventory_available': gpu.get('inventory_available'), 'telemetry_available': gpu.get('telemetry_available'), 'inventory_sources': gpu.get('inventory_sources') or [], 'metric_summary': _device_metric_summary(gpu.get('metrics') or {}), 'metrics': copy.deepcopy(gpu.get('metrics') or {})})
    storage = []
    for disk in matrix.get('storage') or []:
        storage.append({'name': disk.get('name'), 'inventory_available': disk.get('inventory_available'), 'telemetry_available': disk.get('telemetry_available'), 'inventory_sources': disk.get('inventory_sources') or [], 'metric_summary': _device_metric_summary(disk.get('metrics') or {}), 'metrics': copy.deepcopy(disk.get('metrics') or {})})
    audit = {'version': VERSION, 'pipeline': PIPELINE_ID, 'policy': 'REAL_OR_NA_ONLY', 'generated_at': time.time(), 'warmup': warmup, 'host': {'os': platform.system(), 'os_release': platform.release(), 'os_version': platform.version(), 'architecture': _platform_architecture(), 'python_version': platform.python_version(), 'admin': _is_admin_windows()}, 'runtime_dependencies': {'pawnio': _detect_pawnio(), 'lhm_provider': {'available': bool(snapshot.get('_cpu') or snapshot.get('_gpus') or snapshot.get('_storage_devices')), 'source': 'LibreHardwareMonitorLib', 'ready_for_audit': bool(warmup.get('selected_ready'))}}, 'hardware': {'cpu': copy.deepcopy(matrix.get('cpu') or {}), 'gpus': gpus, 'storage': storage, 'battery': copy.deepcopy(matrix.get('battery') or {}), 'gpu_count': len(gpus), 'storage_count': len(storage), 'enumeration': copy.deepcopy(enum)}, 'core_metrics': {key: copy.deepcopy((snapshot.get('_metrics') or {}).get(key) or {}) for key in ('cpu_usage', 'cpu_temp', 'cpu_ghz', 'ram_usage', 'gpu_usage', 'gpu_temp', 'gpu_vram_gb')}, 'compatibility_grade': _compatibility_grade(snapshot), 'audit_ready': bool(warmup.get('selected_ready')), 'universal_claim': False, 'universal_validation_note': 'Este informe certifica solo el equipo actual. La compatibilidad universal debe validarse repitiendo la misma auditoría en múltiples arquitecturas, fabricantes, equipos portátiles/escritorio y configuraciones multi-GPU/multi-almacenamiento.', 'integrity': {'real_or_na': True, 'single_real_snapshot_used': True, 'warmup_does_not_average_or_interpolate': True, 'per_metric_quality': True, 'original_sensor_timestamp': True, 'freshness_states': ['VALID', 'STALE', 'UNAVAILABLE', 'ERROR'], 'inventory_only_devices_never_receive_fake_metrics': True, 'no_synthetic_adjustment': True, 'no_interpolation': True, 'no_artificial_offset': True}}
    return audit

def _count_lhm_metrics(snapshot):
    counts = {'cpu': 0, 'gpu': 0, 'storage': 0, 'battery': 0, 'valid': 0, 'unavailable': 0, 'stale': 0, 'error': 0}

    def add(metrics, category):
        if not isinstance(metrics, dict):
            return
        for meta in metrics.values():
            if not isinstance(meta, dict):
                continue
            counts[category] += 1
            q = str(meta.get('quality') or '').upper()
            if q == 'VALID':
                counts['valid'] += 1
            elif q == 'UNAVAILABLE':
                counts['unavailable'] += 1
            elif q == 'STALE':
                counts['stale'] += 1
            elif q == 'ERROR':
                counts['error'] += 1
    cpu = snapshot.get('_cpu')
    if isinstance(cpu, dict):
        add(cpu.get('_certified_metrics'), 'cpu')
    for gpu in snapshot.get('_gpus') or []:
        if isinstance(gpu, dict):
            add(gpu.get('_certified_metrics'), 'gpu')
    for disk in snapshot.get('_storage_devices') or []:
        if isinstance(disk, dict):
            add(disk.get('_certified_metrics'), 'storage')
    battery = snapshot.get('_battery')
    if isinstance(battery, dict):
        add(battery.get('_certified_metrics'), 'battery')
    return counts

def _lhm_runtime_capability(snapshot):
    counts = _count_lhm_metrics(snapshot)
    provider_available = bool(snapshot.get('_cpu') or snapshot.get('_gpus') or snapshot.get('_storage_devices') or snapshot.get('_battery'))
    if not provider_available:
        status = 'UNAVAILABLE'
    elif counts['valid'] > 0:
        status = 'READY'
    elif counts['stale'] > 0:
        status = 'STALE_ONLY'
    elif counts['error'] > 0:
        status = 'ERROR'
    else:
        status = 'NO_EXPOSED_VALID_SENSORS'
    return {'provider': 'LibreHardwareMonitorLib', 'available': provider_available, 'status': status, 'metric_counts': counts, 'freshness_contract': True, 'real_or_na': True}

def _pawnio_runtime_capability():
    detected = _detect_pawnio()
    return {'detected': bool(detected.get('detected')), 'details': detected, 'role': 'LOW_LEVEL_SENSOR_ACCESS_SUPPORT', 'required_for_all_metrics': False, 'absence_policy': 'CAPABILITY_REDUCED_OR_UNAVAILABLE_NEVER_FABRICATED'}

def get_runtime_capability_certificate(wait_for_first=True):
    """Obtiene la operación `get_runtime_capability_certificate` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
    snapshot = get_system_telemetry(wait_for_first=wait_for_first)
    lhm = _lhm_runtime_capability(snapshot)
    pawnio = _pawnio_runtime_capability()
    matrix = snapshot.get('_hardware_capability_matrix') or {}
    certificate = {'version': VERSION, 'pipeline': PIPELINE_ID, 'policy': 'REAL_OR_NA_ONLY', 'generated_at': time.time(), 'pawnio': pawnio, 'lhm': lhm, 'hardware_capability_matrix': copy.deepcopy(matrix), 'runtime_interpretation': {'pawnio_detected_and_lhm_ready': bool(pawnio.get('detected') and lhm.get('status') == 'READY'), 'missing_sensor_means_na': True, 'missing_driver_never_replaced_with_synthetic_value': True, 'inventory_only_devices_remain_inventory_only': True}}
    return certificate

def get_compatibility_evidence_bundle(wait_for_first=True):
    """Obtiene la operación `get_compatibility_evidence_bundle` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
    snapshot = get_system_telemetry(wait_for_first=wait_for_first)
    return {'version': VERSION, 'pipeline': PIPELINE_ID, 'policy': 'REAL_OR_NA_ONLY', 'generated_at': time.time(), 'telemetry_snapshot': copy.deepcopy(snapshot), 'hardware_inventory': copy.deepcopy(snapshot.get('_hardware_enumeration') or {}), 'capability_matrix': copy.deepcopy(snapshot.get('_hardware_capability_matrix') or {}), 'runtime_capability': get_runtime_capability_certificate(wait_for_first=False), 'cross_pc_audit': get_cross_pc_compatibility_audit(wait_for_first=False), 'integrity': {'real_or_na': True, 'no_synthetic_adjustment': True, 'no_interpolation': True, 'no_artificial_offset': True, 'physical_anomaly_rejection': True, 'freshness_preserved': True}}

def get_system_telemetry(wait_for_first=True):
    snapshot = _base.get_system_telemetry(wait_for_first=wait_for_first)
    return _certify_snapshot(snapshot)
_shutdown_lock = threading.Lock()
_shutdown_complete = False

def shutdown_telemetry_runtime():
    """Detiene la operación `shutdown_telemetry_runtime` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
    global _shutdown_complete
    with _shutdown_lock:
        if _shutdown_complete:
            return {'status': 'ALREADY_CLOSED', 'worker_stopped': True, 'lhm_closed': True}
        worker_stopped = False
        lhm_closed = False
        errors = []
        try:
            if hasattr(_base, 'stop_background_worker'):
                _base.stop_background_worker()
            worker_stopped = True
        except Exception as exc:
            errors.append(f'worker:{type(exc).__name__}:{exc}')
        try:
            provider = getattr(_lhm_module, '_PROVIDER', None)
            if provider is not None:
                provider.close()
            _lhm_module._PROVIDER = None
            lhm_closed = True
        except Exception as exc:
            errors.append(f'lhm:{type(exc).__name__}:{exc}')
        try:
            gc.collect()
            gc.collect()
        except Exception as exc:
            errors.append(f'gc:{type(exc).__name__}:{exc}')
        _shutdown_complete = True
        return {'status': 'CLOSED' if not errors else 'CLOSED_WITH_WARNINGS', 'worker_stopped': worker_stopped, 'lhm_closed': lhm_closed, 'errors': errors}

def stop_background_worker():
    """Detiene la operación `stop_background_worker` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
    return shutdown_telemetry_runtime()

def _atexit_shutdown():
    try:
        shutdown_telemetry_runtime()
    except Exception:
        pass
atexit.register(_atexit_shutdown)

def get_certification_contract():
    return {'version': VERSION, 'pipeline': PIPELINE_ID, 'valid_max_age_seconds': LHM_VALID_MAX_AGE_SECONDS, 'stale_timeout_seconds': LHM_STALE_TIMEOUT_SECONDS, 'policy': 'REAL_OR_NA_ONLY'}
