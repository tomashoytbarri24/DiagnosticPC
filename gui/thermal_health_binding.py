"""Vincula el estado térmico real con los indicadores visuales del dashboard."""
from __future__ import annotations
from core.theme_manager import color as theme_color
# Código refactorizado: nombres estables y documentación en español.
import types
from core.health_engine import evaluate_current_health
GREEN = '#1fd18b'
CYAN = '#14b8ff'
AMBER = '#f3b54a'
RED = '#ff5d6c'
MUTED = theme_color('#7f91a8')

def _cfg(widget, **kwargs):
    try:
        widget.configure(**kwargs)
    except Exception:
        pass

def _color(severity):
    return {'NORMAL': GREEN, 'ELEVATED': AMBER, 'WARNING': AMBER, 'CRITICAL': RED}.get(severity, MUTED)

def apply_thermal_health_semantics(app):
    if getattr(app, '_thermal_health_guard_active', False):
        return
    original = app.apply_telemetry_to_ui

    def wrapped(self, telemetry, disks):
        original(telemetry, disks)
        result = evaluate_current_health(telemetry, disks, preliminary_score=getattr(self, 'latest_score', None))
        self.current_health = result
        self.latest_score = result['score']
        color = _color(result['severity'])
        score_text = f"{result['score']:.1f}%" if isinstance(result.get('score'), (int, float)) else 'N/A'
        _cfg(self.lbl_health_val, text=score_text, text_color=color)
        _cfg(self.lbl_health_status, text=result['status'], text_color=color)
        if hasattr(self, '_health_status'):
            _cfg(self._health_status, text=result['status'], text_color=color)
        if hasattr(self, '_health_score'):
            _cfg(self._health_score, text=f'Índice técnico {score_text}')
        if hasattr(self, '_health_icon'):
            _cfg(self._health_icon, text='!' if result['severity'] in ('ELEVATED', 'WARNING', 'CRITICAL') else '—' if result['severity'] == 'NO_EVALUABLE' else '✓', text_color=color)
        if result['severity'] in ('ELEVATED', 'WARNING', 'CRITICAL'):
            reason = result['reasons'][0] if result['reasons'] else 'Condición térmica actual'
            if hasattr(self, '_alert_value'):
                _cfg(self._alert_value, text='Atención térmica instantánea' if result['severity'] == 'ELEVATED' else 'Advertencia térmica instantánea' if result['severity'] == 'WARNING' else 'Condición térmica crítica', text_color=color)
            if hasattr(self, '_alert_detail'):
                _cfg(self._alert_detail, text=reason, text_color=MUTED)
    app.apply_telemetry_to_ui = types.MethodType(wrapped, app)
    app._thermal_health_guard_active = True
