"""Salud real de almacenamiento en Linux.

Prioridades:
1. UDisks2 NVMe SMART por D-Bus (sesión activa, sin ejecutar CorePulse como root).
2. smartctl JSON cuando el sistema permite abrir el dispositivo.

Nunca convierte un simple SMART PASSED en 100 %. Para NVMe, la vida restante
se deriva únicamente del contador estándar ``Percentage Used`` / ``percent_used``:
``100 - porcentaje_usado``.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from typing import Any, Dict, Iterable


def _num(value: Any):
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except Exception:
        return None


def _run(args: list[str], timeout=8):
    try:
        return subprocess.run(
            args, capture_output=True, text=True, errors='replace', timeout=timeout
        )
    except Exception:
        return None


def _run_json(args: list[str], timeout=8):
    cp = _run(args, timeout=timeout)
    if cp is None:
        return None
    raw = (cp.stdout or '').strip()
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def _physical_block_devices() -> list[dict]:
    """Enumera únicamente discos físicos, excluyendo zram/loop/ram/dm."""
    data = _run_json([
        'lsblk', '--json', '--bytes', '--output',
        'NAME,PATH,TYPE,SIZE,MODEL,SERIAL,TRAN,RM,ROTA'
    ], timeout=5)
    if not isinstance(data, dict):
        return []
    out = []
    for row in data.get('blockdevices') or []:
        if not isinstance(row, dict) or str(row.get('type') or '').casefold() != 'disk':
            continue
        name = str(row.get('name') or '').strip()
        path = str(row.get('path') or '').strip() or (f'/dev/{name}' if name else '')
        low = name.casefold()
        # lsblk clasifica zram como TYPE=disk, pero no es almacenamiento físico.
        if low.startswith(('zram', 'loop', 'ram', 'fd', 'sr', 'dm-')):
            continue
        if not path or str(row.get('rm') or '').strip().casefold() in {'1', 'true', 'yes'}:
            continue
        out.append({
            'device_id': path,
            'model': str(row.get('model') or '').strip() or name or path,
            'serial': str(row.get('serial') or '').strip() or None,
            'size': _num(row.get('size')),
            'transport': str(row.get('tran') or '').strip() or None,
        })
    return out


def _remaining_life(info: dict):
    nvme = info.get('nvme_smart_health_information_log') or {}
    used = _num(nvme.get('percentage_used'))
    if used is not None and used >= 0:
        return max(0.0, min(100.0, 100.0 - used)), used, 'NVMe SMART percentage_used'
    table = ((info.get('ata_smart_attributes') or {}).get('table') or [])
    for row in table:
        if not isinstance(row, dict):
            continue
        name = str(row.get('name') or '').casefold()
        raw = row.get('raw') or {}
        raw_value = _num(raw.get('value'))
        normalized = _num(row.get('value'))
        if 'percentage used' in name and raw_value is not None:
            return max(0.0, min(100.0, 100.0 - raw_value)), raw_value, f"SMART {row.get('name')}"
        if any(token in name for token in ('remaining_lifetime', 'ssd_life_left', 'percent_lifetime_remain')) and normalized is not None:
            return max(0.0, min(100.0, normalized)), None, f"SMART {row.get('name')}"
    return None, None, None


def _udisks_drive_path(device: str) -> str | None:
    if not shutil.which('udisksctl'):
        return None
    cp = _run(['udisksctl', 'info', '-b', device], timeout=5)
    if cp is None or cp.returncode != 0:
        return None
    for line in (cp.stdout or '').splitlines():
        m = re.match(r"\s*Drive:\s*'([^']+)'", line)
        if m:
            value = m.group(1).strip()
            if value and value != '/':
                return value
    return None


def _variant_number(text: str, key: str | None = None):
    target = text or ''
    if key:
        # gdbus imprime a{sv} como 'percent_used': <byte 0x03>, etc.
        m = re.search(
            rf"['\"]{re.escape(key)}['\"]\s*:\s*<(?:(?:byte|uint16|uint32|uint64|int16|int32|int64)\s+)?(0x[0-9a-fA-F]+|-?\d+)",
            target,
        )
    else:
        m = re.search(r"<(?:(?:byte|uint16|uint32|uint64|int16|int32|int64)\s+)?(0x[0-9a-fA-F]+|-?\d+)", target)
    if not m:
        return None
    raw = m.group(1)
    try:
        return int(raw, 16) if raw.lower().startswith('0x') else int(raw)
    except Exception:
        return None


def _gdbus_call(path: str, method: str, *args: str, timeout=5):
    if not shutil.which('gdbus'):
        return None
    cp = _run([
        'gdbus', 'call', '--system', '--dest', 'org.freedesktop.UDisks2',
        '--object-path', path, '--method', method, *args,
    ], timeout=timeout)
    if cp is None or cp.returncode != 0:
        return None
    return (cp.stdout or '').strip()


def _gdbus_property(path: str, interface: str, prop: str):
    return _gdbus_call(
        path,
        'org.freedesktop.DBus.Properties.Get',
        interface,
        prop,
        timeout=4,
    )


def _udisks_nvme_health(device: str) -> Dict[str, Any]:
    """Lee SMART NVMe mediante UDisks2 2.10+ sin abrir /dev como root."""
    drive = _udisks_drive_path(device)
    if not drive:
        return {}
    iface = 'org.freedesktop.UDisks2.NVMe.Controller'

    # En una sesión de escritorio activa, UDisks2 permite refrescar SMART sin
    # contraseña. Si la distro no lo permite, seguimos usando los datos cacheados.
    _gdbus_call(drive, f'{iface}.SmartUpdate', '{}', timeout=5)
    attrs = _gdbus_call(drive, f'{iface}.SmartGetAttributes', '{}', timeout=5)
    if not attrs:
        return {}

    used = _variant_number(attrs, 'percent_used')
    spare = _variant_number(attrs, 'avail_spare')
    spare_threshold = _variant_number(attrs, 'spare_thresh')
    power_cycles = _variant_number(attrs, 'power_cycles')
    unsafe_shutdowns = _variant_number(attrs, 'unsafe_shutdowns')
    media_errors = _variant_number(attrs, 'media_errors')
    err_entries = _variant_number(attrs, 'num_err_log_entries')
    data_read = _variant_number(attrs, 'total_data_read')
    data_written = _variant_number(attrs, 'total_data_written')

    temp_raw = _gdbus_property(drive, iface, 'SmartTemperature')
    temp_k = _variant_number(temp_raw or '')
    temp_c = (float(temp_k) - 273.15) if temp_k and 200 <= temp_k <= 500 else None
    hours_raw = _gdbus_property(drive, iface, 'SmartPowerOnHours')
    power_hours = _variant_number(hours_raw or '')
    warning_raw = _gdbus_property(drive, iface, 'SmartCriticalWarning') or ''
    warnings = re.findall(r"['\"]([a-zA-Z0-9_\-]+)['\"]", warning_raw)
    warnings = [w for w in warnings if w not in {'org', 'freedesktop', 'UDisks2', 'NVMe', 'Controller'}]

    if used is None and temp_c is None and power_hours is None and spare is None:
        return {}
    health = max(0.0, min(100.0, 100.0 - float(used))) if used is not None else None
    return {
        'health': health,
        'health_source': 'UDisks2 NVMe SMART · 100 - Percentage Used' if health is not None else None,
        'health_derived': health is not None,
        'wear': float(used) if used is not None else None,
        'temperature': round(temp_c, 1) if temp_c is not None else None,
        'power_on_hours': int(power_hours) if power_hours is not None else None,
        'power_cycles': int(power_cycles) if power_cycles is not None else None,
        'available_spare_percent': float(spare) if spare is not None else None,
        'available_spare_threshold_percent': float(spare_threshold) if spare_threshold is not None else None,
        'unsafe_shutdowns': int(unsafe_shutdowns) if unsafe_shutdowns is not None else None,
        'media_errors': int(media_errors) if media_errors is not None else None,
        'error_log_entries': int(err_entries) if err_entries is not None else None,
        'data_read_bytes': int(data_read) if data_read is not None else None,
        'data_written_bytes': int(data_written) if data_written is not None else None,
        'health_status': 'Healthy' if not warnings else 'Warning',
        'operational_status': 'OK' if not warnings else 'SMART_WARNING',
        'critical_warnings': warnings,
        'source': 'UDisks2 NVMe SMART',
        'policy': 'REAL_OR_NA',
    }


def _smartctl_health(device: str) -> Dict[str, Any]:
    if not shutil.which('smartctl'):
        return {}
    info = _run_json(['smartctl', '-x', device, '-j'], timeout=10)
    if not isinstance(info, dict):
        return {}
    smart_status = (info.get('smart_status') or {}).get('passed')
    temperature = _num((info.get('temperature') or {}).get('current'))
    if temperature is None:
        temperature = _num((info.get('nvme_smart_health_information_log') or {}).get('temperature'))
    health, wear, health_source = _remaining_life(info)
    power_hours = _num((info.get('power_on_time') or {}).get('hours'))
    nvme = info.get('nvme_smart_health_information_log') or {}
    if power_hours is None:
        power_hours = _num(nvme.get('power_on_hours'))
    meaningful = any(v is not None for v in (health, wear, temperature, power_hours, smart_status))
    if not meaningful:
        return {}
    return {
        'health': health,
        'health_source': health_source,
        'health_derived': health is not None,
        'wear': wear,
        'temperature': temperature,
        'power_on_hours': int(power_hours) if power_hours is not None else None,
        'health_status': 'Healthy' if smart_status is True else 'Failed' if smart_status is False else None,
        'operational_status': 'OK' if smart_status is True else 'SMART_FAILED' if smart_status is False else None,
        'source': 'smartctl JSON',
        'policy': 'REAL_OR_NA',
    }


def _merge(primary: Dict[str, Any], fallback: Dict[str, Any]) -> Dict[str, Any]:
    if not primary:
        return dict(fallback or {})
    out = dict(primary)
    for key, value in (fallback or {}).items():
        if out.get(key) in (None, '', [], {}):
            out[key] = value
    return out


def get_linux_storage_health():
    result = []
    for disk in _physical_block_devices():
        device = disk['device_id']
        udisks = _udisks_nvme_health(device)
        # Evita abrir /dev mediante smartctl cuando UDisks2 ya entregó el SMART
        # cuantitativo que necesitamos. smartctl queda como fallback real.
        need_fallback = not udisks or udisks.get('health') is None
        smartctl = _smartctl_health(device) if need_fallback else {}
        info = _merge(udisks, smartctl)
        result.append({
            'device_id': device,
            'model': disk.get('model'),
            'friendly_name': disk.get('model'),
            'serial': disk.get('serial'),
            'health': info.get('health'),
            'health_source': info.get('health_source'),
            'health_derived': bool(info.get('health_derived')),
            'health_status': info.get('health_status'),
            'operational_status': info.get('operational_status'),
            'temperature': info.get('temperature'),
            'temperature_max': None,
            'wear': info.get('wear'),
            'power_on_hours': info.get('power_on_hours'),
            'power_cycles': info.get('power_cycles'),
            'available_spare_percent': info.get('available_spare_percent'),
            'available_spare_threshold_percent': info.get('available_spare_threshold_percent'),
            'unsafe_shutdowns': info.get('unsafe_shutdowns'),
            'media_errors': info.get('media_errors'),
            'error_log_entries': info.get('error_log_entries'),
            'source': info.get('source') or 'Linux physical inventory',
            'policy': 'REAL_OR_NA',
        })
    return result


if __name__ == '__main__':
    print(json.dumps(get_linux_storage_health(), indent=2, ensure_ascii=False))
