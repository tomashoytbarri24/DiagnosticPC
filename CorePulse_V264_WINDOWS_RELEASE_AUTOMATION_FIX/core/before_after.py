"""Capturas Antes/Después y sesiones de optimización para CorePulse.

V117 conserva la comparación manual histórica y añade sesiones automáticas para
acciones reales (Tweaks/Limpieza). Se guardan únicamente valores observados; N/A
se conserva cuando una métrica no existe y ningún delta implica causalidad.
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path
from core.runtime_paths import data_path
from typing import Any, Dict

import psutil

PATH = data_path('before_after.json')
HISTORY_PATH = data_path('optimization_history.json')
_LOCK = threading.RLock()
MAX_HISTORY = 60


def _num(v):
    try:
        return float(v) if v is not None else None
    except Exception:
        return None


def _first_num(*values):
    for value in values:
        number = _num(value)
        if number is not None:
            return number
    return None


def _system_context(runtime_context=None):
    runtime_context = runtime_context if isinstance(runtime_context, dict) else {}
    ctx = dict(runtime_context)
    try:
        ctx.setdefault('process_count', len(psutil.pids()))
    except Exception:
        ctx.setdefault('process_count', None)
    try:
        boot = float(psutil.boot_time())
        ctx.setdefault('boot_time_epoch', boot)
        ctx.setdefault('uptime_hours', max(0.0, (time.time() - boot) / 3600.0))
    except Exception:
        ctx.setdefault('boot_time_epoch', None)
        ctx.setdefault('uptime_hours', None)
    try:
        vm = psutil.virtual_memory()
        ctx.setdefault('ram_available_gb', float(vm.available) / (1024 ** 3))
        ctx.setdefault('ram_used_percent', float(vm.percent))
    except Exception:
        pass
    return ctx


def capture_metrics(telemetry: Dict[str, Any] | None, disks=None, battery=None, label='snapshot', runtime_context=None):
    t = telemetry if isinstance(telemetry, dict) else {}
    cpu = t.get('_cpu') if isinstance(t.get('_cpu'), dict) else {}
    gpus = t.get('_gpus') if isinstance(t.get('_gpus'), list) else []
    gpu_detail = next((g for g in gpus if isinstance(g, dict) and (_num(g.get('temperature_c')) is not None or _num(g.get('usage_percent')) is not None)), {})
    ctx = _system_context(runtime_context)
    storage = []
    for d in disks or []:
        if isinstance(d, dict):
            storage.append({
                'index': d.get('index'), 'model': d.get('model'),
                'health': _num(d.get('health')),
                'used_percent': _num(d.get('used_percent')),
                'temperature_c': _num(d.get('temperature_c')),
            })
    cpu_usage = _first_num(t.get('cpu_usage'), cpu.get('total_load_percent'))
    ram_usage = _first_num(t.get('ram_usage'), ctx.get('ram_used_percent'))
    ram_available = _first_num(t.get('ram_available_gb'), ctx.get('ram_available_gb'))
    network_latency = _first_num(
        ctx.get('network_latency_ms'), ctx.get('latency_ms'),
        t.get('network_latency_ms'), t.get('latency_ms'),
    )
    fps = _first_num(ctx.get('fps'), t.get('fps'))
    fps_low = _first_num(ctx.get('fps_1pct_low'), t.get('fps_1pct_low'))
    return {
        'label': str(label),
        'timestamp': time.time(),
        'cpu_usage': cpu_usage,
        'cpu_idle_percent': (100.0 - cpu_usage) if cpu_usage is not None else None,
        'cpu_temp': _first_num(t.get('cpu_temp'), cpu.get('package_temp_c'), cpu.get('core_max_temp_c'), cpu.get('core_average_temp_c')),
        'cpu_ghz': _first_num(t.get('cpu_ghz'), cpu.get('clock_avg_ghz'), cpu.get('clock_max_ghz')),
        'cpu_power_w': _num(cpu.get('package_power_w')),
        'ram_usage': ram_usage,
        'ram_available_gb': ram_available,
        'process_count': _num(ctx.get('process_count')),
        'boot_time_epoch': _num(ctx.get('boot_time_epoch')),
        'uptime_hours': _num(ctx.get('uptime_hours')),
        'gpu_usage': _first_num(t.get('gpu_usage'), gpu_detail.get('usage_percent')),
        'gpu_temp': _first_num(t.get('gpu_temp'), gpu_detail.get('temperature_c'), gpu_detail.get('hotspot_c')),
        'fps': fps,
        'fps_1pct_low': fps_low,
        'network_latency_ms': network_latency,
        'storage': storage,
        'battery_health': _num((battery or {}).get('health_percent')) if isinstance(battery, dict) else None,
        'system_score': _num(t.get('system_score')),
        'policy': 'OBSERVED_VALUES_ONLY',
    }


def save_snapshot(snapshot, slot='before'):
    data = {}
    try:
        if PATH.exists():
            data = json.loads(PATH.read_text(encoding='utf-8'))
    except Exception:
        data = {}
    data[str(slot)] = snapshot
    PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = PATH.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(PATH)
    return snapshot


def load_snapshots():
    try:
        return json.loads(PATH.read_text(encoding='utf-8')) if PATH.exists() else {}
    except Exception:
        return {}


def compare(before=None, after=None):
    if before is None or after is None:
        d = load_snapshots(); before = before or d.get('before'); after = after or d.get('after')
    if not isinstance(before, dict) or not isinstance(after, dict):
        return {'available': False, 'deltas': {}}
    fields = (
        'cpu_usage', 'cpu_idle_percent', 'cpu_temp', 'cpu_ghz', 'cpu_power_w',
        'ram_usage', 'ram_available_gb', 'process_count', 'gpu_usage', 'gpu_temp',
        'fps', 'fps_1pct_low', 'network_latency_ms', 'battery_health', 'system_score',
    )
    deltas = {}
    for key in fields:
        a, b = _num(before.get(key)), _num(after.get(key))
        deltas[key] = {'before': a, 'after': b, 'delta': (b-a) if a is not None and b is not None else None}
    # Discos se comparan por índice/modelo, sin inventar equivalencias.
    storage_deltas = []
    before_disks = [x for x in (before.get('storage') or []) if isinstance(x, dict)]
    after_disks = [x for x in (after.get('storage') or []) if isinstance(x, dict)]
    for a_disk in before_disks:
        match = next((x for x in after_disks if x.get('index') == a_disk.get('index') and str(x.get('model') or '') == str(a_disk.get('model') or '')), None)
        if not match:
            continue
        storage_deltas.append({
            'index': a_disk.get('index'), 'model': a_disk.get('model'),
            'health': {'before': _num(a_disk.get('health')), 'after': _num(match.get('health'))},
            'used_percent': {'before': _num(a_disk.get('used_percent')), 'after': _num(match.get('used_percent'))},
            'temperature_c': {'before': _num(a_disk.get('temperature_c')), 'after': _num(match.get('temperature_c'))},
        })
        for metric in ('health', 'used_percent', 'temperature_c'):
            pair = storage_deltas[-1][metric]
            if pair['before'] is not None and pair['after'] is not None:
                pair['delta'] = pair['after'] - pair['before']
            else:
                pair['delta'] = None
    return {
        'available': True,
        'before_ts': before.get('timestamp'),
        'after_ts': after.get('timestamp'),
        'deltas': deltas,
        'storage_deltas': storage_deltas,
        'note': 'Diferencia observada; no implica causalidad por sí sola.',
    }


def _read_history():
    try:
        raw = json.loads(HISTORY_PATH.read_text(encoding='utf-8')) if HISTORY_PATH.exists() else []
        return raw if isinstance(raw, list) else []
    except Exception:
        return []


def _write_history(rows):
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = HISTORY_PATH.with_suffix('.tmp')
    tmp.write_text(json.dumps(list(rows)[-MAX_HISTORY:], ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    tmp.replace(HISTORY_PATH)


def start_operation(action: str, telemetry=None, disks=None, battery=None, *, runtime_context=None, metadata=None):
    """Crea una sesión en memoria; se persiste al finalizar o marcar pendiente."""
    return {
        'id': uuid.uuid4().hex,
        'action': str(action or 'optimización'),
        'started_at': time.time(),
        'finished_at': None,
        'status': 'running',
        'metadata': dict(metadata or {}),
        'before': capture_metrics(telemetry, disks, battery, label='before_operation', runtime_context=runtime_context),
        'after': None,
        'comparison': None,
        'policy': 'OBSERVED_VALUES_ONLY_NO_CAUSALITY',
    }


def finish_operation(session, telemetry=None, disks=None, battery=None, *, runtime_context=None, metadata=None, status='completed', note=None):
    if not isinstance(session, dict):
        return None
    row = dict(session)
    row['finished_at'] = time.time()
    row['status'] = str(status or 'completed')
    merged = dict(row.get('metadata') or {})
    merged.update(dict(metadata or {}))
    row['metadata'] = merged
    row['after'] = capture_metrics(telemetry, disks, battery, label='after_operation', runtime_context=runtime_context)
    row['comparison'] = compare(row.get('before'), row.get('after'))
    if note:
        row['note'] = str(note)
    with _LOCK:
        history = _read_history()
        history.append(row)
        _write_history(history)
    return row


def mark_operation(session, *, status='pending', note=None, metadata=None):
    """Persiste una sesión sin forzar una medición DESPUÉS inexistente.

    Se usa cuando el efecto requiere reinicio/reinicio de Explorer o la operación
    no terminó correctamente. CorePulse no simula un resultado posterior.
    """
    if not isinstance(session, dict):
        return None
    row = dict(session)
    row['finished_at'] = time.time()
    row['status'] = str(status or 'pending')
    merged = dict(row.get('metadata') or {})
    merged.update(dict(metadata or {}))
    row['metadata'] = merged
    row['after'] = None
    row['comparison'] = {'available': False, 'deltas': {}}
    if note:
        row['note'] = str(note)
    with _LOCK:
        history = _read_history()
        history.append(row)
        _write_history(history)
    return row


def latest_operations(limit=12):
    with _LOCK:
        history = _read_history()
    history.sort(key=lambda x: float(x.get('finished_at') or x.get('started_at') or 0), reverse=True)
    return history[:max(1, int(limit))]
