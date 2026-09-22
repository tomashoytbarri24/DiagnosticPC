"""Resumen de compatibilidad de sensores usando la telemetría YA recolectada.

V114 no lanza consultas nuevas de hardware desde esta capa. Consume la matriz de
capacidades y las métricas certificadas del último snapshot para explicar qué
puede leer CorePulse en este equipo bajo la política REAL_OR_NA.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List


_REASON_LABELS = {
    'SENSOR_NOT_EXPOSED': 'sensor no expuesto',
    'SENSOR_SAMPLE_OLD': 'lectura antigua',
    'NOT_PRESENT_OR_NOT_EXPOSED': 'no presente/no expuesto',
    'UNAVAILABLE': 'no disponible',
}


def _metric_meta(meta: Any) -> Dict[str, Any]:
    return meta if isinstance(meta, dict) else {}


def _source(meta: Any) -> str | None:
    item = _metric_meta(meta)
    value = item.get('source')
    if value:
        return str(value)
    sensor = item.get('sensor')
    if sensor:
        return str(sensor)
    return None


def _quality(meta: Any) -> str:
    return str(_metric_meta(meta).get('quality') or 'UNAVAILABLE').upper()


def _is_available(meta: Any) -> bool:
    item = _metric_meta(meta)
    return bool(item.get('available')) or _quality(item) == 'VALID'


def _reason(meta: Any) -> str | None:
    item = _metric_meta(meta)
    value = item.get('reason')
    if not value:
        return None
    return _REASON_LABELS.get(str(value).upper(), str(value).replace('_', ' ').lower())


def _dedupe(values: Iterable[str | None]) -> List[str]:
    out: List[str] = []
    seen = set()
    for value in values:
        text = str(value or '').strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def _group(key: str, label: str, metrics: List[tuple[str, Dict[str, Any]]], *, detail: str = '') -> Dict[str, Any]:
    total = len(metrics)
    available = sum(1 for _, meta in metrics if _is_available(meta))
    if total <= 0:
        state = 'UNAVAILABLE'
    elif available == total:
        state = 'AVAILABLE'
    elif available > 0:
        state = 'PARTIAL'
    else:
        state = 'UNAVAILABLE'
    sources = _dedupe(_source(meta) for _, meta in metrics if _is_available(meta))
    unavailable = [
        {'label': label_text, 'reason': _reason(meta) or 'sin lectura certificada'}
        for label_text, meta in metrics
        if not _is_available(meta)
    ]
    return {
        'key': key,
        'label': label,
        'state': state,
        'available': available,
        'total': total,
        'coverage_percent': (available / total * 100.0) if total else 0.0,
        'sources': sources,
        'unavailable': unavailable,
        'detail': detail,
        'metrics': [
            {
                'label': label_text,
                'available': _is_available(meta),
                'quality': _quality(meta),
                'source': _source(meta),
                'reason': _reason(meta),
            }
            for label_text, meta in metrics
        ],
    }


def build_sensor_diagnostics(snapshot: Any) -> Dict[str, Any]:
    """Devuelve una lectura compacta de sensores sin volver a consultar hardware."""
    snap = snapshot if isinstance(snapshot, dict) else {}
    matrix = snap.get('_hardware_capability_matrix')
    matrix = matrix if isinstance(matrix, dict) else {}
    top = snap.get('_metrics')
    top = top if isinstance(top, dict) else {}

    groups: List[Dict[str, Any]] = []

    cpu = matrix.get('cpu') if isinstance(matrix.get('cpu'), dict) else {}
    cpu_metrics = cpu.get('metrics') if isinstance(cpu.get('metrics'), dict) else {}
    cpu_items = [
        ('Uso', _metric_meta(top.get('cpu_usage'))),
        ('Temperatura', _metric_meta(cpu_metrics.get('package_temp_c') or top.get('cpu_temp'))),
        ('Frecuencia', _metric_meta(cpu_metrics.get('clock_avg_ghz') or top.get('cpu_ghz'))),
        ('Potencia', _metric_meta(cpu_metrics.get('package_power_w'))),
    ]
    groups.append(_group('cpu', 'CPU', cpu_items, detail=str(cpu.get('name') or snap.get('cpu_name') or 'Procesador')))

    ram_items = [('Uso de memoria', _metric_meta(top.get('ram_usage')))]
    groups.append(_group('ram', 'RAM', ram_items, detail='Memoria del sistema'))

    gpu_list = matrix.get('gpus') if isinstance(matrix.get('gpus'), list) else []
    primary_gpu = None
    wanted_name = str(snap.get('gpu_name') or '').strip().lower()
    for gpu in gpu_list:
        if not isinstance(gpu, dict):
            continue
        if wanted_name and str(gpu.get('name') or '').strip().lower() == wanted_name:
            primary_gpu = gpu
            break
        if primary_gpu is None and gpu.get('telemetry_available'):
            primary_gpu = gpu
    if primary_gpu is None and gpu_list:
        primary_gpu = next((g for g in gpu_list if isinstance(g, dict)), None)
    if isinstance(primary_gpu, dict):
        gm = primary_gpu.get('metrics') if isinstance(primary_gpu.get('metrics'), dict) else {}
        gpu_items = [
            ('Uso', _metric_meta(gm.get('usage_percent') or top.get('gpu_usage'))),
            ('Temperatura', _metric_meta(gm.get('temperature_c') or top.get('gpu_temp'))),
            ('Hotspot', _metric_meta(gm.get('hotspot_c'))),
            ('Frecuencia', _metric_meta(gm.get('core_clock_mhz'))),
            ('Potencia', _metric_meta(gm.get('power_w'))),
        ]
        groups.append(_group('gpu', 'GPU', gpu_items, detail=str(primary_gpu.get('name') or snap.get('gpu_name') or 'GPU')))

    storage_list = matrix.get('storage') if isinstance(matrix.get('storage'), list) else []
    if storage_list:
        storage_items: List[tuple[str, Dict[str, Any]]] = []
        for idx, disk in enumerate(storage_list, 1):
            if not isinstance(disk, dict):
                continue
            dm = disk.get('metrics') if isinstance(disk.get('metrics'), dict) else {}
            disk_name = str(disk.get('name') or f'Unidad {idx}')
            storage_items.extend([
                (f'{disk_name} · temperatura', _metric_meta(dm.get('temperature_c'))),
                (f'{disk_name} · vida', _metric_meta(dm.get('life_percent'))),
            ])
        groups.append(_group('storage', 'Almacenamiento', storage_items, detail=f'{len(storage_list)} unidad(es) detectada(s)'))

    battery = matrix.get('battery') if isinstance(matrix.get('battery'), dict) else {}
    if battery.get('inventory_available'):
        bm = battery.get('metrics') if isinstance(battery.get('metrics'), dict) else {}
        battery_items = [
            ('Carga', _metric_meta(bm.get('charge_percent'))),
            ('Desgaste', _metric_meta(bm.get('degradation_percent'))),
            ('Capacidad completa', _metric_meta(bm.get('full_charge_capacity_mwh'))),
            ('Voltaje', _metric_meta(bm.get('voltage_v'))),
        ]
        groups.append(_group('battery', 'Batería', battery_items, detail='Batería detectada por el sistema'))

    total = sum(int(g.get('total') or 0) for g in groups)
    available = sum(int(g.get('available') or 0) for g in groups)
    state = 'AVAILABLE' if total and available == total else 'PARTIAL' if available else 'UNAVAILABLE'
    return {
        'policy': 'REAL_OR_NA_ONLY',
        'source': 'CURRENT_TELEMETRY_SNAPSHOT',
        'groups': groups,
        'available': available,
        'total': total,
        'coverage_percent': (available / total * 100.0) if total else 0.0,
        'state': state,
        'note': 'Esta vista reutiliza el último snapshot certificado; no vuelve a consultar hardware.',
    }
