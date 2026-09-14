"""Conclusión determinista y explicable del Centro de Salud.

No crea un porcentaje nuevo ni reemplaza las autoridades existentes. Resume sólo
lecturas reales ya presentes en CorePulse y explica qué evidencia llevó al estado.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable

from core.health_engine import evaluate_current_health


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


def _count_crashes(crashes: Dict[str, Any] | None, *keys: str) -> int:
    if not isinstance(crashes, dict):
        return 0
    counts = crashes.get('counts') if isinstance(crashes.get('counts'), dict) else {}
    total = 0
    for key in keys:
        try:
            total += int(counts.get(key) or 0)
        except Exception:
            pass
    return total


def build_health_intelligence(
    telemetry: Dict[str, Any] | None,
    disks: Iterable[Dict[str, Any]] | None = None,
    *,
    preliminary_score=None,
    battery: Dict[str, Any] | None = None,
    throttling: Dict[str, Any] | None = None,
    crashes: Dict[str, Any] | None = None,
    active_alerts: Iterable[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    telemetry = telemetry if isinstance(telemetry, dict) else {}
    disk_rows = [x for x in (disks or []) if isinstance(x, dict)]
    base = evaluate_current_health(telemetry, disk_rows, preliminary_score=preliminary_score)

    rank = {'NO_EVALUABLE': 0, 'NORMAL': 1, 'ATTENTION': 2, 'WARNING': 3, 'CRITICAL': 4}
    state = 'NO_EVALUABLE'
    factors: list[dict] = []
    coverage: list[str] = []

    severity = str(base.get('severity') or 'NO_EVALUABLE').upper()
    if severity == 'CRITICAL':
        state = 'CRITICAL'
    elif severity == 'WARNING':
        state = 'WARNING'
    elif severity == 'ELEVATED':
        state = 'ATTENTION'
    elif severity == 'NORMAL':
        state = 'NORMAL'

    if base.get('cpu_temp_c') is not None:
        coverage.append('CPU')
    if base.get('gpu_temp_c') is not None:
        coverage.append('GPU')
    if disk_rows:
        coverage.append('Almacenamiento')

    for reason in base.get('reasons') or []:
        factors.append({'level': severity, 'area': 'Telemetría', 'text': str(reason), 'source': 'Lectura actual'})

    throttle = throttling if isinstance(throttling, dict) else {}
    cpu_thr = throttle.get('cpu') if isinstance(throttle.get('cpu'), dict) else {}
    thr_state = str(cpu_thr.get('state') or '').upper()
    if thr_state == 'CONFIRMED':
        state = max((state, 'WARNING'), key=lambda x: rank[x])
        factors.append({'level': 'WARNING', 'area': 'CPU', 'text': 'CorePulse detectó throttling confirmado por evidencia explícita.', 'source': 'Detector térmico'})
        coverage.append('Throttling')
    elif thr_state in {'SUSPECTED', 'WATCHING'}:
        state = max((state, 'ATTENTION'), key=lambda x: rank[x])
        factors.append({'level': 'ATTENTION', 'area': 'CPU', 'text': 'Hay indicios que conviene seguir observando antes de confirmar throttling.', 'source': 'Detector térmico'})
        coverage.append('Throttling')

    batt = battery if isinstance(battery, dict) else {}
    if batt.get('present'):
        coverage.append('Batería')
        hp = _num(batt.get('health_percent'))
        if hp is not None:
            if hp < 60:
                state = max((state, 'WARNING'), key=lambda x: rank[x])
                factors.append({'level': 'WARNING', 'area': 'Batería', 'text': f'La capacidad útil reportada es {hp:.0f}% de la capacidad de diseño.', 'source': 'Salud de batería'})
            elif hp < 80:
                state = max((state, 'ATTENTION'), key=lambda x: rank[x])
                factors.append({'level': 'ATTENTION', 'area': 'Batería', 'text': f'La batería reporta {hp:.0f}% de salud; conviene vigilar su evolución.', 'source': 'Salud de batería'})

    # Sólo usamos salud de disco cuando existe porcentaje real. N/A no penaliza.
    for row in disk_rows:
        hp = _num(row.get('health'))
        if hp is None:
            continue
        name = str(row.get('name') or row.get('model') or 'Unidad')
        if hp < 60:
            state = max((state, 'WARNING'), key=lambda x: rank[x])
            factors.append({'level': 'WARNING', 'area': 'Almacenamiento', 'text': f'{name}: salud reportada {hp:.0f}%.', 'source': 'SMART/telemetría disponible'})
        elif hp < 80:
            state = max((state, 'ATTENTION'), key=lambda x: rank[x])
            factors.append({'level': 'ATTENTION', 'area': 'Almacenamiento', 'text': f'{name}: salud reportada {hp:.0f}%; conviene seguir su evolución.', 'source': 'SMART/telemetría disponible'})

    if isinstance(crashes, dict) and not crashes.get('error'):
        coverage.append('Estabilidad de Windows')
        critical_events = _count_crashes(crashes, 'whea', 'bsod_bugcheck')
        unexpected = _count_crashes(crashes, 'kernel_power', 'unexpected_shutdown')
        if critical_events > 0:
            state = max((state, 'WARNING'), key=lambda x: rank[x])
            factors.append({'level': 'WARNING', 'area': 'Windows', 'text': f'El análisis reciente encontró {critical_events} evento(s) crítico(s) de hardware/bugcheck.', 'source': 'Registro de eventos'})
        elif unexpected > 0:
            state = max((state, 'ATTENTION'), key=lambda x: rank[x])
            factors.append({'level': 'ATTENTION', 'area': 'Windows', 'text': f'Windows registró {unexpected} apagado(s) o reinicio(s) inesperado(s) en el período analizado.', 'source': 'Registro de eventos'})

    alerts = [x for x in (active_alerts or []) if isinstance(x, dict)]
    if alerts:
        coverage.append('Alertas activas')
        critical = any(str(x.get('level') or '').upper() == 'CRITICAL' for x in alerts)
        warning = any(str(x.get('level') or '').upper() in {'WARNING', 'WARN'} for x in alerts)
        if critical:
            state = 'CRITICAL'
        elif warning:
            state = max((state, 'WARNING'), key=lambda x: rank[x])

    coverage = list(dict.fromkeys(coverage))
    labels = {
        'CRITICAL': ('Requiere atención inmediata', 'Hay evidencia actual que justifica revisar el equipo antes de continuar con cargas exigentes.'),
        'WARNING': ('Requiere atención', 'Se detectaron condiciones reales que conviene revisar. CorePulse muestra abajo la evidencia disponible.'),
        'ATTENTION': ('Conviene vigilar', 'El equipo funciona, pero existen señales que merece la pena seguir observando.'),
        'NORMAL': ('Equipo estable', 'Con los datos actualmente disponibles no se detectan condiciones que requieran intervención.'),
        'NO_EVALUABLE': ('Evidencia insuficiente', 'CorePulse todavía no dispone de lecturas suficientes para emitir una conclusión general.'),
    }
    title, summary = labels[state]

    if state == 'NORMAL' and not factors:
        factors.append({'level': 'NORMAL', 'area': 'Sistema', 'text': 'No se detectaron advertencias con las fuentes disponibles en esta sesión.', 'source': 'Resumen determinista'})

    return {
        'state': state,
        'title': title,
        'summary': summary,
        'factors': factors[:8],
        'coverage': coverage,
        'coverage_count': len(coverage),
        'score': base.get('score'),
        'policy': 'EXPLAINABLE_REAL_DATA_ONLY_NO_SYNTHETIC_SCORE',
        'synthetic': False,
    }


__all__ = ['build_health_intelligence']
