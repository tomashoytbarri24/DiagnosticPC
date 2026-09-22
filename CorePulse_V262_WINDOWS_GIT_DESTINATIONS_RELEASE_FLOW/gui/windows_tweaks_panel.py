"""Vista interna de Tweaks de Windows 11 de CorePulse."""
from __future__ import annotations
from core.theme_manager import color as theme_color

import threading
import copy
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox

from core.windows_tweaks import (
    CATEGORY_ORDER, PRESETS, apply_many, catalog, compatible_tweak_ids, create_restore_point, detect_all,
    environment_info, preset_ids, restart_explorer, saved_rollback_ids,
    selected_metadata, undo_all_saved, undo_many,
)
from core.before_after import capture_metrics, save_snapshot, start_operation, finish_operation, mark_operation
from core.battery_health import collect_battery_health
from gui.internal_navigation import show_dashboard
from gui.stable_scroll import StableScrollHost
from gui.tweak_restore_center import TweakRestoreCenter
from gui.professional_visuals import build_title_block

BG = theme_color('#06111f'); CARD = theme_color('#0d1828'); CARD_2 = theme_color('#0a1524'); BORDER = theme_color('#1b3048')
TEXT = theme_color('#f4f7fb'); TEXT_2 = theme_color('#b8c4d4'); MUTED = theme_color('#7f91a8'); CYAN = '#14b8ff'
GREEN = '#1fd18b'; AMBER = '#f59e0b'; RED = '#ff5d6c'; CRITICAL = '#ff334d'; FONT = 'Segoe UI'
RISK_COLORS = {'Bajo': GREEN, 'Medio': AMBER, 'Alto': RED, 'Crítico': CRITICAL}

# Identidad visual por categoría. Se usan tonos oscuros/sutiles para que cada
# módulo sea reconocible sin convertir Tweaks en una interfaz multicolor.
# Todos los colores pasan por theme_color() para conservar modo claro/oscuro.
CATEGORY_VISUALS = {
    'Explorador': {
        'surface': '#0f1c2d', 'border': '#29435f', 'accent': '#5aa0ff',
        'row': '#0a1524', 'hover': '#102840',
    },
    'Barra de tareas': {
        'surface': '#0f2135', 'border': '#2b668f', 'accent': '#75d2f7',
        'row': '#0a1524', 'hover': '#102840',
    },
    'Interfaz': {
        'surface': '#101d2f', 'border': '#334867', 'accent': '#94a3b8',
        'row': '#0a1524', 'hover': '#0e1d2f',
    },
    'Privacidad': {
        'surface': '#17182f', 'border': '#4a4772', 'accent': '#a991ff',
        'row': '#101226', 'hover': '#1d203d',
    },
    'Gaming': {
        'surface': '#0d2130', 'border': '#174e72', 'accent': '#14b8ff',
        'row': '#091a28', 'hover': '#0f2b40',
    },
    'Rendimiento': {
        'surface': '#102235', 'border': '#178967', 'accent': '#1fd18b',
        'row': '#0b1c26', 'hover': '#10352e',
    },
    'Energía': {
        'surface': '#241d0f', 'border': '#6e5421', 'accent': '#f4b942',
        'row': '#1b170e', 'hover': '#302611',
    },
    'Sistema': {
        'surface': '#12243a', 'border': '#1c3451', 'accent': '#75d2f7',
        'row': '#0c1828', 'hover': '#142c46',
    },
    'Actualizaciones': {
        'surface': '#251c11', 'border': '#725022', 'accent': '#f59e0b',
        'row': '#1b160f', 'hover': '#332611',
    },
    'Red': {
        'surface': '#0d332b', 'border': '#178967', 'accent': '#20c997',
        'row': '#0a211d', 'hover': '#103c33',
    },
    'Apps y debloat': {
        'surface': '#152a41', 'border': '#416887', 'accent': '#8fb7d5',
        'row': '#0d1b2a', 'hover': '#19324e',
    },
    'Seguridad avanzada': {
        'surface': '#2b1d26', 'border': '#693343', 'accent': '#ff5d6c',
        'row': '#20171d', 'hover': '#412530',
    },
}

_DEFAULT_CATEGORY_VISUAL = {
    'surface': '#0d1828', 'border': '#1b3048', 'accent': '#14b8ff',
    'row': '#0a1524', 'hover': '#0e1d2f',
}


def category_visual(category):
    raw = CATEGORY_VISUALS.get(str(category), _DEFAULT_CATEGORY_VISUAL)
    return {key: theme_color(value) for key, value in raw.items()}


class WindowsTweaksPanel:
    def __init__(self, app, host):
        self.app = app
        self.host = host
        self._alive = True
        self._busy = False
        self._detecting = False
        self.items = catalog()
        self.vars = {}
        self.status_labels = {}
        self.undo_labels = {}
        self.check_labels = {}
        self.row_widgets = {}
        self.category_widgets = {}
        self.category_count_labels = {}
        self._category_row_ids = {}
        self._detected_states = {}
        self._compatible_ids_cache = set()
        self._visible_ids = {item['id'] for item in self.items}
        self._filter_after_id = None
        self.search_var = None
        self.state_filter_var = None
        self.category_filter_var = None
        self.risk_filter_var = None
        self.compatible_only_var = None
        self.restore_point_var = ctk.BooleanVar(value=False)
        self._rollback_ids_cache = set()
        self._item_by_id = {item['id']: item for item in self.items}
        self._catalog_ready = False
        self._catalog_groups = []
        self._catalog_index = 0
        self._pending_preset = None
        self._restore_center_panel = None
        self._build()
        # El shell se publica primero. En el siguiente ciclo construimos el catálogo
        # completo con widgets Tk ligeros; no dejamos una lista a medio construir
        # durante varios segundos mientras el usuario ya puede desplazarse.
        try:
            self.frame.after_idle(self._build_catalog_step)
        except Exception:
            self._build_catalog_step()

    def widget(self):
        return self.frame

    def _build(self):
        self.frame = ctk.CTkFrame(self.host, fg_color=BG, corner_radius=0)
        self.frame.pack(fill='both', expand=True)

        header = ctk.CTkFrame(self.frame, fg_color='transparent')
        header.pack(fill='x', padx=18, pady=(15, 7))
        self.header_bar = header
        ctk.CTkButton(
            header, text='Volver al monitoreo', width=145, height=31, fg_color='transparent',
            hover_color=theme_color(theme_color('#102840')), border_width=1, border_color=theme_color(theme_color('#214765')), text_color=TEXT_2,
            font=(FONT, 9, 'bold'), corner_radius=8, command=lambda: show_dashboard(self.app),
        ).pack(side='left')
        titles = ctk.CTkFrame(header, fg_color='transparent')
        titles.pack(side='left', fill='x', expand=True, padx=14)
        hero = build_title_block(
            titles,
            eyebrow='Windows 11 · Ajustes seguros',
            title='Tweaks de Windows 11',
            subtitle=f'{len(self.items)} ajustes · rollback obligatorio, verificación y sin scripts remotos',
            accent=CYAN,
            badges=(('Rollback', GREEN), ('Verificación', CYAN), ('Sin scripts remotos', AMBER)),
            title_size=19,
        )
        hero['frame'].pack(anchor='w', fill='x')
        self.lbl_environment = ctk.CTkLabel(header, text='Comprobando Windows…', font=(FONT, 9, 'bold'), text_color=MUTED)
        self.lbl_environment.pack(side='right')

        info = ctk.CTkFrame(self.frame, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=11)
        info.pack(fill='x', padx=18, pady=(0, 8))
        self.info_bar = info
        self.lbl_info = ctk.CTkLabel(
            info,
            text='Contrato de rollback: CorePulse sólo aplica cambios cuyo estado anterior puede guardar y restaurar. Si no puede garantizarlo, el tweak queda NO DISPONIBLE.',
            font=(FONT, 9), text_color=TEXT_2, anchor='w', justify='left',
        )
        self.lbl_info.pack(side='left', fill='x', expand=True, padx=12, pady=9)
        self.btn_restore_center = ctk.CTkButton(
            info, text='Centro de restauración', width=128, height=27, corner_radius=7,
            fg_color='transparent', hover_color=theme_color('#102840'), border_width=1,
            border_color=theme_color('#245b82'), text_color=theme_color('#9bddff'),
            font=(FONT, 8, 'bold'), command=self._open_restore_center,
        )
        self.btn_restore_center.pack(side='right', padx=(5, 11), pady=6)
        self.lbl_selected = ctk.CTkLabel(info, text='0 seleccionados', font=(FONT, 9, 'bold'), text_color=CYAN)
        self.lbl_selected.pack(side='right', padx=(8, 5))

        # V0.10.2.29w — Tweaks Action UI Cleanup
        # Un único selector de preset sustituye seis botones permanentes. Las
        # acciones de selección quedan agrupadas como herramientas secundarias.
        controls = ctk.CTkFrame(
            self.frame, fg_color=CARD, border_width=1, border_color=BORDER,
            corner_radius=10,
        )
        controls.pack(fill='x', padx=18, pady=(0, 8))
        self.controls_bar = controls

        preset_group = ctk.CTkFrame(controls, fg_color='transparent')
        preset_group.pack(side='left', padx=(11, 8), pady=8)
        ctk.CTkLabel(
            preset_group, text='PRESET', font=(FONT, 8, 'bold'), text_color=MUTED,
        ).pack(side='left', padx=(0, 7))

        preset_keys = ('recommended', 'minimal', 'privacy', 'gaming', 'performance', 'advanced')
        self._preset_label_to_key = {PRESETS[key]: key for key in preset_keys}
        self.preset_var = ctk.StringVar(value='Elegir preset…')
        self.preset_menu = ctk.CTkOptionMenu(
            preset_group,
            values=[PRESETS[key] for key in preset_keys],
            variable=self.preset_var,
            command=self._on_preset_selected,
            width=160,
            height=29,
            corner_radius=7,
            fg_color=theme_color('#0d2942'),
            button_color=theme_color('#164f7d'),
            button_hover_color=theme_color('#1d628f'),
            dropdown_fg_color=theme_color('#0d1828'),
            dropdown_hover_color=theme_color('#16324c'),
            text_color=theme_color('#9bddff'),
            font=(FONT, 8, 'bold'),
            dropdown_font=(FONT, 9),
        )
        self.preset_menu.pack(side='left')
        try:
            self.preset_menu.set('Elegir preset…')
        except Exception:
            pass

        # Separador visual: evita que presets y acciones rápidas se perciban
        # como una única hilera de botones amontonados.
        divider = ctk.CTkFrame(controls, width=1, height=24, fg_color=BORDER)
        divider.pack(side='left', padx=8, pady=9)
        divider.pack_propagate(False)

        selection_group = ctk.CTkFrame(controls, fg_color='transparent')
        selection_group.pack(side='left', fill='x', expand=True, padx=(0, 7), pady=8)
        ctk.CTkLabel(
            selection_group, text='SELECCIÓN', font=(FONT, 8, 'bold'), text_color=MUTED,
        ).pack(side='left', padx=(0, 7))
        ctk.CTkButton(
            selection_group, text='Seleccionar todos los tweaks', width=168, height=29, corner_radius=7,
            fg_color=theme_color('#11304a'), hover_color=theme_color('#164f7d'),
            border_width=1, border_color=theme_color('#245b82'), text_color=theme_color('#9bddff'),
            font=(FONT, 8, 'bold'), command=self._select_all,
        ).pack(side='left', padx=(0, 5))
        ctk.CTkButton(
            selection_group, text='Con rollback', width=100, height=29, corner_radius=7,
            fg_color='transparent', hover_color=theme_color('#102840'), border_width=1,
            border_color=BORDER, text_color=TEXT_2, font=(FONT, 8, 'bold'),
            command=self._select_rollback_available,
        ).pack(side='left', padx=5)
        ctk.CTkButton(
            selection_group, text='Limpiar', width=72, height=29, corner_radius=7,
            fg_color='transparent', hover_color=theme_color('#102840'), border_width=1,
            border_color=BORDER, text_color=TEXT_2, font=(FONT, 8, 'bold'),
            command=self._clear_selection,
        ).pack(side='left', padx=5)

        self.btn_refresh_status = ctk.CTkButton(
            controls, text='Actualizar estado', width=112, height=29, corner_radius=7,
            fg_color='transparent', hover_color=theme_color('#102840'), border_width=1,
            border_color=BORDER, text_color=TEXT_2, font=(FONT, 8, 'bold'),
            command=self.refresh_status,
        )
        self.btn_refresh_status.pack(side='right', padx=(6, 11), pady=8)

        # V0.10.2.53w — Tweaks Search, Filters & State Polish
        # La barra de filtros es deliberadamente compacta y de dos líneas para
        # evitar volver a saturar la pantalla con botones permanentes.
        filters = ctk.CTkFrame(
            self.frame, fg_color=CARD, border_width=1, border_color=BORDER,
            corner_radius=10,
        )
        filters.pack(fill='x', padx=18, pady=(0, 8))
        self.filter_bar = filters

        search_line = ctk.CTkFrame(filters, fg_color='transparent')
        search_line.pack(fill='x', padx=11, pady=(8, 4))
        ctk.CTkLabel(
            search_line, text='BUSCAR', font=(FONT, 8, 'bold'), text_color=MUTED,
        ).pack(side='left', padx=(0, 7))
        self.search_var = ctk.StringVar(value='')
        self.search_entry = ctk.CTkEntry(
            search_line, textvariable=self.search_var, height=29, corner_radius=7,
            placeholder_text='Nombre, descripción, categoría o ID…',
            fg_color=theme_color('#091726'), border_color=BORDER,
            text_color=TEXT, placeholder_text_color=MUTED,
            font=(FONT, 9),
        )
        self.search_entry.pack(side='left', fill='x', expand=True)
        self.lbl_filter_count = ctk.CTkLabel(
            search_line, text=f'{len(self.items)} de {len(self.items)}',
            font=(FONT, 9, 'bold'), text_color=CYAN,
        )
        self.lbl_filter_count.pack(side='right', padx=(12, 2))

        filter_line = ctk.CTkFrame(filters, fg_color='transparent')
        filter_line.pack(fill='x', padx=11, pady=(3, 8))

        def _filter_menu(parent, label, values, variable, width):
            group = ctk.CTkFrame(parent, fg_color='transparent')
            group.pack(side='left', padx=(0, 10))
            ctk.CTkLabel(
                group, text=label, font=(FONT, 8, 'bold'), text_color=MUTED,
            ).pack(side='left', padx=(0, 6))
            menu = ctk.CTkOptionMenu(
                group, values=list(values), variable=variable,
                command=lambda _value: self._schedule_filter_apply(),
                width=width, height=27, corner_radius=7,
                fg_color=theme_color('#0d2942'), button_color=theme_color('#164f7d'),
                button_hover_color=theme_color('#1d628f'), dropdown_fg_color=theme_color('#0d1828'),
                dropdown_hover_color=theme_color('#16324c'), text_color=theme_color('#d5e9f8'),
                font=(FONT, 8, 'bold'), dropdown_font=(FONT, 8),
            )
            menu.pack(side='left')
            return menu

        self.state_filter_var = ctk.StringVar(value='Todos')
        self.category_filter_var = ctk.StringVar(value='Todas')
        self.risk_filter_var = ctk.StringVar(value='Todos')
        self.state_filter_menu = _filter_menu(
            filter_line, 'ESTADO',
            ('Todos', 'Aplicados por CorePulse', 'Ya estaban aplicados', 'Parciales', 'No aplicados', 'No verificables', 'No disponibles'),
            self.state_filter_var, 176,
        )
        self.category_filter_menu = _filter_menu(
            filter_line, 'CATEGORÍA', ('Todas', *CATEGORY_ORDER),
            self.category_filter_var, 152,
        )
        self.risk_filter_menu = _filter_menu(
            filter_line, 'RIESGO', ('Todos', 'Bajo', 'Medio', 'Alto', 'Crítico'),
            self.risk_filter_var, 98,
        )
        self.compatible_only_var = ctk.BooleanVar(value=False)
        self.chk_compatible_only = ctk.CTkCheckBox(
            filter_line, text='Solo compatibles con este equipo',
            variable=self.compatible_only_var, command=self._schedule_filter_apply,
            font=(FONT, 8), text_color=TEXT_2, fg_color=CYAN,
            hover_color=theme_color('#0d8fc7'), border_color=theme_color('#31516d'),
            checkbox_width=18, checkbox_height=18,
        )
        self.chk_compatible_only.pack(side='right', padx=(10, 2))
        self._filter_widgets = (
            self.search_entry, self.state_filter_menu, self.category_filter_menu,
            self.risk_filter_menu, self.chk_compatible_only,
        )
        try:
            self.search_var.trace_add('write', lambda *_args: self._schedule_filter_apply(120))
        except Exception:
            pass

        self.body_scroll = StableScrollHost(self.frame, fg_color=BG, backend='place')
        self.body_scroll.pack(fill='both', expand=True, padx=13, pady=(0, 6))
        self.body = self.body_scroll.content
        grouped = {}
        for item in self.items:
            grouped.setdefault(item['category'], []).append(item)
        self._catalog_groups = [(category, grouped.get(category, [])) for category in CATEGORY_ORDER if grouped.get(category)]
        self._loading_catalog = ctk.CTkLabel(
            self.body, text='Preparando ajustes…', font=(FONT, 10, 'bold'), text_color=MUTED,
            anchor='w',
        )
        self._loading_catalog.pack(anchor='w', padx=12, pady=18)

        action = ctk.CTkFrame(self.frame, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=10)
        action.pack(fill='x', padx=18, pady=(0, 13))
        self.action_bar = action
        left = ctk.CTkFrame(action, fg_color='transparent')
        left.pack(side='left', fill='x', expand=True, padx=10, pady=8)
        self.chk_restore = ctk.CTkCheckBox(
            left, text='Crear punto de restauración antes de aplicar (requiere administrador)',
            variable=self.restore_point_var, font=(FONT, 8), text_color=MUTED, fg_color=CYAN,
            hover_color=theme_color('#0d8fc7'), border_color=theme_color('#31516d'),
        )
        self.chk_restore.pack(anchor='w')
        self.lbl_result = ctk.CTkLabel(left, text='Listo para seleccionar ajustes.', font=(FONT, 8), text_color=MUTED, anchor='w')
        self.lbl_result.pack(anchor='w', pady=(3, 0))
        self.lbl_result_detail = ctk.CTkLabel(
            left, text='', font=(FONT, 8), text_color=MUTED, anchor='w', justify='left', wraplength=820,
        )
        self.lbl_result_detail.pack(anchor='w', pady=(2, 0))
        buttons = ctk.CTkFrame(action, fg_color='transparent')
        buttons.pack(side='right', padx=10, pady=8)

        # Reiniciar Explorer es contextual: permanece oculto hasta que una
        # operación confirme que realmente hace falta. Así no ocupa espacio
        # visual de forma permanente.
        self.btn_restart = ctk.CTkButton(
            buttons, text='Reiniciar Explorador', width=124, height=31,
            fg_color='transparent', hover_color=theme_color('#102840'),
            border_width=1, border_color=BORDER, text_color=TEXT_2,
            font=(FONT, 8, 'bold'), command=self._restart_explorer,
        )
        self._restart_visible = False

        # Las dos variantes de rollback viven en un menú contextual único.
        # Conservamos los nombres funcionales exactos dentro del menú:
        # 'Deshacer seleccionados' y 'Deshacer TODO lo aplicado'.
        self.btn_undo_menu = ctk.CTkButton(
            buttons, text='Deshacer cambios  ▾', width=145, height=31,
            fg_color=theme_color('#2b1d26'), hover_color=theme_color('#412530'),
            border_width=1, border_color=theme_color('#693343'), text_color='#ffb0bd',
            font=(FONT, 8, 'bold'), command=self._show_undo_menu,
        )
        self.btn_undo_menu.pack(side='left', padx=(4, 5))

        # Alias de compatibilidad interna: el motor y pruebas históricas pueden
        # seguir tratando undo/undo_all como acciones separadas, aunque la UI
        # expone un solo control visual.
        self.btn_undo = self.btn_undo_menu
        self.btn_undo_all = self.btn_undo_menu

        self.btn_apply = ctk.CTkButton(
            buttons, text='Aplicar seleccionados', width=145, height=31,
            fg_color=theme_color('#0d5c45'), hover_color=theme_color('#11765a'),
            border_width=1, border_color=theme_color('#178967'), text_color='#b8ffdf',
            font=(FONT, 8, 'bold'), command=lambda: self._run_batch('apply'),
        )
        self.btn_apply.pack(side='left', padx=(5, 0))
        try:
            self.btn_apply.configure(state='disabled')
            self.btn_undo.configure(state='disabled')
            self.btn_undo_all.configure(state='disabled')
        except Exception:
            pass
        self._update_selected_count()

    def _open_restore_center(self):
        """Abre el Restore Center dentro de la misma página, sin nueva ventana."""
        if self._busy or self._restore_center_panel is not None:
            return
        for widget in (self.header_bar, self.info_bar, self.controls_bar, self.filter_bar, self.body_scroll, self.action_bar):
            try:
                widget.pack_forget()
            except Exception:
                pass
        self._restore_center_panel = TweakRestoreCenter(
            self.app,
            self.frame,
            on_close=self._close_restore_center,
            on_changed=self._on_restore_center_changed,
        )
        self._restore_center_panel.widget().pack(fill='both', expand=True)

    def _close_restore_center(self):
        panel = self._restore_center_panel
        self._restore_center_panel = None
        if panel is not None:
            try:
                panel.destroy()
            except Exception:
                pass
        # Recompone exactamente el orden visual de Tweaks V0.10.2.29w.
        try:
            self.header_bar.pack(fill='x', padx=18, pady=(15, 7))
            self.info_bar.pack(fill='x', padx=18, pady=(0, 8))
            self.controls_bar.pack(fill='x', padx=18, pady=(0, 8))
            self.filter_bar.pack(fill='x', padx=18, pady=(0, 8))
            self.body_scroll.pack(fill='both', expand=True, padx=13, pady=(0, 6))
            self.action_bar.pack(fill='x', padx=18, pady=(0, 13))
        except Exception:
            pass
        self.refresh_status()

    def _on_restore_center_changed(self):
        """Sincroniza badges/estados al volver de una restauración."""
        try:
            self._rollback_ids_cache = set(saved_rollback_ids())
        except Exception:
            self._rollback_ids_cache = set()
        try:
            self.refresh_status()
        except Exception:
            pass

    def _on_preset_selected(self, label):
        """Selecciona inmediatamente el preset elegido sin añadir otro botón."""
        key = self._preset_label_to_key.get(str(label))
        if key:
            self._select_preset(key)

    def _show_undo_menu(self):
        """Menú compacto para rollback seleccionado o rollback global."""
        if self._busy:
            return
        rollback_ids = set(saved_rollback_ids())
        selected_rollback = [tid for tid in self._selected_ids() if tid in rollback_ids]

        menu = tk.Menu(
            self.app, tearoff=0, bg=theme_color('#0d1828'), fg=TEXT,
            activebackground=theme_color('#19324e'), activeforeground=TEXT,
            disabledforeground=MUTED, bd=1, relief='flat', font=(FONT, 9),
        )
        menu.add_command(
            label='Deshacer seleccionados',
            state='normal' if selected_rollback else 'disabled',
            command=lambda: self._run_batch('undo'),
        )
        menu.add_separator()
        menu.add_command(
            label='Deshacer TODO lo aplicado',
            state='normal' if rollback_ids else 'disabled',
            command=self._run_undo_all,
        )
        if not rollback_ids:
            menu.add_separator()
            menu.add_command(label='No hay rollback pendiente', state='disabled')

        try:
            x = self.btn_undo_menu.winfo_rootx()
            y = self.btn_undo_menu.winfo_rooty() + self.btn_undo_menu.winfo_height() + 2
            menu.tk_popup(x, y)
        finally:
            try:
                menu.grab_release()
            except Exception:
                pass

    def _set_restart_available(self, visible):
        """Muestra Reiniciar Explorador sólo cuando una operación lo requiere."""
        visible = bool(visible)
        if visible == getattr(self, '_restart_visible', False):
            return
        self._restart_visible = visible
        try:
            if visible:
                self.btn_restart.pack(side='left', padx=(0, 5), before=self.btn_undo_menu)
            else:
                self.btn_restart.pack_forget()
        except Exception:
            pass

    def _build_catalog_step(self):
        """Construye el catálogo completo en un único turno corto.

        Las filas son widgets Tk nativos (sin un CTkCanvas por fila), así que 66
        ajustes dejan de requerir una construcción incremental visible. El usuario
        ve el shell y, acto seguido, el catálogo terminado; no puede arrastrar una
        scrollbar sobre una geometría que todavía está creciendo por categorías.
        """
        if not self._alive or self._catalog_ready:
            return
        try:
            self._loading_catalog.configure(text='Preparando ajustes…')
        except Exception:
            pass
        for category, rows in self._catalog_groups:
            self._build_category(category, rows)
        self._catalog_index = len(self._catalog_groups)
        self._catalog_ready = True
        try:
            self._loading_catalog.destroy()
        except Exception:
            pass
        try:
            self._compatible_ids_cache = set(compatible_tweak_ids())
        except Exception:
            self._compatible_ids_cache = set()
        self._no_results_label = ctk.CTkLabel(
            self.body,
            text='No hay tweaks que coincidan con los filtros actuales.',
            font=(FONT, 10, 'bold'), text_color=MUTED, anchor='w',
        )
        pending = self._pending_preset
        self._pending_preset = None
        if pending:
            self._select_preset(pending)
        self._sync_all_checkbox_glyphs()
        self._apply_filters(preserve_scroll=False)
        self.refresh_status()
        try:
            self.body_scroll._schedule_geometry(1)
        except Exception:
            pass

    def _build_category(self, title, rows):
        """Categoría ligera con identidad visual CorePulse propia."""
        is_security = title == 'Seguridad avanzada'
        visual = category_visual(title)

        card = tk.Frame(
            self.body, bg=visual['surface'], bd=0, highlightthickness=1,
            highlightbackground=visual['border'], highlightcolor=visual['border'],
        )
        card.pack(fill='x', padx=5, pady=(0, 10))
        self.category_widgets[title] = card
        self._category_row_ids.setdefault(title, [])

        # Header de módulo: una barra de acento identifica la categoría sin
        # colorear en exceso toda la lista. Sigue siendo Tk nativo y barato.
        header = tk.Frame(card, bg=visual['surface'], bd=0, highlightthickness=0)
        header.pack(fill='x', padx=0, pady=0)
        accent = tk.Frame(header, bg=visual['accent'], width=5, bd=0, highlightthickness=0)
        accent.pack(side='left', fill='y')
        accent.pack_propagate(False)

        header_text = tk.Frame(header, bg=visual['surface'], bd=0, highlightthickness=0)
        header_text.pack(side='left', fill='x', expand=True, padx=(11, 8), pady=(9, 7))
        heading = f'{title.upper()} · AVANZADO' if is_security else title.upper()
        tk.Label(
            header_text, text=heading, font=(FONT, 10, 'bold'),
            fg=visual['accent'], bg=visual['surface'], anchor='w', bd=0,
        ).pack(side='left', anchor='w')

        count_text = f"{len(rows)} {'AJUSTE' if len(rows) == 1 else 'AJUSTES'}"
        count_label = tk.Label(
            header_text, text=count_text, font=(FONT, 7, 'bold'),
            fg=TEXT_2, bg=visual['surface'], anchor='e', bd=0, padx=7, pady=2,
            highlightthickness=1, highlightbackground=visual['border'], highlightcolor=visual['border'],
        )
        count_label.pack(side='right', anchor='e')
        self.category_count_labels[title] = count_label

        if is_security:
            tk.Label(
                card,
                text='No incluido en presets · Estos cambios reducen protecciones de Windows. Úsalos sólo si entiendes el impacto y tienes una alternativa de seguridad/recuperación.',
                font=(FONT, 8), fg=theme_color('#d9959f'), bg=visual['surface'],
                anchor='w', justify='left', wraplength=1120, bd=0,
            ).pack(anchor='w', padx=16, pady=(0, 7))

        for item in rows:
            self._build_row(card, item, visual)

    def _build_row(self, card, item, visual):
        """Fila 100% Tk con color base heredado de su categoría."""
        risk = item.get('risk', 'Bajo')
        row_bg = visual['row']
        row_border = theme_color('#4d2530') if risk == 'Crítico' else visual['border']
        row = tk.Frame(
            card, bg=row_bg, bd=0, highlightthickness=1,
            highlightbackground=row_border, highlightcolor=row_border,
        )
        row.pack(fill='x', padx=9, pady=4)
        self.row_widgets[item['id']] = row
        self._category_row_ids.setdefault(item.get('category'), []).append(item['id'])

        var = tk.BooleanVar(master=row, value=False)
        self.vars[item['id']] = var
        check = tk.Label(
            row, text='☐', width=2, font=('Segoe UI Symbol', 14, 'bold'),
            fg=theme_color('#5f7189'), bg=row_bg, anchor='center', cursor='hand2', bd=0,
        )
        check.pack(side='left', padx=(9, 4), pady=10)
        self.check_labels[item['id']] = check

        text_box = tk.Frame(row, bg=row_bg, bd=0, highlightthickness=0)
        text_box.pack(side='left', fill='x', expand=True, pady=7)
        title_label = tk.Label(
            text_box, text=item['title'], font=(FONT, 9, 'bold'), fg=TEXT, bg=row_bg,
            anchor='w', justify='left', bd=0,
        )
        title_label.pack(anchor='w', fill='x')
        desc_label = tk.Label(
            text_box, text=item['description'], font=(FONT, 8), fg=MUTED, bg=row_bg,
            anchor='w', justify='left', wraplength=760, bd=0,
        )
        desc_label.pack(anchor='w', fill='x', pady=(1, 0))
        note_label = None
        if item.get('note'):
            note_label = tk.Label(
                text_box, text=item['note'], font=(FONT, 7), fg=theme_color('#9da9b9'), bg=row_bg,
                anchor='w', justify='left', wraplength=760, bd=0,
            )
            note_label.pack(anchor='w', fill='x', pady=(2, 0))

        meta = tk.Frame(row, bg=row_bg, bd=0, highlightthickness=0)
        meta.pack(side='right', padx=10, pady=7)
        flags = []
        if item.get('requires_admin'):
            flags.append('ADMIN')
        if item.get('requires_restart'):
            flags.append('REINICIO')
        elif item.get('requires_explorer'):
            flags.append('EXPLORER')
        tag = f"RIESGO {risk.upper()}"
        if flags:
            tag += ' · ' + ' · '.join(flags)
        risk_label = tk.Label(meta, text=tag, font=(FONT, 7, 'bold'), fg=RISK_COLORS.get(risk, AMBER), bg=row_bg, anchor='e', bd=0)
        risk_label.pack(anchor='e')
        status = tk.Label(meta, text='Comprobando…', font=(FONT, 8, 'bold'), fg=MUTED, bg=row_bg, anchor='e', bd=0)
        status.pack(anchor='e', pady=(2, 0))
        self.status_labels[item['id']] = status
        undo = tk.Label(meta, text='', font=(FONT, 7), fg=MUTED, bg=row_bg, anchor='e', bd=0)
        undo.pack(anchor='e')
        self.undo_labels[item['id']] = undo

        hover_nodes = [check, text_box, title_label, desc_label, meta, risk_label, status, undo]
        if note_label is not None:
            hover_nodes.append(note_label)
        self._bind_row_hover(row, hover_nodes, normal=row_bg, hover=visual['hover'])

        def toggle(_event=None, tweak_id=item['id']):
            self._toggle_row_selection(tweak_id)
            return 'break'

        for node in (check, text_box, title_label, desc_label, note_label):
            if node is not None:
                try:
                    node.bind('<Button-1>', toggle, add='+')
                except Exception:
                    pass

    def _toggle_row_selection(self, tweak_id):
        var = self.vars.get(tweak_id)
        if var is None:
            return
        try:
            var.set(not bool(var.get()))
        except Exception:
            return
        self._sync_checkbox_glyph(tweak_id)
        self._update_selected_count()

    def _sync_checkbox_glyph(self, tweak_id):
        var = self.vars.get(tweak_id)
        label = self.check_labels.get(tweak_id)
        if var is None or label is None:
            return
        try:
            selected = bool(var.get())
            label.configure(text='☑' if selected else '☐', fg=CYAN if selected else theme_color('#5f7189'))
        except Exception:
            pass

    def _sync_all_checkbox_glyphs(self):
        for tweak_id in tuple(self.check_labels):
            self._sync_checkbox_glyph(tweak_id)

    def _bind_row_hover(self, row, tk_nodes, *, normal=None, hover=None):
        """Hover ligero que conserva el tono visual de la categoría."""
        normal = normal or CARD_2
        hover = hover or theme_color('#0e1d2f')

        def paint(color):
            try:
                row.configure(bg=color)
            except Exception:
                pass
            for node in tk_nodes:
                try:
                    node.configure(bg=color)
                except Exception:
                    pass

        def enter(_event=None):
            paint(hover)

        def leave(_event=None):
            try:
                x, y = row.winfo_pointerxy()
                node = row.winfo_containing(x, y)
                while node is not None:
                    if node is row:
                        return
                    node = getattr(node, 'master', None)
            except Exception:
                pass
            paint(normal)

        for node in [row, *tk_nodes]:
            try:
                node.bind('<Enter>', enter, add='+')
                node.bind('<Leave>', leave, add='+')
            except Exception:
                pass

    @staticmethod
    def _configure_status_label(widget, *, text, color):
        try:
            if isinstance(widget, tk.Label):
                widget.configure(text=text, fg=color)
            else:
                widget.configure(text=text, text_color=color)
        except Exception:
            pass

    def _schedule_filter_apply(self, delay=0):
        """Debounce de búsqueda/filtros para no recalcular geometría por tecla."""
        if not self._alive or not self._catalog_ready:
            return
        if self._filter_after_id is not None:
            try:
                self.frame.after_cancel(self._filter_after_id)
            except Exception:
                pass
            self._filter_after_id = None

        def run():
            self._filter_after_id = None
            if not self._alive:
                return
            host = getattr(self, 'body_scroll', None)
            try:
                if host is not None and host.is_scrolling():
                    host.defer_until_idle(lambda: self._apply_filters(preserve_scroll=True))
                    return
            except Exception:
                pass
            self._apply_filters(preserve_scroll=True)

        try:
            self._filter_after_id = self.frame.after(max(0, int(delay)), run)
        except Exception:
            run()

    def _state_filter_matches(self, tweak_id, selected_state):
        if selected_state == 'Todos':
            return True
        detected = self._detected_states.get(tweak_id) or {}
        status = str(detected.get('status') or 'pending').lower()
        origin = str(detected.get('origin') or 'external_or_none').lower()
        available = detected.get('available')
        if selected_state == 'Aplicados por CorePulse':
            return status == 'applied' and origin == 'corepulse'
        if selected_state == 'Ya estaban aplicados':
            return status == 'applied' and origin != 'corepulse'
        if selected_state == 'Parciales':
            return status == 'partial'
        if selected_state == 'No aplicados':
            return status == 'not_applied'
        if selected_state == 'No verificables':
            return status in {'unknown', 'action'}
        if selected_state == 'No disponibles':
            return status == 'unavailable' or available is False
        return True

    def _item_matches_filters(self, item):
        tweak_id = item['id']
        query = str(self.search_var.get() if self.search_var is not None else '').strip().casefold()
        state = str(self.state_filter_var.get() if self.state_filter_var is not None else 'Todos')
        category = str(self.category_filter_var.get() if self.category_filter_var is not None else 'Todas')
        risk = str(self.risk_filter_var.get() if self.risk_filter_var is not None else 'Todos')
        compatible_only = bool(self.compatible_only_var.get()) if self.compatible_only_var is not None else False

        if query:
            haystack = ' '.join(
                str(item.get(key) or '')
                for key in ('id', 'title', 'description', 'note', 'category', 'risk')
            ).casefold()
            if query not in haystack:
                return False
        if category != 'Todas' and str(item.get('category') or '') != category:
            return False
        if risk != 'Todos' and str(item.get('risk') or 'Bajo') != risk:
            return False
        if compatible_only and tweak_id not in self._compatible_ids_cache:
            return False
        if not self._state_filter_matches(tweak_id, state):
            return False
        return True

    def _apply_filters(self, *, preserve_scroll=True):
        """Filtra widgets ya construidos; no destruye ni recrea las 78 filas.

        Esta decisión es importante para el scroll de CorePulse: ocultamos y
        recolocamos sólo las filas Tk existentes, manteniendo selección, badges,
        snapshot/rollback y referencias del motor intactas.
        """
        if not self._alive or not self._catalog_ready:
            return
        first = 0.0
        if preserve_scroll:
            try:
                first = float(self.body_scroll.yview()[0])
            except Exception:
                first = 0.0

        visible_ids = {
            item['id'] for item in self.items if self._item_matches_filters(item)
        }
        self._visible_ids = visible_ids

        # Ocultar primero todas las categorías y filas garantiza que el orden
        # original no cambie al alternar filtros repetidamente.
        for category, _rows in self._catalog_groups:
            card = self.category_widgets.get(category)
            if card is not None:
                try:
                    card.pack_forget()
                except Exception:
                    pass
            for tweak_id in self._category_row_ids.get(category, ()): 
                row = self.row_widgets.get(tweak_id)
                if row is not None:
                    try:
                        row.pack_forget()
                    except Exception:
                        pass

        for category, rows in self._catalog_groups:
            category_visible = [item['id'] for item in rows if item['id'] in visible_ids]
            if not category_visible:
                continue
            card = self.category_widgets.get(category)
            if card is None:
                continue
            try:
                card.pack(fill='x', padx=5, pady=(0, 10))
            except Exception:
                continue
            for tweak_id in self._category_row_ids.get(category, ()):
                if tweak_id not in visible_ids:
                    continue
                row = self.row_widgets.get(tweak_id)
                if row is not None:
                    try:
                        row.pack(fill='x', padx=9, pady=4)
                    except Exception:
                        pass
            count = self.category_count_labels.get(category)
            if count is not None:
                total = len(rows)
                shown = len(category_visible)
                text = f"{shown}/{total} AJUSTES" if shown != total else f"{total} {'AJUSTE' if total == 1 else 'AJUSTES'}"
                try:
                    count.configure(text=text)
                except Exception:
                    pass

        no_results = getattr(self, '_no_results_label', None)
        if no_results is not None:
            try:
                no_results.pack_forget()
            except Exception:
                pass
            if not visible_ids:
                try:
                    no_results.pack(fill='x', padx=12, pady=18)
                except Exception:
                    pass

        try:
            self.lbl_filter_count.configure(text=f'{len(visible_ids)} de {len(self.items)}')
        except Exception:
            pass

        try:
            self.body.update_idletasks()
            self.body_scroll._refresh_geometry()
        except Exception:
            try:
                self.body_scroll._schedule_geometry(0)
            except Exception:
                pass

        if preserve_scroll:
            try:
                self.body_scroll.yview_moveto(first)
            except Exception:
                pass
        try:
            self.body_scroll._flush_repaint(strong=True)
        except Exception:
            pass

    def _selected_ids(self):
        return [item['id'] for item in self.items if self.vars.get(item['id']) is not None and self.vars[item['id']].get()]

    def _update_selected_count(self):
        if not hasattr(self, 'lbl_selected'):
            return
        ids = self._selected_ids()
        meta = selected_metadata(ids)
        suffix = ''
        if meta['critical']:
            suffix = f" · {len(meta['critical'])} críticos"
        elif meta['high_risk']:
            suffix = f" · {len(meta['high_risk'])} alto riesgo"
        self.lbl_selected.configure(text=f'{len(ids)} seleccionados{suffix}', text_color=RED if meta['high_risk'] else CYAN)

    def _select_preset(self, key):
        if not self._catalog_ready:
            self._pending_preset = key
            self.lbl_result.configure(text='El catálogo se está preparando; el preset se aplicará a la selección al terminar.', text_color=CYAN)
            return
        compatible = set(compatible_tweak_ids())
        selected = set(preset_ids(key)) & compatible
        for tweak_id, var in self.vars.items():
            var.set(tweak_id in selected)
        self._sync_all_checkbox_glyphs()
        self._update_selected_count()

    def _select_all(self):
        try:
            self.preset_menu.set('Elegir preset…')
        except Exception:
            pass
        if not self._catalog_ready:
            self.lbl_result.configure(text='El catálogo se está preparando. Intenta de nuevo en un instante.', text_color=CYAN)
            return
        self._pending_preset = None
        compatible = set(compatible_tweak_ids())
        for tweak_id, var in self.vars.items():
            var.set(tweak_id in compatible)
        self._sync_all_checkbox_glyphs()
        self._update_selected_count()
        omitted = max(0, len(self.vars) - len(compatible))
        self.lbl_result.configure(text=f'{len(compatible)} tweaks compatibles seleccionados.', text_color=CYAN)
        self.lbl_result_detail.configure(
            text=(f'{omitted} ajuste(s) no aplican a este Windows/equipo y quedaron fuera de la selección.' if omitted else 'Todos los tweaks del catálogo son aplicables en este equipo.'),
            text_color=MUTED,
        )

    def _clear_selection(self):
        self._pending_preset = None
        try:
            self.preset_menu.set('Elegir preset…')
        except Exception:
            pass
        for var in self.vars.values():
            var.set(False)
        self._sync_all_checkbox_glyphs()
        self._update_selected_count()

    def _select_rollback_available(self):
        try:
            self.preset_menu.set('Elegir preset…')
        except Exception:
            pass
        rollback_ids = saved_rollback_ids()
        self._rollback_ids_cache = set(rollback_ids)
        for tweak_id, var in self.vars.items():
            var.set(tweak_id in rollback_ids)
        self._sync_all_checkbox_glyphs()
        self._update_selected_count()
        if rollback_ids:
            self.lbl_result.configure(text=f'{len(rollback_ids)} tweak(s) con rollback persistente seleccionados.', text_color=CYAN)
        else:
            self.lbl_result.configure(text='No hay cambios de CorePulse pendientes de deshacer.', text_color=MUTED)

    def refresh_status(self):
        if self._busy or self._detecting or not self._catalog_ready:
            return
        self._detecting = True
        env = environment_info()
        if env['supported']:
            edition = env.get('edition') or 'edición N/A'
            self.lbl_environment.configure(
                text=f"Windows 11 {edition} · build {env.get('build') or 'N/A'} · Admin: {'Sí' if env['admin'] else 'No'}",
                text_color=GREEN if env['admin'] else AMBER,
            )
            self.btn_apply.configure(state='normal')
            self.btn_undo.configure(state='normal')
            self.btn_undo_all.configure(state='normal')
        else:
            self.lbl_environment.configure(text='Disponible sólo en Windows 11', text_color=AMBER)
            self.btn_apply.configure(state='disabled')
            self.btn_undo.configure(state='disabled')
            self.btn_undo_all.configure(state='disabled')

        def worker():
            statuses = detect_all() if env['supported'] else {}
            rollback_ids = saved_rollback_ids()
            try:
                compatible_ids = set(compatible_tweak_ids()) if env['supported'] else set()
            except Exception:
                compatible_ids = set()

            def finish():
                self._detecting = False
                if not self._alive:
                    return
                self._rollback_ids_cache = set(rollback_ids)
                self._detected_states = dict(statuses)
                self._compatible_ids_cache = set(compatible_ids)
                applied_corepulse = 0
                preexisting = 0
                partial = 0
                unknown = 0
                for item in self.items:
                    detected = statuses.get(item['id'], {})
                    status = detected.get('status', 'unavailable')
                    origin = detected.get('origin', 'external_or_none')
                    available = bool(detected.get('available', True))

                    if status == 'applied' and origin == 'corepulse':
                        label, color = 'APLICADO · COREPULSE ✓', GREEN
                        applied_corepulse += 1
                    elif status == 'applied':
                        label, color = ('YA ESTABA APLICADO' if available else 'DETECTADO · NO MODIFICABLE'), (GREEN if available else AMBER)
                        preexisting += 1
                    elif status == 'partial':
                        label, color = ('PARCIAL · ROLLBACK ✓' if item['id'] in rollback_ids else 'PARCIAL'), AMBER
                        partial += 1
                    elif status == 'not_applied':
                        label, color = ('CAMBIADO · ROLLBACK ✓' if item['id'] in rollback_ids else 'NO APLICADO'), (AMBER if item['id'] in rollback_ids else MUTED)
                    elif status == 'unknown':
                        label, color = 'NO VERIFICABLE', AMBER
                        unknown += 1
                    elif status == 'action':
                        label, color = 'ESTADO NO DETECTABLE', MUTED
                        unknown += 1
                    elif status == 'unavailable':
                        label, color = 'NO DISPONIBLE', MUTED
                    else:
                        label, color = 'DESCONOCIDO', MUTED
                        unknown += 1

                    self._configure_status_label(self.status_labels[item['id']], text=label, color=color)
                    if item['id'] in rollback_ids:
                        undo_text = 'Deshacer exacto disponible' if item.get('undo_mode') == 'exact' else 'Reversión disponible'
                    elif status == 'applied' and origin == 'preexisting':
                        undo_text = 'Sin snapshot · detectado antes/fuera de CorePulse'
                    elif status == 'partial':
                        matched = detected.get('matched_targets', 0)
                        total = detected.get('total_targets', 0)
                        undo_text = f'{matched}/{total} objetivos coinciden' if total else 'Configuración incompleta'
                    elif status == 'unknown':
                        undo_text = 'CorePulse no asumirá el estado'
                    else:
                        undo_text = ''
                    try:
                        self.undo_labels[item['id']].configure(text=undo_text)
                    except Exception:
                        pass

                summary_parts = []
                if applied_corepulse:
                    summary_parts.append(f'{applied_corepulse} aplicados por CorePulse')
                if preexisting:
                    summary_parts.append(f'{preexisting} ya aplicados')
                if partial:
                    summary_parts.append(f'{partial} parciales')
                if unknown:
                    summary_parts.append(f'{unknown} no verificables')
                if summary_parts:
                    self.lbl_result.configure(text='Detección: ' + ' · '.join(summary_parts), text_color=CYAN if not (partial or unknown) else AMBER)
                # Los filtros de estado/compatibilidad se actualizan con la misma
                # evidencia recién detectada, sin reconstruir el catálogo.
                self._apply_filters(preserve_scroll=True)

            def schedule_finish():
                if not self._alive:
                    return
                host = getattr(self, 'body_scroll', None)
                if host is not None:
                    host.defer_until_idle(finish)
                else:
                    finish()
            try:
                self.frame.after(0, schedule_finish)
            except Exception:
                self._detecting = False

        threading.Thread(target=worker, name='CorePulseTweaksDetect', daemon=True).start()

    def _set_busy(self, busy, text=None):
        self._busy = bool(busy)
        state = 'disabled' if busy else 'normal'
        # Sólo controles visuales únicos; undo/undo_all comparten un botón.
        for btn in (self.btn_apply, self.btn_undo_menu, self.btn_restart, self.btn_refresh_status, self.btn_restore_center):
            try:
                btn.configure(state=state)
            except Exception:
                pass
        try:
            self.preset_menu.configure(state=state)
        except Exception:
            pass
        for widget in getattr(self, '_filter_widgets', ()):
            try:
                widget.configure(state=state)
            except Exception:
                pass
        if text:
            self.lbl_result.configure(text=text, text_color=CYAN if busy else MUTED)

    def _confirm_high_risk(self, ids, meta):
        high = meta['high_risk']
        if not high:
            return True
        names = '\n'.join(f"• {row['title']} ({row['risk']})" for row in high[:8])
        if len(high) > 8:
            names += f"\n• … y {len(high) - 8} más"
        text = (
            'Has seleccionado cambios de ALTO IMPACTO.\n\n'
            f'{names}\n\n'
            'Pueden reducir seguridad, quitar componentes o alterar Windows Update. '
            'No forman parte de ningún preset automático.\n\n¿Quieres continuar?'
        )
        if not messagebox.askyesno('CorePulse · Confirmación de alto impacto', text, parent=self.app):
            return False
        if meta['critical']:
            text2 = (
                'CONFIRMACIÓN CRÍTICA\n\n'
                'La selección incluye cambios de seguridad como Defender, SmartScreen o UAC. '
                'El sistema puede quedar con menos protección.\n\n'
                'CorePulse recomienda crear un punto de restauración y disponer de otra protección.\n\n'
                '¿Confirmas nuevamente que deseas aplicar estos cambios?'
            )
            if not messagebox.askyesno('CorePulse · Riesgo crítico', text2, parent=self.app):
                return False
        return True

    def _run_undo_all(self):
        rollback_ids = saved_rollback_ids()
        if not rollback_ids:
            self.lbl_result.configure(text='No hay cambios aplicados por CorePulse pendientes de deshacer.', text_color=MUTED)
            self.lbl_result_detail.configure(text='No se tocarán ajustes que no tengan un snapshot persistente de CorePulse.', text_color=MUTED)
            return
        if not messagebox.askyesno(
            'CorePulse · Deshacer todos los tweaks',
            f'CorePulse tiene {len(rollback_ids)} tweak(s) con rollback guardado.\n\n'
            'Se restaurará cada valor previo y se verificará después. Si algún cambio requiere administrador, Windows mostrará UAC.\n\n'
            'El snapshot sólo se eliminará cuando la reversión quede confirmada.\n\n¿Continuar?',
            parent=self.app,
        ):
            return
        self._set_busy(True, 'Restaurando TODOS los cambios de CorePulse…')

        def worker():
            results = undo_all_saved(auto_elevate=True)
            ok = sum(1 for row in results if row.get('success'))
            failed = len(results) - ok

            def finish():
                if not self._alive:
                    return
                self._set_busy(False)
                if failed == 0:
                    self.lbl_result.configure(text=f'{ok} tweaks restaurados y verificados.', text_color=GREEN)
                    self.lbl_result_detail.configure(
                        text='Todos los cambios que CorePulse tenía registrados volvieron a su estado previo. No queda rollback pendiente.',
                        text_color=GREEN,
                    )
                else:
                    failures = []
                    for row in results:
                        tweak_id = row.get('id')
                        if row.get('success'):
                            self._configure_status_label(self.status_labels.get(tweak_id), text='RESTAURADO ✓', color=GREEN)
                            continue
                        title = self._item_by_id.get(tweak_id, {}).get('title') or tweak_id or 'Tweak'
                        reason = str(row.get('message') or 'Error no especificado.').replace('\n', ' ').strip()
                        failures.append(f'• {title}: {reason[:220]}')
                        self._configure_status_label(self.status_labels.get(tweak_id), text='ROLLBACK PENDIENTE', color=RED)
                    self.lbl_result.configure(text=f'{ok} restaurados · {failed} pendientes', text_color=RED)
                    self.lbl_result_detail.configure(
                        text='CorePulse NO eliminó los snapshots que fallaron. Puedes pulsar nuevamente “Deshacer TODO lo aplicado”.\n' + '\n'.join(failures[:6]),
                        text_color=RED,
                    )
                self.refresh_status()

            try:
                self.frame.after(0, finish)
            except Exception:
                pass

        threading.Thread(target=worker, name='CorePulseTweaksUndoAll', daemon=True).start()

    def _run_batch(self, action):
        ids = self._selected_ids()
        if not ids:
            self.lbl_result.configure(text='Selecciona al menos un tweak.', text_color=AMBER)
            return
        if action == 'undo':
            rollback_ids = saved_rollback_ids()
            ids = [tweak_id for tweak_id in ids if tweak_id in rollback_ids]
            if not ids:
                self.lbl_result.configure(text='Ninguno de los tweaks seleccionados tiene rollback de CorePulse.', text_color=AMBER)
                self.lbl_result_detail.configure(
                    text='Para proteger tus ajustes previos, CorePulse sólo deshace cambios que tengan un snapshot guardado.',
                    text_color=MUTED,
                )
                return
        env = environment_info()
        if not env['supported']:
            self.lbl_result.configure(text='Esta función requiere Windows 11.', text_color=RED)
            return
        meta = selected_metadata(ids)
        if action == 'apply' and not self._confirm_high_risk(ids, meta):
            return

        verb = 'aplicar' if action == 'apply' else 'deshacer'
        extra = ''
        if action == 'apply' and meta['requires_admin'] and not env['admin']:
            extra += '\n\nWindows mostrará UAC sólo para los tweaks que realmente requieren administrador. Los ajustes de usuario se aplicarán con tu sesión normal.'
        if action == 'undo' and meta['requires_admin'] and not env['admin']:
            extra += '\n\nWindows mostrará UAC sólo para restaurar los cambios que requieren administrador.'
        if meta['requires_restart']:
            extra += '\n\nAlgunos cambios requerirán reiniciar Windows.'
        if not messagebox.askyesno(
            'CorePulse · Tweaks de Windows 11',
            f'¿Quieres {verb} {len(ids)} tweak(s) seleccionados?\n\n'
            'CorePulse registra el valor previo de los cambios de Registro. Las acciones externas indican su método de reversión.' + extra,
            parent=self.app,
        ):
            return

        self._set_busy(True, 'Aplicando cambios…' if action == 'apply' else 'Restaurando cambios…')
        use_restore = action == 'apply' and (bool(self.restore_point_var.get()) or bool(meta.get('high_risk')))
        tele_before = copy.deepcopy(getattr(self.app, 'latest_telemetry', {}) or {}) if action == 'apply' else {}
        disks_before = copy.deepcopy(getattr(self.app, 'latest_disks', []) or []) if action == 'apply' else []
        operation_session = {'value': None}

        def worker():
            if action == 'apply':
                try:
                    batt_before = collect_battery_health(tele_before)
                    before_snapshot = capture_metrics(tele_before, disks_before, batt_before, label='before_tweaks')
                    save_snapshot(before_snapshot, slot='before')
                    operation_session['value'] = start_operation(
                        'Tweaks de Windows', tele_before, disks_before, batt_before,
                        metadata={'tweak_ids': list(ids), 'count': len(ids)},
                    )
                except Exception:
                    operation_session['value'] = None
            restore_result = None
            if use_restore:
                restore_result = create_restore_point()
            results = apply_many(ids, auto_elevate=True) if action == 'apply' else undo_many(ids)
            unavailable = sum(1 for row in results if row.get('status') == 'unavailable' or row.get('skipped'))
            ok = sum(1 for row in results if row.get('success'))
            failed = sum(1 for row in results if (not row.get('success')) and not (row.get('status') == 'unavailable' or row.get('skipped')))
            explorer = any(row.get('success') and row.get('requires_explorer') for row in results)
            restart = any(row.get('success') and row.get('requires_restart') for row in results)

            def finish():
                if not self._alive:
                    return
                self._set_busy(False)
                noun = 'restaurados' if action == 'undo' else 'aplicados/verificados'
                parts = [f'{ok} {noun}']
                if unavailable:
                    parts.append(f'{unavailable} no disponibles')
                if failed:
                    parts.append(f'{failed} con error')
                if restore_result is not None:
                    parts.append('punto de restauración creado' if restore_result.get('success') else 'punto de restauración no creado')
                self._set_restart_available(explorer)
                if explorer:
                    parts.append('reinicio de Explorador recomendado')
                if restart:
                    parts.append('reinicio de Windows requerido/recomendado')
                self.lbl_result.configure(text=' · '.join(parts), text_color=RED if failed else (AMBER if unavailable else GREEN))
                failures = []
                unavailable_details = []
                for row_result in results:
                    tweak_id = row_result.get('id')
                    item = self._item_by_id.get(tweak_id, {})
                    title = item.get('title') or tweak_id or 'Tweak'
                    if row_result.get('status') == 'unavailable' or row_result.get('skipped'):
                        reason = str(row_result.get('message') or 'No disponible en este equipo.').replace('\n', ' ').strip()
                        if len(reason) > 150:
                            reason = reason[:147] + '…'
                        unavailable_details.append(f'• {title}: {reason}')
                        self._configure_status_label(self.status_labels.get(tweak_id), text='NO DISPONIBLE', color=MUTED)
                        continue
                    if row_result.get('success'):
                        if action == 'apply':
                            if row_result.get('changed') and row_result.get('rollback_available'):
                                label, color = 'APLICADO · ROLLBACK ✓', GREEN
                            elif not row_result.get('changed') and not row_result.get('rollback_available'):
                                label, color = 'PREEXISTENTE · SIN SNAPSHOT', AMBER
                            else:
                                label, color = 'APLICADO ✓', GREEN
                        else:
                            label, color = 'RESTAURADO ✓', GREEN
                        self._configure_status_label(self.status_labels.get(tweak_id), text=label, color=color)
                    else:
                        reason = str(row_result.get('message') or 'Error no especificado.').replace('\n', ' ').strip()
                        if len(reason) > 180:
                            reason = reason[:177] + '…'
                        failures.append(f'• {title}: {reason}')
                        self._configure_status_label(self.status_labels.get(tweak_id), text='ERROR', color=RED)
                if failures:
                    self.lbl_result_detail.configure(
                        text='Fallaron:\n' + '\n'.join(failures[:6]),
                        text_color=RED,
                    )
                else:
                    if unavailable:
                        detail = (
                            f'{unavailable} tweak(s) quedaron como NO DISPONIBLE y no se intentaron modificar. ' +
                            ('Los cambios aplicables fueron verificados y mantienen rollback persistente.' if action == 'apply' else 'Los rollbacks aplicables fueron verificados.')
                        )
                        if unavailable_details:
                            detail += '\n' + '\n'.join(unavailable_details[:5])
                        detail_color = AMBER
                    else:
                        detail = 'Todos los cambios nuevos fueron verificados y tienen snapshot persistente antes de tocar Windows. Los ajustes preexistentes se identifican aparte porque CorePulse no puede inventar su estado anterior.' if action == 'apply' else 'Todos los cambios seleccionados volvieron a su estado anterior y fueron verificados.'
                        detail_color = GREEN
                    self.lbl_result_detail.configure(text=detail, text_color=detail_color)
                if action == 'apply':
                    session = operation_session.get('value')
                    if failed:
                        try:
                            mark_operation(session, status='failed', note=f'{failed} tweak(s) no pudieron completarse.', metadata={'failed': failed, 'applied': ok})
                        except Exception:
                            pass
                    elif explorer or restart:
                        try:
                            reason = 'Requiere reiniciar Windows antes de medir el efecto posterior.' if restart else 'Requiere reiniciar Explorer antes de medir el efecto posterior.'
                            mark_operation(session, status='pending_restart', note=reason, metadata={'requires_restart': bool(restart), 'requires_explorer': bool(explorer), 'applied': ok})
                        except Exception:
                            pass
                    else:
                        def capture_after_worker():
                            try:
                                # Deja que la telemetría complete varios ciclos para evitar
                                # comparar el mismo snapshot anterior con el posterior.
                                import time as _time
                                _time.sleep(3.2)
                                tele_after = copy.deepcopy(getattr(self.app, 'latest_telemetry', {}) or {})
                                disks_after = copy.deepcopy(getattr(self.app, 'latest_disks', []) or [])
                                batt_after = collect_battery_health(tele_after)
                                after_snapshot = capture_metrics(tele_after, disks_after, batt_after, label='after_tweaks_settled')
                                save_snapshot(after_snapshot, slot='after')
                                finish_operation(session, tele_after, disks_after, batt_after, metadata={'applied': ok, 'settle_seconds': 3.2})
                            except Exception:
                                try:
                                    mark_operation(session, status='measurement_failed', note='Los tweaks se aplicaron, pero no se pudo obtener la medición posterior.')
                                except Exception:
                                    pass
                        threading.Thread(target=capture_after_worker, name='CorePulseTweaksAfterSnapshot', daemon=True).start()
                self.refresh_status()

            try:
                self.frame.after(0, finish)
            except Exception:
                pass

        threading.Thread(target=worker, name='CorePulseTweaksWorker', daemon=True).start()

    def _restart_explorer(self):
        if not messagebox.askyesno(
            'CorePulse · Reiniciar Explorador',
            'Se cerrará y volverá a abrir explorer.exe. Las ventanas del Explorador pueden cerrarse.\n\n¿Continuar?',
            parent=self.app,
        ):
            return
        result = restart_explorer()
        if result.get('success'):
            self._set_restart_available(False)
        self.lbl_result.configure(text=result.get('message') or 'Operación finalizada.', text_color=GREEN if result.get('success') else RED)

    def refresh(self):
        self.refresh_status()

    def destroy(self):
        self._alive = False
        if self._filter_after_id is not None:
            try:
                self.frame.after_cancel(self._filter_after_id)
            except Exception:
                pass
            self._filter_after_id = None
        panel = getattr(self, '_restore_center_panel', None)
        self._restore_center_panel = None
        if panel is not None:
            try:
                panel.destroy()
            except Exception:
                pass
        try:
            self.frame.destroy()
        except Exception:
            pass
