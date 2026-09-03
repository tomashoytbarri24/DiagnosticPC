"""Capturas Antes/Después para cuantificar cambios sin inventar causalidad."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / 'data' / 'before_after.json'


def _num(v):
    try: return float(v) if v is not None else None
    except Exception: return None


def capture_metrics(telemetry: Dict[str, Any] | None, disks=None, battery=None, label='snapshot'):
    t = telemetry if isinstance(telemetry, dict) else {}
    cpu = t.get('_cpu') if isinstance(t.get('_cpu'), dict) else {}
    storage = []
    for d in disks or []:
        if isinstance(d, dict):
            storage.append({'index': d.get('index'), 'model': d.get('model'), 'health': _num(d.get('health')), 'used_percent': _num(d.get('used_percent')), 'temperature_c': _num(d.get('temperature_c'))})
    return {
        'label': str(label), 'timestamp': time.time(),
        'cpu_usage': _num(t.get('cpu_usage')), 'cpu_temp': _num(t.get('cpu_temp')), 'cpu_ghz': _num(t.get('cpu_ghz')), 'cpu_power_w': _num(cpu.get('package_power_w')),
        'ram_usage': _num(t.get('ram_usage')), 'ram_available_gb': _num(t.get('ram_available_gb')),
        'gpu_usage': _num(t.get('gpu_usage')), 'gpu_temp': _num(t.get('gpu_temp')),
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
