"""Enriquecimiento de salud de almacenamiento para el Resumen de CorePulse.

Esta capa consulta fuentes reales en segundo plano y nunca bloquea el arranque:
- sensor Life/Health ya certificado por LibreHardwareMonitor;
- Windows Storage Reliability Counter;
- NVMe SMART/Health Log nativo cuando el controlador lo expone.

Cuando NVMe expone ``Percentage Used`` o Windows expone ``Wear``, CorePulse puede
mostrar *vida restante derivada* = 100 - desgaste. El valor se etiqueta como
derivado para no presentarlo como un sensor directo de "Health %".
"""
from __future__ import annotations

import copy
from typing import Any, Dict, Optional

from core.storage_health import get_storage_health
from core.storage_details import match_reliability_record, resolve_physical_disk_index
from core.nvme_smart_windows import query_nvme_health_log


def _num(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clamp_pct(value: Any) -> Optional[float]:
    number = _num(value)
    if number is None:
        return None
    return max(0.0, min(100.0, number))


def _remaining_from_wear(value: Any) -> Optional[float]:
    wear = _num(value)
    if wear is None or wear < 0:
        return None
    return max(0.0, min(100.0, 100.0 - wear))


def _status_label(value: Any) -> str:
    raw = str(value or '').strip()
    low = raw.casefold()
    if not raw:
        return ''
    if low in {'healthy', 'ok', 'normal'}:
        return 'Saludable'
    if 'warning' in low or 'warn' in low:
        return 'Advertencia'
    if 'unhealthy' in low or 'critical' in low or 'failed' in low:
        return 'Crítico'
    return raw


def _device_at(telemetry: Dict[str, Any], index: int) -> Dict[str, Any]:
    devices = telemetry.get('_storage_devices') if isinstance(telemetry, dict) else None
    if not isinstance(devices, list) or index < 0 or index >= len(devices):
        return {}
    item = devices[index]
    return dict(item) if isinstance(item, dict) else {}


def collect_storage_summary_health(telemetry: Dict[str, Any]) -> Dict[int, Dict[str, Any]]:
    """Devuelve información de salud por índice visual sin inventar sensores."""
    tele = copy.deepcopy(telemetry) if isinstance(telemetry, dict) else {}
    devices = tele.get('_storage_devices') if isinstance(tele.get('_storage_devices'), list) else []
    records = get_storage_health() or []
    out: Dict[int, Dict[str, Any]] = {}

    for index, device in enumerate(devices):
        if not isinstance(device, dict):
            continue
        record = match_reliability_record(device, records) or {}
        physical_index = resolve_physical_disk_index(index, tele)
        nvme = query_nvme_health_log(physical_index) if physical_index is not None else {}

        direct_health = _clamp_pct(device.get('life_percent'))
        nvme_remaining = _remaining_from_wear(nvme.get('percentage_used'))
        windows_remaining = _remaining_from_wear(record.get('wear'))

        if direct_health is not None:
            health = direct_health
            health_label = f'Salud SMART  {health:.0f}%'
            health_source = 'LibreHardwareMonitor Life/Health'
            derived = False
        elif nvme_remaining is not None:
            health = nvme_remaining
            health_label = f'Salud SMART  {health:.0f}%'
            health_source = 'NVMe SMART Percentage Used · vida restante 100 - desgaste'
            derived = True
        elif windows_remaining is not None:
            health = windows_remaining
            health_label = f'Salud SMART  {health:.0f}%'
            health_source = 'Windows Storage Reliability Wear · vida restante 100 - desgaste'
            derived = True
        else:
            health = None
            status = _status_label(record.get('health_status') or record.get('operational_status'))
            health_label = f'Estado  {status}' if status else 'Salud  N/A'
            health_source = 'Windows Storage HealthStatus' if status else 'N/A'
            derived = False

        temp = _num(device.get('temperature_c'))
        if temp is None:
            temp = _num(nvme.get('temperature_c'))
        if temp is None:
            temp = _num(record.get('temperature'))

        os_inv = device.get('os_inventory') if isinstance(device.get('os_inventory'), dict) else {}
        total_gb = _num(device.get('total_space_gb'))
        if total_gb is not None and total_gb <= 0:
            total_gb = None
        if total_gb is None:
            size_bytes = _num(os_inv.get('size_bytes_os'))
            if size_bytes is not None and size_bytes > 0:
                total_gb = size_bytes / (1024 ** 3)
        if total_gb is None:
            total_gb = _num(record.get('total_gb'))

        mounts = str(record.get('mount_points') or '').strip() or None
        status = _status_label(record.get('health_status') or record.get('operational_status'))

        out[index] = {
            'index': index,
            'physical_disk_index': physical_index,
            'model': device.get('model') or device.get('name'),
            'health': health,
            'health_label': health_label,
            'health_source': health_source,
            'health_derived': derived,
            'windows_health_status': status or None,
            'wear_percent': _num(nvme.get('percentage_used')) if nvme else _num(record.get('wear')),
            'temperature_c': temp,
            'total_gb': total_gb,
            'mount_points': mounts,
            'nvme_smart_available': bool(nvme),
            'nvme_query_scope': nvme.get('query_scope') if isinstance(nvme, dict) else None,
            'nvme_percentage_used': _num(nvme.get('percentage_used')) if isinstance(nvme, dict) else None,
            'reliability_available': bool(record),
        }
    return out


__all__ = ['collect_storage_summary_health']
