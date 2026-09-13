"""Hub Gaming consolidado de CorePulse.

V0.10.2.60w:
- Cabecera Gaming reducida a una sola jerarquía visual.
- Navegación superior clara: Inicio / Biblioteca / Overlay.
- Se eliminan badges y botones duplicados del header.
- Biblioteca ya no necesita un segundo "Volver a Gaming" ni otro título redundante.
"""
from __future__ import annotations

import customtkinter as ctk

from core.theme_manager import color as theme_color
from gui.health_center_panel import HealthCenterPanel
from gui.overlay_config_panel import OverlayConfigPanel
from gui.internal_navigation import show_dashboard
from gui.stable_scroll import StableScrollHost
from gui.professional_visuals import build_title_block

BG = theme_color('#06111f')
SURFACE = theme_color('#091726')
CARD = theme_color('#0d1828')
CARD2 = theme_color('#0a1524')
BORDER = theme_color('#1b3048')
TEXT = theme_color('#f4f7fb')
TEXT2 = theme_color('#b8c4d4')
MUTED = theme_color('#94a3b8')
TAB_ACTIVE = theme_color('#164f7d')
TAB_HOVER = theme_color('#1b5c8f')
TAB_IDLE_HOVER = theme_color('#102840')
ACTION_BORDER = theme_color('#1d5278')
CYAN = '#14b8ff'
GREEN = '#10b981'
AMBER = '#f59e0b'
FONT = 'Segoe UI'


class GamingPanel:
    """Gaming unificado con Overlay separado y vistas cacheadas."""

    # Se conserva el contrato performance/overlay para open_gaming(tab=...).
    # Ya no se dibujan dos pestañas horizontales: performance es la vista Gaming.
    TABS = (('performance', 'Rendimiento'), ('overlay', 'Overlay'))

    def __init__(self, app, host, initial_tab='performance'):
        self.app = app
        self.host = host
        self._alive = True
        self._visible = True
        self._tab = initial_tab if initial_tab in dict(self.TABS) else 'performance'
        self._child_panel = None
        self._performance_panel = None
        self._overlay_panel = None
        self._tab_hosts = {}
        self._tab_panels = {}
        self._view_scrolls = {}
        self._status_after_id = None
        self._initial_load_after_id = None
        self._loading_placeholder = None
        self.main_scroll = None
        self._pending_performance_section = 'home'
        self._nav_buttons = {}

        self._build()
        self._show_loading_placeholder()
        self._schedule_initial_tab_load()

    def widget(self):
        return self.frame

    def _button(self, parent, text, command, *, width=None, height=33, primary=False):
        kwargs = dict(
            text=text,
            command=command,
            height=height,
            corner_radius=8,
            border_width=1,
            font=(FONT, 10, 'bold'),
            fg_color=TAB_ACTIVE if primary else 'transparent',
            hover_color=TAB_HOVER if primary else TAB_IDLE_HOVER,
            border_color=CYAN if primary else BORDER,
            text_color=TEXT if primary else TEXT2,
        )
        if width is not None:
            kwargs['width'] = width
        return ctk.CTkButton(parent, **kwargs)

    def _build(self):
        self.frame = ctk.CTkFrame(self.host, fg_color=BG, corner_radius=0)
        self.frame.pack(fill='both', expand=True)

        # V0.10.2.60w — una sola cabecera: volver, identidad y navegación.
        # Se eliminan "Gaming hub profesional", badges redundantes y el botón
        # Overlay duplicado a la derecha.
        header = ctk.CTkFrame(self.frame, fg_color='transparent')
        header.pack(fill='x', padx=20, pady=(15, 7))

        self._button(
            header, 'Volver al monitoreo', lambda: show_dashboard(self.app),
            width=140, height=32
        ).pack(side='left')

        titles = ctk.CTkFrame(header, fg_color='transparent')
        titles.pack(side='left', fill='x', expand=True, padx=(18, 0))
        self.title_label = ctk.CTkLabel(
            titles, text='Gaming', font=(FONT, 23, 'bold'), text_color=TEXT, anchor='w'
        )
        self.title_label.pack(anchor='w')
        self.subtitle_label = ctk.CTkLabel(
            titles,
            text='Juego actual, perfil y estado del equipo en una sola vista',
            font=(FONT, 10), text_color=MUTED, anchor='w', justify='left'
        )
        self.subtitle_label.pack(anchor='w', pady=(2, 0))

        nav = ctk.CTkFrame(self.frame, fg_color='transparent')
        nav.pack(fill='x', padx=20, pady=(0, 9))
        nav_inner = ctk.CTkFrame(nav, fg_color=CARD2, border_width=1, border_color=BORDER, corner_radius=10)
        nav_inner.pack(side='left')
        for key, label, command in (
            ('home', 'Inicio', lambda: self.select_section('home')),
            ('library', 'Biblioteca', lambda: self.select_section('library')),
            ('stability', 'Estabilidad', lambda: self.select_section('stability')),
            ('overlay', 'Overlay', lambda: self.select_tab('overlay')),
        ):
            btn = self._button(nav_inner, label, command, width=112, height=30)
            btn.pack(side='left', padx=3, pady=3)
            self._nav_buttons[key] = btn
        # Alias de compatibilidad para código/tests previos.
        self.overlay_button = self._nav_buttons['overlay']

        # Área de vistas. Rendimiento será UNA página larga con scroll; Overlay
        # se mantiene separado para no mezclar configuración OSD con perfiles.
        self.page_area = ctk.CTkFrame(self.frame, fg_color=BG, corner_radius=0)
        self.page_area.pack(fill='both', expand=True, padx=20, pady=(0, 12))

    def _show_loading_placeholder(self):
        """Publica Gaming inmediatamente y construye la vista pesada después."""
        if self._loading_placeholder is not None:
            return
        wrap = ctk.CTkFrame(self.page_area, fg_color=BG, corner_radius=0)
        wrap.place(relx=0, rely=0, relwidth=1, relheight=1)
        card = ctk.CTkFrame(
            wrap, fg_color=CARD2, border_width=1, border_color=BORDER, corner_radius=11
        )
        card.pack(fill='x', padx=2, pady=2)
        ctk.CTkLabel(
            card, text='Preparando Gaming…', font=(FONT, 12, 'bold'), text_color=TEXT, anchor='w'
        ).pack(fill='x', padx=14, pady=(12, 2))
        ctk.CTkLabel(
            card,
            text='CorePulse está cargando el hub Gaming simplificado sin bloquear la navegación.',
            font=(FONT, 9), text_color=MUTED, anchor='w', justify='left'
        ).pack(fill='x', padx=14, pady=(0, 12))
        self._loading_placeholder = wrap

    def _schedule_initial_tab_load(self, delay=1):
        if not self._alive or self._initial_load_after_id is not None:
            return
        try:
            self._initial_load_after_id = self.frame.after(
                max(1, int(delay)), self._finish_initial_tab_load
            )
        except Exception:
            self._initial_load_after_id = None
            self._finish_initial_tab_load()

    def _finish_initial_tab_load(self):
        self._initial_load_after_id = None
        if not self._alive:
            return
        try:
            self.frame.update_idletasks()
        except Exception:
            pass
        self._show_current_tab()
        if self._loading_placeholder is not None:
            try:
                self._loading_placeholder.destroy()
            except Exception:
                pass
            self._loading_placeholder = None

    def _set_panel_active(self, panel, active):
        if panel is None:
            return
        try:
            if hasattr(panel, 'set_active'):
                panel.set_active(bool(active))
        except Exception:
            pass

    def _ensure_tab(self, key):
        """Construye Gaming/Overlay una sola vez y conserva estado/scroll."""
        panel = self._tab_panels.get(key)
        host = self._tab_hosts.get(key)
        try:
            valid = panel is not None and host is not None and host.winfo_exists()
        except Exception:
            valid = False
        if valid:
            return host, panel

        host = ctk.CTkFrame(self.page_area, fg_color=BG, corner_radius=0)

        if key == 'overlay':
            # Overlay también recibe scroll propio si la ventana es baja. No hay
            # un segundo scroll dentro de OverlayConfigPanel.
            scroll = StableScrollHost(host, fg_color=BG)
            scroll.pack(fill='both', expand=True)
            overlay_body = scroll.content
            panel = OverlayConfigPanel(overlay_body, self.app)
            panel.widget().pack(fill='x', expand=False)
            self._view_scrolls[key] = scroll
            self._overlay_panel = panel
        else:
            # Vista Gaming consolidada: resumen + TODO Rendimiento comparten este
            # mismo StableScrollHost. HealthCenterPanel no crea scroll anidado.
            scroll = StableScrollHost(host, fg_color=BG)
            scroll.pack(fill='both', expand=True)
            self.main_scroll = scroll
            self._view_scrolls[key] = scroll
            body = scroll.content
            # V0.10.2.53w: Gaming usa una única fuente visual de verdad.
            # El estado de sesión vive dentro de HealthCenterPanel; no se duplica
            # arriba con PERFIL/JUEGO/GAME BOOST/OVERLAY.
            performance_host = ctk.CTkFrame(body, fg_color=BG, corner_radius=0)
            performance_host.pack(fill='x', expand=False)
            panel = HealthCenterPanel(
                self.app,
                performance_host,
                performance_only=True,
                external_scroll=scroll,
            )
            self._performance_panel = panel
            try:
                panel._performance_section = self._pending_performance_section
            except Exception:
                pass

        self._tab_hosts[key] = host
        self._tab_panels[key] = panel
        return host, panel

    def _apply_view_style(self):
        """Refleja una navegación única y evita acciones duplicadas en cabecera."""
        section = 'overlay' if self._tab == 'overlay' else self._current_performance_section()
        # Benchmark pertenece a Estabilidad y Game Boost pertenece a Inicio.
        # Así la navegación superior conserva una jerarquía estable aunque se
        # abra una subvista de configuración.
        nav_section = 'stability' if section == 'benchmark' else 'home' if section == 'boost' else section
        subtitles = {
            'home': 'Juego actual, perfil y estado del equipo en una sola vista',
            'library': 'Tus juegos detectados y manuales, sin ruido técnico innecesario',
            'stability': 'Sesión, temperaturas, throttling y benchmark con evidencia real',
            'overlay': 'Overlay In-Game · métricas reales y configuración sólo cuando la necesites',
        }
        try:
            self.subtitle_label.configure(text=subtitles.get(nav_section, subtitles['home']))
        except Exception:
            pass
        for key, button in self._nav_buttons.items():
            active = key == nav_section
            try:
                button.configure(
                    fg_color=TAB_ACTIVE if active else 'transparent',
                    hover_color=TAB_HOVER if active else TAB_IDLE_HOVER,
                    border_color=CYAN if active else BORDER,
                    text_color=TEXT if active else TEXT2,
                )
            except Exception:
                pass

    def _current_performance_section(self):
        panel = self._performance_panel
        if panel is not None:
            try:
                return str(panel._performance_section or 'home').lower()
            except Exception:
                pass
        return str(self._pending_performance_section or 'home').lower()

    def select_section(self, section):
        """Abre Inicio/Biblioteca dentro de Gaming sin crear otra capa de navegación."""
        section = str(section or 'home').strip().lower()
        if section not in ('home', 'library', 'stability'):
            section = 'home'
        self._pending_performance_section = section
        if self._tab != 'performance':
            self._tab = 'performance'
            if self._initial_load_after_id is None:
                self._show_current_tab()
        panel = self._performance_panel
        if panel is not None:
            try:
                panel._select_performance_section(section)
            except Exception:
                try:
                    panel._performance_section = section
                    panel._render()
                except Exception:
                    pass
        self._apply_view_style()

    def _show_current_tab(self):
        if not self._alive:
            return
        host, panel = self._ensure_tab(self._tab)
        for key, other_host in list(self._tab_hosts.items()):
            other_panel = self._tab_panels.get(key)
            active = key == self._tab
            self._set_panel_active(other_panel, active)
            try:
                if active:
                    other_host.place(relx=0, rely=0, relwidth=1, relheight=1)
                    other_host.lift()
                else:
                    other_host.place_forget()
            except Exception:
                pass
        self._child_panel = panel
        self._apply_view_style()
        self._refresh_hub_status()
        try:
            if hasattr(panel, 'refresh'):
                panel.refresh()
            elif self._tab == 'overlay' and hasattr(panel, '_refresh_status'):
                panel._refresh_status()
        except Exception:
            pass

    def _refresh_hub_status(self):
        """Compatibilidad interna.

        V0.10.2.53w elimina el resumen superior duplicado. El estado visible de
        Gaming se obtiene únicamente desde ``HealthCenterPanel`` mediante
        ``performance_manager.status()``, evitando mostrar dos perfiles distintos.
        """
        return None

    def _schedule_status_tick(self, delay=900):
        if not self._alive or not self._visible or self._status_after_id is not None:
            return
        try:
            self._status_after_id = self.frame.after(int(delay), self._status_tick)
        except Exception:
            self._status_after_id = None

    def _status_tick(self):
        self._status_after_id = None
        if not self._alive or not self._visible:
            return
        self._refresh_hub_status()
        self._schedule_status_tick(900)

    def set_active(self, active):
        self._visible = bool(active)
        if not self._visible and self._status_after_id is not None:
            try:
                self.frame.after_cancel(self._status_after_id)
            except Exception:
                pass
            self._status_after_id = None
        elif self._visible:
            self._refresh_hub_status()
        self._set_panel_active(self._child_panel, self._visible)

    def select_tab(self, key):
        """Compatibilidad pública: performance=Gaming, overlay=Overlay separado."""
        key = str(key or '').lower().strip()
        if key not in dict(self.TABS):
            key = 'performance'
        if key == self._tab and self._child_panel is not None:
            # Reabrir Gaming desde la caché no reconstruye biblioteca/portadas.
            self._refresh_hub_status()
            try:
                if key == 'overlay' and hasattr(self._child_panel, '_refresh_status'):
                    self._child_panel._refresh_status()
            except Exception:
                pass
            return
        self._tab = key
        if key == 'performance' and self._pending_performance_section not in ('home', 'library'):
            self._pending_performance_section = 'home'
        self._apply_view_style()
        if self._initial_load_after_id is not None:
            return
        self._show_current_tab()

    def refresh(self):
        if not self._alive:
            return
        self._refresh_hub_status()
        panel = self._child_panel
        if panel is None:
            if self._initial_load_after_id is not None:
                return
            self._show_current_tab()
            return
        try:
            if hasattr(panel, 'refresh'):
                panel.refresh()
            elif self._tab == 'overlay' and hasattr(panel, '_refresh_status'):
                panel._refresh_status()
        except Exception:
            pass

    def destroy(self):
        self._alive = False
        self._visible = False
        if self._status_after_id is not None:
            try:
                self.frame.after_cancel(self._status_after_id)
            except Exception:
                pass
            self._status_after_id = None
        if self._initial_load_after_id is not None:
            try:
                self.frame.after_cancel(self._initial_load_after_id)
            except Exception:
                pass
            self._initial_load_after_id = None
        for panel in list(self._tab_panels.values()):
            try:
                panel.destroy()
            except Exception:
                pass
        self._tab_panels.clear()
        self._tab_hosts.clear()
        self._view_scrolls.clear()
        self._child_panel = None
        self._performance_panel = None
        self._overlay_panel = None
        self.main_scroll = None
        try:
            self.frame.destroy()
        except Exception:
            pass
