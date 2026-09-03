"""Vista interna de trazabilidad de telemetría certificada de CorePulse.

La vista consume exclusivamente metadata que ya fue producida por el pipeline de
telemetría. No vuelve a consultar hardware, no estima valores y respeta REAL_OR_NA.
"""
from __future__ import annotations
from core.theme_manager import color as theme_color

from datetime import datetime
import time
import customtkinter as ctk

from core.telemetry_background import get_background_telemetry_status
from gui.internal_navigation import show_dashboard
from gui.stable_scroll import StableScrollHost

BG = theme_color('#06111f')
CARD = theme_color('#0d1828')
CARD_ALT = theme_color('#0a1524')
CARD_HOVER = theme_color(theme_color('#102840'))
BORDER = theme_color('#1b3048')
TEXT = theme_color('#f4f7fb')
TEXT_2 = theme_color('#b8c4d4')
MUTED = theme_color('#7f91a8')
CYAN = '#14b8ff'
GREEN = '#1fd18b'
AMBER = '#f59e0b'
RED = '#ef4444'
FONT = 'Segoe UI'

METRIC_LABELS = {
    'cpu_usage': 'Uso de CPU',
    'cpu_temp': 'Temperatura de CPU',
    'cpu_ghz': 'Frecuencia de CPU',
    'ram_usage': 'Uso de RAM',
    'gpu_usage': 'Uso de GPU',
    'gpu_temp': 'Temperatura de GPU',
    'gpu_vram_gb': 'VRAM total',
}
QUALITY_LABELS = {
    'VALID': 'VÁLIDA',
    'STALE': 'DESACTUALIZADA',
    'UNAVAILABLE': 'N/A',
    'ERROR': 'ERROR',
}
QUALITY_COLORS = {
    'VALID': GREEN,
    'STALE': AMBER,
    'UNAVAILABLE': MUTED,
    'ERROR': RED,
}


def _metric_label(name):
    return METRIC_LABELS.get(str(name), str(name).replace('_', ' ').strip().capitalize())


def _quality_label(value):
    quality = str(value or 'UNAVAILABLE').upper()
    return QUALITY_LABELS.get(quality, quality)


def _quality_color(value):
    return QUALITY_COLORS.get(str(value or 'UNAVAILABLE').upper(), MUTED)


class TelemetryDetailPanel:
    """Expone fuente, sensor, calidad y frescura sin inventar lecturas."""

    def __init__(self, app, host):
        self.app = app
        self.host = host
        self._alive = True
        self._metric_rows = []
        self._selected_metric = None
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
            fg_color='transparent', hover_color=theme_color(theme_color('#102840')), border_width=1, border_color=theme_color(theme_color('#214765')), text_color=TEXT_2,
            font=(FONT, 9, 'bold'), corner_radius=8,
            command=lambda: show_dashboard(self.app),
        ).pack(side='left')
        titles = ctk.CTkFrame(header, fg_color='transparent')
        titles.pack(side='left', fill='x', expand=True, padx=14)
        ctk.CTkLabel(
            titles, text='Trazabilidad de telemetría',
            font=(FONT, 19, 'bold'), text_color=TEXT, anchor='w',
        ).pack(anchor='w')
        ctk.CTkLabel(
            titles,
            text='Comprueba el valor real, su fuente, sensor, calidad y antigüedad antes de usarlo en un diagnóstico.',
            font=(FONT, 10), text_color=TEXT_2, anchor='w',
        ).pack(anchor='w', pady=(1, 0))
        ctk.CTkButton(
            header, text='Actualizar', width=92, height=30, fg_color=theme_color('#164f7d'),
            hover_color=theme_color('#1b5c8f'), text_color=TEXT, font=(FONT, 10, 'bold'),
            command=self.refresh,
        ).pack(side='right')

        self.status_row = ctk.CTkFrame(self.frame, fg_color='transparent')
        self.status_row.pack(fill='x', padx=18, pady=(2, 9))
        self.provider_card, self.provider_value, self.provider_detail = self._status_card(
            'PROVEEDOR', 'N/A', 'Estado del proveedor de sensores', CYAN
        )
        self.coverage_card, self.coverage_value, self.coverage_detail = self._status_card(
            'COBERTURA', 'N/A', 'Métricas certificadas', GREEN
        )
        self.freshness_card, self.freshness_value, self.freshness_detail = self._status_card(
            'ACTUALIZACIÓN', 'N/A', 'Antigüedad de la última muestra', CYAN
        )
        self.sensors_card, self.sensors_value, self.sensors_detail = self._status_card(
            'SENSORES', 'N/A', 'Lecturas enumeradas', CYAN
        )
        cards = (self.provider_card, self.coverage_card, self.freshness_card, self.sensors_card)
        for index, card in enumerate(cards):
            card.pack(side='left', fill='both', expand=True, padx=(0 if index == 0 else 5, 0 if index == 3 else 5))

        body = ctk.CTkFrame(self.frame, fg_color='transparent')
        body.pack(fill='both', expand=True, padx=18, pady=(0, 10))
        body.grid_columnconfigure(0, weight=3, uniform='telemetry')
        body.grid_columnconfigure(1, weight=2, uniform='telemetry')
        body.grid_rowconfigure(0, weight=1)

        table = ctk.CTkFrame(body, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=12)
        table.grid(row=0, column=0, sticky='nsew', padx=(0, 5))
        ctk.CTkLabel(
            table, text='MÉTRICAS CERTIFICADAS', font=(FONT, 9, 'bold'),
            text_color=TEXT_2,
        ).pack(anchor='w', padx=12, pady=(10, 6))

        headings = ctk.CTkFrame(table, fg_color=CARD_ALT, height=30, corner_radius=6)
        headings.pack(fill='x', padx=10, pady=(0, 4))
        headings.pack_propagate(False)
        for text, width in [('Métrica', 145), ('Valor', 105), ('Estado', 92), ('Fuente', 210), ('Edad', 70)]:
            ctk.CTkLabel(
                headings, text=text, width=width, font=(FONT, 8, 'bold'),
                text_color=MUTED, anchor='w',
            ).pack(side='left', padx=(8, 0))

        self.scroll_host = StableScrollHost(table, fg_color=CARD)
        self.scroll_host.pack(fill='both', expand=True, padx=5, pady=(0, 7))
        self.scroll = self.scroll_host.content

        inspector = ctk.CTkFrame(body, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=12)
        inspector.grid(row=0, column=1, sticky='nsew', padx=(5, 0))
        ctk.CTkLabel(
            inspector, text='DETALLE DE LA MÉTRICA', font=(FONT, 9, 'bold'),
            text_color=TEXT_2,
        ).pack(anchor='w', padx=14, pady=(11, 7))
        self.inspector_name = ctk.CTkLabel(
            inspector, text='Selecciona una métrica', font=(FONT, 17, 'bold'),
            text_color=TEXT, anchor='w', justify='left', wraplength=360,
        )
        self.inspector_name.pack(fill='x', padx=14, pady=(1, 2))
        self.inspector_value = ctk.CTkLabel(
            inspector, text='—', font=(FONT, 27, 'bold'), text_color=CYAN, anchor='w',
        )
        self.inspector_value.pack(fill='x', padx=14, pady=(0, 10))
        self.inspector_rows = ctk.CTkFrame(inspector, fg_color='transparent')
        self.inspector_rows.pack(fill='both', expand=True, padx=14, pady=(0, 8))
        self.inspector_labels = {}
        for key, label in [
            ('quality', 'Estado'),
            ('source', 'Proveedor / fuente'),
            ('sensor', 'Sensor'),
            ('freshness', 'Frescura'),
            ('timestamp', 'Última lectura'),
            ('internal', 'ID interno'),
        ]:
            row = ctk.CTkFrame(self.inspector_rows, fg_color='transparent', height=34)
            row.pack(fill='x', pady=1)
            row.pack_propagate(False)
            ctk.CTkLabel(row, text=label, width=118, font=(FONT, 8), text_color=MUTED, anchor='w').pack(side='left')
            value = ctk.CTkLabel(
                row, text='N/A', font=(FONT, 9, 'bold'), text_color=TEXT_2,
                anchor='w', justify='left', wraplength=245,
            )
            value.pack(side='left', fill='x', expand=True)
            self.inspector_labels[key] = value
        self.inspector_note = ctk.CTkLabel(
            inspector,
            text='CorePulse no reemplaza una lectura ausente por cero ni por un valor estimado.',
            font=(FONT, 8), text_color=MUTED, justify='left', anchor='w', wraplength=350,
        )
        self.inspector_note.pack(fill='x', padx=14, pady=(2, 12))

        footer = ctk.CTkFrame(self.frame, fg_color='transparent')
        footer.pack(fill='x', padx=18, pady=(0, 12))
        self.lbl_status = ctk.CTkLabel(footer, text='', font=(FONT, 9, 'bold'), text_color=CYAN, anchor='w')
        self.lbl_status.pack(side='left')
        ctk.CTkLabel(
            footer,
            text='Política de integridad: valor real o N/A.',
            font=(FONT, 8), text_color=MUTED, anchor='e',
        ).pack(side='right')

    def _status_card(self, title, value, detail, accent):
        card = ctk.CTkFrame(
            self.status_row, fg_color=CARD, border_width=1,
            border_color=BORDER, corner_radius=12, height=92,
        )
        card.pack_propagate(False)
        ctk.CTkLabel(card, text=title, font=(FONT, 9, 'bold'), text_color=TEXT_2).pack(anchor='w', padx=12, pady=(9, 0))
        value_label = ctk.CTkLabel(card, text=value, font=(FONT, 18, 'bold'), text_color=accent)
        value_label.pack(anchor='w', padx=12)
        detail_label = ctk.CTkLabel(card, text=detail, font=(FONT, 8), text_color=MUTED)
        detail_label.pack(anchor='w', padx=12, pady=(0, 7))
        return card, value_label, detail_label

    @staticmethod
    def _age_seconds(timestamp):
        try:
            return max(0.0, time.time() - float(timestamp))
        except Exception:
            return None

    @classmethod
    def _age_text(cls, timestamp):
        age = cls._age_seconds(timestamp)
        if age is None:
            return 'N/A'
        if age < 1:
            return '< 1 s'
        if age < 60:
            return f'{age:.1f} s'
        return f'{age / 60.0:.1f} min'

    @staticmethod
    def _timestamp_text(timestamp):
        try:
            return datetime.fromtimestamp(float(timestamp)).strftime('%H:%M:%S')
        except Exception:
            return 'N/A'

    @staticmethod
    def _metric_timestamp(meta, snapshot_timestamp=None):
        """Prioriza la marca del sensor y usa el snapshot como respaldo trazable."""
        if not isinstance(meta, dict):
            return snapshot_timestamp
        for candidate in (
            meta.get('sensor_timestamp'),
            meta.get('timestamp'),
            meta.get('snapshot_timestamp'),
            snapshot_timestamp,
        ):
            try:
                if candidate is not None and float(candidate) > 0:
                    return float(candidate)
            except Exception:
                continue
        return None

    @staticmethod
    def _display_value(meta):
        value = meta.get('value')
        unit = str(meta.get('unit') or '').strip()
        if value is None:
            return 'N/A'
        return f'{value} {unit}'.strip()

    def _clear_rows(self):
        for widget in self._metric_rows:
            try:
                widget.destroy()
            except Exception:
                pass
        self._metric_rows.clear()

    def _bind_row_interaction(self, widget, row, name, meta, snapshot_timestamp=None):
        def enter(_event=None):
            try:
                row.configure(fg_color=CARD_HOVER)
            except Exception:
                pass

        def leave(_event=None):
            try:
                row.configure(fg_color='transparent')
            except Exception:
                pass

        def select(_event=None):
            self._select_metric(name, meta, snapshot_timestamp)

        try:
            widget.configure(cursor='hand2')
        except Exception:
            pass
        try:
            widget.bind('<Enter>', enter, add='+')
            widget.bind('<Leave>', leave, add='+')
            widget.bind('<Button-1>', select, add='+')
        except Exception:
            pass

    def _metric_row(self, name, meta, snapshot_timestamp=None):
        row = ctk.CTkFrame(self.scroll, fg_color='transparent', height=42, corner_radius=6)
        row.pack(fill='x', padx=4, pady=1)
        row.pack_propagate(False)
        self._metric_rows.append(row)

        quality = str(meta.get('quality') or 'UNAVAILABLE').upper()
        source = str(meta.get('source') or 'N/A')
        sensor = str(meta.get('sensor') or '').strip()
        source_short = source
        if source == 'LibreHardwareMonitorLib':
            source_short = 'LibreHardwareMonitor'
        if sensor and source_short == 'N/A':
            source_short = sensor

        labels = [
            ctk.CTkLabel(row, text=_metric_label(name), width=145, font=(FONT, 9, 'bold'), text_color=TEXT, anchor='w'),
            ctk.CTkLabel(row, text=self._display_value(meta), width=105, font=(FONT, 9), text_color=TEXT_2, anchor='w'),
            ctk.CTkLabel(row, text=_quality_label(quality), width=92, font=(FONT, 8, 'bold'), text_color=_quality_color(quality), anchor='w'),
            ctk.CTkLabel(row, text=source_short, width=210, font=(FONT, 8), text_color=TEXT_2, anchor='w'),
            ctk.CTkLabel(row, text=self._age_text(self._metric_timestamp(meta, snapshot_timestamp)), width=70, font=(FONT, 8), text_color=MUTED, anchor='w'),
        ]
        for label in labels:
            label.pack(side='left', padx=(8, 0))
            self._bind_row_interaction(label, row, name, meta, snapshot_timestamp)
        self._bind_row_interaction(row, row, name, meta, snapshot_timestamp)

    def _select_metric(self, name, meta, snapshot_timestamp=None):
        self._selected_metric = str(name)
        quality = str(meta.get('quality') or 'UNAVAILABLE').upper()
        source = str(meta.get('source') or 'N/A')
        sensor = str(meta.get('sensor') or '').strip() or 'N/A'
        error = str(meta.get('error') or '').strip()

        self.inspector_name.configure(text=_metric_label(name))
        self.inspector_value.configure(text=self._display_value(meta), text_color=_quality_color(quality) if quality != 'VALID' else CYAN)
        self.inspector_labels['quality'].configure(text=_quality_label(quality), text_color=_quality_color(quality))
        self.inspector_labels['source'].configure(text=source)
        self.inspector_labels['sensor'].configure(text=sensor)
        metric_stamp = self._metric_timestamp(meta, snapshot_timestamp)
        self.inspector_labels['freshness'].configure(text=self._age_text(metric_stamp))
        self.inspector_labels['timestamp'].configure(text=self._timestamp_text(metric_stamp))
        self.inspector_labels['internal'].configure(text=str(name))
        if error:
            self.inspector_note.configure(text=f'Error reportado por la fuente: {error}', text_color=RED)
        else:
            self.inspector_note.configure(
                text='CorePulse no reemplaza una lectura ausente por cero ni por un valor estimado.',
                text_color=MUTED,
            )

    def refresh(self):
        if not self._alive:
            return
        telemetry = getattr(self.app, 'latest_telemetry', None)
        if not isinstance(telemetry, dict):
            telemetry = {}
        metrics = telemetry.get('_metrics') if isinstance(telemetry.get('_metrics'), dict) else {}
        summary = telemetry.get('_sensor_summary') if isinstance(telemetry.get('_sensor_summary'), dict) else {}
        status = get_background_telemetry_status()
        certification = telemetry.get('_telemetry_certification') if isinstance(telemetry.get('_telemetry_certification'), dict) else {}
        snapshot_stamp = telemetry.get('_snapshot_timestamp') or certification.get('snapshot_timestamp') or summary.get('timestamp')

        valid = sum(1 for meta in metrics.values() if isinstance(meta, dict) and str(meta.get('quality') or '').upper() == 'VALID')
        total = sum(1 for meta in metrics.values() if isinstance(meta, dict))
        provider = str(summary.get('provider') or 'N/A')
        provider_available = bool(summary.get('provider_available'))
        provider_error = str(summary.get('provider_error') or '').strip()
        age = status.get('snapshot_age_seconds')
        sensor_count = summary.get('sensor_count')

        provider_display = 'LibreHardwareMonitor' if provider == 'LibreHardwareMonitorLib' else provider
        self.provider_value.configure(text=provider_display, text_color=GREEN if provider_available else AMBER)
        self.provider_detail.configure(text='ACTIVO' if provider_available else (provider_error[:48] if provider_error else 'NO DISPONIBLE'))

        if total:
            percent = round(valid / total * 100.0)
            self.coverage_value.configure(text=f'{valid} / {total}', text_color=GREEN if valid == total else CYAN if valid else MUTED)
            self.coverage_detail.configure(text=f'{percent}% de métricas válidas')
        else:
            self.coverage_value.configure(text='N/A', text_color=MUTED)
            self.coverage_detail.configure(text='Sin métricas certificadas')

        if isinstance(age, (int, float)):
            self.freshness_value.configure(text='< 1 s' if age < 1 else f'{float(age):.1f} s', text_color=GREEN if age <= 2.5 else AMBER)
            self.freshness_detail.configure(text='EN TIEMPO REAL' if age <= 2.5 else 'LECTURA CON RETRASO')
        else:
            self.freshness_value.configure(text='N/A', text_color=MUTED)
            self.freshness_detail.configure(text='Sin muestra disponible')

        self.sensors_value.configure(text=str(sensor_count) if isinstance(sensor_count, int) else 'N/A')
        self.sensors_detail.configure(text='sensores enumerados' if isinstance(sensor_count, int) else 'Sin inventario de sensores')

        self._clear_rows()
        first = None
        for name in sorted(metrics, key=lambda key: list(METRIC_LABELS).index(key) if key in METRIC_LABELS else 999):
            meta = metrics.get(name)
            if isinstance(meta, dict):
                self._metric_row(name, meta, snapshot_stamp)
                if first is None:
                    first = (name, meta)
        if not metrics:
            empty = ctk.CTkLabel(
                self.scroll, text='Aún no existe metadata de telemetría disponible.',
                font=(FONT, 10), text_color=MUTED,
            )
            empty.pack(anchor='w', padx=12, pady=14)
            self._metric_rows.append(empty)
            self.inspector_name.configure(text='Sin métricas disponibles')
            self.inspector_value.configure(text='N/A', text_color=MUTED)
        else:
            selected = metrics.get(self._selected_metric) if self._selected_metric else None
            if isinstance(selected, dict):
                self._select_metric(self._selected_metric, selected, snapshot_stamp)
            elif first:
                self._select_metric(first[0], first[1], snapshot_stamp)

        stamp = datetime.now().strftime('%H:%M:%S')
        worker_text = 'activo' if status.get('worker_alive') else 'detenido'
        self.lbl_status.configure(text=f'Servicio de telemetría {worker_text} · vista actualizada {stamp}')
