"""Galería premium de temas de CorePulse.

V174 mantiene la autoridad exacta de ``core.theme_manager`` y mejora únicamente
la experiencia visual: colección filtrable, tarjetas de paleta y una vista
previa más cercana al Dashboard real. Sigue embebida dentro de CorePulse y no
crea ventanas secundarias.
"""
from __future__ import annotations

import customtkinter as ctk

from core.theme_manager import (
    get_theme,
    get_theme_profiles,
    restart_application,
    set_theme,
)

FONT = 'Segoe UI'


class ThemePanel:
    """Selector de temas embebido con previsualización completa."""

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

        current = self.profiles.get(get_theme(), self.profiles['corepulse'])
        self._initial_palette = dict(current)
        self.root = ctk.CTkFrame(parent, fg_color=current['bg'], corner_radius=0)
        self.root.pack(fill='both', expand=True)
        self.root.grid_columnconfigure(0, minsize=385, weight=0)
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(1, weight=1)

        self._build_header()
        self._build_picker()
        self._build_preview()
        self._select(self.selected_theme)

    def widget(self):
        return self.root

    def set_active(self, active=True):
        self._alive = bool(active)

    def _build_header(self):
        p = self._initial_palette
        header = ctk.CTkFrame(self.root, fg_color=p['bg'], height=82)
        self.header = header
        header.grid(row=0, column=0, columnspan=2, sticky='ew', padx=22, pady=(16, 9))
        header.grid_columnconfigure(0, weight=1)
        self.title = ctk.CTkLabel(header, text='Temas', font=(FONT, 25, 'bold'), anchor='w')
        self.title.grid(row=0, column=0, sticky='w')
        self.current_badge = ctk.CTkLabel(
            header, text='', font=(FONT, 9, 'bold'), corner_radius=9, padx=10, pady=5,
        )
        self.current_badge.grid(row=0, column=1, sticky='e')
        self.subtitle = ctk.CTkLabel(
            header,
            text='Personaliza CorePulse con paletas completas. La vista previa usa exactamente los mismos roles de color que la interfaz real.',
            font=(FONT, 10), anchor='w', justify='left',
        )
        self.subtitle.grid(row=1, column=0, columnspan=2, sticky='w', pady=(4, 0))

    def _build_picker(self):
        p = self._initial_palette
        shell = ctk.CTkFrame(self.root, fg_color=p['surface'], border_color=p['border'], corner_radius=14, border_width=1)
        shell.grid(row=1, column=0, sticky='nsew', padx=(22, 10), pady=(0, 20))
        shell.grid_rowconfigure(2, weight=1)
        shell.grid_columnconfigure(0, weight=1)
        self.picker_shell = shell

        self.picker_title = ctk.CTkLabel(shell, text='Colección de temas', font=(FONT, 12, 'bold'), anchor='w')
        self.picker_title.grid(row=0, column=0, sticky='ew', padx=15, pady=(13, 7))

        filters = ctk.CTkFrame(shell, fg_color='transparent')
        self.filter_bar = filters
        filters.grid(row=1, column=0, sticky='ew', padx=12, pady=(0, 7))
        filters.grid_columnconfigure((0, 1, 2), weight=1)
        self.filter_buttons = {}
        for col, label in enumerate(('Todos', 'Oscuros', 'Claros')):
            button = ctk.CTkButton(
                filters, text=label, height=28, corner_radius=8, border_width=1,
                font=(FONT, 8, 'bold'), command=lambda value=label: self._set_filter(value),
            )
            button.grid(row=0, column=col, sticky='ew', padx=3)
            self.filter_buttons[label] = button

        self.scroll = ctk.CTkScrollableFrame(
            shell, fg_color=p['surface'], corner_radius=0,
            scrollbar_fg_color=p['surface'],
            scrollbar_button_color=p['border'],
            scrollbar_button_hover_color=p['accent_2'],
        )
        self.scroll.grid(row=2, column=0, sticky='nsew', padx=6, pady=(0, 7))
        self.scroll.grid_columnconfigure(0, weight=1)

        for index, (key, profile) in enumerate(self.profiles.items()):
            card = ctk.CTkFrame(
                self.scroll, height=76, corner_radius=11, border_width=1,
                fg_color=profile['surface_2'], border_color=profile['border'],
            )
            card.grid(row=index, column=0, sticky='ew', padx=4, pady=4)
            card.grid_propagate(False)
            card.grid_columnconfigure(0, weight=1)

            text_box = ctk.CTkFrame(card, fg_color='transparent')
            text_box.grid(row=0, column=0, rowspan=2, sticky='nsew', padx=(12, 6), pady=8)
            name = ctk.CTkLabel(text_box, text=profile['name'], font=(FONT, 10, 'bold'), anchor='w')
            name.pack(fill='x')
            desc = ctk.CTkLabel(text_box, text=profile['description'], font=(FONT, 8), anchor='w')
            desc.pack(fill='x', pady=(2, 0))

            swatches = ctk.CTkFrame(card, fg_color='transparent')
            swatches.grid(row=0, column=1, sticky='e', padx=(4, 12), pady=(11, 3))
            swatch_widgets = []
            for color in (profile['bg'], profile['surface'], profile['border'], profile['accent_2'], profile['accent']):
                sw = ctk.CTkFrame(swatches, width=20, height=13, corner_radius=4, fg_color=color)
                sw.pack(side='left', padx=2)
                sw.pack_propagate(False)
                swatch_widgets.append(sw)

            state = ctk.CTkLabel(card, text='', font=(FONT, 8, 'bold'), anchor='e')
            state.grid(row=1, column=1, sticky='e', padx=(4, 12), pady=(1, 10))

            # Botón invisible sólo como autoridad de interacción/teclado; la tarjeta
            # visual permanece construida con Frame para poder mostrar la paleta.
            hit = ctk.CTkButton(
                card, text='', width=1, height=1, fg_color='transparent',
                hover_color=profile['surface_2'], border_width=0,
                command=lambda value=key: self._select(value),
            )
            hit.place(relx=0, rely=0, relwidth=1, relheight=1)
            hit.lower()
            self._theme_buttons[key] = hit
            self._theme_cards[key] = card
            self._theme_card_parts[key] = (name, desc, state, swatch_widgets)
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

    def _build_preview(self):
        p = self._initial_palette
        right = ctk.CTkFrame(self.root, fg_color=p['surface'], border_color=p['border'], corner_radius=14, border_width=1)
        right.grid(row=1, column=1, sticky='nsew', padx=(10, 22), pady=(0, 20))
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(2, weight=1)
        self.preview_shell = right

        top = ctk.CTkFrame(right, fg_color=p['surface'])
        self.preview_top = top
        top.grid(row=0, column=0, sticky='ew', padx=17, pady=(13, 8))
        top.grid_columnconfigure(0, weight=1)
        self.preview_title = ctk.CTkLabel(top, text='Vista previa', font=(FONT, 11, 'bold'), anchor='w')
        self.preview_title.grid(row=0, column=0, sticky='w')
        self.selection_badge = ctk.CTkLabel(top, text='', font=(FONT, 9, 'bold'), corner_radius=8, padx=9, pady=4)
        self.selection_badge.grid(row=0, column=1, sticky='e')

        meta = ctk.CTkFrame(right, fg_color=p['surface_2'], border_width=1, border_color=p['border'], corner_radius=10)
        self.preview_meta = meta
        meta.grid(row=1, column=0, sticky='ew', padx=17, pady=(0, 9))
        meta.grid_columnconfigure(0, weight=1)
        self.preview_name = ctk.CTkLabel(meta, text='', font=(FONT, 16, 'bold'), anchor='w')
        self.preview_name.grid(row=0, column=0, sticky='w', padx=12, pady=(9, 1))
        self.preview_mode = ctk.CTkLabel(meta, text='', font=(FONT, 8, 'bold'), corner_radius=7, padx=8, pady=3)
        self.preview_mode.grid(row=0, column=1, sticky='e', padx=12, pady=(9, 1))
        self.preview_description = ctk.CTkLabel(meta, text='', font=(FONT, 8), anchor='w')
        self.preview_description.grid(row=1, column=0, columnspan=2, sticky='w', padx=12, pady=(0, 9))

        mock = ctk.CTkFrame(right, fg_color=p['bg'], border_color=p['border'], corner_radius=12, border_width=1)
        mock.grid(row=2, column=0, sticky='nsew', padx=17, pady=(0, 10))
        mock.grid_columnconfigure(1, weight=1)
        mock.grid_rowconfigure(0, weight=1)
        self.mock = mock

        side = ctk.CTkFrame(mock, width=126, corner_radius=10, fg_color=p['sidebar'])
        side.grid(row=0, column=0, sticky='nsew', padx=10, pady=10)
        side.grid_propagate(False)
        self.mock_sidebar = side
        self.mock_brand = ctk.CTkLabel(side, text='COREPULSE', font=(FONT, 11, 'bold'))
        self.mock_brand.pack(anchor='w', padx=12, pady=(14, 14))
        self.mock_nav = []
        for text in ('Resumen', 'Diagnóstico', 'Mantenimiento', 'Historial'):
            label = ctk.CTkLabel(side, text=text, height=27, corner_radius=7, anchor='w', padx=10, font=(FONT, 8, 'bold'))
            label.pack(fill='x', padx=8, pady=2)
            self.mock_nav.append(label)

        content = ctk.CTkFrame(mock, fg_color=p['bg'])
        self.preview_content = content
        content.grid(row=0, column=1, sticky='nsew', padx=(0, 10), pady=10)
        content.grid_columnconfigure((0, 1, 2), weight=1)
        content.grid_rowconfigure(3, weight=1)
        self.mock_heading = ctk.CTkLabel(content, text='Estado del sistema', font=(FONT, 14, 'bold'), anchor='w')
        self.mock_heading.grid(row=0, column=0, columnspan=2, sticky='ew', pady=(2, 8))
        self.mock_status = ctk.CTkLabel(content, text='●  MONITOREO ACTIVO', font=(FONT, 7, 'bold'), anchor='e')
        self.mock_status.grid(row=0, column=2, sticky='e', pady=(2, 8))

        self.metric_cards = []
        for col, (name, value) in enumerate((('CPU', '42%'), ('RAM', '58%'), ('GPU', '31%'))):
            card = ctk.CTkFrame(content, fg_color=p['surface'], border_color=p['border'], corner_radius=9, border_width=1)
            card.grid(row=1, column=col, sticky='nsew', padx=(0 if col == 0 else 4, 0), pady=(0, 8))
            title = ctk.CTkLabel(card, text=name, font=(FONT, 7, 'bold'), anchor='w')
            title.pack(fill='x', padx=9, pady=(8, 1))
            metric = ctk.CTkLabel(card, text=value, font=(FONT, 14, 'bold'), anchor='w')
            metric.pack(fill='x', padx=9, pady=(0, 8))
            self.metric_cards.append((card, title, metric))

        chart = ctk.CTkFrame(content, fg_color=p['surface_2'], border_color=p['border'], corner_radius=9, border_width=1)
        chart.grid(row=3, column=0, columnspan=3, sticky='nsew')
        self.chart = chart
        self.chart_title = ctk.CTkLabel(chart, text='Actividad en tiempo real', font=(FONT, 8, 'bold'), anchor='w')
        self.chart_title.pack(fill='x', padx=10, pady=(9, 5))
        self.bars = []
        for amount in (0.76, 0.48, 0.64, 0.35):
            track = ctk.CTkProgressBar(chart, height=5, corner_radius=3, fg_color=p['border'], progress_color=p['accent'])
            track.pack(fill='x', padx=10, pady=5)
            track.set(amount)
            self.bars.append(track)

        palette = ctk.CTkFrame(right, fg_color=p['surface'])
        self.palette_row = palette
        palette.grid(row=3, column=0, sticky='ew', padx=17, pady=(0, 8))
        palette.grid_columnconfigure(1, weight=1)
        self.palette_label = ctk.CTkLabel(palette, text='PALETA', font=(FONT, 8, 'bold'), anchor='w')
        self.palette_label.grid(row=0, column=0, sticky='w', padx=(0, 10))
        swatch_row = ctk.CTkFrame(palette, fg_color='transparent')
        swatch_row.grid(row=0, column=1, sticky='ew')
        swatch_row.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)
        self.preview_swatches = []
        for index in range(5):
            sw = ctk.CTkFrame(swatch_row, height=17, corner_radius=5)
            sw.grid(row=0, column=index, sticky='ew', padx=2)
            self.preview_swatches.append(sw)

        footer = ctk.CTkFrame(right, fg_color=p['surface'])
        self.preview_footer = footer
        footer.grid(row=4, column=0, sticky='ew', padx=17, pady=(0, 14))
        footer.grid_columnconfigure(0, weight=1)
        self.apply_hint = ctk.CTkLabel(footer, text='Selecciona un tema para previsualizarlo.', font=(FONT, 9), anchor='w')
        self.apply_hint.grid(row=0, column=0, sticky='w')
        self.apply_button = ctk.CTkButton(
            footer, text='Aplicar tema', width=138, height=35, corner_radius=9,
            font=(FONT, 10, 'bold'), command=self._apply,
        )
        self.apply_button.grid(row=0, column=1, sticky='e')

    def _set_filter(self, value):
        if value not in ('Todos', 'Oscuros', 'Claros'):
            value = 'Todos'
        self._filter = value
        row = 0
        for key, card in self._theme_cards.items():
            appearance = self.profiles[key].get('appearance', 'dark')
            visible = value == 'Todos' or (value == 'Oscuros' and appearance == 'dark') or (value == 'Claros' and appearance == 'light')
            if visible:
                card.grid(row=row, column=0, sticky='ew', padx=4, pady=4)
                row += 1
            else:
                card.grid_remove()
        # Si el filtro oculta el tema que estaba en vista previa, seleccionar
        # automáticamente el primer tema visible. Evita mostrar, por ejemplo,
        # Bosque mientras la lista está filtrada a temas claros.
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
        p = self.profiles[self.selected_theme]
        for label, button in self.filter_buttons.items():
            active = label == self._filter
            button.configure(
                fg_color=p['accent_2'] if active else p['surface_2'],
                hover_color=p['accent'] if active else p['border'],
                border_color=p['accent'] if active else p['border'],
                text_color=p['text'] if active else p['text_2'],
            )

    def _select(self, theme_key):
        if theme_key not in self.profiles:
            return
        self.selected_theme = theme_key
        p = self.profiles[theme_key]

        for key, card in self._theme_cards.items():
            candidate = self.profiles[key]
            active = key == theme_key
            card.configure(
                fg_color=candidate['surface_2'],
                border_color=candidate['accent'] if active else candidate['border'],
                border_width=2 if active else 1,
            )
            name, desc, state, _swatches = self._theme_card_parts[key]
            name.configure(text_color=candidate['text'])
            desc.configure(text_color=candidate['muted'])
            state.configure(
                text='SELECCIONADO' if active else ('ACTUAL' if key == get_theme() else ''),
                text_color=candidate['accent'] if active or key == get_theme() else candidate['muted'],
            )

        self.root.configure(fg_color=p['bg'])
        self.header.configure(fg_color=p['bg'])
        self.picker_shell.configure(fg_color=p['surface'], border_color=p['border'])
        self.scroll.configure(
            fg_color=p['surface'],
            scrollbar_fg_color=p['surface'],
            scrollbar_button_color=p['border'],
            scrollbar_button_hover_color=p['accent_2'],
        )
        self.preview_shell.configure(fg_color=p['surface'], border_color=p['border'])
        self.preview_top.configure(fg_color=p['surface'])
        self.preview_footer.configure(fg_color=p['surface'])
        self.palette_row.configure(fg_color=p['surface'])
        self.title.configure(text_color=p['text'])
        self.subtitle.configure(text_color=p['muted'])
        current_profile = self.profiles[get_theme()]
        self.current_badge.configure(text=f"ACTUAL · {current_profile['name']}", fg_color=p['surface_2'], text_color=p['text_2'])
        self.picker_title.configure(text_color=p['text_2'])
        self.preview_title.configure(text_color=p['text_2'])
        self.selection_badge.configure(text=p['name'], fg_color=p['accent_2'], text_color=p['text'])
        self.preview_meta.configure(fg_color=p['surface_2'], border_color=p['border'])
        self.preview_name.configure(text=p['name'], text_color=p['text'])
        self.preview_description.configure(text=p['description'], text_color=p['muted'])
        self.preview_mode.configure(
            text='CLARO' if p.get('appearance') == 'light' else 'OSCURO',
            fg_color=p['accent_2'], text_color=p['text'],
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
        self.palette_label.configure(text_color=p['muted'])
        for widget, color in zip(self.preview_swatches, (p['bg'], p['surface'], p['border'], p['accent_2'], p['accent'])):
            widget.configure(fg_color=color)
        self.apply_hint.configure(text_color=p['muted'])
        self.apply_button.configure(fg_color=p['accent_2'], hover_color=p['accent'], text_color=p['text'])
        self._refresh_filter_buttons()

        current = get_theme()
        if theme_key == current:
            self.apply_button.configure(text='Tema actual', state='disabled')
            self.apply_hint.configure(text='Este tema ya está aplicado en CorePulse.')
        else:
            self.apply_button.configure(text='Aplicar tema', state='normal')
            self.apply_hint.configure(text=f"Vista previa exacta de {p['name']}. Pulsa Aplicar para reemplazar la paleta actual.")

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
