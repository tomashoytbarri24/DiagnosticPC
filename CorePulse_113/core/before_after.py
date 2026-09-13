"""Capturas Antes/Después para cuantificar cambios sin inventar causalidad."""
from __future__ import annotations

import json
import time
from pathlib import Path
from core.runtime_paths import data_path
from typing import Any, Dict

PATH = data_path('before_after.json')


def _num(v):
    try: return float(v) if v is not None else None
    except Exception: return None


def _first_num(*values):
    for value in values:
        number = _num(value)
        if number is not None:
            return number
    return None


def capture_metrics(telemetry: Dict[str, Any] | None, disks=None, battery=None, label='snapshot'):
    t = telemetry if isinstance(telemetry, dict) else {}
    cpu = t.get('_cpu') if isinstance(t.get('_cpu'), dict) else {}
    gpus = t.get('_gpus') if isinstance(t.get('_gpus'), list) else []
    gpu_detail = next((g for g in gpus if isinstance(g, dict) and (_num(g.get('temperature_c')) is not None or _num(g.get('usage_percent')) is not None)), {})
    storage = []
    for d in disks or []:
        if isinstance(d, dict):
            storage.append({'index': d.get('index'), 'model': d.get('model'), 'health': _num(d.get('health')), 'used_percent': _num(d.get('used_percent')), 'temperature_c': _num(d.get('temperature_c'))})
    return {
        'label': str(label), 'timestamp': time.time(),
        'cpu_usage': _first_num(t.get('cpu_usage'), cpu.get('total_load_percent')),
        'cpu_temp': _first_num(t.get('cpu_temp'), cpu.get('package_temp_c'), cpu.get('core_max_temp_c'), cpu.get('core_average_temp_c')),
        'cpu_ghz': _first_num(t.get('cpu_ghz'), cpu.get('clock_avg_ghz'), cpu.get('clock_max_ghz')),
        'cpu_power_w': _num(cpu.get('package_power_w')),
        'ram_usage': _num(t.get('ram_usage')), 'ram_available_gb': _num(t.get('ram_available_gb')),
        'gpu_usage': _first_num(t.get('gpu_usage'), gpu_detail.get('usage_percent')),
        'gpu_temp': _first_num(t.get('gpu_temp'), gpu_detail.get('temperature_c'), gpu_detail.get('hotspot_c')),
        'storage': storage,
        'battery_health': _num((battery or {}).get('health_percent')) if isinstance(battery, dict) else None,
        'policy': 'OBSERVED_VALUES_ONLY',
    }


def save_snapshot(snapshot, slot='before'):
    data = {}
    try:
        if PATH.exists(): data = json.loads(PATH.read_text(encoding='utf-8'))
    except Exception: data = {}
    data[str(slot)] = snapshot
    PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = PATH.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(PATH)
    return snapshot


def load_snapshots():
    try: return json.loads(PATH.read_text(encoding='utf-8')) if PATH.exists() else {}
    except Exception: return {}


def compare(before=None, after=None):
    if before is None or after is None:
        d = load_snapshots(); before = before or d.get('before'); after = after or d.get('after')
    if not isinstance(before, dict) or not isinstance(after, dict):
        return {'available': False, 'deltas': {}}
    fields = ('cpu_usage','cpu_temp','cpu_ghz','cpu_power_w','ram_usage','ram_available_gb','gpu_usage','gpu_temp','battery_health')
    deltas = {}
    for key in fields:
        a, b = _num(before.get(key)), _num(after.get(key))
        deltas[key] = {'before': a, 'after': b, 'delta': (b-a) if a is not None and b is not None else None}
    return {'available': True, 'before_ts': before.get('timestamp'), 'after_ts': after.get('timestamp'), 'deltas': deltas, 'note': 'Diferencia observada; no implica causalidad por sí sola.'}
