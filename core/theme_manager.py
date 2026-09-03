"""Autoridad única para el tema visual de CorePulse.

CorePulse mantiene una sola build y selecciona la paleta al iniciar. El cambio de
modo se persiste y reinicia únicamente la capa UI para evitar mezclar colores o
widgets creados bajo temas distintos dentro de una misma sesión de Tk.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

DARK = 'dark'
LIGHT = 'light'
_THEME_FILE = Path(__file__).resolve().parents[1] / 'data' / 'ui_theme.json'
_COLOR_MAP = {
    # Light Comfort: evita blancos puros. El fondo general es un gris azulado
    # suave y las tarjetas quedan un nivel por encima, con bordes nítidos.
    '#06111f': '#e1e6ec',  # app background
    '#071522': '#e9edf2',  # sidebar
    '#08111f': '#e1e6ec',
    '#0a1422': '#e9edf2',  # inner surface
    '#0a1524': '#e9edf2',
    '#0b0f19': '#e1e6ec',
    '#0b1422': '#e1e6ec',
    '#0b1524': '#e9edf2',
    '#0b1626': '#e9edf2',
    '#0b1726': '#f2f4f7',  # primary card
    '#0c1726': '#e9edf2',
    '#0d1322': '#f2f4f7',
    '#0d1828': '#f2f4f7',
    '#0d2130': '#e5ebf1',
    '#0d2942': '#e3edf7',
    '#0d2b45': '#dfeaf5',
    '#0d332b': '#e1eee8',
    '#0d5c45': '#dceee6',
    '#0d8fc7': '#0b78ad',
    '#0e1726': '#e9edf2',
    '#0e1d2f': '#d9e3ec',  # navegación hover: feedback visible
    '#0f172a': '#d2dae3',  # tracks
    '#0f1c2d': '#e8edf2',
    '#0f2135': '#e3e9ef',
    '#0f2437': '#e3e9ef',
    '#101d2e': '#f2f4f7',
    '#101d2f': '#e9edf2',
    '#102235': '#deebe5',
    '#10283a': '#e4eaf0',
    '#102840': '#d4e0eb',  # hover de controles secundarios
    '#102943': '#b4c0cb',  # borde suave pero definido
    '#111827': '#e9edf2',
    '#11765a': '#cce9dc',
    '#12243a': '#e3e9ef',
    '#123e5c': '#dfe8f1',
    '#124f80': '#0b6fae',
    '#13253a': '#e3e9ef',
    '#132741': '#d2dae3',  # dashboard tracks
    '#14243a': '#e3e9ef',
    '#14253b': '#e3e9ef',
    '#14263c': '#e3e9ef',
    '#151c2c': '#f2f4f7',
    '#15243a': '#d2dae3',
    '#152750': '#e8e2f3',
    '#152a41': '#e4eaf0',
    '#16263a': '#e3e9ef',
    '#163047': '#e3e9ef',
    '#164f7d': '#cbdff0',
    '#1687ea': '#156fbd',
    '#17263a': '#e3e9ef',
    '#172a42': '#c3ccd6',
    '#172b43': '#c3ccd6',
    '#17314c': '#b5c0cc',
    '#17314d': '#aab8c5',  # borde principal más nítido
    '#173550': '#c1cad4',
    '#174e72': '#d6e4f0',
    '#178967': '#b9dfcf',
    '#182a40': '#e3e9ef',
    '#19324e': '#c1cad4',
    '#1b3048': '#aab8c5',  # borde de detalle más nítido
    '#1b5c8f': '#bcd4e8',
    '#1c3451': '#bdc8d3',
    '#1d3350': '#bcc6d1',
    '#1d5278': '#9fbad0',
    '#1e3a5f': '#e3edf7',
    '#1f2a3d': '#c1cad4',
    '#202d44': '#bcc6d1',
    '#20344c': '#b5c0cc',
    '#203650': '#b5c0cc',
    '#214765': '#c6d7e5',
    '#232f48': '#bcc6d1',
    '#26344f': '#b5c0cc',
    '#26354d': '#b5c0cc',
    '#263d58': '#b9c5d1',
    '#284f7a': '#d5e4f2',
    '#29435f': '#b6c3cf',
    '#2b1d26': '#f3e5e7',
    '#2b668f': '#b9d1e3',
    '#2f80ed': '#156fbd',
    '#31516d': '#98a8b8',
    '#334155': '#c5ced8',  # chart grid
    '#334867': '#b8c4cf',
    '#3b8df2': '#156fbd',
    '#412530': '#efdadd',
    '#416887': '#8598aa',
    '#475569': '#667589',
    '#4d2530': '#f0e1e3',
    '#5a2630': '#efe0e2',
    '#5aa0ff': '#267bc1',
    '#5f7189': '#647286',
    '#66788f': '#647286',
    '#693343': '#e8c5ca',
    '#72849b': '#647286',
    '#73869e': '#647286',
    '#75d2f7': '#0873ad',
    '#7f91a8': '#647286',
    '#8295ad': '#647286',
    '#94a3b8': '#647286',
    '#9da9b9': '#647286',
    '#aebdd0': '#4c5d70',
    '#b8c4d4': '#344356',
    '#bcd0e2': '#4c5d70',
    '#c2ccda': '#344356',
    '#cbd5e1': '#4c5d70',
    '#e2e8f0': '#2f3d50',
    '#f4f7fb': '#17212f',
    '#f8fafc': '#17212f'
}


def _normalize(value):
    return LIGHT if str(value or '').strip().lower() == LIGHT else DARK


def get_theme():
    try:
        if _THEME_FILE.exists():
            raw = json.loads(_THEME_FILE.read_text(encoding='utf-8'))
            if isinstance(raw, dict):
                return _normalize(raw.get('theme'))
    except Exception:
        pass
    return DARK


def is_light_theme():
    return get_theme() == LIGHT


def get_ctk_appearance_mode():
    return 'Light' if is_light_theme() else 'Dark'


def color(dark_hex):
    value = str(dark_hex)
    if not is_light_theme():
        return value
    return _COLOR_MAP.get(value.lower(), value)


def set_theme(theme):
    value = _normalize(theme)
    _THEME_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = _THEME_FILE.with_suffix('.tmp')
    tmp.write_text(json.dumps({'theme': value}, indent=2, ensure_ascii=False), encoding='utf-8')
    tmp.replace(_THEME_FILE)
    return value


def toggle_theme():
    return set_theme(DARK if is_light_theme() else LIGHT)


def theme_action_label():
    return 'Modo oscuro' if is_light_theme() else 'Modo claro'


def brand_symbol_path(project_root, *, dashboard=False):
    root = Path(project_root)
    if is_light_theme():
        return root / 'assets' / 'CorePulseSymbolLight.png'
    if dashboard:
        return root / 'assets' / 'CorePulseSymbolWhite.png'
    return root / 'assets' / 'CorePulseSymbol.png'


def sidebar_assets_path(project_root):
    root = Path(project_root)
    return root / 'assets' / ('sidebar_light' if is_light_theme() else 'sidebar')


def restart_application():
    """Reinicia CorePulse para aplicar una paleta consistente en todos los widgets."""
    root = Path(__file__).resolve().parents[1]
    try:
        if getattr(sys, 'frozen', False):
            os.execl(sys.executable, sys.executable)
        launcher = root / 'main.py'
        os.execl(sys.executable, sys.executable, str(launcher))
    except Exception:
        try:
            if getattr(sys, 'frozen', False):
                subprocess.Popen([sys.executable], cwd=str(root))
            else:
                subprocess.Popen([sys.executable, str(root / 'main.py')], cwd=str(root))
        finally:
            raise SystemExit(0)
