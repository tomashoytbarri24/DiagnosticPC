"""Proporciona una capa base de telemetría real con estados explícitos de disponibilidad."""
from __future__ import annotations
# Código refactorizado: nombres estables y documentación en español.
import os
import platform
import subprocess
import threading
import time
import psutil
try:
    from core.storage_health import get_storage_health
except ImportError:
    get_storage_health = None
IS_WINDOWS = platform.system() == 'Windows'
if IS_WINDOWS:
    try:
        import pythoncom
    except ImportError:
        pythoncom = None
    try:
        import wmi
    except ImportError:
        wmi = None
else:
    pythoncom = None
    wmi = None
CPU_MODEL_NAME = 'Procesador'
GPU_MODEL_NAME = 'Gráfica'
GPU_VRAM_GB = None
_HARDWARE_LOCK = threading.Lock()
_HARDWARE_INITIALIZED = False

def _init_com():
    if IS_WINDOWS and pythoncom is not None:
        try:
            pythoncom.CoInitialize()
        except Exception:
            pass

def _run_command(command, timeout=2):
    try:
        result = subprocess.check_output(command, shell=True, stderr=subprocess.DEVNULL, timeout=timeout)
        return result.decode('utf-8', errors='ignore').strip()
    except Exception:
        return ''

def _metric(value, unit, source, quality='VALID', error=None):
    return {'value': value, 'unit': unit, 'source': source, 'quality': quality, 'timestamp': time.time(), 'error': error}

def _valid_number(value, low=None, high=None):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if low is not None and number < low:
        return None
    if high is not None and number > high:
        return None
    return number

def _clamp(value, low=0.0, high=100.0):
    if value is None:
        return None
    return max(low, min(high, float(value)))

def get_system_chassis_and_bios():
    is_laptop = False
    chassis_label = 'Torre / Desktop'
    bios_info = 'No disponible'
    board_info = 'No disponible'
    if IS_WINDOWS and wmi is not None:
        _init_com()
        try:
            c = wmi.WMI()
            try:
                bios_list = c.Win32_BIOS()
                if bios_list:
                    bios = bios_list[0]
                    vendor = (getattr(bios, 'Manufacturer', '') or '').strip()
                    version = (getattr(bios, 'SMBIOSBIOSVersion', '') or '').strip()
                    combined = f'{vendor} {version}'.strip()
                    if combined:
                        bios_info = combined
            except Exception:
                pass
            try:
                boards = c.Win32_BaseBoard()
                if boards:
                    board = boards[0]
                    vendor = (getattr(board, 'Manufacturer', '') or '').strip()
                    model = (getattr(board, 'Product', '') or '').strip()
                    combined = f'{vendor} {model}'.strip()
                    if combined:
                        board_info = combined
            except Exception:
                pass
            try:
                systems = c.Win32_ComputerSystem()
                if systems and getattr(systems[0], 'PCSystemType', 0) in (2, 8):
                    is_laptop = True
            except Exception:
                pass
            try:
                enclosures = c.Win32_SystemEnclosure()
                if enclosures:
                    values = getattr(enclosures[0], 'ChassisTypes', []) or []
                    laptop_types = {8, 9, 10, 11, 12, 14, 18, 21, 30, 31, 32}
                    if any((int(v) in laptop_types for v in values)):
                        is_laptop = True
            except Exception:
                pass
            try:
                if psutil.sensors_battery() is not None:
                    is_laptop = True
            except Exception:
                pass
        except Exception:
            pass
    else:
        try:
            if psutil.sensors_battery() is not None:
                is_laptop = True
        except Exception:
            pass
    if is_laptop:
        chassis_label = 'Laptop / Notebook'
    return (is_laptop, chassis_label, bios_info, board_info)

def get_hardware_names():
    global CPU_MODEL_NAME, GPU_MODEL_NAME, GPU_VRAM_GB, _HARDWARE_INITIALIZED
    with _HARDWARE_LOCK:
        if _HARDWARE_INITIALIZED:
            return (CPU_MODEL_NAME, GPU_MODEL_NAME, GPU_VRAM_GB)
        cpu_name = 'Procesador'
        gpu_name = 'Gráfica'
        gpu_vram_gb = None
        if IS_WINDOWS and wmi is not None:
            _init_com()
            try:
                c = wmi.WMI()
                try:
                    cpus = c.Win32_Processor()
                    if cpus and getattr(cpus[0], 'Name', None):
                        cpu_name = cpus[0].Name.strip()
                except Exception:
                    pass
                try:
                    gpus = c.Win32_VideoController()
                    gpu_list = [g for g in gpus if getattr(g, 'Name', None)]
                    if gpu_list:
                        selected = gpu_list[0]
                        gpu_name = selected.Name.strip()
                        adapter_ram = getattr(selected, 'AdapterRAM', None)
                        if adapter_ram:
                            try:
                                gb = abs(int(adapter_ram)) / 1024 ** 3
                                if gb > 0:
                                    gpu_vram_gb = round(gb, 2)
                            except Exception:
                                pass
                except Exception:
                    pass
            except Exception:
                pass
        CPU_MODEL_NAME = cpu_name
        GPU_MODEL_NAME = gpu_name
        GPU_VRAM_GB = gpu_vram_gb
        _HARDWARE_INITIALIZED = True
        return (CPU_MODEL_NAME, GPU_MODEL_NAME, GPU_VRAM_GB)

def _get_nvidia_telemetry():
    result = {'available': False, 'usage': None, 'temperature': None, 'vram_gb': None, 'error': None}
    if not IS_WINDOWS:
        return result
    output = _run_command('nvidia-smi --query-gpu=utilization.gpu,temperature.gpu,memory.total --format=csv,noheader,nounits', timeout=2)
    if not output:
        result['error'] = 'nvidia-smi no disponible o GPU NVIDIA no detectada'
        return result
    try:
        parts = [p.strip() for p in output.splitlines()[0].split(',')]
        if len(parts) < 3:
            result['error'] = 'Respuesta incompleta de nvidia-smi'
            return result
        usage = _valid_number(parts[0], 0, 100)
        temperature = _valid_number(parts[1], 0, 120)
        memory_mb = _valid_number(parts[2], 1, None)
        result['usage'] = usage
        result['temperature'] = temperature
        result['vram_gb'] = round(memory_mb / 1024.0, 2) if memory_mb else None
        result['available'] = any((x is not None for x in (usage, temperature, memory_mb)))
    except Exception as ex:
        result['error'] = str(ex)
    return result

def _get_openhardwaremonitor_data():
    data = {'cpu_temp': None, 'gpu_temp': None, 'gpu_usage': None, 'available': False, 'error': None}
    if not IS_WINDOWS or wmi is None:
        data['error'] = 'WMI no disponible'
        return data
    _init_com()
    try:
        monitor = wmi.WMI(namespace='root\\OpenHardwareMonitor')
        cpu_package = []
        cpu_cores = []
        gpu_temps = []
        gpu_loads = []
        for sensor in monitor.Sensor():
            sensor_type = str(getattr(sensor, 'SensorType', '')).lower()
            name = str(getattr(sensor, 'Name', '')).lower()
            identifier = str(getattr(sensor, 'Identifier', '')).lower()
            value = _valid_number(getattr(sensor, 'Value', None))
            if value is None:
                continue
            combined = f'{name} {identifier}'
            if sensor_type == 'temperature' and 10 <= value <= 115:
                if 'cpu package' in combined or 'package' in combined:
                    cpu_package.append(value)
                elif 'cpu' in combined or 'core' in combined:
                    cpu_cores.append(value)
                if 'gpu' in combined:
                    gpu_temps.append(value)
            if sensor_type == 'load' and 0 <= value <= 100:
                if 'gpu' in combined:
                    gpu_loads.append(value)
        if cpu_package:
            data['cpu_temp'] = round(max(cpu_package), 1)
        elif cpu_cores:
            data['cpu_temp'] = round(max(cpu_cores), 1)
        if gpu_temps:
            data['gpu_temp'] = round(max(gpu_temps), 1)
        if gpu_loads:
            data['gpu_usage'] = round(max(gpu_loads), 1)
        data['available'] = any((data[k] is not None for k in ('cpu_temp', 'gpu_temp', 'gpu_usage')))
    except Exception as ex:
        data['error'] = str(ex)
    return data

def _get_cpu_temperature():
    if IS_WINDOWS:
        ohm = _get_openhardwaremonitor_data()
        if ohm['cpu_temp'] is not None:
            return (ohm['cpu_temp'], 'OpenHardwareMonitor WMI', None)
        return (None, 'No reliable CPU temperature provider', ohm.get('error'))
    try:
        temperatures = psutil.sensors_temperatures() or {}
    except Exception as ex:
        return (None, 'psutil.sensors_temperatures', str(ex))
    for sensor_name in ('coretemp', 'k10temp', 'zenpower', 'cpu_thermal'):
        sensors = temperatures.get(sensor_name) or []
        values = []
        for sensor in sensors:
            current = _valid_number(getattr(sensor, 'current', None), 10, 120)
            if current is not None:
                values.append(current)
        if values:
            return (round(max(values), 1), f'psutil:{sensor_name}', None)
    return (None, 'psutil.sensors_temperatures', 'Sensor CPU no expuesto')

def _get_gpu_telemetry():
    """Obtiene GPU desde un proveedor genérico y usa proveedores opcionales solo como respaldo."""
    ohm = _get_openhardwaremonitor_data()
    if ohm['gpu_usage'] is not None or ohm['gpu_temp'] is not None:
        return {
            'usage': ohm['gpu_usage'], 'temperature': ohm['gpu_temp'], 'vram_gb': None,
            'usage_source': 'OpenHardwareMonitor WMI' if ohm['gpu_usage'] is not None else None,
            'temperature_source': 'OpenHardwareMonitor WMI' if ohm['gpu_temp'] is not None else None,
            'vram_source': None,
        }
    vendor = _get_nvidia_telemetry()
    if vendor['available']:
        return {
            'usage': vendor['usage'], 'temperature': vendor['temperature'], 'vram_gb': vendor['vram_gb'],
            'usage_source': 'nvidia-smi' if vendor['usage'] is not None else None,
            'temperature_source': 'nvidia-smi' if vendor['temperature'] is not None else None,
            'vram_source': 'nvidia-smi' if vendor['vram_gb'] is not None else None,
        }
    return {'usage': None, 'temperature': None, 'vram_gb': None, 'usage_source': None, 'temperature_source': None, 'vram_source': None}

def get_system_telemetry():
    cpu_name, gpu_name, detected_vram = get_hardware_names()
    metrics = {}
    try:
        cpu_usage = _clamp(psutil.cpu_percent(interval=None))
        metrics['cpu_usage'] = _metric(cpu_usage, '%', 'psutil.cpu_percent')
    except Exception as ex:
        cpu_usage = None
        metrics['cpu_usage'] = _metric(None, '%', 'psutil.cpu_percent', 'ERROR', str(ex))
    try:
        freq = psutil.cpu_freq()
        cpu_ghz = round(float(freq.current) / 1000.0, 2) if freq and getattr(freq, 'current', None) else None
        metrics['cpu_ghz'] = _metric(cpu_ghz, 'GHz', 'psutil.cpu_freq', 'VALID' if cpu_ghz is not None else 'UNAVAILABLE')
    except Exception as ex:
        cpu_ghz = None
        metrics['cpu_ghz'] = _metric(None, 'GHz', 'psutil.cpu_freq', 'ERROR', str(ex))
    try:
        ram = psutil.virtual_memory()
        ram_usage = _clamp(float(ram.percent))
        ram_used_gb = round(ram.used / 1024 ** 3, 2)
        ram_total_gb = round(ram.total / 1024 ** 3, 2)
        metrics['ram_usage'] = _metric(ram_usage, '%', 'psutil.virtual_memory')
        metrics['ram_used_gb'] = _metric(ram_used_gb, 'GB', 'psutil.virtual_memory')
        metrics['ram_total_gb'] = _metric(ram_total_gb, 'GB', 'psutil.virtual_memory')
    except Exception as ex:
        ram_usage = None
        ram_used_gb = None
        ram_total_gb = None
        metrics['ram_usage'] = _metric(None, '%', 'psutil.virtual_memory', 'ERROR', str(ex))
        metrics['ram_used_gb'] = _metric(None, 'GB', 'psutil.virtual_memory', 'ERROR', str(ex))
        metrics['ram_total_gb'] = _metric(None, 'GB', 'psutil.virtual_memory', 'ERROR', str(ex))
    cpu_temp, cpu_temp_source, cpu_temp_error = _get_cpu_temperature()
    metrics['cpu_temp'] = _metric(cpu_temp, '°C', cpu_temp_source, 'VALID' if cpu_temp is not None else 'UNAVAILABLE', cpu_temp_error)
    gpu = _get_gpu_telemetry()
    gpu_usage = _clamp(gpu['usage'])
    gpu_temp = _valid_number(gpu['temperature'], 0, 120)
    vram_gb = gpu['vram_gb'] if gpu['vram_gb'] is not None else detected_vram
    metrics['gpu_usage'] = _metric(gpu_usage, '%', gpu['usage_source'] or 'No reliable GPU usage provider', 'VALID' if gpu_usage is not None else 'UNAVAILABLE')
    metrics['gpu_temp'] = _metric(gpu_temp, '°C', gpu['temperature_source'] or 'No reliable GPU temperature provider', 'VALID' if gpu_temp is not None else 'UNAVAILABLE')
    metrics['gpu_vram_gb'] = _metric(vram_gb, 'GB', gpu.get('vram_source') or ('Win32_VideoController' if detected_vram is not None else 'No reliable GPU VRAM provider'), 'VALID' if vram_gb is not None else 'UNAVAILABLE')
    is_laptop, chassis_label, bios_info, board_info = get_system_chassis_and_bios()
    display_cpu = f'{cpu_name} ({cpu_ghz} GHz)' if cpu_ghz is not None else cpu_name
    display_gpu = f'{gpu_name} ({vram_gb} GB)' if vram_gb is not None else gpu_name
    return {'timestamp': time.time(), 'cpu_usage': cpu_usage, 'cpu_ghz': cpu_ghz, 'cpu_temp': cpu_temp, 'cpu_name': display_cpu, 'ram_usage': ram_usage, 'ram_used_gb': ram_used_gb, 'ram_total_gb': ram_total_gb, 'gpu_usage': gpu_usage, 'gpu_temp': gpu_temp, 'gpu_name': display_gpu, 'gpu_vram_gb': vram_gb, 'is_laptop': is_laptop, 'chassis_label': chassis_label, 'bios_info': bios_info, 'board_info': board_info, '_metrics': metrics, '_telemetry_version': '0.5-reliable'}

def get_all_disks_data():
    disks = []
    physical_health = []
    if get_storage_health is not None:
        try:
            physical_health = get_storage_health() or []
        except Exception:
            physical_health = []
    disk_models = {}
    if IS_WINDOWS and wmi is not None:
        _init_com()
        try:
            c = wmi.WMI()
            for disk in c.Win32_DiskDrive():
                model = (getattr(disk, 'Model', None) or 'Disco físico').strip()
                try:
                    for partition in disk.associators('Win32_DiskDriveToDiskPartition'):
                        for logical in partition.associators('Win32_LogicalDiskToPartition'):
                            device_id = getattr(logical, 'DeviceID', None)
                            if device_id:
                                disk_models[device_id] = model
                except Exception:
                    pass
        except Exception:
            pass
    index = 0
    for partition in psutil.disk_partitions(all=False):
        try:
            if 'cdrom' in (partition.opts or '').lower():
                continue
            if not partition.fstype:
                continue
            usage = psutil.disk_usage(partition.mountpoint)
            mount = partition.mountpoint
            if IS_WINDOWS:
                cleaned = mount.replace('\\', '').replace('/', '').rstrip(':')
                device_id = cleaned + ':' if len(cleaned) == 1 else cleaned
                model = disk_models.get(device_id, f'Unidad {device_id}')
                display_mount = f'[{device_id}]'
            else:
                model = partition.device
                display_mount = mount
            health = None
            health_source = 'UNAVAILABLE'
            for physical in physical_health:
                physical_model = str(physical.get('model') or physical.get('friendly_name') or physical.get('FriendlyName') or '').strip()
                if physical_model and (physical_model.lower() in model.lower() or model.lower() in physical_model.lower()):
                    candidate = physical.get('health')
                    if isinstance(candidate, (int, float)):
                        health = float(candidate)
                        health_source = 'core.storage_health'
                    break
            disks.append({'index': index, 'model': model, 'mount_points': display_mount, 'total_gb': round(usage.total / 1024 ** 3, 2), 'used_percent': round(float(usage.percent), 1), 'used_gb': round(usage.used / 1024 ** 3, 2), 'used_mb': int(usage.used / 1024 ** 2), 'used_kb': int(usage.used / 1024), 'health': health, 'health_quality': 'VALID' if health is not None else 'UNAVAILABLE', 'health_source': health_source, 'used_source': 'psutil.disk_usage'})
            index += 1
        except Exception:
            continue
    return disks

def calculate_preliminary_score(cpu_usage, ram_usage, cpu_temp, gpu_temp, disks):
    """Calcula la operación `calculate_preliminary_score` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
    evidence = 0
    penalties = 0.0
    if isinstance(cpu_usage, (int, float)):
        evidence += 1
        if cpu_usage >= 95:
            penalties += 5
    if isinstance(ram_usage, (int, float)):
        evidence += 1
        if ram_usage >= 95:
            penalties += 8
    if isinstance(cpu_temp, (int, float)):
        evidence += 1
        if cpu_temp >= 95:
            penalties += 30
        elif cpu_temp >= 85:
            penalties += 12
    if isinstance(gpu_temp, (int, float)):
        evidence += 1
        if gpu_temp >= 95:
            penalties += 30
        elif gpu_temp >= 85:
            penalties += 12
    for disk in disks or []:
        used = disk.get('used_percent')
        if isinstance(used, (int, float)):
            evidence += 1
            if used >= 95:
                penalties += 10
            elif used >= 90:
                penalties += 5
        health = disk.get('health')
        if isinstance(health, (int, float)):
            evidence += 1
            if health < 50:
                penalties += 30
            elif health < 70:
                penalties += 15
    if evidence < 2:
        return None
    return max(0.0, min(100.0, round(100.0 - penalties, 1)))
