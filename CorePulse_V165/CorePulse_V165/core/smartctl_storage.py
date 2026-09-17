"""Proveedor opcional smartctl para salud real de almacenamiento.

CorePulse no instala ni descarga herramientas en segundo plano. Si smartctl ya está
instalado (PATH, Smartmontools estándar) o se incluye en tools/, esta capa lo usa
como fallback para controladores que no exponen el NVMe Health Log vía IOCTL.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any, Dict, Optional


def _num(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> Optional[int]:
    number = _num(value)
    return int(number) if number is not None else None


def find_smartctl() -> Optional[str]:
    candidates = []
    path = shutil.which('smartctl') or shutil.which('smartctl.exe')
    if path:
        candidates.append(Path(path))

    root = Path(__file__).resolve().parents[1]
    candidates.extend([
        root / 'tools' / 'smartmontools' / 'smartctl.exe',
        root / 'tools' / 'smartctl' / 'smartctl.exe',
        Path(os.environ.get('PROGRAMFILES', r'C:\Program Files')) / 'smartmontools' / 'bin' / 'smartctl.exe',
        Path(os.environ.get('PROGRAMFILES(X86)', r'C:\Program Files (x86)')) / 'smartmontools' / 'bin' / 'smartctl.exe',
    ])
    for candidate in candidates:
        try:
            if candidate.is_file():
                return str(candidate)
        except OSError:
            continue
    return None


def _run_json(exe: str, target: str) -> Dict[str, Any]:
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    try:
        proc = subprocess.run(
            [exe, '-a', '-j', target],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=18,
            creationflags=flags,
        )
    except (OSError, subprocess.SubprocessError):
        return {}
    raw = (proc.stdout or '').strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def query_smartctl_health(physical_index: Optional[int]) -> Dict[str, Any]:
    """Consulta ``PhysicalDriveN`` y devuelve sólo evidencia real utilizable."""
    if physical_index is None:
        return {}
    exe = find_smartctl()
    if not exe:
        return {}

    data = _run_json(exe, rf'\\.\PhysicalDrive{int(physical_index)}')
    if not data:
        return {}

    nvme = data.get('nvme_smart_health_information_log')
    nvme = nvme if isinstance(nvme, dict) else {}
    temperature = data.get('temperature') if isinstance(data.get('temperature'), dict) else {}
    smart_status = data.get('smart_status') if isinstance(data.get('smart_status'), dict) else {}

    percentage_used = _num(nvme.get('percentage_used'))
    temp_c = _num(nvme.get('temperature'))
    if temp_c is None:
        temp_c = _num(temperature.get('current'))

    result = {
        'source': 'smartctl / smartmontools',
        'smartctl_path': exe,
        'smartctl_available': True,
        'model_name': data.get('model_name') or data.get('model_family'),
        'serial_number': data.get('serial_number'),
        'smart_passed': smart_status.get('passed') if isinstance(smart_status.get('passed'), bool) else None,
        'percentage_used': percentage_used,
        'temperature_c': temp_c,
        'available_spare_percent': _num(nvme.get('available_spare')),
        'available_spare_threshold_percent': _num(nvme.get('available_spare_threshold')),
        'power_on_hours': _int(nvme.get('power_on_hours')),
        'power_cycles': _int(nvme.get('power_cycles')),
        'unsafe_shutdowns': _int(nvme.get('unsafe_shutdowns')),
        'media_errors': _int(nvme.get('media_errors')),
        'error_log_entries': _int(nvme.get('num_err_log_entries')),
        'critical_warning': _int(nvme.get('critical_warning')),
    }
    # No devolvemos una pseudo-salud si smartctl sólo pudo identificar el disco.
    meaningful = any(result.get(key) is not None for key in (
        'percentage_used', 'temperature_c', 'smart_passed', 'available_spare_percent',
        'power_on_hours', 'media_errors', 'critical_warning',
    ))
    return result if meaningful else {}


def merge_health_sources(primary: Dict[str, Any], fallback: Dict[str, Any]) -> Dict[str, Any]:
    """Completa huecos de la fuente primaria sin sobreescribir evidencia existente."""
    a = dict(primary or {})
    b = dict(fallback or {})
    if not a:
        return b
    if not b:
        return a
    for key, value in b.items():
        if key not in a or a.get(key) is None or a.get(key) == []:
            a[key] = value
    psrc = str(primary.get('source') or '').strip()
    fsrc = str(fallback.get('source') or '').strip()
    if psrc and fsrc and fsrc not in psrc:
        a['fallback_source'] = fsrc
    return a


__all__ = ['find_smartctl', 'query_smartctl_health', 'merge_health_sources']
