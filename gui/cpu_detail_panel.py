"""Vista avanzada de CPU de CorePulse.

Combina identidad estática obtenida desde Windows con el snapshot vivo que ya
produce el pipeline de telemetría. La interfaz nunca sondea sensores directamente
desde Tkinter y respeta la política REAL_OR_NA.
"""
from __future__ import annotations
from core.theme_manager import color as theme_color

import threading
import time
from datetime import datetime

import customtkinter as ctk

from core.device_identity import collect_cpu_identity
from core.runtime_logging import get_logger
from gui.internal_navigation import show_dashboard
from gui.stable_scroll import StableScrollHost

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
logger = get_logger('cpu_detail_panel')

TYPE_LABELS = {
    'temperature': 'TEMPERATURA',
    'clock': 'RELOJ',
    'load': 'CARGA',
    'power': 'POTENCIA',
    'voltage': 'VOLTAJE',
    'current': 'CORRIENTE',
}
TYPE_COLORS = {
    'temperature': AMBER,
    'clock': CYAN,
    'load': GREEN,
    'power': PURPLE,
    'voltage': CYAN,
    'current': TEXT_2,
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


def _yes_no(value):
    if value is True:
        return 'Sí'
    if value is False:
        return 'No'
    return 'N/A'


def _cache(value_kb):
    number = _num(value_kb)
    if number is None:
        return 'N/A'
    if number >= 1024:
        return f'{number / 1024.0:.1f} MB'
    return f'{int(number)} KB'


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
    if number < 75:
        return GREEN
    if number < 90:
        return AMBER
    return RED


def _distance_to_tjmax_color(value):
    """Para margen a TjMax, un número menor significa una condición peor."""
    number = _num(value)
    if number is None:
        return MUTED
    if number <= 5:
        return RED
    if number <= 20:
        return AMBER
    return GREEN


def _sensor_value_color(sensor):
    kind = str((sensor or {}).get('type') or '').lower()
    if kind != 'temperature':
        return TEXT_2
    name = str((sensor or {}).get('name') or '').lower()
    if 'distance to tjmax' in name or 'distancia' in name and 'tjmax' in name:
        return _distance_to_tjmax_color((sensor or {}).get('value'))
    return _thermal_color((sensor or {}).get('value'))


def _display_sensor_value(sensor):
    value = _num(sensor.get('value'))
    if value is None:
        return 'N/A'
    kind = str(sensor.get('type') or '').lower()
    unit = str(sensor.get('unit') or '').strip()
    digits = 3 if kind == 'voltage' else 2 if kind in {'power', 'current'} else 1
    return f'{value:.{digits}f} {unit}'.strip()


class CPUDetailPanel:
    """Presenta especificaciones y sensores reales de la CPU monitoreada."""

    def __init__(self, app, host):
        self.app = app
        self.host = host
        self._alive = True
        self._after_id = None
        self._identity = None
        self._identity_loading = False
        self._spec_labels = {}
        self._advanced_labels = {}
        self._sensor_widgets = {}
        self._identity_applied_signature = None
        self._scroll_active_until = 0.0
        self._scroll_watch_after_id = None
        self._last_scroll_view = None
        self._last_refresh_error_log_at = 0.0
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
            text='Detalles avanzados de CPU',
            font=(FONT, 19, 'bold'),
            text_color=TEXT,
            anchor='w',
        )
        self.lbl_title.pack(anchor='w')
        self.lbl_subtitle = ctk.CTkLabel(
            titles,
            text='Identidad de Windows + sensores reales en tiempo real',
            font=(FONT, 10),
            text_color=TEXT_2,
            anchor='w',
        )
        self.lbl_subtitle.pack(anchor='w', pady=(1, 0))
        self.lbl_freshness = ctk.CTkLabel(
            header,
            text='Actualización: N/A',
            font=(FONT, 9, 'bold'),
            text_color=MUTED,
        )
        self.lbl_freshness.pack(side='right', padx=(8, 0))

        self.summary_row = ctk.CTkFrame(self.frame, fg_color='transparent')
        self.summary_row.pack(fill='x', padx=18, pady=(2, 9))
        self.usage_card, self.usage_value, self.usage_detail = self._summary_card('USO', 'N/A', 'Carga del procesador', CYAN)
        self.temp_card, self.temp_value, self.temp_detail = self._summary_card('TEMPERATURA', 'N/A', 'CPU Package', GREEN)
        self.clock_card, self.clock_value, self.clock_detail = self._summary_card('FRECUENCIA', 'N/A', 'Promedio de núcleos', CYAN)
        self.power_card, self.power_value, self.power_detail = self._summary_card('POTENCIA', 'N/A', 'CPU Package', PURPLE)
        for index, card in enumerate((self.usage_card, self.temp_card, self.clock_card, self.power_card)):
            card.pack(side='left', fill='both', expand=True, padx=(0 if index == 0 else 5, 0 if index == 3 else 5))

        self.body_scroll = StableScrollHost(self.frame, fg_color=BG)
        self.body_scroll.pack(fill='both', expand=True, padx=13, pady=(0, 10))
        self.body = self.body_scroll.content
        # El cuerpo continúa siendo desplazable para mantener compatibilidad con
        # ventanas compactas, pero ninguna telemetría modifica sus widgets mientras
        # el canvas se está moviendo. Esto evita artefactos de repintado de Tk/CTk.

        overview = ctk.CTkFrame(self.body, fg_color='transparent')
        overview.pack(fill='x', padx=5, pady=(0, 8))
        overview.grid_columnconfigure(0, weight=1)
        overview.grid_columnconfigure(1, weight=1)

        specs = self._section_card(overview, 'ESPECIFICACIONES DEL PROCESADOR', 'Datos reportados por Windows / Win32_Processor')
        specs.grid(row=0, column=0, sticky='nsew', padx=(0, 5))
        advanced = self._section_card(overview, 'LECTURAS AVANZADAS', 'Valores presentes únicamente cuando el sensor existe')
        advanced.grid(row=0, column=1, sticky='nsew', padx=(5, 0))

        self._add_spec_row(specs, 'manufacturer', 'Fabricante')
        self._add_spec_row(specs, 'cores_threads', 'Núcleos / hilos')
        self._add_spec_row(specs, 'socket', 'Socket')
        self._add_spec_row(specs, 'architecture', 'Arquitectura')
        self._add_spec_row(specs, 'address_width', 'Ancho de dirección')
        self._add_spec_row(specs, 'max_clock', 'Frecuencia nominal (Windows)')
        self._add_spec_row(specs, 'l2', 'Caché L2')
        self._add_spec_row(specs, 'l3', 'Caché L3')
        self._add_spec_row(specs, 'virtualization', 'Virtualización firmware (Windows)')
        self._add_spec_row(specs, 'slat', 'SLAT (Windows)')
        self._add_spec_row(specs, 'vm_monitor', 'Extensiones VM monitor (Windows)')
        self._add_spec_row(specs, 'family', 'Familia / stepping / revisión')

        self._add_advanced_row(advanced, 'lhm_load', 'Carga total sensor LHM')
        self._add_advanced_row(advanced, 'core_max', 'Temperatura máxima núcleo')
        self._add_advanced_row(advanced, 'core_avg', 'Temperatura promedio núcleo')
        self._add_advanced_row(advanced, 'tjmax', 'Distancia mínima a TjMax')
        self._add_advanced_row(advanced, 'clock_max', 'Clock máximo observado')
        self._add_advanced_row(advanced, 'bus_clock', 'Bus clock')
        self._add_advanced_row(advanced, 'voltage', 'Voltaje de núcleo')
        self._add_advanced_row(advanced, 'sensor_count', 'Sensores CPU visibles')
        self._add_advanced_row(advanced, 'provider', 'Proveedor')

        sensor_card = ctk.CTkFrame(
            self.body,
            fg_color=CARD,
            border_width=1,
            border_color=BORDER,
            corner_radius=12,
        )
        sensor_card.pack(fill='x', padx=5, pady=(0, 8))
        sensor_header = ctk.CTkFrame(sensor_card, fg_color='transparent')
        sensor_header.pack(fill='x', padx=14, pady=(10, 5))
        ctk.CTkLabel(
            sensor_header,
            text='SENSORES DE CPU EN TIEMPO REAL',
            font=(FONT, 10, 'bold'),
            text_color=TEXT_2,
        ).pack(side='left')
        self.lbl_sensor_status = ctk.CTkLabel(
            sensor_header,
            text='Esperando telemetría',
            font=(FONT, 8, 'bold'),
            text_color=MUTED,
        )
        self.lbl_sensor_status.pack(side='right')

        headings = ctk.CTkFrame(sensor_card, fg_color=CARD_2, height=28, corner_radius=6)
        headings.pack(fill='x', padx=10, pady=(0, 4))
        headings.pack_propagate(False)
        for text, width in [('TIPO', 120), ('SENSOR', 330), ('VALOR', 130), ('ORIGEN', 210), ('FRESCURA', 90)]:
            ctk.CTkLabel(headings, text=text, width=width, font=(FONT, 8, 'bold'), text_color=MUTED, anchor='w').pack(side='left', padx=(8, 0))

        self.sensor_rows = ctk.CTkFrame(sensor_card, fg_color='transparent')
        self.sensor_rows.pack(fill='x', padx=10, pady=(0, 9))
        self.lbl_no_sensors = ctk.CTkLabel(
            self.sensor_rows,
            text='No hay sensores CPU expuestos por el proveedor actual.',
            font=(FONT, 9),
            text_color=MUTED,
            anchor='w',
        )
        self.lbl_no_sensors.pack(fill='x', padx=8, pady=12)

        footer = ctk.CTkFrame(self.body, fg_color='transparent')
        footer.pack(fill='x', padx=8, pady=(0, 6))
        ctk.CTkLabel(
            footer,
            text='CorePulse muestra datos reales o N/A. No estima TDP, voltaje, temperatura ni frecuencia ausente.',
            font=(FONT, 8),
            text_color=MUTED,
            anchor='w',
        ).pack(side='left')
        self.lbl_identity_source = ctk.CTkLabel(
            footer,
            text='Identidad CPU: cargando…',
            font=(FONT, 8, 'bold'),
            text_color=MUTED,
            anchor='e',
        )
        self.lbl_identity_source.pack(side='right')

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
        order = {'load': 0, 'temperature': 1, 'clock': 2, 'power': 3, 'voltage': 4, 'current': 5}
        kind = str((sensor or {}).get('type') or '').lower()
        return (
            order.get(kind, 9),
            str((sensor or {}).get('name') or '').lower(),
            str((sensor or {}).get('identifier') or '').lower(),
        )

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
        row = ctk.CTkFrame(parent, fg_color='transparent', height=28)
        row.pack(fill='x', padx=14, pady=1)
        row.pack_propagate(False)
        ctk.CTkLabel(row, text=label, width=155, font=(FONT, 9), text_color=MUTED, anchor='w').pack(side='left')
        value = ctk.CTkLabel(row, text='N/A', font=(FONT, 9, 'bold'), text_color=TEXT, anchor='w')
        value.pack(side='left', fill='x', expand=True)
        self._spec_labels[key] = value

    def _add_advanced_row(self, parent, key, label):
        row = ctk.CTkFrame(parent, fg_color='transparent', height=28)
        row.pack(fill='x', padx=14, pady=1)
        row.pack_propagate(False)
        ctk.CTkLabel(row, text=label, width=180, font=(FONT, 9), text_color=MUTED, anchor='w').pack(side='left')
        value = ctk.CTkLabel(row, text='N/A', font=(FONT, 9, 'bold'), text_color=TEXT, anchor='w')
        value.pack(side='left', fill='x', expand=True)
        self._advanced_labels[key] = value

    def _start_identity_load(self):
        if self._identity_loading or self._identity is not None:
            return
        self._identity_loading = True

        def worker():
            try:
                result = collect_cpu_identity()
            except Exception:
                result = {}
            self._identity = result if isinstance(result, dict) else {}
            self._identity_loading = False

        threading.Thread(target=worker, name='CorePulseCPUIdentity', daemon=True).start()

    def _apply_identity(self):
        identity = self._identity
        if identity is None:
            self.lbl_identity_source.configure(text='Identidad CPU: cargando…', text_color=MUTED)
            return
        try:
            signature = tuple(sorted((str(k), repr(v)) for k, v in identity.items()))
        except Exception:
            signature = id(identity)
        if signature == self._identity_applied_signature:
            return
        name = str(identity.get('name') or '').strip()
        if name:
            self.lbl_title.configure(text=name)
        self._spec_labels['manufacturer'].configure(text=str(identity.get('manufacturer') or 'N/A'))
        cores = _fmt_int(identity.get('cores'))
        threads = _fmt_int(identity.get('threads'))
        self._spec_labels['cores_threads'].configure(text=f'{cores} / {threads}' if cores != 'N/A' or threads != 'N/A' else 'N/A')
        self._spec_labels['socket'].configure(text=str(identity.get('socket') or 'N/A'))
        architecture = str(identity.get('architecture') or 'N/A')
        data_width = _fmt_int(identity.get('data_width_bits'), ' bits')
        self._spec_labels['architecture'].configure(text=f'{architecture} · {data_width}' if data_width != 'N/A' else architecture)
        self._spec_labels['address_width'].configure(text=_fmt_int(identity.get('address_width_bits'), ' bits'))
        self._spec_labels['max_clock'].configure(text=_fmt(identity.get('max_clock_ghz'), 3, ' GHz'))
        self._spec_labels['l2'].configure(text=_cache(identity.get('l2_cache_kb')))
        self._spec_labels['l3'].configure(text=_cache(identity.get('l3_cache_kb')))
        self._spec_labels['virtualization'].configure(text=_yes_no(identity.get('virtualization_firmware_enabled')))
        self._spec_labels['slat'].configure(text=_yes_no(identity.get('slat_supported')))
        self._spec_labels['vm_monitor'].configure(text=_yes_no(identity.get('vm_monitor_mode_extensions')))
        family = _fmt_int(identity.get('family'))
        stepping = _fmt_int(identity.get('stepping'))
        revision = _fmt_int(identity.get('revision'))
        family_parts = []
        if family != 'N/A':
            family_parts.append(f'Familia {family}')
        if stepping != 'N/A':
            family_parts.append(f'Stepping {stepping}')
        if revision != 'N/A':
            family_parts.append(f'Rev. {revision}')
        self._spec_labels['family'].configure(text=' · '.join(family_parts) if family_parts else 'N/A')
        source = str(identity.get('source') or 'N/A')
        self.lbl_identity_source.configure(text=f'Identidad CPU: {source}', text_color=GREEN if source != 'N/A' else MUTED)
        self._identity_applied_signature = signature

    def _aggregate_sensor_rows(self, cpu, snapshot_stamp=None):
        """Reconstruye filas sólo desde métricas reales ya certificadas del snapshot.

        Es un respaldo de compatibilidad para el primer snapshot tras una actualización
        o para snapshots antiguos que todavía no traigan ``cpu["sensors"]``. No crea
        valores nuevos: cada fila exige un valor real presente en ``_cpu``.
        """
        if not isinstance(cpu, dict):
            return []
        definitions = [
            ('package_temp_c', 'temperature', 'CPU Package', '°C'),
            ('core_max_temp_c', 'temperature', 'Core Max', '°C'),
            ('core_average_temp_c', 'temperature', 'Core Average', '°C'),
            ('distance_to_tjmax_min_c', 'temperature', 'Distance to TjMax (mínima)', '°C'),
            ('total_load_percent', 'load', 'CPU Total', '%'),
            ('clock_avg_ghz', 'clock', 'Clock promedio certificado', 'GHz'),
            ('clock_max_ghz', 'clock', 'Clock máximo observado', 'GHz'),
            ('bus_clock_mhz', 'clock', 'Bus Clock', 'MHz'),
            ('package_power_w', 'power', 'CPU Package', 'W'),
            ('core_voltage_v', 'voltage', 'CPU Core', 'V'),
        ]
        certified = cpu.get('_certified_metrics') if isinstance(cpu.get('_certified_metrics'), dict) else {}
        raw_meta = cpu.get('_metrics') if isinstance(cpu.get('_metrics'), dict) else {}
        rows = []
        for field, kind, default_name, unit in definitions:
            value = _num(cpu.get(field))
            if value is None:
                continue
            cert = certified.get(field) if isinstance(certified.get(field), dict) else {}
            raw = raw_meta.get(field) if isinstance(raw_meta.get(field), dict) else {}
            sensor_name = str(cert.get('sensor') or raw.get('sensor') or default_name).strip()
            source = str(cert.get('source') or raw.get('source') or cpu.get('source') or 'N/A')
            timestamp = cert.get('sensor_timestamp') or raw.get('sensor_timestamp') or cpu.get('timestamp') or snapshot_stamp
            rows.append({
                'name': sensor_name,
                'type': kind,
                'value': value,
                'unit': unit,
                'identifier': f'aggregate::{field}',
                'source': source,
                'quality': str(cert.get('quality') or cpu.get('quality') or 'VALID'),
                'timestamp': timestamp,
                'aggregate_fallback': True,
            })
        return rows

    def _snapshot_metric_rows(self, telemetry, snapshot_stamp=None):
        """Último respaldo: métricas CPU reales publicadas por el pipeline general.

        Se usa únicamente cuando el proveedor de hardware no entrega inventario ni
        agregados CPU. No sintetiza valores: exige quality VALID y value real.
        """
        if not isinstance(telemetry, dict):
            return []
        metrics = telemetry.get('_metrics') if isinstance(telemetry.get('_metrics'), dict) else {}
        definitions = [
            ('cpu_usage', 'load', 'Uso total CPU', '%'),
            ('cpu_temp', 'temperature', 'Temperatura CPU', '°C'),
            ('cpu_ghz', 'clock', 'Frecuencia CPU', 'GHz'),
        ]
        rows = []
        for key, kind, default_name, default_unit in definitions:
            meta = metrics.get(key) if isinstance(metrics.get(key), dict) else {}
            value = _num(meta.get('value') if 'value' in meta else telemetry.get(key))
            quality = str(meta.get('quality') or ('VALID' if value is not None else 'UNAVAILABLE')).upper()
            if value is None or quality != 'VALID':
                continue
            rows.append({
                'name': str(meta.get('sensor') or default_name),
                'type': kind,
                'value': value,
                'unit': str(meta.get('unit') or default_unit),
                'identifier': f'snapshot::{key}',
                'source': str(meta.get('source') or 'CorePulse telemetry'),
                'quality': 'VALID',
                'timestamp': meta.get('sensor_timestamp') or meta.get('timestamp') or meta.get('snapshot_timestamp') or snapshot_stamp,
                'snapshot_fallback': True,
            })
        return rows

    def _log_refresh_exception(self, message):
        now = time.monotonic()
        if now - self._last_refresh_error_log_at >= 5.0:
            self._last_refresh_error_log_at = now
            logger.exception(message)

    def _update_sensor_rows(self, sensors):
        # Redibujar decenas de CTkLabel mientras el canvas se desplaza provoca
        # ghosting en Windows/Tk. Durante el movimiento conservamos el último
        # frame estable y actualizamos apenas finaliza la inercia del scroll.
        if self._is_scrolling():
            return
        valid = sorted((s for s in sensors if isinstance(s, dict)), key=self._sensor_sort_key)
        keys = []
        for index, sensor in enumerate(valid):
            key = str(sensor.get('identifier') or f"{sensor.get('type')}::{sensor.get('name')}::{index}")
            keys.append(key)
            if key not in self._sensor_widgets:
                if self.lbl_no_sensors.winfo_manager():
                    self.lbl_no_sensors.pack_forget()
                row = ctk.CTkFrame(self.sensor_rows, fg_color='transparent', height=33, corner_radius=5)
                row.pack(fill='x', pady=1)
                row.pack_propagate(False)
                kind = ctk.CTkLabel(row, text='', width=120, font=(FONT, 8, 'bold'), text_color=CYAN, anchor='w')
                name = ctk.CTkLabel(row, text='', width=330, font=(FONT, 9, 'bold'), text_color=TEXT, anchor='w')
                value = ctk.CTkLabel(row, text='', width=130, font=(FONT, 9, 'bold'), text_color=TEXT_2, anchor='w')
                source = ctk.CTkLabel(row, text='', width=210, font=(FONT, 8), text_color=TEXT_2, anchor='w')
                age = ctk.CTkLabel(row, text='', width=90, font=(FONT, 8), text_color=MUTED, anchor='w')
                for label in (kind, name, value, source, age):
                    label.pack(side='left', padx=(8, 0))
                self._sensor_widgets[key] = (row, kind, name, value, source, age)
            row, kind_lbl, name_lbl, value_lbl, source_lbl, age_lbl = self._sensor_widgets[key]
            kind = str(sensor.get('type') or '').lower()
            kind_lbl.configure(text=TYPE_LABELS.get(kind, kind.upper() or 'SENSOR'), text_color=TYPE_COLORS.get(kind, CYAN))
            name_lbl.configure(text=str(sensor.get('name') or 'Sensor'))
            value_lbl.configure(text=_display_sensor_value(sensor), text_color=_sensor_value_color(sensor))
            source = str(sensor.get('source') or 'N/A').replace('LibreHardwareMonitorLib', 'LibreHardwareMonitor')
            source_lbl.configure(text=source)
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
        self.lbl_sensor_status.configure(
            text=f'{len(valid)} sensores válidos' if valid else 'Sin sensores disponibles',
            text_color=GREEN if valid else MUTED,
        )

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
            scrolling = self._is_scrolling()
            if not scrolling:
                self._apply_identity()
            telemetry = getattr(self.app, 'latest_telemetry', None)
            if not isinstance(telemetry, dict):
                telemetry = {}
            cpu = telemetry.get('_cpu') if isinstance(telemetry.get('_cpu'), dict) else {}
            snapshot_stamp = telemetry.get('_snapshot_timestamp') or telemetry.get('timestamp')

            cpu_name = str(cpu.get('hardware') or '').strip()
            if cpu_name and not (self._identity and self._identity.get('name')):
                self.lbl_title.configure(text=cpu_name)

            usage = telemetry.get('cpu_usage')
            temp = cpu.get('package_temp_c') if cpu.get('package_temp_c') is not None else telemetry.get('cpu_temp')
            clock = cpu.get('clock_avg_ghz') if cpu.get('clock_avg_ghz') is not None else telemetry.get('cpu_ghz')
            power = cpu.get('package_power_w')

            self.usage_value.configure(text=_fmt(usage, 1, '%'), text_color=CYAN if _num(usage) is not None else MUTED)
            self.usage_detail.configure(text='Carga total del sistema · psutil')
            self.temp_value.configure(text=_fmt(temp, 1, ' °C'), text_color=_thermal_color(temp))
            self.temp_detail.configure(text='CPU Package · LibreHardwareMonitor' if cpu.get('source') else 'Sensor térmico disponible')
            self.clock_value.configure(text=_fmt(clock, 3, ' GHz'), text_color=CYAN if _num(clock) is not None else MUTED)
            max_clock = cpu.get('clock_max_ghz')
            self.clock_detail.configure(text=f'Máximo observado: {_fmt(max_clock, 3, " GHz")}' if _num(max_clock) is not None else 'Frecuencia actual disponible')
            self.power_value.configure(text=_fmt(power, 2, ' W'), text_color=PURPLE if _num(power) is not None else MUTED)
            self.power_detail.configure(text='CPU Package · sensor real' if _num(power) is not None else 'Sensor de potencia no disponible')

            # Las tarjetas superiores quedan vivas durante el scroll. En cambio,
            # todo widget que pertenece al canvas desplazable permanece congelado
            # hasta que el viewport se estabiliza para evitar repintados corruptos.
            if not scrolling:
                self._advanced_labels['lhm_load'].configure(text=_fmt(cpu.get('total_load_percent'), 1, '%'))
                self._advanced_labels['core_max'].configure(text=_fmt(cpu.get('core_max_temp_c'), 1, ' °C'))
                self._advanced_labels['core_avg'].configure(text=_fmt(cpu.get('core_average_temp_c'), 1, ' °C'))
                self._advanced_labels['tjmax'].configure(text=_fmt(cpu.get('distance_to_tjmax_min_c'), 1, ' °C'), text_color=_distance_to_tjmax_color(cpu.get('distance_to_tjmax_min_c')))
                self._advanced_labels['clock_max'].configure(text=_fmt(cpu.get('clock_max_ghz'), 3, ' GHz'))
                self._advanced_labels['bus_clock'].configure(text=_fmt(cpu.get('bus_clock_mhz'), 2, ' MHz'))
                self._advanced_labels['voltage'].configure(text=_fmt(cpu.get('core_voltage_v'), 4, ' V'))
                provider = str(cpu.get('source') or 'N/A').replace('LibreHardwareMonitorLib', 'LibreHardwareMonitor')
                self._advanced_labels['provider'].configure(text=provider)

                sensors = cpu.get('sensors') if isinstance(cpu.get('sensors'), list) else []
                sensors = [sensor for sensor in sensors if isinstance(sensor, dict)]
                if not sensors:
                    sensors = self._aggregate_sensor_rows(cpu, snapshot_stamp)
                if not sensors:
                    sensors = self._snapshot_metric_rows(telemetry, snapshot_stamp)
                sensor_count = cpu.get('sensor_count')
                if _num(sensor_count) is None or (int(_num(sensor_count) or 0) == 0 and sensors):
                    sensor_count = len(sensors)
                self._advanced_labels['sensor_count'].configure(text=_fmt_int(sensor_count))
                self._update_sensor_rows(sensors)
            self.lbl_freshness.configure(text=f'Actualización: {_age_text(snapshot_stamp)}')
        except Exception:
            self._log_refresh_exception('Fallo al refrescar Detalles avanzados de CPU')

        if self._alive:
            try:
                self._after_id = self.frame.after(850, self.refresh)
            except Exception:
                self._after_id = None


__all__ = ['CPUDetailPanel']
