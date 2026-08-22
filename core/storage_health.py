import json
import logging
import platform
import subprocess

logger = logging.getLogger("DiagnosticPC")

IS_WINDOWS = platform.system() == "Windows"


# ============================================================
# UTILIDADES
# ============================================================

def _safe_int(value, default=None):
    if value is None:
        return default
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default


def _safe_float(value, default=None):
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _normalize_value(value):
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        if value == "":
            return None
        try:
            if "." in value:
                return float(value)
            return int(value)
        except ValueError:
            return value
    return value


# ============================================================
# EJECUTAR POWERSHELL (WINDOWS)
# ============================================================

def _run_powershell(script):
    if not IS_WINDOWS:
        return None

    try:
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                script,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15
        )

        if result.returncode != 0:
            logger.warning(f"[STORAGE WARNING] PowerShell devolvió código {result.returncode}")
            if result.stderr:
                logger.warning(f"[STORAGE WARNING] {result.stderr.strip()}")
            return None

        return result.stdout.strip()

    except subprocess.TimeoutExpired:
        logger.error("[STORAGE ERROR] PowerShell tardó demasiado en responder.")
        return None
    except Exception as e:
        logger.error(f"[STORAGE ERROR] Error ejecutando PowerShell: {e}")
        return None


# ============================================================
# OBTENER DATOS REALES DE STORAGE (WINDOWS)
# ============================================================

def get_windows_storage_health():
    if not IS_WINDOWS:
        return []

    script = r"""
$ErrorActionPreference = 'SilentlyContinue'
$result = @()
$physicalDisks = Get-PhysicalDisk

foreach ($disk in $physicalDisks) {
    $counter = $null
    try {
        $counter = Get-StorageReliabilityCounter -PhysicalDisk $disk
    }
    catch {
        $counter = $null
    }

    $result += [PSCustomObject]@{
        DeviceId = $disk.DeviceId
        FriendlyName = $disk.FriendlyName
        Model = $disk.Model
        SerialNumber = $disk.SerialNumber
        MediaType = [string]$disk.MediaType
        BusType = [string]$disk.BusType
        OperationalStatus = [string]$disk.OperationalStatus
        HealthStatus = [string]$disk.HealthStatus
        Size = $disk.Size
        Temperature = if ($counter) { $counter.Temperature } else { $null }
        TemperatureMax = if ($counter) { $counter.TemperatureMax } else { $null }
        Wear = if ($counter) { $counter.Wear } else { $null }
        PowerOnHours = if ($counter) { $counter.PowerOnHours } else { $null }
        ReadErrorsCorrected = if ($counter) { $counter.ReadErrorsCorrected } else { $null }
        ReadErrorsTotal = if ($counter) { $counter.ReadErrorsTotal } else { $null }
        ReadErrorsUncorrected = if ($counter) { $counter.ReadErrorsUncorrected } else { $null }
        WriteErrorsCorrected = if ($counter) { $counter.WriteErrorsCorrected } else { $null }
        WriteErrorsTotal = if ($counter) { $counter.WriteErrorsTotal } else { $null }
        WriteErrorsUncorrected = if ($counter) { $counter.WriteErrorsUncorrected } else { $null }
        StartStopCycleCount = if ($counter) { $counter.StartStopCycleCount } else { $null }
        LoadUnloadCycleCount = if ($counter) { $counter.LoadUnloadCycleCount } else { $null }
    }
}

$result | ConvertTo-Json -Depth 5 -Compress
"""

    output = _run_powershell(script)
    if not output:
        return []

    try:
        data = json.loads(output)
    except json.JSONDecodeError as e:
        logger.error(f"[STORAGE ERROR] No se pudo interpretar la respuesta de PowerShell: {e}")
        return []

    if isinstance(data, dict):
        data = [data]

    if not isinstance(data, list):
        return []

    normalized = []
    for item in data:
        if not isinstance(item, dict):
            continue
        normalized.append({
            key: _normalize_value(value)
            for key, value in item.items()
        })

    return normalized


# ============================================================
# CALCULAR SALUD
# ============================================================

def calculate_storage_health(data):
    if not isinstance(data, dict):
        return None

    health_status = str(data.get("HealthStatus", "") or "").strip().lower()
    wear = _safe_float(data.get("Wear"))
    read_uncorrected = _safe_int(data.get("ReadErrorsUncorrected"), 0)
    write_uncorrected = _safe_int(data.get("WriteErrorsUncorrected"), 0)

    if (read_uncorrected is not None and read_uncorrected > 0) or (write_uncorrected is not None and write_uncorrected > 0):
        return 0

    if wear is not None:
        wear = max(0, min(100, wear))
        return round(100 - wear, 1)

    if health_status in ("healthy", "ok", "normal"):
        return 100.0
    if health_status in ("warning", "degraded"):
        return 60.0
    if health_status in ("unhealthy", "critical", "failed"):
        return 0.0

    return None


# ============================================================
# NORMALIZAR PARA COREPulse
# ============================================================

def normalize_storage_data(raw_disks):
    normalized = []
    for index, disk in enumerate(raw_disks, start=1):
        if not isinstance(disk, dict):
            continue

        health = calculate_storage_health(disk)
        temperature = _safe_float(disk.get("Temperature"))
        temperature_max = _safe_float(disk.get("TemperatureMax"))

        normalized.append({
            "index": index,
            "device_id": disk.get("DeviceId"),
            "model": disk.get("Model") or disk.get("FriendlyName") or "Unidad de almacenamiento",
            "friendly_name": disk.get("FriendlyName"),
            "serial": disk.get("SerialNumber"),
            "media_type": disk.get("MediaType"),
            "bus_type": disk.get("BusType"),
            "operational_status": disk.get("OperationalStatus"),
            "health_status": disk.get("HealthStatus"),
            "health": health,
            "temperature": temperature,
            "temperature_max": temperature_max,
            "wear": _safe_float(disk.get("Wear")),
            "power_on_hours": _safe_int(disk.get("PowerOnHours")),
            "read_errors_corrected": _safe_int(disk.get("ReadErrorsCorrected"), 0),
            "read_errors_total": _safe_int(disk.get("ReadErrorsTotal"), 0),
            "read_errors_uncorrected": _safe_int(disk.get("ReadErrorsUncorrected"), 0),
            "write_errors_corrected": _safe_int(disk.get("WriteErrorsCorrected"), 0),
            "write_errors_total": _safe_int(disk.get("WriteErrorsTotal"), 0),
            "write_errors_uncorrected": _safe_int(disk.get("WriteErrorsUncorrected"), 0),
            "start_stop_cycles": _safe_int(disk.get("StartStopCycleCount")),
            "load_unload_cycles": _safe_int(disk.get("LoadUnloadCycleCount")),
            "used_gb": 0,
            "total_gb": round((_safe_int(disk.get("Size"), 0) or 0) / (1024 ** 3), 1),
            "used_percent": 0,
        })

    return normalized


# ============================================================
# FUNCIÓN PRINCIPAL (MULTIPLATAFORMA)
# ============================================================

def get_storage_health():
    """
    Función pública utilizada por CorePulse.
    Soporta Windows (PowerShell) y Linux (smartctl).
    """
    if platform.system() == "Linux":
        try:
            from core.storage_health_linux import get_linux_storage_health
            return get_linux_storage_health()
        except ImportError:
            logger.error("[STORAGE ERROR] No se pudo cargar storage_health_linux.py")
            return []

    if not IS_WINDOWS:
        logger.warning("[STORAGE WARNING] Sistema operativo no soportado para lectura nativa de almacenamiento.")
        return []

    raw = get_windows_storage_health()
    if not raw:
        logger.warning("[STORAGE WARNING] No se pudieron obtener datos de confiabilidad de las unidades.")
        return []

    normalized = normalize_storage_data(raw)
    logger.info(f"[STORAGE INFO] Se detectaron {len(normalized)} unidades.")
    
    return normalized


# ============================================================
# PRUEBA DIRECTA
# ============================================================

if __name__ == "__main__":
    print("=" * 70)
    print("COREPULSE - STORAGE HEALTH TEST")
    print("=" * 70)

    disks = get_storage_health()
    print()
    print(json.dumps(disks, indent=2, ensure_ascii=False))