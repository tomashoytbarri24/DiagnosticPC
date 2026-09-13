"""Lectura nativa del SMART / Health Information Log de unidades NVMe en Windows.

CorePulse usa IOCTL_STORAGE_QUERY_PROPERTY con StorageDeviceProtocolSpecificProperty.
No necesita CrystalDiskInfo ni ejecuta comandos vendor-specific. Si Windows, el
controlador o la unidad no exponen el log, devuelve ``{}`` y el consumidor muestra N/A.

Contrato: REAL_OR_NA.
"""
from __future__ import annotations

import ctypes
import logging
import os
import struct
from typing import Any, Dict, Optional

logger = logging.getLogger("CorePulse.Storage.NVMe")

# WinIoCtl.h / ntddstor.h
IOCTL_STORAGE_QUERY_PROPERTY = 0x002D1400
STORAGE_ADAPTER_PROTOCOL_SPECIFIC_PROPERTY = 49
STORAGE_DEVICE_PROTOCOL_SPECIFIC_PROPERTY = 50
PROPERTY_STANDARD_QUERY = 0
PROTOCOL_TYPE_NVME = 3
NVME_DATA_TYPE_LOG_PAGE = 2
NVME_LOG_PAGE_HEALTH_INFO = 0x02

# STORAGE_PROTOCOL_SPECIFIC_DATA contiene 10 ULONG = 40 bytes.
PROTOCOL_SPECIFIC_DATA_SIZE = 40
NVME_HEALTH_LOG_SIZE = 512


def _u128(raw: bytes, offset: int) -> int:
    return int.from_bytes(raw[offset:offset + 16], "little", signed=False)


def _kelvin_to_celsius(kelvin: int) -> Optional[float]:
    if not kelvin:
        return None
    value = float(kelvin) - 273.15
    # Defensa contra una respuesta inválida/corrupta. No convierte basura en sensor.
    if value < -100.0 or value > 250.0:
        return None
    return round(value, 1)


def _data_units_to_gb(units: int) -> float:
    # NVMe Data Unit: 1000 bloques de 512 bytes. Se expresa en GB decimales.
    return round((int(units) * 1000 * 512) / 1_000_000_000, 1)


def parse_nvme_health_log(data: bytes) -> Dict[str, Any]:
    """Parsea los 512 bytes de ``NVME_HEALTH_INFO_LOG`` sin estimar campos."""
    raw = bytes(data or b"")
    if len(raw) < NVME_HEALTH_LOG_SIZE:
        raise ValueError("NVMe SMART/Health log incompleto")

    critical_warning = int(raw[0])
    composite_kelvin = int.from_bytes(raw[1:3], "little")

    flags = []
    if critical_warning & 0x01:
        flags.append("AVAILABLE_SPARE_LOW")
    if critical_warning & 0x02:
        flags.append("TEMPERATURE_THRESHOLD")
    if critical_warning & 0x04:
        flags.append("RELIABILITY_DEGRADED")
    if critical_warning & 0x08:
        flags.append("READ_ONLY")
    if critical_warning & 0x10:
        flags.append("VOLATILE_MEMORY_BACKUP_FAILED")

    sensors = []
    for index in range(8):
        kelvin = int.from_bytes(raw[200 + index * 2:202 + index * 2], "little")
        celsius = _kelvin_to_celsius(kelvin)
        if celsius is not None:
            sensors.append({
                "name": f"NVMe Temperature Sensor {index + 1}",
                "value_c": celsius,
                "source": "Windows NVMe SMART/Health Log",
            })

    data_units_read = _u128(raw, 32)
    data_units_written = _u128(raw, 48)

    return {
        "source": "Windows NVMe SMART/Health Log",
        "critical_warning": critical_warning,
        "critical_warning_flags": flags,
        "temperature_c": _kelvin_to_celsius(composite_kelvin),
        "available_spare_percent": int(raw[3]),
        "available_spare_threshold_percent": int(raw[4]),
        # PercentageUsed es vida *usada*. No se convierte aquí en "salud".
        "percentage_used": int(raw[5]),
        "data_units_read": data_units_read,
        "data_units_written": data_units_written,
        "data_read_gb": _data_units_to_gb(data_units_read),
        "data_written_gb": _data_units_to_gb(data_units_written),
        "host_read_commands": _u128(raw, 64),
        "host_write_commands": _u128(raw, 80),
        "controller_busy_minutes": _u128(raw, 96),
        "power_cycles": _u128(raw, 112),
        "power_on_hours": _u128(raw, 128),
        "unsafe_shutdowns": _u128(raw, 144),
        "media_errors": _u128(raw, 160),
        "error_log_entries": _u128(raw, 176),
        "warning_temperature_minutes": int.from_bytes(raw[192:196], "little"),
        "critical_temperature_minutes": int.from_bytes(raw[196:200], "little"),
        "temperature_sensors": sensors,
        "raw_log_size": NVME_HEALTH_LOG_SIZE,
    }


def _query_protocol_health_log(handle, property_id: int, drive_index: int) -> Dict[str, Any]:
    """Consulta SMART NVMe por ámbito device o adapter usando el mismo handle."""
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.DeviceIoControl.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD,
        wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
        wintypes.LPVOID,
    ]
    kernel32.DeviceIoControl.restype = wintypes.BOOL

    # 512 bytes es el mínimo para un Log Page NVMe; dejamos margen para
    # miniports que devuelven descriptor/padding adicional.
    buffer_len = 4096
    payload = bytearray(buffer_len)
    struct.pack_into("<II", payload, 0, int(property_id), PROPERTY_STANDARD_QUERY)
    struct.pack_into(
        "<IIIIIIIIII",
        payload,
        8,
        PROTOCOL_TYPE_NVME,
        NVME_DATA_TYPE_LOG_PAGE,
        NVME_LOG_PAGE_HEALTH_INFO,
        0,
        PROTOCOL_SPECIFIC_DATA_SIZE,
        NVME_HEALTH_LOG_SIZE,
        0,
        0,
        0,
        0,
    )

    c_buffer = (ctypes.c_ubyte * len(payload)).from_buffer(payload)
    returned = wintypes.DWORD(0)
    ok = kernel32.DeviceIoControl(
        handle,
        IOCTL_STORAGE_QUERY_PROPERTY,
        c_buffer,
        8 + PROTOCOL_SPECIFIC_DATA_SIZE,
        c_buffer,
        len(payload),
        ctypes.byref(returned),
        None,
    )
    if not ok or returned.value < 8 + PROTOCOL_SPECIFIC_DATA_SIZE:
        return {}

    try:
        version, descriptor_size = struct.unpack_from("<II", payload, 0)
        if version < 8 + PROTOCOL_SPECIFIC_DATA_SIZE or descriptor_size < 8 + PROTOCOL_SPECIFIC_DATA_SIZE:
            return {}
        (
            protocol_type,
            data_type,
            request_value,
            _request_subvalue,
            data_offset,
            data_length,
            _fixed_return,
            _subvalue2,
            _subvalue3,
            _subvalue4,
        ) = struct.unpack_from("<IIIIIIIIII", payload, 8)
        if protocol_type != PROTOCOL_TYPE_NVME or data_type != NVME_DATA_TYPE_LOG_PAGE:
            return {}
        if request_value != NVME_LOG_PAGE_HEALTH_INFO:
            return {}
        if data_offset < PROTOCOL_SPECIFIC_DATA_SIZE or data_length < NVME_HEALTH_LOG_SIZE:
            return {}
        start = 8 + int(data_offset)
        end = start + NVME_HEALTH_LOG_SIZE
        if end > len(payload):
            return {}
        result = parse_nvme_health_log(bytes(payload[start:end]))
        result["physical_drive_index"] = drive_index
        result["query_property_id"] = int(property_id)
        result["query_scope"] = (
            "device"
            if int(property_id) == STORAGE_DEVICE_PROTOCOL_SPECIFIC_PROPERTY
            else "adapter"
        )
        result["source"] = f"Windows NVMe SMART/Health Log ({result['query_scope']})"
        return result
    except Exception:
        return {}


def query_nvme_health_log(physical_drive_index: int) -> Dict[str, Any]:
    r"""Lee ``\\.\PhysicalDriveN`` y devuelve SMART NVMe real o ``{}``.

    Se prueba primero StorageDeviceProtocolSpecificProperty y luego
    StorageAdapterProtocolSpecificProperty. Esta segunda ruta mejora la
    compatibilidad con NVMe detrás de controladores/VMD que no reenvían SMART
    por el namespace individual, pero sí por el controlador.
    """
    if os.name != "nt":
        return {}
    try:
        drive_index = int(physical_drive_index)
    except (TypeError, ValueError):
        return {}
    if drive_index < 0:
        return {}

    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
    ]
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    FILE_SHARE_READ = 0x00000001
    FILE_SHARE_WRITE = 0x00000002
    GENERIC_READ = 0x80000000
    GENERIC_WRITE = 0x40000000
    OPEN_EXISTING = 3
    INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

    path = rf"\\.\PhysicalDrive{drive_index}"
    for desired_access in (0, GENERIC_READ, GENERIC_READ | GENERIC_WRITE):
        handle = kernel32.CreateFileW(
            path,
            desired_access,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            None,
            OPEN_EXISTING,
            0,
            None,
        )
        value = getattr(handle, "value", handle) if handle else None
        if value in (None, INVALID_HANDLE_VALUE):
            continue
        try:
            for property_id in (
                STORAGE_DEVICE_PROTOCOL_SPECIFIC_PROPERTY,
                STORAGE_ADAPTER_PROTOCOL_SPECIFIC_PROPERTY,
            ):
                result = _query_protocol_health_log(handle, property_id, drive_index)
                if result:
                    return result
        except Exception as exc:
            logger.debug(
                "SMART NVMe no disponible para PhysicalDrive%s acceso=0x%X: %s",
                drive_index,
                int(desired_access),
                exc,
            )
        finally:
            try:
                kernel32.CloseHandle(handle)
            except Exception:
                pass
    return {}


__all__ = ["parse_nvme_health_log", "query_nvme_health_log"]
