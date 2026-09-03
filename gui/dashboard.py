"""Construye la presentación visual del Dashboard principal de CorePulse.

Este módulo SOLO modifica presentación. No obtiene telemetría, no altera valores,
no calcula salud y no reemplaza ninguna autoridad de diagnóstico. Los widgets
siguen consumiendo exactamente los mismos datos reales del runtime.
"""
from __future__ import annotations
from core.theme_manager import color as theme_color, brand_symbol_path, sidebar_assets_path, theme_action_label

import time
import types
import threading
from pathlib import Path

import psutil
import customtkinter as ctk
from PIL import Image

from core.version import VERSION_LABEL
from core.device_identity import collect_device_identity

VERSION = VERSION_LABEL
DESIGN_ID = 'COREPULSE_DASHBOARD_REFERENCE'

# Paleta tomada de la referencia aprobada por el usuario.
COLORS = {
    'app': theme_color('#06111f'),
    'sidebar': theme_color(theme_color('#071522')),
    'surface': theme_color('#0b1726'),
    'surface_2': theme_color('#0e1d2f'),
    'surface_hover': theme_color(theme_color('#102840')),
    'border': theme_color('#17314d'),
    'border_soft': theme_color(theme_color('#102943')),
    'text': theme_color('#f4f7fb'),
    'text_2': theme_color('#c2ccda'),
    'muted': theme_color('#8295ad'),
    'primary': '#08aef0',
    'primary_dark': theme_color('#124f80'),
    'green': '#16d98b',
    'amber': '#f3b54a',
    'red': '#ff5d6c',
    'purple': '#a064ff',
    'track': theme_color(theme_color('#132741')),
}
FONT = 'Segoe UI'
SIDEBAR_ICON_FILES = {
    '_btn_summary': 'summary.png',
    'btn_overlay': 'overlay.png',
    'btn_diagnostic': 'diagnostic.png',
    'btn_health_center': 'diagnostic.png',
    'btn_cleanup': 'cleanup.png',
    'btn_tweaks': 'tweaks.png',
    'btn_network': 'network.png',
    'btn_smart_alerts': 'alerts.png',
    'btn_session_trends': 'trends.png',
    'btn_alert_history': 'history.png',
}
SIDEBAR_LABELS = {
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


def _safe_config(widget, **kwargs):
    try:
        widget.configure(**kwargs)
    except Exception:
        pass


def _safe_pack_forget(widget):
    try:
        widget.pack_forget()
    except Exception:
        pass


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


def _bind_card_hover(root, *, normal=None, hover=None):
    """Feedback estable incluso al mover el puntero entre hijos de una tarjeta."""
    if root is None:
        return
    normal = normal or COLORS['surface']
    hover = hover or COLORS['surface_hover']
    pending = {'after': None}

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

    def finalize_leave():
        pending['after'] = None
        if not inside_root():
            _safe_config(root, fg_color=normal)

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
        font=(FONT, 9, 'bold'),
        text_color=COLORS['muted'],
        anchor='w',
    )


def _style_nav_button(btn, *, active=False, disabled=False):
    if disabled:
        _safe_config(
            btn,
            fg_color='transparent',
            hover_color=COLORS['surface'],
            text_color=theme_color('#5f7189'),
            border_width=0,
            corner_radius=8,
            height=36,
            font=(FONT, 10, 'bold'),
            anchor='w',
        )
        return
    _safe_config(
        btn,
        fg_color=theme_color('#164f7d') if active else 'transparent',
        hover_color=theme_color('#1b5c8f') if active else COLORS['surface_hover'],
        text_color=COLORS['text'],
        border_width=0,
        corner_radius=8,
        height=36,
        font=(FONT, 10, 'bold'),
        anchor='w',
    )


def _load_white_brand_asset(app):
    """Carga el símbolo de CorePulse para la cabecera principal.

    Desde V0.9.24.10w la marca deja de consumir altura en el sidebar. La imagen
    se mantiene como una única referencia CTkImage y se monta en el header.
    """
    try:
        path = brand_symbol_path(Path(__file__).resolve().parents[1], dashboard=True)
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
    base = sidebar_assets_path(Path(__file__).resolve().parents[1])
    for attr, filename in SIDEBAR_ICON_FILES.items():
        try:
            path = base / filename
            if not path.exists():
                continue
            pil = Image.open(path).convert('RGBA')
            images[attr] = ctk.CTkImage(light_image=pil, dark_image=pil, size=(17, 17))
        except Exception:
            continue
    app._dashboard_sidebar_icons = images
    return images


def _apply_sidebar_icon(app, attr, *, active=False):
    button = getattr(app, attr, None)
    if button is None:
        return
    image = getattr(app, '_dashboard_sidebar_icons', {}).get(attr)
    label = SIDEBAR_LABELS.get(attr, '')
    kwargs = dict(text=label, compound='left', anchor='w')
    if image is not None:
        kwargs['image'] = image
    _safe_config(button, **kwargs)
    _style_nav_button(button, active=active)



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
    header = ctk.CTkFrame(app.main_content, fg_color='transparent', height=72)
    header.pack_propagate(False)

    # La marca y la identidad del equipo comparten una sola cabecera. Esto
    # libera el sidebar para navegación y evita comprimir la tarjeta del agente.
    identity = ctk.CTkFrame(header, fg_color='transparent')
    # V0.9.24.10w: la identidad se separa del borde del contenido para que el
    # símbolo respire y quede visualmente alineado con el dashboard.
    identity.pack(side='left', fill='both', expand=True, padx=(34, 18))
    app._header_identity = identity

    _load_white_brand_asset(app)
    brand = ctk.CTkLabel(
        identity,
        text='',
        image=getattr(app, '_dashboard_brand_image', None),
        width=50,
        height=50,
    )
    brand.pack(side='left', padx=(4, 14), pady=(9, 7))
    app._header_brand_icon = brand

    device_box = ctk.CTkFrame(identity, fg_color='transparent')
    device_box.pack(side='left', fill='both', expand=True)
    app._header_device_box = device_box

    app._header_device_model = ctk.CTkLabel(
        device_box,
        text='Identificando modelo…',
        font=(FONT, 13, 'bold'),
        text_color=COLORS['text_2'],
        anchor='w',
        justify='left',
        wraplength=660,
    )
    app._header_device_model.pack(fill='x', anchor='w', pady=(24, 0))

    right = ctk.CTkFrame(header, fg_color='transparent')
    right.pack(side='right', pady=(5, 0))

    agent = ctk.CTkFrame(
        right,
        fg_color=COLORS['surface'],
        border_width=1,
        border_color=COLORS['border_soft'],
        corner_radius=10,
        height=48,
    )
    agent.pack(side='left', padx=(0, 12))
    agent.pack_propagate(False)

    dot = ctk.CTkLabel(
        agent,
        text='●',
        font=(FONT, 12, 'bold'),
        text_color=COLORS['green'],
        width=18,
    )
    dot.pack(side='left', padx=(11, 4), pady=7)
    agent_text = ctk.CTkLabel(
        agent,
        text='Monitoreo activo\nAgente en ejecución',
        justify='left',
        anchor='w',
        font=(FONT, 9, 'bold'),
        text_color=COLORS['text'],
        width=112,
    )
    agent_text.pack(side='left', padx=(0, 11), pady=7)

    app._header_agent_frame = agent
    app._header_agent_dot = dot
    app._header_agent_text = agent_text
    app._header_last_update = ctk.CTkLabel(
        right,
        text='Última actualización: esperando',
        font=(FONT, 9),
        text_color=COLORS['muted'],
    )
    app._header_last_update.pack(side='left', padx=(0, 2))

    _start_device_identity_load(app)
    return header


def _status_card(parent, icon, title, *, accent):
    card = ctk.CTkFrame(
        parent,
        fg_color=COLORS['surface'],
        border_width=1,
        border_color=COLORS['border'],
        corner_radius=13,
        height=106,
    )
    card.pack_propagate(False)

    row = ctk.CTkFrame(card, fg_color='transparent')
    row.pack(fill='both', expand=True, padx=15, pady=14)

    icon_box = ctk.CTkLabel(
        row,
        text=icon,
        width=43,
        height=43,
        corner_radius=21,
        fg_color=theme_color('#0d2b45') if accent == COLORS['primary'] else theme_color('#0d332b') if accent == COLORS['green'] else theme_color(theme_color('#152750')),
        text_color=accent,
        font=(FONT, 19, 'bold'),
    )
    icon_box.pack(side='left', padx=(0, 12))

    text_box = ctk.CTkFrame(row, fg_color='transparent')
    text_box.pack(side='left', fill='both', expand=True)
    ctk.CTkLabel(
        text_box,
        text=title,
        font=(FONT, 8, 'bold'),
        text_color=COLORS['text_2'],
        anchor='w',
    ).pack(anchor='w')
    value = ctk.CTkLabel(
        text_box,
        text='--',
        font=(FONT, 15, 'bold'),
        text_color=COLORS['text'],
        anchor='w',
    )
    value.pack(anchor='w', pady=(3, 0))
    detail = ctk.CTkLabel(
        text_box,
        text='',
        font=(FONT, 8),
        text_color=COLORS['text_2'],
        justify='left',
        anchor='w',
        wraplength=205,
    )
    detail.pack(anchor='w', pady=(2, 0))
    return card, icon_box, value, detail


def _build_system_band(app):
    """Crea las cuatro tarjetas superiores como piezas independientes."""
    band = ctk.CTkFrame(app.main_content, fg_color='transparent', height=106)
    band.pack_propagate(False)

    health_card, app._health_icon, app._health_status, app._health_score = _status_card(
        band,
        '✓',
        'ESTADO ACTUAL',
        accent=COLORS['green'],
    )
    health_card.pack(side='left', fill='both', expand=True, padx=(0, 5))
    app._health_status.configure(text='EVALUANDO', text_color=COLORS['green'])
    app._health_score.configure(text='Índice técnico N/A')

    alerts, app._alert_icon, app._alert_value, app._alert_detail = _status_card(
        band,
        '✓',
        'ALERTAS',
        accent=COLORS['primary'],
    )
    alerts.pack(side='left', fill='both', expand=True, padx=5)
    app._alert_value.configure(text='Sin alertas activas', text_color=COLORS['green'])
    app._alert_detail.configure(text='Todo funcionando correctamente')

    coverage, app._coverage_icon, app._coverage_value, app._coverage_detail = _status_card(
        band,
        '◆',
        'COBERTURA DE TELEMETRÍA',
        accent=COLORS['primary'],
    )
    coverage.pack(side='left', fill='both', expand=True, padx=5)
    app._coverage_value.configure(text='Esperando')
    app._coverage_detail.configure(text='Métricas certificadas · clic para inspeccionar')
    _bind_click_tree(health_card, getattr(app, 'open_smart_alert_window', None))
    _bind_card_hover(health_card)
    _bind_click_tree(alerts, getattr(app, 'open_smart_alert_window', None))
    _bind_card_hover(alerts)
    _bind_click_tree(coverage, getattr(app, 'open_telemetry_details', None))
    _bind_card_hover(coverage)

    uptime, app._uptime_icon, app._uptime_value, app._uptime_detail = _status_card(
        band,
        '◷',
        'TIEMPO DE ACTIVIDAD',
        accent=COLORS['primary'],
    )
    uptime.pack(side='left', fill='both', expand=True, padx=(5, 0))
    app._uptime_value.configure(text=_uptime_text())
    app._uptime_detail.configure(text='Desde el último reinicio')

    app._status_cards = (health_card, alerts, coverage, uptime)
    return band


def _rebuild_sidebar(app):
    for child in list(app.sidebar.winfo_children()):
        _safe_pack_forget(child)

    _safe_config(app.sidebar, fg_color=COLORS['sidebar'], width=248)

    # V0.9.24.10w: el sidebar queda dedicado exclusivamente a navegación.
    # La marca se mueve al header principal para recuperar altura útil.
    _safe_pack_forget(app.frame_logo)
    _safe_pack_forget(getattr(app, 'lbl_logo_icon', None))
    _safe_pack_forget(app.lbl_brand)
    _safe_config(app.lbl_brand, text='')
    _safe_pack_forget(app.lbl_subtitle)
    _safe_config(app.lbl_subtitle, text='')
    _safe_pack_forget(app.card_health_sidebar)

    monitor = _section_label(app.sidebar, 'MONITOREO')
    monitor.pack(fill='x', padx=20, pady=(4, 4))

    _load_sidebar_icons(app)

    app._btn_summary = ctk.CTkButton(app.sidebar, text='Resumen', command=lambda: None)
    _apply_sidebar_icon(app, '_btn_summary', active=True)
    app._btn_summary.pack(fill='x', padx=13, pady=1)

    _apply_sidebar_icon(app, 'btn_overlay')
    app.btn_overlay.pack(fill='x', padx=13, pady=1)

    diagnosis = _section_label(app.sidebar, 'DIAGNÓSTICO')
    diagnosis.pack(fill='x', padx=20, pady=(13, 5))
    _apply_sidebar_icon(app, 'btn_diagnostic')
    app.btn_diagnostic.pack(fill='x', padx=13, pady=1)
    _apply_sidebar_icon(app, 'btn_health_center')
    app.btn_health_center.pack(fill='x', padx=13, pady=1)
    _safe_pack_forget(app.btn_pdf)

    maintenance = _section_label(app.sidebar, 'MANTENIMIENTO')
    maintenance.pack(fill='x', padx=20, pady=(13, 5))
    _apply_sidebar_icon(app, 'btn_cleanup')
    app.btn_cleanup.pack(fill='x', padx=13, pady=1)
    _apply_sidebar_icon(app, 'btn_tweaks')
    app.btn_tweaks.pack(fill='x', padx=13, pady=1)
    _apply_sidebar_icon(app, 'btn_network')
    app.btn_network.pack(fill='x', padx=13, pady=1)

    history = _section_label(app.sidebar, 'HISTORIAL')
    history.pack(fill='x', padx=20, pady=(13, 5))
    _apply_sidebar_icon(app, 'btn_smart_alerts')
    app.btn_smart_alerts.pack(fill='x', padx=13, pady=1)
    _apply_sidebar_icon(app, 'btn_session_trends')
    app.btn_session_trends.pack(fill='x', padx=13, pady=1)
    _apply_sidebar_icon(app, 'btn_alert_history')
    app.btn_alert_history.pack(fill='x', padx=13, pady=1)

    app._theme_toggle_button = ctk.CTkButton(
        app.sidebar,
        text=theme_action_label(),
        height=32,
        corner_radius=8,
        fg_color=COLORS['surface'],
        hover_color=COLORS['surface_hover'],
        border_width=1,
        border_color=COLORS['border'],
        text_color=COLORS['text_2'],
        font=(FONT, 9, 'bold'),
        command=getattr(app, 'toggle_ui_theme', None),
    )
    app._theme_toggle_button.pack(side='bottom', fill='x', padx=16, pady=(2, 4))

    app._sidebar_version = ctk.CTkLabel(
        app.sidebar,
        text=f'{VERSION_LABEL}\nRF/RNF Compliance',
        justify='left',
        font=(FONT, 8),
        text_color=COLORS['muted'],
    )
    app._sidebar_version.pack(side='bottom', anchor='w', padx=20, pady=(4, 14))


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
            corner_radius=13,
        )
        _safe_config(title, font=(FONT, 9, 'bold'), text_color=COLORS['text_2'], justify='left', anchor='w')
        _safe_config(value, font=(FONT, 28, 'bold'), text_color=COLORS['text'])
        _safe_config(detail, font=(FONT, 9, 'bold'), text_color=accent)
        _safe_config(bar, height=5, progress_color=accent, fg_color=COLORS['track'])


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
                fg_color=theme_color('#0d2942'),
                hover_color=theme_color('#164f7d'),
                border_width=1,
                border_color=theme_color('#1d5278'),
                text_color=theme_color('#75d2f7'),
                font=(FONT, 8, 'bold'),
                command=cpu_callback,
            )
            app._cpu_details_button.place(relx=1.0, rely=0.0, x=-10, y=8, anchor='ne')
        _safe_config(app.lbl_cpu_title, wraplength=285)
        _bind_card_hover(app.card_cpu)

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
                fg_color=theme_color('#0d2942'),
                hover_color=theme_color('#164f7d'),
                border_width=1,
                border_color=theme_color('#1d5278'),
                text_color=theme_color('#75d2f7'),
                font=(FONT, 8, 'bold'),
                command=ram_callback,
            )
            app._ram_details_button.place(relx=1.0, rely=0.0, x=-10, y=8, anchor='ne')
        _safe_config(app.lbl_ram_title, wraplength=285)
        _bind_card_hover(app.card_ram)

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
                fg_color=theme_color('#0d2942'),
                hover_color=theme_color('#164f7d'),
                border_width=1,
                border_color=theme_color('#1d5278'),
                text_color=theme_color('#75d2f7'),
                font=(FONT, 8, 'bold'),
                command=gpu_callback,
            )
            app._gpu_details_button.place(relx=1.0, rely=0.0, x=-10, y=8, anchor='ne')
        _safe_config(app.lbl_gpu_title, wraplength=285)
        _bind_card_hover(app.card_gpu)


def _style_charts(app):
    _safe_config(
        app.frame_charts,
        fg_color=COLORS['surface'],
        border_color=COLORS['border'],
        border_width=1,
        corner_radius=13,
    )
    try:
        app.fig.set_facecolor(COLORS['surface'])
        for ax in (app.ax_cpu, app.ax_ram, app.ax_gpu):
            ax.set_facecolor(COLORS['surface'])
            ax.tick_params(colors=COLORS['muted'], labelsize=7, length=0)
            ax.grid(False)
            ax.yaxis.grid(True, color=COLORS['border_soft'], linestyle='-', linewidth=0.45, alpha=0.65)
            ax.set_xticks([0, 6, 12, 18, 24])
            ax.set_xticklabels(['-60s', '-45s', '-30s', '-15s', 'Ahora'])
            for spine in ax.spines.values():
                spine.set_visible(False)
            ax.title.set_color(COLORS['text_2'])
            ax.title.set_fontsize(8)
            ax.title.set_fontweight('bold')
        app.fig.subplots_adjust(left=0.045, right=0.987, top=0.88, bottom=0.17, wspace=0.16)
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

    app.frame_meters.pack(fill='x', pady=(0, 8))
    _safe_pack_forget(app.alert_summary_bar)

    if storage_label is not None:
        _safe_config(
            storage_label,
            text='ALMACENAMIENTO',
            font=(FONT, 10, 'bold'),
            text_color=COLORS['text_2'],
        )
        storage_label.pack(anchor='w', pady=(0, 5))

    _safe_config(app.scroll_disks, fg_color='transparent')
    app.scroll_disks.pack(fill='x', pady=(0, 8))

    app.frame_charts.pack(fill='both', expand=True, pady=(0, 0))

    _style_existing_cards(app)
    _style_charts(app)


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

        score = getattr(self, 'latest_score', None)
        color = _status_color(score)
        name = _status_name(score)
        _safe_config(self._health_status, text=name, text_color=color)
        _safe_config(
            self._health_score,
            text=f'Índice técnico {float(score):.1f}%' if isinstance(score, (int, float)) else 'Índice técnico N/A',
        )
        _safe_config(
            self._health_icon,
            text='✓' if name in {'ÓPTIMO', 'ESTABLE'} else '!',
            text_color=color,
        )

        alert_text = 'Sin alertas activas'
        alert_detail = 'Todo funcionando correctamente'
        try:
            current = str(self.lbl_alert_summary.cget('text') or '').strip()
            if current:
                cleaned = current.replace('✓', '').strip()
                if cleaned and cleaned.upper() not in {'MONITOREO INICIANDO', 'SIN ALERTAS ACTIVAS'}:
                    alert_text = cleaned[:42]
                    alert_detail = 'Revisar el módulo de alertas y diagnóstico'
        except Exception:
            pass
        _safe_config(self._alert_value, text=alert_text, text_color=COLORS['green'] if alert_text == 'Sin alertas activas' else COLORS['amber'])
        _safe_config(self._alert_detail, text=alert_detail)

        valid, total = _telemetry_coverage(telemetry)
        if total:
            _safe_config(
                self._coverage_value,
                text=f'{valid} / {total} VÁLIDAS',
                text_color=COLORS['green'] if valid == total else COLORS['primary'],
            )
            _safe_config(self._coverage_detail, text='Métricas certificadas · clic para inspeccionar')
        else:
            _safe_config(self._coverage_value, text='N/A', text_color=COLORS['muted'])
            _safe_config(self._coverage_detail, text='Sin metadata de certificación')

        _safe_config(self._uptime_value, text=_uptime_text())
        _safe_config(self._header_last_update, text=f'Última actualización: {_relative_update_text(telemetry)}')

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
                corner_radius=12,
            )
            _safe_config(widgets.get('bar'), progress_color=COLORS['primary'], fg_color=COLORS['track'], height=5)

            model = d.get('model') or 'Unidad de almacenamiento'
            mounts = d.get('mount_points') or 'N/A'
            _safe_config(
                widgets.get('lbl_name'),
                text=f'{model}   ·   {mounts}',
                text_color=COLORS['text'],
                font=(FONT, 10, 'bold'),
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
                    capacity = f'Capacidad: {total:.0f} GB  ·  Disponible: {available:.0f} GB  ·  Uso: {pct:.1f}%'
                else:
                    capacity = 'Información de capacidad: N/A'

                if isinstance(temp, (int, float)):
                    capacity += f'  ·  Temperatura: {float(temp):.0f} °C'
                else:
                    capacity += '  ·  Temperatura: N/A'

                _safe_config(
                    widgets.get('lbl_exact'),
                    text=capacity,
                    text_color=COLORS['primary'],
                    font=(FONT, 9),
                )
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
