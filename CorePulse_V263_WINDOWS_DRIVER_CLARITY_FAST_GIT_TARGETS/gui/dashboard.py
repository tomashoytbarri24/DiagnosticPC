"""Construye la presentación visual del Dashboard principal de CorePulse.

Este módulo SOLO modifica presentación. No obtiene telemetría, no altera valores,
no calcula salud y no reemplaza ninguna autoridad de diagnóstico. Los widgets
siguen consumiendo exactamente los mismos datos reales del runtime.
"""
from __future__ import annotations
from gui.widget_updates import configure_changed
from core.theme_manager import color as theme_color, brand_symbol_path, sidebar_assets_path, theme_action_label, role_color

import time
import math
import types
import threading
from pathlib import Path
from core.runtime_paths import resource_root

import psutil
import customtkinter as ctk
from PIL import Image

from core.version import VERSION_LABEL
from core.device_identity import collect_device_identity

VERSION = VERSION_LABEL
DESIGN_ID = 'COREPULSE_DASHBOARD_REFERENCE'

# V128 — contrato visual de temas. Las superficies estructurales del Dashboard
# consumen directamente los roles EXACTOS de la paleta activa. No se infieren
# desde azules heredados y no se aplican mezclas, darken/lighten ni filtros.
# Esta misma semántica es la que usa la vista previa de Temas.
COLORS = {
    'app': role_color('bg'),
    'sidebar': role_color('sidebar'),
    'surface': role_color('surface'),
    'surface_2': role_color('surface_2'),
    'surface_hover': role_color('surface_2'),
    'border': role_color('border'),
    'border_soft': role_color('border'),
    'text': role_color('text'),
    'text_2': role_color('text_2'),
    'muted': role_color('muted'),
    'primary': role_color('accent'),
    'primary_dark': role_color('accent_2'),
    'green': '#16d98b',
    'amber': '#f3b54a',
    'red': '#ff5d6c',
    'purple': '#a064ff',
    'track': role_color('surface_2'),
}
FONT = 'Segoe UI'
ICON_FONT = 'Segoe UI Symbol'

# V128 — el estado activo replica la previsualización de Temas: accent_2
# exacto, hover accent y texto del rol text. Sin tonos intermedios derivados.
SIDEBAR_ACTIVE_BG = role_color('accent_2')
SIDEBAR_ACTIVE_HOVER = role_color('accent')
SIDEBAR_ACTIVE_BORDER = role_color('accent')
SIDEBAR_INACTIVE_TEXT = role_color('text_2')

# V229 — experimento visual: borde funcional por opción del sidebar.
SIDEBAR_OPTION_ACCENTS = {
    '_btn_summary': COLORS['primary'],
    'btn_benchmark': COLORS['purple'],
    'btn_diagnostic': COLORS['amber'],
    'btn_health_center': COLORS['green'],
    'btn_cleanup': COLORS['primary'],
    'btn_tweaks': COLORS['purple'],
    'btn_network': COLORS['primary'],
    'btn_smart_alerts': COLORS['red'],
    'btn_session_trends': COLORS['green'],
    'btn_alert_history': COLORS['amber'],
}

def _sidebar_option_accent(attr):
    return SIDEBAR_OPTION_ACCENTS.get(attr, COLORS['primary'])

SIDEBAR_ICON_FILES = {
    '_btn_summary': 'summary.png',
    'btn_benchmark': 'overlay.png',
    'btn_diagnostic': 'diagnostic.png',
    'btn_health_center': 'health.png',
    'btn_cleanup': 'cleanup.png',
    'btn_tweaks': 'tweaks.png',
    'btn_network': 'network.png',
    'btn_smart_alerts': 'alerts.png',
    'btn_session_trends': 'trends.png',
    'btn_alert_history': 'history.png',
}
SIDEBAR_LABELS = {
    '_btn_summary': 'Resumen',
    'btn_benchmark': 'Benchmark',
    'btn_diagnostic': 'Iniciar diagnóstico',
    'btn_health_center': 'Centro de salud',
    'btn_cleanup': 'Limpieza de sistema',
    'btn_tweaks': 'Tweaks Windows 11',
    'btn_network': 'Red avanzada',
    'btn_smart_alerts': 'Alertas técnicas',
    'btn_session_trends': 'Tendencias',
    'btn_alert_history': 'Historial de alertas',
}


def _safe_config(widget, **kwargs):
    try:
        configure_changed(widget, **kwargs)
    except Exception:
        pass


def _safe_pack_forget(widget):
    try:
        widget.pack_forget()
    except Exception:
        pass


def _bind_sidebar_glyph(widget, command):
    """Hace clickeable un glifo sin convertirlo en botón/cápsula."""
    if widget is None:
        return widget
    try:
        widget.configure(cursor='hand2')
    except Exception:
        pass
    try:
        widget.bind('<Button-1>', lambda _event: command() if callable(command) else None, add='+')
    except Exception:
        pass
    return widget


def _sync_sidebar_visibility_controls(app):
    """V254: al ocultarse el sidebar sólo queda ☰ como glifo independiente."""
    glyph = getattr(app, '_sidebar_reopen_button', None)
    try:
        exists = bool(glyph is not None and glyph.winfo_exists())
    except Exception:
        exists = False
    if not exists:
        glyph = ctk.CTkLabel(
            app,
            text='☰',
            width=30,
            height=30,
            fg_color='transparent',
            text_color=COLORS['text_2'],
            font=(ICON_FONT, 20, 'bold'),
            anchor='center',
        )
        app._sidebar_reopen_button = glyph
        _bind_sidebar_glyph(glyph, getattr(app, 'toggle_sidebar_collapse', None))
    else:
        _safe_config(
            glyph,
            text='☰',
            width=30,
            height=30,
            fg_color='transparent',
            text_color=COLORS['text_2'],
            font=(ICON_FONT, 20, 'bold'),
        )
    if bool(getattr(app, '_sidebar_collapsed', False)):
        try:
            glyph.place(x=16, y=14, anchor='nw')
            glyph.lift()
        except Exception:
            pass
    else:
        try:
            glyph.place_forget()
        except Exception:
            pass
    return glyph

def _status_color(score):
    try:
        score = float(score)
    except Exception:
        return COLORS['muted']
    if score < 50:
        return COLORS['red']
    if score < 70:
        return COLORS['amber']
    if score < 85:
        return COLORS['primary']
    return COLORS['green']


def _status_name(score):
    try:
        score = float(score)
    except Exception:
        return 'EVALUANDO'
    if score < 50:
        return 'CRÍTICO'
    if score < 70:
        return 'ADVERTENCIA'
    if score < 85:
        return 'ESTABLE'
    return 'ÓPTIMO'


def _uptime_text():
    try:
        elapsed = max(0, int(time.time() - psutil.boot_time()))
        h, rem = divmod(elapsed, 3600)
        m, s = divmod(rem, 60)
        if h >= 100:
            d, h = divmod(h, 24)
            return f'{d}d {h:02d}:{m:02d}'
        return f'{h:02d}:{m:02d}:{s:02d}'
    except Exception:
        return 'N/A'


def _telemetry_coverage(telemetry):
    """Cuenta únicamente el metadata de certificación ya producido por CorePulse."""
    if not isinstance(telemetry, dict):
        return (None, None)
    metrics = telemetry.get('_metrics')
    if not isinstance(metrics, dict) or not metrics:
        return (None, None)
    total = 0
    valid = 0
    for meta in metrics.values():
        if not isinstance(meta, dict):
            continue
        total += 1
        if str(meta.get('quality') or '').upper() == 'VALID':
            valid += 1
    return (valid, total)


def _bind_click_tree(widget, callback):
    """Hace clickeable una tarjeta completa sin duplicar acciones de botones hijos."""
    if widget is None or not callable(callback):
        return
    # Los CTkButton conservan su propio command. Evita dobles aperturas cuando
    # una tarjeta navegable contiene un botón de acción explícito.
    if isinstance(widget, ctk.CTkButton):
        return
    try:
        widget.configure(cursor='hand2')
    except Exception:
        pass
    try:
        widget.bind('<Button-1>', lambda _event: callback(), add='+')
    except Exception:
        pass
    try:
        for child in widget.winfo_children():
            _bind_click_tree(child, callback)
    except Exception:
        pass


def _bind_card_hover(root, *, normal=None, hover=None, action_button=None, action_place=None):
    """Feedback estable y acción contextual visible sólo mientras la tarjeta está bajo el puntero.

    La navegación de la tarjeta sigue funcionando completa. ``action_button`` es sólo
    una affordance visual: se oculta en reposo para reducir ruido y aparece al hacer
    hover sin alterar telemetría ni el layout de la tarjeta.
    """
    if root is None:
        return
    normal = normal or COLORS['surface']
    hover = hover or COLORS['surface_hover']
    pending = {'after': None}
    action_place = dict(action_place or {})

    def show_action():
        if action_button is None:
            return
        try:
            if not action_button.winfo_manager():
                action_button.place(**action_place)
            action_button.lift()
        except Exception:
            pass

    def hide_action():
        if action_button is None:
            return
        try:
            action_button.place_forget()
        except Exception:
            pass

    def inside_root():
        try:
            x, y = root.winfo_pointerxy()
            node = root.winfo_containing(x, y)
            while node is not None:
                if node is root:
                    return True
                node = getattr(node, 'master', None)
        except Exception:
            pass
        return False

    def enter(_event=None):
        after_id = pending.get('after')
        if after_id:
            try:
                root.after_cancel(after_id)
            except Exception:
                pass
            pending['after'] = None
        _safe_config(root, fg_color=hover)
        show_action()

    def finalize_leave():
        pending['after'] = None
        if not inside_root():
            _safe_config(root, fg_color=normal)
            hide_action()

    def leave(_event=None):
        try:
            pending['after'] = root.after(12, finalize_leave)
        except Exception:
            finalize_leave()

    def bind_node(node):
        try:
            node.configure(cursor='hand2')
        except Exception:
            pass
        try:
            node.bind('<Enter>', enter, add='+')
            node.bind('<Leave>', leave, add='+')
        except Exception:
            pass
        try:
            for child in node.winfo_children():
                bind_node(child)
        except Exception:
            pass

    bind_node(root)
    hide_action()


def _relative_update_text(telemetry):
    if not isinstance(telemetry, dict):
        return 'esperando'
    stamp = telemetry.get('_snapshot_timestamp') or telemetry.get('timestamp')
    try:
        age = max(0.0, time.time() - float(stamp))
    except Exception:
        return 'ahora'
    if age < 1.0:
        return '< 1 s'
    if age < 60.0:
        return f'{int(age)} s'
    return f'{age / 60.0:.1f} min'


def _section_label(parent, text):
    return ctk.CTkLabel(
        parent,
        text=text,
        height=17,
        font=(FONT, 8, 'bold'),
        text_color=COLORS['muted'],
        anchor='w',
    )


def _section_header(parent, title, subtitle):
    """Cabecera compacta de sección para dar más jerarquía al Resumen."""
    box = ctk.CTkFrame(parent, fg_color='transparent', height=30)
    box.pack_propagate(False)
    left = ctk.CTkFrame(box, fg_color='transparent')
    left.pack(side='left', fill='both', expand=True)
    ctk.CTkLabel(
        left,
        text=title,
        height=16,
        font=(FONT, 9, 'bold'),
        text_color=COLORS['text_2'],
        anchor='w',
    ).pack(anchor='w')
    ctk.CTkLabel(
        left,
        text=subtitle,
        height=14,
        font=(FONT, 8),
        text_color=COLORS['muted'],
        anchor='w',
    ).pack(anchor='w', pady=(0, 1))
    return box


def _ensure_soft_card_accent(card, accent, *, placement='left', length=0.32):
    """Aplica un acento visual suave a las tarjetas del dashboard."""
    if card is None:
        return None
    bar = getattr(card, '_soft_accent_bar', None)
    if bar is None or not bool(getattr(bar, 'winfo_exists', lambda: False)()):
        bar = ctk.CTkFrame(card, fg_color=accent, corner_radius=16)
        card._soft_accent_bar = bar
    try:
        if placement == 'top':
            bar.place(relx=0.0, rely=0.0, x=12, y=8, relwidth=max(0.18, min(0.55, length)), height=3, anchor='nw')
        else:
            bar.place(relx=0.0, rely=0.0, x=1, y=10, relheight=0.72, width=3, anchor='nw')
        bar.lift()
    except Exception:
        pass
    return bar


def _set_nav_selection_indicator(btn, active=False):
    """Acento lateral fino para que la selección del sidebar se vea más premium."""
    if btn is None:
        return None
    bar = getattr(btn, '_nav_selection_indicator', None)
    if active:
        if bar is None or not bool(getattr(bar, 'winfo_exists', lambda: False)()):
            bar = ctk.CTkFrame(btn, fg_color=COLORS['primary'], corner_radius=16)
            btn._nav_selection_indicator = bar
        try:
            bar.place(x=7, rely=0.5, anchor='w', width=3, relheight=0.52)
            bar.lift()
        except Exception:
            pass
    elif bar is not None:
        try:
            bar.place_forget()
        except Exception:
            pass
    return bar


def _set_sidebar_option_line(btn, color, *, active=False):
    """V254: sólo la opción activa usa una línea vertical fina."""
    if btn is None:
        return None
    line = getattr(btn, '_sidebar_option_line', None)
    if not active:
        if line is not None:
            try:
                line.place_forget()
            except Exception:
                pass
        return line
    try:
        exists = bool(line is not None and line.winfo_exists())
    except Exception:
        exists = False
    if not exists:
        line = ctk.CTkFrame(btn, fg_color=color, corner_radius=6)
        btn._sidebar_option_line = line
    _safe_config(line, fg_color=color)
    try:
        line.place(x=5, rely=0.5, anchor='w', width=3, relheight=0.54)
        line.lift()
    except Exception:
        pass
    return line


def _resource_soft_bg(accent):
    if accent == COLORS['green']:
        return theme_color('#0d332b')
    if accent == COLORS['purple']:
        return theme_color('#1c2752')
    return theme_color('#0d2b45')


def _resource_title_text(kind, previous_text):
    kind = str(kind or '').strip()
    previous = str(previous_text or '').strip()
    if '\n' in previous:
        return previous
    if not previous or previous.upper() == kind.upper():
        return kind
    return f'{kind}\n{previous}'


def _ensure_resource_card_decor(app, card, accent, eyebrow_text):
    """V237: tarjeta de recurso según la referencia aprobada por el usuario.

    Mantiene el borde/acento lateral actual y elimina iconos, pills y adornos.
    La jerarquía queda: componente/modelo -> porcentaje -> barra -> detalle.
    """
    if card is None:
        return
    if getattr(card, '_corepulse_reference_layout', False):
        return

    if card is app.card_cpu:
        old_title, old_value, old_bar, old_detail = app.lbl_cpu_title, app.lbl_cpu, app.bar_cpu, app.lbl_cpu_temp
    elif card is app.card_ram:
        old_title, old_value, old_bar, old_detail = app.lbl_ram_title, app.lbl_ram, app.bar_ram, app.lbl_ram_gb
    else:
        old_title, old_value, old_bar, old_detail = app.lbl_gpu_title, app.lbl_gpu, app.bar_gpu, app.lbl_gpu_temp

    try:
        title_text = _resource_title_text(eyebrow_text, old_title.cget('text'))
    except Exception:
        title_text = eyebrow_text
    try:
        value_text = str(old_value.cget('text') or 'N/A')
    except Exception:
        value_text = 'N/A'
    try:
        detail_text = str(old_detail.cget('text') or 'N/A')
    except Exception:
        detail_text = 'N/A'
    try:
        old_progress = float(old_bar.get())
    except Exception:
        old_progress = 0.0

    for child in list(card.winfo_children()):
        try:
            child.destroy()
        except Exception:
            pass

    _safe_config(
        card,
        fg_color=COLORS['surface'],
        border_color=COLORS['border'],
        border_width=1,
        corner_radius=16,
    )
    try:
        card.pack_propagate(False)
    except Exception:
        pass

    shell = ctk.CTkFrame(card, fg_color='transparent')
    shell.pack(fill='both', expand=True)

    # IMPORTANTE: se conserva exactamente el acento/borde lateral de color.
    accent_bar = ctk.CTkFrame(shell, fg_color=accent, width=4, corner_radius=14)
    accent_bar.pack(side='left', fill='y', padx=(1, 0), pady=1)
    card._corepulse_resource_accent = accent_bar

    content = ctk.CTkFrame(shell, fg_color='transparent')
    content.pack(side='left', fill='both', expand=True, padx=(12, 12), pady=(9, 8))

    title = ctk.CTkLabel(
        content, text=title_text, font=(FONT, 9, 'bold'),
        text_color=COLORS['text_2'], anchor='w', justify='left', height=30,
    )
    title.pack(fill='x', anchor='w', pady=(0, 1))

    value = ctk.CTkLabel(
        content, text=value_text, font=(FONT, 29, 'bold'),
        text_color=COLORS['text'], anchor='w', height=34,
    )
    value.pack(fill='x', anchor='w', pady=(0, 1))

    bar = ctk.CTkProgressBar(
        content, height=6, corner_radius=3,
        progress_color=accent, fg_color=COLORS['track'],
    )
    bar.set(max(0.0, min(1.0, old_progress)))
    bar.pack(fill='x', pady=(0, 5))

    detail = ctk.CTkLabel(
        content, text=detail_text, font=(FONT, 9, 'bold'),
        text_color=accent, anchor='w', justify='left', height=18,
    )
    detail.pack(fill='x', anchor='w', pady=(0, 0))

    if card is app.card_cpu:
        app.lbl_cpu_title, app.lbl_cpu, app.bar_cpu, app.lbl_cpu_temp = title, value, bar, detail
    elif card is app.card_ram:
        app.lbl_ram_title, app.lbl_ram, app.bar_ram, app.lbl_ram_gb = title, value, bar, detail
    else:
        app.lbl_gpu_title, app.lbl_gpu, app.bar_gpu, app.lbl_gpu_temp = title, value, bar, detail

    card._corepulse_reference_layout = True
    card._corepulse_status_parity = True


def _apply_resource_card_geometry(app):
    # La geometría ya está definida por la estructura tipo status-card.
    return


def _ensure_storage_card_decor(card, widgets=None, accent=None):
    """V238: tarjeta compacta por unidad y acción contextual sólo en hover.

    Cada disco conserva su propia tarjeta. El alto del viewport se decide en
    ``dashboard_layout``: 1 unidad compacta, 2 visibles completas y 3+ con
    scroll interno.
    """
    if card is None:
        return
    if getattr(card, '_corepulse_storage_v238', False):
        return

    widgets = widgets if isinstance(widgets, dict) else {}
    old_name = widgets.get('lbl_name')
    old_badge = widgets.get('lbl_badge')
    old_exact = widgets.get('lbl_exact')
    old_bar = widgets.get('bar')
    old_details = widgets.get('btn_details')

    try:
        name_text = str(old_name.cget('text') or 'Unidad de almacenamiento')
    except Exception:
        name_text = 'Unidad de almacenamiento'
    try:
        badge_text = str(old_badge.cget('text') or 'SMART N/A')
    except Exception:
        badge_text = 'SMART N/A'
    try:
        exact_text = str(old_exact.cget('text') or 'Información de capacidad: N/A')
    except Exception:
        exact_text = 'Información de capacidad: N/A'
    try:
        old_progress = float(old_bar.get())
    except Exception:
        old_progress = 0.0
    try:
        details_command = getattr(old_details, '_command', None)
    except Exception:
        details_command = None

    for child in list(card.winfo_children()):
        try:
            child.destroy()
        except Exception:
            pass

    _safe_config(
        card,
        fg_color=COLORS['surface'],
        border_color=COLORS['border'],
        border_width=1,
        corner_radius=16,
        height=86,
    )
    try:
        card.pack_propagate(False)
    except Exception:
        pass

    shell = ctk.CTkFrame(card, fg_color='transparent')
    shell.pack(fill='both', expand=True)
    storage_accent = accent or COLORS['primary']
    accent_rail = ctk.CTkFrame(shell, fg_color=storage_accent, width=4, corner_radius=14)
    accent_rail.pack(side='left', fill='y', padx=(1, 0), pady=1)

    content = ctk.CTkFrame(shell, fg_color='transparent')
    content.pack(side='left', fill='both', expand=True, padx=(12, 12), pady=(7, 7))

    top = ctk.CTkFrame(content, fg_color='transparent', height=25)
    top.pack(fill='x')
    top.pack_propagate(False)

    name = ctk.CTkLabel(
        top, text=name_text, font=(FONT, 10, 'bold'), text_color=COLORS['text'],
        anchor='w', justify='left'
    )
    name.pack(side='left', fill='x', expand=True)

    # V261: salud vuelve a ocupar el extremo derecho real de la tarjeta. En
    # V238 se reservaban 100 px adicionales para «Ver detalles» incluso cuando
    # el botón estaba oculto, por eso la insignia parecía desplazada al centro.
    # Badge y acción comparten el mismo slot: en reposo se ve la salud; al hover
    # el botón se superpone sin mover nada del layout.
    action_slot = ctk.CTkFrame(top, fg_color='transparent', width=108, height=25)
    action_slot.pack(side='right', padx=(8, 0))
    action_slot.pack_propagate(False)

    badge = ctk.CTkLabel(
        action_slot, text=badge_text, font=(FONT, 8, 'bold'), text_color=COLORS['green'],
        fg_color=COLORS['surface_2'], corner_radius=10, padx=10, pady=2, anchor='e'
    )
    badge.pack(side='right')

    exact = ctk.CTkLabel(
        content, text=exact_text, font=(FONT, 9), text_color=COLORS['primary'],
        anchor='w', justify='left', height=18
    )
    exact.pack(fill='x', pady=(3, 2))

    bar = ctk.CTkProgressBar(
        content, height=6, corner_radius=3,
        progress_color=COLORS['primary'], fg_color=COLORS['track']
    )
    bar.set(max(0.0, min(1.0, old_progress)))
    bar.pack(fill='x', pady=(0, 0))

    details = ctk.CTkButton(
        action_slot, text='Ver detalles', width=92, height=24, corner_radius=7,
        fg_color=role_color('accent_2'), hover_color=role_color('accent'),
        border_width=1, border_color=role_color('accent'), text_color=role_color('text'),
        font=(FONT, 8, 'bold'), command=details_command if callable(details_command) else None,
    )

    # La acción aparece sólo cuando el puntero está dentro de esta unidad.
    _bind_card_hover(
        card,
        action_button=details,
        action_place={'relx': 1.0, 'rely': 0.5, 'anchor': 'e'},
    )

    widgets.update({
        'lbl_name': name,
        'lbl_badge': badge,
        'lbl_exact': exact,
        'bar': bar,
        'btn_details': details,
        'details_slot': action_slot,
    })
    card._corepulse_reference_layout = True
    card._corepulse_status_parity = True
    card._corepulse_storage_v238 = True


def _ensure_chart_accents(app):
    frame = getattr(app, 'frame_charts', None)
    if frame is None:
        return
    bars = list(getattr(app, '_chart_top_accents', []) or [])
    if len(bars) != 3:
        for item in bars:
            try:
                item.destroy()
            except Exception:
                pass
        bars = []
        for color in (COLORS['primary'], COLORS['green'], COLORS['purple']):
            bars.append(ctk.CTkFrame(frame, fg_color=color, height=3, corner_radius=8))
        app._chart_top_accents = bars
    for idx, bar in enumerate(bars):
        try:
            bar.place(relx=0.012 + idx * 0.333, y=8, relwidth=0.309, height=3, anchor='nw')
            bar.lift()
        except Exception:
            pass


def _build_sidebar_toggle(app):
    """Botón flotante pegado al divisor entre sidebar y contenido."""
    button = getattr(app, '_sidebar_toggle_button', None)
    try:
        exists = bool(button is not None and button.winfo_exists())
    except Exception:
        exists = False
    if not exists:
        button = ctk.CTkButton(
            app,
            text='›' if getattr(app, '_sidebar_collapsed', False) else '‹',
            width=18,
            height=34,
            corner_radius=9,
            fg_color=COLORS['surface_2'],
            hover_color=COLORS['surface_hover'],
            border_width=1,
            border_color=COLORS['border'],
            text_color=COLORS['text'],
            font=(FONT, 15, 'bold'),
            command=getattr(app, 'toggle_sidebar_collapse', None),
        )
        app._sidebar_toggle_button = button
    else:
        _safe_config(
            button,
            text='›' if getattr(app, '_sidebar_collapsed', False) else '‹',
            command=getattr(app, 'toggle_sidebar_collapse', None),
        )
    try:
        app._position_sidebar_toggle()
    except Exception:
        pass
    return button


def _style_nav_button(btn, *, active=False, disabled=False, accent=None):
    """V254: navegación uniforme, compacta y con selección sobria."""
    accent = accent or COLORS['primary']
    if disabled:
        _safe_config(
            btn,
            fg_color='transparent',
            hover_color='transparent',
            text_color=theme_color('#5f7189'),
            border_width=0,
            corner_radius=8,
            height=36,
            font=(FONT, 10, 'bold'),
            anchor='w',
            padx=15,
        )
        _set_nav_selection_indicator(btn, False)
        _set_sidebar_option_line(btn, accent, active=False)
        return
    _safe_config(
        btn,
        fg_color=COLORS['surface_2'] if active else 'transparent',
        hover_color=COLORS['surface_2'],
        text_color=COLORS['text'] if active else SIDEBAR_INACTIVE_TEXT,
        border_width=0,
        corner_radius=8,
        height=36,
        font=(FONT, 10, 'bold'),
        anchor='w',
        padx=17 if active else 15,
    )
    _set_nav_selection_indicator(btn, False)
    _set_sidebar_option_line(btn, COLORS['primary'], active=active)

def _load_white_brand_asset(app):
    """Carga el símbolo de CorePulse para la cabecera principal.

    Desde V0.9.24.10w la marca deja de consumir altura en el sidebar. La imagen
    se mantiene como una única referencia CTkImage y se monta en el header.
    """
    try:
        path = brand_symbol_path(resource_root(), dashboard=True)
        if not path.exists():
            return
        pil_img = Image.open(path)
        app._dashboard_brand_image = ctk.CTkImage(
            light_image=pil_img,
            dark_image=pil_img,
            size=(46, 46),
        )
        # Compatibilidad con la referencia creada por main.py, pero el widget
        # queda deliberadamente fuera del layout lateral.
        icon = getattr(app, 'lbl_logo_icon', None)
        if icon is not None:
            _safe_pack_forget(icon)
            _safe_config(icon, image=app._dashboard_brand_image, text='')
    except Exception:
        pass


def _load_sidebar_icons(app):
    """Carga iconos PNG reales para evitar glifos Unicode deformados en Windows."""
    images = {}
    base = sidebar_assets_path(resource_root())
    for attr, filename in SIDEBAR_ICON_FILES.items():
        try:
            path = base / filename
            if not path.exists():
                continue
            pil = Image.open(path).convert('RGBA')
            images[attr] = ctk.CTkImage(light_image=pil, dark_image=pil, size=(20, 20))
        except Exception:
            continue
    app._dashboard_sidebar_icons = images
    return images


def _apply_sidebar_icon(app, attr, *, active=False, collapsed=False):
    button = getattr(app, attr, None)
    if button is None:
        return
    image = getattr(app, '_dashboard_sidebar_icons', {}).get(attr)
    label = SIDEBAR_LABELS.get(attr, '')
    kwargs = dict(text='' if collapsed else label, compound='left', anchor='center' if collapsed else 'w')
    if image is not None:
        kwargs['image'] = image
    _safe_config(button, **kwargs)
    _style_nav_button(button, active=active, accent=_sidebar_option_accent(attr))
    if collapsed:
        _safe_config(button, padx=0)



def _format_device_model(identity):
    """Forma un nombre visible usando solo identidad real reportada por Windows."""
    if not isinstance(identity, dict):
        return 'N/A'

    manufacturer = str(identity.get('manufacturer') or '').strip()
    model = str(identity.get('display_model') or identity.get('model') or '').strip()
    form_factor = str(identity.get('form_factor') or '').upper().strip()

    if form_factor == 'DESKTOP' and model.lower().startswith('pc de escritorio'):
        return model

    if manufacturer and model:
        if manufacturer.casefold() in model.casefold():
            return model
        return f'{manufacturer} {model}'
    if model:
        return model
    if manufacturer:
        return manufacturer

    # Para PC de escritorio, la placa madre es una identidad real útil cuando
    # Windows no expone un modelo de sistema válido.
    if form_factor == 'DESKTOP':
        board = identity.get('motherboard') if isinstance(identity.get('motherboard'), dict) else {}
        board_manufacturer = str(board.get('manufacturer') or '').strip()
        board_model = str(board.get('model') or '').strip()
        board_name = ' '.join(x for x in (board_manufacturer, board_model) if x).strip()
        if board_name:
            return f'PC · {board_name}'

    return 'N/A'


def _poll_device_identity(app):
    """Actualiza la etiqueta desde el hilo principal cuando finaliza la consulta."""
    try:
        pending = getattr(app, '_dashboard_device_identity_pending', None)
        if isinstance(pending, dict):
            app._device_identity_cache = pending
            app._dashboard_device_identity_pending = None
            try:
                if hasattr(app, '_prime_battery_presence_cache'):
                    app._prime_battery_presence_cache(pending)
            except Exception:
                pass
            _safe_config(
                getattr(app, '_header_device_model', None),
                text=_format_device_model(pending),
                text_color=COLORS['text'],
            )
            return
        if getattr(app, '_dashboard_device_identity_done', False):
            _safe_config(
                getattr(app, '_header_device_model', None),
                text='N/A',
                text_color=COLORS['muted'],
            )
            return
        app.after(120, lambda: _poll_device_identity(app))
    except Exception:
        pass


def _start_device_identity_load(app):
    """Obtiene el modelo real sin bloquear la interfaz de CorePulse."""
    cached = getattr(app, '_device_identity_cache', None)
    if isinstance(cached, dict):
        _safe_config(
            getattr(app, '_header_device_model', None),
            text=_format_device_model(cached),
            text_color=COLORS['text'],
        )
        return

    if getattr(app, '_dashboard_device_identity_loading', False):
        return

    app._dashboard_device_identity_loading = True
    app._dashboard_device_identity_done = False
    app._dashboard_device_identity_pending = None

    def worker():
        try:
            identity = collect_device_identity()
            if isinstance(identity, dict):
                app._dashboard_device_identity_pending = identity
        except Exception:
            app._dashboard_device_identity_pending = None
        finally:
            app._dashboard_device_identity_done = True

    threading.Thread(
        target=worker,
        name='CorePulseDeviceIdentityUI',
        daemon=True,
    ).start()
    app.after(120, lambda: _poll_device_identity(app))

def _build_header(app):
    """Cabecera V227: identidad centrada + estado REAL del agente a la derecha."""
    header = ctk.CTkFrame(app.main_content, fg_color='transparent', height=88)
    header.pack_propagate(False)

    hero = ctk.CTkFrame(
        header,
        fg_color='transparent',
        border_width=0,
        corner_radius=0,
        height=84,
    )
    hero.pack(fill='both', expand=True)
    hero.pack_propagate(False)
    app._header_hero = hero

    # Identidad del equipo: el icono + nombre se centran como una sola unidad.
    left = ctk.CTkFrame(hero, fg_color='transparent')
    left.pack(side='left', fill='both', expand=True, padx=(6, 8), pady=(3, 3))

    identity = ctk.CTkFrame(left, fg_color='transparent')
    identity.pack(expand=True)
    app._header_identity = identity

    _load_white_brand_asset(app)
    brand = ctk.CTkLabel(
        identity,
        text='',
        image=getattr(app, '_dashboard_brand_image', None),
        width=48,
        height=48,
    )
    brand.pack(side='left', padx=(0, 13), pady=3)
    app._header_brand_icon = brand

    device_box = ctk.CTkFrame(identity, fg_color='transparent')
    device_box.pack(side='left', pady=(0, 0))
    app._header_device_box = device_box

    app._header_eyebrow = ctk.CTkLabel(
        device_box,
        text='RESUMEN EJECUTIVO DEL EQUIPO',
        font=(FONT, 8, 'bold'),
        text_color=COLORS['primary'],
        anchor='w',
    )
    app._header_eyebrow.pack(anchor='w', pady=(2, 3))

    app._header_device_model = ctk.CTkLabel(
        device_box,
        text='Identificando modelo…',
        font=(FONT, 17, 'bold'),
        text_color=COLORS['text'],
        anchor='w',
        justify='left',
        wraplength=650,
    )
    app._header_device_model.pack(anchor='w')

    app._header_subtitle = None
    app._header_chip_row = None
    app._header_chip_live = None
    app._header_chip_data = None
    app._header_chip_focus = None

    # V259: el estado del agente deja de ocupar una tarjeta propia en el header.
    # La información importante ya está representada por Salud / Supervisión /
    # Trazabilidad y alertas. Conservamos los atributos como None para que las
    # rutas antiguas de refresco sean no-op y no creen duplicados en el sidebar.
    app._header_right_stack = None
    app._header_agent_frame = None
    app._agent_card = None
    app._agent_title = None
    app._agent_badge = None
    app._agent_dot = None
    app._agent_status = None
    app._agent_mode = None
    app._agent_state = None
    app._agent_detail = None
    app._header_agent_dot = None
    app._header_agent_text = None
    app._header_agent_hint = None
    app._header_meta = None
    # V260: V259 retiró la tarjeta del agente del header, pero el wrapper de
    # telemetría todavía referenciaba esta etiqueta. Mantener el atributo como
    # None hace que _safe_config sea un no-op y evita que la primera muestra
    # real aborte el cierre del Startup Gate en 97 %.
    app._header_last_update = None
    app._header_meta_hint = None
    app._header_agent_divider = None

    _start_device_identity_load(app)
    return header


def _status_card(parent, icon, title, *, accent, eyebrow='Módulo'):
    card = ctk.CTkFrame(
        parent,
        fg_color=COLORS['surface'],
        border_width=1,
        border_color=COLORS['border'],
        corner_radius=15,
        height=124,
    )
    card.pack_propagate(False)

    shell = ctk.CTkFrame(card, fg_color='transparent')
    shell.pack(fill='both', expand=True, padx=(0, 0), pady=(0, 0))

    side_accent = ctk.CTkFrame(shell, fg_color=accent, width=4, corner_radius=14)
    side_accent.pack(side='left', fill='y', padx=(1, 0), pady=1)

    row = ctk.CTkFrame(shell, fg_color='transparent')
    row.pack(side='left', fill='both', expand=True, padx=(12, 12), pady=(10, 11))

    icon_box = ctk.CTkLabel(
        row,
        text=icon,
        width=44,
        height=44,
        corner_radius=14,
        fg_color=theme_color('#0d2b45') if accent == COLORS['primary'] else theme_color('#0d332b') if accent == COLORS['green'] else theme_color('#152750') if accent == COLORS['purple'] else theme_color('#33260d'),
        text_color=accent,
        font=(FONT, 15, 'bold'),
    )
    icon_box.pack(side='left', padx=(0, 10))

    text_box = ctk.CTkFrame(row, fg_color='transparent')
    text_box.pack(side='left', fill='both', expand=True)
    eyebrow_label = ctk.CTkLabel(
        text_box,
        text=str(eyebrow).upper(),
        font=(FONT, 8, 'bold'),
        text_color=accent,
        anchor='w',
    )
    eyebrow_label.pack(anchor='w')
    title_label = ctk.CTkLabel(
        text_box,
        text=title,
        font=(FONT, 9, 'bold'),
        text_color=COLORS['text_2'],
        anchor='w',
    )
    title_label.pack(anchor='w', pady=(2, 0))
    value = ctk.CTkLabel(
        text_box,
        text='--',
        font=(FONT, 18, 'bold'),
        text_color=COLORS['text'],
        anchor='w',
    )
    value.pack(anchor='w', pady=(5, 0))
    detail = ctk.CTkLabel(
        text_box,
        text='',
        font=(FONT, 9),
        text_color=COLORS['text_2'],
        justify='left',
        anchor='w',
        wraplength=190,
    )
    detail.pack(anchor='w', pady=(2, 0))
    return card, icon_box, value, detail


def _build_system_band(app):
    """Jerarquía superior: estado/condición primero; datos/sesión después."""
    band = ctk.CTkFrame(app.main_content, fg_color='transparent', height=124)
    band.pack_propagate(False)
    band.grid_columnconfigure(0, weight=5, uniform='dashboard_status_primary')
    band.grid_columnconfigure(1, weight=5, uniform='dashboard_status_primary')
    band.grid_columnconfigure(2, weight=3, uniform='dashboard_status_secondary')
    band.grid_columnconfigure(3, weight=3, uniform='dashboard_status_secondary')
    band.grid_rowconfigure(0, weight=1)

    health_card, app._health_icon, app._health_status, app._health_score = _status_card(
        band,
        '✓',
        'ESTADO CONSOLIDADO',
        accent=COLORS['green'],
        eyebrow='Salud del sistema',
    )
    health_card.grid(row=0, column=0, sticky='nsew', padx=(0, 5))
    app._health_status.configure(text='EVALUANDO', text_color=COLORS['green'], justify='left', anchor='w', wraplength=185)
    app._health_score.configure(text='')
    app._health_score.pack_forget()

    alerts, app._alert_icon, app._alert_value, app._alert_detail = _status_card(
        band,
        '!',
        'CONDICIÓN Y ALERTAS',
        accent=COLORS['amber'],
        eyebrow='Supervisión actual',
    )
    alerts.grid(row=0, column=1, sticky='nsew', padx=5)
    app._alert_value.configure(text='Sin alertas activas', text_color=COLORS['green'], justify='left', anchor='w', wraplength=185)
    app._alert_detail.configure(text='')
    app._alert_detail.pack_forget()

    coverage, app._coverage_icon, app._coverage_value, app._coverage_detail = _status_card(
        band,
        '◎',
        'DATOS VÁLIDOS',
        accent=COLORS['primary'],
        eyebrow='Trazabilidad',
    )
    coverage.grid(row=0, column=2, sticky='nsew', padx=5)
    app._coverage_value.configure(text='Esperando')
    app._coverage_detail.configure(text='')
    app._coverage_detail.pack_forget()

    uptime, app._uptime_icon, app._uptime_value, app._uptime_detail = _status_card(
        band,
        '◷',
        'TIEMPO ACTIVO',
        accent=COLORS['purple'],
        eyebrow='Sesión',
    )
    uptime.grid(row=0, column=3, sticky='nsew', padx=(5, 0))
    app._uptime_value.configure(text=_uptime_text())
    app._uptime_detail.configure(text='')
    app._uptime_detail.pack_forget()

    _bind_click_tree(health_card, getattr(app, 'open_smart_alert_window', None))
    _bind_card_hover(health_card)
    _bind_click_tree(alerts, getattr(app, 'open_smart_alert_window', None))
    _bind_card_hover(alerts)
    _bind_click_tree(coverage, getattr(app, 'open_telemetry_details', None))
    _bind_card_hover(coverage)

    app._status_cards = (health_card, alerts, coverage, uptime)
    return band

def _rebuild_sidebar(app):
    # V223: no acumular labels/bloques dinámicos entre cierre y reapertura.
    # Los controles funcionales originales se conservan; todo lo creado por el
    # dashboard profesional se destruye antes de reconstruirlo.
    persistent = {
        getattr(app, 'frame_logo', None),
        getattr(app, 'lbl_subtitle', None),
        getattr(app, 'card_health_sidebar', None),
        getattr(app, 'btn_overlay', None),
        getattr(app, 'btn_benchmark', None),
        getattr(app, 'btn_diagnostic', None),
        getattr(app, 'btn_health_center', None),
        getattr(app, 'btn_pdf', None),
        getattr(app, 'btn_cleanup', None),
        getattr(app, 'btn_tweaks', None),
        getattr(app, 'btn_network', None),
        getattr(app, 'btn_smart_alerts', None),
        getattr(app, 'btn_session_trends', None),
        getattr(app, 'btn_alert_history', None),
    }
    for child in list(app.sidebar.winfo_children()):
        try:
            if child in persistent:
                child.pack_forget()
            else:
                child.destroy()
        except Exception:
            pass

    for attr in ('_btn_summary', '_theme_toggle_button', '_update_button', '_personalization_block',
                 '_personalization_label', '_personalization_hint', '_personalization_divider', '_sidebar_version',
                 '_sidebar_top_controls', '_sidebar_menu_button', '_sidebar_close_button'):
        try:
            setattr(app, attr, None)
        except Exception:
            pass

    collapsed = False
    try:
        sidebar_width = int(app._sidebar_target_width())
    except Exception:
        sidebar_width = 232
    _safe_config(app.sidebar, fg_color=COLORS['sidebar'], width=sidebar_width)

    _safe_pack_forget(app.frame_logo)
    _safe_pack_forget(getattr(app, 'lbl_logo_icon', None))
    _safe_pack_forget(app.lbl_brand)
    _safe_config(app.lbl_brand, text='')
    _safe_pack_forget(app.lbl_subtitle)
    _safe_config(app.lbl_subtitle, text='')
    _safe_pack_forget(app.card_health_sidebar)

    app._sidebar_brand_title = None
    app._sidebar_brand_company = None
    app._sidebar_brand_block = None
    app._sidebar_brand_rule = None

    # V224: retirar cualquier flecha/widget flotante heredado de V212–V223.
    old_toggle = getattr(app, '_sidebar_toggle_button', None)
    if old_toggle is not None:
        try:
            old_toggle.place_forget()
            old_toggle.destroy()
        except Exception:
            pass
    app._sidebar_toggle_button = None

    # V254: control de cierre como glifo suelto, sin botón ni fondo.
    top_controls = ctk.CTkFrame(app.sidebar, fg_color='transparent', height=30)
    top_controls.pack(fill='x', padx=14, pady=(10, 4))
    top_controls.pack_propagate(False)
    app._sidebar_top_controls = top_controls
    app._sidebar_menu_button = None

    close_button = ctk.CTkLabel(
        top_controls,
        text='✕',
        width=30,
        height=30,
        fg_color='transparent',
        text_color=COLORS['text_2'],
        font=(FONT, 15, 'bold'),
        anchor='center',
    )
    _bind_sidebar_glyph(close_button, getattr(app, 'toggle_sidebar_collapse', None))
    close_button.pack(side='left')
    app._sidebar_close_button = close_button

    monitor = _section_label(app.sidebar, 'MONITOREO')
    monitor.pack(fill='x', padx=17, pady=(8, 4))
    _load_sidebar_icons(app)

    app._btn_summary = ctk.CTkButton(app.sidebar, text='Resumen', command=lambda: None)
    _apply_sidebar_icon(app, '_btn_summary', active=True, collapsed=False)
    app._btn_summary.pack(fill='x', padx=10, pady=1)

    _apply_sidebar_icon(app, 'btn_benchmark', collapsed=False)
    app.btn_benchmark.pack(fill='x', padx=10, pady=(1, 4))

    diagnosis = _section_label(app.sidebar, 'DIAGNÓSTICO')
    diagnosis.pack(fill='x', padx=17, pady=(12, 4))
    _apply_sidebar_icon(app, 'btn_diagnostic', collapsed=False)
    app.btn_diagnostic.pack(fill='x', padx=10, pady=1)
    _apply_sidebar_icon(app, 'btn_health_center', collapsed=False)
    app.btn_health_center.pack(fill='x', padx=10, pady=1)
    _safe_pack_forget(app.btn_pdf)

    maintenance = _section_label(app.sidebar, 'MANTENIMIENTO')
    maintenance.pack(fill='x', padx=17, pady=(12, 4))
    _apply_sidebar_icon(app, 'btn_cleanup', collapsed=False)
    app.btn_cleanup.pack(fill='x', padx=10, pady=1)
    _apply_sidebar_icon(app, 'btn_tweaks', collapsed=False)
    app.btn_tweaks.pack(fill='x', padx=10, pady=1)
    _apply_sidebar_icon(app, 'btn_network', collapsed=False)
    app.btn_network.pack(fill='x', padx=10, pady=1)

    history = _section_label(app.sidebar, 'HISTORIAL')
    history.pack(fill='x', padx=17, pady=(12, 4))
    _apply_sidebar_icon(app, 'btn_smart_alerts', collapsed=False)
    app.btn_smart_alerts.pack(fill='x', padx=10, pady=1)
    _apply_sidebar_icon(app, 'btn_session_trends', collapsed=False)
    app.btn_session_trends.pack(fill='x', padx=10, pady=1)
    _apply_sidebar_icon(app, 'btn_alert_history', collapsed=False)
    app.btn_alert_history.pack(fill='x', padx=10, pady=1)

    personalization_block = ctk.CTkFrame(
        app.sidebar,
        fg_color='transparent',
        border_width=0,
        corner_radius=0,
    )
    app._personalization_block = personalization_block

    personalization = _section_label(personalization_block, 'PERSONALIZACIÓN')
    app._personalization_label = personalization
    personalization.pack(fill='x', padx=17, pady=(7, 1))
    # V256: se elimina el subtítulo visual "Apariencia y versión".
    # Se conserva el atributo por compatibilidad con el layout responsivo.
    app._personalization_hint = None

    app._theme_toggle_button = ctk.CTkButton(
        personalization_block,
        text='◉  Temas',
        height=34,
        corner_radius=8,
        fg_color='transparent',
        hover_color=COLORS['surface_2'],
        border_width=0,
        border_color=COLORS['purple'],
        text_color=COLORS['text_2'],
        font=(FONT, 9, 'bold'),
        anchor='w',
        command=getattr(app, 'open_themes', None),
    )
    app._theme_toggle_button.pack(fill='x', padx=12, pady=(0, 2))

    app._update_button = ctk.CTkButton(
        personalization_block,
        text='↻  Actualizaciones',
        height=34,
        corner_radius=8,
        fg_color='transparent',
        hover_color=COLORS['surface_2'],
        border_width=0,
        border_color=COLORS['primary'],
        text_color=COLORS['text_2'],
        font=(FONT, 9, 'bold'),
        anchor='w',
        command=getattr(app, 'open_update_center', None),
    )
    app._update_button.pack(fill='x', padx=12, pady=(2, 4))

    divider = ctk.CTkFrame(personalization_block, fg_color='transparent', height=0, corner_radius=0)
    divider.pack_forget()
    app._personalization_divider = divider

    app._sidebar_version = ctk.CTkLabel(
        personalization_block,
        text='',
        height=14,
        font=(FONT, 7),
        text_color=COLORS['muted'],
        anchor='w',
    )
    app._sidebar_version.pack(fill='x', padx=17, pady=(3, 8))
    personalization_block.pack(side='bottom', fill='x', padx=0, pady=(6, 10))

    _sync_sidebar_visibility_controls(app)


def _style_existing_cards(app):
    specs = (
        (app.card_cpu, app.lbl_cpu_title, app.lbl_cpu, app.lbl_cpu_temp, app.bar_cpu, COLORS['primary']),
        (app.card_ram, app.lbl_ram_title, app.lbl_ram, app.lbl_ram_gb, app.bar_ram, COLORS['green']),
        (app.card_gpu, app.lbl_gpu_title, app.lbl_gpu, app.lbl_gpu_temp, app.bar_gpu, COLORS['purple']),
    )
    for card, title, value, detail, bar, accent in specs:
        _safe_config(
            card,
            fg_color=COLORS['surface'],
            border_color=COLORS['border'],
            border_width=1,
            corner_radius=16,
        )
        _safe_config(title, font=(FONT, 9, 'bold'), text_color=COLORS['text_2'], justify='left', anchor='w')
        _safe_config(value, font=(FONT, 30, 'bold'), text_color=COLORS['text'])
        _safe_config(detail, font=(FONT, 9, 'bold'), text_color=accent)
        _safe_config(bar, height=6, progress_color=accent, fg_color=COLORS['track'])
        _ensure_resource_card_decor(app, card, accent, 'CPU' if card is app.card_cpu else 'MEMORIA RAM' if card is app.card_ram else 'GPU')


    # La ficha CPU es navegable y expone una acción explícita con el mismo
    # lenguaje visual del Dashboard. El botón no usa flechas ni símbolos ajenos
    # a la identidad de CorePulse.
    cpu_callback = getattr(app, 'open_cpu_details', None)
    if callable(cpu_callback):
        _bind_click_tree(app.card_cpu, cpu_callback)
        if getattr(app, '_cpu_details_button', None) is None:
            app._cpu_details_button = ctk.CTkButton(
                app.card_cpu,
                text='Ver detalles',
                width=92,
                height=24,
                corner_radius=7,
                fg_color=role_color('accent_2'),
                hover_color=role_color('accent'),
                border_width=1,
                border_color=role_color('accent'),
                text_color=role_color('text'),
                font=(FONT, 8, 'bold'),
                command=cpu_callback,
            )
        _safe_config(app.lbl_cpu_title, wraplength=285)
        _bind_card_hover(
            app.card_cpu,
            action_button=app._cpu_details_button,
            action_place={'relx': 1.0, 'rely': 0.0, 'x': -10, 'y': 8, 'anchor': 'ne'},
        )

    # RAM completa la simetría de las tres tarjetas principales. La ficha completa
    # se alimenta del snapshot certificado y carga el inventario Windows/SMBIOS
    # fuera del hilo gráfico para conservar una navegación fluida.
    ram_callback = getattr(app, 'open_ram_details', None)
    if callable(ram_callback):
        _bind_click_tree(app.card_ram, ram_callback)
        if getattr(app, '_ram_details_button', None) is None:
            app._ram_details_button = ctk.CTkButton(
                app.card_ram,
                text='Ver detalles',
                width=92,
                height=24,
                corner_radius=7,
                fg_color=role_color('accent_2'),
                hover_color=role_color('accent'),
                border_width=1,
                border_color=role_color('accent'),
                text_color=role_color('text'),
                font=(FONT, 8, 'bold'),
                command=ram_callback,
            )
        _safe_config(app.lbl_ram_title, wraplength=285)
        _bind_card_hover(
            app.card_ram,
            action_button=app._ram_details_button,
            action_place={'relx': 1.0, 'rely': 0.0, 'x': -10, 'y': 8, 'anchor': 'ne'},
        )

    # La ficha GPU usa exactamente el mismo patrón visual y de navegación que CPU.
    # No prioriza marcas: la vista selecciona inicialmente la GPU representativa por
    # actividad real y permite cambiar entre todos los adaptadores detectados.
    gpu_callback = getattr(app, 'open_gpu_details', None)
    if callable(gpu_callback):
        _bind_click_tree(app.card_gpu, gpu_callback)
        if getattr(app, '_gpu_details_button', None) is None:
            app._gpu_details_button = ctk.CTkButton(
                app.card_gpu,
                text='Ver detalles',
                width=92,
                height=24,
                corner_radius=7,
                fg_color=role_color('accent_2'),
                hover_color=role_color('accent'),
                border_width=1,
                border_color=role_color('accent'),
                text_color=role_color('text'),
                font=(FONT, 8, 'bold'),
                command=gpu_callback,
            )
        _safe_config(app.lbl_gpu_title, wraplength=285)
        _bind_card_hover(
            app.card_gpu,
            action_button=app._gpu_details_button,
            action_place={'relx': 1.0, 'rely': 0.0, 'x': -10, 'y': 8, 'anchor': 'ne'},
        )

    _apply_resource_card_geometry(app)


def _series_stats(values):
    clean = []
    for value in values or []:
        try:
            number = float(value)
        except Exception:
            continue
        if math.isfinite(number):
            clean.append(number)
    if not clean:
        return None
    return {
        'average': sum(clean) / len(clean),
        'peak': max(clean),
    }


def _update_trend_titles(app):
    """Mantiene títulos limpios; promedio/pico quedan fuera del Resumen.

    El detalle estadístico completo pertenece a Tendencias. El Resumen sólo
    necesita mostrar la forma de la serie para evitar duplicación de datos.
    """
    titles = (
        (app.ax_cpu, 'CPU (%)', COLORS['primary']),
        (app.ax_ram, 'RAM (%)', COLORS['green']),
        (app.ax_gpu, 'GPU (%)', COLORS['purple']),
    )
    for ax, text, color in titles:
        try:
            ax.set_title(text, color=color, fontsize=9, fontweight='bold', pad=8)
        except Exception:
            pass


def _apply_chart_geometry_alignment(app):
    """Delega la geometría a la autoridad responsiva del dashboard.

    `dashboard_layout` calcula el alto útil de la tarjeta, descuenta la cabecera
    real y redimensiona el FigureCanvas para que los gráficos se mantengan
    legibles tanto en ventanas compactas como amplias.
    """
    try:
        from gui.dashboard_layout import request_chart_reflow
        request_chart_reflow(app, redraw=False)
    except Exception:
        pass


def _style_charts(app):
    _safe_config(
        app.frame_charts,
        fg_color=COLORS['surface'],
        border_color=COLORS['border'],
        border_width=1,
        corner_radius=0,
    )
    try:
        _ensure_chart_accents(app)
        app.fig.set_facecolor(COLORS['surface'])
        axes = (app.ax_cpu, app.ax_ram, app.ax_gpu)
        for ax in axes:
            ax.set_facecolor(COLORS['surface'])
            ax.tick_params(axis='x', colors=COLORS['muted'], labelsize=8, length=0, pad=6)
            ax.tick_params(axis='y', colors=COLORS['muted'], labelsize=8, length=0, pad=6, labelleft=True)
            ax.grid(False)
            ax.yaxis.grid(True, color=COLORS['border_soft'], linestyle='-', linewidth=0.55, alpha=0.72)
            ax.set_axisbelow(True)
            ax.set_yticks([25, 50, 75, 100])
            ax.set_xticks([0, 6, 12, 18, 24])
            ax.set_xticklabels(['-60s', '-45s', '-30s', '-15s', 'Ahora'])
            ax.margins(x=0.02, y=0.10)
            for side, spine in ax.spines.items():
                spine.set_visible(True)
                spine.set_linewidth(1.0 if side in ('left', 'bottom') else 0.8)
                spine.set_color(COLORS['border'] if side in ('left', 'bottom') else COLORS['border_soft'])
        _update_trend_titles(app)
        _apply_chart_geometry_alignment(app)
        app.background = None
        app.canvas.draw_idle()
    except Exception:
        pass

def _rebuild_main_layout(app):
    children = list(app.main_content.winfo_children())
    storage_label = None
    for child in children:
        try:
            if isinstance(child, ctk.CTkLabel) and 'UNIDADES DE ALMACENAMIENTO' in str(child.cget('text')):
                storage_label = child
        except Exception:
            pass

    for child in children:
        _safe_pack_forget(child)

    app._header = _build_header(app)
    app._header.pack(fill='x', pady=(0, 7))

    app._status_band = _build_system_band(app)
    app._status_band.pack(fill='x', pady=(0, 8))

    if getattr(app, '_resources_section', None) is not None:
        _safe_pack_forget(app._resources_section)
    app.frame_meters.pack(fill='x', pady=(0, 10))
    _safe_pack_forget(app.alert_summary_bar)

    if getattr(app, '_storage_section_header', None) is not None:
        _safe_pack_forget(app._storage_section_header)
    if storage_label is not None:
        try:
            storage_label.pack_forget()
        except Exception:
            pass

    _safe_config(app.scroll_disks, fg_color='transparent')
    try:
        # V0.10.2.28w: impedir que el Canvas interno del viewport de discos
        # vuelva a imponer su altura solicitada durante reconstrucciones visuales.
        app.scroll_disks.grid_propagate(False)
    except Exception:
        pass
    app.scroll_disks.pack(fill='x', expand=False, pady=(0, 10))

    if getattr(app, '_trends_section_header', None) is not None:
        _safe_pack_forget(app._trends_section_header)
    app.frame_charts.pack(fill='x', expand=False, pady=(0, 0))

    _style_existing_cards(app)
    _style_charts(app)
    _ensure_soft_card_accent(app.frame_charts, COLORS['primary'], placement='left')


def _wrap_telemetry_update(app):
    if getattr(app, '_dashboard_telemetry_wrapped', False):
        return
    original = app.apply_telemetry_to_ui

    def wrapped(self, telemetry, disks):
        original(telemetry, disks)

        # Reorganiza únicamente las etiquetas visuales; no modifica los datos.
        if isinstance(telemetry, dict):
            cpu_name = telemetry.get('cpu_name') or 'N/A'
            gpu_name = telemetry.get('gpu_name') or 'N/A'
            _safe_config(self.lbl_cpu_title, text=f'CPU\n{cpu_name}')
            _safe_config(self.lbl_ram_title, text='MEMORIA RAM\nUso físico del sistema')
            _safe_config(self.lbl_gpu_title, text=f'GPU\n{gpu_name}')

        _apply_resource_card_geometry(self)

        # La salud/alertas finales son autoridad de `live_health_binding`, que
        # corre después de este wrapper. Aquí sólo dejamos un fallback de carga
        # inicial y evitamos volver a declarar 'ÓPTIMO' a partir de un score viejo
        # cuando el agente ya observa una condición instantánea más severa.
        if not isinstance(getattr(self, 'current_live_health', None), dict):
            score = getattr(self, 'latest_score', None)
            color = _status_color(score)
            name = _status_name(score)
            _safe_config(self._health_status, text=name, text_color=color)
            _safe_config(self._health_score, text=f'Índice técnico {float(score):.1f}%' if isinstance(score, (int, float)) else 'Índice técnico N/A')
            _safe_config(self._health_icon, text='✓' if name in {'ÓPTIMO', 'ESTABLE'} else '!', text_color=color)

        _update_trend_titles(self)

        valid, total = _telemetry_coverage(telemetry)
        if total:
            _safe_config(
                self._coverage_value,
                text=f'{valid} / {total} VÁLIDAS',
                text_color=COLORS['green'] if valid == total else COLORS['primary'],
            )
            _safe_config(self._coverage_detail, text='Métricas certificadas')
        else:
            _safe_config(self._coverage_value, text='N/A', text_color=COLORS['muted'])
            _safe_config(self._coverage_detail, text='Sin metadata de certificación')

        _safe_config(self._uptime_value, text=_uptime_text())
        _safe_config(
            getattr(self, '_header_last_update', None),
            text=f'Última actualización: {_relative_update_text(telemetry)}',
        )

    app.apply_telemetry_to_ui = types.MethodType(wrapped, app)
    app._dashboard_telemetry_wrapped = True


def _wrap_disk_update(app):
    if getattr(app, '_dashboard_disks_wrapped', False):
        return
    original = app.update_disks_ui

    def wrapped(self, disks_data):
        original(disks_data)
        by_index = {}
        for d in disks_data or []:
            try:
                by_index[d.get('index')] = d
            except Exception:
                pass

        for idx, widgets in getattr(self, 'disk_widgets', {}).items():
            d = by_index.get(idx, {})
            _safe_config(
                widgets.get('card'),
                fg_color=COLORS['surface'],
                border_color=COLORS['border'],
                border_width=1,
                corner_radius=16,
            )
            _ensure_storage_card_decor(widgets.get('card'), widgets)
            _safe_config(widgets.get('bar'), progress_color=COLORS['primary'], fg_color=COLORS['track'], height=6)
            _safe_config(
                widgets.get('btn_details'),
                command=lambda disk_index=idx: self.open_storage_details(disk_index),
            )

            model = d.get('model') or 'Unidad de almacenamiento'
            mounts = d.get('mount_points') or 'N/A'
            _safe_config(
                widgets.get('lbl_name'),
                text=f'{model}   ·   {mounts}',
                text_color=COLORS['text'],
                font=(FONT, 10, 'bold'),
            )


            try:
                smart = d.get('health_percent')
            except Exception:
                smart = None
            badge_text = 'SMART N/A'
            badge_color = COLORS['surface_2']
            badge_text_color = COLORS['muted']
            if isinstance(smart, (int, float)):
                smart_val = float(smart)
                badge_text = f'SMART {smart_val:.0f}%'
                if smart_val >= 90:
                    badge_color = role_color('ok_bg')
                    badge_text_color = COLORS['green']
                elif smart_val >= 70:
                    badge_color = role_color('warn_bg')
                    badge_text_color = COLORS['amber']
                else:
                    badge_color = role_color('bad_bg')
                    badge_text_color = COLORS['red']
            _safe_config(
                widgets.get('lbl_badge'),
                text=badge_text,
                fg_color=badge_color,
                text_color=badge_text_color,
                corner_radius=10,
                padx=10,
                pady=2,
                font=(FONT, 8, 'bold'),
            )

            try:
                used_raw = d.get('used_gb')
                total_raw = d.get('total_gb')
                pct_raw = d.get('used_percent')
                temp = d.get('temperature_c')

                if isinstance(used_raw, (int, float)) and isinstance(total_raw, (int, float)) and total_raw > 0:
                    used = float(used_raw)
                    total = float(total_raw)
                    available = max(0.0, total - used)
                    pct = float(pct_raw) if isinstance(pct_raw, (int, float)) else (used / total * 100.0)
                    capacity = f'Usado {used:.0f} GB  ·  Disponible {available:.0f} GB  ·  {pct:.1f}%'
                else:
                    capacity = 'Información de capacidad: N/A'

                if isinstance(temp, (int, float)):
                    capacity += f'  ·  {float(temp):.0f} °C'
                else:
                    capacity += '  ·  N/A °C'

                _safe_config(
                    widgets.get('lbl_exact'),
                    text=capacity,
                    text_color=COLORS['primary'],
                    font=(FONT, 9),
                )
            except Exception:
                pass

        try:
            from gui.dashboard_layout import _finalize_storage_viewport
            _finalize_storage_viewport(self, getattr(self, '_layout_mode', 'compact'))
        except Exception:
            pass

    app.update_disks_ui = types.MethodType(wrapped, app)
    app._dashboard_disks_wrapped = True


def _apply_window_contract(app):
    # No cambia geometría ni tamaño. Solo conserva el título y la paleta.
    app.title('CorePulse — Hardware Monitoring & Diagnostics')
    _safe_config(app, fg_color=COLORS['app'])
    _safe_config(app.main_content, fg_color='transparent')


def apply_professional_dashboard(app):
    """Aplica el rediseño visual sin alterar el pipeline funcional de CorePulse."""
    if getattr(app, '_professional_ui_active', False):
        return
    _apply_window_contract(app)
    _rebuild_sidebar(app)
    _rebuild_main_layout(app)
    _wrap_telemetry_update(app)
    _wrap_disk_update(app)
    app._professional_ui_active = True
    app._corepulse_design_id = DESIGN_ID


def refresh_professional_charts(app):
    """Aplica el estilo 60w a gráficos creados de forma diferida en 61w."""
    _style_charts(app)

