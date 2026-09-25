"""Galería interna de temas de CorePulse (V0.10.2.97w)."""
from __future__ import annotations

import customtkinter as ctk

from core.theme_manager import (
    get_theme,
    get_theme_profiles,
    preview_color,
    apply_theme_live,
    set_theme,
)

FONT = 'Segoe UI'


class ThemePanel:
    """Selector de temas embebido; nunca crea una Toplevel."""

    def __init__(self, app, parent):
        self.app = app
        self.parent = parent
        self._alive = True
        self.profiles = get_theme_profiles()
        self.selected_theme = get_theme()
        self._theme_buttons = {}
        self._preview_widgets = {}

        # V128: la galería también nace con la paleta exacta. Evita que widgets
        # transparentes/scrollables conserven el gris por defecto de CustomTkinter
        # durante el primer render o al cambiar la previsualización.
        current = self.profiles.get(get_theme(), self.profiles['corepulse'])
        self._initial_palette = dict(current)
        self.root = ctk.CTkFrame(parent, fg_color=current['bg'], corner_radius=0)
        self.root.pack(fill='both', expand=True)
        self.root.grid_columnconfigure(0, minsize=330, weight=0)
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
        header = ctk.CTkFrame(self.root, fg_color=p['bg'], height=76)
        self.header = header
        header.grid(row=0, column=0, columnspan=2, sticky='ew', padx=20, pady=(14, 8))
        header.grid_columnconfigure(0, weight=1)
        self.title = ctk.CTkLabel(header, text='Temas', font=(FONT, 24, 'bold'), anchor='w')
        self.title.grid(row=0, column=0, sticky='w')
        self.subtitle = ctk.CTkLabel(
            header,
            text='Elige una identidad visual completa. Al aplicar, CorePulse reemplaza la paleta actual por estos colores exactos, sin filtros.',
            font=(FONT, 10), anchor='w', justify='left',
        )
        self.subtitle.grid(row=1, column=0, sticky='w', pady=(3, 0))

    def _build_picker(self):
        p = self._initial_palette
        shell = ctk.CTkFrame(self.root, fg_color=p['surface'], border_color=p['border'], corner_radius=12, border_width=1)
        shell.grid(row=1, column=0, sticky='nsew', padx=(20, 9), pady=(0, 18))
        shell.grid_rowconfigure(1, weight=1)
        shell.grid_columnconfigure(0, weight=1)
        self.picker_shell = shell

        self.picker_title = ctk.CTkLabel(shell, text=f'{len(self.profiles)} temas oscuros disponibles', font=(FONT, 11, 'bold'), anchor='w')
        self.picker_title.grid(row=0, column=0, sticky='ew', padx=14, pady=(12, 7))

        self.scroll = ctk.CTkScrollableFrame(
            shell, fg_color=p['surface'], corner_radius=0,
            scrollbar_fg_color=p['surface'],
            scrollbar_button_color=p['border'],
            scrollbar_button_hover_color=p['accent_2'],
        )
        self.scroll.grid(row=1, column=0, sticky='nsew', padx=5, pady=(0, 6))
        self.scroll.grid_columnconfigure((0, 1), weight=1)

        for index, (key, profile) in enumerate(self.profiles.items()):
            card = ctk.CTkFrame(
                self.scroll, fg_color=profile['surface_2'], border_width=1,
                border_color=profile['border'], corner_radius=11, height=92,
            )
            card.grid(row=index // 2, column=index % 2, sticky='nsew', padx=4, pady=4)
            card.grid_propagate(False)
            card.grid_columnconfigure(0, weight=1)

            button = ctk.CTkButton(
                card, text=profile['name'], height=32, corner_radius=8,
                fg_color='transparent', hover_color=profile['border'],
                text_color=profile['text'], anchor='w',
                font=(FONT, 10, 'bold'),
                command=lambda value=key: self._select(value),
            )
            button.grid(row=0, column=0, columnspan=4, sticky='ew', padx=7, pady=(6, 0))

            desc = ctk.CTkLabel(
                card, text=profile['description'], font=(FONT, 7),
                text_color=profile['text_2'], anchor='w', justify='left',
                wraplength=128,
            )
            desc.grid(row=1, column=0, columnspan=4, sticky='ew', padx=10, pady=(0, 4))

            swatches = []
            colors = (profile['accent'], profile['accent_2'], profile['surface'], profile['bg'])
            for col, color in enumerate(colors):
                swatch = ctk.CTkFrame(card, height=6, fg_color=color, corner_radius=3)
                swatch.grid(row=2, column=col, sticky='ew', padx=(10 if col == 0 else 2, 10 if col == 3 else 2), pady=(0, 7))
                card.grid_columnconfigure(col, weight=1)
                swatches.append(swatch)

            self._theme_buttons[key] = {
                'card': card, 'button': button, 'description': desc, 'swatches': swatches,
            }

    def _build_preview(self):
        p = self._initial_palette
        right = ctk.CTkFrame(self.root, fg_color=p['surface'], border_color=p['border'], corner_radius=12, border_width=1)
        right.grid(row=1, column=1, sticky='nsew', padx=(9, 20), pady=(0, 18))
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)
        self.preview_shell = right

        top = ctk.CTkFrame(right, fg_color=p['surface'])
        self.preview_top = top
        top.grid(row=0, column=0, sticky='ew', padx=16, pady=(12, 8))
        top.grid_columnconfigure(0, weight=1)
        self.preview_title = ctk.CTkLabel(top, text='Vista previa', font=(FONT, 11, 'bold'), anchor='w')
        self.preview_title.grid(row=0, column=0, sticky='w')
        self.selection_badge = ctk.CTkLabel(top, text='', font=(FONT, 9, 'bold'), corner_radius=8, padx=9, pady=4)
        self.selection_badge.grid(row=0, column=1, sticky='e')

        mock = ctk.CTkFrame(right, fg_color=p['bg'], border_color=p['border'], corner_radius=12, border_width=1)
        mock.grid(row=1, column=0, sticky='nsew', padx=16, pady=(0, 12))
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
        content.grid_rowconfigure(2, weight=1)
        self.mock_heading = ctk.CTkLabel(content, text='Estado del sistema', font=(FONT, 14, 'bold'), anchor='w')
        self.mock_heading.grid(row=0, column=0, columnspan=3, sticky='ew', pady=(2, 8))

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
        chart.grid(row=2, column=0, columnspan=3, sticky='nsew')
        self.chart = chart
        self.chart_title = ctk.CTkLabel(chart, text='Actividad en tiempo real', font=(FONT, 8, 'bold'), anchor='w')
        self.chart_title.pack(fill='x', padx=10, pady=(9, 5))
        self.bars = []
        for amount in (0.76, 0.48, 0.64, 0.35):
            track = ctk.CTkProgressBar(chart, height=5, corner_radius=3, fg_color=p['border'], progress_color=p['accent'])
            track.pack(fill='x', padx=10, pady=5)
            track.set(amount)
            self.bars.append(track)

        footer = ctk.CTkFrame(right, fg_color=p['surface'])
        self.preview_footer = footer
        footer.grid(row=2, column=0, sticky='ew', padx=16, pady=(0, 14))
        footer.grid_columnconfigure(0, weight=1)
        self.apply_hint = ctk.CTkLabel(footer, text='Selecciona un tema para previsualizarlo.', font=(FONT, 9), anchor='w')
        self.apply_hint.grid(row=0, column=0, sticky='w')
        self.apply_button = ctk.CTkButton(
            footer, text='Aplicar tema', width=130, height=34, corner_radius=9,
            font=(FONT, 10, 'bold'), command=self._apply,
        )
        self.apply_button.grid(row=0, column=1, sticky='e')

    def _select(self, theme_key):
        if theme_key not in self.profiles:
            return
        self.selected_theme = theme_key
        p = self.profiles[theme_key]

        # Selector. Sólo reconfiguración de widgets ya creados: sin reconstrucción,
        # imágenes ni IO; esto mantiene la respuesta inmediata incluso al hacer scroll.
        for key, widgets in self._theme_buttons.items():
            candidate = self.profiles[key]
            active = key == theme_key
            card = widgets['card']
            button = widgets['button']
            desc = widgets['description']
            card.configure(
                fg_color=candidate['surface_2'],
                border_color=candidate['accent'] if active else candidate['border'],
                border_width=2 if active else 1,
            )
            button.configure(
                fg_color=candidate['accent_2'] if active else 'transparent',
                hover_color=candidate['accent'] if active else candidate['border'],
                text_color=candidate['text'],
            )
            desc.configure(text_color=candidate['text_2'])

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
        self.title.configure(text_color=p['text'])
        self.subtitle.configure(text_color=p['muted'])
        self.picker_title.configure(text_color=p['text_2'])
        self.preview_title.configure(text_color=p['text_2'])
        self.selection_badge.configure(text=p['name'], fg_color=p['accent_2'], text_color=p['text'])

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
        for card, title, value in self.metric_cards:
            card.configure(fg_color=p['surface'], border_color=p['border'])
            title.configure(text_color=p['muted'])
            value.configure(text_color=p['text'])
        self.chart.configure(fg_color=p['surface_2'], border_color=p['border'])
        self.chart_title.configure(text_color=p['text_2'])
        for bar in self.bars:
            bar.configure(fg_color=p['border'], progress_color=p['accent'])
        self.apply_hint.configure(text_color=p['muted'])
        self.apply_button.configure(fg_color=p['accent_2'], hover_color=p['accent'], text_color=p['text'])

        current = get_theme()
        if theme_key == current:
            self.apply_button.configure(text='Tema actual', state='disabled')
            self.apply_hint.configure(text='Este tema ya está aplicado en CorePulse.')
        else:
            self.apply_button.configure(text='Aplicar tema', state='normal')
            self.apply_hint.configure(text=f"Vista previa exacta de {p['name']}. Pulsa Aplicar para reemplazar la paleta actual.")

    def _apply(self):
        current = get_theme()
        if self.selected_theme == current:
            return
        try:
            self.apply_button.configure(text='Aplicando…', state='disabled')
            self.root.update_idletasks()
            selected = self.selected_theme
            set_theme(selected)
            apply_theme_live(self.app, current, selected)
            # Restaura la identidad propia de cada muestra y deja la selección
            # coherente después del recoloreado global. No hay reinicio ni flash.
            self._select(selected)
            self.apply_button.configure(text='Tema actual', state='disabled')
            self.apply_hint.configure(text='Tema aplicado al instante, sin reiniciar CorePulse.')
        except Exception:
            try:
                set_theme(current)
            except Exception:
                pass
            self.apply_button.configure(text='Aplicar tema', state='normal')
