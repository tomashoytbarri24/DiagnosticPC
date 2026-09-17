"""Calcula el estado técnico actual a partir de evidencia térmica y métricas certificadas."""
from __future__ import annotations
from core.version import VERSION_LABEL as VERSION
# Código refactorizado: nombres estables y documentación en español.
POLICY = 'REAL_SENSOR_SEVERITY_GUARD'

def _num(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        value = float(value)
    except Exception:
        return None
    if value != value or value in (float('inf'), float('-inf')):
        return None
    return value

def _quality_valid(meta):
    if not isinstance(meta, dict):
        return True
    q = str(meta.get('quality') or '').upper()
    return q in ('', 'VALID')

def _certified_metric_value(obj, key):
    if not isinstance(obj, dict):
        return None
    certs = obj.get('_certified_metrics')
    if isinstance(certs, dict):
        meta = certs.get(key)
        if isinstance(meta, dict) and _quality_valid(meta):
            v = _num(meta.get('value'))
            if v is not None:
                return v
    return _num(obj.get(key))

def _cpu_distance_to_tjmax(telemetry):
    if not isinstance(telemetry, dict):
        return None
    cpu = telemetry.get('_cpu')
    if isinstance(cpu, dict):
        for key in ('distance_to_tjmax_min_c', 'distance_to_tjmax_c', 'distance_to_tjmax'):
            v = _certified_metric_value(cpu, key)
            if v is not None:
                return v
    for key in ('cpu_distance_to_tjmax_min_c', 'cpu_distance_to_tjmax_c', 'distance_to_tjmax_min_c'):
        v = _num(telemetry.get(key))
        if v is not None:
            return v
    return None

def _cap_score(score, cap):
    return min(score, cap) if score is not None else None

def evaluate_current_health(telemetry, disks=None, preliminary_score=None):
    """Evalúa la operación `evaluate_current_health` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
    telemetry = telemetry if isinstance(telemetry, dict) else {}
    score = _num(preliminary_score)
    score = None if score is None else max(0.0, min(100.0, score))
    reasons = []
    severity = 'NORMAL'
    evidence_available = score is not None
    cpu_temp = _num(telemetry.get('cpu_temp'))
    gpu_temp = _num(telemetry.get('gpu_temp'))
    cpu_distance = _cpu_distance_to_tjmax(telemetry)
    if cpu_distance is not None:
        evidence_available = True
        if cpu_distance <= 5.0:
            severity = 'CRITICAL'
            reasons.append(f'CPU a {cpu_distance:.1f} °C de TjMax')
            score = _cap_score(score, 49.0)
        elif cpu_distance <= 10.0:
            severity = 'WARNING'
            reasons.append(f'CPU a {cpu_distance:.1f} °C de TjMax')
            score = _cap_score(score, 69.0)
        elif cpu_distance <= 20.0:
            severity = 'ELEVATED'
            reasons.append(f'Margen térmico CPU reducido ({cpu_distance:.1f} °C a TjMax)')
            score = _cap_score(score, 84.0)
    elif cpu_temp is not None:
        evidence_available = True
        if cpu_temp >= 95.0:
            severity = 'CRITICAL'
            reasons.append(f'CPU a {cpu_temp:.1f} °C')
            score = _cap_score(score, 49.0)
        elif cpu_temp >= 90.0:
            severity = 'WARNING'
            reasons.append(f'CPU a {cpu_temp:.1f} °C')
            score = _cap_score(score, 69.0)
        elif cpu_temp >= 80.0:
            severity = 'ELEVATED'
            reasons.append(f'CPU a {cpu_temp:.1f} °C')
            score = _cap_score(score, 84.0)
    gpu_rank = {'NORMAL': 0, 'ELEVATED': 1, 'WARNING': 2, 'CRITICAL': 3}
    gpu_severity = 'NORMAL'
    if gpu_temp is not None:
        evidence_available = True
        if gpu_temp >= 95.0:
            gpu_severity = 'CRITICAL'
            reasons.append(f'GPU a {gpu_temp:.1f} °C')
            score = _cap_score(score, 49.0)
        elif gpu_temp >= 88.0:
            gpu_severity = 'WARNING'
            reasons.append(f'GPU a {gpu_temp:.1f} °C')
            score = _cap_score(score, 69.0)
        elif gpu_temp >= 80.0:
            gpu_severity = 'ELEVATED'
            reasons.append(f'GPU a {gpu_temp:.1f} °C')
            score = _cap_score(score, 84.0)
    if gpu_rank[gpu_severity] > gpu_rank[severity]:
        severity = gpu_severity
    for disk in disks or []:
        if not isinstance(disk, dict):
            continue
        life = _num(disk.get('health'))
        if life is None:
            continue
        evidence_available = True
        if life < 50.0:
            if gpu_rank['CRITICAL'] > gpu_rank[severity]:
                severity = 'CRITICAL'
            reasons.append(f'Salud de almacenamiento {life:.0f}%')
            score = _cap_score(score, 49.0)
        elif life < 70.0:
            if gpu_rank['WARNING'] > gpu_rank[severity]:
                severity = 'WARNING'
            reasons.append(f'Salud de almacenamiento {life:.0f}%')
            score = _cap_score(score, 69.0)
    if not evidence_available:
        severity = 'NO_EVALUABLE'
    thermal_critical = bool(
        severity == 'CRITICAL' and (
            (cpu_distance is not None and cpu_distance <= 5.0)
            or (cpu_temp is not None and cpu_temp >= 95.0)
            or (gpu_temp is not None and gpu_temp >= 95.0)
        )
    )
    labels = {
        'NORMAL': 'ÓPTIMO' if score is not None and score >= 85.0 else 'ESTABLE',
        'ELEVATED': 'ATENCIÓN TÉRMICA',
        'WARNING': 'ADVERTENCIA TÉRMICA',
        'CRITICAL': 'TEMPERATURA CRÍTICA' if thermal_critical else 'ESTADO CRÍTICO',
        'NO_EVALUABLE': 'NO EVALUABLE',
    }
    return {'version': VERSION, 'policy': POLICY, 'score': round(score, 1) if score is not None else None, 'severity': severity, 'status': labels[severity], 'reasons': reasons, 'cpu_temp_c': cpu_temp, 'gpu_temp_c': gpu_temp, 'cpu_distance_to_tjmax_c': cpu_distance, 'thermal_critical': thermal_critical, 'sensor_values_unchanged': True, 'synthetic': False, 'estimated': False}
