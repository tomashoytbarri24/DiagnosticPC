"""Clasificación instantánea del Agente CorePulse sin promoverla a alerta sostenida."""
from __future__ import annotations
import time
from core.health_engine import evaluate_current_health


def _num(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def instant_health_from_sample(sample):
    """Evalúa una muestra real con la misma política térmica usada por el Dashboard.

    El resultado es observacional: no activa alertas rolling ni inventa persistencia.
    """
    sample = sample if isinstance(sample, dict) else {}
    telemetry = {
        'cpu_temp': sample.get('cpu_temp'),
        'gpu_temp': sample.get('gpu_temp'),
    }
    distance = sample.get('cpu_tjmax_distance')
    if _num(distance):
        telemetry['_cpu'] = {'distance_to_tjmax_min_c': float(distance)}
    try:
        result = evaluate_current_health(telemetry, [], preliminary_score=None)
    except Exception:
        result = {'severity': 'UNKNOWN', 'status': 'NO EVALUABLE', 'reasons': []}
    return {
        'severity': str(result.get('severity') or 'UNKNOWN').upper(),
        'status': str(result.get('status') or 'NO EVALUABLE'),
        'reasons': [str(x) for x in (result.get('reasons') or []) if x],
        'thermal_critical': bool(result.get('thermal_critical')),
        'timestamp': float(sample.get('timestamp') or time.time()),
        'source': 'REALTIME_AGENT_CURRENT_SAMPLE',
        'synthetic': False,
        'estimated': False,
    }


RANK = {'UNKNOWN': -1, 'NO_EVALUABLE': -1, 'NORMAL': 0, 'INFO': 0, 'OBSERVING': 0, 'ELEVATED': 1, 'WARNING': 2, 'CRITICAL': 3, 'ERROR': 3}

def _agent_level(state):
    raw = str((state or {}).get('overall') or 'UNKNOWN').upper()
    aliases = {'OK': 'NORMAL', 'OPTIMAL': 'NORMAL', 'OPTIMO': 'NORMAL', 'ÓPTIMO': 'NORMAL', 'WARN': 'WARNING', 'ADVERTENCIA': 'WARNING', 'CRITICO': 'CRITICAL', 'CRÍTICO': 'CRITICAL'}
    return aliases.get(raw, raw)

def _active_alerts(state):
    try:
        values = ((state or {}).get('alerts') or {}).get('active') or []
        return values if isinstance(values, list) else []
    except Exception:
        return []

def _primary_alert(state):
    values = _active_alerts(state)
    if not values:
        return None
    severity = {'CRITICAL': 3, 'WARNING': 2, 'INFO': 1}
    best = max(values, key=lambda item: severity.get(str((item or {}).get('level') or '').upper(), 0) if isinstance(item, dict) else -1)
    if not isinstance(best, dict):
        return None
    return str(best.get('title') or best.get('message') or '').strip() or None

def _instant_candidate(state, live_health=None):
    candidates = []
    if isinstance(state, dict) and isinstance(state.get('instant'), dict):
        candidates.append(state.get('instant'))
    if isinstance(live_health, dict):
        live_instant = live_health.get('instant') if isinstance(live_health.get('instant'), dict) else live_health
        if isinstance(live_instant, dict):
            candidates.append(live_instant)
    if not candidates:
        return {}
    return max(candidates, key=lambda item: RANK.get(str(item.get('severity') or 'UNKNOWN').upper(), -1))

def agent_display_state(state, live_health=None, *, alive=True):
    """Estado visual puro: reacción instantánea != alerta sostenida."""
    state = state if isinstance(state, dict) else {}
    sustained = _agent_level(state)
    primary = _primary_alert(state)
    instant = _instant_candidate(state, live_health)
    instant_level = str(instant.get('severity') or 'UNKNOWN').upper()
    reasons = [str(x) for x in (instant.get('reasons') or []) if x]
    instant_reason = reasons[0] if reasons else str(instant.get('status') or '').strip()
    if not alive:
        return {'status': 'INACTIVO', 'tone': 'RED', 'prefix': 'AGENTE', 'label': 'NO DISPONIBLE', 'detail': 'El agente no está ejecutándose.', 'border_level': 'ERROR'}
    if sustained in {'CRITICAL', 'ERROR'}:
        return {'status': 'REACCIONANDO', 'tone': 'RED', 'prefix': 'ALERTAS', 'label': 'CRÍTICA SOSTENIDA', 'detail': primary or 'Condición sostenida crítica.', 'border_level': 'CRITICAL'}
    if sustained == 'WARNING':
        return {'status': 'REACCIONANDO', 'tone': 'AMBER', 'prefix': 'ALERTAS', 'label': 'ADVERTENCIA SOSTENIDA', 'detail': primary or 'Condición sostenida que requiere atención.', 'border_level': 'WARNING'}
    if instant_level in {'CRITICAL', 'ERROR'}:
        detail = instant_reason or 'Condición crítica instantánea.'
        return {'status': 'REACCIONANDO', 'tone': 'RED', 'prefix': 'CONDICIÓN', 'label': 'CRÍTICA INSTANTÁNEA', 'detail': f'{detail} · confirmando persistencia', 'border_level': 'CRITICAL'}
    if instant_level == 'WARNING':
        detail = instant_reason or 'Advertencia instantánea.'
        return {'status': 'OBSERVANDO', 'tone': 'AMBER', 'prefix': 'CONDICIÓN', 'label': 'ADVERTENCIA INSTANTÁNEA', 'detail': f'{detail} · confirmando persistencia', 'border_level': 'WARNING'}
    if instant_level == 'ELEVATED':
        detail = instant_reason or 'Condición térmica elevada.'
        return {'status': 'OBSERVANDO', 'tone': 'AMBER', 'prefix': 'CONDICIÓN', 'label': 'ATENCIÓN TÉRMICA', 'detail': f'{detail} · observando evolución', 'border_level': 'WARNING'}
    if sustained in {'UNKNOWN', '', 'NONE'}:
        return {'status': 'MONITOREANDO', 'tone': 'CYAN', 'prefix': 'ALERTAS', 'label': 'EVALUANDO', 'detail': 'Acumulando evidencia del sistema...', 'border_level': 'NORMAL'}
    if sustained == 'OBSERVING':
        return {'status': 'OBSERVANDO', 'tone': 'CYAN', 'prefix': 'AGENTE', 'label': 'EVALUANDO SESIÓN', 'detail': 'Acumulando evidencia de la sesión activa...', 'border_level': 'NORMAL'}
    if sustained == 'INFO':
        return {'status': 'MONITOREANDO', 'tone': 'GREEN', 'prefix': 'ALERTAS', 'label': 'NINGUNA SOSTENIDA', 'detail': primary or 'Sin alertas sostenidas.', 'border_level': 'NORMAL'}
    return {'status': 'MONITOREANDO', 'tone': 'GREEN', 'prefix': 'ALERTAS', 'label': 'NINGUNA SOSTENIDA', 'detail': 'Sin alertas sostenidas.', 'border_level': 'NORMAL'}
