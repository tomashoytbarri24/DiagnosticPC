"""Calcula tamaños de ventana compatibles con distintas resoluciones de monitor."""
from __future__ import annotations
from core.theme_manager import color as theme_color
# Código refactorizado: nombres estables y documentación en español.
import json
from pathlib import Path
import tkinter as tk
import customtkinter as ctk
from core.version import VERSION_LABEL
VERSION = VERSION_LABEL
DESIGN_ID = 'COREPULSE_MONITOR_AWARE_AUTO_GEOMETRY'
PREFERRED_W = 1420
PREFERRED_H = 780
MIN_W = 1120
MIN_H = 680
SCREEN_MARGIN_X = 40
SCREEN_MARGIN_Y = 64
AUTO_MAX_W = 1720
AUTO_MAX_H = 960
PRESETS = {'Automático': None, 'Compacto': (1240, 720), 'Recomendado': (1420, 780), 'Amplio': (1560, 860)}
LEGACY_PRESET_SIZES = {(1280, 740): ('Automático', None, None), (1400, 780): ('Automático', None, None), (1500, 830): ('Automático', None, None), (1280, 800): ('Automático', None, None), (1400, 850): ('Automático', None, None), (1500, 900): ('Automático', None, None)}
BG = theme_color('#0b1422')
CARD = theme_color('#0f1c2d')
BORDER = theme_color('#20344c')
TEXT = theme_color('#f4f7fb')
TEXT_2 = theme_color('#aebdd0')
MUTED = theme_color('#73869e')
BLUE = theme_color('#2f80ed')
GREEN = '#39d98a'

def _settings_path():
    return Path(__file__).resolve().parents[1] / 'data' / 'window_preferences.json'

def _load_preferences():
    defaults = {'preset': 'Automático', 'width': PREFERRED_W, 'height': PREFERRED_H, 'remember_last_size': True}
    try:
        path = _settings_path()
        if path.exists():
            raw = json.loads(path.read_text(encoding='utf-8'))
            if isinstance(raw, dict):
                defaults.update(raw)
                try:
                    legacy_key = (int(raw.get('width', 0)), int(raw.get('height', 0)))
                    migrated = LEGACY_PRESET_SIZES.get(legacy_key)
                    if migrated is not None:
                        name, width, height = migrated
                        defaults['preset'] = name
                        if width is not None:
                            defaults['width'] = width
                        if height is not None:
                            defaults['height'] = height
                except Exception:
                    pass
    except Exception:
        pass
    return defaults

def _save_preferences(data):
    try:
        path = _settings_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
        return True
    except Exception:
        return False

def _screen_bounds(app):
    try:
        return (max(640, int(app.winfo_screenwidth())), max(480, int(app.winfo_screenheight())))
    except Exception:
        return (1920, 1080)

def _automatic_size(app):
    """Gestiona la operación `automatic_size` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
    sw, sh = _screen_bounds(app)
    usable_w = max(MIN_W, sw - SCREEN_MARGIN_X)
    usable_h = max(MIN_H, sh - SCREEN_MARGIN_Y)
    if sw <= 1366 or sh <= 768:
        width_ratio, height_ratio = (0.94, 0.9)
    elif sw <= 1600 or sh <= 900:
        width_ratio, height_ratio = (0.9, 0.88)
    elif sw <= 1920 or sh <= 1080:
        width_ratio, height_ratio = (0.84, 0.84)
    else:
        width_ratio, height_ratio = (0.78, 0.8)
    width = min(AUTO_MAX_W, int(usable_w * width_ratio))
    height = min(AUTO_MAX_H, int(usable_h * height_ratio))
    width = max(MIN_W, width)
    height = max(MIN_H, height)
    return _fit_size(app, width, height)

def _fit_size(app, width, height):
    sw, sh = _screen_bounds(app)
    max_w = max(1000, sw - SCREEN_MARGIN_X)
    max_h = max(720, sh - SCREEN_MARGIN_Y)
    width = min(int(width), max_w)
    height = min(int(height), max_h)
    width = max(min(MIN_W, max_w), width)
    height = max(min(MIN_H, max_h), height)
    return (width, height)

def _center_geometry(app, width, height):
    sw, sh = _screen_bounds(app)
    x = max(0, (sw - width) // 2)
    y = max(0, (sh - height) // 2)
    return f'{width}x{height}+{x}+{y}'

def apply_window_size(app, width, height, persist=False, preset=None):
    """Aplica la operación `apply_window_size` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
    if getattr(app, 'is_fullscreen', False):
        return False
    width, height = _fit_size(app, width, height)
    try:
        app.state('normal')
    except Exception:
        pass
    try:
        app.minsize(min(MIN_W, width), min(MIN_H, height))
        app.geometry(_center_geometry(app, width, height))
    except Exception:
        return False
    if persist:
        prefs = _load_preferences()
        prefs.update({'width': width, 'height': height, 'preset': preset or 'Personalizado'})
        _save_preferences(prefs)
    return True

def apply_preferred_launch_geometry(app):
    if getattr(app, '_launch_geometry_applied', False):
        return
    app._launch_geometry_applied = True
    prefs = _load_preferences()
    preset = str(prefs.get('preset', 'Automático'))
    if preset == 'Automático':
        width, height = _automatic_size(app)
    else:
        try:
            width = int(prefs.get('width', PREFERRED_W))
            height = int(prefs.get('height', PREFERRED_H))
        except Exception:
            width, height = (PREFERRED_W, PREFERRED_H)
    apply_window_size(app, width, height, persist=False)
    _install_settings_entry(app)

def _install_settings_entry(app):
    """Mantiene el selector de tamaño disponible sin ocupar espacio en el Dashboard.

    La referencia visual aprobada no incluye un botón "Tamaño" en el encabezado.
    Para no perder la función, se conserva mediante Ctrl+Shift+S.
    """
    if getattr(app, '_size_shortcut_installed', False):
        return
    try:
        app.bind('<Control-Shift-s>', lambda event: show_window_size_dialog(app), add=True)
        app.bind('<Control-Shift-S>', lambda event: show_window_size_dialog(app), add=True)
    except Exception:
        pass
    app._size_button = None
    app._size_shortcut_installed = True


def show_window_size_dialog(app):
    existing = getattr(app, '_size_dialog', None)
    try:
        if existing is not None and existing.winfo_exists():
            existing.lift()
            existing.focus_force()
            return
    except Exception:
        pass
    win = ctk.CTkToplevel(app)
    app._size_dialog = win
    win.title('CorePulse · Tamaño de ventana')
    win.geometry('520x430')
    win.resizable(False, False)
    win.configure(fg_color=BG)
    try:
        win.transient(app)
        win.update_idletasks()
        sw, sh = _screen_bounds(app)
        win.geometry(f'520x430+{max(0, (sw - 520) // 2)}+{max(0, (sh - 430) // 2)}')
    except Exception:
        pass
    outer = ctk.CTkFrame(win, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=13)
    outer.pack(fill='both', expand=True, padx=14, pady=14)
    ctk.CTkLabel(outer, text='Tamaño de la aplicación', font=('Segoe UI', 19, 'bold'), text_color=TEXT).pack(anchor='w', padx=18, pady=(17, 3))
    ctk.CTkLabel(outer, text='CorePulse cambia únicamente la geometría. El Dashboard adapta su densidad con una sola autoridad responsive.', font=('Segoe UI', 9), text_color=TEXT_2, wraplength=455, justify='left').pack(anchor='w', padx=18, pady=(0, 14))
    prefs = _load_preferences()
    selected = tk.StringVar(value=str(prefs.get('preset', 'Automático')))
    preset_frame = ctk.CTkFrame(outer, fg_color=theme_color('#0c1726'), corner_radius=10)
    preset_frame.pack(fill='x', padx=18, pady=(0, 12))
    preset_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)
    buttons = {}

    def refresh_buttons():
        current = selected.get()
        for name, btn in buttons.items():
            active = name == current
            btn.configure(fg_color=BLUE if active else theme_color('#14243a'), border_color=theme_color('#5aa0ff') if active else theme_color('#263d58'), text_color='#ffffff' if active else TEXT_2)
    for col, (name, dims) in enumerate(PRESETS.items()):
        if dims is None:
            label = 'Automático\nCentrado'
        else:
            w, h = dims
            label = f'{name}\n{w} × {h}'
        btn = ctk.CTkButton(preset_frame, text=label, height=66, corner_radius=8, fg_color=theme_color('#14243a'), hover_color=theme_color('#1c3451'), border_width=1, border_color=theme_color('#263d58'), text_color=TEXT_2, font=('Segoe UI', 9, 'bold'), command=lambda n=name: (selected.set(n), refresh_buttons()))
        btn.grid(row=0, column=col, sticky='ew', padx=5, pady=7)
        buttons[name] = btn
    refresh_buttons()
    ctk.CTkLabel(outer, text='Automático abre CorePulse centrado, con proporción tipo Steam. F11 sigue siendo fullscreen real.', font=('Segoe UI', 8), text_color=MUTED, wraplength=455, justify='left').pack(anchor='w', padx=18, pady=(0, 10))
    remember_var = tk.BooleanVar(value=bool(prefs.get('remember_last_size', True)))
    ctk.CTkCheckBox(outer, text='Recordar este tamaño para el próximo inicio', variable=remember_var, font=('Segoe UI', 9), text_color=TEXT_2, fg_color=BLUE, hover_color=theme_color('#3b8df2')).pack(anchor='w', padx=18, pady=(0, 15))
    actions = ctk.CTkFrame(outer, fg_color='transparent')
    actions.pack(fill='x', padx=18, pady=(0, 16))
    actions.grid_columnconfigure((0, 1), weight=1)

    def close_dialog():
        try:
            win.destroy()
        finally:
            app._size_dialog = None

    def apply_selected():
        name = selected.get()
        dims = PRESETS.get(name)
        if name == 'Automático' or dims is None:
            width, height = _automatic_size(app)
        else:
            width, height = dims
        ok = apply_window_size(app, width, height, persist=False)
        if ok:
            if remember_var.get():
                fitted_w, fitted_h = _fit_size(app, width, height)
                _save_preferences({'preset': name, 'width': fitted_w, 'height': fitted_h, 'remember_last_size': True})
            else:
                _save_preferences({'preset': 'Automático', 'width': PREFERRED_W, 'height': PREFERRED_H, 'remember_last_size': False})
        close_dialog()
    ctk.CTkButton(actions, text='Cancelar', height=34, fg_color=theme_color('#16263a'), hover_color=theme_color(theme_color('#203650')), border_width=1, border_color=theme_color('#29435f'), text_color=TEXT, command=close_dialog).grid(row=0, column=0, sticky='ew', padx=(0, 5))
    ctk.CTkButton(actions, text='Aplicar tamaño', height=34, fg_color=BLUE, hover_color=theme_color('#3b8df2'), text_color='#ffffff', font=('Segoe UI', 9, 'bold'), command=apply_selected).grid(row=0, column=1, sticky='ew', padx=(5, 0))
