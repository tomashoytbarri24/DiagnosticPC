"""Galería de temas de CorePulse.

La integración V258 conserva la regla visual recuperada de V223: seleccionar una paleta sólo cambia la
zona *Vista previa*. La interfaz real conserva el tema aplicado hasta pulsar
``Aplicar tema`` y reiniciar la capa visual.
"""
from __future__ import annotations

import customtkinter as ctk

from gui.stable_scroll import StableScrollHost
from core.theme_manager import (
    get_theme,
    get_theme_profiles,
    role_color,
    restart_application,
    set_theme,
)

FONT = 'Segoe UI'


class ThemePanel:
    """Selector de 20 temas con previsualización aislada de la UI real."""

    def __init__(self, app, parent):
        self.app = app
        self.parent = parent
        self._alive = True
        self.profiles = get_theme_profiles()
        self.selected_theme = get_theme()
        self._theme_buttons = {}
        self._theme_cards = {}
        self._theme_card_parts = {}
        self._filter = 'Todos'

        current = self._ui_palette()
        self.root = ctk.CTkFrame(parent, fg_color=current['bg'], corner_radius=0)
        self.root.pack(fill='both', expand=True)
        self.root.grid_columnconfigure(0, minsize=420, weight=0)
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(1, weight=1)

        self._build_header()
        self._build_picker()
        self._build_preview()
        self._select(self.selected_theme)

    def _ui_palette(self):
        return self.profiles.get(get_theme(), self.profiles['corepulse'])

    def widget(self):
        return self.root

    def set_active(self, active=True):
        self._alive = bool(active)

    # ------------------------------------------------------------------
    # Cabecera / colección
    # ------------------------------------------------------------------
    def _build_header(self):
        p = self._ui_palette()
        header = ctk.CTkFrame(self.root, fg_color=p['bg'], height=102)
        self.header = header
        header.grid(row=0, column=0, columnspan=2, sticky='ew', padx=26, pady=(18, 10))
        header.grid_columnconfigure(0, weight=1)

        eyebrow = ctk.CTkLabel(
            header, text='PERSONALIZACIÓN  /  APARIENCIA',
            font=(FONT, 8, 'bold'), text_color=p['accent'], anchor='w',
        )
        eyebrow.grid(row=0, column=0, sticky='w')
        self.eyebrow = eyebrow

        self.current_badge = ctk.CTkLabel(
            header, text='', font=(FONT, 9, 'bold'),
            fg_color=p['surface_2'], text_color=p['text_2'],
            corner_radius=11, padx=12, pady=6,
        )
        self.current_badge.grid(row=0, column=1, rowspan=2, sticky='e')

        self.title = ctk.CTkLabel(
            header, text='Temas', font=(FONT, 28, 'bold'),
            text_color=p['text'], anchor='w',
        )
        self.title.grid(row=1, column=0, sticky='w', pady=(2, 0))

        self.subtitle = ctk.CTkLabel(
            header,
            text='Explora una paleta sin alterar CorePulse. El cambio real sólo se aplica cuando confirmas el tema.',
            font=(FONT, 10), text_color=p['muted'], anchor='w', justify='left',
        )
        self.subtitle.grid(row=2, column=0, columnspan=2, sticky='w', pady=(4, 0))

    def _build_picker(self):
        p = self._ui_palette()
        shell = ctk.CTkFrame(
            self.root, fg_color=p['surface'], border_color=p['border'],
            corner_radius=18, border_width=1,
        )
        shell.grid(row=1, column=0, sticky='nsew', padx=(26, 10), pady=(0, 22))
        shell.grid_rowconfigure(3, weight=1)
        shell.grid_columnconfigure(0, weight=1)
        self.picker_shell = shell

        heading_row = ctk.CTkFrame(shell, fg_color='transparent')
        heading_row.grid(row=0, column=0, sticky='ew', padx=16, pady=(15, 2))
        heading_row.grid_columnconfigure(0, weight=1)
        self.picker_title = ctk.CTkLabel(
            heading_row, text='Colección de temas',
            font=(FONT, 13, 'bold'), text_color=p['text'], anchor='w',
        )
        self.picker_title.grid(row=0, column=0, sticky='w')
        self.theme_count = ctk.CTkLabel(
            heading_row, text=f'{len(self.profiles)} DISPONIBLES',
            font=(FONT, 8, 'bold'), fg_color=p['surface_2'],
            text_color=p['text_2'], corner_radius=9, padx=9, pady=4,
        )
        self.theme_count.grid(row=0, column=1, sticky='e')

        self.picker_hint = ctk.CTkLabel(
            shell, text='Selecciona una tarjeta para verla a la derecha.',
            font=(FONT, 8), text_color=p['muted'], anchor='w',
        )
        self.picker_hint.grid(row=1, column=0, sticky='ew', padx=16, pady=(0, 9))

        filters = ctk.CTkFrame(shell, fg_color=p['surface_2'], corner_radius=11)
        self.filter_bar = filters
        filters.grid(row=2, column=0, sticky='ew', padx=12, pady=(0, 8))
        filters.grid_columnconfigure((0, 1, 2), weight=1)
        self.filter_buttons = {}
        for col, label in enumerate(('Todos', 'Oscuros', 'Claros')):
            button = ctk.CTkButton(
                filters, text=label, height=32, corner_radius=9, border_width=1,
                font=(FONT, 9, 'bold'), command=lambda value=label: self._set_filter(value),
            )
            button.grid(row=0, column=col, sticky='ew', padx=4, pady=4)
            self.filter_buttons[label] = button

        self.scroll_host = StableScrollHost(
            shell, fg_color=p['surface'], backend='place',
            scrollbar_track_color=p['surface'], scrollbar_button_color=p['border'],
            scrollbar_button_hover_color=p['accent_2'],
        )
        self.scroll_host.grid(row=3, column=0, sticky='nsew', padx=7, pady=(0, 9))
        self.scroll = self.scroll_host.content
        self.scroll.grid_columnconfigure(0, weight=1)

        for index, (key, profile) in enumerate(self.profiles.items()):
            card = ctk.CTkFrame(
                self.scroll, height=86, corner_radius=14, border_width=1,
                fg_color=profile['surface_2'], border_color=profile['border'],
            )
            card.grid(row=index, column=0, sticky='ew', padx=5, pady=5)
            card.grid_propagate(False)
            card.grid_columnconfigure(0, weight=1)

            rail = ctk.CTkFrame(card, width=4, height=50, corner_radius=4, fg_color=profile['accent'])
            rail.grid(row=0, column=0, rowspan=2, sticky='w', padx=(0, 0), pady=15)

            text_box = ctk.CTkFrame(card, fg_color='transparent')
            text_box.grid(row=0, column=0, rowspan=2, sticky='nsew', padx=(14, 6), pady=10)
            name = ctk.CTkLabel(
                text_box, text=profile['name'], font=(FONT, 11, 'bold'),
                text_color=profile['text'], anchor='w',
            )
            name.pack(fill='x')
            desc = ctk.CTkLabel(
                text_box, text=profile['description'], font=(FONT, 8),
                text_color=profile['muted'], anchor='w',
            )
            desc.pack(fill='x', pady=(3, 0))

            swatches = ctk.CTkFrame(card, fg_color='transparent')
            swatches.grid(row=0, column=1, sticky='e', padx=(4, 13), pady=(14, 3))
            swatch_widgets = []
            for color in (profile['bg'], profile['surface'], profile['border'], profile['accent_2'], profile['accent']):
                sw = ctk.CTkFrame(swatches, width=20, height=14, corner_radius=5, fg_color=color)
                sw.pack(side='left', padx=2)
                sw.pack_propagate(False)
                swatch_widgets.append(sw)

            state = ctk.CTkLabel(card, text='', font=(FONT, 8, 'bold'), anchor='e')
            state.grid(row=1, column=1, sticky='e', padx=(4, 13), pady=(1, 12))

            hit = ctk.CTkButton(
                card, text='', width=1, height=1, fg_color='transparent',
                hover_color=profile['surface_2'], border_width=0,
                command=lambda value=key: self._select(value),
            )
            hit.place(relx=0, rely=0, relwidth=1, relheight=1)
            hit.lower()
            self._theme_buttons[key] = hit
            self._theme_cards[key] = card
            self._theme_card_parts[key] = (name, desc, state, swatch_widgets, rail)
            self._bind_click(card, lambda value=key: self._select(value))

    def _bind_click(self, widget, callback):
        try:
            widget.bind('<Button-1>', lambda _event: callback(), add='+')
            widget.configure(cursor='hand2')
        except Exception:
            pass
        try:
            for child in widget.winfo_children():
                self._bind_click(child, callback)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Vista previa. Sólo esta zona adopta el tema candidato.
    # ------------------------------------------------------------------
    def _build_preview(self):
        p = self._ui_palette()
        right = ctk.CTkFrame(
            self.root, fg_color=p['surface'], border_color=p['border'],
            corner_radius=18, border_width=1,
        )
        right.grid(row=1, column=1, sticky='nsew', padx=(10, 26), pady=(0, 22))
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(2, weight=1)
        self.preview_shell = right

        top = ctk.CTkFrame(right, fg_color='transparent')
        self.preview_top = top
        top.grid(row=0, column=0, sticky='ew', padx=19, pady=(15, 9))
        top.grid_columnconfigure(0, weight=1)
        self.preview_title = ctk.CTkLabel(
            top, text='Vista previa', font=(FONT, 13, 'bold'),
            text_color=p['text'], anchor='w',
        )
        self.preview_title.grid(row=0, column=0, sticky='w')
        self.preview_safety = ctk.CTkLabel(
            top, text='SOLO PREVISUALIZACIÓN', font=(FONT, 8, 'bold'),
            fg_color=p['surface_2'], text_color=p['text_2'],
            corner_radius=9, padx=9, pady=4,
        )
        self.preview_safety.grid(row=0, column=1, sticky='e', padx=(8, 8))
        self.selection_badge = ctk.CTkLabel(
            top, text='', font=(FONT, 9, 'bold'), corner_radius=9, padx=10, pady=4,
        )
        self.selection_badge.grid(row=0, column=2, sticky='e')

        meta = ctk.CTkFrame(right, border_width=1, corner_radius=14)
        self.preview_meta = meta
        meta.grid(row=1, column=0, sticky='ew', padx=19, pady=(0, 10))
        meta.grid_columnconfigure(0, weight=1)
        self.preview_name = ctk.CTkLabel(meta, text='', font=(FONT, 19, 'bold'), anchor='w')
        self.preview_name.grid(row=0, column=0, sticky='w', padx=14, pady=(11, 1))
        self.preview_mode = ctk.CTkLabel(meta, text='', font=(FONT, 8, 'bold'), corner_radius=8, padx=9, pady=4)
        self.preview_mode.grid(row=0, column=1, sticky='e', padx=14, pady=(11, 1))
        self.preview_description = ctk.CTkLabel(meta, text='', font=(FONT, 9), anchor='w')
        self.preview_description.grid(row=1, column=0, columnspan=2, sticky='w', padx=14, pady=(1, 11))

        mock = ctk.CTkFrame(right, corner_radius=15, border_width=1)
        mock.grid(row=2, column=0, sticky='nsew', padx=19, pady=(0, 11))
        mock.grid_columnconfigure(1, weight=1)
        mock.grid_rowconfigure(0, weight=1)
        self.mock = mock

        side = ctk.CTkFrame(mock, width=132, corner_radius=12)
        side.grid(row=0, column=0, sticky='nsew', padx=11, pady=11)
        side.grid_propagate(False)
        self.mock_sidebar = side
        self.mock_brand = ctk.CTkLabel(side, text='COREPULSE', font=(FONT, 11, 'bold'))
        self.mock_brand.pack(anchor='w', padx=13, pady=(15, 13))
        self.mock_nav = []
        for text in ('Resumen', 'Diagnóstico', 'Mantenimiento', 'Historial'):
            label = ctk.CTkLabel(
                side, text=text, height=29, corner_radius=8, anchor='w',
                padx=11, font=(FONT, 8, 'bold'),
            )
            label.pack(fill='x', padx=8, pady=2)
            self.mock_nav.append(label)

        content = ctk.CTkFrame(mock)
        self.preview_content = content
        content.grid(row=0, column=1, sticky='nsew', padx=(0, 11), pady=11)
        content.grid_columnconfigure((0, 1, 2), weight=1)
        content.grid_rowconfigure(3, weight=1)
        self.mock_heading = ctk.CTkLabel(content, text='Estado del sistema', font=(FONT, 15, 'bold'), anchor='w')
        self.mock_heading.grid(row=0, column=0, columnspan=2, sticky='ew', pady=(2, 9))
        self.mock_status = ctk.CTkLabel(content, text='●  DATOS EN VIVO', font=(FONT, 7, 'bold'), anchor='e')
        self.mock_status.grid(row=0, column=2, sticky='e', pady=(2, 9))

        self.metric_cards = []
        for col, (name, value) in enumerate((('CPU', '42%'), ('RAM', '58%'), ('GPU', '31%'))):
            card = ctk.CTkFrame(content, corner_radius=11, border_width=1)
            card.grid(row=1, column=col, sticky='nsew', padx=(0 if col == 0 else 5, 0), pady=(0, 9))
            title = ctk.CTkLabel(card, text=name, font=(FONT, 7, 'bold'), anchor='w')
            title.pack(fill='x', padx=10, pady=(9, 1))
            metric = ctk.CTkLabel(card, text=value, font=(FONT, 15, 'bold'), anchor='w')
            metric.pack(fill='x', padx=10, pady=(0, 9))
            self.metric_cards.append((card, title, metric))

        chart = ctk.CTkFrame(content, corner_radius=11, border_width=1)
        chart.grid(row=3, column=0, columnspan=3, sticky='nsew')
        self.chart = chart
        self.chart_title = ctk.CTkLabel(chart, text='Actividad reciente', font=(FONT, 8, 'bold'), anchor='w')
        self.chart_title.pack(fill='x', padx=11, pady=(10, 5))
        self.bars = []
        for amount in (0.76, 0.48, 0.64, 0.35):
            track = ctk.CTkProgressBar(chart, height=6, corner_radius=4)
            track.pack(fill='x', padx=11, pady=5)
            track.set(amount)
            self.bars.append(track)

        palette = ctk.CTkFrame(right, fg_color='transparent')
        self.palette_row = palette
        palette.grid(row=3, column=0, sticky='ew', padx=19, pady=(0, 9))
        palette.grid_columnconfigure(1, weight=1)
        self.palette_label = ctk.CTkLabel(palette, text='PALETA', font=(FONT, 8, 'bold'), text_color=p['muted'], anchor='w')
        self.palette_label.grid(row=0, column=0, sticky='w', padx=(0, 10))
        swatch_row = ctk.CTkFrame(palette, fg_color='transparent')
        swatch_row.grid(row=0, column=1, sticky='ew')
        swatch_row.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)
        self.preview_swatches = []
        for index in range(5):
            sw = ctk.CTkFrame(swatch_row, height=19, corner_radius=6)
            sw.grid(row=0, column=index, sticky='ew', padx=3)
            self.preview_swatches.append(sw)

        footer = ctk.CTkFrame(right, fg_color='transparent')
        self.preview_footer = footer
        footer.grid(row=4, column=0, sticky='ew', padx=19, pady=(0, 16))
        footer.grid_columnconfigure(0, weight=1)
        self.apply_hint = ctk.CTkLabel(
            footer, text='Selecciona un tema para previsualizarlo.',
            font=(FONT, 9), text_color=p['muted'], anchor='w',
        )
        self.apply_hint.grid(row=0, column=0, sticky='w', padx=(0, 12))
        self.apply_button = ctk.CTkButton(
            footer, text='Aplicar tema', width=150, height=38, corner_radius=10,
            font=(FONT, 10, 'bold'), command=self._apply,
        )
        self.apply_button.grid(row=0, column=1, sticky='e')

    # ------------------------------------------------------------------
    # Interacción
    # ------------------------------------------------------------------
    def _set_filter(self, value):
        if value not in ('Todos', 'Oscuros', 'Claros'):
            value = 'Todos'
        self._filter = value
        row = 0
        for key, card in self._theme_cards.items():
            appearance = self.profiles[key].get('appearance', 'dark')
            visible = value == 'Todos' or (value == 'Oscuros' and appearance == 'dark') or (value == 'Claros' and appearance == 'light')
            if visible:
                card.grid(row=row, column=0, sticky='ew', padx=5, pady=5)
                row += 1
            else:
                card.grid_remove()

        selected_appearance = self.profiles[self.selected_theme].get('appearance', 'dark')
        selected_visible = (
            value == 'Todos'
            or (value == 'Oscuros' and selected_appearance == 'dark')
            or (value == 'Claros' and selected_appearance == 'light')
        )
        if not selected_visible:
            for key, profile in self.profiles.items():
                appearance = profile.get('appearance', 'dark')
                if value == 'Todos' or (value == 'Oscuros' and appearance == 'dark') or (value == 'Claros' and appearance == 'light'):
                    self._select(key)
                    break
        self._refresh_filter_buttons()

    def _refresh_filter_buttons(self):
        # Los filtros pertenecen a la UI REAL, no al tema candidato.
        p = self._ui_palette()
        try:
            self.filter_bar.configure(fg_color=p['surface_2'])
        except Exception:
            pass
        for label, button in self.filter_buttons.items():
            active = label == self._filter
            button.configure(
                fg_color=p['accent_2'] if active else p['surface'],
                hover_color=p['accent'] if active else p['border'],
                border_color=p['accent'] if active else p['border'],
                text_color=role_color('text_on_accent', get_theme()) if active else p['text_2'],
            )

    def _style_real_ui(self):
        """Reafirma el tema actualmente aplicado en toda la galería externa."""
        p = self._ui_palette()
        self.root.configure(fg_color=p['bg'])
        self.header.configure(fg_color=p['bg'])
        self.eyebrow.configure(text_color=p['accent'])
        self.title.configure(text_color=p['text'])
        self.subtitle.configure(text_color=p['muted'])
        self.current_badge.configure(
            text=f"ACTUAL · {p['name']}", fg_color=p['surface_2'], text_color=p['text_2'],
        )
        self.picker_shell.configure(fg_color=p['surface'], border_color=p['border'])
        self.picker_title.configure(text_color=p['text'])
        self.theme_count.configure(fg_color=p['surface_2'], text_color=p['text_2'])
        self.picker_hint.configure(text_color=p['muted'])
        self.scroll_host.set_palette(
            fg_color=p['surface'], scrollbar_track_color=p['surface'],
            scrollbar_button_color=p['border'], scrollbar_button_hover_color=p['accent_2'],
        )
        self.preview_shell.configure(fg_color=p['surface'], border_color=p['border'])
        self.preview_title.configure(text_color=p['text'])
        self.preview_safety.configure(fg_color=p['surface_2'], text_color=p['text_2'])
        self.palette_label.configure(text_color=p['muted'])
        self.apply_hint.configure(text_color=p['muted'])
        self.apply_button.configure(fg_color=p['accent_2'], hover_color=p['accent'], text_color=role_color('text_on_accent', get_theme()))
        self._refresh_filter_buttons()

    def _select(self, theme_key):
        if theme_key not in self.profiles:
            return
        self.selected_theme = theme_key
        candidate = self.profiles[theme_key]
        current_key = get_theme()

        # La colección mantiene cada paleta en su propia tarjeta, pero el resto
        # del módulo conserva el tema YA APLICADO.
        for key, card in self._theme_cards.items():
            profile = self.profiles[key]
            active = key == theme_key
            card.configure(
                fg_color=profile['surface_2'],
                border_color=profile['accent'] if active else profile['border'],
                border_width=2 if active else 1,
            )
            name, desc, state, _swatches, rail = self._theme_card_parts[key]
            name.configure(text_color=profile['text'])
            desc.configure(text_color=profile['muted'])
            rail.configure(fg_color=profile['accent'])
            state.configure(
                text='VISTA PREVIA' if active else ('ACTUAL' if key == current_key else ''),
                text_color=profile['accent'] if active or key == current_key else profile['muted'],
            )

        self._style_real_ui()

        # Desde aquí sólo cambia la vista previa del candidato.
        p = candidate
        self.selection_badge.configure(text=p['name'], fg_color=p['accent_2'], text_color=role_color('text_on_accent', theme_key))
        self.preview_meta.configure(fg_color=p['surface_2'], border_color=p['border'])
        self.preview_name.configure(text=p['name'], text_color=p['text'])
        self.preview_description.configure(text=p['description'], text_color=p['muted'])
        self.preview_mode.configure(
            text='CLARO' if p.get('appearance') == 'light' else 'OSCURO',
            fg_color=p['accent_2'], text_color=role_color('text_on_accent', theme_key),
        )

        self.mock.configure(fg_color=p['bg'], border_color=p['border'])
        self.preview_content.configure(fg_color=p['bg'])
        self.mock_sidebar.configure(fg_color=p['sidebar'])
        self.mock_brand.configure(text_color=p['accent'])
        for index, label in enumerate(self.mock_nav):
            label.configure(
                text_color=p['text'] if index == 0 else p['text_2'],
                fg_color=p['accent_2'] if index == 0 else 'transparent',
            )
        self.mock_heading.configure(text_color=p['text'])
        self.mock_status.configure(text_color=p['accent'])
        for card, title, value in self.metric_cards:
            card.configure(fg_color=p['surface'], border_color=p['border'])
            title.configure(text_color=p['muted'])
            value.configure(text_color=p['text'])
        self.chart.configure(fg_color=p['surface_2'], border_color=p['border'])
        self.chart_title.configure(text_color=p['text_2'])
        for bar in self.bars:
            bar.configure(fg_color=p['border'], progress_color=p['accent'])
        for widget, color in zip(self.preview_swatches, (p['bg'], p['surface'], p['border'], p['accent_2'], p['accent'])):
            widget.configure(fg_color=color)

        if theme_key == current_key:
            self.apply_button.configure(text='Tema actual', state='disabled')
            self.apply_hint.configure(text='Este tema ya está aplicado. La interfaz real no ha cambiado.')
        else:
            self.apply_button.configure(text='Aplicar tema', state='normal')
            self.apply_hint.configure(text=f"Vista previa de {p['name']}. Pulsa Aplicar para usarla en CorePulse.")

    def _apply(self):
        if self.selected_theme == get_theme():
            return
        try:
            self.apply_button.configure(text='Aplicando…', state='disabled')
            self.root.update_idletasks()
            set_theme(self.selected_theme)
        except Exception:
            self.apply_button.configure(text='Aplicar tema', state='normal')
            return
        restart_application()
