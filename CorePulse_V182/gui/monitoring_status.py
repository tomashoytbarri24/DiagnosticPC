"""Separa visualmente el estado del servicio de monitoreo y el estado analítico del agente."""
from __future__ import annotations
from core.theme_manager import color as theme_color
# Código refactorizado: nombres estables y documentación en español.
DESIGN_ID = 'COREPULSE_MONITORING_AGENT_STATE'

def _safe_config(widget, **kwargs):
    if widget is None:
        return False
    try:
        widget.configure(**kwargs)
        return True
    except Exception:
        return False

def _worker_alive(app):
    agent = getattr(app, 'realtime_agent', None)
    if agent is None:
        agent = getattr(app, 'agent', None)
    if agent is None:
        return False
    for name in ('thread', '_thread', 'worker', '_worker', 'worker_thread'):
        obj = getattr(agent, name, None)
        if obj is not None and hasattr(obj, 'is_alive'):
            try:
                return bool(obj.is_alive())
            except Exception:
                pass
    for name in ('worker_alive', 'is_running', 'running'):
        value = getattr(agent, name, None)
        try:
            if callable(value):
                return bool(value())
            if value is not None:
                return bool(value)
        except Exception:
            pass
    return False

def _agent_state(app):
    agent = getattr(app, 'realtime_agent', None)
    if agent is None:
        agent = getattr(app, 'agent', None)
    if agent is None:
        return {}
    try:
        state = agent.get_state()
        return state if isinstance(state, dict) else {}
    except Exception:
        return {}

def _find_header_labels(app):
    widget = getattr(app, '_header_agent_text', None)
    return [widget] if widget is not None else []

def _render_service_badge(app):
    alive = _worker_alive(app)
    state = _agent_state(app)
    overall = str(state.get('overall') or 'UNKNOWN').upper()
    if alive and overall == 'UNKNOWN':
        title = 'Inicializando'
        subtitle = 'Preparando monitoreo'
        color = '#f5b83d'
    elif alive:
        title = 'Monitoreo activo'
        subtitle = 'Agente en ejecución'
        color = '#22d995'
    else:
        title = 'Monitoreo detenido'
        subtitle = 'Agente no disponible'
        color = '#ff5d6c'
    labels = _find_header_labels(app)
    dot = getattr(app, '_header_agent_dot', None)
    _safe_config(dot, text='●', text_color=color, font=('Segoe UI', 13, 'bold'))
    for w in labels:
        _safe_config(w, text=f'{title}\n{subtitle}', text_color=theme_color('#f4f7fb'), font=('Segoe UI', 9, 'bold'), justify='left')
    app._monitoring_service_state = {'worker_alive': alive, 'runtime_overall': overall, 'display': title}

def _install_refresh_hook(app):
    if getattr(app, '_monitoring_refresh_hook', False):
        return
    for method_name in ('_refresh_agent_status_panel', 'refresh_agent_ui', '_refresh_agent_ui', 'update_agent_ui', '_update_agent_ui', 'refresh_dashboard', '_refresh_dashboard'):
        original = getattr(app, method_name, None)
        if not callable(original):
            continue

        def wrapped(*args, __orig=original, **kwargs):
            result = __orig(*args, **kwargs)
            try:
                _render_service_badge(app)
            except Exception:
                pass
            return result
        setattr(app, method_name, wrapped)
        app._monitoring_refresh_hook = True
        app._monitoring_hooked_method = method_name
        return
    app._monitoring_refresh_hook = True
    app._monitoring_hooked_method = None

def apply_monitoring_service_agent_separation(app):
    if getattr(app, '_monitoring_status_active', False):
        return
    _install_refresh_hook(app)
    _render_service_badge(app)
    app._monitoring_status_active = True
    app._corepulse_design_id = DESIGN_ID
