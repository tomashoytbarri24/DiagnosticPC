# core/telemetry.py

import os
import json
import platform
import subprocess
import threading
import time

import psutil

# Integración del módulo de salud física de almacenamiento
try:
    from core.storage_health import get_storage_health
except ImportError:
    get_storage_health = None

IS_WINDOWS = platform.system() == "Windows"

# ============================================================================
# WINDOWS - IMPORTS OPCIONALES
# ============================================================================

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


# ============================================================================
# ESTADO GLOBAL
# ============================================================================

LAST_VALID_GPU_TEMP = 38.0
LAST_VALID_CPU_TEMP = 45.0

CPU_MODEL_NAME = "Procesador"
GPU_MODEL_NAME = "Gráfica"
GPU_VRAM_GB = 0.0

_HARDWARE_LOCK = threading.Lock()
_HARDWARE_INITIALIZED = False


# ============================================================================
# COM
# ============================================================================

def _init_com():
    """
    Inicializa COM para el hilo actual.
    """
    if not IS_WINDOWS or pythoncom is None:
        return

    try:
        pythoncom.CoInitialize()
    except Exception:
        pass


# ============================================================================
# UTILIDADES
# ============================================================================

def _safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def _safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def _run_command(command, timeout=2):
    """
    Ejecuta un comando de forma segura.
    """
    try:
        result = subprocess.check_output(
            command,
            shell=True,
            stderr=subprocess.DEVNULL,
            timeout=timeout
        )
        return result.decode("utf-8", errors="ignore").strip()
    except Exception:
        return ""


# ============================================================================
# INFORMACIÓN DEL CHASIS / BIOS / PLACA
# ============================================================================

def get_system_chassis_and_bios():
    is_laptop = False
    chassis_label = "Torre / Desktop"
    bios_info = "Desconocida"
    board_info = "Desconocida"

    # ------------------------------------------------------------------------
    # WINDOWS
    # ------------------------------------------------------------------------
    if IS_WINDOWS and wmi is not None:
        _init_com()
        try:
            c = wmi.WMI()

            # BIOS
            try:
                bios_list = c.Win32_BIOS()
                if bios_list:
                    bios = bios_list[0]
                    vendor = bios.Manufacturer.strip() if bios.Manufacturer else ""
                    version = bios.SMBIOSBIOSVersion.strip() if bios.SMBIOSBIOSVersion else ""
                    bios_info = f"{vendor} {version}".strip()
            except Exception:
                pass

            # PLACA
            try:
                board_list = c.Win32_BaseBoard()
                if board_list:
                    board = board_list[0]
                    vendor = board.Manufacturer.strip() if board.Manufacturer else ""
                    model = board.Product.strip() if board.Product else ""
                    board_info = f"{vendor} {model}".strip()
            except Exception:
                pass

            # TIPO DE PC
            try:
                cs_list = c.Win32_ComputerSystem()
                if cs_list:
                    pc_type = getattr(cs_list[0], "PCSystemType", 0)
                    if pc_type in (2, 8):
                        is_laptop = True
            except Exception:
                pass

            # Batería
            try:
                if psutil.sensors_battery() is not None:
                    is_laptop = True
            except Exception:
                pass

            # Chasis
            try:
                enclosure = c.Win32_SystemEnclosure()
                if enclosure:
                    chassis_types = getattr(enclosure[0], "ChassisTypes", []) or []
                    laptop_types = {8, 9, 10, 14, 30, 31, 32}
                    if any(t in laptop_types for t in chassis_types):
                        is_laptop = True
            except Exception:
                pass

        except Exception:
            pass

    # ------------------------------------------------------------------------
    # LINUX / UNIX
    # ------------------------------------------------------------------------
    else:
        try:
            if psutil.sensors_battery() is not None:
                is_laptop = True
        except Exception:
            pass

        try:
            bios_path = "/sys/class/dmi/id/bios_version"
            if os.path.exists(bios_path):
                with open(bios_path, "r", encoding="utf-8", errors="ignore") as f:
                    bios_info = f.read().strip()
        except Exception:
            pass

        try:
            board_path = "/sys/class/dmi/id/board_name"
            if os.path.exists(board_path):
                with open(board_path, "r", encoding="utf-8", errors="ignore") as f:
                    board_info = f.read().strip()
        except Exception:
            pass

        try:
            chassis_path = "/sys/class/dmi/id/chassis_type"
            if os.path.exists(chassis_path):
                with open(chassis_path, "r", encoding="utf-8", errors="ignore") as f:
                    chassis_type = f.read().strip()
                if chassis_type in {"8", "9", "10", "14", "30", "31", "32"}:
                    is_laptop = True
        except Exception:
            pass

    if is_laptop:
        chassis_label = "Laptop / Notebook"

    return is_laptop, chassis_label, bios_info, board_info


# ============================================================================
# NOMBRES DE HARDWARE
# ============================================================================

def get_hardware_names():
    global CPU_MODEL_NAME
    global GPU_MODEL_NAME
    global GPU_VRAM_GB
    global _HARDWARE_INITIALIZED

    with _HARDWARE_LOCK:
        if _HARDWARE_INITIALIZED:
            return CPU_MODEL_NAME, GPU_MODEL_NAME, GPU_VRAM_GB

        cpu_name = "Procesador"
        gpu_name = "Gráfica"
        gpu_vram_gb = 0.0

        if IS_WINDOWS and wmi is not None:
            _init_com()
            try:
                w = wmi.WMI()

                # CPU
                try:
                    cpus = w.Win32_Processor()
                    if cpus and cpus[0].Name:
                        cpu_name = cpus[0].Name.strip()
                except Exception:
                    pass

                # GPU
                try:
                    gpus = w.Win32_VideoController()
                    gpu_list = [g for g in gpus if getattr(g, "Name", None)]

                    nvidia = [g for g in gpu_list if "nvidia" in g.Name.lower()]
                    amd = [g for g in gpu_list if ("radeon" in g.Name.lower() or "amd" in g.Name.lower())]
                    intel = [g for g in gpu_list if "intel" in g.Name.lower()]

                    if nvidia:
                        selected_gpu = nvidia[0]
                    elif amd:
                        selected_gpu = amd[0]
                    elif intel:
                        selected_gpu = intel[0]
                    elif gpu_list:
                        selected_gpu = gpu_list[0]
                    else:
                        selected_gpu = None

                    if selected_gpu:
                        gpu_name = selected_gpu.Name.strip()
                        adapter_ram = getattr(selected_gpu, "AdapterRAM", None)
                        if adapter_ram:
                            try:
                                gpu_vram_gb = round(abs(int(adapter_ram)) / (1024 ** 3), 2)
                            except Exception:
                                pass
                except Exception:
                    pass

                # NVIDIA VRAM exacta
                try:
                    result = _run_command("nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits", timeout=2)
                    if result:
                        first_value = result.splitlines()[0].strip()
                        value_mb = float(first_value)
                        if value_mb > 0:
                            gpu_vram_gb = round(value_mb / 1024.0, 2)
                except Exception:
                    pass

            except Exception:
                pass

        else:
            try:
                with open("/proc/cpuinfo", "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if "model name" in line:
                            cpu_name = line.split(":", 1)[1].strip()
                            break
            except Exception:
                pass

            try:
                result = _run_command("lspci | grep -E 'VGA|3D|Display'", timeout=2)
                if result:
                    lines = result.splitlines()
                    gpu_line = lines[0]
                    gpu_name = gpu_line.split(":", 2)[-1].strip()
            except Exception:
                pass

        CPU_MODEL_NAME = cpu_name
        GPU_MODEL_NAME = gpu_name
        GPU_VRAM_GB = gpu_vram_gb

        _HARDWARE_INITIALIZED = True

        return CPU_MODEL_NAME, GPU_MODEL_NAME, GPU_VRAM_GB


# ============================================================================
# TEMPERATURA GPU - NVIDIA
# ============================================================================

def _get_nvidia_telemetry():
    result = {
        "available": False,
        "usage": 0.0,
        "temperature": None,
        "vram_gb": 0.0
    }

    if not IS_WINDOWS:
        return result

    try:
        output = _run_command(
            "nvidia-smi --query-gpu=utilization.gpu,temperature.gpu,memory.total --format=csv,noheader,nounits",
            timeout=2
        )
        if not output:
            return result

        line = output.splitlines()[0]
        parts = [p.strip() for p in line.split(",")]

        if len(parts) < 3:
            return result

        usage = float(parts[0])
        temperature = float(parts[1])
        memory_mb = float(parts[2])

        result["available"] = True
        result["usage"] = max(0.0, min(100.0, usage))

        if 0 <= temperature <= 120:
            result["temperature"] = temperature

        if memory_mb > 0:
            result["vram_gb"] = round(memory_mb / 1024.0, 2)

    except Exception:
        pass

    return result


# ============================================================================
# OPEN HARDWARE MONITOR
# ============================================================================

def _get_openhardwaremonitor_data():
    data = {
        "cpu_temp": None,
        "gpu_temp": None,
        "gpu_usage": None
    }

    if not IS_WINDOWS or wmi is None:
        return data

    _init_com()

    try:
        w = wmi.WMI(namespace="root\\OpenHardwareMonitor")

        for sensor in w.Sensor():
            sensor_type = str(getattr(sensor, "SensorType", "")).lower()
            name = str(getattr(sensor, "Name", "")).lower()
            identifier = str(getattr(sensor, "Identifier", "")).lower()
            value = getattr(sensor, "Value", None)

            if value is None:
                continue

            try:
                value = float(value)
            except Exception:
                continue

            if value <= 0:
                continue

            combined = name + " " + identifier

            if sensor_type == "temperature" and ("cpu" in combined or "core" in combined or "package" in combined):
                if data["cpu_temp"] is None or value < data["cpu_temp"]:
                    data["cpu_temp"] = round(value, 1)

            if sensor_type == "temperature" and ("gpu" in combined or "nvidia" in combined or "radeon" in combined or "amd" in combined):
                if data["gpu_temp"] is None or value > data["gpu_temp"]:
                    data["gpu_temp"] = round(value, 1)

            if sensor_type == "load" and ("gpu" in combined or "nvidia" in combined or "radeon" in combined or "amd" in combined):
                if data["gpu_usage"] is None or value > data["gpu_usage"]:
                    data["gpu_usage"] = round(value, 1)

    except Exception:
        pass

    return data


# ============================================================================
# TEMPERATURA CPU WINDOWS
# ============================================================================

def _get_windows_cpu_temperature():
    ohm = _get_openhardwaremonitor_data()
    if ohm["cpu_temp"] is not None:
        temperature = ohm["cpu_temp"]
        if 10 <= temperature <= 110:
            return temperature

    if IS_WINDOWS and wmi is not None:
        _init_com()
        try:
            w = wmi.WMI()
            zones = w.Win32_PerfFormattedData_Counters_ThermalZoneInformation()
            values = []

            for zone in zones:
                value = getattr(zone, "HighPrecisionTemperature", None)
                if value is None:
                    continue
                try:
                    value = float(value)
                except Exception:
                    continue

                temperature = (value - 2732) / 10.0
                if 10 <= temperature <= 110:
                    values.append(temperature)

            if values:
                return round(sum(values) / len(values), 1)

        except Exception:
            pass

    return None


# ============================================================================
# TELEMETRÍA PRINCIPAL
# ============================================================================

def get_system_telemetry():
    global LAST_VALID_GPU_TEMP
    global LAST_VALID_CPU_TEMP

    cpu_name, gpu_name, vram_gb = get_hardware_names()

    # CPU
    try:
        cpu_usage = psutil.cpu_percent(interval=None)
    except Exception:
        cpu_usage = 0.0

    try:
        freq = psutil.cpu_freq()
        cpu_ghz = round(freq.current / 1000.0, 2) if freq and freq.current else 0.0
    except Exception:
        cpu_ghz = 0.0

    # RAM
    try:
        ram = psutil.virtual_memory()
        ram_usage = float(ram.percent)
        ram_used_gb = round(ram.used / (1024 ** 3), 2)
        ram_total_gb = round(ram.total / (1024 ** 3), 2)
    except Exception:
        ram_usage = 0.0
        ram_used_gb = 0.0
        ram_total_gb = 0.0

    cpu_temp = LAST_VALID_CPU_TEMP
    gpu_temp = LAST_VALID_GPU_TEMP
    gpu_usage = 0.0

    if IS_WINDOWS:
        nvidia = _get_nvidia_telemetry()
        if nvidia["available"]:
            gpu_usage = nvidia["usage"]
            if nvidia["temperature"] is not None:
                gpu_temp = round(nvidia["temperature"], 1)
                LAST_VALID_GPU_TEMP = gpu_temp
            if nvidia["vram_gb"] > 0:
                vram_gb = nvidia["vram_gb"]

        ohm = _get_openhardwaremonitor_data()
        if gpu_usage == 0.0 and ohm["gpu_usage"] is not None:
            gpu_usage = ohm["gpu_usage"]

        if not nvidia["available"] and ohm["gpu_temp"] is not None:
            gpu_temp = ohm["gpu_temp"]
            LAST_VALID_GPU_TEMP = gpu_temp

        measured_cpu_temp = _get_windows_cpu_temperature()
        if measured_cpu_temp is not None:
            cpu_temp = measured_cpu_temp
            LAST_VALID_CPU_TEMP = cpu_temp
        else:
            cpu_temp = round(40.0 + (cpu_usage * 0.35), 1)
            LAST_VALID_CPU_TEMP = cpu_temp

    else:
        try:
            temperatures = psutil.sensors_temperatures()
            if temperatures:
                for sensor_name in ("coretemp", "k10temp", "zenpower", "cpu_thermal", "acpitz"):
                    sensors = temperatures.get(sensor_name)
                    if not sensors:
                        continue
                    valid = [s.current for s in sensors if getattr(s, "current", None) is not None and 10 <= s.current <= 120]
                    if valid:
                        cpu_temp = round(max(valid), 1)
                        LAST_VALID_CPU_TEMP = cpu_temp
                        break

                for sensor_name in ("amdgpu", "nvidia", "nouveau"):
                    sensors = temperatures.get(sensor_name)
                    if not sensors:
                        continue
                    for sensor in sensors:
                        value = getattr(sensor, "current", None)
                        if value is not None and 0 <= value <= 120:
                            gpu_temp = round(value, 1)
                            LAST_VALID_GPU_TEMP = gpu_temp
                            break
                    if gpu_temp != LAST_VALID_GPU_TEMP:
                        continue
        except Exception:
            pass

    is_laptop, chassis_label, bios_info, board_info = get_system_chassis_and_bios()

    hardware_string = (cpu_name + " " + gpu_name).lower()
    if "laptop" in hardware_string or "mobile" in hardware_string:
        is_laptop = True
        chassis_label = "Laptop / Notebook"

    display_cpu = f"{cpu_name} ({cpu_ghz} GHz)" if cpu_ghz > 0 else cpu_name
    display_gpu = f"{gpu_name} ({vram_gb} GB)" if vram_gb > 0 else gpu_name

    return {
        "timestamp": time.time(),
        "cpu_usage": round(max(0, min(100, cpu_usage)), 1),
        "cpu_ghz": cpu_ghz,
        "cpu_temp": round(cpu_temp, 1),
        "cpu_name": display_cpu,
        "ram_usage": round(max(0, min(100, ram_usage)), 1),
        "ram_used_gb": ram_used_gb,
        "ram_total_gb": ram_total_gb,
        "gpu_usage": round(max(0, min(100, gpu_usage)), 1),
        "gpu_temp": round(max(0, min(120, gpu_temp)), 1),
        "gpu_name": display_gpu,
        "gpu_vram_gb": vram_gb,
        "is_laptop": is_laptop,
        "chassis_label": chassis_label,
        "bios_info": bios_info,
        "board_info": board_info
    }


# ============================================================================
# DISCOS Y ALMACENAMIENTO (FUSIÓN LÓGICA + SALUD FÍSICA)
# ============================================================================

def get_all_disks_data():
    """
    Obtiene los discos combinando datos lógicos de psutil 
    con la salud física (S.M.A.R.T./Health) mediante get_storage_health().
    """
    disks = []
    
    # 1. Intentar obtener datos de salud física si el módulo está disponible
    physical_health_data = []
    if get_storage_health is not None:
        try:
            physical_health_data = get_storage_health() or []
        except Exception:
            physical_health_data = []

    # ------------------------------------------------------------------------
    # WINDOWS
    # ------------------------------------------------------------------------
    if IS_WINDOWS:
        _init_com()
        try:
            partitions = psutil.disk_partitions(all=False)
            disk_models = {}

            if wmi is not None:
                try:
                    c = wmi.WMI()
                    for disk in c.Win32_DiskDrive():
                        model = disk.Model.strip() if disk.Model else "Disco físico"
                        for partition in disk.associators("Win32_DiskDriveToDiskPartition"):
                            for logical in partition.associators("Win32_LogicalDiskToPartition"):
                                device_id = getattr(logical, "DeviceID", None)
                                if device_id:
                                    disk_models[device_id] = model
                except Exception:
                    pass

            index = 0
            for partition in partitions:
                try:
                    if "cdrom" in partition.opts:
                        continue
                    if not partition.fstype:
                        continue

                    mountpoint = partition.mountpoint
                    usage = psutil.disk_usage(mountpoint)
                    mount_letter = mountpoint.replace("\\", "").replace("/", "").rstrip(":")
                    device_id = mount_letter + ":" if len(mount_letter) == 1 else mount_letter

                    model = disk_models.get(device_id, f"Unidad {device_id}")

                    total_bytes = usage.total
                    used_bytes = usage.used
                    total_gb = round(total_bytes / (1024 ** 3), 2)
                    used_gb = round(used_bytes / (1024 ** 3), 2)

                    # Intentar cruzarlo con salud física S.M.A.R.T.
                    health_val = 100
                    for phy in physical_health_data:
                        if phy.get("health") is not None:
                            health_val = phy.get("health")
                            break

                    disks.append({
                        "index": index,
                        "model": model,
                        "mount_points": f"[{device_id}]",
                        "total_gb": total_gb,
                        "used_percent": round(usage.percent, 1),
                        "used_gb": used_gb,
                        "used_mb": int(used_bytes / (1024 ** 2)),
                        "used_kb": int(used_bytes / 1024),
                        "health": health_val
                    })
                    index += 1
                except Exception:
                    continue
        except Exception:
            pass

    # ------------------------------------------------------------------------
    # LINUX / UNIX
    # ------------------------------------------------------------------------
    else:
        try:
            # Si el módulo físico en Linux obtuvo discos directamente, los mapeamos
            if physical_health_data:
                for disk in physical_health_data:
                    disks.append({
                        "index": disk.get("index", 0),
                        "model": disk.get("model", "Unidad de almacenamiento"),
                        "mount_points": disk.get("device_id", "/dev/sdX"),
                        "total_gb": disk.get("total_gb", 0.0),
                        "used_percent": disk.get("used_percent", 0.0),
                        "used_gb": disk.get("used_gb", 0.0),
                        "used_mb": int(disk.get("used_gb", 0.0) * 1024),
                        "used_kb": int(disk.get("used_gb", 0.0) * 1024 * 1024),
                        "health": disk.get("health", 100)
                    })
            else:
                # Fallback estándar con psutil para Linux
                index = 0
                for part in psutil.disk_partitions(all=False):
                    if part.fstype in ("", "squashfs"):
                        continue
                    try:
                        usage = psutil.disk_usage(part.mountpoint)
                        total_gb = round(usage.total / (1024 ** 3), 2)
                        used_gb = round(usage.used / (1024 ** 3), 2)
                        disks.append({
                            "index": index,
                            "model": part.device,
                            "mount_points": part.mountpoint,
                            "total_gb": total_gb,
                            "used_percent": round(usage.percent, 1),
                            "used_gb": used_gb,
                            "used_mb": int(usage.used / (1024 ** 2)),
                            "used_kb": int(usage.used / 1024),
                            "health": 100
                        })
                        index += 1
                    except Exception:
                        continue
        except Exception:
            pass

    return disks


# ============================================================================
# CÁLCULO DE SALUD PRELIMINAR DEL SISTEMA
# ============================================================================

def calculate_preliminary_score(cpu_usage, ram_usage, cpu_temp, gpu_temp, disks):
    """
    Calcula un puntaje general de salud estimado para el sistema (0.0 a 100.0).
    """
    score = 100.0

    # Penalización por alto uso de CPU y RAM
    score -= (float(cpu_usage) * 0.25)
    score -= (float(ram_usage) * 0.25)

    # Penalización por temperaturas elevadas
    if isinstance(cpu_temp, (int, float)) and cpu_temp > 75:
        score -= (cpu_temp - 75) * 0.8

    if isinstance(gpu_temp, (int, float)) and gpu_temp > 80:
        score -= (gpu_temp - 80) * 0.8

    # Penalización por poco espacio libre en discos
    if disks:
        for disk in disks:
            used_p = float(disk.get("used_percent", 0))
            if used_p > 90:
                score -= 10.0
            elif used_p > 80:
                score -= 5.0

    return max(0.0, min(100.0, round(score, 1)))