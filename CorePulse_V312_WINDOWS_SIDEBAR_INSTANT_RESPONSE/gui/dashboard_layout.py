"""Administra la distribución responsiva del dashboard, navegación y tarjeta del agente."""
from __future__ import annotations
from gui.widget_updates import configure_changed
from core.theme_manager import color as theme_color, theme_action_label, role_color
# Código refactorizado: nombres estables y documentación en español.
import threading, types, time
import customtkinter as ctk
from core.version import VERSION_LABEL
from core.agent_reaction import agent_display_state
VERSION = VERSION_LABEL
DESIGN_ID = 'COREPULSE_REFERENCE_DASHBOARD_LAYOUT'
FONT = 'Segoe UI'
ICON_FONT = 'Segoe UI Symbol'
# V128: misma autoridad de roles exactos que la vista previa de Temas.
APP = role_color('bg')
SIDEBAR = role_color('sidebar')
SURFACE = role_color('surface')
SURFACE_2 = role_color('surface_2')
BORDER = role_color('border')
BORDER_SOFT = role_color('border')
TRACK = role_color('surface_2')
TEXT = role_color('text')
TEXT_2 = role_color('text_2')
MUTED = role_color('muted')
CYAN = role_color('accent')
GREEN = '#16d98b'
AMBER = '#f3b54a'
RED = '#ff5d6c'
PURPLE = '#a064ff'
PRIMARY_DARK = role_color('accent_2')
SIDEBAR_ACTIVE_BG = role_color('accent_2')
SIDEBAR_ACTIVE_HOVER = role_color('accent')
SIDEBAR_ACTIVE_BORDER = role_color('accent')
SIDEBAR_INACTIVE_TEXT = role_color('text_2')
RESIZE_DEBOUNCE_MS = 85
FULLSCREEN_SETTLE_MS = 420
NAV = {'_btn_summary': 'Resumen', 'btn_benchmark': 'Benchmark', 'btn_diagnostic': 'Iniciar diagnóstico', 'btn_health_center': 'Centro de salud', 'btn_cleanup': 'Limpieza de sistema', 'btn_tweaks': 'Tweaks Windows 11', 'btn_network': 'Red avanzada', 'btn_smart_alerts': 'Alertas técnicas', 'btn_session_trends': 'Tendencias', 'btn_alert_history': 'Historial de alertas'}
SIDEBAR_OPTION_ACCENTS = {
    '_btn_summary': CYAN,
    'btn_benchmark': PURPLE,
    'btn_diagnostic': AMBER,
    'btn_health_center': GREEN,
    'btn_cleanup': CYAN,
    'btn_tweaks': PURPLE,
    'btn_network': CYAN,
    'btn_smart_alerts': RED,
    'btn_session_trends': GREEN,
    'btn_alert_history': AMBER,
}

def _sidebar_option_accent(attr):
    return SIDEBAR_OPTION_ACCENTS.get(attr, CYAN)


def _sidebar_line(button, color, active=False):
    if button is None:
        return None
    try:
        from gui.dashboard import _set_sidebar_option_line
        return _set_sidebar_option_line(button, color, active=active)
    except Exception:
        return None


def _set_resizing(app, active):
    """Punto único que marca is_resizing y, en el mismo gesto, activa/desactiva
    la guarda de redibujo CTk de esta ventana (V159). Al pasar a
    False, la guarda aplica de una sola vez los redibujos de widgets que
    quedaron pendientes durante el arrastre."""
    app.is_resizing = bool(active)
    try:
        from gui.resize_render_guard import set_active as _set_render_guard_active
        _set_render_guard_active(active, owner=app)
    except Exception:
        pass

def _cfg(w, **kw):
    if w is None:
        return
    try:
        configure_changed(w, **kw)
    except Exception:
        pass

def _text(w):
    try:
        return str(w.cget('text') or '').strip()
    except Exception:
        return ''

def _children(w):
    try:
        return list(w.winfo_children())
    except Exception:
        return []

def _desc(w):
    out = []
    stack = list(_children(w))
    while stack:
        n = stack.pop(0)
        out.append(n)
        stack.extend(_children(n))
    return out

def _cancel(app, attr):
    aid = getattr(app, attr, None)
    if aid:
        try:
            app.after_cancel(aid)
        except Exception:
            pass
    try:
        setattr(app, attr, None)
    except Exception:
        pass

def _style_sidebar(app):
    _cfg(app.sidebar, width=248, fg_color=SIDEBAR)
    try:
        app.sidebar.grid_propagate(False)
    except Exception:
        pass
    _cfg(getattr(app, 'lbl_brand', None), text='')
    _cfg(getattr(app, 'lbl_subtitle', None), text='')
    # V113: la esquina superior izquierda queda limpia; no se reinyecta branding.
    _cfg(getattr(app, '_sidebar_brand_title', None), text='')
    _cfg(getattr(app, '_sidebar_brand_company', None), text='')
    _cfg(getattr(app, '_sidebar_brand_rule', None), height=0)
    for attr, label in NAV.items():
        b = getattr(app, attr, None)
        if b is None:
            continue
        active = attr == '_btn_summary'
        _cfg(
            b,
            text=label,
            height=38,
            corner_radius=11,
            font=(FONT, 11, 'bold'),
            anchor='w',
            padx=16 if active else 14,
            text_color=TEXT if active else SIDEBAR_INACTIVE_TEXT,
            fg_color=role_color('accent_soft') if active else 'transparent',
            hover_color=SIDEBAR_ACTIVE_HOVER if active else SURFACE_2,
            border_width=0,
            border_color=_sidebar_option_accent(attr),
        )
        _sidebar_line(b, _sidebar_option_accent(attr), active=active)
    _cfg(getattr(app, '_sidebar_version', None), text=f'{VERSION_LABEL} · Cereon Technologies', font=(FONT, 8), text_color=MUTED)
    # V131 — Personalización usa el mismo lenguaje contextual del resto del
    # sidebar: sin relleno hasta seleccionar Temas o Actualizaciones.
    _cfg(getattr(app, '_personalization_block', None), fg_color='transparent', border_width=0, corner_radius=0)
    _cfg(getattr(app, '_personalization_label', None), text_color=MUTED)
    _cfg(getattr(app, '_personalization_hint', None), text_color=MUTED)
    _cfg(getattr(app, '_personalization_divider', None), fg_color='transparent', height=0)
    for attr, label, accent in (
        ('_theme_toggle_button', '◉  Temas', PURPLE),
        ('_update_button', '↻  Actualizaciones', CYAN),
    ):
        button = getattr(app, attr, None)
        _cfg(
            button, text=label, height=34, corner_radius=9,
            fg_color='transparent', hover_color=SURFACE_2,
            border_width=0, border_color=accent,
            text_color=SIDEBAR_INACTIVE_TEXT, font=(FONT, 11, 'bold'),
            anchor='w', padx=12,
        )
        _sidebar_line(button, accent, active=False)


def _is_agent_container(w):
    titles = {'AGENTE COREPULSE', 'ESTADO DEL AGENTE'}
    return any((_text(n).upper() in titles for n in [w] + _desc(w)))

def _destroy_existing_agent_cards(app):
    for child in list(_children(getattr(app, 'sidebar', None))):
        if _is_agent_container(child):
            try:
                child.destroy()
            except Exception:
                pass

def _worker_alive(agent):
    if agent is None:
        return False
    for v in vars(agent).values():
        if isinstance(v, threading.Thread):
            try:
                if v.is_alive():
                    return True
            except Exception:
                pass
    for a in ('running', 'is_running', 'active'):
        try:
            v = getattr(agent, a)
            if isinstance(v, bool):
                return v
        except Exception:
            pass
    return False

def _agent_level(state):
    raw = str((state or {}).get('overall') or 'UNKNOWN').upper()
    return {'OK': 'NORMAL', 'OPTIMAL': 'NORMAL', 'OPTIMO': 'NORMAL', 'ÓPTIMO': 'NORMAL', 'WARN': 'WARNING', 'ADVERTENCIA': 'WARNING', 'CRITICO': 'CRITICAL', 'CRÍTICO': 'CRITICAL'}.get(raw, raw)

def _active_alerts(state):
    try:
        a = (state.get('alerts') or {}).get('active') or []
        return a if isinstance(a, list) else []
    except Exception:
        return []

def _primary_alert(state):
    a = _active_alerts(state)
    if not a:
        return None
    rank = {'CRITICAL': 3, 'WARNING': 2, 'INFO': 1}
    best = max(a, key=lambda x: rank.get(str((x or {}).get('level') or '').upper(), 0) if isinstance(x, dict) else -1)
    return str(best.get('title') or best.get('message') or '').strip() or None if isinstance(best, dict) else None

def _build_agent_card(app):
    """V227: el Estado del agente vive en el header, nunca en el sidebar."""
    _destroy_existing_agent_cards(app)
    header_card = getattr(app, '_header_agent_frame', None)
    try:
        valid = header_card is not None and header_card.winfo_exists()
    except Exception:
        valid = header_card is not None
    if valid:
        app._agent_card = header_card
        return header_card
    return None


def render_agent_card(app, state=None):
    card = getattr(app, '_agent_card', None)
    try:
        invalid = card is None or not card.winfo_exists()
    except Exception:
        invalid = True
    if invalid:
        try:
            card = _build_agent_card(app)
        except Exception:
            return
        if card is None:
            return
    if state is None:
        try:
            state = app.realtime_agent.get_state()
        except Exception:
            state = {}
    if not isinstance(state, dict):
        state = {}
    alive = _worker_alive(getattr(app, 'realtime_agent', None))
    mode = str(state.get('mode') or state.get('context') or 'DESKTOP').upper()
    mode = {'DESKTOP': 'ESCRITORIO', 'GAME': 'JUEGO', 'GAME_ACTIVE': 'JUEGO'}.get(mode, mode)
    display = agent_display_state(state, getattr(app, 'current_live_health', None), alive=alive)
    _cfg(getattr(app, '_agent_title', None), text='ESTADO DEL AGENTE', text_color=TEXT_2)
    tone_color = {'RED': RED, 'AMBER': AMBER, 'CYAN': CYAN, 'GREEN': GREEN}.get(display.get('tone'), MUTED)
    _cfg(app._agent_dot, text_color=tone_color)
    _cfg(app._agent_status, text=display['status'], text_color=tone_color)
    _cfg(app._agent_mode, text=mode.title(), text_color=MUTED)
    
    human_label = {
        'NINGUNA SOSTENIDA': 'Sin alertas sostenidas',
        'EVALUANDO': 'Evaluando evidencia',
        'EVALUANDO SESIÓN': 'Evaluando la sesión',
        'CRÍTICA SOSTENIDA': 'Alerta crítica sostenida',
        'ADVERTENCIA SOSTENIDA': 'Advertencia sostenida',
        'CRÍTICA INSTANTÁNEA': 'Condición crítica instantánea',
        'ADVERTENCIA INSTANTÁNEA': 'Advertencia instantánea',
        'ATENCIÓN TÉRMICA': 'Atención térmica',
        'NO DISPONIBLE': 'Agente no disponible',
    }.get(str(display.get('label') or '').upper(), str(display.get('label') or '').replace('_', ' ').capitalize())
    _cfg(app._agent_state, text=human_label, text_color=tone_color)
    detail_text = str(display.get('detail') or '').strip()
    if app._agent_card is getattr(app, '_header_agent_frame', None) and len(detail_text) > 58:
        detail_text = detail_text[:55].rstrip() + '…'
    _cfg(app._agent_detail, text=detail_text, text_color=MUTED)
    _cfg(app._agent_card, border_color={'WARNING': AMBER, 'CRITICAL': RED, 'ERROR': RED}.get(display['border_level'], BORDER))


def _install_agent_route(app):
    app.agent_status_panel = None

    def ensure(self):
        if getattr(self, '_agent_card', None) is None:
            _build_agent_card(self)

    def refresh(self, state=None):
        if getattr(self, 'is_running', False):
            render_agent_card(self, state)
    app._ensure_agent_status_panel = types.MethodType(ensure, app)
    app._refresh_agent_status_panel = types.MethodType(refresh, app)

def _hide_storage_scrollbar_if_possible(app, disk_count):
    bar = getattr(getattr(app, 'scroll_disks', None), '_scrollbar', None)
    if bar is None:
        return
    try:
        if disk_count <= 2:
            bar.grid_remove()
        else:
            bar.grid()
    except Exception:
        pass

def _storage_height_for(app, mode):
    """Altura determinista del bloque multiunidad sin tocar la fuente SMART.

    1 unidad: una tarjeta completa.
    2 unidades: dos tarjetas completas.
    3+ unidades: dos tarjetas visibles + scroll interno.
    """
    count = len(getattr(app, 'disk_widgets', {}) or {})
    if count <= 0:
        return 58 if mode == 'compact' else 64

    card_h = 86
    pack_gap = 4  # pady=2 arriba + abajo
    one = card_h + pack_gap + 4
    two = (card_h + pack_gap) * 2 + 4
    return one if count == 1 else two


def _finalize_storage_viewport(app, mode=None):
    """Fija orden, scrollregion y posición tras cambios de topología.

    No modifica ningún dato de disco: sólo geometría/presentación.
    """
    if mode is None:
        mode = getattr(app, '_layout_mode', 'standard')
    host = getattr(app, 'scroll_disks', None)
    widgets_map = getattr(app, 'disk_widgets', {}) or {}
    if host is None:
        return

    # Reafirma el orden visual según el índice real. Esto evita que una tarjeta
    # creada por hot-plug quede fuera del flujo de pack en Windows/Tk.
    for idx in sorted(widgets_map):
        widgets = widgets_map.get(idx) or {}
        card = widgets.get('card')
        if card is None:
            continue
        try:
            card.pack_propagate(False)
            card.pack_configure(fill='x', expand=False, padx=0, pady=2)
        except Exception:
            pass

    target_h = _storage_height_for(app, mode)
    _cfg(host, height=target_h)
    try:
        host.grid_propagate(False)
        host.pack_configure(fill='x', expand=False, pady=(0, 4 if mode == 'compact' else 5))
    except Exception:
        pass

    try:
        host.content.update_idletasks()
        host.update_idletasks()
    except Exception:
        pass

    count = len(widgets_map)
    _hide_storage_scrollbar_if_possible(app, count)
    try:
        host.yview_moveto(0.0)
    except Exception:
        pass

    # StableScrollHost ya expone esta autoridad. Repetimos una vez en idle y
    # una vez diferida porque Windows puede publicar la geometría del widget USB
    # uno o dos frames después de crearlo.
    schedule = getattr(host, '_schedule_geometry', None) or getattr(host, '_schedule_scrollregion', None)
    if callable(schedule):
        try:
            schedule(0)
            app.after_idle(lambda: schedule(0))
            app.after(70, lambda: schedule(0))
        except Exception:
            pass


def _sync_storage_height(app, mode=None):
    if mode is None:
        mode = getattr(app, '_layout_mode', 'standard')
    _finalize_storage_viewport(app, mode)


def _style_storage_widgets(app):
    _cfg(getattr(app, 'scroll_disks', None), fg_color='transparent')
    for widgets in getattr(app, 'disk_widgets', {}).values():
        card = widgets.get('card')
        name = widgets.get('lbl_name')
        badge = widgets.get('lbl_badge')
        exact = widgets.get('lbl_exact')
        bar = widgets.get('bar')
        try:
            card.pack_propagate(False)
        except Exception:
            pass
        _cfg(card, fg_color=SURFACE, border_color=BORDER, border_width=1, corner_radius=16, height=86)
        try:
            from gui.dashboard import _ensure_storage_card_decor
            _ensure_storage_card_decor(card, widgets)
        except Exception:
            pass
        try:
            card.pack_configure(fill='x', expand=False, padx=0, pady=2)
        except Exception:
            pass
        if name is not None:
            cur = _text(name)
            for prefix in ('💾 ', '▰  ', '▰ '):
                while cur.startswith(prefix):
                    cur = cur[len(prefix):].strip()
            _cfg(name, text=cur, font=(FONT, 10, 'bold'), text_color=TEXT, anchor='w')
        _cfg(badge, font=(FONT, 9, 'bold'))
        _cfg(exact, font=(FONT, 9), text_color=CYAN, anchor='w', justify='left')
        _cfg(bar, height=6, fg_color=TRACK, progress_color=CYAN)
    _sync_storage_height(app)

def _install_storage_route(app):
    if getattr(app, '_storage_layout_wrapped', False):
        return
    original = app.update_disks_ui

    def update(self, disks_data):
        original(disks_data)
        _style_storage_widgets(self)
        _sync_storage_height(self)
    app.update_disks_ui = types.MethodType(update, app)
    app._storage_layout_wrapped = True
    app._sync_storage_height_callback = types.MethodType(lambda self: _sync_storage_height(self), app)
    _style_storage_widgets(app)

def _style_hardware(app):
    specs = (
        (app.card_cpu, app.lbl_cpu_title, app.lbl_cpu, app.lbl_cpu_temp, app.bar_cpu, CYAN),
        (app.card_ram, app.lbl_ram_title, app.lbl_ram, app.lbl_ram_gb, app.bar_ram, GREEN),
        (app.card_gpu, app.lbl_gpu_title, app.lbl_gpu, app.lbl_gpu_temp, app.bar_gpu, PURPLE),
    )
    for card, title, value, detail, bar, accent in specs:
        _cfg(card, fg_color=SURFACE, border_color=BORDER, border_width=1, corner_radius=16, height=134)
        try:
            card.pack_propagate(False)
        except Exception:
            pass
        _cfg(title, font=(FONT, 9, 'bold'), text_color=TEXT, anchor='w', justify='left')
        _cfg(value, font=(FONT, 28, 'bold'), text_color=TEXT, anchor='w')
        _cfg(detail, font=(FONT, 9, 'bold'), text_color=accent, anchor='w', justify='left')
        _cfg(bar, height=6, progress_color=accent, fg_color=TRACK)
        try:
            from gui.dashboard import _ensure_soft_card_accent
            _ensure_soft_card_accent(card, accent, placement='left')
        except Exception:
            pass
    try:
        app.card_cpu.pack_configure(side='left', expand=True, fill='both', padx=(0, 6))
        app.card_ram.pack_configure(side='left', expand=True, fill='both', padx=6)
        app.card_gpu.pack_configure(side='left', expand=True, fill='both', padx=(6, 0))
    except Exception:
        pass


def _layout_mode(w, h):
    if w < 1360 or h < 820:
        return 'compact'
    if w < 1600 or h < 930:
        return 'standard'
    return 'large'

def _sidebar_section_labels(app):
    wanted = {'MONITOREO', 'DIAGNÓSTICO', 'MANTENIMIENTO', 'HISTORIAL'}
    out = []
    for child in _children(getattr(app, 'sidebar', None)):
        if _text(child).upper() in wanted:
            out.append(child)
    return out

def _style_sidebar_mode(app, mode):
    compact = mode == 'compact'
    standard = mode == 'standard'
    try:
        viewport_h = int(app.winfo_height())
    except Exception:
        viewport_h = 900
    # V300: el ancho de la ventana no debe convertir Personalización en un
    # footer flotante. En otros PCs (p. ej. 1280 px de ancho / escalado DPI)
    # `mode == 'compact'` se activaba aunque hubiera altura suficiente y dejaba
    # un hueco enorme bajo Historial. El modo ajustado depende SOLO de la altura
    # real disponible; además el bloque siempre conserva el flujo del menú.
    personalization_tight = viewport_h < 690
    # V131: el lateral conserva una anchura mínima legible incluso en modo compacto.
    collapsed = False
    width = 242 if compact else 248 if standard else 254
    _cfg(app.sidebar, width=width, fg_color=SIDEBAR, border_width=0, corner_radius=0)
    try:
        border = getattr(app, '_sidebar_native_border', None)
        border_lines = border if isinstance(border, (tuple, list)) else ((border,) if border is not None else ())
        for line in border_lines:
            if line is not None and line.winfo_exists():
                line.configure(bg=BORDER)
                line.lift()
    except Exception:
        pass

    # El logotipo gráfico grande no vuelve al lateral; sólo queda la identidad
    # tipográfica compacta creada por dashboard.py.
    try:
        app.frame_logo.pack_forget()
    except Exception:
        pass
    _cfg(getattr(app, 'lbl_brand', None), text='')
    _cfg(getattr(app, 'lbl_subtitle', None), text='')

    brand = getattr(app, '_sidebar_brand_block', None)
    if brand is not None:
        _cfg(brand, height=43 if compact else 48)
        try:
            brand.pack_configure(fill='x', padx=13 if compact else 16, pady=(7 if compact else 10, 3 if compact else 4))
        except Exception:
            pass
    _cfg(getattr(app, '_sidebar_brand_title', None), font=(FONT, 13 if compact else 15, 'bold'), height=20 if compact else 23)
    _cfg(getattr(app, '_sidebar_brand_company', None), font=(FONT, 6 if compact else 7, 'bold'), height=13 if compact else 15)
    rule = getattr(app, '_sidebar_brand_rule', None)
    try:
        if rule is not None:
            rule.pack_configure(fill='x', padx=13 if compact else 16, pady=(0, 5 if compact else 7))
    except Exception:
        pass

    has_brand_block = getattr(app, '_sidebar_brand_block', None) is not None
    for label in _sidebar_section_labels(app):
        try:
            name = _text(label).upper()
            if name == 'MONITOREO':
                # Al retirar el branding superior, conservamos el aire visual que
                # antes aportaba ese bloque. No cambia el ancho ni la navegación.
                top_gap = 4 if compact else 6 if standard else 8
                if has_brand_block:
                    top_gap = 0
            else:
                top_gap = 3 if compact else 5
            label.pack_configure(padx=17, pady=(top_gap, 2 if compact else 3))
        except Exception:
            pass
        _cfg(label, height=15 if compact else 17, font=(FONT, 8 if compact else 9, 'bold'))

    context_button = {
        'dashboard': '_btn_summary',
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
        'updates': '_update_button',
    }
    active_attr = context_button.get(str(getattr(app, '_navigation_context', 'dashboard')).lower(), '_btn_summary')
    for attr in NAV:
        b = getattr(app, attr, None)
        if b is None:
            continue
        active = attr == active_attr
        _cfg(
            b,
            height=40 if collapsed else 34 if compact else 36 if standard else 38,
            width=44 if collapsed else 0,
            font=(FONT, 10, 'bold'),
            corner_radius=11 if collapsed else 10,
            padx=(14 if compact else 17) if active else (12 if compact else 15),
            text_color=TEXT if active else SIDEBAR_INACTIVE_TEXT,
            fg_color=role_color('accent_soft') if active else 'transparent',
            hover_color=SIDEBAR_ACTIVE_HOVER if active else SURFACE_2,
            border_width=0,
            border_color=_sidebar_option_accent(attr),
            anchor='w',
        )
        try:
            from gui.dashboard import _set_nav_selection_indicator
            _set_nav_selection_indicator(b, False)
        except Exception:
            pass
        _sidebar_line(b, _sidebar_option_accent(attr), active=active)
        try:
            b.pack_configure(fill='none' if collapsed else 'x', padx=10 if collapsed else 11 if compact else 12, pady=1, anchor='center' if collapsed else 'w')
        except Exception:
            pass

    # V227: no existe tarjeta de agente en el sidebar. El bloque real vive en el header.
    legacy_agent = getattr(app, '_agent_card', None)
    if legacy_agent is not None and legacy_agent is not getattr(app, '_header_agent_frame', None):
        try:
            legacy_agent.pack_forget()
        except Exception:
            pass

    # V133 — Personalización conserva dos acciones completas y recorta primero
    # metadatos secundarios cuando el alto de la ventana es limitado. Esto evita
    # que Actualizaciones quede pegado/cortado contra el borde inferior.
    personal = getattr(app, '_personalization_block', None)
    _cfg(personal, fg_color='transparent', border_width=0, corner_radius=0)
    try:
        pdiv = getattr(app, '_personalization_top_divider', None)
        if pdiv is not None and pdiv.winfo_exists():
            pdiv.configure(bg=BORDER, height=1)
    except Exception:
        pass
    _cfg(getattr(app, '_personalization_label', None), height=16, font=(FONT, 8 if compact else 9, 'bold'), text_color=MUTED)
    _cfg(getattr(app, '_personalization_hint', None), height=13, font=(FONT, 8), text_color=MUTED)
    _cfg(getattr(app, '_personalization_divider', None), fg_color='transparent', height=0)

    context = str(getattr(app, '_navigation_context', '') or '').lower()
    for attr, label, key, accent in (
        ('_theme_toggle_button', '◉  Temas', 'themes', PURPLE),
        ('_update_button', '↻  Actualizaciones', 'updates', CYAN),
    ):
        button = getattr(app, attr, None)
        active = context == key
        _cfg(
            button,
            text=label,
            height=35 if personalization_tight else 37,
            corner_radius=9,
            fg_color=role_color('accent_soft') if active else 'transparent',
            hover_color=SIDEBAR_ACTIVE_HOVER if active else SURFACE_2,
            border_width=0,
            border_color=accent,
            text_color=TEXT if active else SIDEBAR_INACTIVE_TEXT,
            font=(FONT, 10 if compact else 11, 'bold'),
            anchor='w',
            padx=11 if compact else 12,
        )
        _sidebar_line(button, accent, active=active)

    hint = getattr(app, '_personalization_hint', None)
    divider = getattr(app, '_personalization_divider', None)
    ver = getattr(app, '_sidebar_version', None)
    _cfg(ver, text=f'{VERSION_LABEL} · Cereon Technologies', font=(FONT, 8), text_color=MUTED)
    try:
        if personalization_tight:
            # Prioridad: Temas + Actualizaciones siempre visibles. El subtítulo y
            # divisor permanecen retirados; la versión se conserva si cabe en el
            # footer compacto.
            if hint is not None:
                hint.pack_forget()
            if divider is not None:
                divider.pack_forget()
            if ver is not None and not ver.winfo_manager():
                ver.pack(fill='x', padx=17, pady=(1, 1))
        else:
            theme_button = getattr(app, '_theme_toggle_button', None)
            # V256: subtítulo de Personalización eliminado por diseño.
            # No volver a insertarlo durante cambios de tamaño/layout.
            if hint is not None and hint.winfo_manager():
                hint.pack_forget()
            if divider is not None and divider.winfo_manager():
                divider.pack_forget()
            if ver is not None and not ver.winfo_manager():
                ver.pack(fill='x', padx=17, pady=(1, 2))
        if personal is not None:
            # V300: Personalización forma parte del flujo del sidebar en TODAS
            # las resoluciones. Nunca se ancla al borde inferior: eso hacía que
            # un cambio de ancho/DPI generara el hueco visual visto en otros PCs.
            # En alturas muy bajas solo compactamos paddings/controles.
            personal.pack_configure(
                side='top',
                fill='x',
                padx=0,
                pady=((3, 1) if personalization_tight else (6, 2)),
                after=getattr(app, 'btn_alert_history', None),
            )
    except Exception:
        pass


def _style_header_mode(app, mode):
    compact = mode == 'compact'
    header = getattr(app, '_header', None)
    try:
        header.pack_configure(fill='x', pady=(0, 5 if compact else 7))
        _cfg(header, height=82 if compact else 86 if mode == 'standard' else 88)
    except Exception:
        pass
    # La identidad del equipo tiene una autoridad visual explícita.
    # Antes este bloque tomaba el primer Label del header por posición y lo
    # trataba como el antiguo título, sobrescribiendo el modelo a 23/26/28 px.
    # Eso hacía inútiles los tamaños definidos en dashboard.py.
    identity = getattr(app, '_header_identity', None)
    try:
        if identity is not None:
            left_pad = 10 if compact else 16 if mode == 'standard' else 18
            identity.pack_configure(padx=(left_pad, 18))
    except Exception:
        pass
    brand = getattr(app, '_header_brand_icon', None)
    try:
        if brand is not None:
            brand.pack_configure(padx=(4, 14), pady=(6 if compact else 7, 4))
    except Exception:
        pass

    _cfg(
        getattr(app, '_header_device_model', None),
        font=(FONT, 14 if compact else 15 if mode == 'standard' else 17, 'bold'),
        text_color=TEXT,
        anchor='w',
        justify='left',
        wraplength=390 if compact else 520 if mode == 'standard' else 650,
    )
    _cfg(
        getattr(app, '_header_brand_icon', None),
        width=46,
        height=46,
    )
    _cfg(getattr(app, '_header_eyebrow', None), font=(FONT, 7 if compact else 8, 'bold'), text_color=CYAN)
    _cfg(getattr(app, '_header_subtitle', None), font=(FONT, 8 if compact else 9), wraplength=420 if compact else 540 if mode == 'standard' else 660)
    _cfg(getattr(app, '_header_meta_hint', None), font=(FONT, 7 if compact else 8), wraplength=220 if compact else 260)
    for attr in ('_header_chip_live', '_header_chip_data', '_header_chip_focus'):
        _cfg(getattr(app, attr, None), font=(FONT, 7 if compact else 8, 'bold'))
    _cfg(getattr(app, '_header_agent_text', None), font=(FONT, 8 if compact else 9, 'bold'))
    _cfg(getattr(app, '_header_agent_hint', None), font=(FONT, 7 if compact else 8))
    _cfg(getattr(app, '_header_last_update', None), font=(FONT, 6 if compact else 7))
    _cfg(getattr(app, '_agent_title', None), font=(FONT, 7 if compact else 8, 'bold'))
    _cfg(getattr(app, '_agent_badge', None), font=(FONT, 6 if compact else 7, 'bold'))
    _cfg(getattr(app, '_agent_status', None), font=(FONT, 8 if compact else 9, 'bold'))
    _cfg(getattr(app, '_agent_mode', None), font=(FONT, 6 if compact else 7, 'bold'))
    _cfg(getattr(app, '_agent_state', None), font=(FONT, 7 if compact else 8, 'bold'))
    _cfg(getattr(app, '_agent_detail', None), font=(FONT, 6 if compact else 7), wraplength=285 if compact else 325)
    # La referencia no muestra el botón de tamaño en el encabezado.
    size_button = getattr(app, '_size_button', None)
    try:
        if size_button:
            size_button.pack_forget()
    except Exception:
        pass


def _style_status_band(app):
    band = getattr(app, '_status_band', None)
    if band is None:
        return
    _cfg(band, fg_color='transparent', border_width=0, corner_radius=0)
    for card in getattr(app, '_status_cards', ()):
        _cfg(card, fg_color=SURFACE, border_color=BORDER, border_width=1, corner_radius=16)


def _style_status_mode(app, mode):
    band = getattr(app, '_status_band', None)
    if band is None:
        return
    compact = mode == 'compact'
    standard = mode == 'standard'
    height = 104 if compact else 118 if standard else 124
    _cfg(band, height=height)
    try:
        band.pack_configure(fill='x', pady=(0, 5 if compact else 8))
    except Exception:
        pass

    for card in getattr(app, '_status_cards', ()):
        _cfg(card, height=height, corner_radius=11 if compact else 12)

    icon_size = 34 if compact else 38 if standard else 42
    icon_font = 14 if compact else 16 if standard else 18
    for attr in ('_health_icon', '_alert_icon', '_coverage_icon', '_uptime_icon'):
        _cfg(getattr(app, attr, None), width=icon_size, height=icon_size, corner_radius=icon_size // 2, font=(ICON_FONT, icon_font, 'bold'))

    _cfg(
        getattr(app, '_health_status', None),
        font=(FONT, 12 if compact else 14 if standard else 15, 'bold'),
        wraplength=150 if compact else 175 if standard else 195,
        justify='left',
        anchor='w',
    )
    _cfg(getattr(app, '_health_score', None), font=(FONT, 7 if compact else 8))
    _cfg(
        getattr(app, '_alert_value', None),
        font=(FONT, 11 if compact else 12 if standard else 14, 'bold'),
        wraplength=142 if compact else 168 if standard else 190,
        justify='left',
        anchor='w',
    )
    for attr in ('_coverage_value', '_uptime_value'):
        _cfg(getattr(app, attr, None), font=(FONT, 12 if compact else 14 if standard else 16, 'bold'))
    for attr in ('_alert_detail', '_coverage_detail', '_uptime_detail'):
        _cfg(getattr(app, attr, None), font=(FONT, 7 if compact else 8), wraplength=145 if compact else 172 if standard else 195, justify='left', anchor='w')


def _chart_tick_positions(total_points):
    total = max(2, int(total_points or 0))
    last = total - 1
    positions = [1, round(last * 0.28), round(last * 0.56), round(last * 0.80), last]
    deduped = []
    for value in positions:
        value = max(0, min(last, int(value)))
        if value not in deduped:
            deduped.append(value)
    while len(deduped) < 5:
        deduped.append(last)
    return deduped[:5]


def _chart_target_height_for(app, mode):
    """Reserva una porción visible del Dashboard a las tendencias.

    V105 prioriza la legibilidad: la tarjeta de tendencias usa entre ~31 % y
    ~38 % del alto de la ventana, con límites seguros para no deformar el resto.
    """
    try:
        width = int(app.winfo_width())
        height = int(app.winfo_height())
    except Exception:
        width, height = (1280, 800)
    ratio = 0.31 if mode == 'compact' else 0.39 if mode == 'standard' else 0.41
    target = int(height * ratio)
    minimum = 236 if mode == 'compact' else 338 if mode == 'standard' else 360
    maximum = 310 if mode == 'compact' else 420 if mode == 'standard' else 468
    if width >= 1700:
        target += 12
    return max(minimum, min(target, maximum))


def _style_charts(app):
    _cfg(app.frame_charts, fg_color=SURFACE, border_color=BORDER, border_width=1, corner_radius=0)
    try:
        from gui.dashboard import _ensure_chart_accents
        _ensure_chart_accents(app)
    except Exception:
        pass
    try:
        max_points = max(2, int(getattr(app, 'max_points', 25) or 25))
        ticks = _chart_tick_positions(max_points)
        labels = ['-60s', '-45s', '-30s', '-15s', 'Ahora']
        app.fig.set_facecolor(SURFACE)
        axes = (app.ax_cpu, app.ax_ram, app.ax_gpu)
        for ax in axes:
            ax.set_facecolor(SURFACE)
            ax.tick_params(axis='x', colors=MUTED, labelsize=8, length=0, pad=6)
            ax.tick_params(axis='y', colors=MUTED, labelsize=8, length=0, pad=6, labelleft=True)
            ax.grid(False)
            ax.yaxis.grid(True, color=BORDER_SOFT, linestyle='-', linewidth=0.55, alpha=0.74)
            ax.set_axisbelow(True)
            ax.set_yticks([25, 50, 75, 100])
            ax.set_xticks(ticks)
            ax.set_xticklabels(labels)
            ax.set_ylim(0, 100)
            ax.set_xlim(0, max_points - 1)
            ax.margins(x=0.02, y=0.10)
            ax.title.set_color(TEXT_2)
            ax.title.set_fontsize(9)
            ax.title.set_fontweight('bold')
            for side, spine in ax.spines.items():
                spine.set_visible(True)
                spine.set_linewidth(1.0 if side in ('left', 'bottom') else 0.9)
                spine.set_color(BORDER if side in ('left', 'bottom') else BORDER_SOFT)
        app.fig.subplots_adjust(left=0.052, right=0.985, top=0.84, bottom=0.20, wspace=0.18)
        app.background = None
    except Exception:
        pass


def _sync_chart_figure_geometry(app, mode):
    """Sincroniza Matplotlib con la tarjeta usando el alto realmente útil."""
    frame = getattr(app, 'frame_charts', None)
    fig = getattr(app, 'fig', None)
    canvas = getattr(app, 'canvas', None)
    if frame is None or fig is None or canvas is None:
        return
    try:
        app.update_idletasks()
        width = max(760, int(frame.winfo_width()) - 16)
        min_plot_h = 226 if mode == 'compact' else 258 if mode == 'standard' else 286
        inner_h = int(frame.winfo_height()) - 20
        height = max(min_plot_h, inner_h)
        dpi = float(fig.get_dpi() or 96.0)
        fig.set_size_inches(width / dpi, height / dpi, forward=True)
        canvas_widget = canvas.get_tk_widget()
        canvas_widget.pack_configure(
            side='top',
            fill='both',
            expand=True,
            padx=12 if mode == 'compact' else 14,
            pady=(8, 10),
        )
        try:
            canvas_widget.configure(height=height)
        except Exception:
            pass
        fig.subplots_adjust(left=0.052, right=0.985, top=0.84, bottom=0.20, wspace=0.18)
        app.background = None
    except Exception:
        pass


def _style_charts_mode(app, mode, mode_changed=False):
    # V104: la tarjeta adopta una altura mínima más generosa y responde al
    # tamaño real de la ventana para que los tres gráficos nunca queden aplastados.
    target_h = _chart_target_height_for(app, mode)
    _cfg(app.frame_charts, height=target_h)
    try:
        app.frame_charts.pack_propagate(False)
        app.frame_charts.pack_configure(
            fill='x',
            expand=False,
            pady=(8 if mode == 'compact' else 10, 0),
        )
        _sync_chart_figure_geometry(app, mode)
        if mode_changed:
            app.background = None
            app.canvas.draw_idle()
    except Exception:
        pass


def _apply_layout(app, *, force=False):
    """Aplica layout sin reconfigurar todo el árbol en cada cambio de tamaño.

    El estilo completo sólo se recalcula cuando cambia el breakpoint responsive
    (compact/standard/large) o cuando se pide explícitamente. Si el usuario sólo
    estira la ventana dentro del mismo breakpoint, V111 conserva fuentes, cards,
    sidebar y posiciones; únicamente sincroniza alturas dependientes del viewport
    y la figura de tendencias. Esto elimina el reflow visual destructivo.
    """
    if not getattr(app, 'is_running', False):
        return
    try:
        w, h = (int(app.winfo_width()), int(app.winfo_height()))
    except Exception:
        return
    if w < 500 or h < 400:
        return

    mode = _layout_mode(w, h)
    previous = getattr(app, '_layout_mode', None)
    mode_changed = mode != previous
    app._layout_mode = mode

    if (not force) and (not mode_changed):
        # Fast path: no fuentes, grids, packs ni tarjetas se reconstruyen.
        if not getattr(app, '_active_internal_page', None):
            _sync_storage_height(app, mode)
            _style_charts_mode(app, mode, mode_changed=False)
        app.background = None
        return

    _style_sidebar_mode(app, mode)
    _style_header_mode(app, mode)
    try:
        app.main_content.grid_configure(
            padx=12 if mode == 'compact' else 16 if mode == 'standard' else 18,
            pady=9 if mode == 'compact' else 12 if mode == 'standard' else 14,
        )
    except Exception:
        pass

    _style_status_mode(app, mode)

    meter_h = 108 if mode == 'compact' else 122 if mode == 'standard' else 130
    for card in (app.card_cpu, app.card_ram, app.card_gpu):
        _cfg(card, height=meter_h)
    try:
        app.frame_meters.pack_configure(fill='x', pady=(0, 5 if mode == 'compact' else 8))
    except Exception:
        pass

    font_value = 23 if mode == 'compact' else 26 if mode == 'standard' else 28
    font_detail = 8 if mode == 'compact' else 9
    for value in (app.lbl_cpu, app.lbl_ram, app.lbl_gpu):
        _cfg(value, font=(FONT, font_value, 'bold'))
    for detail in (app.lbl_cpu_temp, app.lbl_ram_gb, app.lbl_gpu_temp):
        _cfg(detail, font=(FONT, font_detail, 'bold'))
    for title in (app.lbl_cpu_title, app.lbl_ram_title, app.lbl_gpu_title):
        _cfg(title, font=(FONT, 8 if mode == 'compact' else 9, 'bold'))

    _style_storage_widgets(app)
    _sync_storage_height(app, mode)
    _style_charts_mode(app, mode, mode_changed=mode_changed)
    app.background = None


def request_stable_layout_sync(app, force=False):
    """Sincroniza la geometría visible una sola vez fuera del gesto de resize."""
    if getattr(app, '_layout_transition', False) or getattr(app, 'is_resizing', False):
        return
    try:
        _apply_layout(app, force=bool(force))
    except Exception:
        pass


def _finish(app):
    app._layout_transition = False
    _set_resizing(app, False)
    _apply_layout(app, force=True)

def _enter(app):
    if getattr(app, '_layout_transition', False) or getattr(app, 'is_fullscreen', False):
        return
    try:
        app._previous_geometry = app.winfo_geometry()
        app._previous_window_state = app.state()
    except Exception:
        pass
    app._layout_transition = True
    _set_resizing(app, True)
    app.is_fullscreen = True
    _cancel(app, '_resize_after_id')
    def stage_fullscreen():
        try:
            try:
                app.state('zoomed')
                app.update_idletasks()
            except Exception:
                try:
                    sw = int(app.winfo_screenwidth())
                    sh = int(app.winfo_screenheight())
                    if sw > 0 and sh > 0:
                        app.geometry(f'{sw}x{sh}+0+0')
                        app.update_idletasks()
                except Exception:
                    pass

            def commit_fullscreen():
                try:
                    app.attributes('-fullscreen', True)
                    app.update_idletasks()
                except Exception:
                    pass
                try:
                    app.after(FULLSCREEN_SETTLE_MS, lambda: _finish(app))
                except Exception:
                    _finish(app)
            try:
                app.after(55, commit_fullscreen)
            except Exception:
                commit_fullscreen()
        except Exception:
            _finish(app)
    try:
        app.after_idle(stage_fullscreen)
    except Exception:
        stage_fullscreen()

def _exit(app):
    if getattr(app, '_layout_transition', False) or not getattr(app, 'is_fullscreen', False):
        return
    app._layout_transition = True
    _set_resizing(app, True)
    app.is_fullscreen = False
    _cancel(app, '_resize_after_id')
    try:
        app.attributes('-fullscreen', False)
        app.update_idletasks()
    except Exception:
        pass

    def restore():
        try:
            previous_state = getattr(app, '_previous_window_state', None)
            previous_geometry = getattr(app, '_previous_geometry', None)
            if previous_state == 'zoomed':
                app.state('zoomed')
            else:
                app.state('normal')
                app.update_idletasks()
                if previous_geometry:
                    app.geometry(previous_geometry)
            app.update_idletasks()
        except Exception:
            pass
        _finish(app)
    try:
        app.after(120, restore)
    except Exception:
        restore()

def _toggle(app, event=None):
    _exit(app) if getattr(app, 'is_fullscreen', False) else _enter(app)
    return 'break'

def _escape(app, event=None):
    if getattr(app, 'is_fullscreen', False):
        _exit(app)
        return 'break'

def _install_layout_authority(app):
    _cancel(app, 'resize_timer')
    for seq in ('<Configure>', '<F11>', '<Escape>'):
        try:
            app.unbind(seq)
        except Exception:
            pass
    app._resize_after_id = None
    app._layout_transition = False
    app._previous_geometry = None
    app._previous_window_state = None
    try:
        app.update_idletasks()
        app._layout_last_client_size = (int(app.winfo_width()), int(app.winfo_height()))
    except Exception:
        app._layout_last_client_size = None

    def configure(event):
        try:
            if event.widget is not app or app._layout_transition:
                return
        except Exception:
            return

        # Windows/Tk emite <Configure> tanto al REDIMENSIONAR como al MOVER.
        # Si ancho y alto no cambiaron, es un movimiento puro: no se toca el
        # responsive, no se invalida matplotlib y no se marca is_resizing.
        try:
            width = int(getattr(event, 'width', 0) or app.winfo_width())
            height = int(getattr(event, 'height', 0) or app.winfo_height())
        except Exception:
            return
        size = (width, height)
        previous_size = getattr(app, '_layout_last_client_size', None)
        if previous_size == size:
            return
        app._layout_last_client_size = size

        _set_resizing(app, True)
        # V148: no cancelar/crear un callback Tcl por cada pixel. Se mantiene un
        # único detector trailing que observa la última marca temporal.
        app._layout_last_resize_event = time.monotonic()

        def settle():
            try:
                elapsed_ms = (time.monotonic() - float(getattr(app, '_layout_last_resize_event', 0.0))) * 1000.0
            except Exception:
                elapsed_ms = RESIZE_DEBOUNCE_MS
            if elapsed_ms < RESIZE_DEBOUNCE_MS:
                delay = max(12, int(RESIZE_DEBOUNCE_MS - elapsed_ms))
                try:
                    app._resize_after_id = app.after(delay, settle)
                    return
                except Exception:
                    pass
            app._resize_after_id = None
            _set_resizing(app, False)
            # Mientras una página interna está visible, el Dashboard permanece
            # cacheado debajo y no necesita reestilizarse. Su layout se sincroniza
            # al volver, evitando trabajo y repaints ocultos durante el resize.
            if getattr(app, '_active_internal_page', None):
                app._dashboard_layout_sync_pending = True
                try:
                    from gui.internal_navigation import notify_active_page_geometry
                    app.after_idle(lambda: notify_active_page_geometry(app))
                except Exception:
                    pass
                return
            app._dashboard_layout_sync_pending = False
            _apply_layout(app, force=False)
        if getattr(app, '_resize_after_id', None) is None:
            try:
                app._resize_after_id = app.after(RESIZE_DEBOUNCE_MS, settle)
            except Exception:
                settle()
    app.bind('<Configure>', configure, add=False)
    app.bind('<F11>', lambda e: _toggle(app, e), add=False)
    app.bind('<Escape>', lambda e: _escape(app, e), add=False)
    app.toggle_fullscreen = types.MethodType(lambda self, event=None: _toggle(self, event), app)
    app.exit_fullscreen = types.MethodType(lambda self, event=None: _escape(self, event), app)

def request_chart_reflow(app, redraw=True):
    """Reflujo liviano; nunca pelea con un resize que todavía está en curso."""
    if getattr(app, 'is_resizing', False) or getattr(app, '_layout_transition', False):
        app._chart_reflow_pending = True
        return
    app._chart_reflow_pending = False
    try:
        mode = getattr(app, '_layout_mode', None) or _layout_mode(int(app.winfo_width()), int(app.winfo_height()))
    except Exception:
        mode = 'standard'
    _sync_chart_figure_geometry(app, mode)
    if redraw:
        try:
            app.canvas.draw_idle()
        except Exception:
            pass


def _install_chart_geometry_authority(app):
    if getattr(app, '_chart_geometry_authority_active', False):
        return

    def on_frame_configure(event=None):
        frame = getattr(app, 'frame_charts', None)
        try:
            if frame is None or (event is not None and event.widget is not frame):
                return
        except Exception:
            return
        _cancel(app, '_chart_reflow_after_id')

        def settle():
            app._chart_reflow_after_id = None
            if getattr(app, 'is_resizing', False) or getattr(app, '_layout_transition', False):
                app._chart_reflow_pending = True
                return
            request_chart_reflow(app, redraw=False)
        try:
            app._chart_reflow_after_id = app.after(70, settle)
        except Exception:
            settle()

    try:
        app.frame_charts.bind('<Configure>', on_frame_configure, add='+')
    except Exception:
        pass
    app._chart_geometry_authority_active = True


def apply_dashboard_architecture(app):
    if getattr(app, '_dashboard_layout_active', False):
        return
    _style_sidebar(app)
    _style_status_band(app)
    _style_hardware(app)
    _style_charts(app)
    _install_chart_geometry_authority(app)
    _install_agent_route(app)
    _build_agent_card(app)
    render_agent_card(app)
    _install_storage_route(app)
    _install_layout_authority(app)
    app._dashboard_layout_active = True
    app._corepulse_design_id = DESIGN_ID

    # V0.10.2.28w: aplica una geometría responsiva inicial aunque Windows no
    # emita otro <Configure> después de instalar la autoridad de layout.
    try:
        app.after_idle(lambda: _apply_layout(app, force=True))
    except Exception:
        _apply_layout(app)
