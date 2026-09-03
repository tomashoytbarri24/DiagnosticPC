"""Vista avanzada de memoria RAM de CorePulse.

Combina dos fuentes separadas y explícitas:
- Windows/SMBIOS para módulos físicos y slots.
- Snapshot certificado de CorePulse para uso físico en tiempo real.

La vista no consulta hardware desde el hilo Tk y respeta REAL_OR_NA.
"""
from __future__ import annotations
from core.theme_manager import color as theme_color

import threading
import time

import customtkinter as ctk

from core.device_identity import collect_ram_identity
from gui.internal_navigation import show_dashboard
from gui.stable_scroll import StableScrollHost

BG = theme_color('#06111f')
CARD = theme_color('#0d1828')
CARD_2 = theme_color('#0a1524')
BORDER = theme_color('#1b3048')
TEXT = theme_color('#f4f7fb')
TEXT_2 = theme_color('#b8c4d4')
MUTED = theme_color('#7f91a8')
GREEN = '#1fd18b'
CYAN = '#14b8ff'
AMBER = '#f59e0b'
FONT = 'Segoe UI'


def _num(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except Exception:
        return None


def _fmt(value, digits=2, suffix=''):
    number = _num(value)
    if number is None:
        return 'N/A'
    return f'{number:.{digits}f}{suffix}'


def _fmt_int(value, suffix=''):
    number = _num(value)
    if number is None:
        return 'N/A'
    return f'{int(number)}{suffix}'


def _age_text(timestamp):
    try:
        age = max(0.0, time.time() - float(timestamp))
    except Exception:
        return 'N/A'
    if age < 1:
        return '< 1 s'
    if age < 60:
        return f'{age:.1f} s'
    return f'{age / 60.0:.1f} min'


def _safe_text(value):
    text = str(value or '').strip()
    return text if text else 'N/A'


class RAMDetailPanel:
    """Panel de módulos RAM y memoria física utilizable en tiempo real."""

    def __init__(self, app, host):
        self.app = app
        self.host = host
        self._alive = True
        self._after_id = None
        self._identity = None
        self._identity_loading = False
        self._identity_applied_signature = None
        self._module_signature = None
        self._scroll_active_until = 0.0
        self._scroll_watch_after_id = None
        self._last_scroll_view = None
        self._inventory_labels = {}
        self._runtime_labels = {}
        self._build()
        self._start_identity_load()
        self.refresh()

    def widget(self):
        return self.frame

    def _build(self):
        self.frame = ctk.CTkFrame(self.host, fg_color=BG, corner_radius=0)
        self.frame.pack(fill='both', expand=True)

        header = ctk.CTkFrame(self.frame, fg_color='transparent')
        header.pack(fill='x', padx=18, pady=(15, 8))
        ctk.CTkButton(
            header,
            text='Volver al resumen',
            width=145,
            height=31,
            fg_color='transparent',
            hover_color=theme_color(theme_color('#102840')),
            border_width=1,
            border_color=theme_color(theme_color('#214765')),
            text_color=TEXT_2,
            font=(FONT, 9, 'bold'),
            corner_radius=8,
            command=lambda: show_dashboard(self.app),
        ).pack(side='left')

        titles = ctk.CTkFrame(header, fg_color='transparent')
        titles.pack(side='left', fill='x', expand=True, padx=14)
        self.lbl_title = ctk.CTkLabel(
            titles,
            text='Memoria RAM',
            font=(FONT, 19, 'bold'),
            text_color=TEXT,
            anchor='w',
        )
        self.lbl_title.pack(anchor='w')
        ctk.CTkLabel(
            titles,
            text='Inventario Windows/SMBIOS + uso físico real en tiempo real',
            font=(FONT, 10),
            text_color=TEXT_2,
            anchor='w',
        ).pack(anchor='w', pady=(1, 0))
        self.lbl_freshness = ctk.CTkLabel(
            header,
            text='Actualización: N/A',
            font=(FONT, 9, 'bold'),
            text_color=MUTED,
        )
        self.lbl_freshness.pack(side='right', padx=(8, 0))

        self.summary_row = ctk.CTkFrame(self.frame, fg_color='transparent')
        self.summary_row.pack(fill='x', padx=18, pady=(2, 9))
        self.usage_card, self.usage_value, self.usage_detail = self._summary_card('USO', 'N/A', 'Memoria física', GREEN)
        self.used_card, self.used_value, self.used_detail = self._summary_card('EN USO', 'N/A', 'Memoria utilizada', GREEN)
        self.available_card, self.available_value, self.available_detail = self._summary_card('DISPONIBLE', 'N/A', 'Memoria disponible', CYAN)
        self.total_card, self.total_value, self.total_detail = self._summary_card('TOTAL', 'N/A', 'Utilizable por Windows', CYAN)
        for index, card in enumerate((self.usage_card, self.used_card, self.available_card, self.total_card)):
            card.pack(side='left', fill='both', expand=True, padx=(0 if index == 0 else 5, 0 if index == 3 else 5))

        self.body_scroll = StableScrollHost(self.frame, fg_color=BG)
        self.body_scroll.pack(fill='both', expand=True, padx=13, pady=(0, 10))
        self.body = self.body_scroll.content

        overview = ctk.CTkFrame(self.body, fg_color='transparent')
        overview.pack(fill='x', padx=5, pady=(0, 8))
        overview.grid_columnconfigure(0, weight=1)
        overview.grid_columnconfigure(1, weight=1)

        inventory = self._section_card(
            overview,
            'CONFIGURACIÓN DE MEMORIA',
            'Módulos y slots reportados por Windows / SMBIOS',
        )
        inventory.grid(row=0, column=0, sticky='nsew', padx=(0, 5))
        runtime = self._section_card(
            overview,
            'MEMORIA FÍSICA EN TIEMPO REAL',
            'Valores del snapshot certificado de CorePulse',
        )
        runtime.grid(row=0, column=1, sticky='nsew', padx=(5, 0))

        for key, label in (
            ('installed', 'Capacidad instalada (módulos)'),
            ('modules', 'Módulos detectados'),
            ('slots_total', 'Slots reportados'),
            ('slots_available', 'Slots disponibles'),
            ('types', 'Tipo de memoria detectado'),
            ('source', 'Fuente de inventario'),
        ):
            self._add_row(inventory, self._inventory_labels, key, label)

        for key, label in (
            ('usage', 'Uso físico'),
            ('used', 'Memoria en uso'),
            ('available', 'Memoria disponible'),
            ('total', 'Total utilizable por Windows'),
            ('snapshot', 'Frescura del snapshot'),
            ('source', 'Fuente de telemetría'),
        ):
            self._add_row(runtime, self._runtime_labels, key, label)

        self.modules_card = ctk.CTkFrame(
            self.body,
            fg_color=CARD,
            border_width=1,
            border_color=BORDER,
            corner_radius=12,
        )
        self.modules_card.pack(fill='x', padx=5, pady=(0, 8))
        modules_header = ctk.CTkFrame(self.modules_card, fg_color='transparent')
        modules_header.pack(fill='x', padx=14, pady=(10, 5))
        ctk.CTkLabel(
            modules_header,
            text='MÓDULOS FÍSICOS DETECTADOS',
            font=(FONT, 10, 'bold'),
            text_color=TEXT_2,
        ).pack(side='left')
        self.lbl_module_count = ctk.CTkLabel(
            modules_header,
            text='Cargando inventario',
            font=(FONT, 8, 'bold'),
            text_color=MUTED,
        )
        self.lbl_module_count.pack(side='right')

        self.module_rows = ctk.CTkFrame(self.modules_card, fg_color='transparent')
        self.module_rows.pack(fill='x', padx=10, pady=(0, 10))
        self.lbl_no_modules = ctk.CTkLabel(
            self.module_rows,
            text='Windows/SMBIOS no ha expuesto módulos individuales todavía.',
            font=(FONT, 9),
            text_color=MUTED,
            anchor='w',
        )
        self.lbl_no_modules.pack(fill='x', padx=8, pady=14)

        note = ctk.CTkFrame(self.body, fg_color=CARD_2, border_width=1, border_color=BORDER, corner_radius=10)
        note.pack(fill='x', padx=5, pady=(0, 7))
        ctk.CTkLabel(
            note,
            text='LECTURA UNIVERSAL',
            font=(FONT, 9, 'bold'),
            text_color=GREEN,
        ).pack(anchor='w', padx=12, pady=(9, 2))
        ctk.CTkLabel(
            note,
            text=(
                'CorePulse no deduce canal Single/Dual, timings CAS, XMP/EXPO ni perfiles SPD cuando Windows no los expone. '
                'La capacidad instalada puede ser ligeramente mayor que la memoria utilizable por Windows debido a memoria reservada por hardware.'
            ),
            font=(FONT, 8),
            text_color=MUTED,
            justify='left',
            anchor='w',
            wraplength=1150,
        ).pack(fill='x', padx=12, pady=(0, 9))

        footer = ctk.CTkFrame(self.body, fg_color='transparent')
        footer.pack(fill='x', padx=8, pady=(0, 6))
        ctk.CTkLabel(
            footer,
            text='CorePulse muestra datos reales o N/A. Los slots disponibles sólo se calculan desde contadores WMI reales.',
            font=(FONT, 8),
            text_color=MUTED,
            anchor='w',
        ).pack(side='left')
        self.lbl_identity_source = ctk.CTkLabel(
            footer,
            text='Inventario RAM: cargando…',
            font=(FONT, 8, 'bold'),
            text_color=MUTED,
            anchor='e',
        )
        self.lbl_identity_source.pack(side='right')

    def _summary_card(self, title, value, detail, accent):
        card = ctk.CTkFrame(
            self.summary_row,
            fg_color=CARD,
            border_width=1,
            border_color=BORDER,
            corner_radius=12,
            height=92,
        )
        card.pack_propagate(False)
        ctk.CTkLabel(card, text=title, font=(FONT, 9, 'bold'), text_color=TEXT_2).pack(anchor='w', padx=12, pady=(9, 0))
        value_label = ctk.CTkLabel(card, text=value, font=(FONT, 20, 'bold'), text_color=accent)
        value_label.pack(anchor='w', padx=12)
        detail_label = ctk.CTkLabel(card, text=detail, font=(FONT, 8), text_color=MUTED)
        detail_label.pack(anchor='w', padx=12, pady=(0, 7))
        return card, value_label, detail_label

    def _section_card(self, parent, title, subtitle):
        card = ctk.CTkFrame(parent, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=12)
        ctk.CTkLabel(card, text=title, font=(FONT, 10, 'bold'), text_color=TEXT_2).pack(anchor='w', padx=14, pady=(11, 0))
        ctk.CTkLabel(card, text=subtitle, font=(FONT, 8), text_color=MUTED).pack(anchor='w', padx=14, pady=(1, 7))
        return card

    def _add_row(self, parent, target, key, label):
        row = ctk.CTkFrame(parent, fg_color='transparent', height=35)
        row.pack(fill='x', padx=12, pady=1)
        row.pack_propagate(False)
        ctk.CTkLabel(row, text=label, width=190, font=(FONT, 9), text_color=MUTED, anchor='w').pack(side='left')
        value = ctk.CTkLabel(row, text='N/A', font=(FONT, 9, 'bold'), text_color=TEXT, anchor='w')
        value.pack(side='left', fill='x', expand=True, padx=(8, 0))
        target[key] = value

    def _scroll_canvas(self):
        return getattr(getattr(self, 'body_scroll', None), 'canvas', None)

    def _start_scroll_watch(self):
        # Compatibilidad con builds anteriores: StableScrollHost administra la
        # rueda, scrollbar e inercia sin un polling de 60 ms por página.
        return None

    def _is_scrolling(self):
        host = getattr(self, 'body_scroll', None)
        return bool(host is not None and host.is_scrolling())

    def _start_identity_load(self):
        if self._identity_loading or self._identity is not None:
            return
        self._identity_loading = True

        def worker():
            try:
                result = collect_ram_identity()
            except Exception:
                result = {}
            self._identity = result if isinstance(result, dict) else {}
            self._identity_loading = False

        threading.Thread(target=worker, name='CorePulseRAMIdentity', daemon=True).start()

    def _apply_identity(self):
        identity = self._identity
        if identity is None:
            self.lbl_identity_source.configure(text='Inventario RAM: cargando…', text_color=MUTED)
            return
        try:
            signature = repr(identity)
        except Exception:
            signature = str(id(identity))
        if signature == self._identity_applied_signature:
            return

        installed = identity.get('installed_capacity_gb')
        module_count = identity.get('module_count')
        slots_total = identity.get('slots_total')
        slots_available = identity.get('slots_available')
        types = identity.get('memory_types') if isinstance(identity.get('memory_types'), list) else []
        source = str(identity.get('source') or 'N/A')

        self._inventory_labels['installed'].configure(text=_fmt(installed, 2, ' GB'))
        self._inventory_labels['modules'].configure(text=_fmt_int(module_count))
        self._inventory_labels['slots_total'].configure(text=_fmt_int(slots_total))
        available_text = _fmt_int(slots_available)
        if available_text != 'N/A':
            available_text += ' · derivado de inventario WMI'
        self._inventory_labels['slots_available'].configure(text=available_text, text_color=GREEN if _num(slots_available) is not None else TEXT)
        self._inventory_labels['types'].configure(text=' / '.join(types) if types else 'N/A')
        self._inventory_labels['source'].configure(text=source.replace('Win32_', 'Windows / '))
        self.lbl_identity_source.configure(
            text=f'Inventario RAM: {source}' if source != 'N/A' else 'Inventario RAM: N/A',
            text_color=GREEN if source != 'N/A' else MUTED,
        )
        modules = identity.get('modules') if isinstance(identity.get('modules'), list) else []
        self._rebuild_modules(modules)
        self._identity_applied_signature = signature

    def _rebuild_modules(self, modules):
        try:
            signature = tuple(
                (
                    str(m.get('slot') or ''), str(m.get('bank') or ''), _num(m.get('capacity_gb')),
                    str(m.get('part_number') or ''), _num(m.get('configured_speed_mhz')),
                )
                for m in modules if isinstance(m, dict)
            )
        except Exception:
            signature = ()
        if signature == self._module_signature:
            return
        for child in list(self.module_rows.winfo_children()):
            try:
                child.destroy()
            except Exception:
                pass

        valid = [m for m in modules if isinstance(m, dict)]
        if not valid:
            self.lbl_no_modules = ctk.CTkLabel(
                self.module_rows,
                text='Windows/SMBIOS no expone módulos físicos individuales en este equipo.',
                font=(FONT, 9),
                text_color=MUTED,
                anchor='w',
            )
            self.lbl_no_modules.pack(fill='x', padx=8, pady=14)
            self.lbl_module_count.configure(text='0 módulos detectados', text_color=MUTED)
            self._module_signature = signature
            return

        self.lbl_module_count.configure(text=f'{len(valid)} módulo' + ('' if len(valid) == 1 else 's') + ' detectado' + ('' if len(valid) == 1 else 's'), text_color=GREEN)
        for index, module in enumerate(valid, start=1):
            self._build_module_card(index, module)
        self._module_signature = signature

    def _build_module_card(self, index, module):
        card = ctk.CTkFrame(self.module_rows, fg_color=CARD_2, border_width=1, border_color=BORDER, corner_radius=9)
        card.pack(fill='x', pady=4)
        header = ctk.CTkFrame(card, fg_color='transparent')
        header.pack(fill='x', padx=12, pady=(8, 4))
        slot = _safe_text(module.get('slot'))
        bank = _safe_text(module.get('bank'))
        location = slot if slot != 'N/A' else bank
        ctk.CTkLabel(
            header,
            text=f'MÓDULO {index} · {location}',
            font=(FONT, 10, 'bold'),
            text_color=TEXT,
        ).pack(side='left')
        ctk.CTkLabel(
            header,
            text=_fmt(module.get('capacity_gb'), 2, ' GB'),
            font=(FONT, 11, 'bold'),
            text_color=GREEN,
        ).pack(side='right')

        grid = ctk.CTkFrame(card, fg_color='transparent')
        grid.pack(fill='x', padx=12, pady=(0, 9))
        grid.grid_columnconfigure(0, weight=1)
        grid.grid_columnconfigure(1, weight=1)
        rows = [
            ('Banco', bank, 'Fabricante', _safe_text(module.get('manufacturer'))),
            ('Part number', _safe_text(module.get('part_number')), 'Tipo SMBIOS', _safe_text(module.get('memory_type'))),
            ('Formato', _safe_text(module.get('form_factor')), 'Velocidad configurada', _fmt(module.get('configured_speed_mhz'), 0, ' MHz')),
            ('Velocidad reportada', _fmt(module.get('speed_mhz'), 0, ' MHz'), 'Ancho de datos', _fmt_int(module.get('data_width_bits'), ' bits')),
            ('Ancho total', _fmt_int(module.get('total_width_bits'), ' bits'), 'Voltaje configurado', _fmt(module.get('configured_voltage_v'), 3, ' V')),
        ]
        for row_index, (l1, v1, l2, v2) in enumerate(rows):
            self._module_field(grid, row_index, 0, l1, v1)
            self._module_field(grid, row_index, 1, l2, v2)

    def _module_field(self, parent, row, column, label, value):
        box = ctk.CTkFrame(parent, fg_color='transparent')
        box.grid(row=row, column=column, sticky='ew', padx=(0 if column == 0 else 8, 8 if column == 0 else 0), pady=2)
        ctk.CTkLabel(box, text=label, width=130, font=(FONT, 8), text_color=MUTED, anchor='w').pack(side='left')
        ctk.CTkLabel(box, text=value, font=(FONT, 9, 'bold'), text_color=TEXT, anchor='w').pack(side='left', fill='x', expand=True, padx=(6, 0))

    def refresh(self):
        if not self._alive:
            return
        if self._after_id is not None:
            try:
                self.frame.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        try:
            telemetry = getattr(self.app, 'latest_telemetry', None)
            if not isinstance(telemetry, dict):
                telemetry = {}
            stamp = telemetry.get('_snapshot_timestamp') or telemetry.get('timestamp')
            usage = telemetry.get('ram_usage')
            used = telemetry.get('ram_used_gb')
            available = telemetry.get('ram_available_gb')
            total = telemetry.get('ram_total_gb')

            self.usage_value.configure(text=_fmt(usage, 1, '%'), text_color=GREEN if _num(usage) is not None else MUTED)
            self.used_value.configure(text=_fmt(used, 2, ' GB'), text_color=GREEN if _num(used) is not None else MUTED)
            self.available_value.configure(text=_fmt(available, 2, ' GB'), text_color=CYAN if _num(available) is not None else MUTED)
            self.total_value.configure(text=_fmt(total, 2, ' GB'), text_color=CYAN if _num(total) is not None else MUTED)
            self.lbl_freshness.configure(text=f'Actualización: {_age_text(stamp)}')

            if not self._is_scrolling():
                self._apply_identity()
                self._runtime_labels['usage'].configure(text=_fmt(usage, 1, '%'))
                self._runtime_labels['used'].configure(text=_fmt(used, 2, ' GB'))
                self._runtime_labels['available'].configure(text=_fmt(available, 2, ' GB'))
                self._runtime_labels['total'].configure(text=_fmt(total, 2, ' GB'))
                self._runtime_labels['snapshot'].configure(text=_age_text(stamp), text_color=GREEN if stamp is not None else MUTED)
                self._runtime_labels['source'].configure(text='psutil.virtual_memory · snapshot certificado')
        except Exception:
            pass

        if self._alive:
            try:
                self._after_id = self.frame.after(850, self.refresh)
            except Exception:
                self._after_id = None
