"""Vista avanzada multi-GPU de CorePulse.

Presenta inventario real de Windows y sensores certificados ya contenidos en el
snapshot de telemetría. La interfaz no consulta hardware directamente y conserva
la política REAL_OR_NA.
"""
from __future__ import annotations
from core.theme_manager import color as theme_color
from core.runtime_logging import get_logger

import re
import time

import customtkinter as ctk

from gui.internal_navigation import show_dashboard
from gui.stable_scroll import StableScrollHost
from core.gpu_display_logic import (
    active_display_on_other_gpu,
    human_gpu_hardware_type,
    windows_status_text,
    wmi_vram_presentation,
)

BG = theme_color('#06111f')
CARD = theme_color('#0d1828')
CARD_2 = theme_color('#0a1524')
BORDER = theme_color('#1b3048')
TEXT = theme_color('#f4f7fb')
TEXT_2 = theme_color('#b8c4d4')
MUTED = theme_color('#7f91a8')
CYAN = '#14b8ff'
GREEN = '#1fd18b'
AMBER = '#f59e0b'
RED = '#ef4444'
PURPLE = '#a064ff'
FONT = 'Segoe UI'
logger = get_logger('gpu_detail_panel')

TYPE_LABELS = {
    'temperature': 'TEMPERATURA', 'clock': 'RELOJ', 'load': 'CARGA',
    'power': 'POTENCIA', 'voltage': 'VOLTAJE', 'current': 'CORRIENTE',
    'fan': 'VENTILADOR', 'control': 'CONTROL', 'smalldata': 'MEMORIA',
    'throughput': 'TRANSFERENCIA',
}
TYPE_COLORS = {
    'temperature': AMBER, 'clock': CYAN, 'load': GREEN, 'power': PURPLE,
    'voltage': CYAN, 'current': TEXT_2, 'fan': CYAN, 'control': GREEN,
    'smalldata': PURPLE, 'throughput': TEXT_2,
}


def _num(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except Exception:
        return None


def _fmt(value, digits=1, suffix=''):
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


def _thermal_color(value):
    number = _num(value)
    if number is None:
        return MUTED
    if number < 70:
        return GREEN
    if number < 85:
        return AMBER
    return RED


def _norm(value):
    text = str(value or '').lower()
    text = re.sub(r'\(r\)|\(tm\)|[™®]', ' ', text)
    text = re.sub(r'[^a-z0-9]+', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def _display_sensor_value(sensor):
    value = _num((sensor or {}).get('value'))
    if value is None:
        return 'N/A'
    kind = str((sensor or {}).get('type') or '').lower()
    unit = str((sensor or {}).get('unit') or '').strip()
    digits = 4 if kind == 'voltage' else 2 if kind in {'power', 'current', 'throughput'} else 1
    return f'{value:.{digits}f} {unit}'.strip()


def _sensor_value_color(sensor):
    kind = str((sensor or {}).get('type') or '').lower()
    if kind == 'temperature':
        return _thermal_color((sensor or {}).get('value'))
    return TYPE_COLORS.get(kind, TEXT_2)


def _gb_from_mb(value):
    number = _num(value)
    return None if number is None else number / 1024.0


def _gb_from_bytes(value):
    number = _num(value)
    return None if number is None else number / (1024.0 ** 3)


class GPUDetailPanel:
    """Panel avanzado que mantiene cada adaptador GPU separado por identidad real."""

    def __init__(self, app, host):
        self.app = app
        self.host = host
        self._alive = True
        self._after_id = None
        self._selected_index = None
        self._selected_name = None
        self._selector_signature = None
        self._selector_buttons = []
        self._spec_labels = {}
        self._advanced_labels = {}
        self._sensor_widgets = {}
        self._scroll_active_until = 0.0
        self._scroll_watch_after_id = None
        self._last_scroll_view = None
        self._last_refresh_error_log_at = 0.0
        self._build()
        self.refresh()

    def widget(self):
        return self.frame

    def _build(self):
        self.frame = ctk.CTkFrame(self.host, fg_color=BG, corner_radius=0)
        self.frame.pack(fill='both', expand=True)

        header = ctk.CTkFrame(self.frame, fg_color='transparent')
        header.pack(fill='x', padx=18, pady=(15, 8))
        ctk.CTkButton(
            header, text='Volver al resumen', width=145, height=31,
            fg_color='transparent', hover_color=theme_color(theme_color('#102840')), border_width=1,
            border_color=theme_color(theme_color('#214765')), text_color=TEXT_2, font=(FONT, 9, 'bold'),
            corner_radius=8, command=lambda: show_dashboard(self.app),
        ).pack(side='left')

        titles = ctk.CTkFrame(header, fg_color='transparent')
        titles.pack(side='left', fill='x', expand=True, padx=14)
        self.lbl_title = ctk.CTkLabel(titles, text='Detalles avanzados de GPU', font=(FONT, 19, 'bold'), text_color=TEXT, anchor='w')
        self.lbl_title.pack(anchor='w')
        self.lbl_subtitle = ctk.CTkLabel(titles, text='Inventario de Windows + sensores reales en tiempo real', font=(FONT, 10), text_color=TEXT_2, anchor='w')
        self.lbl_subtitle.pack(anchor='w', pady=(1, 0))
        self.lbl_freshness = ctk.CTkLabel(header, text='Actualización: N/A', font=(FONT, 9, 'bold'), text_color=MUTED)
        self.lbl_freshness.pack(side='right', padx=(8, 0))

        self.selector = ctk.CTkFrame(self.frame, fg_color='transparent')
        self.selector.pack(fill='x', padx=18, pady=(0, 8))

        self.summary_row = ctk.CTkFrame(self.frame, fg_color='transparent')
        self.summary_row.pack(fill='x', padx=18, pady=(0, 9))
        self.usage_card, self.usage_value, self.usage_detail = self._summary_card('USO', 'N/A', 'Carga GPU', PURPLE)
        self.temp_card, self.temp_value, self.temp_detail = self._summary_card('TEMPERATURA', 'N/A', 'GPU Core', GREEN)
        self.vram_card, self.vram_value, self.vram_detail = self._summary_card('VRAM', 'N/A', 'Memoria dedicada', CYAN)
        self.power_card, self.power_value, self.power_detail = self._summary_card('POTENCIA', 'N/A', 'GPU Package', PURPLE)
        for index, card in enumerate((self.usage_card, self.temp_card, self.vram_card, self.power_card)):
            card.pack(side='left', fill='both', expand=True, padx=(0 if index == 0 else 5, 0 if index == 3 else 5))

        self.body_scroll = StableScrollHost(self.frame, fg_color=BG)
        self.body_scroll.pack(fill='both', expand=True, padx=13, pady=(0, 10))
        self.body = self.body_scroll.content

        overview = ctk.CTkFrame(self.body, fg_color='transparent')
        overview.pack(fill='x', padx=5, pady=(0, 8))
        overview.grid_columnconfigure(0, weight=1)
        overview.grid_columnconfigure(1, weight=1)

        specs = self._section_card(overview, 'IDENTIDAD Y CONTROLADOR', 'Datos expuestos por Windows / Win32_VideoController')
        specs.grid(row=0, column=0, sticky='nsew', padx=(0, 5))
        advanced = self._section_card(overview, 'LECTURAS AVANZADAS', 'Sólo valores que el adaptador realmente expone')
        advanced.grid(row=0, column=1, sticky='nsew', padx=(5, 0))

        for key, label in (
            ('vendor', 'Fabricante reportado'), ('video_processor', 'Procesador de vídeo'),
            ('driver', 'Versión del controlador'), ('windows_status', 'Estado del dispositivo'),
            ('wmi_vram', 'VRAM según Windows (WMI)'), ('resolution', 'Resolución asociada'),
            ('refresh_rate', 'Frecuencia asociada'), ('hardware_type', 'Familia de sensores'),
            ('pnp_id', 'PNP Device ID'), ('inventory_source', 'Fuentes de inventario'),
        ):
            self._add_spec_row(specs, key, label)

        for key, label in (
            ('hotspot', 'GPU Hot Spot'), ('core_clock', 'Clock del núcleo'),
            ('memory_clock', 'Clock de memoria'), ('memory_load', 'Carga de memoria'),
            ('vram_used', 'VRAM utilizada'), ('vram_total', 'VRAM total sensor'),
            ('fan_rpm', 'Ventilador'), ('fan_control', 'Control ventilador'),
            ('voltage', 'Voltaje de núcleo'), ('power', 'Potencia GPU'),
            ('sensor_count', 'Sensores GPU visibles'), ('provider', 'Proveedor'),
        ):
            self._add_advanced_row(advanced, key, label)

        sensor_card = ctk.CTkFrame(self.body, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=12)
        sensor_card.pack(fill='x', padx=5, pady=(0, 8))
        sensor_header = ctk.CTkFrame(sensor_card, fg_color='transparent')
        sensor_header.pack(fill='x', padx=14, pady=(10, 5))
        ctk.CTkLabel(sensor_header, text='SENSORES DE GPU EN TIEMPO REAL', font=(FONT, 10, 'bold'), text_color=TEXT_2).pack(side='left')
        self.lbl_sensor_status = ctk.CTkLabel(sensor_header, text='Esperando telemetría', font=(FONT, 8, 'bold'), text_color=MUTED)
        self.lbl_sensor_status.pack(side='right')

        headings = ctk.CTkFrame(sensor_card, fg_color=CARD_2, height=28, corner_radius=6)
        headings.pack(fill='x', padx=10, pady=(0, 4))
        headings.pack_propagate(False)
        for text, width in [('TIPO', 120), ('SENSOR', 330), ('VALOR', 130), ('ORIGEN', 210), ('FRESCURA', 90)]:
            ctk.CTkLabel(headings, text=text, width=width, font=(FONT, 8, 'bold'), text_color=MUTED, anchor='w').pack(side='left', padx=(8, 0))

        self.sensor_rows = ctk.CTkFrame(sensor_card, fg_color='transparent')
        self.sensor_rows.pack(fill='x', padx=10, pady=(0, 9))
        self.lbl_no_sensors = ctk.CTkLabel(self.sensor_rows, text='No hay sensores GPU expuestos para este adaptador.', font=(FONT, 9), text_color=MUTED, anchor='w')
        self.lbl_no_sensors.pack(fill='x', padx=8, pady=12)

        footer = ctk.CTkFrame(self.body, fg_color='transparent')
        footer.pack(fill='x', padx=8, pady=(0, 6))
        ctk.CTkLabel(footer, text='CorePulse muestra datos reales o N/A. No deriva VRAM usada, potencia, clocks, ventilador ni voltaje ausentes.', font=(FONT, 8), text_color=MUTED, anchor='w').pack(side='left')
        self.lbl_identity_source = ctk.CTkLabel(footer, text='Inventario GPU: esperando snapshot', font=(FONT, 8, 'bold'), text_color=MUTED, anchor='e')
        self.lbl_identity_source.pack(side='right')

    def _summary_card(self, title, value, detail, accent):
        card = ctk.CTkFrame(self.summary_row, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=12, height=92)
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

    def _add_spec_row(self, parent, key, label):
        row = ctk.CTkFrame(parent, fg_color='transparent', height=30)
        row.pack(fill='x', padx=14, pady=1)
        row.pack_propagate(False)
        ctk.CTkLabel(row, text=label, width=175, font=(FONT, 9), text_color=MUTED, anchor='w').pack(side='left')
        value = ctk.CTkLabel(row, text='N/A', font=(FONT, 9, 'bold'), text_color=TEXT, anchor='w')
        value.pack(side='left', fill='x', expand=True)
        self._spec_labels[key] = value

    def _add_advanced_row(self, parent, key, label):
        row = ctk.CTkFrame(parent, fg_color='transparent', height=30)
        row.pack(fill='x', padx=14, pady=1)
        row.pack_propagate(False)
        ctk.CTkLabel(row, text=label, width=170, font=(FONT, 9), text_color=MUTED, anchor='w').pack(side='left')
        value = ctk.CTkLabel(row, text='N/A', font=(FONT, 9, 'bold'), text_color=TEXT, anchor='w')
        value.pack(side='left', fill='x', expand=True)
        self._advanced_labels[key] = value

    def _scroll_canvas(self):
        return getattr(getattr(self, 'body_scroll', None), 'canvas', None)

    def _start_scroll_watch(self):
        # Compatibilidad con builds anteriores: StableScrollHost administra la
        # rueda, scrollbar e inercia sin un polling de 60 ms por página.
        return None

    def _is_scrolling(self):
        host = getattr(self, 'body_scroll', None)
        return bool(host is not None and host.is_scrolling())

    @staticmethod
    def _sensor_sort_key(sensor):
        order = {'load': 0, 'temperature': 1, 'clock': 2, 'smalldata': 3, 'power': 4, 'fan': 5, 'control': 6, 'voltage': 7, 'current': 8, 'throughput': 9}
        kind = str((sensor or {}).get('type') or '').lower()
        return (order.get(kind, 20), str((sensor or {}).get('name') or '').lower(), str((sensor or {}).get('identifier') or '').lower())

    def _gpu_list(self, telemetry):
        inventory = telemetry.get('_gpu_inventory') if isinstance(telemetry.get('_gpu_inventory'), list) else None
        if inventory is not None:
            return [gpu for gpu in inventory if isinstance(gpu, dict)]
        raw = telemetry.get('_gpus') if isinstance(telemetry.get('_gpus'), list) else []
        return [gpu for gpu in raw if isinstance(gpu, dict)]

    def _select_initial_index(self, telemetry, gpus):
        if not gpus:
            self._selected_index = None
            self._selected_name = None
            return
        if self._selected_name:
            wanted = _norm(self._selected_name)
            for index, gpu in enumerate(gpus):
                if _norm(gpu.get('name')) == wanted:
                    self._selected_index = index
                    return
        primary = _norm(telemetry.get('gpu_name'))
        if self._selected_index is None and primary:
            for index, gpu in enumerate(gpus):
                if _norm(gpu.get('name')) == primary:
                    self._selected_index = index
                    self._selected_name = gpu.get('name')
                    return
        if self._selected_index is None or self._selected_index >= len(gpus):
            self._selected_index = 0
        self._selected_name = gpus[self._selected_index].get('name')

    def _select_gpu(self, index):
        try:
            self._selected_index = int(index)
        except Exception:
            self._selected_index = 0
        telemetry = getattr(self.app, 'latest_telemetry', {}) or {}
        gpus = self._gpu_list(telemetry) if isinstance(telemetry, dict) else []
        if 0 <= self._selected_index < len(gpus):
            self._selected_name = gpus[self._selected_index].get('name')
        self._selector_signature = None
        self.refresh()

    def _update_selector(self, gpus):
        signature = tuple(str(gpu.get('name') or f'GPU {i}') for i, gpu in enumerate(gpus))
        selected = self._selected_index
        if signature == self._selector_signature:
            for i, button in enumerate(self._selector_buttons):
                try:
                    active = i == selected
                    button.configure(fg_color=theme_color(theme_color('#173550')) if active else theme_color('#0d1828'), border_color=theme_color('#2b668f') if active else BORDER, text_color=CYAN if active else TEXT_2)
                except Exception:
                    pass
            return
        for child in self.selector.winfo_children():
            try:
                child.destroy()
            except Exception:
                pass
        self._selector_buttons = []
        if not gpus:
            ctk.CTkLabel(self.selector, text='No se detectaron adaptadores GPU físicos.', font=(FONT, 9, 'bold'), text_color=MUTED).pack(side='left')
            self._selector_signature = signature
            return
        ctk.CTkLabel(self.selector, text='ADAPTADORES', font=(FONT, 8, 'bold'), text_color=MUTED).pack(side='left', padx=(0, 8))
        for i, gpu in enumerate(gpus):
            active = i == selected
            label = str(gpu.get('name') or f'GPU {i}')
            if len(label) > 38:
                label = label[:35] + '…'
            button = ctk.CTkButton(
                self.selector, text=f'GPU {i} · {label}', height=28, width=170,
                fg_color=theme_color(theme_color('#173550')) if active else theme_color('#0d1828'), hover_color=theme_color('#164f7d'),
                border_width=1, border_color=theme_color('#2b668f') if active else BORDER,
                text_color=CYAN if active else TEXT_2, font=(FONT, 8, 'bold'), corner_radius=7,
                command=lambda gpu_index=i: self._select_gpu(gpu_index),
            )
            button.pack(side='left', padx=(0, 6))
            self._selector_buttons.append(button)
        self._selector_signature = signature

    def _update_sensor_rows(self, sensors):
        if self._is_scrolling():
            return
        valid = [sensor for sensor in sensors if isinstance(sensor, dict) and _num(sensor.get('value')) is not None]
        valid = sorted(valid, key=self._sensor_sort_key)
        if valid and self.lbl_no_sensors.winfo_manager():
            self.lbl_no_sensors.pack_forget()
        keys = []
        for sensor in valid:
            key = (str(sensor.get('type') or ''), str(sensor.get('identifier') or sensor.get('name') or ''))
            keys.append(key)
            widgets = self._sensor_widgets.get(key)
            if widgets is None:
                row = ctk.CTkFrame(self.sensor_rows, fg_color='transparent', height=30)
                row.pack(fill='x', pady=1)
                row.pack_propagate(False)
                type_lbl = ctk.CTkLabel(row, width=120, font=(FONT, 8, 'bold'), anchor='w')
                type_lbl.pack(side='left', padx=(8, 0))
                name_lbl = ctk.CTkLabel(row, width=330, font=(FONT, 9), text_color=TEXT, anchor='w')
                name_lbl.pack(side='left', padx=(8, 0))
                value_lbl = ctk.CTkLabel(row, width=130, font=(FONT, 9, 'bold'), anchor='w')
                value_lbl.pack(side='left', padx=(8, 0))
                source_lbl = ctk.CTkLabel(row, width=210, font=(FONT, 8), text_color=MUTED, anchor='w')
                source_lbl.pack(side='left', padx=(8, 0))
                age_lbl = ctk.CTkLabel(row, width=90, font=(FONT, 8), text_color=MUTED, anchor='w')
                age_lbl.pack(side='left', padx=(8, 0))
                widgets = (row, type_lbl, name_lbl, value_lbl, source_lbl, age_lbl)
                self._sensor_widgets[key] = widgets
            _, type_lbl, name_lbl, value_lbl, source_lbl, age_lbl = widgets
            kind = str(sensor.get('type') or '').lower()
            type_lbl.configure(text=TYPE_LABELS.get(kind, kind.upper() or 'SENSOR'), text_color=TYPE_COLORS.get(kind, CYAN))
            name_lbl.configure(text=str(sensor.get('name') or 'Sensor'))
            value_lbl.configure(text=_display_sensor_value(sensor), text_color=_sensor_value_color(sensor))
            source_lbl.configure(text=str(sensor.get('source') or 'N/A').replace('LibreHardwareMonitorLib', 'LibreHardwareMonitor'))
            age_lbl.configure(text=_age_text(sensor.get('timestamp')))
        active = set(keys)
        for key in list(self._sensor_widgets):
            if key in active:
                continue
            row = self._sensor_widgets.pop(key)[0]
            try:
                row.destroy()
            except Exception:
                pass
        if not valid and not self.lbl_no_sensors.winfo_manager():
            self.lbl_no_sensors.pack(fill='x', padx=8, pady=12)
        self.lbl_sensor_status.configure(text=f'{len(valid)} sensores válidos' if valid else 'Sin sensores disponibles', text_color=GREEN if valid else MUTED)

    def _apply_static_rows(self, gpu, all_gpus):
        os_inv = gpu.get('os_inventory') if isinstance(gpu.get('os_inventory'), dict) else {}
        self._spec_labels['vendor'].configure(text=str(os_inv.get('vendor') or 'N/A'))
        self._spec_labels['video_processor'].configure(text=str(os_inv.get('video_processor') or 'N/A'))
        self._spec_labels['driver'].configure(text=str(os_inv.get('driver_version') or 'N/A'))
        self._spec_labels['windows_status'].configure(text=windows_status_text(os_inv.get('os_status')))

        wmi_vram_text, wmi_limited = wmi_vram_presentation(
            os_inv.get('adapter_ram_bytes_os'), gpu.get('memory_total_mb')
        )
        wmi_vram_color = MUTED if wmi_vram_text == 'N/A' else AMBER if wmi_limited else TEXT
        self._spec_labels['wmi_vram'].configure(text=wmi_vram_text, text_color=wmi_vram_color)

        width = _num(os_inv.get('current_horizontal_resolution'))
        height = _num(os_inv.get('current_vertical_resolution'))
        mode = str(os_inv.get('video_mode_description') or '').strip()
        display_elsewhere = active_display_on_other_gpu(gpu, all_gpus)
        if width is not None and height is not None:
            resolution = f'{int(width)} × {int(height)}'
        elif mode:
            resolution = mode
        elif display_elsewhere:
            resolution = 'No asociada directamente a este adaptador'
        else:
            resolution = 'N/A'
        self._spec_labels['resolution'].configure(text=resolution, text_color=MUTED if display_elsewhere and width is None and not mode else TEXT)

        refresh = _num(os_inv.get('current_refresh_rate'))
        if refresh is not None:
            refresh_text = f'{int(refresh)} Hz'
        elif display_elsewhere:
            refresh_text = 'No asociada directamente a este adaptador'
        else:
            refresh_text = 'N/A'
        self._spec_labels['refresh_rate'].configure(text=refresh_text, text_color=MUTED if refresh is None else TEXT)
        self._spec_labels['hardware_type'].configure(text=human_gpu_hardware_type(gpu.get('hardware_type')))
        pnp = str(os_inv.get('pnp_device_id') or 'N/A')
        self._spec_labels['pnp_id'].configure(text=pnp if len(pnp) <= 58 else pnp[:55] + '…')
        sources = gpu.get('inventory_sources') if isinstance(gpu.get('inventory_sources'), list) else []
        source_text = ' + '.join(str(x).replace('LibreHardwareMonitorLib', 'LibreHardwareMonitor') for x in sources) if sources else str(gpu.get('source') or 'N/A').replace('LibreHardwareMonitorLib', 'LibreHardwareMonitor')
        self._spec_labels['inventory_source'].configure(text=source_text)
        self.lbl_identity_source.configure(text=f'Inventario GPU: {source_text}', text_color=GREEN if (sources or gpu.get('source')) else MUTED)

    def _log_refresh_exception(self, message):
        now = time.monotonic()
        if now - self._last_refresh_error_log_at >= 5.0:
            self._last_refresh_error_log_at = now
            logger.exception(message)

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
            gpus = self._gpu_list(telemetry)
            self._select_initial_index(telemetry, gpus)
            self._update_selector(gpus)
            snapshot_stamp = telemetry.get('_snapshot_timestamp') or telemetry.get('timestamp')
            self.lbl_freshness.configure(text=f'Actualización: {_age_text(snapshot_stamp)}')

            if self._selected_index is None or not (0 <= self._selected_index < len(gpus)):
                self.lbl_title.configure(text='Detalles avanzados de GPU')
                self.usage_value.configure(text='N/A', text_color=MUTED)
                self.temp_value.configure(text='N/A', text_color=MUTED)
                self.vram_value.configure(text='N/A', text_color=MUTED)
                self.power_value.configure(text='N/A', text_color=MUTED)
                return

            gpu = gpus[self._selected_index]
            self._selected_name = gpu.get('name')
            self.lbl_title.configure(text=str(gpu.get('name') or f'GPU {self._selected_index}'))

            usage = gpu.get('usage_percent')
            temp = gpu.get('temperature_c')
            used_mb = gpu.get('memory_used_mb')
            total_mb = gpu.get('memory_total_mb')
            os_inv = gpu.get('os_inventory') if isinstance(gpu.get('os_inventory'), dict) else {}
            total_gb = _gb_from_mb(total_mb)
            total_source = 'LibreHardwareMonitor'
            if total_gb is None:
                total_gb = _gb_from_bytes(os_inv.get('adapter_ram_bytes_os'))
                total_source = 'Windows' if total_gb is not None else 'N/A'
            used_gb = _gb_from_mb(used_mb)
            power = gpu.get('power_w')

            self.usage_value.configure(text=_fmt(usage, 1, '%'), text_color=PURPLE if _num(usage) is not None else MUTED)
            self.usage_detail.configure(text='GPU Core · LibreHardwareMonitor' if _num(usage) is not None else 'Sensor de carga no disponible')
            self.temp_value.configure(text=_fmt(temp, 1, ' °C'), text_color=_thermal_color(temp))
            self.temp_detail.configure(text='GPU Core · LibreHardwareMonitor' if _num(temp) is not None else 'Sensor térmico no disponible')
            if used_gb is not None and total_gb is not None:
                vram_text = f'{used_gb:.2f} / {total_gb:.2f} GB'
            elif total_gb is not None:
                vram_text = f'{total_gb:.2f} GB'
            else:
                vram_text = 'N/A'
            self.vram_value.configure(text=vram_text, text_color=CYAN if total_gb is not None else MUTED)
            self.vram_detail.configure(text=('Total certificado por LibreHardwareMonitor' if total_source == 'LibreHardwareMonitor' else 'Total de inventario según Windows (WMI)') if total_gb is not None else 'VRAM no disponible')
            self.power_value.configure(text=_fmt(power, 2, ' W'), text_color=PURPLE if _num(power) is not None else MUTED)
            self.power_detail.configure(text='GPU Package · sensor real' if _num(power) is not None else 'Sensor de potencia no disponible')

            if not self._is_scrolling():
                self._apply_static_rows(gpu, gpus)
                self._advanced_labels['hotspot'].configure(text=_fmt(gpu.get('hotspot_c'), 1, ' °C'), text_color=_thermal_color(gpu.get('hotspot_c')))
                self._advanced_labels['core_clock'].configure(text=_fmt(gpu.get('core_clock_mhz'), 1, ' MHz'))
                self._advanced_labels['memory_clock'].configure(text=_fmt(gpu.get('memory_clock_mhz'), 1, ' MHz'))
                self._advanced_labels['memory_load'].configure(text=_fmt(gpu.get('memory_usage_percent'), 1, '%'))
                self._advanced_labels['vram_used'].configure(text=_fmt(used_gb, 2, ' GB'))
                self._advanced_labels['vram_total'].configure(text=_fmt(_gb_from_mb(total_mb), 2, ' GB'))
                self._advanced_labels['fan_rpm'].configure(text=_fmt(gpu.get('fan_rpm'), 0, ' RPM'))
                self._advanced_labels['fan_control'].configure(text=_fmt(gpu.get('fan_control_percent'), 1, '%'))
                self._advanced_labels['voltage'].configure(text=_fmt(gpu.get('core_voltage_v'), 4, ' V'))
                self._advanced_labels['power'].configure(text=_fmt(power, 2, ' W'))
                sensors = gpu.get('sensors') if isinstance(gpu.get('sensors'), list) else []
                sensors = [s for s in sensors if isinstance(s, dict)]
                sensor_count = gpu.get('sensor_count')
                if _num(sensor_count) is None or (int(_num(sensor_count) or 0) == 0 and sensors):
                    sensor_count = len(sensors)
                self._advanced_labels['sensor_count'].configure(text=_fmt_int(sensor_count))
                provider = str(gpu.get('source') or 'N/A').replace('LibreHardwareMonitorLib', 'LibreHardwareMonitor')
                self._advanced_labels['provider'].configure(text=provider)
                self._update_sensor_rows(sensors)
        except Exception:
            self._log_refresh_exception('Fallo al refrescar Detalles avanzados de GPU')
        finally:
            if self._alive:
                try:
                    self._after_id = self.frame.after(850, self.refresh)
                except Exception:
                    self._after_id = None


__all__ = ['GPUDetailPanel']
