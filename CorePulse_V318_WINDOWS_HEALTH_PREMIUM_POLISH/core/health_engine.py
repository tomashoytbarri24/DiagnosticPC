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


RANK = {'NORMAL': 0, 'ELEVATED': 1, 'WARNING': 2, 'CRITICAL': 3, 'NO_EVALUABLE': -1}


def _raise_severity(current, candidate):
    current = str(current or 'NORMAL').upper()
    candidate = str(candidate or 'NORMAL').upper()
    return candidate if RANK.get(candidate, -1) > RANK.get(current, -1) else current


def _append_reason(reasons, text):
    text = str(text or '').strip()
    if text and text not in reasons:
        reasons.append(text)


def _disk_label(disk, index):
    if not isinstance(disk, dict):
        return f'Disco {index + 1}'
    for key in ('model', 'name', 'friendly_name'):
        value = str(disk.get(key) or '').strip()
        if value:
            return value
    mount = str(disk.get('mount_points') or '').strip()
    return mount or f'Disco {index + 1}'


def _score_status(score, severity, *, thermal_critical=False):
    if score is None:
        return 'NO EVALUABLE'
    if str(severity or '').upper() == 'CRITICAL' and thermal_critical:
        return 'TEMPERATURA CRÍTICA'
    if score >= 90.0:
        return 'ÓPTIMO'
    if score >= 75.0:
        return 'BUEN ESTADO'
    if score >= 55.0:
        return 'ESTADO MEDIO'
    if score >= 40.0:
        return 'REQUIERE REVISIÓN'
    return 'CRÍTICO'


def evaluate_current_health(telemetry, disks=None, preliminary_score=None):
    """Evalúa la salud global real sin inventar métricas ni reemplazar sensores.

    El porcentaje parte de la puntuación preliminar calculada por CorePulse y se
    reinterpreta junto a la evidencia instantánea: temperatura CPU/GPU, presión
    de RAM, llenado del almacenamiento y salud SMART cuando está disponible.
    """
    telemetry = telemetry if isinstance(telemetry, dict) else {}
    score = _num(preliminary_score)
    if score is None:
        try:
            from core.telemetry_reliable import calculate_preliminary_score
            score = calculate_preliminary_score(
                telemetry.get('cpu_usage'),
                telemetry.get('ram_usage'),
                telemetry.get('cpu_temp'),
                telemetry.get('gpu_temp'),
                disks or [],
            )
        except Exception:
            score = None
    score = None if score is None else max(0.0, min(100.0, score))

    reasons = []
    severity = 'NORMAL'
    evidence_available = score is not None

    cpu_temp = _num(telemetry.get('cpu_temp'))
    gpu_temp = _num(telemetry.get('gpu_temp'))
    ram_usage = _num(telemetry.get('ram_usage'))
    cpu_distance = _cpu_distance_to_tjmax(telemetry)

    if cpu_distance is not None:
        evidence_available = True
        if cpu_distance <= 5.0:
            severity = _raise_severity(severity, 'CRITICAL')
            _append_reason(reasons, f'Temperatura CPU muy cerca del máximo: {cpu_distance:.1f} °C de margen')
            score = _cap_score(score, 39.0)
        elif cpu_distance <= 10.0:
            severity = _raise_severity(severity, 'WARNING')
            _append_reason(reasons, f'Temperatura CPU cerca del máximo: {cpu_distance:.1f} °C de margen')
            score = _cap_score(score, 54.0)
        elif cpu_distance <= 20.0:
            severity = _raise_severity(severity, 'ELEVATED')
            _append_reason(reasons, f'Temperatura CPU elevada: {cpu_distance:.1f} °C de margen hasta el máximo')
            score = _cap_score(score, 74.0)
    elif cpu_temp is not None:
        evidence_available = True
        if cpu_temp >= 95.0:
            severity = _raise_severity(severity, 'CRITICAL')
            _append_reason(reasons, f'CPU caliente: {cpu_temp:.1f} °C')
            score = _cap_score(score, 39.0)
        elif cpu_temp >= 90.0:
            severity = _raise_severity(severity, 'WARNING')
            _append_reason(reasons, f'CPU alta: {cpu_temp:.1f} °C')
            score = _cap_score(score, 54.0)
        elif cpu_temp >= 80.0:
            severity = _raise_severity(severity, 'ELEVATED')
            _append_reason(reasons, f'CPU elevada: {cpu_temp:.1f} °C')
            score = _cap_score(score, 74.0)

    if gpu_temp is not None:
        evidence_available = True
        if gpu_temp >= 95.0:
            severity = _raise_severity(severity, 'CRITICAL')
            _append_reason(reasons, f'GPU caliente: {gpu_temp:.1f} °C')
            score = _cap_score(score, 39.0)
        elif gpu_temp >= 88.0:
            severity = _raise_severity(severity, 'WARNING')
            _append_reason(reasons, f'GPU alta: {gpu_temp:.1f} °C')
            score = _cap_score(score, 54.0)
        elif gpu_temp >= 80.0:
            severity = _raise_severity(severity, 'ELEVATED')
            _append_reason(reasons, f'GPU elevada: {gpu_temp:.1f} °C')
            score = _cap_score(score, 74.0)

    if ram_usage is not None:
        evidence_available = True
        if ram_usage >= 95.0:
            severity = _raise_severity(severity, 'WARNING')
            _append_reason(reasons, f'RAM casi saturada: {ram_usage:.1f}% en uso')
            score = _cap_score(score, 54.0)
        elif ram_usage >= 90.0:
            severity = _raise_severity(severity, 'ELEVATED')
            _append_reason(reasons, f'RAM exigida: {ram_usage:.1f}% en uso')
            score = _cap_score(score, 69.0)
        elif ram_usage >= 85.0:
            severity = _raise_severity(severity, 'ELEVATED')
            _append_reason(reasons, f'RAM alta: {ram_usage:.1f}% en uso')
            score = _cap_score(score, 79.0)

    for index, disk in enumerate(disks or []):
        if not isinstance(disk, dict):
            continue
        label = _disk_label(disk, index)
        used = _num(disk.get('used_percent'))
        health = _num(disk.get('health'))
        if used is not None:
            evidence_available = True
            if used >= 95.0:
                severity = _raise_severity(severity, 'WARNING')
                _append_reason(reasons, f'{label} muy lleno: {used:.0f}% ocupado')
                score = _cap_score(score, 54.0)
            elif used >= 90.0:
                severity = _raise_severity(severity, 'ELEVATED')
                _append_reason(reasons, f'{label} con poco espacio: {used:.0f}% ocupado')
                score = _cap_score(score, 69.0)
            elif used >= 85.0:
                severity = _raise_severity(severity, 'ELEVATED')
                _append_reason(reasons, f'{label} cargado: {used:.0f}% ocupado')
                score = _cap_score(score, 79.0)
        if health is not None:
            evidence_available = True
            if health < 50.0:
                severity = _raise_severity(severity, 'CRITICAL')
                _append_reason(reasons, f'{label} con salud baja: {health:.0f}%')
                score = _cap_score(score, 39.0)
            elif health < 70.0:
                severity = _raise_severity(severity, 'WARNING')
                _append_reason(reasons, f'{label} con salud reducida: {health:.0f}%')
                score = _cap_score(score, 54.0)
            elif health < 85.0:
                severity = _raise_severity(severity, 'ELEVATED')
                _append_reason(reasons, f'{label} con desgaste perceptible: {health:.0f}%')
                score = _cap_score(score, 79.0)

    if not evidence_available:
        severity = 'NO_EVALUABLE'

    # Si no hubo una causa dominante, el propio porcentaje ordena el bucket
    # visual de la tarjeta de salud para que 66% se interprete como un estado
    # intermedio y no como "óptimo".
    if severity == 'NORMAL' and score is not None:
        if score < 40.0:
            severity = 'CRITICAL'
        elif score < 55.0:
            severity = 'WARNING'
        elif score < 75.0:
            severity = 'ELEVATED'

    thermal_critical = bool(
        severity == 'CRITICAL' and (
            (cpu_distance is not None and cpu_distance <= 5.0)
            or (cpu_temp is not None and cpu_temp >= 95.0)
            or (gpu_temp is not None and gpu_temp >= 95.0)
        )
    )

    status = _score_status(score, severity, thermal_critical=thermal_critical)
    if score is not None and not reasons and status in {'ÓPTIMO', 'BUEN ESTADO'}:
        _append_reason(reasons, 'No se detectan señales relevantes de RAM saturada, SSD lleno, desgaste crítico ni temperatura alta.')

    return {
        'version': VERSION,
        'policy': POLICY,
        'score': round(score, 1) if score is not None else None,
        'severity': severity,
        'status': status,
        'reasons': reasons,
        'cpu_temp_c': cpu_temp,
        'gpu_temp_c': gpu_temp,
        'ram_usage_percent': ram_usage,
        'cpu_distance_to_tjmax_c': cpu_distance,
        'thermal_critical': thermal_critical,
        'sensor_values_unchanged': True,
        'synthetic': False,
        'estimated': False,
    }
