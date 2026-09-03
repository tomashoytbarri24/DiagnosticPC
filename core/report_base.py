"""Utilidades de datos compartidas por el constructor PDF vigente de CorePulse.

Este módulo no renderiza páginas. Su responsabilidad es normalizar valores reales,
leer el historial local y exponer el inventario certificado al constructor en
``core.report_builder``. Mantener esta capa pequeña evita conservar generadores PDF
obsoletos en la distribución.
"""
from __future__ import annotations

import json
import math
import platform
from pathlib import Path
from typing import Any, Dict

from core.device_identity import collect_hardware_inventory
from core.telemetry_consistency import apply_source_consistency


def _num(value: Any):
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except Exception:
        return None


def _pick(obj: Any, *paths: str, default=None):
    for path in paths:
        current = obj
        ok = True
        for key in str(path).split('.'):
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                ok = False
                break
        if ok and current not in (None, ''):
            return current
    return default


def _text(value: Any, default: str = 'N/A') -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _fmt(value: Any, suffix: str = '', decimals: int = 1, default: str = 'N/A') -> str:
    number = _num(value)
    if number is None:
        return default
    return f'{number:.{decimals}f}{suffix}'


def _duration(seconds: Any) -> str:
    value = _num(seconds)
    if value is None:
        return 'N/A'
    total = max(0, int(value))
    if total < 60:
        return f'{total} s'
    minutes, remaining = divmod(total, 60)
    if minutes < 60:
        return f'{minutes} min {remaining} s'
    hours, minutes = divmod(minutes, 60)
    return f'{hours} h {minutes} min'


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding='utf-8'))
            return data if isinstance(data, dict) else {}
    except Exception:
        pass
    return {}


def _diag_status(diag: Dict[str, Any]):
    raw = str(_pick(diag, 'overall_status', 'overall', 'status', default='UNKNOWN')).upper()
    if raw in {'CRITICAL', 'CRÍTICO', 'CRITICO'}:
        return ('CRÍTICO', '#DC2626')
    if raw in {'WARNING', 'WARN', 'ADVERTENCIA'}:
        return ('ADVERTENCIA', '#D97706')
    if raw in {'NORMAL', 'OK', 'PASS', 'OPTIMAL', 'OPTIMO', 'ÓPTIMO'}:
        return ('NORMAL', '#059669')
    if raw in {'OBSERVING', 'OBSERVANDO'}:
        return ('OBSERVANDO', '#06B6D4')
    return ('NO DETERMINADO', '#64748B')


def _friendly_component(value: Any) -> str:
    raw = _text(value, 'SYSTEM')
    upper = raw.upper()
    if upper.startswith(('STORAGE:', 'SSD:', 'DISK:')):
        return 'ALMACENAMIENTO'
    if upper.startswith('GPU:'):
        return 'GPU'
    if upper.startswith('CPU'):
        return 'CPU'
    if upper.startswith(('RAM', 'MEMORY')):
        return 'RAM'
    if upper.startswith('BATTERY'):
        return 'BATERÍA'
    return raw


def _finding_level(finding: Dict[str, Any]):
    raw = str(finding.get('level') or finding.get('status') or finding.get('severity') or 'INFO').upper()
    if raw in {'CRITICAL', 'CRÍTICO', 'CRITICO'}:
        return ('CRÍTICO', '#DC2626')
    if raw in {'WARNING', 'WARN', 'ADVERTENCIA'}:
        return ('ADVERTENCIA', '#D97706')
    if raw in {'NORMAL', 'OK', 'PASS', 'OPTIMAL', 'OPTIMO', 'ÓPTIMO'}:
        return ('NORMAL', '#059669')
    if raw in {'NO_EVALUABLE', 'UNAVAILABLE', 'UNKNOWN'}:
        return ('NO EVALUABLE', '#64748B')
    return ('INFORMATIVO', '#06B6D4')


def _findings(diag: Dict[str, Any]):
    values = diag.get('findings') if isinstance(diag, dict) else None
    return [item for item in values if isinstance(item, dict)] if isinstance(values, list) else []


def _statistics(diag: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(diag, dict):
        return {}
    value = diag.get('statistics')
    return value if isinstance(value, dict) else {}


def _stat(stats: Dict[str, Any], component: str, metric: str, field: str):
    return _num(_pick(stats, f'{component}.{metric}.{field}'))


def _gpu_stat(stats: Dict[str, Any], metric: str, field: str):
    gpus = stats.get('gpus') if isinstance(stats, dict) else None
    if not isinstance(gpus, dict):
        return None
    values = []
    for gpu in gpus.values():
        if not isinstance(gpu, dict):
            continue
        value = _num(_pick(gpu, f'{metric}.{field}'))
        if value is not None:
            values.append(value)
    if not values:
        return None
    return max(values) if field == 'max' else sum(values) / len(values)


def _diagnostic_metrics(diag: Dict[str, Any]) -> Dict[str, Any]:
    stats = _statistics(diag)
    return {
        'cpu_temp_avg': _stat(stats, 'cpu', 'package_temp_c', 'avg'),
        'cpu_temp_max': _stat(stats, 'cpu', 'package_temp_c', 'max'),
        'cpu_usage_avg': _stat(stats, 'cpu', 'usage_percent', 'avg'),
        'ram_usage_avg': _stat(stats, 'ram', 'usage_percent', 'avg'),
        'ram_usage_max': _stat(stats, 'ram', 'usage_percent', 'max'),
        'gpu_temp_avg': _gpu_stat(stats, 'temperature_c', 'avg'),
        'gpu_temp_max': _gpu_stat(stats, 'temperature_c', 'max'),
        'gpu_hotspot_max': _gpu_stat(stats, 'hotspot_c', 'max'),
        'gpu_usage_max': _gpu_stat(stats, 'usage_percent', 'max'),
    }


def _current_hardware(telemetry: Dict[str, Any]) -> Dict[str, Any]:
    telemetry = telemetry if isinstance(telemetry, dict) else {}
    return {
        'cpu_name': _text(_pick(telemetry, 'cpu_name', 'cpu.name', 'cpu.model', default=platform.processor() or None)),
        'cpu_usage': _pick(telemetry, 'cpu_usage', 'cpu.usage', 'cpu.percent'),
        'cpu_temp': _pick(telemetry, 'cpu_temp', 'cpu.temperature', 'cpu.temp'),
        'cpu_ghz': _pick(telemetry, 'cpu_ghz', 'cpu.frequency_ghz', 'cpu.ghz'),
        'ram_usage': _pick(telemetry, 'ram_usage', 'ram.usage', 'memory.usage'),
        'ram_used': _pick(telemetry, 'ram_used_gb', 'ram.used_gb', 'memory.used_gb'),
        'ram_total': _pick(telemetry, 'ram_total_gb', 'ram.total_gb', 'memory.total_gb'),
        'gpu_name': _text(_pick(telemetry, 'gpu_name', 'gpu.name', 'gpu.model')),
        'gpu_usage': _pick(telemetry, 'gpu_usage', 'gpu.usage', 'gpu.percent'),
        'gpu_temp': _pick(telemetry, 'gpu_temp', 'gpu.temperature', 'gpu.temp'),
        'gpu_hotspot': _pick(telemetry, 'gpu_hotspot', 'gpu.hotspot'),
        'gpu_vram': _pick(telemetry, 'gpu_vram_gb', 'gpu.vram_total_gb'),
    }


def _sessions():
    data = _load_json(_project_root() / 'data' / 'session_trends.json')
    values = data.get('sessions')
    if not isinstance(values, list):
        return []
    sessions = [item for item in values if isinstance(item, dict)]
    sessions.sort(key=lambda item: float(item.get('ended_at') or 0), reverse=True)
    return sessions[:12]


def _profile(session: Dict[str, Any]) -> str:
    profile = str(session.get('profile') or session.get('context') or '').upper()
    if 'GAME' in profile:
        return 'JUEGO'
    if 'LEGACY' in profile:
        return 'LEGACY'
    return 'ESCRITORIO'


def _session_maxima(session: Dict[str, Any]):
    if _profile(session) == 'JUEGO':
        metrics = session.get('game_maxima')
        if isinstance(metrics, dict) and metrics:
            return (metrics, 'GAME_ACTIVE')
    metrics = session.get('maxima')
    return (metrics if isinstance(metrics, dict) else {}, 'SESIÓN COMPLETA')


def _identity_from_inventory(inventory: Dict[str, Any]) -> Dict[str, Any]:
    ident = inventory.get('identity') if isinstance(inventory, dict) else {}
    ident = ident if isinstance(ident, dict) else {}
    board = ident.get('motherboard') if isinstance(ident.get('motherboard'), dict) else {}
    bios = ident.get('bios') if isinstance(ident.get('bios'), dict) else {}
    return {
        'manufacturer': ident.get('manufacturer'),
        'model': ident.get('display_model') or ident.get('model'),
        'form_factor': ident.get('form_factor'),
        'baseboard': ' '.join(str(item) for item in (board.get('manufacturer'), board.get('model')) if item) or None,
        'bios': ' '.join(str(item) for item in (bios.get('manufacturer'), bios.get('version')) if item) or None,
    }


__all__ = [
    '_num', '_pick', '_text', '_fmt', '_duration', '_diag_status', '_friendly_component',
    '_finding_level', '_findings', '_diagnostic_metrics', '_current_hardware', '_sessions',
    '_profile', '_session_maxima', '_identity_from_inventory', 'collect_hardware_inventory',
    'apply_source_consistency',
]
