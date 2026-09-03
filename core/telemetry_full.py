"""Normaliza la telemetría completa de CPU, GPU, RAM, almacenamiento y batería."""
from __future__ import annotations
# Código refactorizado: nombres estables y documentación en español.
import time
from collections import defaultdict
from core.telemetry_lhm import get_system_telemetry as _get_lhm_telemetry, get_all_disks_data, calculate_preliminary_score, get_hardware_names, get_system_chassis_and_bios
from core.lhm_provider import get_lhm_provider
from core.hardware_policy import select_active_gpu

def _metric(value, unit, source, quality='VALID', error=None, sensor=None):
    data = {'value': value, 'unit': unit, 'source': source, 'quality': quality, 'timestamp': time.time(), 'error': error}
    if sensor:
        data['sensor'] = sensor
    return data

def _sensors():
    provider = get_lhm_provider()
    return (provider, provider.all_sensors())

def _first(items, predicate):
    for item in items:
        if predicate(item):
            return item
    return None

def _matching(items, hw_type=None, sensor_type=None):
    result = []
    for s in items:
        if hw_type is not None and s['hardware_type'].lower() != hw_type.lower():
            continue
        if sensor_type is not None and s['sensor_type'].lower() != sensor_type.lower():
            continue
        result.append(s)
    return result

def _pick_named(items, names):
    lowered = [(s['sensor_name'].lower(), s) for s in items]
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
        'level': '%',
        'throughput': 'B/s',
        'fan': 'RPM',
        'control': '%',
        'smalldata': 'MB',
    }.get(str(sensor_type or '').lower(), '')


def _cpu_details(sensors):
    cpu = _matching(sensors, 'Cpu')
    temps = [s for s in cpu if s['sensor_type'].lower() == 'temperature']
    clocks = [s for s in cpu if s['sensor_type'].lower() == 'clock']
    loads = [s for s in cpu if s['sensor_type'].lower() == 'load']
    power = [s for s in cpu if s['sensor_type'].lower() == 'power']
    voltages = [s for s in cpu if s['sensor_type'].lower() == 'voltage']

    package = _pick_named(temps, ['CPU Package', 'Package', 'Tctl/Tdie'])
    core_max = _pick_named(temps, ['Core Max'])
    core_avg = _pick_named(temps, ['Core Average'])
    distance = [s for s in temps if 'distance to tjmax' in s['sensor_name'].lower()]
    core_clocks = [s for s in clocks if s['sensor_name'].lower().startswith('cpu core #')]
    package_power = _pick_named(power, ['CPU Package', 'Package'])
    total_load = _pick_named(loads, ['CPU Total', 'Total'])
    bus_clock = _pick_named(clocks, ['Bus Speed', 'Bus Clock'])
    core_voltage = _pick_named(voltages, ['CPU Core', 'Core', 'VCore'])
    clock_values = [s['value'] for s in core_clocks if s['value'] > 0]

    sensor_rows = []
    allowed = {'temperature', 'clock', 'load', 'power', 'voltage', 'current'}
    for sensor in cpu:
        sensor_type = str(sensor.get('sensor_type') or '')
        if sensor_type.lower() not in allowed:
            continue
        sensor_rows.append({
            'name': sensor.get('sensor_name') or 'Sensor',
            'type': sensor_type,
            'value': round(float(sensor['value']), 3),
            'unit': _sensor_unit(sensor_type),
            'identifier': sensor.get('identifier') or None,
            'hardware': sensor.get('hardware_name') or None,
            'source': 'LibreHardwareMonitorLib',
            'quality': 'VALID',
            'timestamp': sensor.get('timestamp') or time.time(),
        })
    sensor_rows.sort(key=lambda item: (str(item.get('type') or '').casefold(), str(item.get('name') or '').casefold()))

    return {
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
        'quality': 'VALID' if cpu else 'UNAVAILABLE',
        'sensor_count': len(sensor_rows),
        'sensors': sensor_rows,
        'timestamp': time.time(),
    }

def _gpu_details(sensors):
    grouped = defaultdict(list)
    for s in sensors:
        if s['hardware_type'].lower().startswith('gpu'):
            grouped[s['hardware_type'], s['hardware_name']].append(s)
    result = []
    allowed = {'temperature', 'clock', 'load', 'power', 'voltage', 'current', 'fan', 'control', 'smalldata', 'throughput'}
    for (hw_type, hw_name), items in grouped.items():
        temps = [s for s in items if s['sensor_type'].lower() == 'temperature']
        clocks = [s for s in items if s['sensor_type'].lower() == 'clock']
        loads = [s for s in items if s['sensor_type'].lower() == 'load']
        power = [s for s in items if s['sensor_type'].lower() == 'power']
        small = [s for s in items if s['sensor_type'].lower() == 'smalldata']
        fans = [s for s in items if s['sensor_type'].lower() == 'fan']
        controls = [s for s in items if s['sensor_type'].lower() == 'control']
        voltages = [s for s in items if s['sensor_type'].lower() == 'voltage']
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
            if sensor_type.lower() not in allowed:
                continue
            sensor_rows.append({'name': sensor.get('sensor_name') or 'Sensor', 'type': sensor_type, 'value': round(float(sensor['value']), 3), 'unit': _sensor_unit(sensor_type), 'identifier': sensor.get('identifier') or None, 'hardware': sensor.get('hardware_name') or None, 'source': 'LibreHardwareMonitorLib', 'quality': 'VALID', 'timestamp': sensor.get('timestamp')})
        sensor_rows.sort(key=lambda item: (str(item.get('type') or '').casefold(), str(item.get('name') or '').casefold()))
        timestamps = [row.get('timestamp') for row in sensor_rows if row.get('timestamp') is not None]
        result.append({'name': hw_name, 'hardware_type': hw_type, 'temperature_c': round(core_temp['value'], 1) if core_temp else None, 'hotspot_c': round(hotspot['value'], 1) if hotspot else None, 'usage_percent': round(core_load['value'], 1) if core_load else None, 'memory_usage_percent': round(mem_load['value'], 1) if mem_load else None, 'core_clock_mhz': round(core_clock['value'], 1) if core_clock else None, 'memory_clock_mhz': round(mem_clock['value'], 1) if mem_clock else None, 'power_w': round(package_power['value'], 2) if package_power else None, 'memory_total_mb': round(mem_total['value'], 1) if mem_total else None, 'memory_used_mb': round(mem_used['value'], 1) if mem_used else None, 'fan_rpm': round(fan['value'], 1) if fan else None, 'fan_control_percent': round(fan_control['value'], 1) if fan_control else None, 'core_voltage_v': round(core_voltage['value'], 4) if core_voltage else None, 'source': 'LibreHardwareMonitorLib', 'quality': 'VALID', 'sensor_count': len(sensor_rows), 'sensors': sensor_rows, 'timestamp': min(timestamps) if timestamps else None})
    result.sort(key=lambda x: str(x.get('name') or '').casefold())
    return result

def _storage_details(sensors):
    grouped = defaultdict(list)
    for s in sensors:
        if s['hardware_type'].lower() == 'storage':
            grouped[s['hardware_name']].append(s)
    result = []
    for hw_name, items in grouped.items():
        temps = [s for s in items if s['sensor_type'].lower() == 'temperature']
        levels = [s for s in items if s['sensor_type'].lower() == 'level']
        factors = [s for s in items if s['sensor_type'].lower() == 'factor']
        data = [s for s in items if s['sensor_type'].lower() == 'data']
        loads = [s for s in items if s['sensor_type'].lower() == 'load']
        actual_temps = [s for s in temps if 'warning' not in s['sensor_name'].lower() and 'critical' not in s['sensor_name'].lower()]
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
        result.append({'name': hw_name, 'temperature_c': round(primary_temp['value'], 1) if primary_temp else None, 'temperature_sensors_c': [{'name': s['sensor_name'], 'value': round(s['value'], 1)} for s in actual_temps], 'warning_temperature_c': round(warning['value'], 1) if warning else None, 'critical_temperature_c': round(critical['value'], 1) if critical else None, 'life_percent': round(life['value'], 1) if life else None, 'power_on_hours': int(power_hours['value']) if power_hours else None, 'power_on_count': int(power_count['value']) if power_count else None, 'data_read': round(data_read['value'], 3) if data_read else None, 'data_written': round(data_written['value'], 3) if data_written else None, 'used_space_percent': round(used_space['value'], 1) if used_space else None, 'free_space_gb': round(free_space['value'], 2) if free_space else None, 'total_space_gb': round(total_space['value'], 2) if total_space else None, 'source': 'LibreHardwareMonitorLib', 'quality': 'VALID', 'timestamp': time.time()})
    return result

def _battery_details(sensors):
    battery = _matching(sensors, 'Battery')
    if not battery:
        return None
    energy = [s for s in battery if s['sensor_type'].lower() == 'energy']
    levels = [s for s in battery if s['sensor_type'].lower() == 'level']
    voltage = [s for s in battery if s['sensor_type'].lower() == 'voltage']
    current = [s for s in battery if s['sensor_type'].lower() == 'current']
    power = [s for s in battery if s['sensor_type'].lower() == 'power']
    designed = _pick_named(energy, ['Designed Capacity'])
    full = _pick_named(energy, ['Fully-Charged Capacity', 'Full Charged Capacity'])
    remaining = _pick_named(energy, ['Remaining Capacity'])
    degradation = _pick_named(levels, ['Degradation Level'])
    charge = _pick_named(levels, ['Charge Level'])
    volt = _pick_named(voltage, ['Voltage'])
    curr = _pick_named(current, ['Charge/Discharge Current'])
    rate = _pick_named(power, ['Charge/Discharge Rate'])
    return {'designed_capacity_mwh': round(designed['value'], 1) if designed else None, 'full_charge_capacity_mwh': round(full['value'], 1) if full else None, 'remaining_capacity_mwh': round(remaining['value'], 1) if remaining else None, 'degradation_percent': round(degradation['value'], 2) if degradation else None, 'charge_percent': round(charge['value'], 2) if charge else None, 'voltage_v': round(volt['value'], 3) if volt else None, 'current_ma': round(curr['value'], 2) if curr else None, 'charge_discharge_rate_w': round(rate['value'], 2) if rate else None, 'source': 'LibreHardwareMonitorLib', 'quality': 'VALID', 'timestamp': time.time()}

def get_system_telemetry():
    telemetry = _get_lhm_telemetry()
    provider, sensors = _sensors()
    telemetry['_telemetry_version'] = '0.5.3'
    cpu = _cpu_details(sensors)
    gpus = _gpu_details(sensors)
    storage = _storage_details(sensors)
    battery = _battery_details(sensors)
    telemetry['_cpu'] = cpu
    telemetry['_gpus'] = gpus
    telemetry['_storage_devices'] = storage
    telemetry['_battery'] = battery
    if cpu['package_temp_c'] is not None:
        telemetry['cpu_temp'] = cpu['package_temp_c']
        telemetry['_metrics']['cpu_temp'] = _metric(cpu['package_temp_c'], '°C', 'LibreHardwareMonitorLib', 'VALID', sensor=f"{cpu['hardware']} / CPU Package")
    if cpu['clock_avg_ghz'] is not None:
        telemetry['cpu_ghz'] = cpu['clock_avg_ghz']
        telemetry['_metrics']['cpu_ghz'] = _metric(cpu['clock_avg_ghz'], 'GHz', 'LibreHardwareMonitorLib', 'VALID', sensor=f"{cpu['hardware']} / CPU core clocks")
    if gpus:
        primary = select_active_gpu(gpus)
        if telemetry.get('gpu_temp') is None and primary['temperature_c'] is not None:
            telemetry['gpu_temp'] = primary['temperature_c']
            telemetry['_metrics']['gpu_temp'] = _metric(primary['temperature_c'], '°C', 'LibreHardwareMonitorLib', 'VALID', sensor=f"{primary['name']} / GPU Core")
        if telemetry.get('gpu_usage') is None and primary['usage_percent'] is not None:
            telemetry['gpu_usage'] = primary['usage_percent']
            telemetry['_metrics']['gpu_usage'] = _metric(primary['usage_percent'], '%', 'LibreHardwareMonitorLib', 'VALID', sensor=f"{primary['name']} / GPU Core")
    telemetry['_sensor_summary'] = {'provider': 'LibreHardwareMonitorLib', 'provider_available': provider.available, 'provider_error': provider.error, 'sensor_count': len(sensors), 'cpu_detected': bool(cpu['hardware']), 'gpu_count': len(gpus), 'storage_count': len(storage), 'battery_detected': battery is not None, 'timestamp': time.time()}
    return telemetry
