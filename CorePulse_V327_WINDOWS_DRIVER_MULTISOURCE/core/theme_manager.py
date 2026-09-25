"""Autoridad única para los temas visuales de CorePulse.

V280 mantiene exclusivamente temas oscuros y unifica superficies para evitar fondos claros/aislados entre módulos. La preferencia se persiste y puede aplicarse en caliente a la capa UI, sin reiniciar el proceso.
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
LIGHT = DEFAULT_THEME
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
    'crimson': {
        'name': 'Rojo', 'description': 'Negro carbón con rojo intenso', 'appearance': 'dark',
        'bg': '#100708', 'surface': '#1a0c0f', 'surface_2': '#251014',
        'sidebar': '#14090b', 'border': '#5c2029', 'text': '#fff5f6',
        'text_2': '#e7bcc1', 'muted': '#a9787f', 'accent': '#ff334d', 'accent_2': '#c8142f',
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
    'midnight': {
        'name': 'Medianoche', 'description': 'Azul tinta profundo y elegante', 'appearance': 'dark',
        'bg': '#080d18', 'surface': '#101827', 'surface_2': '#172236',
        'sidebar': '#0b1220', 'border': '#2a3b56', 'text': '#f4f7ff',
        'text_2': '#c1cce0', 'muted': '#8492aa', 'accent': '#6ea8ff', 'accent_2': '#356fc7',
    },
    'copper': {
        'name': 'Cobre', 'description': 'Carbón cálido con cobre metálico', 'appearance': 'dark',
        'bg': '#17110e', 'surface': '#241a16', 'surface_2': '#30221c',
        'sidebar': '#1c1411', 'border': '#5e4336', 'text': '#fff8f2',
        'text_2': '#e3c9b9', 'muted': '#a68776', 'accent': '#d98a55', 'accent_2': '#a85d34',
    },
    'indigo': {
        'name': 'Índigo', 'description': 'Azul violeta sobrio de alto contraste', 'appearance': 'dark',
        'bg': '#0d1020', 'surface': '#151a31', 'surface_2': '#1e2542',
        'sidebar': '#11162a', 'border': '#3c4770', 'text': '#f7f8ff',
        'text_2': '#c9cee8', 'muted': '#8f97b8', 'accent': '#748cff', 'accent_2': '#5065d6',
    },
    'obsidian': {
        'name': 'Obsidiana', 'description': 'Negro profundo y acero frío', 'appearance': 'dark',
        'bg': '#07090c', 'surface': '#101419', 'surface_2': '#171d24',
        'sidebar': '#0b0e12', 'border': '#303943', 'text': '#f5f7fa',
        'text_2': '#c3cbd4', 'muted': '#7f8b97', 'accent': '#9ab4c8', 'accent_2': '#607d94',
    },
    'arctic': {
        'name': 'Ártico', 'description': 'Azul noche con hielo eléctrico', 'appearance': 'dark',
        'bg': '#071019', 'surface': '#0c1a27', 'surface_2': '#11283a',
        'sidebar': '#081521', 'border': '#24506d', 'text': '#f3fbff',
        'text_2': '#bad7e8', 'muted': '#789eb5', 'accent': '#65d8ff', 'accent_2': '#279bc9',
    },
    'jade': {
        'name': 'Jade', 'description': 'Negro mineral y verde jade', 'appearance': 'dark',
        'bg': '#07120f', 'surface': '#0d1e19', 'surface_2': '#132a23',
        'sidebar': '#091813', 'border': '#285344', 'text': '#f2fff9',
        'text_2': '#b8ddcc', 'muted': '#79a18f', 'accent': '#2ed39a', 'accent_2': '#15966d',
    },
    'gold': {
        'name': 'Oro', 'description': 'Carbón oscuro y dorado técnico', 'appearance': 'dark',
        'bg': '#151109', 'surface': '#211a0e', 'surface_2': '#2c2414',
        'sidebar': '#1a140b', 'border': '#5e4d27', 'text': '#fffaf0',
        'text_2': '#e5d6ae', 'muted': '#a89466', 'accent': '#f2c14e', 'accent_2': '#b88a24',
    },
    'ultraviolet': {
        'name': 'Ultravioleta', 'description': 'Negro violeta y neón púrpura', 'appearance': 'dark',
        'bg': '#0c0714', 'surface': '#160d22', 'surface_2': '#21122f',
        'sidebar': '#10091a', 'border': '#4c2866', 'text': '#fbf5ff',
        'text_2': '#d6bce5', 'muted': '#9c7dad', 'accent': '#c058ff', 'accent_2': '#8730c4',
    },
    'volcano': {
        'name': 'Volcán', 'description': 'Negro volcánico y naranja vivo', 'appearance': 'dark',
        'bg': '#120b08', 'surface': '#20120d', 'surface_2': '#2c1911',
        'sidebar': '#180e0a', 'border': '#5f3524', 'text': '#fff7f1',
        'text_2': '#e8c4b3', 'muted': '#aa7f69', 'accent': '#ff6b35', 'accent_2': '#c5461e',
    },
    'electric': {
        'name': 'Eléctrico', 'description': 'Azul negro con lima brillante', 'appearance': 'dark',
        'bg': '#08100d', 'surface': '#0f1b16', 'surface_2': '#17271f',
        'sidebar': '#0b1511', 'border': '#334f3f', 'text': '#f6fff9',
        'text_2': '#c6dacd', 'muted': '#879d8f', 'accent': '#9be84f', 'accent_2': '#5da925',
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
    """Devuelve una copia de las paletas oscuras disponibles."""
    return {key: dict(value) for key, value in _THEME_PROFILES.items()}


def get_theme_profile(theme=None):
    key = _normalize(theme if theme is not None else get_theme())
    return dict(_THEME_PROFILES[key])


def _relative_luminance(value):
    channels = []
    for raw in _hex_to_rgb(value):
        channel = raw / 255.0
        channels.append(channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def _contrast_ratio(a, b):
    la, lb = _relative_luminance(a), _relative_luminance(b)
    lighter, darker = max(la, lb), min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


def _best_text_on(background, profile):
    # Mantiene cada tema reconocible, pero nunca sacrifica la legibilidad del botón.
    candidates = (profile['text'], '#ffffff', '#07111f', '#111827')
    return max(candidates, key=lambda value: _contrast_ratio(value, background))


def _derived_role(profile, key):
    dark = profile.get('appearance') != 'light'
    if key == 'accent_soft':
        return _mix(profile['surface_2'], profile['accent'], 0.24 if dark else 0.14)
    if key == 'accent_edge':
        return _mix(profile['border'], profile['accent'], 0.58)
    if key == 'ok_bg':
        return _mix(profile['surface'], '#16d98b', 0.16 if dark else 0.09)
    if key == 'warn_bg':
        return _mix(profile['surface'], '#f3b54a', 0.17 if dark else 0.10)
    if key == 'bad_bg':
        return _mix(profile['surface'], '#ff5d6c', 0.16 if dark else 0.09)
    if key == 'ok_text':
        return '#24e49a' if dark else '#087a4f'
    if key == 'warn_text':
        return '#ffc96b' if dark else '#805000'
    if key == 'bad_text':
        return '#ff7b87' if dark else '#a51f31'
    if key == 'text_on_accent':
        return _best_text_on(profile['accent_2'], profile)
    return None


def role_color(role, theme=None):
    """Devuelve un rol visual seguro de la paleta activa.

    Los roles base siguen usando el hexadecimal exacto del tema. Los roles
    funcionales (selección, estados y texto sobre botones) se derivan de esa
    misma paleta para mantener contraste. Antes, cualquier rol desconocido
    caía en ``accent`` y podía convertir botones/selecciones en bloques neón.
    """
    profile = get_theme_profile(theme)
    key = str(role or '').strip().lower()
    if key in profile:
        return profile[key]
    derived = _derived_role(profile, key)
    return derived if derived is not None else profile['accent']


def _normalize(value):
    raw = str(value or '').strip().lower()
    # Migración transparente: cualquier tema/modo claro previo vuelve a CorePulse oscuro.
    if raw in {'dark', 'light', 'sky', 'mint', 'sand', 'lavender', 'pearl', 'snow', 'frost', 'sakura'}:
        return DEFAULT_THEME
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
    """Compatibilidad histórica: V280 ya no ofrece modo claro."""
    return set_theme(DEFAULT_THEME)


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



def _live_theme_color_map(old_theme, new_theme):
    """Mapa exacto old->new para recolorear la UI sin reiniciar el proceso."""
    old_profile = get_theme_profile(old_theme)
    new_profile = get_theme_profile(new_theme)
    mapping = {}
    base_roles = ('bg', 'surface', 'surface_2', 'sidebar', 'border', 'text', 'text_2', 'muted', 'accent', 'accent_2')
    for role in base_roles:
        old = str(old_profile.get(role) or '').lower()
        new = str(new_profile.get(role) or '')
        if old:
            mapping[old] = new
    # También cubre colores estructurales heredados que todavía puedan estar
    # presentes cuando el tema previo era CorePulse.
    for color_value, role in _ROLE_BY_COLOR.items():
        mapping[str(color_value).lower()] = str(new_profile[role])
    for role in ('accent_soft', 'accent_edge', 'ok_bg', 'warn_bg', 'bad_bg', 'ok_text', 'warn_text', 'bad_text', 'text_on_accent'):
        old = _derived_role(old_profile, role)
        new = _derived_role(new_profile, role)
        if old and new:
            mapping[str(old).lower()] = str(new)
    return mapping


def _remap_live_value(value, mapping):
    if isinstance(value, str):
        return mapping.get(value.lower(), value)
    if isinstance(value, tuple):
        return tuple(_remap_live_value(item, mapping) for item in value)
    if isinstance(value, list):
        return [_remap_live_value(item, mapping) for item in value]
    return value


def _patch_live_module_palettes(mapping):
    """Actualiza constantes UI ya importadas para que futuras vistas usen el nuevo tema."""
    for module_name, module in list(sys.modules.items()):
        if module is None or module_name == __name__:
            continue
        if not (module_name == '__main__' or module_name == 'main' or module_name.startswith('gui.')):
            continue
        namespace = getattr(module, '__dict__', None)
        if not isinstance(namespace, dict):
            continue
        for key, value in list(namespace.items()):
            if key.startswith('__'):
                continue
            if isinstance(value, str):
                replacement = mapping.get(value.lower())
                if replacement is not None:
                    namespace[key] = replacement
            elif isinstance(value, dict) and key.upper() in {'COLORS', 'PALETTE', 'THEME', 'THEME_COLORS'}:
                for subkey, subvalue in list(value.items()):
                    if isinstance(subvalue, str):
                        replacement = mapping.get(subvalue.lower())
                        if replacement is not None:
                            value[subkey] = replacement


def _recolor_widget_tree(widget, mapping):
    """Recolorea widgets CTk/Tk existentes. Tk pinta los cambios al volver al loop."""
    if widget is None:
        return
    ctk_options = (
        'fg_color', 'bg_color', 'border_color', 'text_color', 'hover_color',
        'progress_color', 'button_color', 'button_hover_color',
        'scrollbar_fg_color', 'scrollbar_button_color', 'scrollbar_button_hover_color',
        'checkmark_color', 'dropdown_fg_color', 'dropdown_hover_color',
        'dropdown_text_color', 'selected_color', 'selected_hover_color',
    )
    updates = {}
    for option in ctk_options:
        try:
            current = widget.cget(option)
        except Exception:
            continue
        mapped = _remap_live_value(current, mapping)
        if mapped != current:
            updates[option] = mapped
    if updates:
        try:
            widget.configure(**updates)
        except Exception:
            # Algunos widgets exponen cget pero no permiten reconfigurar todas las opciones.
            for option, mapped in updates.items():
                try:
                    widget.configure(**{option: mapped})
                except Exception:
                    pass
    # Widgets Tk nativos usados en bordes/divisores.
    for option in ('bg', 'background', 'fg', 'foreground', 'highlightbackground', 'highlightcolor'):
        try:
            current = widget.cget(option)
        except Exception:
            continue
        mapped = _remap_live_value(current, mapping)
        if mapped != current:
            try:
                widget.configure(**{option: mapped})
            except Exception:
                pass
    try:
        children = list(widget.winfo_children())
    except Exception:
        children = []
    for child in children:
        _recolor_widget_tree(child, mapping)


def apply_theme_live(app, old_theme, new_theme):
    """Aplica la nueva paleta en el proceso actual, sin cerrar ni relanzar CorePulse."""
    old_key = _normalize(old_theme)
    new_key = _normalize(new_theme)
    if old_key == new_key:
        return new_key
    mapping = _live_theme_color_map(old_key, new_key)
    _patch_live_module_palettes(mapping)
    _recolor_widget_tree(app, mapping)

    # Matplotlib no forma parte del árbol CTk: sincronizarlo con la misma paleta.
    try:
        dashboard = sys.modules.get('gui.dashboard')
        if dashboard is not None:
            style_charts = getattr(dashboard, '_style_charts', None)
            if callable(style_charts):
                style_charts(app)
    except Exception:
        pass
    try:
        app.configure(fg_color=get_theme_profile(new_key)['bg'])
    except Exception:
        pass
    try:
        app.update_idletasks()
    except Exception:
        pass
    return new_key

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
