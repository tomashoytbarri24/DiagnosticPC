"""Construye la ficha detallada de almacenamiento de CorePulse.

Fuentes permitidas:
- LibreHardwareMonitor: sensores/telemetría real.
- Win32_DiskDrive: identidad e índice físico.
- Windows Storage Reliability Counter: confiabilidad genérica, cuando existe.
- Windows NVMe SMART/Health Log: contadores NVMe directos, cuando el driver los expone.

Los campos ausentes permanecen N/A. En particular, CorePulse NO convierte
``Wear`` ni ``PercentageUsed`` en un porcentaje inventado de salud.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

from core.hardware_policy import normalize_hardware_label


def _text(value: Any) -> str:
    return str(value or "").strip()


def _number(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> Optional[int]:
    number = _number(value)
    return int(number) if number is not None else None


def _first(*values):
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def _model_match(a: Any, b: Any) -> bool:
    left = normalize_hardware_label(a)
    right = normalize_hardware_label(b)
    if not left or not right:
        return False
    if left == right:
        return True
    lt = set(left.split())
    rt = set(right.split())
    common = lt & rt
    return len(common) >= 2 and len(common) / max(1, min(len(lt), len(rt))) >= 0.65


def match_reliability_record(
    device: Dict[str, Any],
    records: Iterable[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Empareja confiabilidad Windows sin elegir una unidad por posición.

    Prioridad:
    1) serial exacto;
    2) Disk Index/DeviceId + modelo compatible;
    3) modelo únicamente cuando la coincidencia es inequívoca.
    """
    records = [r for r in (records or []) if isinstance(r, dict)]
    if not records:
        return None

    os_inv = device.get("os_inventory") if isinstance(device.get("os_inventory"), dict) else {}
    serial = _text(_first(device.get("serial_number"), os_inv.get("serial_number"))).casefold()
    model = _text(_first(
        device.get("model"),
        device.get("name"),
        os_inv.get("model"),
        os_inv.get("name"),
    ))
    disk_index = _first(device.get("disk_index"), os_inv.get("disk_index"))

    if serial:
        exact = [
            row for row in records
            if _text(_first(
                row.get("serial"),
                row.get("serial_number"),
                row.get("SerialNumber"),
            )).casefold() == serial
        ]
        if len(exact) == 1:
            return exact[0]
        if len(exact) > 1:
            return None

    if disk_index is not None:
        indexed = [
            row for row in records
            if str(_first(row.get("device_id"), row.get("DeviceId"), "")).strip()
            == str(disk_index).strip()
        ]
        if len(indexed) == 1:
            row_model = _first(
                indexed[0].get("model"),
                indexed[0].get("friendly_name"),
                indexed[0].get("Model"),
                indexed[0].get("FriendlyName"),
            )
            if not model or not row_model or _model_match(model, row_model):
                return indexed[0]
        elif len(indexed) > 1:
            return None

    model_matches = [
        row for row in records
        if _model_match(
            model,
            _first(
                row.get("model"),
                row.get("friendly_name"),
                row.get("Model"),
                row.get("FriendlyName"),
            ),
        )
    ]
    return model_matches[0] if len(model_matches) == 1 else None


def _fast_disk(index: int, disks: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    matches = [
        disk for disk in (disks or [])
        if isinstance(disk, dict) and disk.get("index") == index
    ]
    return dict(matches[0]) if len(matches) == 1 else {}


def _device(index: int, telemetry: Dict[str, Any]) -> Dict[str, Any]:
    devices = telemetry.get("_storage_devices") if isinstance(telemetry, dict) else None
    if not isinstance(devices, list) or index < 0 or index >= len(devices):
        return {}
    value = devices[index]
    return dict(value) if isinstance(value, dict) else {}


def resolve_physical_disk_index(index: int, telemetry: Dict[str, Any]) -> Optional[int]:
    """Devuelve el Win32_DiskDrive.Index de la unidad si fue emparejada exactamente."""
    device = _device(index, telemetry or {})
    os_inv = device.get("os_inventory") if isinstance(device.get("os_inventory"), dict) else {}
    value = _first(os_inv.get("disk_index"), device.get("disk_index"))
    return _int(value)


def _space_values(fast: Dict[str, Any], device: Dict[str, Any]):
    total = _number(_first(fast.get("total_gb"), device.get("total_space_gb")))
    used_pct = _number(_first(fast.get("used_percent"), device.get("used_space_percent")))
    free = _number(device.get("free_space_gb"))
    used = _number(fast.get("used_gb"))

    if used is None and total is not None and free is not None:
        used = max(0.0, total - free)
    if free is None and total is not None and used is not None:
        free = max(0.0, total - used)
    return total, used, free, used_pct


def _metric_source(device: Dict[str, Any], metric: str) -> str:
    metrics = device.get("_metrics") if isinstance(device.get("_metrics"), dict) else {}
    meta = metrics.get(metric) if isinstance(metrics.get(metric), dict) else {}
    return _text(meta.get("source"))


def build_storage_detail_snapshot(
    index: int,
    telemetry: Dict[str, Any],
    disks: Iterable[Dict[str, Any]],
    reliability_records: Optional[Iterable[Dict[str, Any]]] = None,
    nvme_smart: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Devuelve una ficha normalizada para una unidad física concreta."""
    device = _device(index, telemetry or {})
    fast = _fast_disk(index, disks or [])
    os_inv = device.get("os_inventory") if isinstance(device.get("os_inventory"), dict) else {}
    reliability = match_reliability_record(device, reliability_records or []) if device else None
    reliability = reliability if isinstance(reliability, dict) else {}
    nvme = nvme_smart if isinstance(nvme_smart, dict) else {}

    total, used, free, used_pct = _space_values(fast, device)

    # Preferimos el sensor Life/Health certificado del dispositivo. Solo usamos el
    # valor consolidado de fast si no existe ese sensor. Jamás 100-Wear.
    life = _number(_first(device.get("life_percent"), fast.get("health")))
    health_source = _metric_source(device, "life_percent")
    if life is not None and not health_source:
        health_source = _text(device.get("source"))
    if life is not None and not health_source and fast.get("health") is not None:
        health_source = "Fuente de almacenamiento consolidada"

    temp = _number(_first(
        device.get("temperature_c"),
        nvme.get("temperature_c"),
        fast.get("temperature_c"),
        reliability.get("temperature"),
    ))
    warning_temp = _number(device.get("warning_temperature_c"))
    critical_temp = _number(device.get("critical_temperature_c"))

    sensors = []
    seen = set()
    for sensor in device.get("temperature_sensors_c") or []:
        if not isinstance(sensor, dict):
            continue
        value = _number(sensor.get("value"))
        if value is None:
            continue
        name = _text(sensor.get("name")) or "Sensor"
        sensors.append({
            "name": name,
            "value_c": value,
            "source": _text(sensor.get("source")) or "LibreHardwareMonitor",
        })
        seen.add(normalize_hardware_label(name))

    for sensor in nvme.get("temperature_sensors") or []:
        if not isinstance(sensor, dict):
            continue
        value = _number(sensor.get("value_c"))
        if value is None:
            continue
        name = _text(sensor.get("name")) or "NVMe Sensor"
        key = normalize_hardware_label(name)
        if key in seen:
            continue
        sensors.append({
            "name": name,
            "value_c": value,
            "source": _text(sensor.get("source")) or "Windows NVMe SMART/Health Log",
        })
        seen.add(key)

    sources = []
    for source in [
        device.get("source"),
        *(device.get("inventory_sources") or []),
        "Windows Storage Reliability" if reliability else None,
        nvme.get("source") if nvme else None,
    ]:
        source = _text(source)
        if source and source not in sources:
            sources.append(source)

    model = _text(_first(
        device.get("model"),
        device.get("name"),
        os_inv.get("model"),
        os_inv.get("name"),
        fast.get("model"),
        reliability.get("model"),
        reliability.get("friendly_name"),
    )) or f"Unidad {index}"

    nvme_used = _number(nvme.get("percentage_used"))
    windows_wear = _number(reliability.get("wear"))
    wear = nvme_used if nvme_used is not None else windows_wear
    wear_source = (
        "SMART NVMe"
        if nvme_used is not None
        else "Windows Reliability"
        if windows_wear is not None
        else "N/A"
    )

    return {
        "index": index,
        "physical_disk_index": resolve_physical_disk_index(index, telemetry or {}),
        "model": model,
        "mount_points": (
            _text(fast.get("mount_points"))
            if _text(fast.get("mount_points")).upper() not in {"", "N/A", "NONE"}
            else _text(reliability.get("mount_points"))
        ) or "N/A",
        "capacity_gb": total,
        "used_gb": used,
        "free_gb": free,
        "used_percent": used_pct,
        "health_percent": life,
        "health_source": health_source or "N/A",
        "temperature_c": temp,
        "warning_temperature_c": warning_temp,
        "critical_temperature_c": critical_temp,
        "temperature_sensors": sensors,
        "interface": _text(_first(
            os_inv.get("interface_type"),
            device.get("interface_type"),
            reliability.get("bus_type"),
        )) or "N/A",
        "media_type": _text(_first(
            os_inv.get("media_type_os"),
            device.get("media_type_os"),
            reliability.get("media_type"),
        )) or "N/A",
        "firmware": _text(_first(
            os_inv.get("firmware_revision"),
            reliability.get("firmware_version"),
        )) or "N/A",
        "serial": _text(_first(
            device.get("serial_number"),
            os_inv.get("serial_number"),
            reliability.get("serial"),
        )) or "N/A",
        "windows_health_status": _text(_first(
            reliability.get("health_status"),
            os_inv.get("os_status"),
        )) or "N/A",
        "operational_status": _text(_first(
            reliability.get("operational_status"),
            os_inv.get("os_status"),
        )) or "N/A",
        "wear_percent": wear,
        "wear_source": wear_source,
        "available_spare_percent": _number(nvme.get("available_spare_percent")),
        "available_spare_threshold_percent": _number(nvme.get("available_spare_threshold_percent")),
        "power_on_hours": _int(_first(
            nvme.get("power_on_hours"),
            device.get("power_on_hours"),
            reliability.get("power_on_hours"),
        )),
        "power_on_count": _int(_first(
            nvme.get("power_cycles"),
            device.get("power_on_count"),
        )),
        "start_stop_cycles": _int(reliability.get("start_stop_cycles")),
        "load_unload_cycles": _int(reliability.get("load_unload_cycles")),
        "data_read_gb": _number(_first(
            nvme.get("data_read_gb"),
            device.get("data_read"),
        )),
        "data_written_gb": _number(_first(
            nvme.get("data_written_gb"),
            device.get("data_written"),
        )),
        "unsafe_shutdowns": _int(nvme.get("unsafe_shutdowns")),
        "media_errors": _int(nvme.get("media_errors")),
        "error_log_entries": _int(nvme.get("error_log_entries")),
        "critical_warning": _int(nvme.get("critical_warning")),
        "critical_warning_flags": list(nvme.get("critical_warning_flags") or []),
        "read_errors_corrected": _int(reliability.get("read_errors_corrected")),
        "read_errors_total": _int(reliability.get("read_errors_total")),
        "read_errors_uncorrected": _int(reliability.get("read_errors_uncorrected")),
        "write_errors_corrected": _int(reliability.get("write_errors_corrected")),
        "write_errors_total": _int(reliability.get("write_errors_total")),
        "write_errors_uncorrected": _int(reliability.get("write_errors_uncorrected")),
        "temperature_max_c": _number(reliability.get("temperature_max")),
        "telemetry_available": bool(device.get("telemetry_available", True) if device else False),
        "reliability_available": bool(reliability),
        "nvme_smart_available": bool(nvme),
        "identity_ambiguous": bool(device.get("identity_ambiguous")),
        "sources": sources,
        "policy": "REAL_OR_NA",
        "derived_health_from_wear": False,
    }


__all__ = [
    "build_storage_detail_snapshot",
    "match_reliability_record",
    "resolve_physical_disk_index",
]
