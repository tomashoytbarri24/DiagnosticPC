"""Mantiene coherencia visual y una única cola de navegación del sidebar."""
from __future__ import annotations
from core.theme_manager import color as theme_color
from gui.render_polish import polish_widget_tree

DESIGN_ID = 'COREPULSE_INTERNAL_NAV_STATE'
TEXT = theme_color('#f4f7fb')
MUTED = theme_color('#8295ad')
ACTIVE_BG = theme_color('#0c2941')
ACTIVE_HOVER = theme_color('#123b59')
ACTIVE_BORDER = theme_color('#17658f')
ACTIVE_TEXT = '#08aef0'
INACTIVE_TEXT = theme_color('#c2ccda')
HOVER = theme_color('#0e1d2f')
ACTIONS = ('btn_benchmark', 'btn_diagnostic', 'btn_health_center', 'btn_cleanup', 'btn_tweaks', 'btn_network', 'btn_smart_alerts', 'btn_session_trends', 'btn_alert_history', '_theme_toggle_button')
CONTEXT_BUTTON = {
    'dashboard': '_btn_summary',
    'benchmark': 'btn_benchmark',
    'gaming': 'btn_health_center',
    'overlay': 'btn_health_center',
    'diagnostic': 'btn_diagnostic',
    'health_center': 'btn_health_center',
    'cleanup': 'btn_cleanup',
    'tweaks': 'btn_tweaks',
    'network': 'btn_network',
    'alerts': 'btn_smart_alerts',
    'trends': 'btn_session_trends',
    'history': 'btn_alert_history',
    'themes': '_theme_toggle_button',
}


def _cfg(widget, **kwargs):
    if widget is None:
        return
    try:
        widget.configure(**kwargs)
    except Exception:
        pass


def _is_disabled(widget):
    try:
        return str(widget.cget('state')).lower() == 'disabled'
    except Exception:
        return False


def refresh_navigation_state(app, context=None):
    context = str(context or getattr(app, '_navigation_context', None) or 'dashboard').lower()
    if context not in CONTEXT_BUTTON:
        context = 'dashboard'
    active_attr = CONTEXT_BUTTON[context]
    all_attrs = ('_btn_summary',) + ACTIONS
    for attr in all_attrs:
        button = getattr(app, attr, None)
        if button is None:
            continue
        disabled = _is_disabled(button)
        active = attr == active_attr and not disabled
        _cfg(
            button,
            fg_color=ACTIVE_BG if active else 'transparent',
            hover_color=ACTIVE_HOVER if active else HOVER,
            text_color=MUTED if disabled else (ACTIVE_TEXT if active else INACTIVE_TEXT),
            border_width=1 if active else 0,
            border_color=ACTIVE_BORDER,
            corner_radius=9,
            anchor='w',
        )
    app._navigation_context = context


def restore_dashboard_context(app):
    try:
        from gui.internal_navigation import show_dashboard
        show_dashboard(app)
    except Exception:
        refresh_navigation_state(app, context='dashboard')


def _install_debounced_commands(app):
    """Todos los botones pasan por el mismo dispatcher; los clics rápidos se coalescen."""
    try:
        from gui.internal_navigation import request_navigation, show_dashboard
    except Exception:
        return

    routes = {
        '_btn_summary': ('dashboard', lambda: show_dashboard(app)),
        'btn_benchmark': ('benchmark', lambda: app.open_benchmark()),
        'btn_diagnostic': ('diagnostic', lambda: app.start_diagnostic_session()),
        'btn_health_center': ('health_center', lambda: app.open_health_center()),
        'btn_cleanup': ('cleanup', lambda: app.run_cleanup()),
        'btn_tweaks': ('tweaks', lambda: app.open_windows_tweaks()),
        'btn_network': ('network', lambda: app.open_network_details()),
        'btn_smart_alerts': ('alerts', lambda: app.open_smart_alert_window()),
        'btn_session_trends': ('trends', lambda: app.open_session_trends_window()),
        'btn_alert_history': ('history', lambda: app.open_alert_history_window()),
        '_theme_toggle_button': ('themes', lambda: app.open_themes()),
    }
    for attr, (key, callback) in routes.items():
        button = getattr(app, attr, None)
        if button is None:
            continue
        _cfg(
            button,
            command=lambda k=key, cb=callback: request_navigation(app, k, cb),
        )
    app._navigation_dispatcher_ready = True


def apply_ui_consistency(app):
    # Puede llamarse más de una vez: siempre reata los comandos porque el
    # Dashboard profesional puede reconstruir el botón Resumen.
    _install_debounced_commands(app)
    if getattr(app, '_ui_consistency_active', False):
        refresh_navigation_state(app)
        return
    refresh_navigation_state(app, context='dashboard')
    try:
        polish_widget_tree(getattr(app, 'main_content', app))
        polish_widget_tree(getattr(app, 'sidebar', None))
    except Exception:
        pass
    app._ui_consistency_active = True
    app._corepulse_design_id = DESIGN_ID
