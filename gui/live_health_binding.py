"""Vincula la autoridad de salud en vivo con los componentes visuales del dashboard.

V0.9.19.1w separa explícitamente condición instantánea de alertas sostenidas para
que una temperatura elevada no se presente simultáneamente como "todo óptimo".
"""
from __future__ import annotations
from core.theme_manager import color as theme_color

import types
from core.live_health import evaluate_unified_live_health

GREEN = '#1fd18b'
CYAN = '#14b8ff'
AMBER = '#f3b54a'
RED = '#ff5d6c'
MUTED = theme_color('#7f91a8')


def _cfg(widget, **kwargs):
    if widget is None:
        return
    try:
        widget.configure(**kwargs)
    except Exception:
        pass


def _color(level):
    return {
        'NORMAL': GREEN,
        'INFO': GREEN,
        'OBSERVING': CYAN,
        'ELEVATED': AMBER,
        'WARNING': AMBER,
        'CRITICAL': RED,
        'ERROR': RED,
    }.get(str(level or '').upper(), MUTED)


def _agent_state(app):
    try:
        return app.realtime_agent.get_state()
    except Exception:
        return {}


def _agent_has_sustained_alert(result):
    return str((result or {}).get('agent_overall') or '').upper() in {'WARNING', 'CRITICAL', 'ERROR'}


def _render_alert_card(app, result, color):
    """Distingue atención instantánea de una alerta ya sostenida por el agente."""
    level = str(result.get('severity') or 'UNKNOWN').upper()
    sustained = _agent_has_sustained_alert(result)
    reason = result['reasons'][0] if result.get('reasons') else ''
    tj = (result.get('tjmax_trace') or {}).get('value_c')
    if tj is not None and level in ('ELEVATED', 'WARNING', 'CRITICAL', 'ERROR'):
        reason = f'CPU a {tj:.1f} °C de TjMax'

    if sustained:
        if level in ('CRITICAL', 'ERROR'):
            title = 'Alerta crítica activa'
        else:
            title = 'Alerta sostenida activa'
        detail = reason or 'El agente confirmó una condición sostenida.'
        icon = '!'
        alert_color = color
    elif level in ('CRITICAL', 'ERROR'):
        title = 'Temperatura crítica instantánea' if ('CPU' in reason or 'GPU' in reason) else 'Condición crítica instantánea'
        detail = reason or 'Lectura crítica actual; el agente aún evalúa persistencia.'
        icon = '!'
        alert_color = RED
    elif level == 'WARNING':
        title = 'Sin alertas sostenidas'
        detail = f'Advertencia instantánea · {reason}' if reason else 'Advertencia instantánea en observación.'
        icon = '◷'
        alert_color = AMBER
    elif level == 'ELEVATED':
        title = 'Sin alertas sostenidas'
        detail = f'Atención instantánea · {reason}' if reason else 'Condición instantánea en observación.'
        icon = '◷'
        alert_color = AMBER
    elif level in ('NO_EVALUABLE', 'UNKNOWN'):
        title = 'Sin alertas sostenidas'
        detail = 'Falta evidencia para evaluar el estado actual.'
        icon = '—'
        alert_color = MUTED
    else:
        title = 'Sin alertas activas'
        detail = 'Sin condiciones sostenidas que requieran atención.'
        icon = '✓'
        alert_color = GREEN

    _cfg(getattr(app, '_alert_value', None), text=title, text_color=alert_color)
    _cfg(getattr(app, '_alert_detail', None), text=detail, text_color=MUTED)
    _cfg(getattr(app, '_alert_icon', None), text=icon, text_color=alert_color)


def _render(app, telemetry, disks):
    result = evaluate_unified_live_health(
        telemetry,
        disks,
        preliminary_score=getattr(app, 'latest_score', None),
        agent_state=_agent_state(app),
    )
    app.current_live_health = result
    app.latest_score = result['score']
    level = result['severity']
    color = _color(level)
    score_text = f"{result['score']:.1f}%" if isinstance(result.get('score'), (int, float)) else 'N/A'

    _cfg(app.lbl_health_val, text=score_text, text_color=color)
    _cfg(app.lbl_health_status, text=result['status'], text_color=color)
    _cfg(getattr(app, '_health_status', None), text=result['status'], text_color=color)
    _cfg(getattr(app, '_health_score', None), text=f'Índice técnico {score_text}', text_color=MUTED)
    _cfg(
        getattr(app, '_health_icon', None),
        text='!' if level in ('ELEVATED', 'WARNING', 'CRITICAL', 'ERROR') else '—' if level in ('NO_EVALUABLE', 'UNKNOWN') else '✓',
        text_color=color,
    )

    _render_alert_card(app, result, color)
    return result


def apply_live_health_authority(app):
    if getattr(app, '_live_health_binding_active', False):
        return
    original_apply = app.apply_telemetry_to_ui

    def wrapped_apply(self, telemetry, disks):
        original_apply(telemetry, disks)
        _render(self, telemetry, disks)

    app.apply_telemetry_to_ui = types.MethodType(wrapped_apply, app)
    original_agent_update = getattr(app, '_update_agent_ui', None)
    if callable(original_agent_update):

        def wrapped_agent_update(self):
            original_agent_update()
            telemetry = getattr(self, 'latest_telemetry', None)
            disks = getattr(self, 'latest_disks', None)
            if isinstance(telemetry, dict):
                _render(self, telemetry, disks or [])

        app._update_agent_ui = types.MethodType(wrapped_agent_update, app)
    app._live_health_binding_active = True
