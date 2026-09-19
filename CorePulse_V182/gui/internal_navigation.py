"""Navegación interna robusta de CorePulse.

La navegación evita condiciones de carrera:
- solo la última solicitud rápida se ejecuta (debounce en sidebar);
- cada página se construye en un host propio;
- el cambio visible se confirma de forma síncrona, sin callbacks after_idle pendientes;
- una página antigua nunca puede reaparecer después de una más nueva;
- mientras una vista se construye, los clics nuevos se almacenan y solo se ejecuta el último.
"""
from __future__ import annotations
import platform
from core.theme_manager import color as theme_color

import customtkinter as ctk
from gui.render_polish import polish_widget_tree
from gui.high_refresh import DEFAULT_NAVIGATION_DEBOUNCE_MS, get_ui_refresh_policy

BG = theme_color('#06111f')

PAGE_BUTTONS = {
    'dashboard': '_btn_summary',
    'benchmark': 'btn_benchmark',
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
    'storage_details': None,
    'telemetry_details': None,
    'cpu_details': None,
    'gpu_details': None,
    'ram_details': None,
}

PAGE_PANEL_REFS = {
    'benchmark': 'benchmark_panel',
    'gaming': 'gaming_panel',
    'overlay': 'overlay_config_panel',
    'diagnostic': 'diagnostic_experience_panel',
    'health_center': 'health_center_panel',
    'cleanup': 'cleaning_center_panel',
    'tweaks': 'windows_tweaks_panel',
    'network': 'network_detail_panel',
    'alerts': 'smart_alert_panel',
    'trends': 'session_trends_panel',
    'history': 'alert_history_panel',
    'themes': 'theme_panel',
    'updates': 'update_panel',
    'storage_details': 'storage_detail_panel',
    'telemetry_details': 'telemetry_detail_panel',
    'cpu_details': 'cpu_detail_panel',
    'gpu_details': 'gpu_detail_panel',
    'ram_details': 'ram_detail_panel',
}

PANEL_REFS = tuple(PAGE_PANEL_REFS.values())
CACHEABLE_PAGES = {'benchmark', 'gaming', 'diagnostic', 'health_center', 'cleanup', 'tweaks', 'network', 'alerts', 'trends', 'history', 'themes', 'updates', 'cpu_details', 'ram_details', 'gpu_details', 'storage_details'}

PAGE_LABELS = {
    'benchmark': 'Benchmark',
    'gaming': 'Gaming',
    'diagnostic': 'Diagnóstico',
    'health_center': 'Centro de salud',
    'cleanup': 'Limpieza de sistema',
    'tweaks': ('Tweaks Windows 11' if platform.system() == 'Windows' else 'Ajustes Linux'),
    'network': 'Red avanzada',
    'alerts': 'Alertas técnicas',
    'trends': 'Tendencias',
    'history': 'Historial de alertas',
    'themes': 'Temas',
    'updates': 'Actualizaciones',
}




def _clear_navigation_transition(app):
    transition = getattr(app, '_navigation_transition', None)
    if _exists(transition):
        try:
            transition.destroy()
        except Exception:
            pass
    app._navigation_transition = None


def _show_navigation_transition(app, page_key):
    """Cubre la vista anterior con una transición liviana y coherente.

    La transición sólo se usa en la primera construcción de una página. Las
    páginas cacheadas cambian de forma inmediata y nunca muestran loader.
    """
    _clear_navigation_transition(app)
    parent = getattr(app, 'main_content', app)
    try:
        frame = ctk.CTkFrame(parent, fg_color=BG, corner_radius=0)
        frame.place(x=0, y=0, relx=0, rely=0, relwidth=1, relheight=1)
        accent = ctk.CTkFrame(frame, fg_color=theme_color('#14b8ff'), height=3, corner_radius=0)
        accent.pack(fill='x', side='top')
        center = ctk.CTkFrame(frame, fg_color='transparent')
        center.place(relx=0.5, rely=0.46, anchor='center')
        ctk.CTkLabel(center, text='COREPULSE', font=('Segoe UI', 9, 'bold'), text_color=theme_color('#14b8ff')).pack(pady=(0, 7))
        ctk.CTkLabel(center, text=PAGE_LABELS.get(page_key, 'CorePulse'), font=('Segoe UI', 19, 'bold'), text_color=theme_color('#f4f7fb')).pack()
        ctk.CTkLabel(center, text='Preparando vista…', font=('Segoe UI', 9), text_color=theme_color('#8295ad')).pack(pady=(6, 0))
        frame.lift()
        frame.update_idletasks()
        app._navigation_transition = frame
        return frame
    except Exception:
        app._navigation_transition = None
        return None


def _is_cached(app, page_key):
    if page_key == 'dashboard':
        return True
    if page_key == getattr(app, '_active_internal_page', None):
        return True
    cached = _page_cache(app).get(page_key) if page_key in CACHEABLE_PAGES else None
    return bool(isinstance(cached, dict) and _exists(cached.get('host')))

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


def request_navigation(app, page_key, callback, delay_ms=DEFAULT_NAVIGATION_DEBOUNCE_MS):
    """Despacha navegación sin desmontar la vista que el usuario ya está viendo.

    V111 mantiene la página actual completamente estable mientras una vista no
    cacheada se construye fuera del viewport. La nueva página sólo aparece cuando
    ``commit_internal_page`` confirma que está terminada. No hay loader de página,
    flash intermedio ni selección prematura del menú. Las páginas cacheadas siguen
    cambiando de forma inmediata.
    """
    page_key = str(page_key or 'dashboard').strip().lower()
    if page_key not in PAGE_BUTTONS:
        page_key = 'dashboard'

    _cancel_debounce(app)
    generation = int(getattr(app, '_navigation_request_generation', 0) or 0) + 1
    app._navigation_request_generation = generation
    app._navigation_requested_key = page_key

    if getattr(app, '_navigation_building', False):
        app._navigation_queued_request = (generation, page_key, callback)
        return

    def execute_callback():
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

    def begin_transition():
        if generation != int(getattr(app, '_navigation_request_generation', 0) or 0):
            return
        app._navigation_debounce_after = None
        cached = _is_cached(app, page_key)
        if cached:
            _clear_navigation_transition(app)
            _refresh_nav(app, page_key)
            execute_callback()
            return

        # V111: una página nueva se construye detrás de la vista actual. No se
        # coloca ninguna capa sobre el contenido, no se altera la geometría y el
        # estado del sidebar sólo cambia cuando el commit atómico publica la vista.
        # El frame de cortesía permite que Windows termine cualquier click/repaint
        # pendiente antes de empezar a crear widgets fuera de pantalla.
        _clear_navigation_transition(app)
        try:
            frame_ms = max(1, min(8, int(get_ui_refresh_policy().frame_ms)))
            app._navigation_debounce_after = app.after(frame_ms, execute_callback)
        except Exception:
            execute_callback()

    if page_key == 'dashboard':
        _clear_navigation_transition(app)
        _refresh_nav(app, 'dashboard')
        execute_callback()
        return

    try:
        app._navigation_debounce_after = app.after(max(0, int(delay_ms)), begin_transition)
    except Exception:
        begin_transition()


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


def _page_cache(app):
    cache = getattr(app, '_internal_page_cache', None)
    if not isinstance(cache, dict):
        cache = {}
        app._internal_page_cache = cache
    return cache


def _activate_cached_page(app, page_key):
    cached = _page_cache(app).get(page_key)
    if not isinstance(cached, dict):
        return None
    host = cached.get('host'); panel = cached.get('panel')
    if not _exists(host):
        _page_cache(app).pop(page_key, None)
        return None

    old_host = getattr(app, '_internal_page_host', None)
    old_key = getattr(app, '_active_internal_page', None)
    old_attr = PAGE_PANEL_REFS.get(str(old_key or '').lower())
    old_panel = getattr(app, old_attr, None) if old_attr else None
    try:
        host.place_configure(x=0, y=0, relx=0, rely=0, relwidth=1, relheight=1)
        host.lift()
    except Exception:
        pass
    _clear_navigation_transition(app)
    app._internal_page_host = host
    app._active_internal_page = page_key
    panel_attr = PAGE_PANEL_REFS.get(page_key)
    if panel_attr:
        setattr(app, panel_attr, panel)
    try:
        if hasattr(panel, 'set_active'):
            panel.set_active(True)
    except Exception:
        pass
    _refresh_nav(app, page_key)
    if old_host is not None and old_host is not host:
        _retire_page(app, old_key, old_host, old_panel)
    return host, panel


def _retire_page(app, page_key, host, panel):
    """Retira una página; Tweaks se conserva offscreen para reapertura instantánea."""
    page_key = str(page_key or '').lower()
    if page_key in CACHEABLE_PAGES and _exists(host):
        try:
            if hasattr(panel, 'set_active'):
                panel.set_active(False)
        except Exception:
            pass
        try:
            host.place_forget()
        except Exception:
            pass
        _page_cache(app)[page_key] = {'host': host, 'panel': panel}
        return

    _mark_panel_inactive(panel)
    panel_attr = PAGE_PANEL_REFS.get(page_key)
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

    # Nunca dejamos un host de una transición anterior esperando commit, incluso
    # cuando la página solicitada ya está cacheada.
    _discard_pending(app)
    cached = _activate_cached_page(app, page_key) if page_key in CACHEABLE_PAGES else None
    if cached is not None:
        return (cached[0], True)

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
        polish_widget_tree(host)
    except Exception:
        pass
    try:
        # Publicación atómica: el host ya está completamente construido fuera
        # del viewport. Se coloca y eleva en una sola operación; la transición
        # desaparece sólo después, evitando frames con dos páginas mezcladas.
        host.place_configure(x=0, y=0, relx=0, rely=0, relwidth=1, relheight=1)
        host.lift()
    except Exception:
        pass
    _clear_navigation_transition(app)
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
    if page_key in CACHEABLE_PAGES:
        _page_cache(app)[page_key] = {'host': host, 'panel': panel}

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


def attach_internal_page_panel(app, page_key, host, panel):
    """Asocia el panel real a un host que ya fue publicado como shell.

    Las fichas de hardware usan esta ruta para responder al clic en el primer
    frame y construir sus widgets después. No vuelve a ejecutar el pulido global
    del árbol ni remapea la página, evitando trabajo duplicado en el hilo Tk.
    """
    page_key = str(page_key or '').strip().lower()
    if page_key not in PAGE_BUTTONS or not _exists(host) or panel is None:
        return False

    active = (
        getattr(app, '_internal_page_host', None) is host
        and str(getattr(app, '_active_internal_page', '') or '').lower() == page_key
    )

    panel_attr = PAGE_PANEL_REFS.get(page_key)
    if panel_attr:
        try:
            setattr(app, panel_attr, panel)
        except Exception:
            pass

    if page_key in CACHEABLE_PAGES:
        _page_cache(app)[page_key] = {'host': host, 'panel': panel}

    try:
        if hasattr(panel, 'set_active'):
            panel.set_active(bool(active))
    except Exception:
        pass
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
    _clear_navigation_transition(app)
    try:
        app.configure(cursor='')
    except Exception:
        pass
    active = getattr(app, '_active_internal_page', None) or 'dashboard'
    _refresh_nav(app, active)


def _redraw_dashboard(app):
    """Solicita el próximo repaint del Dashboard sin un draw() síncrono.

    Matplotlib conserva su background entre páginas; forzar ``canvas.draw()`` en
    cada vuelta al Resumen añadía una pausa visible. ``draw_idle`` permite que Tk
    muestre el Dashboard primero y redibuje el gráfico cuando el event loop queda
    libre.
    """
    try:
        canvas = getattr(app, 'canvas', None)
        if canvas is not None:
            widget = canvas.get_tk_widget()
            try:
                widget.configure(bg=theme_color('#0d1828'), highlightthickness=0)
            except Exception:
                pass
            canvas.draw_idle()
    except Exception:
        pass


def show_dashboard(app):
    """Vuelve al Dashboard conservando geometría y repaints de forma diferida."""
    cancel_navigation_request(app)
    _clear_navigation_transition(app)
    clear_internal_page(app)
    _refresh_nav(app, 'dashboard')
    try:
        app.main_content.lift()
    except Exception:
        pass
    try:
        from gui.dashboard_layout import request_stable_layout_sync
        app.after_idle(lambda: request_stable_layout_sync(app, force=False))
    except Exception:
        pass
    _redraw_dashboard(app)


def notify_active_page_geometry(app):
    """Notifica una sola vez a la vista visible cuando termina un resize."""
    key = str(getattr(app, '_active_internal_page', '') or '').lower()
    if not key:
        return
    attr = PAGE_PANEL_REFS.get(key)
    panel = getattr(app, attr, None) if attr else None
    if panel is None:
        return
    callback = getattr(panel, 'on_viewport_settled', None)
    if callable(callback):
        try:
            callback()
        except Exception:
            pass


def active_page(app):
    pending = _pending(app)
    if pending:
        return pending.get('key') or 'dashboard'
    return getattr(app, '_active_internal_page', None) or 'dashboard'
