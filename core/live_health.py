"""Unifica el estado instantáneo y las alertas sostenidas para mostrar una sola autoridad de salud."""
from __future__ import annotations
from core.version import VERSION_LABEL as VERSION
# Código refactorizado: nombres estables y documentación en español.
from core.health_engine import evaluate_current_health
POLICY = 'UNIFIED_LIVE_HEALTH_AUTHORITY_REAL_ONLY'
RANK = {'NO_EVALUABLE': -1, 'UNKNOWN': -1, 'NORMAL': 0, 'INFO': 0, 'OBSERVING': 0, 'ELEVATED': 1, 'WARNING': 2, 'CRITICAL': 3, 'ERROR': 3}

def _num(v):
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except Exception:
        return None
    if f != f or f in (float('inf'), float('-inf')):
        return None
    return f

def _agent_level(state):
    if not isinstance(state, dict):
        return 'UNKNOWN'
    overall = str(state.get('overall') or 'UNKNOWN').upper()
    if overall in RANK:
        return overall
    active = (state.get('alerts') or {}).get('active') or []
    best = 'UNKNOWN'
    for item in active:
        if not isinstance(item, dict):
            continue
        level = str(item.get('level') or 'UNKNOWN').upper()
        if RANK.get(level, -1) > RANK.get(best, -1):
            best = level
    return best

def _active_agent_reasons(state):
    out = []
    if not isinstance(state, dict):
        return out
    active = (state.get('alerts') or {}).get('active') or []
    for item in active:
        if not isinstance(item, dict):
            continue
        title = str(item.get('title') or '').strip()
        if title and title not in out:
            out.append(title)
    return out

def _tjmax_trace(telemetry):
    trace = {'value_c': None, 'quality': None, 'source': None, 'sensor': None, 'sensor_timestamp': None, 'snapshot_timestamp': None, 'contributors': [], 'derivation': None}
    if not isinstance(telemetry, dict):
        return trace
    cpu = telemetry.get('_cpu')
    if not isinstance(cpu, dict):
        return trace
    value = _num(cpu.get('distance_to_tjmax_min_c'))
    cert = (cpu.get('_certified_metrics') or {}).get('distance_to_tjmax_min_c') or {}
    raw = (cpu.get('_metrics') or {}).get('distance_to_tjmax_min_c') or {}
    trace.update({'value_c': value, 'quality': cert.get('quality'), 'source': cert.get('source') or raw.get('source'), 'sensor': cert.get('sensor') or raw.get('sensor'), 'sensor_timestamp': cert.get('sensor_timestamp') or raw.get('sensor_timestamp'), 'snapshot_timestamp': cert.get('snapshot_timestamp') or telemetry.get('_snapshot_timestamp'), 'contributors': list(raw.get('contributors') or []), 'derivation': 'MINIMUM_OF_REAL_LHM_DISTANCE_TO_TJMAX_SENSORS' if raw.get('derived_from_real') else 'DIRECT_REAL_SENSOR'})
    return trace

def evaluate_unified_live_health(telemetry, disks=None, preliminary_score=None, agent_state=None):
    instant = evaluate_current_health(telemetry, disks, preliminary_score=preliminary_score)
    instant_level = str(instant.get('severity') or 'UNKNOWN').upper()
    agent_level = _agent_level(agent_state)
    winner = instant_level
    authority = 'INSTANT_CERTIFIED_TELEMETRY'
    if RANK.get(agent_level, -1) > RANK.get(instant_level, -1):
        winner = agent_level
        authority = 'REALTIME_AGENT_ROLLING_EVIDENCE'
    elif RANK.get(agent_level, -1) == RANK.get(instant_level, -1) and RANK.get(agent_level, -1) >= RANK['WARNING']:
        authority = 'INSTANT_AND_ROLLING_EVIDENCE'
    score = _num(instant.get('score'))
    if winner in ('CRITICAL', 'ERROR'):
        score = min(score, 49.0) if score is not None else None
        thermal_critical = bool((instant or {}).get('thermal_critical'))
        status = 'TEMPERATURA CRÍTICA' if thermal_critical else 'ESTADO CRÍTICO'
    elif winner == 'WARNING':
        score = min(score, 69.0) if score is not None else None
        status = 'ADVERTENCIA TÉRMICA' if any(('CPU' in r or 'GPU' in r for r in instant.get('reasons') or [])) else 'ADVERTENCIA'
    elif winner == 'ELEVATED':
        score = min(score, 84.0) if score is not None else None
        status = 'ATENCIÓN TÉRMICA'
    elif winner in ('NO_EVALUABLE', 'UNKNOWN'):
        status = 'NO EVALUABLE'
    elif winner == 'OBSERVING':
        status = 'EN OBSERVACIÓN'
    else:
        status = 'ÓPTIMO' if score is not None and score >= 85.0 else 'ESTABLE'
    reasons = []
    for item in (instant.get('reasons') or []) + _active_agent_reasons(agent_state):
        if item and item not in reasons:
            reasons.append(item)
    trace = _tjmax_trace(telemetry)
    return {'version': VERSION, 'policy': POLICY, 'score': round(score, 1) if score is not None else None, 'severity': winner, 'status': status, 'authority': authority, 'instant': instant, 'agent_overall': agent_level, 'reasons': reasons, 'tjmax_trace': trace, 'sensor_values_unchanged': True, 'synthetic': False, 'estimated': False, 'interpolated': False}
