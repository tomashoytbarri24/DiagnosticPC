"""Obtiene información real de salud y confiabilidad de unidades de almacenamiento."""
from __future__ import annotations

import json
import logging
import platform
import subprocess

logger = logging.getLogger("CorePulse.Storage")
IS_WINDOWS = platform.system() == "Windows"


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
            timeout=15,
        )
        if result.returncode != 0:
            logger.warning("[STORAGE WARNING] PowerShell devolvió código %s", result.returncode)
            if result.stderr:
                logger.warning("[STORAGE WARNING] %s", result.stderr.strip())
            return None
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        logger.error("[STORAGE ERROR] PowerShell tardó demasiado en responder.")
        return None
    except Exception as exc:
        logger.error("[STORAGE ERROR] Error ejecutando PowerShell: %s", exc)
        return None


def get_windows_storage_health():
    """Lee Get-PhysicalDisk/Get-StorageReliabilityCounter sin derivar métricas."""
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

    $mounts = @()
    try {
        $diskNumber = [int]$disk.DeviceId
        $mounts = Get-Partition -DiskNumber $diskNumber |
            Where-Object { $_.DriveLetter } |
            ForEach-Object { "$($_.DriveLetter):" }
    }
    catch {
        $mounts = @()
    }

    $result += [PSCustomObject]@{
        DeviceId = $disk.DeviceId
        FriendlyName = $disk.FriendlyName
        Model = $disk.Model
        SerialNumber = $disk.SerialNumber
        FirmwareVersion = $disk.FirmwareVersion
        MountPoints = ($mounts -join ', ')
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
    except json.JSONDecodeError as exc:
        logger.error("[STORAGE ERROR] No se pudo interpretar PowerShell: %s", exc)
        return []

    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        return []

    return [
        {key: _normalize_value(value) for key, value in item.items()}
        for item in data
        if isinstance(item, dict)
    ]


def calculate_storage_health(data):
    """No convierte ``Wear`` en un porcentaje de salud.

    ``Wear`` es desgaste reportado por Windows/driver. Mostrar ``100 - Wear`` como
    "vida" haría pasar una derivación por una lectura SMART real, por lo que CorePulse
    devuelve ``None`` aquí.
    """
    return None


def normalize_storage_data(raw_disks):
    normalized = []
    for index, disk in enumerate(raw_disks, start=1):
        if not isinstance(disk, dict):
            continue
        size = _safe_int(disk.get("Size"))
        normalized.append({
            "index": index,
            "device_id": disk.get("DeviceId"),
            "model": disk.get("Model") or disk.get("FriendlyName") or "Unidad de almacenamiento",
            "friendly_name": disk.get("FriendlyName"),
            "serial": disk.get("SerialNumber"),
            "firmware_version": disk.get("FirmwareVersion"),
            "mount_points": disk.get("MountPoints"),
            "media_type": disk.get("MediaType"),
            "bus_type": disk.get("BusType"),
            "operational_status": disk.get("OperationalStatus"),
            "health_status": disk.get("HealthStatus"),
            # Intencionalmente N/A: no se deriva de Wear.
            "health": calculate_storage_health(disk),
            "temperature": _safe_float(disk.get("Temperature")),
            "temperature_max": _safe_float(disk.get("TemperatureMax")),
            "wear": _safe_float(disk.get("Wear")),
            "power_on_hours": _safe_int(disk.get("PowerOnHours")),
            "read_errors_corrected": _safe_int(disk.get("ReadErrorsCorrected")),
            "read_errors_total": _safe_int(disk.get("ReadErrorsTotal")),
            "read_errors_uncorrected": _safe_int(disk.get("ReadErrorsUncorrected")),
            "write_errors_corrected": _safe_int(disk.get("WriteErrorsCorrected")),
            "write_errors_total": _safe_int(disk.get("WriteErrorsTotal")),
            "write_errors_uncorrected": _safe_int(disk.get("WriteErrorsUncorrected")),
            "start_stop_cycles": _safe_int(disk.get("StartStopCycleCount")),
            "load_unload_cycles": _safe_int(disk.get("LoadUnloadCycleCount")),
            "used_gb": None,
            "total_gb": round(size / 1024 ** 3, 1) if size is not None else None,
            "used_percent": None,
            "source": "Windows Storage Reliability",
            "policy": "REAL_OR_NA",
        })
    return normalized


def get_storage_health():
    """Obtiene confiabilidad nativa sin rellenar campos no expuestos."""
    if platform.system() == "Linux":
        try:
            from core.storage_health_linux import get_linux_storage_health
            return get_linux_storage_health()
        except ImportError:
            logger.error("[STORAGE ERROR] No se pudo cargar storage_health_linux.py")
            return []

    if not IS_WINDOWS:
        logger.warning("[STORAGE WARNING] SO no soportado para lectura nativa.")
        return []

    raw = get_windows_storage_health()
    if not raw:
        logger.warning("[STORAGE WARNING] No se obtuvieron datos de confiabilidad.")
        return []

    normalized = normalize_storage_data(raw)
    logger.info("[STORAGE INFO] Se detectaron %s unidades.", len(normalized))
    return normalized


if __name__ == "__main__":
    print("=" * 70)
    print("COREPULSE - STORAGE HEALTH TEST")
    print("=" * 70)
    print(json.dumps(get_storage_health(), indent=2, ensure_ascii=False))
