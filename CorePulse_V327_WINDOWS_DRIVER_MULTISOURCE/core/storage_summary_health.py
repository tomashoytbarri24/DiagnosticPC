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
import json
import time
from typing import Any, Dict, Optional

from core.storage_health import get_storage_health
from core.storage_details import match_reliability_record, resolve_physical_disk_index
from core.nvme_smart_windows import query_nvme_health_log
from core.smartctl_storage import query_smartctl_health, merge_health_sources
from core.runtime_paths import cache_path

_CACHE_FILE = cache_path('storage_summary_health.json')
_CACHE_MAX_AGE_SECONDS = 24 * 60 * 60


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


def _valid_temperature(value: Any) -> Optional[float]:
    """Acepta sólo una temperatura física utilizable.

    Varios drivers/OEM rellenan sensores no soportados con 0. CorePulse no debe
    convertir ese sentinel en una lectura real de 0 °C.
    """
    temp = _num(value)
    if temp is None or temp <= 0.0 or temp > 200.0:
        return None
    return temp


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


def collect_storage_summary_health(telemetry: Dict[str, Any], *, include_slow_fallbacks: bool = True) -> Dict[int, Dict[str, Any]]:
    """Devuelve salud por disco físico usando primero APIs nativas de Windows.

    Autoridad cuantitativa:
    1) NVMe Health Log vía IOCTL de Windows (Percentage Used);
    2) Storage Reliability Counter (Wear);
    3) Life/Health real publicado por LibreHardwareMonitor;
    4) smartctl sólo como último fallback opcional.

    Nunca convierte ``Healthy``/``SMART PASSED`` en 100%.
    """
    tele = copy.deepcopy(telemetry) if isinstance(telemetry, dict) else {}
    devices = tele.get('_storage_inventory') if isinstance(tele.get('_storage_inventory'), list) else None
    if not isinstance(devices, list):
        devices = tele.get('_storage_devices') if isinstance(tele.get('_storage_devices'), list) else []
    # La lectura NVMe nativa es rápida. Storage Reliability/PowerShell se reserva
    # para el enriquecimiento posterior, para que el Resumen no espere decenas de segundos.
    records = (get_storage_health() or []) if include_slow_fallbacks else []
    out: Dict[int, Dict[str, Any]] = {}

    for index, device in enumerate(devices):
        if not isinstance(device, dict):
            continue
        os_inv = device.get('os_inventory') if isinstance(device.get('os_inventory'), dict) else {}
        record = match_reliability_record(device, records) or {}
        physical_index = resolve_physical_disk_index(index, tele)
        # V258 merge: si LHM no publicó el Win32_DiskDrive.Index, reutiliza el
        # DeviceId/DiskNumber del registro Windows ya emparejado por serial/modelo.
        # Esto permite consultar el NVMe Health Log nativo sin depender de que el
        # proveedor de sensores entregue también la identidad física del disco.
        if physical_index is None and record:
            try:
                candidate = record.get('device_id')
                physical_index = int(candidate) if candidate is not None else None
            except (TypeError, ValueError):
                physical_index = None

        try:
            nvme_native = query_nvme_health_log(physical_index) if physical_index is not None else {}
        except Exception:
            nvme_native = {}

        status = _status_label(
            record.get('health_status') or record.get('operational_status')
            or os_inv.get('health_status_os') or os_inv.get('operational_status_os')
        )
        native_used = _num(nvme_native.get('percentage_used'))
        native_remaining = _remaining_from_wear(native_used)
        windows_wear = _num(record.get('wear'))
        windows_health = _clamp_pct(record.get('health'))
        direct_health = _clamp_pct(device.get('life_percent'))
        windows_health_source = str(record.get('health_source') or '').strip()

        smartctl = {}
        smart_used = None
        smart_remaining = None
        # smartctl se reserva para el final. Sólo se ejecuta si las fuentes
        # nativas/embebidas no entregaron un porcentaje cuantitativo.
        if include_slow_fallbacks and native_remaining is None and windows_health is None and not (windows_wear is not None and windows_wear > 0) and not (direct_health is not None and direct_health > 0):
            try:
                smartctl = query_smartctl_health(physical_index) if physical_index is not None else {}
            except Exception:
                smartctl = {}
            smart_used = _num(smartctl.get('percentage_used'))
            smart_remaining = _remaining_from_wear(smart_used)

        if native_remaining is not None:
            health = native_remaining
            health_label = f'Salud  {health:.0f}%'
            health_source = 'Windows NVMe Health Log · 100 - Percentage Used'
            derived = True
            wear = native_used
            wear_source = 'Windows NVMe Health Log / Percentage Used'
        elif windows_health is not None:
            health = windows_health
            health_label = f'Salud  {health:.0f}%'
            health_source = windows_health_source or 'Windows Storage Reliability · 100 - Wear'
            derived = True
            wear = windows_wear
            wear_source = record.get('reliability_counter_path') or 'Windows Storage Reliability / Wear'
        elif windows_wear is not None and windows_wear > 0.0:
            health = _remaining_from_wear(windows_wear)
            health_label = f'Salud  {health:.0f}%'
            health_source = record.get('reliability_counter_path') or 'Windows Storage Reliability · 100 - Wear'
            derived = True
            wear = windows_wear
            wear_source = record.get('reliability_counter_path') or 'Windows Storage Reliability / Wear'
        elif direct_health is not None and direct_health > 0.0:
            health = direct_health
            health_label = f'Salud  {health:.0f}%'
            health_source = 'LibreHardwareMonitor Life/Health'
            derived = False
            wear = None
            wear_source = None
        elif smart_remaining is not None:
            health = smart_remaining
            health_label = f'Salud  {health:.0f}%'
            health_source = 'smartctl NVMe Percentage Used · fallback'
            derived = True
            wear = smart_used
            wear_source = 'smartctl / Percentage Used'
        elif direct_health == 0.0 and status in {'Crítico', 'Advertencia'}:
            health = 0.0
            health_label = 'Salud  0%'
            health_source = 'LibreHardwareMonitor Life/Health · corroborado por Windows'
            derived = False
            wear = None
            wear_source = None
        else:
            health = None
            health_label = f'Estado  {status}' if status else 'Salud  N/A'
            health_source = 'Windows Storage HealthStatus' if status else 'N/A'
            derived = False
            wear = windows_wear if windows_wear is not None else smart_used
            wear_source = None

        temp = _valid_temperature(nvme_native.get('temperature_c'))
        temp_source = 'Windows NVMe Health Log' if temp is not None else None
        if temp is None:
            temp = _valid_temperature(record.get('temperature'))
            if temp is not None:
                temp_source = 'Windows Storage Reliability'
        if temp is None:
            temp = _valid_temperature(device.get('temperature_c'))
            if temp is not None:
                temp_source = 'LibreHardwareMonitor'
        if temp is None and smartctl:
            temp = _valid_temperature(smartctl.get('temperature_c'))
            if temp is not None:
                temp_source = 'smartctl fallback'

        size_bytes = _num(os_inv.get('size_bytes_os'))
        total_gb = _num(record.get('total_gb'))
        if total_gb is None and size_bytes is not None and size_bytes > 0:
            total_gb = size_bytes / (1024 ** 3)
        if total_gb is None:
            total_gb = _num(device.get('total_space_gb'))

        mounts = (
            str(os_inv.get('mount_points') or '').strip()
            or str(record.get('mount_points') or '').strip()
            or str(device.get('mount_points') or '').strip()
            or None
        )
        volume_total = _num(os_inv.get('volume_total_gb'))
        if volume_total is None:
            volume_total = _num(record.get('volume_total_gb'))
        used_gb = _num(os_inv.get('used_space_gb'))
        if used_gb is None:
            used_gb = _num(record.get('used_gb'))
        free_gb = _num(os_inv.get('free_space_gb'))
        if free_gb is None:
            free_gb = _num(record.get('free_gb'))
        used_percent = _num(os_inv.get('used_space_percent'))
        if used_percent is None:
            used_percent = _num(record.get('used_percent'))
        if used_percent is None and volume_total and used_gb is not None:
            used_percent = (used_gb / volume_total) * 100.0

        out[index] = {
            'index': index,
            'physical_disk_index': physical_index,
            'model': device.get('model') or device.get('name') or os_inv.get('model'),
            'health': health,
            'health_label': health_label,
            'health_source': health_source,
            'health_derived': derived,
            'windows_health_status': status or None,
            'wear_percent': wear,
            'wear_source': wear_source,
            'wear_quantitative_reliable': bool(health is not None and (native_remaining is not None or windows_health is not None or (windows_wear is not None and windows_wear > 0) or direct_health not in (None, 0.0) or smart_remaining is not None)),
            'temperature_c': temp,
            'temperature_source': temp_source,
            'total_gb': total_gb,
            'volume_total_gb': volume_total,
            'used_gb': used_gb,
            'free_gb': free_gb,
            'used_percent': used_percent,
            'volume_count': int(_num(os_inv.get('volume_count')) or _num(record.get('volume_count')) or 0),
            'mount_points': mounts,
            'system_disk': bool(os_inv.get('system_disk')),
            'nvme_smart_available': bool(nvme_native),
            'smartctl_available': bool(smartctl),
            'smartctl_source': smartctl.get('source') if isinstance(smartctl, dict) else None,
            'nvme_query_scope': nvme_native.get('query_scope') if isinstance(nvme_native, dict) else None,
            'nvme_percentage_used': native_used,
            'reliability_available': bool(record),
            'reliability_counter_path': record.get('reliability_counter_path'),
        }
    return out


def save_storage_summary_health_cache(result: Dict[int, Dict[str, Any]]) -> bool:
    """Persiste sólo evidencia ya obtenida para sobrevivir reinicios de tema/UI."""
    if not isinstance(result, dict) or not result:
        return False
    usable = {}
    for key, value in result.items():
        if not isinstance(value, dict):
            continue
        if value.get('health') is None and value.get('used_gb') is None and value.get('mount_points') in (None, '', 'N/A'):
            continue
        usable[str(key)] = dict(value)
    if not usable:
        return False
    payload = {'saved_at': time.time(), 'disks': usable}
    try:
        _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        temp = _CACHE_FILE.with_suffix('.tmp')
        temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        temp.replace(_CACHE_FILE)
        return True
    except Exception:
        return False


def load_storage_summary_health_cache(max_age_seconds: float = _CACHE_MAX_AGE_SECONDS) -> Dict[int, Dict[str, Any]]:
    """Restaura evidencia reciente; nunca genera ni recalcula porcentajes."""
    try:
        raw = json.loads(_CACHE_FILE.read_text(encoding='utf-8'))
        saved_at = float(raw.get('saved_at') or 0.0)
        if saved_at <= 0 or time.time() - saved_at > float(max_age_seconds):
            return {}
        disks = raw.get('disks')
        if not isinstance(disks, dict):
            return {}
        result = {}
        for key, value in disks.items():
            if not isinstance(value, dict):
                continue
            try:
                idx = int(key)
            except (TypeError, ValueError):
                continue
            item = dict(value)
            item['cache_restored'] = True
            item['cache_saved_at'] = saved_at
            result[idx] = item
        return result
    except Exception:
        return {}


__all__ = ['collect_storage_summary_health', 'save_storage_summary_health_cache', 'load_storage_summary_health_cache']
