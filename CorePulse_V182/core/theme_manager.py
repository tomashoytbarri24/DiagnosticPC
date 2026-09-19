"""Autoridad única para los temas visuales de CorePulse.

V0.10.2.97w reemplaza el selector binario claro/oscuro por una galería de
15 temas. La preferencia se persiste y se aplica al reiniciar únicamente la
capa UI, evitando mezclar widgets ya creados con colores de otro tema.
"""
from __future__ import annotations

import colorsys
import json
import os
import subprocess
import sys
from pathlib import Path

from core.windows_commands import hidden_creationflags
from core.runtime_paths import data_path, executable_root

DEFAULT_THEME = 'corepulse'
LIGHT = 'snow'
DARK = DEFAULT_THEME
_THEME_FILE = data_path('ui_theme.json')

# Paletas pensadas para mantener contraste y jerarquía, no sólo cambiar un
# color de acento. ``appearance`` controla únicamente el render base de CTk.
_THEME_PROFILES = {
    'corepulse': {
        'name': 'CorePulse', 'description': 'Azul técnico original', 'appearance': 'dark',
        'bg': '#06111f', 'surface': '#0d1828', 'surface_2': '#101d2f',
        'sidebar': '#071522', 'border': '#1b3048', 'text': '#f4f7fb',
        'text_2': '#b8c4d4', 'muted': '#7f91a8', 'accent': '#14b8ff', 'accent_2': '#1687ea',
    },
    'ocean': {
        'name': 'Océano', 'description': 'Azules profundos y eléctricos', 'appearance': 'dark',
        'bg': '#071423', 'surface': '#0b2035', 'surface_2': '#102a43',
        'sidebar': '#071a2b', 'border': '#1f4b70', 'text': '#f2f8ff',
        'text_2': '#b5d0e8', 'muted': '#7798b5', 'accent': '#2f9cff', 'accent_2': '#1d77d4',
    },
    'aurora': {
        'name': 'Aurora', 'description': 'Turquesa frío y verde luminoso', 'appearance': 'dark',
        'bg': '#071716', 'surface': '#0d2421', 'surface_2': '#11302b',
        'sidebar': '#081d1b', 'border': '#24584f', 'text': '#f1fffb',
        'text_2': '#b9ded5', 'muted': '#7ea69d', 'accent': '#20d6b0', 'accent_2': '#0fa783',
    },
    'violet': {
        'name': 'Violeta', 'description': 'Púrpura profesional', 'appearance': 'dark',
        'bg': '#120d1d', 'surface': '#1d162c', 'surface_2': '#261d39',
        'sidebar': '#171022', 'border': '#493762', 'text': '#fbf7ff',
        'text_2': '#d2c3e5', 'muted': '#9886ad', 'accent': '#a970ff', 'accent_2': '#7d4ed8',
    },
    'ember': {
        'name': 'Brasa', 'description': 'Rojo carbón y naranja', 'appearance': 'dark',
        'bg': '#180d0b', 'surface': '#281713', 'surface_2': '#341e19',
        'sidebar': '#1f100e', 'border': '#63372c', 'text': '#fff8f5',
        'text_2': '#e8c8bd', 'muted': '#ad887c', 'accent': '#ff7849', 'accent_2': '#d9502f',
    },
    'forest': {
        'name': 'Bosque', 'description': 'Verde oscuro y esmeralda', 'appearance': 'dark',
        'bg': '#0a1510', 'surface': '#11251b', 'surface_2': '#173126',
        'sidebar': '#0d1d15', 'border': '#315b46', 'text': '#f3fff8',
        'text_2': '#bfdccb', 'muted': '#82a28f', 'accent': '#35d07f', 'accent_2': '#1ea661',
    },
    'rose': {
        'name': 'Rosa', 'description': 'Magenta sobrio y ciruela', 'appearance': 'dark',
        'bg': '#180d16', 'surface': '#281524', 'surface_2': '#341c2f',
        'sidebar': '#1f101c', 'border': '#613554', 'text': '#fff7fc',
        'text_2': '#e4c1d6', 'muted': '#aa829a', 'accent': '#f062b5', 'accent_2': '#c83e8e',
    },
    'graphite': {
        'name': 'Grafito', 'description': 'Neutro, sobrio y minimalista', 'appearance': 'dark',
        'bg': '#101214', 'surface': '#191c1f', 'surface_2': '#22262a',
        'sidebar': '#141719', 'border': '#3a4147', 'text': '#f6f7f8',
        'text_2': '#c9ced3', 'muted': '#8f989f', 'accent': '#8aa4b8', 'accent_2': '#657f93',
    },
    'cyber': {
        'name': 'Cyber', 'description': 'Cian neón sobre azul noche', 'appearance': 'dark',
        'bg': '#050f17', 'surface': '#071c28', 'surface_2': '#0a2836',
        'sidebar': '#06151f', 'border': '#145268', 'text': '#effcff',
        'text_2': '#a8d8e3', 'muted': '#6998a3', 'accent': '#00e0ff', 'accent_2': '#00a6c7',
    },
    'sky': {
        'name': 'Cielo', 'description': 'Azul claro, limpio y fresco', 'appearance': 'light',
        'bg': '#e6f2fb', 'surface': '#f6fbff', 'surface_2': '#dbeaf5',
        'sidebar': '#edf6fc', 'border': '#a9c5d8', 'text': '#173042',
        'text_2': '#35566c', 'muted': '#6b8291', 'accent': '#1686c9', 'accent_2': '#5aa9db',
    },
    'mint': {
        'name': 'Menta', 'description': 'Verde claro, suave y descansado', 'appearance': 'light',
        'bg': '#e5f3ec', 'surface': '#f5fbf8', 'surface_2': '#d8e9e1',
        'sidebar': '#ecf7f1', 'border': '#a7c9b8', 'text': '#173528',
        'text_2': '#3e5f50', 'muted': '#6d887a', 'accent': '#218a62', 'accent_2': '#57ad88',
    },
    'sand': {
        'name': 'Arena', 'description': 'Cálido crema con acento ámbar', 'appearance': 'light',
        'bg': '#f1eadf', 'surface': '#fbf7f0', 'surface_2': '#e7dccb',
        'sidebar': '#f5efe5', 'border': '#cdbba2', 'text': '#3a2d20',
        'text_2': '#5d4d3c', 'muted': '#877663', 'accent': '#b86f2c', 'accent_2': '#d39b62',
    },
    'lavender': {
        'name': 'Lavanda', 'description': 'Lila claro y profesional', 'appearance': 'light',
        'bg': '#eeeaf5', 'surface': '#faf8fd', 'surface_2': '#e3ddeb',
        'sidebar': '#f4f0f8', 'border': '#c2b4d1', 'text': '#312641',
        'text_2': '#564869', 'muted': '#7e708f', 'accent': '#7a5bb7', 'accent_2': '#a58ad1',
    },
    'pearl': {
        'name': 'Perla', 'description': 'Neutro claro, elegante y sobrio', 'appearance': 'light',
        'bg': '#ecebea', 'surface': '#f8f7f5', 'surface_2': '#e1dfdc',
        'sidebar': '#f1f0ee', 'border': '#bebbb6', 'text': '#292827',
        'text_2': '#4e4c49', 'muted': '#77736e', 'accent': '#5f7890', 'accent_2': '#8ea4b7',
    },
    'snow': {
        'name': 'Nieve', 'description': 'Claro suave, sin blanco puro', 'appearance': 'light',
        'bg': '#e1e6ec', 'surface': '#f2f4f7', 'surface_2': '#dde3e9',
        'sidebar': '#e9edf2', 'border': '#aab8c5', 'text': '#17212f',
        'text_2': '#344356', 'muted': '#647286', 'accent': '#0873ad', 'accent_2': '#156fbd',
    },
}

# Compatibilidad con el anterior modo claro; también se usa para Nieve en los
# colores específicos que tenían un equivalente cuidadosamente ajustado.
_COLOR_MAP_LIGHT = {
    '#06111f': '#e1e6ec', '#071522': '#e9edf2', '#08111f': '#e1e6ec', '#091726': '#e8eef4',
    '#0a1422': '#e9edf2', '#0a1524': '#e9edf2', '#0b0f19': '#e1e6ec', '#0b1422': '#e1e6ec',
    '#0b1524': '#e9edf2', '#0b1626': '#e9edf2', '#0b1726': '#f2f4f7', '#0c1726': '#e9edf2',
    '#0d1322': '#f2f4f7', '#0d1828': '#f2f4f7', '#0d2130': '#e5ebf1', '#0d2942': '#e3edf7',
    '#0d2b45': '#dfeaf5', '#0d332b': '#e1eee8', '#0d5c45': '#dceee6', '#0d8fc7': '#0b78ad',
    '#0e1726': '#e9edf2', '#0e1d2f': '#d9e3ec', '#0f172a': '#d2dae3', '#0f1c2d': '#e8edf2',
    '#0f2135': '#e3e9ef', '#0f2437': '#e3e9ef', '#101d2e': '#f2f4f7', '#101d2f': '#e9edf2',
    '#102235': '#deebe5', '#10283a': '#e4eaf0', '#102840': '#d4e0eb', '#102943': '#b4c0cb',
    '#111827': '#e9edf2', '#11765a': '#cce9dc', '#12243a': '#e3e9ef', '#123e5c': '#dfe8f1',
    '#124f80': '#0b6fae', '#13253a': '#e3e9ef', '#132741': '#d2dae3', '#14243a': '#e3e9ef',
    '#14253b': '#e3e9ef', '#14263c': '#e3e9ef', '#151c2c': '#f2f4f7', '#15243a': '#d2dae3',
    '#152750': '#e8e2f3', '#152a41': '#e4eaf0', '#16263a': '#e3e9ef', '#163047': '#e3e9ef',
    '#164f7d': '#cbdff0', '#1687ea': '#156fbd', '#17263a': '#e3e9ef', '#172a42': '#c3ccd6',
    '#172b43': '#c3ccd6', '#17314c': '#b5c0cc', '#17314d': '#aab8c5', '#173550': '#c1cad4',
    '#174e72': '#d6e4f0', '#178967': '#b9dfcf', '#182a40': '#e3e9ef', '#19324e': '#c1cad4',
    '#1b3048': '#aab8c5', '#1b5c8f': '#bcd4e8', '#1c3451': '#bdc8d3', '#1d3350': '#bcc6d1',
    '#1d5278': '#9fbad0', '#1e3a5f': '#e3edf7', '#1f2a3d': '#c1cad4', '#202d44': '#bcc6d1',
    '#20344c': '#b5c0cc', '#203650': '#b5c0cc', '#214765': '#c6d7e5', '#232f48': '#bcc6d1',
    '#26344f': '#b5c0cc', '#26354d': '#b5c0cc', '#263d58': '#b9c5d1', '#284f7a': '#d5e4f2',
    '#29435f': '#b6c3cf', '#2b1d26': '#f3e5e7', '#2b668f': '#b9d1e3', '#2f80ed': '#156fbd',
    '#31516d': '#98a8b8', '#334155': '#c5ced8', '#334867': '#b8c4cf', '#3b8df2': '#156fbd',
    '#412530': '#efdadd', '#416887': '#8598aa', '#475569': '#667589', '#4d2530': '#f0e1e3',
    '#5a2630': '#efe0e2', '#5aa0ff': '#267bc1', '#5f7189': '#647286', '#66788f': '#647286',
    '#693343': '#e8c5ca', '#72849b': '#647286', '#73869e': '#647286', '#75d2f7': '#0873ad',
    '#7f91a8': '#647286', '#8295ad': '#647286', '#94a3b8': '#647286', '#9da9b9': '#647286',
    '#aebdd0': '#4c5d70', '#b8c4d4': '#344356', '#bcd0e2': '#4c5d70', '#c2ccda': '#344356',
    '#cbd5e1': '#4c5d70', '#e2e8f0': '#2f3d50', '#f4f7fb': '#17212f', '#f8fafc': '#17212f',
    '#17182f': '#eeeaf8', '#4a4772': '#aaa1c8', '#a991ff': '#7055c7', '#101226': '#f4f1fa',
    '#1d203d': '#e4def2', '#091a28': '#e9f2f7', '#0f2b40': '#d9e9f2', '#0b1c26': '#e8f2ee',
    '#10352e': '#d7ebe2', '#241d0f': '#f6f0e3', '#6e5421': '#c2a76d', '#f4b942': '#9b6b08',
    '#1b170e': '#faf6ed', '#302611': '#eee3c9', '#0c1828': '#edf1f6', '#142c46': '#dde6ef',
    '#251c11': '#f7f0e6', '#725022': '#c7a16c', '#1b160f': '#faf6ef', '#332611': '#eee1ca',
    '#20c997': '#07845f', '#0a211d': '#e8f3ef', '#103c33': '#d4e9e1', '#8fb7d5': '#416f92',
    '#0d1b2a': '#edf1f5', '#20171d': '#f7ecef'
}

_ROLE_ALIASES = {
    # Los alias describen el ROL visual del color original. En temas distintos
    # a CorePulse el valor se sustituye por el color exacto de ese rol; no se
    # mezcla con el azul anterior. Esto hace que la UI aplicada coincida con la
    # vista previa y evita el efecto de "filtro oscuro".
    'bg': {
        '#06111f', '#071626', '#08111f', '#08121d', '#081424', '#0b0f19',
        '#0b1422', '#0c1726', '#0d1322',
    },
    'sidebar': {'#071522'},
    'surface': {
        '#091726', '#0a1422', '#0a1726', '#0b1626', '#0b1726', '#0d1728',
        '#0d1828', '#0e1726', '#0f1c2d', '#101d2e', '#151c2c',
    },
    'surface_2': {
        '#091827', '#091a28', '#0a1524', '#0a1b2d', '#0b1524', '#0b2232',
        '#0c2035', '#0d2130', '#0e1d2f', '#0f172a', '#0f2135', '#0f2437',
        '#102235', '#10263a', '#10263b', '#10283a', '#111827', '#111d2e',
        '#122433', '#12243a', '#132338', '#13253a', '#14243a', '#14253b',
        '#14263c', '#14283b', '#15243a', '#16263a', '#163047', '#172338',
        '#17263a', '#182a40', '#1f2a3d',
    },
    'border': {
        '#17314c', '#17314d', '#173550', '#18314b', '#19324e', '#1b3048',
        '#1c3451', '#1d3350', '#202d44', '#20344c', '#203650', '#214765',
        '#232f48', '#26344f', '#26354d', '#263d58', '#29435f', '#31516d',
        '#334155', '#334867', '#416887', '#475569',
    },
    'text': {'#f8fafc', '#f4f7fb', '#e2e8f0'},
    'text_2': {'#cbd5e1', '#c2ccda', '#bcd0e2', '#b8c4d4', '#aebdd0', '#9bddff'},
    'muted': {
        '#9da9b9', '#94a3b8', '#8295ad', '#7f91a8', '#7fa7c5', '#73869e',
        '#72849b', '#70839b', '#66788f', '#5f7189',
    },
    'accent': {'#14b8ff', '#38bdf8', '#75d2f7'},
    'accent_2': {
        '#0d2942', '#0d2b45', '#0d8fc7', '#11304a', '#12324b', '#12324c',
        '#123b59', '#123e5c', '#124f80', '#15314b', '#164f7d', '#1687ea',
        '#174e72', '#17658f', '#1b4e7c', '#1b5c8f', '#1d5278', '#1d628f',
        '#215c92', '#23577c', '#245b82', '#284f7a', '#2a7bc0', '#2b668f',
        '#2d617b', '#2f6084', '#2f80ed', '#3b8df2', '#5aa0ff',
    },
}

_ROLE_BY_COLOR = {
    color: role
    for role, colors in _ROLE_ALIASES.items()
    for color in colors
}


def _profile_values(profile):
    return {str(profile.get(role, '')).lower() for role in (
        'bg', 'surface', 'surface_2', 'sidebar', 'border', 'text', 'text_2',
        'muted', 'accent', 'accent_2'
    )}


def _fallback_structural_role(value):
    """Asigna colores estructurales al rol CorePulse MÁS CERCANO.

    Antes se usaban umbrales de luminosidad. Un azul que visualmente era el
    fondo podía terminar clasificado como ``surface`` o ``surface_2`` y, al
    cambiar de tema, verse más oscuro que la vista previa. La referencia ahora
    es la propia paleta CorePulse: se busca el rol cuyo hexadecimal original es
    más cercano y después se usa el valor EXACTO de ese rol en el tema elegido.

    Los colores semánticos (rojo, verde, ámbar, violeta, etc.) siguen intactos.
    """
    try:
        r, g, b = [x / 255.0 for x in _hex_to_rgb(value)]
        h, l, sat = colorsys.rgb_to_hls(r, g, b)
    except Exception:
        return None

    is_blue_family = 0.50 <= h <= 0.70
    is_neutral = sat <= 0.18
    if not (is_blue_family or is_neutral):
        return None

    # No reinterpretar blancos/grises semánticos fuera de la jerarquía textual.
    candidates = ('bg', 'surface', 'surface_2', 'border', 'text', 'text_2', 'muted', 'accent', 'accent_2')
    base = _THEME_PROFILES[DEFAULT_THEME]
    rr, gg, bb = _hex_to_rgb(value)

    def distance(role):
        cr, cg, cb = _hex_to_rgb(base[role])
        # El ojo percibe el verde con más peso; esta aproximación simple evita
        # que azules cercanos salten de rol sólo por el canal B.
        return ((rr - cr) ** 2 * 0.30 + (gg - cg) ** 2 * 0.59 + (bb - cb) ** 2 * 0.11)

    return min(candidates, key=distance)


def get_theme_profiles():
    """Devuelve una copia liviana de las 15 paletas disponibles."""
    return {key: dict(value) for key, value in _THEME_PROFILES.items()}


def get_theme_profile(theme=None):
    key = _normalize(theme if theme is not None else get_theme())
    return dict(_THEME_PROFILES[key])


def role_color(role, theme=None):
    """Devuelve el hexadecimal EXACTO de un rol de la paleta activa.

    Usar esto en superficies estructurales evita inferencias por luminosidad y
    garantiza que la interfaz real coincida con la vista previa del selector.
    """
    profile = get_theme_profile(theme)
    key = str(role or '').strip().lower()
    return profile.get(key, profile['accent'])


def _normalize(value):
    raw = str(value or '').strip().lower()
    # Migración transparente desde ui_theme.json de versiones <= 96w.
    if raw == 'dark':
        return DEFAULT_THEME
    if raw == 'light':
        return LIGHT
    return raw if raw in _THEME_PROFILES else DEFAULT_THEME


def get_theme():
    try:
        if _THEME_FILE.exists():
            raw = json.loads(_THEME_FILE.read_text(encoding='utf-8'))
            if isinstance(raw, dict):
                return _normalize(raw.get('theme'))
    except Exception:
        pass
    return DEFAULT_THEME


def is_light_theme():
    return _THEME_PROFILES[get_theme()]['appearance'] == 'light'


def get_ctk_appearance_mode():
    return 'Light' if is_light_theme() else 'Dark'


def _hex_to_rgb(value):
    value = value.lstrip('#')
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def _rgb_to_hex(rgb):
    return '#%02x%02x%02x' % tuple(max(0, min(255, int(round(v)))) for v in rgb)


def _mix(a, b, ratio):
    ar = _hex_to_rgb(a); br = _hex_to_rgb(b)
    r = max(0.0, min(1.0, float(ratio)))
    return _rgb_to_hex(tuple(ar[i] * (1.0 - r) + br[i] * r for i in range(3)))


def _theme_role_color(value, profile):
    key = value.lower()

    # Idempotencia: algunos módulos antiguos envuelven theme_color(theme_color()).
    # Si el color ya pertenece a la paleta activa, no se procesa otra vez.
    if key in _profile_values(profile):
        return value

    role = _ROLE_BY_COLOR.get(key)
    if role is None:
        role = _fallback_structural_role(value)
    if role is None:
        return value
    return profile[role]


def color(dark_hex):
    """Sustituye el color estructural CorePulse por el rol exacto del tema.

    No aplica tintes, mezclas ni filtros sobre el azul original. Así, por
    ejemplo, ``surface`` en la vista previa y ``surface`` en la interfaz real
    son exactamente el mismo hexadecimal.
    """
    value = str(dark_hex)
    if not (len(value) == 7 and value.startswith('#')):
        return value
    theme = get_theme()
    if theme == DEFAULT_THEME:
        return value
    return _theme_role_color(value, _THEME_PROFILES[theme])


def preview_color(theme, role):
    """Color directo de una paleta para la vista previa del selector."""
    profile = _THEME_PROFILES[_normalize(theme)]
    return profile.get(str(role), profile['accent'])


def set_theme(theme):
    value = _normalize(theme)
    _THEME_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = _THEME_FILE.with_suffix('.tmp')
    tmp.write_text(json.dumps({'theme': value}, indent=2, ensure_ascii=False), encoding='utf-8')
    tmp.replace(_THEME_FILE)
    return value


def toggle_theme():
    """Compatibilidad: alterna entre CorePulse y Nieve."""
    return set_theme(DEFAULT_THEME if is_light_theme() else LIGHT)


def theme_action_label():
    # El antiguo botón claro/oscuro se reemplazó por el módulo Temas.
    return 'Temas'


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
    """Reinicia CorePulse para aplicar la paleta de forma consistente."""
    root = executable_root()
    try:
        if getattr(sys, 'frozen', False):
            os.execl(sys.executable, sys.executable)
        launcher = root / 'main.py'
        os.execl(sys.executable, sys.executable, str(launcher))
    except Exception:
        try:
            if getattr(sys, 'frozen', False):
                subprocess.Popen([sys.executable], cwd=str(root), creationflags=hidden_creationflags())
            else:
                subprocess.Popen([sys.executable, str(root / 'main.py')], cwd=str(root), creationflags=hidden_creationflags())
        finally:
            raise SystemExit(0)
