"""Pulido visual global para CorePulse.

En modo claro CustomTkinter puede mostrar artefactos en radios grandes con borde
fino, sobre todo bajo escalado DPI fraccional. Además, toda la aplicación usa
una normalización geométrica suave para mantener una estética más profesional y
coherente entre tarjetas, badges y controles interactivos.
"""
from __future__ import annotations

import customtkinter as ctk

from core.theme_manager import is_light_theme, color as theme_color

LIGHT_CARD_RADIUS = 9
LIGHT_BUTTON_RADIUS = 7
LIGHT_BADGE_RADIUS = 7
GLOBAL_CARD_RADIUS = 12
GLOBAL_BUTTON_RADIUS = 8
GLOBAL_INPUT_RADIUS = 8
GLOBAL_BADGE_RADIUS = 8


def _safe_cget(widget, key, default=None):
    try:
        return widget.cget(key)
    except Exception:
        return default


def _safe_config(widget, **kwargs):
    try:
        widget.configure(**kwargs)
        return True
    except Exception:
        return False


def _numeric(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return float(default)


def polish_widget(widget):
    """Normaliza un widget ya creado sin invadir la lógica de negocio."""
    if widget is None:
        return

    light = is_light_theme()
    radius = _numeric(_safe_cget(widget, 'corner_radius', 0))
    border = _numeric(_safe_cget(widget, 'border_width', 0))

    if isinstance(widget, ctk.CTkFrame):
        fg = _safe_cget(widget, 'fg_color', 'transparent')
        if light and border > 0 and radius > LIGHT_CARD_RADIUS:
            _safe_config(widget, corner_radius=LIGHT_CARD_RADIUS)
        elif fg not in (None, 'transparent') and radius not in (0.0,) and radius < GLOBAL_CARD_RADIUS:
            _safe_config(widget, corner_radius=GLOBAL_CARD_RADIUS)
    elif isinstance(widget, ctk.CTkButton):
        target = LIGHT_BUTTON_RADIUS if light and radius > LIGHT_BUTTON_RADIUS else GLOBAL_BUTTON_RADIUS
        if radius < target or (light and radius > LIGHT_BUTTON_RADIUS):
            _safe_config(widget, corner_radius=target)
    elif isinstance(widget, (ctk.CTkEntry, ctk.CTkTextbox, ctk.CTkOptionMenu, ctk.CTkComboBox)):
        if radius < GLOBAL_INPUT_RADIUS:
            _safe_config(widget, corner_radius=GLOBAL_INPUT_RADIUS)
    elif isinstance(widget, ctk.CTkLabel):
        fg = _safe_cget(widget, 'fg_color', 'transparent')
        target = LIGHT_BADGE_RADIUS if light and radius > LIGHT_BADGE_RADIUS else GLOBAL_BADGE_RADIUS
        if fg not in (None, 'transparent') and (radius < target or (light and radius > LIGHT_BADGE_RADIUS)):
            _safe_config(widget, corner_radius=target)


def polish_widget_tree(root):
    """Aplica el pulido a un árbol CTk sin bloquear si un hijo desaparece."""
    if root is None:
        return
    stack = [root]
    seen = set()
    while stack:
        node = stack.pop()
        ident = id(node)
        if ident in seen:
            continue
        seen.add(ident)
        polish_widget(node)
        try:
            stack.extend(node.winfo_children())
        except Exception:
            pass


def install_hover_feedback(button, *, active=False):
    """Refuerza hover de botones CTk cuando su color era casi invisible."""
    if button is None:
        return
    normal = theme_color('#164f7d') if active else 'transparent'
    hover = theme_color('#1b5c8f') if active else theme_color('#0e1d2f')

    def on_enter(_event=None):
        _safe_config(button, fg_color=hover)

    def on_leave(_event=None):
        _safe_config(button, fg_color=normal)

    try:
        button.bind('<Enter>', on_enter, add='+')
        button.bind('<Leave>', on_leave, add='+')
    except Exception:
        pass
