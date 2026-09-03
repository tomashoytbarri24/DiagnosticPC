"""Navegación interna robusta de CorePulse.

La navegación evita condiciones de carrera:
- solo la última solicitud rápida se ejecuta (debounce en sidebar);
- cada página se construye en un host propio;
- el cambio visible se confirma de forma síncrona, sin callbacks after_idle pendientes;
- una página antigua nunca puede reaparecer después de una más nueva;
- mientras una vista se construye, los clics nuevos se almacenan y solo se ejecuta el último.
"""
from __future__ import annotations
from core.theme_manager import color as theme_color

import customtkinter as ctk
from gui.render_polish import polish_widget_tree

BG = theme_color('#06111f')

PAGE_BUTTONS = {
    'dashboard': '_btn_summary',
    'overlay': 'btn_overlay',
    'diagnostic': 'btn_diagnostic',
    'health_center': 'btn_health_center',
    'cleanup': 'btn_cleanup',
    'tweaks': 'btn_tweaks',
    'network': 'btn_network',
    'alerts': 'btn_smart_alerts',
    'trends': 'btn_session_trends',
    'history': 'btn_alert_history',
    'storage_details': None,
    'telemetry_details': None,
    'cpu_details': None,
    'gpu_details': None,
    'ram_details': None,
}

PAGE_PANEL_REFS = {
    'overlay': 'overlay_config_panel',
    'diagnostic': 'diagnostic_experience_panel',
    'health_center': 'health_center_panel',
    'cleanup': 'cleaning_center_panel',
    'tweaks': 'windows_tweaks_panel',
    'network': 'network_detail_panel',
    'alerts': 'smart_alert_panel',
    'trends': 'session_trends_panel',
    'history': 'alert_history_panel',
    'storage_details': 'storage_detail_panel',
    'telemetry_details': 'telemetry_detail_panel',
    'cpu_details': 'cpu_detail_panel',
    'gpu_details': 'gpu_detail_panel',
    'ram_details': 'ram_detail_panel',
}

PANEL_REFS = tuple(PAGE_PANEL_REFS.values())


def _exists(widget):
    try:
        return bool(widget is not None and widget.winfo_exists())
    except Exception:
        return False


def _panel_widget(panel):
    if panel is None:
        return None
    if hasattr(panel, 'widget'):
        try:
            return panel.widget()
        except Exception:
            return None
    return panel


def _mark_panel_inactive(panel):
    if panel is None:
        return
    if hasattr(panel, '_alive'):
        try:
            panel._alive = False
        except Exception:
            pass
    if hasattr(panel, '_closed'):
        try:
            panel._closed = True
        except Exception:
            pass


def _refresh_nav(app, context):
    try:
        from gui.ui_consistency import refresh_navigation_state
        refresh_navigation_state(app, context=context)
    except Exception:
        app._navigation_context = context


def _cancel_debounce(app):
    after_id = getattr(app, '_navigation_debounce_after', None)
    if after_id:
        try:
            app.after_cancel(after_id)
        except Exception:
            pass
    app._navigation_debounce_after = None


def cancel_navigation_request(app):
    """Cancela solicitudes pendientes sin interrumpir una vista en construcción."""
    _cancel_debounce(app)
    app._navigation_requested_key = None
    app._navigation_queued_request = None
    app._navigation_request_generation = int(getattr(app, '_navigation_request_generation', 0) or 0) + 1


def _schedule_queued_navigation(app, delay_ms=1):
    queued = getattr(app, '_navigation_queued_request', None)
    app._navigation_queued_request = None
    if not queued:
        return
    generation, page_key, callback = queued
    if generation != int(getattr(app, '_navigation_request_generation', 0) or 0):
        return

    def run_queued():
        if generation != int(getattr(app, '_navigation_request_generation', 0) or 0):
            return
        if getattr(app, '_navigation_building', False):
            app._navigation_queued_request = (generation, page_key, callback)
            return
        app._navigation_building = True
        try:
            callback()
        finally:
            app._navigation_building = False
            _schedule_queued_navigation(app)

    try:
        app._navigation_debounce_after = app.after(int(delay_ms), run_queued)
    except Exception:
        app._navigation_debounce_after = None
        run_queued()


def request_navigation(app, page_key, callback, delay_ms=55):
    """Ejecuta una sola transición y conserva únicamente el último clic recibido.

    Si una vista está en plena construcción, NO se destruye su host. El clic nuevo
    queda en cola y reemplaza cualquier solicitud anterior; se ejecutará al terminar
    la construcción actual. Esto evita destruir widgets de CustomTkinter a mitad de
    su __init__, incluido el canvas interno de controles complejos.
    """
    page_key = str(page_key or 'dashboard').strip().lower()
    if page_key not in PAGE_BUTTONS:
        page_key = 'dashboard'

    _cancel_debounce(app)
    generation = int(getattr(app, '_navigation_request_generation', 0) or 0) + 1
    app._navigation_request_generation = generation
    app._navigation_requested_key = page_key
    _refresh_nav(app, page_key)

    if getattr(app, '_navigation_building', False):
        app._navigation_queued_request = (generation, page_key, callback)
        return

    def run_latest():
        if generation != int(getattr(app, '_navigation_request_generation', 0) or 0):
            return
        app._navigation_debounce_after = None
        app._navigation_requested_key = None
        app._navigation_building = True
        try:
            callback()
        finally:
            app._navigation_building = False
            _schedule_queued_navigation(app)

    try:
        app._navigation_debounce_after = app.after(int(delay_ms), run_latest)
    except Exception:
        app._navigation_debounce_after = None
        run_latest()


def _pending(app):
    value = getattr(app, '_internal_page_pending', None)
    return value if isinstance(value, dict) else None


def _discard_pending(app):
    pending = _pending(app)
    if pending:
        panel = pending.get('panel')
        _mark_panel_inactive(panel)
        transition = pending.get('transition')
        if _exists(transition):
            try:
                transition.destroy()
            except Exception:
                pass
        host = pending.get('host')
        if _exists(host):
            try:
                host.destroy()
            except Exception:
                pass
    app._internal_page_pending = None
    app._internal_page_pending_host = None
    app._internal_page_pending_key = None
    app._internal_page_build_host = None


def _retire_page(app, page_key, host, panel):
    """Retira una página anterior después de que la siguiente ya está visible."""
    _mark_panel_inactive(panel)
    panel_attr = PAGE_PANEL_REFS.get(str(page_key or '').lower())
    if panel_attr and getattr(app, panel_attr, None) is panel:
        try:
            setattr(app, panel_attr, None)
        except Exception:
            pass
    if _exists(host):
        try:
            host.destroy()
        except Exception:
            pass


def clear_internal_page(app):
    """Retira cualquier página interna y vuelve a dejar visible el Dashboard base."""
    _discard_pending(app)

    active_key = getattr(app, '_active_internal_page', None)
    active_host = getattr(app, '_internal_page_host', None)
    active_attr = PAGE_PANEL_REFS.get(str(active_key or '').lower())
    active_panel = getattr(app, active_attr, None) if active_attr else None

    _retire_page(app, active_key, active_host, active_panel)

    # Limpia referencias antiguas que pudieran venir de versiones previas.
    for attr in PANEL_REFS:
        panel = getattr(app, attr, None)
        widget = _panel_widget(panel)
        if panel is not active_panel and panel is not None and not _exists(widget):
            _mark_panel_inactive(panel)
            try:
                setattr(app, attr, None)
            except Exception:
                pass

    app._internal_page_host = None
    app._active_internal_page = None


def activate_internal_page(app, page_key):
    """Inicia la construcción de una página en un host aislado.

    La función NO agenda un commit futuro. El creador de la página debe llamar a
    ``commit_internal_page`` cuando todos sus widgets ya estén construidos.
    """
    page_key = str(page_key or '').strip().lower()
    if page_key not in PAGE_BUTTONS or page_key == 'dashboard':
        show_dashboard(app)
        return (None, False)

    current_host = getattr(app, '_internal_page_host', None)
    current_key = getattr(app, '_active_internal_page', None)
    if current_key == page_key and _exists(current_host):
        try:
            current_host.lift()
        except Exception:
            pass
        _refresh_nav(app, page_key)
        return (current_host, True)

    # Nunca dejamos un host de una transición anterior esperando commit.
    _discard_pending(app)

    old_host = current_host if _exists(current_host) else None
    old_key = current_key
    old_panel_attr = PAGE_PANEL_REFS.get(str(old_key or '').lower())
    old_panel = getattr(app, old_panel_attr, None) if old_panel_attr else None

    generation = int(getattr(app, '_internal_page_generation', 0) or 0) + 1
    app._internal_page_generation = generation

    parent = getattr(app, 'main_content', app)
    host = ctk.CTkFrame(parent, fg_color=BG, corner_radius=0)
    # La página se construye fuera del viewport. Algunos CTk widgets crean
    # canvases/ventanas Tk hijas que pueden atravesar una capa superpuesta si el
    # host ya está mapeado; mantenerlo fuera de pantalla elimina ese bleed.
    host.place(x=-20000, y=0, relwidth=1, relheight=1)

    # Transición sin flash: la vista actual permanece visible mientras la nueva
    # se construye fuera del viewport. El commit hace un intercambio atómico.
    # Esto evita el panel gris/blanco de carga que producía parpadeos perceptibles.
    transition = None
    try:
        app.configure(cursor='watch')
    except Exception:
        pass

    pending = {
        'generation': generation,
        'key': page_key,
        'host': host,
        'transition': transition,
        'panel': None,
        'old_host': old_host,
        'old_key': old_key,
        'old_panel': old_panel,
    }
    app._internal_page_pending = pending
    # Alias de compatibilidad con código anterior y autoridad explícita para los
    # paneles que resuelven su parent desde ``app``.
    app._internal_page_pending_host = host
    app._internal_page_pending_key = page_key
    app._internal_page_build_host = host
    return (host, False)


def commit_internal_page(app, page_key, host, panel=None):
    """Publica una página ya construida y elimina la anterior de forma atómica."""
    page_key = str(page_key or '').strip().lower()
    pending = _pending(app)
    if not pending or pending.get('host') is not host or pending.get('key') != page_key:
        _mark_panel_inactive(panel)
        if _exists(host) and host is not getattr(app, '_internal_page_host', None):
            try:
                host.destroy()
            except Exception:
                pass
        return False

    if int(pending.get('generation') or -1) != int(getattr(app, '_internal_page_generation', 0) or 0):
        _discard_pending(app)
        return False

    pending['panel'] = panel

    if not _exists(host):
        _discard_pending(app)
        return False

    try:
        host.update_idletasks()
    except Exception:
        pass
    try:
        polish_widget_tree(host)
    except Exception:
        pass
    try:
        # Publicación atómica: primero se trae el host al viewport, se deja que
        # Tk resuelva geometría y recién entonces se retira el loader.
        host.place_configure(x=0, y=0, relx=0, rely=0, relwidth=1, relheight=1)
        host.update_idletasks()
        host.lift()
    except Exception:
        pass
    transition = pending.get('transition')
    if _exists(transition):
        try:
            transition.destroy()
        except Exception:
            pass
    try:
        app.configure(cursor='')
    except Exception:
        pass

    old_host = pending.get('old_host')
    old_key = pending.get('old_key')
    old_panel = pending.get('old_panel')

    app._internal_page_host = host
    app._active_internal_page = page_key
    app._internal_page_pending = None
    app._internal_page_pending_host = None
    app._internal_page_pending_key = None
    app._internal_page_build_host = None

    panel_attr = PAGE_PANEL_REFS.get(page_key)
    if panel_attr:
        try:
            setattr(app, panel_attr, panel)
        except Exception:
            pass

    _refresh_nav(app, page_key)

    if old_host is not None and old_host is not host:
        _retire_page(app, old_key, old_host, old_panel)
    return True


def abort_internal_page(app, page_key=None, host=None, panel=None):
    """Descarta una construcción fallida sin tocar la página que seguía visible."""
    pending = _pending(app)
    if pending and (host is None or pending.get('host') is host):
        _mark_panel_inactive(panel or pending.get('panel'))
        transition = pending.get('transition')
        if _exists(transition):
            try:
                transition.destroy()
            except Exception:
                pass
        pending_host = pending.get('host')
        if _exists(pending_host):
            try:
                pending_host.destroy()
            except Exception:
                pass
        app._internal_page_pending = None
        app._internal_page_pending_host = None
        app._internal_page_pending_key = None
        app._internal_page_build_host = None
    try:
        app.configure(cursor='')
    except Exception:
        pass
    active = getattr(app, '_active_internal_page', None) or 'dashboard'
    _refresh_nav(app, active)


def _redraw_dashboard(app):
    """Fuerza el repintado del canvas TkAgg después de descubrirlo."""
    try:
        canvas = getattr(app, 'canvas', None)
        if canvas is not None:
            widget = canvas.get_tk_widget()
            try:
                widget.configure(bg=theme_color('#0d1828'), highlightthickness=0)
            except Exception:
                pass
            canvas.draw()
    except Exception:
        pass


def show_dashboard(app):
    """Vuelve al Dashboard con un único repintado visible del canvas."""
    cancel_navigation_request(app)
    clear_internal_page(app)
    _refresh_nav(app, 'dashboard')
    try:
        app.main_content.lift()
        app.main_content.update_idletasks()
    except Exception:
        pass
    # Un solo draw síncrono evita el rectángulo sin pintar sin producir tres
    # flashes consecutivos como ocurría en revisiones anteriores.
    _redraw_dashboard(app)
    try:
        app.after_idle(lambda: getattr(getattr(app, 'canvas', None), 'draw_idle', lambda: None)())
    except Exception:
        pass


def active_page(app):
    pending = _pending(app)
    if pending:
        return pending.get('key') or 'dashboard'
    return getattr(app, '_active_internal_page', None) or 'dashboard'
