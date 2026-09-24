"""Vincula la autoridad de salud en vivo con los componentes visuales del dashboard.

V0.9.19.1w separa explícitamente condición instantánea de alertas sostenidas para
que una temperatura elevada no se presente simultáneamente como "todo óptimo".
"""
from __future__ import annotations
from gui.widget_updates import configure_changed
from core.theme_manager import color as theme_color

import types
from core.live_health import evaluate_unified_live_health

GREEN = '#1fd18b'
CYAN = '#14b8ff'
AMBER = '#f3b54a'
RED = '#ff5d6c'
MUTED = theme_color('#7f91a8')
BRIGHT = theme_color('#eef6ff')


def _cfg(widget, **kwargs):
    if widget is None:
        return
    try:
        configure_changed(widget, **kwargs)
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


def _pill_bg(level):
    level = str(level or '').upper()
    if level in ('CRITICAL', 'ERROR'):
        return theme_color('#3a121a')
    if level in ('WARNING', 'ELEVATED'):
        return theme_color('#33260d')
    if level in ('NO_EVALUABLE', 'UNKNOWN'):
        return theme_color('#1b2636')
    return theme_color('#0d332b')


def _health_summary_text(result, reasons):
    if not isinstance(result.get('score'), (int, float)):
        return 'Sin evidencia suficiente para evaluar la salud global'
    if not reasons or (len(reasons) == 1 and reasons[0].startswith('No se detectan señales')):
        return 'Sin revisión necesaria'
    if len(reasons) == 1:
        return '1 factor a revisar'
    return f'{len(reasons)} factores a revisar'


def _animate_health_progress(app, target, color):
    widget = getattr(app, '_health_progress', None)
    if widget is None:
        return
    try:
        target = max(0.0, min(1.0, float(target)))
    except Exception:
        target = 0.0
    try:
        current = float(widget.get())
    except Exception:
        current = target
    try:
        previous = getattr(app, '_health_progress_anim_id', None)
        if previous:
            app.after_cancel(previous)
    except Exception:
        pass
    try:
        widget.configure(progress_color=color)
    except Exception:
        pass

    steps = 7
    delta = (target - current) / float(steps)
    state = {'step': 0}

    def tick():
        state['step'] += 1
        value = target if state['step'] >= steps else current + delta * state['step']
        try:
            widget.set(max(0.0, min(1.0, value)))
        except Exception:
            return
        if state['step'] < steps:
            try:
                app._health_progress_anim_id = app.after(12, tick)
            except Exception:
                pass
        else:
            app._health_progress_anim_id = None

    tick()


def _render_health_semaphore(app, level):
    level = str(level or '').upper()
    dim_green = theme_color('#174a3a')
    dim_amber = theme_color('#5f4a1d')
    dim_red = theme_color('#5a2630')
    normal_active = level in ('NORMAL', 'INFO', 'OBSERVING')
    warning_active = level in ('ELEVATED', 'WARNING')
    critical_active = level in ('CRITICAL', 'ERROR')
    _cfg(getattr(app, '_health_semaphore_normal', None), text_color=GREEN if normal_active else dim_green)
    _cfg(getattr(app, '_health_semaphore_warning', None), text_color=AMBER if warning_active else dim_amber)
    _cfg(getattr(app, '_health_semaphore_critical', None), text_color=RED if critical_active else dim_red)


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
        reason = f'Temperatura cerca del máximo permitido · margen {tj:.1f} °C'

    if sustained:
        if level in ('CRITICAL', 'ERROR'):
            title = 'Alerta crítica activa'
        else:
            title = 'Alerta sostenida activa'
        detail = reason or 'El agente confirmó una condición sostenida.'
        icon = '!'
        alert_color = color
    elif level in ('CRITICAL', 'ERROR'):
        # Instantáneo != sostenido. Hasta que el agente confirme persistencia
        # se presenta como observación ámbar; las alertas sostenidas conservan
        # rojo y prioridad crítica.
        title = 'Temperatura alta' if ('CPU' in reason or 'GPU' in reason) else 'Condición elevada'
        detail = reason or 'Lectura alta en observación.'
        icon = '◷'
        alert_color = AMBER
    elif level == 'WARNING':
        title = 'Sin alertas sostenidas'
        detail = reason or 'Advertencia instantánea.'
        icon = '◷'
        alert_color = AMBER
    elif level == 'ELEVATED':
        title = 'Sin alertas sostenidas'
        detail = reason or 'Condición en observación.'
        icon = '◷'
        alert_color = AMBER
    elif level in ('NO_EVALUABLE', 'UNKNOWN'):
        title = 'Sin alertas sostenidas'
        detail = 'Falta evidencia para evaluar el estado actual.'
        icon = '—'
        alert_color = MUTED
    else:
        title = 'Sin alertas activas'
        detail = 'Sin condición que requiera acción.'
        icon = '✓'
        alert_color = GREEN

    _cfg(getattr(app, '_alert_value', None), text=title, text_color=alert_color)
    _cfg(getattr(app, '_alert_detail', None), text=detail, text_color=BRIGHT)
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
    reasons = [str(item).strip() for item in (result.get('reasons') or []) if str(item).strip()]
    summary = _health_summary_text(result, reasons)

    _cfg(app.lbl_health_val, text=score_text, text_color=color)
    _cfg(app.lbl_health_status, text=result['status'], text_color=color)
    _cfg(getattr(app, '_health_status', None), text=score_text, text_color=color)
    _cfg(getattr(app, '_health_score', None), text=summary, text_color=BRIGHT)
    _cfg(
        getattr(app, '_health_icon', None),
        text='!' if level in ('ELEVATED', 'WARNING', 'CRITICAL', 'ERROR') else '—' if level in ('NO_EVALUABLE', 'UNKNOWN') else '✓',
        text_color=color,
    )
    _cfg(getattr(app, '_health_pill', None), text=result['status'], text_color=color, fg_color=_pill_bg(level))
    _cfg(getattr(app, '_health_icon', None), fg_color=_pill_bg(level))
    _cfg(getattr(app, '_health_accent', None), fg_color=color)
    progress_value = max(0.0, min(1.0, float(result.get('score', 0.0)) / 100.0)) if isinstance(result.get('score'), (int, float)) else 0.0
    _animate_health_progress(app, progress_value, color)
    _render_health_semaphore(app, level)
    _cfg(getattr(app, '_health_hint', None), text='Pasa el mouse para ver detalles' if reasons else 'Estado saludable en tiempo real', text_color=BRIGHT)

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
