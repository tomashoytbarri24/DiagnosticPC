"""Obtiene información real de salud y confiabilidad de unidades de almacenamiento."""
from __future__ import annotations

import json
import logging
from core.windows_commands import run_powershell

logger = logging.getLogger("CorePulse.Storage")
IS_WINDOWS = True


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
    result = run_powershell(script, timeout=25, category='STORAGE')
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
$physicalDisks = @(Get-PhysicalDisk)
$osDisks = @(Get-Disk)
$cimCounters = @()
try {
    $cimCounters = @(Get-CimInstance -Namespace 'root/Microsoft/Windows/Storage' -ClassName MSFT_StorageReliabilityCounter)
} catch {
    $cimCounters = @()
}

function Get-CounterEvidenceScore($counter) {
    if (-not $counter) { return -1 }
    $score = 0
    foreach ($name in @(
        'Temperature','TemperatureMax','Wear','PowerOnHours',
        'ReadErrorsCorrected','ReadErrorsTotal','ReadErrorsUncorrected',
        'WriteErrorsCorrected','WriteErrorsTotal','WriteErrorsUncorrected',
        'StartStopCycleCount','LoadUnloadCycleCount',
        'FlushLatencyMax','ReadLatencyMax','WriteLatencyMax'
    )) {
        try {
            if ($null -ne $counter.$name) { $score += 1 }
        } catch { }
    }
    return $score
}

function Test-CounterLive($counter) {
    if (-not $counter) { return $false }
    foreach ($name in @(
        'PowerOnHours','ReadErrorsCorrected','ReadErrorsTotal','ReadErrorsUncorrected',
        'WriteErrorsCorrected','WriteErrorsTotal','WriteErrorsUncorrected',
        'StartStopCycleCount','LoadUnloadCycleCount',
        'FlushLatencyMax','ReadLatencyMax','WriteLatencyMax'
    )) {
        try {
            $value = $counter.$name
            if ($null -ne $value -and [double]$value -gt 0) { return $true }
        } catch { }
    }
    return $false
}

function Select-BestReliabilityCounter($diskCounter, $physicalCounter, $cimCounter) {
    # V201: Windows expone dos asociaciones oficiales para el mismo contador:
    # MSFT_Disk -> ReliabilityCounter y MSFT_PhysicalDisk -> ReliabilityCounter.
    # En algunos controladores NVMe/VMD una ruta devuelve Wear real y la otra
    # sólo un placeholder. Priorizamos cualquier Wear cuantitativo >0; si no,
    # elegimos la ruta con más campos realmente expuestos. No fabricamos salud.
    $items = @()
    if ($diskCounter)     { $items += [PSCustomObject]@{ Name='Get-StorageReliabilityCounter -Disk'; Counter=$diskCounter } }
    if ($physicalCounter) { $items += [PSCustomObject]@{ Name='Get-StorageReliabilityCounter -PhysicalDisk'; Counter=$physicalCounter } }
    if ($cimCounter)      { $items += [PSCustomObject]@{ Name='MSFT_StorageReliabilityCounter CIM'; Counter=$cimCounter } }
    if ($items.Count -eq 0) { return $null }

    foreach ($item in $items) {
        try {
            if ($null -ne $item.Counter.Wear -and [double]$item.Counter.Wear -gt 0) {
                return $item
            }
        } catch { }
    }

    $best = $items[0]
    $bestScore = Get-CounterEvidenceScore $best.Counter
    foreach ($item in $items) {
        $score = Get-CounterEvidenceScore $item.Counter
        if ($score -gt $bestScore) {
            $best = $item
            $bestScore = $score
        }
    }
    return $best
}

foreach ($disk in $physicalDisks) {
    # Empareja MSFT_PhysicalDisk con MSFT_Disk antes de consultar la segunda
    # asociación de ReliabilityCounter. Serial es autoridad; nombre+tamaño es
    # fallback sólo cuando resulta inequívoco.
    $osDisk = $null
    $diskNumber = $null
    try {
        $serial = ([string]$disk.SerialNumber).Trim()
        $matches = @()
        if ($serial) {
            $matches = @($osDisks | Where-Object { ([string]$_.SerialNumber).Trim() -eq $serial })
        }
        if ($matches.Count -ne 1) {
            $matches = @($osDisks | Where-Object {
                ([string]$_.FriendlyName).Trim() -eq ([string]$disk.FriendlyName).Trim() -and
                [math]::Abs([double]$_.Size - [double]$disk.Size) -lt [math]::Max(1048576, ([double]$disk.Size * 0.01))
            })
        }
        if ($matches.Count -eq 1) {
            $osDisk = $matches[0]
            $diskNumber = [int]$osDisk.Number
        } else {
            $candidate = $null
            try { $candidate = [int]$disk.DeviceId } catch { $candidate = $null }
            $byNumber = @($osDisks | Where-Object { $null -ne $candidate -and $_.Number -eq $candidate })
            if ($byNumber.Count -eq 1) {
                $osDisk = $byNumber[0]
                $diskNumber = $candidate
            }
        }
    } catch {
        $osDisk = $null
        $diskNumber = $null
    }

    $counterPhysical = $null
    try {
        $counterPhysical = Get-StorageReliabilityCounter -PhysicalDisk $disk
    } catch { $counterPhysical = $null }

    $counterDisk = $null
    if ($osDisk) {
        try {
            # Ruta documentada alternativa. En ciertos portátiles con VMD/RST
            # es la que sí publica Wear/temperatura del NVMe real.
            $counterDisk = Get-StorageReliabilityCounter -Disk $osDisk
        } catch { $counterDisk = $null }
    }

    $counterCim = $null
    try {
        $candidateIds = @([string]$disk.DeviceId)
        if ($null -ne $diskNumber) { $candidateIds += [string]$diskNumber }
        $counterMatches = @($cimCounters | Where-Object { $candidateIds -contains ([string]$_.DeviceId) })
        if ($counterMatches.Count -eq 1) {
            $counterCim = $counterMatches[0]
        }
    } catch { $counterCim = $null }

    $selected = Select-BestReliabilityCounter $counterDisk $counterPhysical $counterCim
    $counter = if ($selected) { $selected.Counter } else { $null }
    $counterPath = if ($selected) { $selected.Name } else { $null }

    $mounts = @()
    $volumeTotal = $null
    $volumeFree = $null
    $volumeUsed = $null
    $volumeUsedPercent = $null
    $volumeCount = 0
    if ($null -ne $diskNumber) {
        try {
            $parts = @(Get-Partition -DiskNumber $diskNumber)
            $mounts = $parts |
                Where-Object { $_.DriveLetter } |
                ForEach-Object { "$($_.DriveLetter):" }

            $volumes = @()
            foreach ($part in $parts) {
                try {
                    $vol = Get-Volume -Partition $part -ErrorAction SilentlyContinue
                    if ($vol -and $null -ne $vol.Size -and [double]$vol.Size -gt 0) {
                        $volumes += $vol
                    }
                } catch { }
            }
            if ($volumes.Count -gt 0) {
                $volumeCount = $volumes.Count
                $volumeTotal = [double](($volumes | Measure-Object -Property Size -Sum).Sum)
                $volumeFree = [double](($volumes | Measure-Object -Property SizeRemaining -Sum).Sum)
                if ($null -ne $volumeTotal -and $volumeTotal -gt 0) {
                    $volumeUsed = [math]::Max(0, $volumeTotal - [double]$volumeFree)
                    $volumeUsedPercent = ($volumeUsed / $volumeTotal) * 100.0
                }
            }
        } catch { $mounts = @() }
    }

    $wearDisk = if ($counterDisk -and $null -ne $counterDisk.Wear) { $counterDisk.Wear } else { $null }
    $wearPhysical = if ($counterPhysical -and $null -ne $counterPhysical.Wear) { $counterPhysical.Wear } else { $null }
    $wearCim = if ($counterCim -and $null -ne $counterCim.Wear) { $counterCim.Wear } else { $null }

    $result += [PSCustomObject]@{
        DeviceId = if ($null -ne $diskNumber) { $diskNumber } else { $disk.DeviceId }
        PhysicalDiskDeviceId = $disk.DeviceId
        DiskNumber = $diskNumber
        FriendlyName = $disk.FriendlyName
        Model = $disk.Model
        SerialNumber = $disk.SerialNumber
        FirmwareVersion = $disk.FirmwareVersion
        MountPoints = ($mounts -join ', ')
        VolumeCount = $volumeCount
        VolumeTotal = $volumeTotal
        VolumeFree = $volumeFree
        VolumeUsed = $volumeUsed
        VolumeUsedPercent = $volumeUsedPercent
        MediaType = [string]$disk.MediaType
        BusType = [string]$disk.BusType
        OperationalStatus = [string]$disk.OperationalStatus
        HealthStatus = [string]$disk.HealthStatus
        Size = $disk.Size
        Temperature = if ($counter) { $counter.Temperature } else { $null }
        TemperatureMax = if ($counter) { $counter.TemperatureMax } else { $null }
        Wear = if ($counter) { $counter.Wear } else { $null }
        WearByDisk = $wearDisk
        WearByPhysicalDisk = $wearPhysical
        WearByCim = $wearCim
        ReliabilityCounterPath = $counterPath
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
        ReliabilityCounterLive = if ($counter) { Test-CounterLive $counter } else { $false }
        ReliabilityEvidenceFields = if ($counter) {
            @('Temperature','TemperatureMax','Wear','PowerOnHours','ReadErrorsCorrected','ReadErrorsTotal','ReadErrorsUncorrected','WriteErrorsCorrected','WriteErrorsTotal','WriteErrorsUncorrected','StartStopCycleCount','LoadUnloadCycleCount','FlushLatencyMax','ReadLatencyMax','WriteLatencyMax') |
                Where-Object { $null -ne $counter.$_ } |
                ForEach-Object { $_ }
        } else { @() }
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
                f"{disk.get('ReliabilityCounterPath') or 'Windows Storage Reliability'} Wear · vida restante 100 - desgaste"
                if calculate_storage_health(disk) is not None else None
            ),
            "health_derived": calculate_storage_health(disk) is not None,
            "reliability_counter_available": bool(disk.get("ReliabilityCounterAvailable")),
            "reliability_counter_live": bool(disk.get("ReliabilityCounterLive")),
            "reliability_counter_path": disk.get("ReliabilityCounterPath"),
            "wear_by_disk": _safe_float(disk.get("WearByDisk")),
            "wear_by_physical_disk": _safe_float(disk.get("WearByPhysicalDisk")),
            "wear_by_cim": _safe_float(disk.get("WearByCim")),
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
            "used_gb": (round(_safe_float(disk.get("VolumeUsed")) / 1024 ** 3, 2)
                        if _safe_float(disk.get("VolumeUsed")) is not None else None),
            "free_gb": (round(_safe_float(disk.get("VolumeFree")) / 1024 ** 3, 2)
                        if _safe_float(disk.get("VolumeFree")) is not None else None),
            "volume_total_gb": (round(_safe_float(disk.get("VolumeTotal")) / 1024 ** 3, 2)
                                 if _safe_float(disk.get("VolumeTotal")) is not None else None),
            "volume_count": _safe_int(disk.get("VolumeCount"), 0),
            "total_gb": round(size / 1024 ** 3, 1) if size is not None else None,
            "used_percent": _safe_float(disk.get("VolumeUsedPercent")),
            "source": "Windows Storage Reliability",
            "policy": "REAL_OR_NA",
        })
    return normalized


def get_storage_health():
    """Obtiene confiabilidad nativa de almacenamiento en Windows sin inventar campos."""
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
