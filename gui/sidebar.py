"""Mantiene la navegación lateral limpia y coherente con el Dashboard."""
from __future__ import annotations

DESIGN_ID = 'COREPULSE_REFERENCE_SIDEBAR'
FONT = 'Segoe UI'
TEXT_LABELS = {
    '_btn_summary': 'Resumen',
    'btn_overlay': 'Overlay In-Game',
    'btn_diagnostic': 'Iniciar diagnóstico',
    'btn_health_center': 'Centro de salud',
    'btn_cleanup': 'Limpieza de sistema',
    'btn_tweaks': 'Tweaks Windows 11',
    'btn_network': 'Red avanzada',
    'btn_smart_alerts': 'Alertas y diagnóstico',
    'btn_session_trends': 'Tendencias',
    'btn_alert_history': 'Historial de alertas',
}


def _cfg(widget, **kwargs):
    if widget is None:
        return
    try:
        widget.configure(**kwargs)
    except Exception:
        pass


def apply_clean_text_sidebar(app):
    """Aplica solo texto/espaciado; no cambia las acciones de navegación."""
    if getattr(app, '_clean_sidebar_active', False):
        return
    for attr, label in TEXT_LABELS.items():
        button = getattr(app, attr, None)
        if button is None:
            continue
        _cfg(button, text=label, font=(FONT, 10, 'bold'), anchor='w', padx=13)
    app._clean_sidebar_active = True
    app._corepulse_design_id = DESIGN_ID
