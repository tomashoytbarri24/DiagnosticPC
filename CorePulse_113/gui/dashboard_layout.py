"""Administra la distribución responsiva del dashboard, navegación y tarjeta del agente."""
from __future__ import annotations
from core.theme_manager import color as theme_color, theme_action_label
# Código refactorizado: nombres estables y documentación en español.
import threading, types
import customtkinter as ctk
from core.version import VERSION_LABEL
from core.agent_reaction import agent_display_state
VERSION = VERSION_LABEL
DESIGN_ID = 'COREPULSE_REFERENCE_DASHBOARD_LAYOUT'
FONT = 'Segoe UI'
ICON_FONT = 'Segoe UI Symbol'
APP = theme_color('#06111f')
SIDEBAR = theme_color(theme_color('#071522'))
SURFACE = theme_color('#0b1726')
SURFACE_2 = theme_color('#0e1d2f')
BORDER = theme_color('#17314d')
BORDER_SOFT = theme_color(theme_color('#102943'))
TRACK = theme_color(theme_color('#132741'))
TEXT = theme_color('#f4f7fb')
TEXT_2 = theme_color('#c2ccda')
MUTED = theme_color('#8295ad')
CYAN = '#08aef0'
GREEN = '#16d98b'
AMBER = '#f3b54a'
RED = '#ff5d6c'
PURPLE = '#a064ff'
PRIMARY_DARK = theme_color('#164f7d')
SIDEBAR_ACTIVE_BG = theme_color('#0c2941')
SIDEBAR_ACTIVE_HOVER = theme_color('#123b59')
SIDEBAR_ACTIVE_BORDER = theme_color('#17658f')
SIDEBAR_INACTIVE_TEXT = theme_color('#c2ccda')
RESIZE_DEBOUNCE_MS = 85
FULLSCREEN_SETTLE_MS = 420
NAV = {'_btn_summary': 'Resumen', 'btn_diagnostic': 'Iniciar diagnóstico', 'btn_health_center': 'Centro de salud', 'btn_cleanup': 'Limpieza de sistema', 'btn_tweaks': 'Tweaks Windows 11', 'btn_network': 'Red avanzada', 'btn_smart_alerts': 'Alertas y diagnóstico', 'btn_session_trends': 'Tendencias', 'btn_alert_history': 'Historial de alertas', '_theme_toggle_button': 'Temas'}

def _cfg(w, **kw):
    if w is None:
        return
    try:
        w.configure(**kw)
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
    _cfg(app.sidebar, width=224, fg_color=SIDEBAR)
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
            height=34,
            corner_radius=9,
            font=(FONT, 10, 'bold'),
            anchor='w',
            padx=12,
            text_color=CYAN if active else SIDEBAR_INACTIVE_TEXT,
            fg_color=SIDEBAR_ACTIVE_BG if active else 'transparent',
            hover_color=SIDEBAR_ACTIVE_HOVER if active else SURFACE_2,
            border_width=1 if active else 0,
            border_color=SIDEBAR_ACTIVE_BORDER,
        )
    _cfg(getattr(app, '_sidebar_version', None), text=f'{VERSION_LABEL} · Cereon Technologies', font=(FONT, 7), text_color=MUTED)
    _cfg(getattr(app, '_theme_toggle_button', None), text='Temas', height=31, corner_radius=9, fg_color='transparent', hover_color=SURFACE_2, border_width=1, border_color=BORDER, text_color=TEXT_2, font=(FONT, 9, 'bold'))


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
    _destroy_existing_agent_cards(app)
    card = ctk.CTkFrame(app.sidebar, fg_color=SURFACE, border_width=1, border_color=BORDER, corner_radius=11, height=122)
    card.pack_propagate(False)
    card.grid_propagate(False)
    card.grid_columnconfigure(0, weight=1)
    card.grid_rowconfigure(4, weight=1)

    title_row = ctk.CTkFrame(card, fg_color='transparent')
    title_row.grid(row=0, column=0, sticky='ew', padx=12, pady=(9, 2))
    title_row.grid_columnconfigure(0, weight=1)
    title = ctk.CTkLabel(title_row, text='ESTADO DEL AGENTE', height=17, font=(FONT, 8, 'bold'), text_color=TEXT_2, anchor='w')
    title.grid(row=0, column=0, sticky='w')
    badge = ctk.CTkLabel(title_row, text='Tiempo real', height=17, font=(FONT, 7, 'bold'), text_color=CYAN, fg_color=theme_color('#0d2942'), corner_radius=8, padx=7, pady=1)
    badge.grid(row=0, column=1, sticky='e')

    row = ctk.CTkFrame(card, fg_color='transparent', height=19)
    row.grid(row=1, column=0, sticky='ew', padx=12, pady=(1, 1))
    row.pack_propagate(False)
    dot = ctk.CTkLabel(row, text='●', width=12, height=16, font=(FONT, 9, 'bold'), text_color=GREEN)
    dot.pack(side='left', padx=(0, 5))
    status = ctk.CTkLabel(row, text='INICIALIZANDO', height=16, font=(FONT, 9, 'bold'), text_color=CYAN, anchor='w')
    status.pack(side='left')

    mode = ctk.CTkLabel(card, text='Escritorio', height=15, font=(FONT, 7, 'bold'), text_color=MUTED, anchor='w')
    mode.grid(row=2, column=0, sticky='ew', padx=12, pady=(2, 0))
    state = ctk.CTkLabel(card, text='Evaluando evidencia', height=16, font=(FONT, 8, 'bold'), text_color=CYAN, anchor='w')
    state.grid(row=3, column=0, sticky='ew', padx=12, pady=(1, 0))
    detail = ctk.CTkLabel(card, text='Acumulando evidencia del sistema…', height=18, font=(FONT, 7), text_color=MUTED, anchor='nw', justify='left', wraplength=174)
    detail.grid(row=4, column=0, sticky='nsew', padx=12, pady=(3, 8))

    app._agent_card = card
    app._agent_title = title
    app._agent_badge = badge
    app._agent_dot = dot
    app._agent_status = status
    app._agent_mode = mode
    app._agent_state = state
    app._agent_detail = detail

    ver = getattr(app, '_sidebar_version', None)
    try:
        if ver is not None:
            ver.pack_forget()
        card.pack_forget()
    except Exception:
        pass

    theme_button = getattr(app, '_theme_toggle_button', None)
    try:
        if theme_button is not None:
            theme_button.pack_forget()
    except Exception:
        pass
    try:
        # El agente baja un poco para respirar respecto a la navegación.
        card.pack(side='top', fill='x', padx=11, pady=(20, 8))
    except Exception:
        pass
    if theme_button is not None:
        try:
            # 'Temas' sube y queda asociado visualmente al bloque del agente.
            theme_button.pack(side='top', fill='x', padx=12, pady=(8, 4))
        except Exception:
            pass
    if ver is not None:
        try:
            # La versión queda en la esquina inferior del sidebar.
            ver.pack(side='bottom', fill='x', padx=14, pady=(3, 10))
        except Exception:
            pass


def render_agent_card(app, state=None):
    card = getattr(app, '_agent_card', None)
    try:
        invalid = card is None or not card.winfo_exists()
    except Exception:
        invalid = True
    if invalid:
        try:
            _build_agent_card(app)
        except Exception:
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
    _cfg(app._agent_detail, text=display['detail'], text_color=MUTED)
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
    """Mide el contenido REAL para que Almacenamiento no robe espacio a Tendencias."""
    widgets = list((getattr(app, 'disk_widgets', {}) or {}).values())
    count = len(widgets)
    if count == 0:
        return 64 if mode == 'compact' else 70
    # V111 evita update_idletasks() dentro del resize: forzar el event loop aquí
    # podía encadenar nuevos <Configure> y producir el efecto de "desarmado".
    # StableScrollHost ya mantiene un frame interno que conoce el alto real de
    # todas las tarjetas. Usarlo evita sumar requests inflados y elimina la zona
    # transparente que antes quedaba debajo de uno o dos discos.
    content_host = getattr(getattr(app, 'scroll_disks', None), 'content', None)
    try:
        content = int(content_host.winfo_reqheight()) + 4 if content_host is not None else 0
    except Exception:
        content = 0
    if content <= 0:
        heights = []
        for item in widgets:
            card = item.get('card') if isinstance(item, dict) else None
            try:
                heights.append(max(54, int(card.winfo_reqheight()) + 2))
            except Exception:
                heights.append(58)
        content = sum(heights) + 4

    if count <= 2:
        cap = {'compact': 142, 'standard': 154, 'large': 164}.get(mode, 154)
        return max(68, min(content, cap))
    cap = {'compact': 146, 'standard': 160, 'large': 174}.get(mode, 160)
    return min(content, cap)

def _sync_storage_height(app, mode=None):
    if mode is None:
        mode = getattr(app, '_layout_mode', 'standard')
    count = len(getattr(app, 'disk_widgets', {}) or {})
    target_h = _storage_height_for(app, mode)
    _cfg(getattr(app, 'scroll_disks', None), height=target_h)
    try:
        # V0.10.2.28w — Storage Viewport Geometry Fix
        # StableScrollHost usa un tk.Canvas administrado con grid. El Canvas tiene
        # un tamaño solicitado propio y, con grid_propagate(True), puede imponer
        # ~200-300 px al host aunque Dashboard configure una altura menor. Ese era
        # el espacio vacío real que empujaba los gráficos hacia abajo.
        #
        # La autoridad vertical queda aquí: host = target_h; Canvas = fill interno.
        app.scroll_disks.grid_propagate(False)
        app.scroll_disks.pack_configure(
            fill='x',
            expand=False,
            pady=(0, 4 if mode == 'compact' else 5),
        )
    except Exception:
        pass
    _hide_storage_scrollbar_if_possible(app, count)

def _style_storage_widgets(app):
    _cfg(getattr(app, 'scroll_disks', None), fg_color='transparent')
    for widgets in getattr(app, 'disk_widgets', {}).values():
        card = widgets.get('card')
        name = widgets.get('lbl_name')
        badge = widgets.get('lbl_badge')
        exact = widgets.get('lbl_exact')
        bar = widgets.get('bar')
        try:
            card.pack_propagate(True)
        except Exception:
            pass
        _cfg(card, fg_color=SURFACE, border_color=BORDER, border_width=1, corner_radius=11)
        try:
            card.pack_configure(fill='x', expand=False, padx=2, pady=2)
        except Exception:
            pass
        if name is not None:
            cur = _text(name)
            for prefix in ('💾 ', '▰  ', '▰ '):
                while cur.startswith(prefix):
                    cur = cur[len(prefix):].strip()
            _cfg(name, text=cur, font=(FONT, 10, 'bold'), text_color=TEXT, anchor='w')
        _cfg(badge, font=(FONT, 9, 'bold'))
        _cfg(exact, font=(FONT, 9), text_color=CYAN, anchor='w')
        _cfg(bar, height=5, fg_color=TRACK, progress_color=CYAN)
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
        _cfg(card, fg_color=SURFACE, border_color=BORDER, border_width=1, corner_radius=12, height=126)
        try:
            card.pack_propagate(False)
        except Exception:
            pass
        _cfg(title, font=(FONT, 9, 'bold'), text_color=TEXT_2, anchor='w', justify='left')
        _cfg(value, font=(FONT, 28, 'bold'), text_color=TEXT, anchor='w')
        _cfg(detail, font=(FONT, 9, 'bold'), text_color=accent, anchor='w', justify='left')
        _cfg(bar, height=5, progress_color=accent, fg_color=TRACK)
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
    width = 210 if compact else 224 if standard else 236
    _cfg(app.sidebar, width=width, fg_color=SIDEBAR)

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
                top_gap = 8 if compact else 12 if standard else 14
                if has_brand_block:
                    top_gap = 0
            else:
                top_gap = 5 if compact else 8
            label.pack_configure(padx=15 if compact else 17, pady=(top_gap, 2 if compact else 3))
        except Exception:
            pass
        _cfg(label, height=16 if compact else 18, font=(FONT, 7 if compact else 8, 'bold'))

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
    }
    active_attr = context_button.get(str(getattr(app, '_navigation_context', 'dashboard')).lower(), '_btn_summary')
    for attr in NAV:
        b = getattr(app, attr, None)
        if b is None:
            continue
        active = attr == active_attr
        _cfg(
            b,
            height=30 if compact else 33 if standard else 34,
            font=(FONT, 9 if compact else 10, 'bold'),
            corner_radius=8 if compact else 9,
            padx=10 if compact else 12,
            text_color=CYAN if active else SIDEBAR_INACTIVE_TEXT,
            fg_color=SIDEBAR_ACTIVE_BG if active else 'transparent',
            hover_color=SIDEBAR_ACTIVE_HOVER if active else SURFACE_2,
            border_width=1 if active else 0,
            border_color=SIDEBAR_ACTIVE_BORDER,
        )
        try:
            b.pack_configure(padx=9 if compact else 11, pady=0 if compact else 1)
        except Exception:
            pass

    card = getattr(app, '_agent_card', None)
    if card is not None:
        target_h = 112 if compact else 122 if standard else 126
        _cfg(card, height=target_h, corner_radius=11)
        try:
            card.pack_propagate(False)
            card.grid_propagate(False)
            try:
                current_side = str(card.pack_info().get('side') or '')
            except Exception:
                current_side = ''
            if current_side != 'top':
                card.pack_forget()
                card.pack(side='top', fill='x', padx=9 if compact else 11, pady=(16 if compact else 20, 8))
            else:
                card.pack_configure(fill='x', padx=9 if compact else 11, pady=(16 if compact else 20, 8))
        except Exception:
            pass
        _cfg(getattr(app, '_agent_title', None), height=16, font=(FONT, 7 if compact else 8, 'bold'))
        _cfg(getattr(app, '_agent_badge', None), height=16, font=(FONT, 6 if compact else 7, 'bold'))
        _cfg(getattr(app, '_agent_status', None), height=16, font=(FONT, 8 if compact else 9, 'bold'))
        _cfg(getattr(app, '_agent_mode', None), height=14, font=(FONT, 6 if compact else 7, 'bold'))
        _cfg(getattr(app, '_agent_state', None), height=15, font=(FONT, 7 if compact else 8, 'bold'))
        _cfg(getattr(app, '_agent_detail', None), height=16 if compact else 18, font=(FONT, 6 if compact else 7), wraplength=158 if compact else 174 if standard else 186, anchor='nw')
        try:
            app._agent_detail.grid(sticky='nsew')
        except Exception:
            pass

    theme_button = getattr(app, '_theme_toggle_button', None)
    _cfg(theme_button, height=29 if compact else 31, corner_radius=8 if compact else 9)
    try:
        if theme_button is not None:
            theme_button.pack_configure(side='top', fill='x', padx=10 if compact else 12, pady=(8 if compact else 10, 4 if compact else 5))
    except Exception:
        pass

    ver = getattr(app, '_sidebar_version', None)
    _cfg(ver, text=f'{VERSION_LABEL} · Cereon Technologies', font=(FONT, 6 if compact else 7), text_color=MUTED)
    try:
        ver.pack_configure(side='bottom', fill='x', padx=11 if compact else 14, pady=(3, 8 if compact else 10))
    except Exception:
        pass


def _style_header_mode(app, mode):
    compact = mode == 'compact'
    header = getattr(app, '_header', None)
    try:
        header.pack_configure(fill='x', pady=(0, 5 if compact else 7))
        _cfg(header, height=62 if compact else 68 if mode == 'standard' else 72)
    except Exception:
        pass
    # La identidad del equipo tiene una autoridad visual explícita.
    # Antes este bloque tomaba el primer Label del header por posición y lo
    # trataba como el antiguo título, sobrescribiendo el modelo a 23/26/28 px.
    # Eso hacía inútiles los tamaños definidos en dashboard.py.
    identity = getattr(app, '_header_identity', None)
    try:
        if identity is not None:
            left_pad = 18 if compact else 28 if mode == 'standard' else 36
            identity.pack_configure(padx=(left_pad, 18))
    except Exception:
        pass
    brand = getattr(app, '_header_brand_icon', None)
    try:
        if brand is not None:
            brand.pack_configure(padx=(4, 14), pady=(8 if compact else 9, 6))
    except Exception:
        pass

    _cfg(
        getattr(app, '_header_device_model', None),
        font=(FONT, 12 if compact else 13, 'bold'),
        text_color=TEXT,
        anchor='w',
        justify='left',
        wraplength=500 if compact else 660,
    )
    _cfg(
        getattr(app, '_header_brand_icon', None),
        width=46,
        height=46,
    )
    _cfg(getattr(app, '_header_last_update', None), font=(FONT, 7 if compact else 8 if mode == 'standard' else 9))
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
        _cfg(card, fg_color=SURFACE, border_color=BORDER, border_width=1, corner_radius=12)


def _style_status_mode(app, mode):
    band = getattr(app, '_status_band', None)
    if band is None:
        return
    compact = mode == 'compact'
    standard = mode == 'standard'
    height = 90 if compact else 100 if standard else 106
    _cfg(band, height=height)
    try:
        band.pack_configure(fill='x', pady=(0, 5 if compact else 8))
    except Exception:
        pass

    for card in getattr(app, '_status_cards', ()):
        _cfg(card, height=height, corner_radius=11 if compact else 12)

    icon_size = 34 if compact else 39 if standard else 43
    icon_font = 15 if compact else 17 if standard else 19
    for attr in ('_health_icon', '_alert_icon', '_coverage_icon', '_uptime_icon'):
        _cfg(getattr(app, attr, None), width=icon_size, height=icon_size, corner_radius=icon_size // 2, font=(ICON_FONT, icon_font, 'bold'))

    _cfg(getattr(app, '_health_status', None), font=(FONT, 13 if compact else 14 if standard else 15, 'bold'))
    _cfg(getattr(app, '_health_score', None), font=(FONT, 7 if compact else 8))
    for attr in ('_alert_value', '_coverage_value', '_uptime_value'):
        _cfg(getattr(app, attr, None), font=(FONT, 11 if compact else 13 if standard else 15, 'bold'))
    for attr in ('_alert_detail', '_coverage_detail', '_uptime_detail'):
        _cfg(getattr(app, attr, None), font=(FONT, 7 if compact else 8))


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
    ratio = 0.33 if mode == 'compact' else 0.37 if mode == 'standard' else 0.40
    target = int(height * ratio)
    minimum = 286 if mode == 'compact' else 326 if mode == 'standard' else 352
    maximum = 360 if mode == 'compact' else 420 if mode == 'standard' else 468
    if width >= 1700:
        target += 12
    return max(minimum, min(target, maximum))


def _style_charts(app):
    _cfg(app.frame_charts, fg_color=SURFACE, border_color=BORDER, border_width=1, corner_radius=12)
    try:
        max_points = max(2, int(getattr(app, 'max_points', 25) or 25))
        ticks = _chart_tick_positions(max_points)
        labels = ['-60s', '-45s', '-30s', '-15s', 'Ahora']
        app.fig.set_facecolor(SURFACE)
        axes = (app.ax_cpu, app.ax_ram, app.ax_gpu)
        for ax in axes:
            ax.set_facecolor(theme_color('#0f1827'))
            ax.tick_params(axis='x', colors=MUTED, labelsize=8, length=0, pad=6)
            ax.tick_params(axis='y', colors=MUTED, labelsize=8, length=0, pad=6, labelleft=True)
            ax.grid(False)
            ax.yaxis.grid(True, color=BORDER_SOFT, linestyle='-', linewidth=0.45, alpha=0.65)
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
        app.fig.subplots_adjust(left=0.052, right=0.985, top=0.86, bottom=0.22, wspace=0.18)
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
        fig.subplots_adjust(left=0.052, right=0.985, top=0.86, bottom=0.22, wspace=0.18)
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
            pady=(6 if mode == 'compact' else 8, 0),
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

    meter_h = 108 if mode == 'compact' else 118 if mode == 'standard' else 126
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
    app.is_resizing = False
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
    app.is_resizing = True
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
    app.is_resizing = True
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

        app.is_resizing = True
        _cancel(app, '_resize_after_id')

        def settle(expected=size):
            app._resize_after_id = None
            if getattr(app, '_layout_last_client_size', None) != expected:
                return
            app.is_resizing = False
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
