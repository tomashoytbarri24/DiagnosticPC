"""Obtiene información real de salud y confiabilidad de unidades de almacenamiento."""
from __future__ import annotations

import json
import logging
import platform
from core.windows_commands import run_powershell

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
    result = run_powershell(script, timeout=15, category='STORAGE')
    if not result.ok:
        logger.warning('[STORAGE WARNING] PowerShell falló: %s', result.message())
        return None
    return result.stdout.strip()


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

    # Algunos drivers exponen MSFT_StorageReliabilityCounter pero el cmdlet no
    # resuelve correctamente la asociación PhysicalDisk. Intentamos la clase CIM
    # directa antes de declarar Wear/temperatura como ausentes.
    if (-not $counter) {
        try {
            $diskId = [string]$disk.DeviceId
            $counter = Get-CimInstance -Namespace 'root/Microsoft/Windows/Storage' -ClassName MSFT_StorageReliabilityCounter |
                Where-Object { [string]$_.DeviceId -eq $diskId } |
                Select-Object -First 1
        }
        catch {
            $counter = $null
        }
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
        FlushLatencyMax = if ($counter) { $counter.FlushLatencyMax } else { $null }
        ReadLatencyMax = if ($counter) { $counter.ReadLatencyMax } else { $null }
        WriteLatencyMax = if ($counter) { $counter.WriteLatencyMax } else { $null }
        ReliabilityCounterAvailable = [bool]$counter
        ReliabilityEvidenceFields = if ($counter) {
            @('Temperature','TemperatureMax','Wear','PowerOnHours','ReadErrorsCorrected','ReadErrorsTotal','ReadErrorsUncorrected','WriteErrorsCorrected','WriteErrorsTotal','WriteErrorsUncorrected','StartStopCycleCount','LoadUnloadCycleCount','FlushLatencyMax','ReadLatencyMax','WriteLatencyMax') |
                Where-Object { $null -ne $counter.$_ } |
                ForEach-Object { $_ }
        } else { @() }
        ReliabilityCounterLive = if ($counter) {
            $evidence = @()
            foreach ($name in @('PowerOnHours','ReadErrorsCorrected','ReadErrorsTotal','ReadErrorsUncorrected','WriteErrorsCorrected','WriteErrorsTotal','WriteErrorsUncorrected','StartStopCycleCount','LoadUnloadCycleCount','FlushLatencyMax','ReadLatencyMax','WriteLatencyMax')) {
                $value = $counter.$name
                if ($null -ne $value) {
                    try {
                        if ([double]$value -gt 0) { $evidence += $name }
                    } catch { }
                }
            }
            # Wear=0 por sí solo puede ser ambiguo en miniports incompletos.
            # Latencias reales de E/S, horas/ciclos o contadores de error no cero
            # demuestran que MSFT_StorageReliabilityCounter está activo y no es
            # un objeto placeholder. En ese caso Wear=0 sí es evidencia
            # cuantitativa válida de 0% de desgaste reportado por Windows.
            [bool]($evidence.Count -gt 0)
        } else { $false }
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


def _status_is_healthy(data):
    raw = str(data.get("HealthStatus") or data.get("health_status") or "").strip().casefold()
    op = str(data.get("OperationalStatus") or data.get("operational_status") or "").strip().casefold()
    return raw in {"healthy", "ok", "normal"} or op in {"healthy", "ok", "normal"}


def _reliability_counter_live(data):
    value = data.get("ReliabilityCounterLive")
    if value is None:
        value = data.get("reliability_counter_live")
    if isinstance(value, str):
        return value.strip().casefold() in {"true", "1", "yes"}
    return bool(value)


def calculate_storage_health(data):
    """Deriva vida restante sólo desde desgaste cuantitativo corroborado.

    ``Wear`` de ``MSFT_StorageReliabilityCounter`` representa porcentaje de
    desgaste. Algunos controladores devuelven 0 incluso cuando no implementan
    realmente el contador; por eso un 0 sólo se acepta si el mismo proveedor
    entrega además evidencia operacional real (latencias de E/S, horas, ciclos
    o errores) y Windows reporta el disco sano. Un Wear positivo es evidencia cuantitativa
    por sí mismo y se convierte en ``100 - Wear``.
    """
    wear = _safe_float(data.get("Wear") if "Wear" in data else data.get("wear"))
    if wear is None or wear < 0:
        return None
    if wear > 0:
        return max(0.0, min(100.0, 100.0 - wear))
    if wear == 0 and _reliability_counter_live(data) and _status_is_healthy(data):
        return 100.0
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
            "health": calculate_storage_health(disk),
            "health_source": (
                "Windows Storage Reliability Wear · vida restante 100 - desgaste"
                if calculate_storage_health(disk) is not None else None
            ),
            "health_derived": calculate_storage_health(disk) is not None,
            "reliability_counter_available": bool(disk.get("ReliabilityCounterAvailable")),
            "reliability_counter_live": bool(disk.get("ReliabilityCounterLive")),
            "reliability_evidence_fields": disk.get("ReliabilityEvidenceFields") or [],
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
            "flush_latency_max_ms": _safe_float(disk.get("FlushLatencyMax")),
            "read_latency_max_ms": _safe_float(disk.get("ReadLatencyMax")),
            "write_latency_max_ms": _safe_float(disk.get("WriteLatencyMax")),
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
