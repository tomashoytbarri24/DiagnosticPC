"""Vista interna de detalle de unidades de almacenamiento de CorePulse."""
from __future__ import annotations
from core.theme_manager import color as theme_color

import copy
import threading

import customtkinter as ctk

from core.storage_details import build_storage_detail_snapshot, resolve_physical_disk_index
from core.storage_health import get_storage_health
from core.nvme_smart_windows import query_nvme_health_log
from gui.internal_navigation import activate_internal_page, commit_internal_page, abort_internal_page, show_dashboard

BG = theme_color('#06111f')
CARD = theme_color('#0d1828')
CARD_2 = theme_color('#101d2f')
BORDER = theme_color('#1b3048')
TEXT = theme_color('#f4f7fb')
TEXT_2 = theme_color('#b8c4d4')
MUTED = theme_color('#7f91a8')
CYAN = '#14b8ff'
GREEN = '#1fd18b'
AMBER = '#f59e0b'
RED = '#ef4444'
FONT = 'Segoe UI'


def _number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except Exception:
        return None


def _fmt(value, digits=1, suffix=''):
    number = _number(value)
    if number is None:
        return 'N/A'
    return f'{number:.{digits}f}{suffix}'


def _fmt_int(value, suffix=''):
    number = _number(value)
    if number is None:
        return 'N/A'
    return f'{int(number):,}{suffix}'.replace(',', '.')


def _display_status(value):
    text = str(value or '').strip()
    return text if text else 'N/A'


def _health_color(value):
    number = _number(value)
    if number is None:
        return MUTED
    if number >= 90:
        return GREEN
    if number >= 70:
        return AMBER
    return RED

def _health_state(value):
    number = _number(value)
    if number is None:
        return 'No evaluable'
    if number >= 90:
        return 'Excelente'
    if number >= 70:
        return 'Atención'
    return 'Crítico'


def _temperature_state(snapshot):
    value = _number(snapshot.get('temperature_c'))
    if value is None:
        return 'No disponible'
    critical = _number(snapshot.get('critical_temperature_c'))
    warning = _number(snapshot.get('warning_temperature_c'))
    if critical is not None and value >= critical:
        return 'Crítica'
    if warning is not None and value >= warning:
        return 'Elevada'
    if value >= 70:
        return 'Elevada'
    return 'Normal'


def _space_color(value):
    number = _number(value)
    if number is None:
        return MUTED
    if number >= 90:
        return RED
    if number >= 80:
        return AMBER
    return CYAN


def _temperature_color(snapshot):
    value = _number(snapshot.get('temperature_c'))
    if value is None:
        return MUTED
    critical = _number(snapshot.get('critical_temperature_c'))
    warning = _number(snapshot.get('warning_temperature_c'))
    if critical is not None and value >= critical:
        return RED
    if warning is not None and value >= warning:
        return AMBER
    return CYAN


class StorageDetailPanel:
    def __init__(self, app, host, disk_index):
        self.app = app
        self.host = host
        self.disk_index = int(disk_index)
        self._alive = True
        self._load_generation = 0
        self._job = None
        self._value_labels = {}
        self._sensor_labels = []
        self._error_labels = []
        self._reliability_labels = []
        self._build()
        self.select_disk(self.disk_index)

    def widget(self):
        return self.frame

    def _build(self):
        self.frame = ctk.CTkFrame(self.host, fg_color=BG, corner_radius=0)
        self.frame.pack(fill='both', expand=True)

        header = ctk.CTkFrame(self.frame, fg_color='transparent')
        header.pack(fill='x', padx=18, pady=(15, 8))
        ctk.CTkButton(
            header, text='← Volver a almacenamiento', width=175, height=30,
            fg_color=theme_color('#15243a'), hover_color=theme_color('#1d3350'), text_color=TEXT,
            font=(FONT, 10, 'bold'), corner_radius=8,
            command=lambda: show_dashboard(self.app),
        ).pack(side='left')
        titles = ctk.CTkFrame(header, fg_color='transparent')
        titles.pack(side='left', fill='x', expand=True, padx=14)
        self.lbl_title = ctk.CTkLabel(titles, text='Detalles del almacenamiento', font=(FONT, 19, 'bold'), text_color=TEXT, anchor='w')
        self.lbl_title.pack(anchor='w')
        self.lbl_subtitle = ctk.CTkLabel(titles, text='Cargando identidad real de la unidad…', font=(FONT, 10), text_color=TEXT_2, anchor='w')
        self.lbl_subtitle.pack(anchor='w', pady=(1, 0))
        self.btn_refresh = ctk.CTkButton(
            header, text='Actualizar', width=92, height=30, fg_color=theme_color('#164f7d'),
            hover_color=theme_color('#1b5c8f'), text_color=TEXT, font=(FONT, 10, 'bold'),
            command=self.refresh_reliability,
        )
        self.btn_refresh.pack(side='right')

        self.status_row = ctk.CTkFrame(self.frame, fg_color='transparent')
        self.status_row.pack(fill='x', padx=18, pady=(2, 9))
        self.health_card, self.health_value, self.health_detail = self._status_card('SALUD', 'N/A', 'SMART / confiabilidad', GREEN)
        self.temp_card, self.temp_value, self.temp_detail = self._status_card('TEMPERATURA', 'N/A', 'Sensor actual', CYAN)
        self.space_card, self.space_value, self.space_detail = self._status_card('ESPACIO', 'N/A', 'Uso de la unidad', CYAN)
        self.health_card.pack(side='left', fill='both', expand=True, padx=(0, 5))
        self.temp_card.pack(side='left', fill='both', expand=True, padx=5)
        self.space_card.pack(side='left', fill='both', expand=True, padx=(5, 0))

        body = ctk.CTkFrame(self.frame, fg_color='transparent')
        body.pack(fill='both', expand=True, padx=18, pady=(0, 10))
        body.grid_columnconfigure(0, weight=1, uniform='storage')
        body.grid_columnconfigure(1, weight=1, uniform='storage')
        body.grid_rowconfigure(0, weight=1)

        left = self._section(body, 'IDENTIDAD Y CAPACIDAD')
        left.grid(row=0, column=0, sticky='nsew', padx=(0, 5))
        right = self._section(body, 'CONFIABILIDAD Y USO')
        right.grid(row=0, column=1, sticky='nsew', padx=(5, 0))

        for key, label in [
            ('model', 'Modelo exacto'),
            ('mount_points', 'Unidad / volumen'),
            ('capacity_gb', 'Capacidad'),
            ('used_gb', 'Usado'),
            ('free_gb', 'Disponible'),
            ('interface', 'Interfaz / bus'),
            ('media_type', 'Tipo de medio'),
            ('firmware', 'Firmware'),
            ('serial', 'N.º de serie'),
        ]:
            self._row(left, key, label)

        self.reliability_box = ctk.CTkFrame(right, fg_color='transparent')
        self.reliability_box.pack(fill='both', expand=True, padx=11, pady=(3, 8))
        self._set_reliability_rows({})

        bottom = ctk.CTkFrame(self.frame, fg_color='transparent')
        bottom.pack(fill='x', padx=18, pady=(0, 10))
        bottom.grid_columnconfigure(0, weight=1, uniform='bottom')
        bottom.grid_columnconfigure(1, weight=1, uniform='bottom')

        errors = self._section(bottom, 'ERRORES IMPORTANTES')
        errors.grid(row=0, column=0, sticky='nsew', padx=(0, 5))
        self.error_box = ctk.CTkFrame(errors, fg_color='transparent')
        self.error_box.pack(fill='both', expand=True, padx=11, pady=(3, 8))
        self._set_error_rows({})

        sensors = self._section(bottom, 'SENSORES DE TEMPERATURA')
        sensors.grid(row=0, column=1, sticky='nsew', padx=(5, 0))
        self.sensor_box = ctk.CTkFrame(sensors, fg_color='transparent')
        self.sensor_box.pack(fill='both', expand=True, padx=11, pady=(3, 8))
        self._set_sensor_rows([])

        footer = ctk.CTkFrame(self.frame, fg_color='transparent')
        footer.pack(fill='x', padx=18, pady=(0, 12))
        self.lbl_loading = ctk.CTkLabel(footer, text='', font=(FONT, 9, 'bold'), text_color=CYAN, anchor='w')
        self.lbl_loading.pack(side='left')
        self.lbl_sources = ctk.CTkLabel(
            footer,
            text='Política: REAL_OR_NA · Los campos no disponibles se muestran como N/A.',
            font=(FONT, 8), text_color=MUTED, anchor='e',
        )
        self.lbl_sources.pack(side='right')

    def _status_card(self, title, value, detail, accent):
        card = ctk.CTkFrame(self.status_row, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=12, height=92)
        card.pack_propagate(False)
        ctk.CTkLabel(card, text=title, font=(FONT, 9, 'bold'), text_color=TEXT_2).pack(anchor='w', padx=13, pady=(10, 0))
        value_label = ctk.CTkLabel(card, text=value, font=(FONT, 23, 'bold'), text_color=accent)
        value_label.pack(anchor='w', padx=13, pady=(0, 0))
        detail_label = ctk.CTkLabel(card, text=detail, font=(FONT, 9), text_color=MUTED)
        detail_label.pack(anchor='w', padx=13, pady=(0, 8))
        return card, value_label, detail_label

    def _section(self, parent, title):
        frame = ctk.CTkFrame(parent, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=12)
        ctk.CTkLabel(frame, text=title, font=(FONT, 9, 'bold'), text_color=TEXT_2).pack(anchor='w', padx=12, pady=(10, 5))
        return frame

    def _row(self, parent, key, label):
        row = ctk.CTkFrame(parent, fg_color='transparent', height=28)
        row.pack(fill='x', padx=11, pady=1)
        row.pack_propagate(False)
        ctk.CTkLabel(row, text=label, font=(FONT, 9), text_color=MUTED, width=135, anchor='w').pack(side='left')
        value = ctk.CTkLabel(row, text='N/A', font=(FONT, 9, 'bold'), text_color=TEXT, anchor='w')
        value.pack(side='left', fill='x', expand=True)
        self._value_labels[key] = value

    def _dynamic_row(self, parent, title, value, color=TEXT):
        row = ctk.CTkFrame(parent, fg_color='transparent', height=27)
        row.pack(fill='x', pady=1)
        row.pack_propagate(False)
        ctk.CTkLabel(
            row, text=title, font=(FONT, 9), text_color=MUTED,
            width=170, anchor='w',
        ).pack(side='left')
        ctk.CTkLabel(
            row, text=value, font=(FONT, 9, 'bold'), text_color=color,
            anchor='w',
        ).pack(side='left', fill='x', expand=True)
        return row

    def _clear_dynamic(self, widgets):
        for widget in widgets:
            try:
                widget.destroy()
            except Exception:
                pass
        widgets.clear()

    def _set_reliability_rows(self, data):
        """Muestra solo métricas de confiabilidad realmente disponibles."""
        self._clear_dynamic(self._reliability_labels)
        rows = []

        windows_status = _display_status(data.get('windows_health_status'))
        if windows_status != 'N/A':
            normalized = windows_status.casefold()
            color = GREEN if normalized in {'healthy', 'ok', 'bueno', 'normal'} else TEXT
            rows.append(('Estado Windows', windows_status, color))

        operational = _display_status(data.get('operational_status'))
        if operational != 'N/A' and operational.casefold() != windows_status.casefold():
            rows.append(('Estado operacional', operational, TEXT))

        wear = _number(data.get('wear_percent'))
        if wear is not None:
            source = _display_status(data.get('wear_source'))
            wear_color = RED if wear >= 100 else AMBER if wear >= 90 else GREEN
            rows.append(('Vida usada / desgaste', f'{wear:.1f}% · {source}', wear_color))

        spare = _number(data.get('available_spare_percent'))
        if spare is not None:
            threshold = _number(data.get('available_spare_threshold_percent'))
            spare_color = RED if threshold is not None and spare < threshold else GREEN
            rows.append(('Reserva disponible', f'{spare:.0f}%', spare_color))

        power_hours = _number(data.get('power_on_hours'))
        if power_hours is not None:
            rows.append(('Horas encendido', _fmt_int(power_hours, ' h'), TEXT))

        power_count = _number(data.get('power_on_count'))
        if power_count is not None:
            rows.append(('Ciclos de energía', _fmt_int(power_count), TEXT))

        # En HDD/ATA puede ser útil. En NVMe directo no ocupa espacio.
        start_stop = _number(data.get('start_stop_cycles'))
        if start_stop is not None and not data.get('nvme_smart_available'):
            rows.append(('Ciclos inicio/parada', _fmt_int(start_stop), TEXT))

        data_read = _number(data.get('data_read_gb'))
        if data_read is not None:
            rows.append(('Datos leídos', _fmt(data_read, 1, ' GB'), TEXT))

        data_written = _number(data.get('data_written_gb'))
        if data_written is not None:
            rows.append(('Datos escritos', _fmt(data_written, 1, ' GB'), TEXT))

        if not rows:
            label = ctk.CTkLabel(
                self.reliability_box,
                text='El dispositivo no expone contadores adicionales de confiabilidad.',
                font=(FONT, 9), text_color=MUTED, anchor='w',
                justify='left', wraplength=350,
            )
            label.pack(fill='x', pady=3)
            self._reliability_labels.append(label)
            return

        for title, value, color in rows:
            self._reliability_labels.append(
                self._dynamic_row(self.reliability_box, title, value, color)
            )

    def _set_error_rows(self, data):
        """Prioriza SMART NVMe y oculta filas N/A que no aportan información."""
        self._clear_dynamic(self._error_labels)
        rows = []

        if data.get('nvme_smart_available'):
            warning = _number(data.get('critical_warning'))
            if warning is not None:
                warning_int = int(warning)
                value = 'Ninguna (0x00)' if warning_int == 0 else f'0x{warning_int:02X}'
                rows.append((
                    'Advertencia crítica',
                    value,
                    GREEN if warning_int == 0 else RED,
                ))

            media_errors = _number(data.get('media_errors'))
            if media_errors is not None:
                rows.append((
                    'Errores medios / integridad',
                    _fmt_int(media_errors),
                    GREEN if int(media_errors) == 0 else RED,
                ))

            error_log_entries = _number(data.get('error_log_entries'))
            if error_log_entries is not None:
                # Es un contador histórico, no significa por sí solo un fallo actual.
                rows.append(('Entradas log de errores', _fmt_int(error_log_entries), TEXT))

            unsafe = _number(data.get('unsafe_shutdowns'))
            if unsafe is not None:
                rows.append(('Apagados inseguros', _fmt_int(unsafe), AMBER if int(unsafe) > 0 else GREEN))
        else:
            for key, title in [
                ('read_errors_uncorrected', 'Lecturas sin corregir'),
                ('write_errors_uncorrected', 'Escrituras sin corregir'),
                ('read_errors_total', 'Errores de lectura'),
                ('write_errors_total', 'Errores de escritura'),
            ]:
                value = _number(data.get(key))
                if value is None:
                    continue
                rows.append((
                    title,
                    _fmt_int(value),
                    GREEN if int(value) == 0 else RED,
                ))

        if not rows:
            message = (
                'Windows o el controlador no expone contadores de error '
                'adicionales para esta unidad.'
            )
            label = ctk.CTkLabel(
                self.error_box,
                text=message,
                font=(FONT, 9), text_color=MUTED, anchor='w',
                justify='left', wraplength=350,
            )
            label.pack(fill='x', pady=3)
            self._error_labels.append(label)
            return

        for title, value, color in rows[:5]:
            self._error_labels.append(
                self._dynamic_row(self.error_box, title, value, color)
            )

    def _set_sensor_rows(self, sensors):
        for label in self._sensor_labels:
            try:
                label.destroy()
            except Exception:
                pass
        self._sensor_labels = []
        if not sensors:
            label = ctk.CTkLabel(self.sensor_box, text='Sensores adicionales: N/A', font=(FONT, 9), text_color=MUTED, anchor='w')
            label.pack(fill='x', pady=2)
            self._sensor_labels.append(label)
            return
        for sensor in sensors[:4]:
            name = str(sensor.get('name') or 'Sensor')
            value = _fmt(sensor.get('value_c'), 1, ' °C')
            label = ctk.CTkLabel(self.sensor_box, text=f'{name}:  {value}', font=(FONT, 9, 'bold'), text_color=TEXT, anchor='w')
            label.pack(fill='x', pady=2)
            self._sensor_labels.append(label)

    def select_disk(self, disk_index):
        self.disk_index = int(disk_index)
        self._load_generation += 1
        self._render(self._snapshot([]))
        self.refresh_reliability()

    def _snapshot(self, reliability_records, nvme_smart=None):
        telemetry = copy.deepcopy(getattr(self.app, 'latest_telemetry', {}) or {})
        disks = copy.deepcopy(getattr(self.app, 'latest_disks', []) or [])
        return build_storage_detail_snapshot(
            self.disk_index,
            telemetry,
            disks,
            reliability_records,
            nvme_smart or {},
        )

    def refresh_reliability(self):
        if not self._alive:
            return
        self._load_generation += 1
        generation = self._load_generation
        telemetry = copy.deepcopy(getattr(self.app, 'latest_telemetry', {}) or {})
        disks = copy.deepcopy(getattr(self.app, 'latest_disks', []) or [])
        job = {'done': threading.Event(), 'records': [], 'nvme_smart': {}, 'error': None, 'generation': generation}
        self._job = job
        self.lbl_loading.configure(text='Consultando SMART / confiabilidad de Windows…')
        self.btn_refresh.configure(state='disabled', text='Leyendo…')

        def worker():
            try:
                job['records'] = get_storage_health()
                physical_index = resolve_physical_disk_index(self.disk_index, telemetry)
                if physical_index is not None:
                    job['nvme_smart'] = query_nvme_health_log(physical_index)
            except Exception as exc:
                job['error'] = str(exc)
            finally:
                job['done'].set()

        threading.Thread(target=worker, daemon=True, name='CorePulse-Storage-Details').start()
        self._poll_job(telemetry, disks, generation)

    def _poll_job(self, telemetry, disks, generation):
        if not self._alive:
            return
        try:
            if not self.frame.winfo_exists():
                self._alive = False
                return
        except Exception:
            self._alive = False
            return
        job = self._job
        if not isinstance(job, dict) or job.get('generation') != generation:
            return
        if not job['done'].is_set():
            self.app.after(120, lambda: self._poll_job(telemetry, disks, generation))
            return

        self.btn_refresh.configure(state='normal', text='Actualizar')
        records = job.get('records') or []
        snapshot = build_storage_detail_snapshot(
            self.disk_index,
            telemetry,
            disks,
            records,
            job.get('nvme_smart') or {},
        )
        self._render(snapshot)
        if job.get('error'):
            self.lbl_loading.configure(text='SMART adicional no disponible; se mantienen los datos monitorizados.')
        elif snapshot.get('nvme_smart_available'):
            self.lbl_loading.configure(text='SMART NVMe leído directamente desde Windows.')
        elif snapshot.get('identity_ambiguous'):
            self.lbl_loading.configure(text='Identidad física ambigua: CorePulse no atribuye SMART a una unidad sin certeza.')
        elif snapshot.get('reliability_available'):
            self.lbl_loading.configure(text='Confiabilidad de Windows actualizada; SMART NVMe directo no disponible.')
        else:
            self.lbl_loading.configure(text='Windows/controlador no expuso contadores SMART adicionales.')

    def _render(self, data):
        model = _display_status(data.get('model'))
        self.lbl_title.configure(text=model)
        subtitle_bits = [f"Disco {data.get('index', self.disk_index)}"]
        if data.get('mount_points') not in (None, '', 'N/A'):
            subtitle_bits.append(str(data.get('mount_points')))
        if _number(data.get('capacity_gb')) is not None:
            subtitle_bits.append(_fmt(data.get('capacity_gb'), 1, ' GB'))
        self.lbl_subtitle.configure(text=' · '.join(subtitle_bits))

        health = _number(data.get('health_percent'))
        critical_warning = _number(data.get('critical_warning'))

        if health is not None:
            health_text = f'{health:.0f}%'
            health_color = _health_color(health)
            health_detail = f"{_health_state(health)} · Fuente: {_display_status(data.get('health_source'))}"
        elif critical_warning is not None:
            warning_int = int(critical_warning)
            health_text = 'OK' if warning_int == 0 else 'REVISAR'
            health_color = GREEN if warning_int == 0 else RED
            health_detail = (
                'SMART NVMe · sin advertencias críticas'
                if warning_int == 0
                else f'SMART NVMe · advertencia 0x{warning_int:02X}'
            )
        else:
            windows_status = _display_status(data.get('windows_health_status'))
            health_text = windows_status
            normalized = windows_status.casefold()
            health_color = GREEN if normalized in {'healthy', 'ok', 'bueno', 'normal'} else MUTED
            health_detail = (
                'Estado cualitativo de Windows · porcentaje N/A'
                if windows_status != 'N/A'
                else 'Porcentaje de salud no reportado'
            )

        self.health_value.configure(text=health_text, text_color=health_color)
        self.health_detail.configure(text=health_detail)

        temp = _number(data.get('temperature_c'))
        self.temp_value.configure(text=_fmt(temp, 0, ' °C'), text_color=_temperature_color(data))
        warning = _number(data.get('warning_temperature_c'))
        critical = _number(data.get('critical_temperature_c'))
        temp_state = _temperature_state(data)
        if warning is not None or critical is not None:
            parts = [temp_state]
            if warning is not None:
                parts.append(f'aviso {warning:.0f} °C')
            if critical is not None:
                parts.append(f'crítico {critical:.0f} °C')
            self.temp_detail.configure(text=' · '.join(parts))
        else:
            self.temp_detail.configure(text=f'{temp_state} · umbral del dispositivo N/A')

        pct = _number(data.get('used_percent'))
        self.space_value.configure(text=_fmt(pct, 1, '%'), text_color=_space_color(pct))
        used = _number(data.get('used_gb'))
        free = _number(data.get('free_gb'))
        parts = []
        if used is not None:
            parts.append(f'{used:.1f} GB usados')
        if free is not None:
            parts.append(f'{free:.1f} GB libres')
        self.space_detail.configure(text=' · '.join(parts) if parts else 'Capacidad utilizada: N/A')

        values = {
            'model': model,
            'mount_points': _display_status(data.get('mount_points')),
            'capacity_gb': _fmt(data.get('capacity_gb'), 2, ' GB'),
            'used_gb': _fmt(data.get('used_gb'), 2, ' GB'),
            'free_gb': _fmt(data.get('free_gb'), 2, ' GB'),
            'interface': _display_status(data.get('interface')),
            'media_type': _display_status(data.get('media_type')),
            'firmware': _display_status(data.get('firmware')),
            'serial': _display_status(data.get('serial')),
        }
        for key, value in values.items():
            label = self._value_labels.get(key)
            if label is not None:
                label.configure(text=value)

        self._set_reliability_rows(data)
        self._set_error_rows(data)
        self._set_sensor_rows(data.get('temperature_sensors') or [])
        sources = data.get('sources') or []
        source_text = ', '.join(sources) if sources else 'N/A'
        self.lbl_sources.configure(text=f'Fuentes: {source_text} · Política REAL_OR_NA')

    def destroy(self):
        self._alive = False
        try:
            self.frame.destroy()
        except Exception:
            pass


def show_storage_details(app, disk_index):
    """Abre la ficha del disco dentro del Dashboard, no en una ventana separada."""
    host, reused = activate_internal_page(app, 'storage_details')
    if reused:
        panel = getattr(app, 'storage_detail_panel', None)
        if panel is not None:
            panel.select_disk(disk_index)
        return panel
    if host is None:
        return None
    panel = None
    try:
        panel = StorageDetailPanel(app, host, disk_index)
        if not commit_internal_page(app, 'storage_details', host, panel=panel):
            return None
        app.storage_detail_panel = panel
        return panel
    except Exception:
        abort_internal_page(app, 'storage_details', host, panel=panel)
        raise


__all__ = ['StorageDetailPanel', 'show_storage_details']
