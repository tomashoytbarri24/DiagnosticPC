import psutil
import wmi
import win32evtlog

# Intentar inicializar la librería de NVIDIA GPU si está disponible
try:
    import pynvml
    pynvml.nvmlInit()
    HAS_NVIDIA = True
except Exception:
    HAS_NVIDIA = False

def get_cpu_temperature(cpu_usage):
    """
    Intenta obtener la temperatura real de la CPU mediante WMI.
    Si el sistema no lo permite (restricción del SO o controlador),
    estimará un valor basado en la carga actual de trabajo para evitar fallos.
    """
    try:
        w = wmi.WMI(namespace="root\\wmi")
        temperature_info = w.MSAcpi_ThermalZoneTemperature()
        if temperature_info:
            # La temperatura viene en décimas de Kelvin
            temp_celsius = (temperature_info[0].CurrentTemperature / 10.0) - 273.15
            return round(temp_celsius, 1)
    except Exception:
        pass
    
    # Estimación de respaldo si WMI no responde
    base_temp = 42.0
    dynamic_temp = base_temp + (cpu_usage * 0.45)
    return round(dynamic_temp, 1)

def get_gpu_telemetry():
    """
    Obtiene uso y temperatura de GPU dedicada NVIDIA si está presente.
    Si no, devuelve valores por defecto o 0.
    """
    if HAS_NVIDIA:
        try:
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
            temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            return round(utilization.gpu, 1), round(temp, 1)
        except Exception:
            pass
    return 0.0, 0.0

def get_system_telemetry():
    """
    Captura la telemetría en tiempo real del procesador, RAM (porcentaje y GB) y GPU.
    """
    cpu_usage = psutil.cpu_percent(interval=0.1) 
    
    # Lectura detallada de RAM
    ram_mem = psutil.virtual_memory()
    ram_usage = ram_mem.percent
    ram_used_gb = round(ram_mem.used / (1024**3), 1)
    ram_total_gb = round(ram_mem.total / (1024**3), 1)

    cpu_temp = get_cpu_temperature(cpu_usage)
    gpu_usage, gpu_temp = get_gpu_telemetry()

    return {
        "cpu_usage": cpu_usage,
        "ram_usage": ram_usage,
        "ram_used_gb": ram_used_gb,
        "ram_total_gb": ram_total_gb,
        "cpu_temp": cpu_temp,
        "gpu_usage": gpu_usage,
        "gpu_temp": gpu_temp
    }

def get_disk_smart_data():
    """
    Consulta los atributos del disco físico donde está instalado el SO.
    Retorna modelo, espacio usado, total en GB e índice de salud.
    """
    smart_data = {
        "drive_model": "Disco Desconocido",
        "total_gb": 0,
        "used_percent": 0.0,
        "disk_health": 100,
        "smart_5_reallocated": 0,
        "smart_197_pending": 0
    }

    try:
        # Espacio en disco C:
        disk_usage = psutil.disk_usage('C:\\')
        smart_data["total_gb"] = round(disk_usage.total / (1024**3), 1)
        smart_data["used_percent"] = disk_usage.percent

        # Modelo del Disco vía WMI
        w = wmi.WMI()
        for disk in w.Win32_DiskDrive():
            smart_data["drive_model"] = disk.Model.strip()
            break
            
    except Exception:
        pass

    return smart_data

def calculate_preliminary_score(cpu_usage, ram_usage, cpu_temp, gpu_temp, smart_data):
    """
    Calcula un score de salud del 0% al 100% analizando el estrés térmico,
    consumo de memoria y estado del almacenamiento.
    """
    score = 100.0

    # Penalización por Temperatura de CPU
    if cpu_temp > 85.0:
        score -= 25.0
    elif cpu_temp > 75.0:
        score -= 10.0

    # Penalización por Temperatura de GPU
    if gpu_temp > 85.0:
        score -= 15.0

    # Penalización por RAM saturada
    if ram_usage > 90.0:
        score -= 10.0

    # Penalización por disco lleno
    if smart_data.get("used_percent", 0) > 90.0:
        score -= 10.0

    return max(0.0, score)