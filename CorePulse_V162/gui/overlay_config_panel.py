"""Configuración visual del Overlay In-Game de CorePulse."""
from __future__ import annotations

import customtkinter as ctk

from core.theme_manager import color as theme_color
from core.overlay_preferences import DEFAULTS, load_overlay_preferences, reset_overlay_preferences, save_overlay_preferences
from core.global_hotkeys import (
    CAPTURE_VERSION,
    DEFAULT_TOGGLE_HOTKEY,
    hotkey_to_label,
    normalize_hotkey_config,
    normalize_key_from_tk_event,
)
from gui.professional_visuals import build_title_block

BG = theme_color('#06111f')
INNER = theme_color('#08121d')
CARD = theme_color('#0d1828')
CARD2 = theme_color('#091827')
CARD3 = theme_color('#0b1524')
BORDER = theme_color('#1b3048')
TEXT = theme_color('#f4f7fb')
DIM = theme_color('#aebdd0')
MUTED = theme_color('#72849b')
CYAN = '#38bdf8'
GREEN = '#22c993'
WARN = '#f0a23a'
FONT = 'Segoe UI'


class OverlayConfigPanel:
    def __init__(self, parent, app):
        self.parent = parent
        self.app = app
        self._alive = True
        self._visible = True
        self._status_after_id = None
        self._advanced_open = True
        self._layout_mode = None
        self._metrics_columns = None
        self._responsive_after_id = None
        self._last_responsive_width = None
        self._recording_hotkey = False
        self._record_bind_press = None
        self._record_bind_release = None
        self._record_widget = None
        self._pressed_modifiers = set()
        self._pending_hotkey = None

        p = load_overlay_preferences()
        self.root = ctk.CTkFrame(parent, fg_color=BG, corner_radius=0)
        self.layout_var = ctk.StringVar(value='Completo' if p['layout'] == 'FULL' else 'Compacto')
        self.pixel_var = ctk.StringVar(value=f"{p['pixel']}x")
        self.x_var = ctk.StringVar(value=str(p['x']))
        self.y_var = ctk.StringVar(value=str(p['y']))
        self.metric_vars = {
            k: ctk.BooleanVar(value=p[k])
            for k in ('show_fps', 'show_frametime', 'show_1pct_low', 'show_cpu', 'show_ram', 'show_gpu', 'show_storage')
        }
        self.hotkey_spec = normalize_hotkey_config(p.get('toggle_hotkey'), DEFAULT_TOGGLE_HOTKEY)
        self.hotkey_var = ctk.StringVar(value=hotkey_to_label(self.hotkey_spec))
        if int(self.hotkey_spec.get('capture_version', 1) or 1) < CAPTURE_VERSION:
            hotkey_hint = 'Atajo heredado de una versión anterior. Grábalo de nuevo una vez para certificar la combinación exacta.'
        else:
            hotkey_hint = 'CorePulse registra exactamente las teclas que presionas; no añade Alt ni otros modificadores.'
        self.hotkey_hint_var = ctk.StringVar(value=hotkey_hint)
        self._metric_cards = []
        self._build()
        self._schedule_status_tick(200)

    def widget(self):
        return self.root

    def destroy(self):
        self._alive = False
        self._visible = False
        self._stop_hotkey_recording(cancel=True)
        if self._responsive_after_id is not None:
            try:
                self.root.after_cancel(self._responsive_after_id)
            except Exception:
                pass
            self._responsive_after_id = None
        if self._status_after_id is not None:
            try:
                self.root.after_cancel(self._status_after_id)
            except Exception:
                pass
            self._status_after_id = None

    def set_active(self, active):
        self._visible = bool(active)
        if self._visible:
            self._on_resize()
        if not self._visible and self._status_after_id is not None:
            try:
                self.root.after_cancel(self._status_after_id)
            except Exception:
                pass
            self._status_after_id = None
        elif self._visible and self._alive and self._status_after_id is None:
            self._schedule_status_tick(30)

    def _schedule_status_tick(self, delay=800):
        if not self._alive or not self._visible or self._status_after_id is not None:
            return
        try:
            self._status_after_id = self.root.after(int(delay), self._status_tick)
        except Exception:
            self._status_after_id = None

    def _build(self):
        # V102: una sola jerarquía visual, siempre visible. El panel evita "tarjeta dentro de tarjeta"
        # y deja las decisiones importantes a la vista sin ocupar media pantalla.
        header = ctk.CTkFrame(self.root, fg_color='transparent')
        header.pack(fill='x', padx=14, pady=(12, 8))
        hero = build_title_block(
            header,
            eyebrow='OSD · RTSS',
            title='Overlay In-Game',
            subtitle='Métricas, estilo, posición y atajo global del OSD.',
            accent=CYAN,
            badges=(),
            title_size=17,
        )
        hero['frame'].pack(side='left', fill='x', expand=True)

        header_actions = ctk.CTkFrame(header, fg_color='transparent')
        header_actions.pack(side='right', padx=(14, 0))
        self.status_badge = ctk.CTkLabel(
            header_actions, text='DETENIDO', font=(FONT, 9, 'bold'), text_color=MUTED,
            fg_color=theme_color('#102235'), corner_radius=999, padx=12, pady=6,
        )
        self.status_badge.pack(side='left', padx=(0, 8))
        self.btn_toggle = ctk.CTkButton(
            header_actions, text='Iniciar Overlay', command=self._toggle_overlay,
            height=34, width=124, corner_radius=10,
            fg_color=theme_color('#123e5c'), hover_color=theme_color('#174e72'),
            border_width=1, border_color=CYAN, text_color=TEXT, font=(FONT, 9, 'bold'),
        )
        self.btn_toggle.pack(side='left')

        # Estado compacto: sin una tarjeta completa para tres líneas de información.
        service = ctk.CTkFrame(self.root, fg_color='transparent')
        service.pack(fill='x', padx=14, pady=(0, 8))
        self.lbl_rtss = ctk.CTkLabel(
            service, text='RTSS: overlay detenido', font=(FONT, 9, 'bold'),
            text_color=DIM, anchor='w'
        )
        self.lbl_rtss.pack(side='left')
        self.lbl_app = ctk.CTkLabel(
            service, text='Juego: N/A', font=(FONT, 8), text_color=MUTED, anchor='w'
        )
        self.lbl_app.pack(side='left', padx=(16, 0))
        self.lbl_policy = ctk.CTkLabel(
            service, text='FPS medidos · N/A sin datos', font=(FONT, 8, 'bold'),
            text_color=CYAN, anchor='w'
        )
        self.lbl_policy.pack(side='left', padx=(16, 0))

        divider = ctk.CTkFrame(self.root, fg_color=BORDER, height=1, corner_radius=999)
        divider.pack(fill='x', padx=14, pady=(0, 10))

        # Personalización expandible. Sólo tres superficies principales:
        # métricas, preview y configuración.
        self.body = ctk.CTkFrame(self.root, fg_color='transparent')

        self.overview = ctk.CTkFrame(self.body, fg_color='transparent')
        self.overview.grid_columnconfigure(0, weight=3)
        self.overview.grid_columnconfigure(1, weight=2)

        self.metrics = ctk.CTkFrame(
            self.overview, fg_color=CARD, border_width=1, border_color=BORDER,
            corner_radius=14
        )
        metrics_head = ctk.CTkFrame(self.metrics, fg_color='transparent')
        metrics_head.pack(fill='x', padx=14, pady=(12, 8))
        ctk.CTkLabel(
            metrics_head, text='Métricas', font=(FONT, 11, 'bold'), text_color=TEXT
        ).pack(side='left')
        ctk.CTkLabel(
            metrics_head, text='Activa sólo lo necesario', font=(FONT, 8), text_color=MUTED
        ).pack(side='right')

        self.metrics_grid = ctk.CTkFrame(self.metrics, fg_color='transparent')
        self.metrics_grid.pack(fill='x', padx=10, pady=(0, 10))
        metric_specs = (
            ('show_fps', 'FPS', 'fotogramas/s'),
            ('show_frametime', 'Frametime', 'ms por frame'),
            ('show_1pct_low', '1% Low', 'caídas de FPS'),
            ('show_cpu', 'CPU', 'uso · °C · GHz'),
            ('show_ram', 'RAM', 'memoria usada'),
            ('show_gpu', 'GPU', 'uso · °C · hotspot'),
            ('show_storage', 'SSD', 'temperatura · salud'),
        )
        for key, title, detail in metric_specs:
            row = ctk.CTkFrame(
                self.metrics_grid, fg_color=theme_color('#0a1725'),
                border_width=1, border_color=theme_color('#17314a'), corner_radius=10,
                height=64,
            )
            row.pack_propagate(False)
            labels = ctk.CTkFrame(row, fg_color='transparent')
            labels.pack(side='left', fill='both', expand=True, padx=(11, 4), pady=7)
            ctk.CTkLabel(
                labels, text=title, height=20, font=(FONT, 10, 'bold'), text_color=TEXT, anchor='w'
            ).pack(anchor='w')
            ctk.CTkLabel(
                labels, text=detail, height=18, font=(FONT, 8), text_color=MUTED, anchor='w'
            ).pack(anchor='w', pady=(1, 0))
            ctk.CTkSwitch(
                row, text='', width=40, variable=self.metric_vars[key],
                command=self._save_live, progress_color=CYAN
            ).pack(side='right', padx=(4, 10))
            self._metric_cards.append(row)

        self.preview_card = ctk.CTkFrame(
            self.overview, fg_color=CARD, border_width=1, border_color=BORDER,
            corner_radius=14
        )
        preview_head = ctk.CTkFrame(self.preview_card, fg_color='transparent')
        preview_head.pack(fill='x', padx=14, pady=(12, 8))
        ctk.CTkLabel(
            preview_head, text='Vista previa', font=(FONT, 11, 'bold'), text_color=TEXT
        ).pack(side='left')
        self.preview_hint = ctk.CTkLabel(
            preview_head, text='OSD', font=(FONT, 8, 'bold'), text_color=CYAN
        )
        self.preview_hint.pack(side='right')

        preview = ctk.CTkFrame(
            self.preview_card, fg_color=theme_color('#07111d'),
            border_width=1, border_color=theme_color('#17314d'), corner_radius=10
        )
        preview.pack(fill='x', padx=12, pady=(0, 12))
        self.preview_title = ctk.CTkLabel(
            preview, text='CorePulse', font=(FONT, 9, 'bold'), text_color=CYAN, anchor='w'
        )
        self.preview_title.pack(fill='x', padx=11, pady=(10, 3))
        self.preview_text = ctk.CTkLabel(
            preview, text='', font=('Consolas', 11, 'bold'), text_color=TEXT,
            anchor='w', justify='left'
        )
        self.preview_text.pack(fill='x', padx=11, pady=(0, 10))

        # Configuración: un único panel, cuatro zonas ligeras y sin sub-tarjetas.
        self.visual = ctk.CTkFrame(
            self.body, fg_color=CARD, border_width=1, border_color=BORDER,
            corner_radius=14
        )
        visual_head = ctk.CTkFrame(self.visual, fg_color='transparent')
        visual_head.pack(fill='x', padx=14, pady=(12, 8))
        ctk.CTkLabel(
            visual_head, text='Configuración', font=(FONT, 11, 'bold'), text_color=TEXT
        ).pack(side='left')
        ctk.CTkLabel(
            visual_head, text='Cambios en vivo', font=(FONT, 8), text_color=MUTED
        ).pack(side='right')

        controls = ctk.CTkFrame(self.visual, fg_color='transparent')
        controls.pack(fill='x', padx=12, pady=(0, 10))
        controls.grid_columnconfigure(0, weight=1, uniform='overlay_controls')
        controls.grid_columnconfigure(1, weight=1, uniform='overlay_controls')

        self._control_sections = []

        # Diseño
        design = ctk.CTkFrame(controls, fg_color='transparent')
        design.grid(row=0, column=0, sticky='ew', padx=(0, 8), pady=(0, 10))
        ctk.CTkLabel(design, text='Diseño', font=(FONT, 8, 'bold'), text_color=DIM).pack(anchor='w', pady=(0, 4))
        ctk.CTkSegmentedButton(
            design, values=['Completo', 'Compacto'], variable=self.layout_var,
            command=lambda _=None: self._save_live(), height=30,
            selected_color=theme_color('#164f7d'), selected_hover_color=theme_color('#1b5c8f'),
            unselected_color=theme_color('#091827'), unselected_hover_color=theme_color('#102840')
        ).pack(fill='x')

        # Escala
        scale = ctk.CTkFrame(controls, fg_color='transparent')
        scale.grid(row=0, column=1, sticky='ew', padx=(8, 0), pady=(0, 10))
        ctk.CTkLabel(scale, text='Escala', font=(FONT, 8, 'bold'), text_color=DIM).pack(anchor='w', pady=(0, 4))
        ctk.CTkSegmentedButton(
            scale, values=['1x', '2x', '3x', '4x'], variable=self.pixel_var,
            command=lambda _=None: self._save_live(), height=30,
            selected_color=theme_color('#164f7d'), selected_hover_color=theme_color('#1b5c8f'),
            unselected_color=theme_color('#091827'), unselected_hover_color=theme_color('#102840')
        ).pack(fill='x')

        # Posición
        position = ctk.CTkFrame(controls, fg_color='transparent')
        position.grid(row=1, column=0, sticky='ew', padx=(0, 8), pady=(0, 2))
        ctk.CTkLabel(position, text='Posición', font=(FONT, 8, 'bold'), text_color=DIM).pack(anchor='w', pady=(0, 4))
        pos = ctk.CTkFrame(position, fg_color='transparent')
        pos.pack(fill='x')
        for title, var in (('X', self.x_var), ('Y', self.y_var)):
            group = ctk.CTkFrame(pos, fg_color='transparent')
            group.pack(side='left', fill='x', expand=True, padx=(0, 6) if title == 'X' else (6, 0))
            ctk.CTkLabel(group, text=title, font=(FONT, 7, 'bold'), text_color=MUTED).pack(anchor='w')
            entry = ctk.CTkEntry(
                group, textvariable=var, height=30, fg_color=INNER,
                border_color=BORDER, text_color=TEXT
            )
            entry.pack(fill='x', pady=(2, 0))
            entry.bind('<Return>', lambda _e: self._save_live())
            entry.bind('<FocusOut>', lambda _e: self._save_live())

        # Atajo
        hotkey = ctk.CTkFrame(controls, fg_color='transparent')
        hotkey.grid(row=1, column=1, sticky='ew', padx=(8, 0), pady=(0, 2))
        ctk.CTkLabel(hotkey, text='Atajo global', font=(FONT, 8, 'bold'), text_color=DIM).pack(anchor='w', pady=(0, 4))
        hotkey_row = ctk.CTkFrame(hotkey, fg_color='transparent')
        hotkey_row.pack(fill='x')
        self.hotkey_entry = ctk.CTkEntry(
            hotkey_row, textvariable=self.hotkey_var, state='readonly', height=30,
            fg_color=INNER, border_color=BORDER, text_color=TEXT
        )
        self.hotkey_entry.pack(side='left', fill='x', expand=True)
        self.btn_record_hotkey = ctk.CTkButton(
            hotkey_row, text='Grabar', command=self._toggle_hotkey_recording,
            height=30, width=72, corner_radius=8, fg_color=theme_color('#123e5c'),
            hover_color=theme_color('#174e72'), border_width=1, border_color=CYAN,
            text_color=TEXT, font=(FONT, 8, 'bold')
        )
        self.btn_record_hotkey.pack(side='left', padx=(6, 0))
        self.btn_clear_hotkey = ctk.CTkButton(
            hotkey_row, text='Limpiar', command=self._clear_hotkey,
            height=30, width=64, corner_radius=8, fg_color='transparent',
            hover_color=theme_color('#14253b'), border_width=1, border_color=BORDER,
            text_color=DIM, font=(FONT, 8, 'bold')
        )
        self.btn_clear_hotkey.pack(side='left', padx=(6, 0))

        self._control_sections = [design, scale, position, hotkey]
        self._controls_grid = controls
        self._controls_columns = None

        visual_footer = ctk.CTkFrame(self.visual, fg_color='transparent')
        visual_footer.pack(fill='x', padx=14, pady=(0, 12))
        self.hotkey_hint = ctk.CTkLabel(
            visual_footer, textvariable=self.hotkey_hint_var, font=(FONT, 7),
            text_color=MUTED, justify='left', anchor='w'
        )
        self.hotkey_hint.pack(side='left', fill='x', expand=True)
        ctk.CTkButton(
            visual_footer, text='Restaurar', command=self._reset, height=28, width=82,
            corner_radius=8, fg_color='transparent', hover_color=theme_color('#14253b'),
            border_width=1, border_color=BORDER, text_color=DIM, font=(FONT, 8, 'bold')
        ).pack(side='right', padx=(10, 0))

        # V102: la configuración del Overlay permanece siempre visible.
        self.body.pack(fill='x', expand=False, padx=14, pady=(0, 10))

        self.root.bind('<Configure>', self._on_resize, add='+')
        self._responsive_after_id = self.root.after(80, self._apply_responsive_layout)
        self._update_preview()

    def _toggle_advanced_settings(self):
        """Compatibilidad: V102 mantiene la personalización siempre visible."""
        self._advanced_open = True
        try:
            if not self.body.winfo_manager():
                self.body.pack(fill='x', expand=False, padx=14, pady=(0, 10))
            self.root.after_idle(self._apply_responsive_layout)
        except Exception:
            pass

    def _on_resize(self, event=None):
        if not self._alive or (event is not None and getattr(event, 'widget', None) is not self.root):
            return
        try:
            width = int(self.root.winfo_width())
        except Exception:
            return
        if width <= 1:
            return
        # Sólo reagendar si el ancho realmente cambió de forma apreciable. Esto
        # evita decenas de grid_forget/grid durante maximizar/restaurar.
        if self._last_responsive_width is not None and abs(width - self._last_responsive_width) < 18:
            return
        if self._responsive_after_id is not None:
            try:
                self.root.after_cancel(self._responsive_after_id)
            except Exception:
                pass
        try:
            self._responsive_after_id = self.root.after(70, self._apply_responsive_layout)
        except Exception:
            self._apply_responsive_layout()

    def on_viewport_settled(self):
        """Aplica el breakpoint sólo cuando la ventana terminó de cambiar tamaño."""
        if not self._alive:
            return
        self._apply_responsive_layout()

    def _apply_responsive_layout(self):
        if self._responsive_after_id is not None:
            try:
                self.root.after_cancel(self._responsive_after_id)
            except Exception:
                pass
        self._responsive_after_id = None
        if not self._alive or not self._visible:
            return
        if getattr(self.app, 'is_resizing', False):
            self._responsive_after_id = self.root.after(80, self._apply_responsive_layout)
            return
        width = int(self.root.winfo_width())
        if width <= 1:
            return
        # CTk expresa geometría física; breakpoints en unidades lógicas para DPI.
        logical_width = self.root._reverse_widget_scaling(width)
        self._last_responsive_width = width
        mode = 'columns' if logical_width >= 960 else 'stacked'
        metric_width = logical_width * .60 if mode == 'columns' else logical_width
        metric_cols = 2 if metric_width >= 520 else 1
        if metric_cols != self._metrics_columns:
            self._metrics_columns = metric_cols
            for col in range(2):
                self.metrics_grid.grid_columnconfigure(col, weight=1 if col < metric_cols else 0,
                                                       minsize=0, uniform='overlay_metrics' if col < metric_cols else '')
            for idx, card in enumerate(self._metric_cards):
                card.grid(row=idx // metric_cols, column=idx % metric_cols, columnspan=1,
                          sticky='ew', padx=3, pady=3)
        if mode != self._layout_mode:
            self._layout_mode = mode
            self.overview.grid_columnconfigure(0, weight=3 if mode == 'columns' else 1)
            self.overview.grid_columnconfigure(1, weight=2 if mode == 'columns' else 0)
            self.metrics.grid(row=0, column=0, columnspan=1, sticky='new',
                              padx=(0, 6) if mode == 'columns' else 0, pady=0)
            self.preview_card.grid(row=0 if mode == 'columns' else 1, column=1 if mode == 'columns' else 0,
                                   columnspan=1, sticky='new', padx=(6, 0) if mode == 'columns' else 0,
                                   pady=0 if mode == 'columns' else (8, 0))
            self.overview.grid(row=0, column=0, sticky='new')
            self.visual.grid(row=1, column=0, sticky='new', pady=(10, 0))
            self.body.grid_columnconfigure(0, weight=1)
        control_cols = 2 if logical_width >= 760 else 1
        if control_cols != self._controls_columns:
            self._controls_columns = control_cols
            for col in range(2):
                self._controls_grid.grid_columnconfigure(col, weight=1 if col < control_cols else 0,
                    uniform='overlay_controls' if col < control_cols else '')
            for idx, section in enumerate(self._control_sections):
                section.grid(row=idx // control_cols, column=idx % control_cols, sticky='ew',
                             padx=(0, 8) if control_cols == 2 and idx % 2 == 0 else 0, pady=(0, 10))
        self.hotkey_hint.configure(wraplength=max(220, logical_width - 160))

    def _collect(self):
        try:
            pixel = int(str(self.pixel_var.get()).replace('x', ''))
        except Exception:
            pixel = DEFAULTS['pixel']
        try:
            x = int(self.x_var.get())
        except Exception:
            x = DEFAULTS['x']
        try:
            y = int(self.y_var.get())
        except Exception:
            y = DEFAULTS['y']
        data = {'layout': 'FULL' if self.layout_var.get() == 'Completo' else 'COMPACT', 'x': x, 'y': y, 'pixel': pixel, 'toggle_hotkey': normalize_hotkey_config(self.hotkey_spec, DEFAULT_TOGGLE_HOTKEY)}
        for key, var in self.metric_vars.items():
            data[key] = bool(var.get())
        return data

    def _update_preview(self):
        if not self._alive:
            return
        enabled = self._collect()
        lines = []
        if enabled.get('show_fps'):
            lines.append('FPS        —')
        if enabled.get('show_frametime'):
            lines.append('Frame      — ms')
        if enabled.get('show_1pct_low'):
            lines.append('1% Low     —')
        if enabled.get('show_cpu'):
            lines.append('CPU        —%  ·  — °C')
        if enabled.get('show_ram'):
            lines.append('RAM        — GB')
        if enabled.get('show_gpu'):
            lines.append('GPU        —%  ·  — °C')
        if enabled.get('show_storage'):
            lines.append('SSD        — °C')
        if not lines:
            lines = ['Sin métricas seleccionadas']
        if enabled.get('layout') == 'COMPACT':
            lines = lines[:4]
        try:
            self.preview_text.configure(text='\n'.join(lines))
            self.preview_title.configure(text=f"CorePulse · {self.pixel_var.get()} · {hotkey_to_label(self.hotkey_spec)}")
        except Exception:
            pass

    def _save_live(self):
        prefs = save_overlay_preferences(self._collect())
        self.x_var.set(str(prefs['x']))
        self.y_var.set(str(prefs['y']))
        self.pixel_var.set(f"{prefs['pixel']}x")
        self.hotkey_spec = normalize_hotkey_config(prefs.get('toggle_hotkey'), DEFAULT_TOGGLE_HOTKEY)
        self.hotkey_var.set(hotkey_to_label(self.hotkey_spec))
        self._update_preview()
        try:
            if hasattr(self.app, '_configure_overlay_hotkey'):
                self.app._configure_overlay_hotkey()
        except Exception:
            pass
        return prefs

    def _reset(self):
        prefs = reset_overlay_preferences()
        self.layout_var.set('Completo')
        self.pixel_var.set(f"{prefs['pixel']}x")
        self.x_var.set(str(prefs['x']))
        self.y_var.set(str(prefs['y']))
        for key, var in self.metric_vars.items():
            var.set(bool(prefs[key]))
        self.hotkey_spec = normalize_hotkey_config(prefs.get('toggle_hotkey'), DEFAULT_TOGGLE_HOTKEY)
        self.hotkey_var.set(hotkey_to_label(self.hotkey_spec))
        self.hotkey_hint_var.set('Preferencias restauradas. Puedes volver a grabar el atajo cuando quieras.')
        self._update_preview()
        try:
            if hasattr(self.app, '_configure_overlay_hotkey'):
                self.app._configure_overlay_hotkey()
        except Exception:
            pass

    def _toggle_overlay(self):
        self._save_live()
        self.app.toggle_overlay()
        self._refresh_status()

    def _toggle_hotkey_recording(self):
        if self._recording_hotkey:
            self._stop_hotkey_recording(cancel=True)
            return
        self._recording_hotkey = True
        self._pressed_modifiers = set()
        self._pending_hotkey = None
        self.hotkey_hint_var.set('Grabando… presiona la combinación exacta, por ejemplo Ctrl+9.')
        self.btn_record_hotkey.configure(text='Cancelar')
        self._record_widget = self.root.winfo_toplevel()
        try:
            self._record_widget.focus_force()
        except Exception:
            pass
        try:
            self._record_bind_press = self._record_widget.bind('<KeyPress>', self._on_hotkey_keypress, add='+')
            self._record_bind_release = self._record_widget.bind('<KeyRelease>', self._on_hotkey_keyrelease, add='+')
        except Exception:
            self._recording_hotkey = False
            self.btn_record_hotkey.configure(text='Grabar atajo')
            self.hotkey_hint_var.set('No se pudo iniciar la captura del atajo.')

    def _stop_hotkey_recording(self, cancel=False):
        if not self._recording_hotkey and self._record_widget is None:
            return
        widget = self._record_widget
        if widget is not None:
            try:
                if self._record_bind_press:
                    widget.unbind('<KeyPress>', self._record_bind_press)
            except Exception:
                pass
            try:
                if self._record_bind_release:
                    widget.unbind('<KeyRelease>', self._record_bind_release)
            except Exception:
                pass
        self._record_widget = None
        self._record_bind_press = None
        self._record_bind_release = None
        self._recording_hotkey = False
        self._pressed_modifiers = set()
        self._pending_hotkey = None
        try:
            self.btn_record_hotkey.configure(text='Grabar atajo')
        except Exception:
            pass
        if cancel:
            self.hotkey_hint_var.set('Captura cancelada. El atajo anterior se mantiene intacto.')

    def _on_hotkey_keypress(self, event=None):
        if not self._recording_hotkey or event is None:
            return 'break'
        key = normalize_key_from_tk_event(getattr(event, 'keysym', ''))
        if not key:
            return 'break'
        if key in {'CTRL', 'ALT', 'SHIFT', 'WIN'}:
            self._pressed_modifiers.add(key)
            if self._pressed_modifiers:
                text = '+'.join({'CTRL': 'Ctrl', 'ALT': 'Alt', 'SHIFT': 'Shift', 'WIN': 'Win'}[m] for m in ('CTRL', 'ALT', 'SHIFT', 'WIN') if m in self._pressed_modifiers)
                self.hotkey_var.set(text + '+…')
            return 'break'
        # No usamos event.state: en Tk/Windows puede traer flags Mod1 residuales
        # y añadir Alt aunque el usuario nunca lo haya pulsado. Sólo cuentan los
        # modificadores cuya pulsación recibimos explícitamente durante la captura.
        mods = set(self._pressed_modifiers)
        if not mods:
            self.hotkey_hint_var.set('Agrega al menos Ctrl, Alt, Shift o Win para evitar conflictos con el juego.')
            self.hotkey_var.set(hotkey_to_label(self.hotkey_spec))
            return 'break'
        spec = normalize_hotkey_config({
            'modifiers': list(mods), 'key': key, 'enabled': True,
            'capture_version': CAPTURE_VERSION,
        }, DEFAULT_TOGGLE_HOTKEY)
        self.hotkey_spec = spec
        self.hotkey_var.set(hotkey_to_label(spec))
        self.hotkey_hint_var.set(f"Atajo configurado: {hotkey_to_label(spec)}. CorePulse usará exactamente esa combinación.")
        self._save_live()
        self._stop_hotkey_recording(cancel=False)
        self.hotkey_hint_var.set(f"Atajo configurado: {hotkey_to_label(spec)}. CorePulse usará exactamente esa combinación.")
        return 'break'

    def _on_hotkey_keyrelease(self, event=None):
        if not self._recording_hotkey or event is None:
            return 'break'
        key = normalize_key_from_tk_event(getattr(event, 'keysym', ''))
        if key in self._pressed_modifiers:
            try:
                self._pressed_modifiers.remove(key)
            except Exception:
                pass
        return 'break'

    def _clear_hotkey(self):
        self._stop_hotkey_recording(cancel=False)
        self.hotkey_spec = normalize_hotkey_config({'modifiers': [], 'key': '', 'enabled': False, 'capture_version': CAPTURE_VERSION}, DEFAULT_TOGGLE_HOTKEY)
        self.hotkey_var.set(hotkey_to_label(self.hotkey_spec))
        self.hotkey_hint_var.set('Atajo desactivado. Puedes grabar una nueva combinación cuando quieras.')
        self._save_live()

    def _refresh_status(self):
        overlay = getattr(self.app, 'overlay_window', None)
        try:
            running = bool(overlay is not None and overlay.winfo_exists())
        except Exception:
            running = False
        if not running:
            self.status_badge.configure(text='DETENIDO', text_color=MUTED)
            self.lbl_rtss.configure(text='RTSS: overlay detenido', text_color=DIM)
            self.lbl_app.configure(text='Juego detectado: N/A')
            self.lbl_policy.configure(text='FPS medidos · N/A sin datos')
            self.btn_toggle.configure(text='Iniciar Overlay')
            return
        try:
            status = overlay.get_status() or {}
        except Exception:
            status = {}
        available = bool(status.get('rtss_available'))
        active = status.get('active_app') or {}
        app_name = active.get('name') if isinstance(active, dict) else None
        error = status.get('last_error')
        self.status_badge.configure(text='ACTIVO' if available else 'ESPERANDO RTSS', text_color=GREEN if available else WARN)
        self.lbl_rtss.configure(text=f"RTSS: conectado · v{status.get('rtss_version')}" if available else f"RTSS: {error or 'no disponible'}", text_color=GREEN if available else WARN)
        self.lbl_app.configure(text=f"Juego detectado: {app_name or 'N/A'}")
        self.lbl_policy.configure(text='FPS medidos · N/A sin datos')
        self.btn_toggle.configure(text='Detener Overlay')

    def _status_tick(self):
        self._status_after_id = None
        if not self._alive or not self._visible:
            return
        try:
            if not self.root.winfo_exists():
                return
            self._refresh_status()
            self._schedule_status_tick(800)
        except Exception:
            pass
