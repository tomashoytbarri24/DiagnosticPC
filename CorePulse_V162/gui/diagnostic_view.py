"""Gestiona la experiencia visual del diagnóstico y la exportación del resultado a PDF."""
from __future__ import annotations
from core.theme_manager import color as theme_color
# Código refactorizado: nombres estables y documentación en español.
import math
import threading
import time
import tkinter as tk
import customtkinter as ctk
from core.adaptive_diagnostic import readiness_stage
from core.device_identity import collect_device_identity
from core.diagnostic_summary import build_component_assessments, build_component_evidence, build_diagnostic_overview, select_priority_assessment
from core.version import VERSION_LABEL
from gui.professional_visuals import build_title_block
from gui.stable_scroll import StableScrollHost
VERSION = VERSION_LABEL
DESIGN_ID = 'COREPULSE_PRO_DIAGNOSTIC'
BG = theme_color('#08111f')
SURFACE = theme_color('#0d1828')
SURFACE_2 = theme_color('#101d2e')
SURFACE_3 = theme_color('#0b1524')
BORDER = theme_color('#1b3048')
TEXT = theme_color('#f4f7fb')
DIM = theme_color('#aebdd0')
MUTED = theme_color('#72849b')
CYAN = '#21c7ff'
GREEN = '#22c993'
YELLOW = '#f2b84b'
RED = '#f05d68'
PURPLE = '#a855f7'
STATUS_COLORS = {'NORMAL': GREEN, 'WARNING': YELLOW, 'CRITICAL': RED, 'NO_EVALUABLE': DIM, 'INFO': CYAN}
STATUS_LABELS = {'NORMAL': 'Sistema estable', 'WARNING': 'Requiere revisión', 'CRITICAL': 'Atención inmediata', 'NO_EVALUABLE': 'Evidencia limitada', 'INFO': 'Solo informativo'}
STATUS_PRIORITY = {'CRITICAL': 0, 'WARNING': 1, 'NORMAL': 2, 'INFO': 3, 'NO_EVALUABLE': 4}

def _number(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    return None

def _pct(value):
    value = _number(value)
    if value is None:
        return 0.0
    return max(0.0, min(100.0, value))

def _fmt(value, digits=1, suffix=''):
    value = _number(value)
    if value is None:
        return 'N/A'
    return f'{value:.{digits}f}{suffix}'

def _device_display(identity):
    identity = identity if isinstance(identity, dict) else {}
    form = str(identity.get('form_factor') or 'UNKNOWN').upper()
    model = str(identity.get('model') or '').strip()
    display_model = str(identity.get('display_model') or '').strip()
    if form == 'LAPTOP':
        name = model or display_model
        return (name or 'Modelo no disponible', 'LAPTOP')
    if form == 'DESKTOP':
        board = identity.get('motherboard') if isinstance(identity.get('motherboard'), dict) else {}
        board_name = ' '.join((str(x).strip() for x in (board.get('manufacturer'), board.get('model')) if str(x or '').strip())).strip()
        name = board_name or display_model or model
        return (name or 'Modelo no disponible', 'DESKTOP')
    name = display_model or model
    return (name or 'Modelo no disponible', 'EQUIPO')

def _session_stat(result, component, metric):
    try:
        statistics = result.get('statistics') or {}
        component_stats = statistics.get(component) or {}
        block = component_stats.get(metric) or {}
        avg = _number(block.get('avg'))
        minimum = _number(block.get('min'))
        maximum = _number(block.get('max'))
        samples = int(block.get('samples') or 0)
        if samples <= 0 or avg is None:
            return None
        return {'avg': avg, 'min': minimum, 'max': maximum, 'samples': samples}
    except Exception:
        return None

def _result_findings(result):
    findings = list(result.get('findings') or [])
    findings.sort(key=lambda f: (STATUS_PRIORITY.get(str(f.get('status') or 'INFO').upper(), 9), str(f.get('component') or '')))
    return findings

def _finding_lines(result, limit=4):
    lines = []
    for finding in _result_findings(result)[:limit]:
        status = str(finding.get('status') or 'INFO').upper()
        comp = str(finding.get('component') or 'Componente')
        title = str(finding.get('title') or 'Hallazgo')
        lines.append({'status': status, 'text': f'{comp} · {title}'})
    if not lines:
        lines.append({'status': 'INFO', 'text': 'No hay hallazgos registrados para esta sesión.'})
    return lines

def _interpretation_text(result):
    status = str(result.get('overall_status') or 'NO_EVALUABLE').upper()
    findings = _result_findings(result)
    session_valid = bool(result.get('session_valid'))
    findings_count = len(findings)
    if status == 'CRITICAL':
        return 'Se detectó al menos una condición crítica sostenida. Revisa prioritariamente los hallazgos marcados en rojo antes de continuar con cargas exigentes.'
    if status == 'WARNING':
        return 'La sesión reunió evidencia suficiente y detectó condiciones que conviene revisar. No implica fallo inmediato, pero sí seguimiento recomendado.'
    if status == 'NORMAL':
        return 'La sesión no mostró condiciones sostenidas de riesgo en los componentes evaluables. El comportamiento observado fue estable dentro de esta captura.'
    base = 'La evidencia recopilada fue insuficiente o parcial para clasificar todas las áreas evaluadas.'
    if not session_valid:
        base += ' La sesión no alcanzó la ventana de validación esperada.'
    elif findings_count == 0:
        base += ' No se registraron hallazgos interpretables.'
    return base

def _observed_metrics(result):
    statistics = result.get('statistics') or {}
    cpu_temp = _session_stat(result, 'cpu', 'package_temp_c')
    cpu_clock = _session_stat(result, 'cpu', 'clock_avg_ghz')
    gpu_count = len(statistics.get('gpus') or {})
    storage_count = len(statistics.get('storage') or {})
    metrics = [('CPU máx', _fmt(cpu_temp.get('max') if cpu_temp else None, 1, ' °C')), ('CPU GHz prom', _fmt(cpu_clock.get('avg') if cpu_clock else None, 2, ' GHz')), ('GPU monitoreadas', str(gpu_count)), ('Unidades', str(storage_count))]
    return metrics

def _progress_hint(info):
    waiting = list(info.get('waiting_for') or [])
    if waiting:
        human = ' · '.join((str(x).capitalize() for x in waiting[:3]))
        return f'CorePulse está: {human}.'
    return 'La evidencia mínima requerida está completa.'

def _complete_findings(result, limit=4):
    complete = result.get('complete_diagnostic') if isinstance(result.get('complete_diagnostic'), dict) else {}
    additional = [x for x in (complete.get('additional_findings') or []) if isinstance(x, dict)]
    if not additional:
        return _finding_lines(result, limit=limit)
    additional.sort(key=lambda f: (STATUS_PRIORITY.get(str(f.get('status') or 'INFO').upper(), 9), str(f.get('component') or '')))
    lines = []
    for finding in additional[:limit]:
        status = str(finding.get('status') or 'INFO').upper()
        comp = str(finding.get('component') or 'Área')
        title = str(finding.get('title') or 'Hallazgo')
        lines.append({'status': status, 'text': f'{comp} · {title}'})
    return lines or _finding_lines(result, limit=limit)

def _phase_statuses(result):
    complete = result.get('complete_diagnostic') if isinstance(result.get('complete_diagnostic'), dict) else {}
    windows = complete.get('windows') if isinstance(complete.get('windows'), dict) else {}
    phases = complete.get('phases') or {}
    return [(label, str((phases.get(key) or {}).get('status') or 'N/A'))
            for key, label in (('desktop', 'Escritorio'), ('windows', 'Windows'),
                               ('benchmark', 'Benchmark'), ('load_observation', 'Bajo carga'))]


def _running_phase_values(state):
    """Actividad real del worker; no deduce fases desde porcentajes estimados."""
    state = getattr(state, 'value', state)
    return {
        'RUNNING_HARDWARE': ['✓', '○', '○', '○'],
        'RUNNING_WINDOWS': ['✓', '●', '○', '○'],
        'RUNNING_BENCHMARK': ['✓', '✓', '●', '●'],
        'ANALYZING_BENCHMARK': ['✓', '✓', '✓', '●'],
        'CORRELATING': ['✓', '✓', '✓', '✓'],
    }.get(state, ['●', '○', '○', '○'])


def _worst_finding_for(result, components):
    wanted = {str(x).upper() for x in components}
    matches = []
    for finding in _result_findings(result):
        component = str(finding.get('component') or '').upper()
        if component in wanted:
            matches.append(finding)
    return matches[0] if matches else None


def _status_from_finding(finding, fallback='NORMAL'):
    if not isinstance(finding, dict):
        return fallback
    status = str(finding.get('status') or fallback).upper()
    return status if status in STATUS_COLORS else fallback


def _metric_from_summary(summary, metric, field='max'):
    if not isinstance(summary, dict):
        return None
    block = summary.get(metric) if isinstance(summary.get(metric), dict) else {}
    return _number(block.get(field))


def _component_reports(result):
    """Compatibilidad V143+: Salud, Benchmark y Telemetría desde la interpretación centralizada V146."""
    return build_component_assessments(result if isinstance(result, dict) else {})

def _complete_interpretation(result):
    status = str(result.get('overall_status') or 'NO_EVALUABLE').upper()
    complete = result.get('complete_diagnostic') if isinstance(result.get('complete_diagnostic'), dict) else {}
    benchmark = complete.get('benchmark') if isinstance(complete.get('benchmark'), dict) else {}
    if benchmark.get('safety_stop'):
        return 'CorePulse detuvo una carga por seguridad. Revisa la evidencia térmica antes de repetir pruebas exigentes; ninguna reparación se ejecutó automáticamente.'
    if status == 'CRITICAL':
        return 'El diagnóstico completo encontró evidencia crítica en al menos una fase. Usa Ver evidencia y los módulos de reparación sólo para las acciones que decidas realizar.'
    if status == 'WARNING':
        return 'El diagnóstico completo encontró condiciones que conviene revisar. Salud, estabilidad y rendimiento se mantienen separados para no confundir una medición baja con un fallo físico.'
    if status == 'NORMAL':
        return 'Escritorio, Windows y benchmark finalizaron sin anomalías observadas entre las áreas evaluables. El PDF es opcional.'
    return 'Una o más fases no pudieron evaluarse por completo. CorePulse conserva N/A donde falta evidencia y no convierte un fallo de medición en un fallo de hardware.'

class DiagnosticGauge(tk.Canvas):

    def __init__(self, parent, size=254):
        super().__init__(parent, width=size, height=size, bg=BG, highlightthickness=0, bd=0)
        self.size = size
        self.progress = 0.0
        self.stage = 'Preparando evidencia'
        self.value_text = '0%'
        self.sub_text = 'Evidencia real'
        self.accent = CYAN
        # V148: el Canvas no se repinta por cada pixel durante el resize. Tk
        # puede emitir cientos de <Configure> al arrastrar un borde; un solo
        # repaint diferido mantiene el movimiento de la ventana fluido.
        self._redraw_after = None
        self._pending_canvas_size = None
        self._last_canvas_size = None
        self.bind('<Configure>', self._schedule_configure_redraw, add='+')

    def _schedule_configure_redraw(self, event=None):
        try:
            size = (int(getattr(event, 'width', 0) or self.winfo_width()),
                    int(getattr(event, 'height', 0) or self.winfo_height()))
        except Exception:
            size = None
        if size and size == self._last_canvas_size:
            return
        self._pending_canvas_size = size
        if self._redraw_after is not None:
            return
        try:
            self._redraw_after = self.after(72, self._flush_configure_redraw)
        except Exception:
            self._redraw_after = None

    def _flush_configure_redraw(self):
        self._redraw_after = None
        self._last_canvas_size = self._pending_canvas_size
        self.redraw()

    def set_state(self, progress, stage, value_text=None, sub_text=None, accent=None):
        self.progress = _pct(progress)
        self.stage = str(stage or 'Analizando evidencia')
        self.value_text = str(value_text if value_text is not None else f'{self.progress:.0f}%')
        self.sub_text = str(sub_text or 'Evidencia real')
        self.accent = accent or CYAN
        self.redraw()

    def redraw(self):
        self.delete('all')
        w = max(210, int(self.winfo_width() or self.size))
        h = max(210, int(self.winfo_height() or self.size))
        size = min(w, h)
        cx, cy = (w / 2, h / 2 + 5)
        r = size * 0.34
        lw = max(10, int(size * 0.04))
        start = 150
        extent_total = 240
        box = (cx - r, cy - r, cx + r, cy + r)
        self.create_arc(*box, start=start, extent=-extent_total, style='arc', width=lw, outline=theme_color('#172a42'))
        for i in range(9):
            angle = math.radians(start - extent_total * i / 8)
            rr1 = r - lw * 0.78
            rr2 = r + lw * 0.78
            x1 = cx + math.cos(angle) * rr1
            y1 = cy - math.sin(angle) * rr1
            x2 = cx + math.cos(angle) * rr2
            y2 = cy - math.sin(angle) * rr2
            self.create_line(x1, y1, x2, y2, fill=theme_color('#0b1626'), width=2)
        progress_extent = -extent_total * (self.progress / 100.0)
        if self.progress > 0:
            self.create_arc(*box, start=start, extent=progress_extent, style='arc', width=lw, outline=self.accent)
            end_angle = math.radians(start + progress_extent)
            ex = cx + math.cos(end_angle) * r
            ey = cy - math.sin(end_angle) * r
            dot = max(4, lw // 3)
            self.create_oval(ex - dot, ey - dot, ex + dot, ey + dot, fill=self.accent, outline='')
        value_size = max(24, int(size * 0.09))
        if len(self.value_text) > 9:
            value_size = max(20, int(size * 0.062))
        self.create_text(cx, cy - 33, text=self.stage.upper(), fill=DIM, font=('Segoe UI', max(8, int(size * 0.028)), 'bold'))
        self.create_text(cx, cy + 2, text=self.value_text, fill=TEXT, font=('Segoe UI', value_size, 'bold'))
        self.create_text(cx, cy + 39, text=self.sub_text, fill=self.accent, font=('Segoe UI', max(8, int(size * 0.026)), 'bold'))

class DiagnosticExperiencePanel(ctk.CTkFrame):

    def __init__(self, app):
        parent = getattr(app, '_internal_page_build_host', None) or getattr(app, '_internal_page_host', None) or getattr(app, 'main_content', app)
        super().__init__(parent, fg_color=BG, corner_radius=0)
        self.app = app
        self._closed = False
        self._finished = False
        self._identity_name = 'Modelo no disponible'
        self._identity_type = 'EQUIPO'
        self._finding_rows = []
        self._observed_title_labels = []
        self._observed_value_labels = []
        self._layout_mode = None
        self._layout_after = None
        self._last_viewport_size = None
        self._last_layout_signature = None
        self._pending_layout_signature = None
        self.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.lift()
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build_header()
        self._build_body()
        self.bind('<Configure>', self._on_panel_configure, add='+')
        self.after(60, self._apply_responsive_layout)
        self._load_identity_async()

    @staticmethod
    def _layout_signature_for(width, height):
        """Devuelve sólo los breakpoints que realmente cambian la composición.

        V148 evita ligar el layout al tamaño exacto de cada pixel. Mientras el
        usuario arrastra un borde, Tk se encarga de estirar los contenedores;
        CorePulse sólo recompone widgets al cruzar un breakpoint o al terminar.
        """
        if width >= 1320:
            mode = 'wide'
        elif width >= 900:
            mode = 'medium'
        else:
            mode = 'compact'
        columns = 3 if width >= 1320 else 2 if width >= 830 else 1
        low_height = bool(height < 660)
        return (mode, columns, low_height)

    def _on_panel_configure(self, event=None):
        """Fast path de resize: no reconstruye tarjetas en cada pixel."""
        if self._closed:
            return
        try:
            if event is not None and event.widget is not self:
                return
            width = max(1, int(getattr(event, 'width', 0) or self.winfo_width()))
            height = max(1, int(getattr(event, 'height', 0) or self.winfo_height()))
        except Exception:
            return
        size = (width, height)
        if size == self._last_viewport_size:
            return
        self._last_viewport_size = size
        signature = self._layout_signature_for(width, height)
        self._pending_layout_signature = signature

        # Durante un drag continuo no se cancela/reagenda una cascada de grids.
        # Sólo un cruce real de breakpoint merece una recomposición inmediata.
        if signature != self._last_layout_signature and self._layout_after is None:
            try:
                self._layout_after = self.after_idle(self._apply_responsive_layout)
            except Exception:
                self._layout_after = None
                self._apply_responsive_layout()
        elif not getattr(self.app, 'is_resizing', False) and self._layout_after is None:
            try:
                self._layout_after = self.after_idle(self._apply_responsive_layout)
            except Exception:
                self._layout_after = None

    def on_viewport_settled(self):
        """Llamado por la autoridad global cuando termina el gesto de resize."""
        if self._closed:
            return
        self._apply_responsive_layout(force=True)
        try:
            self.details_scroll._schedule_geometry(1)
        except Exception:
            pass

    def _apply_responsive_layout(self, force=False):
        """Responsive V148 por breakpoints, sin trabajo pesado por pixel."""
        self._layout_after = None
        if self._closed:
            return
        try:
            width = max(1, int(self.winfo_width()))
            height = max(1, int(self.winfo_height()))
        except Exception:
            return
        signature = self._layout_signature_for(width, height)
        mode, columns, low_height = signature
        if (not force) and signature == self._last_layout_signature:
            return

        if mode == 'wide':
            left_width, left_height, gauge_size = 376, 430, 238
            left_weight, right_weight = 7, 17
        elif mode == 'medium':
            left_width, left_height, gauge_size = 330, 414, 220
            left_weight, right_weight = 6, 16
        else:
            # Modo ventana: la columna visual cede espacio al informe sin
            # desaparecer ni reducir la legibilidad del gauge.
            left_width, left_height, gauge_size = 270, 386, 196
            left_weight, right_weight = 5, 17

        if low_height:
            left_height = max(352, left_height - 30)
            gauge_size = max(186, gauge_size - 12)

        try:
            self._shell.grid_columnconfigure(0, weight=left_weight)
            self._shell.grid_columnconfigure(1, weight=right_weight)
            self._gauge_side.configure(width=left_width, height=left_height)
            self.gauge.configure(width=gauge_size, height=gauge_size)
            self.lbl_quality.configure(wraplength=max(210, left_width - 30))
            self.lbl_hint.configure(wraplength=max(210, left_width - 30))
            self._left_outer.grid_configure(
                padx=(6, 3) if mode == 'compact' else ((9, 4) if mode == 'medium' else (12, 6)),
                pady=7 if low_height else 8,
            )
        except Exception:
            pass

        try:
            for col in range(3):
                self.component_report.grid_columnconfigure(
                    col, weight=1 if col < columns else 0, uniform='diag_component'
                )
            self.priority_card.grid_configure(columnspan=columns)
            self.evidence_card.grid_configure(columnspan=columns)
            for idx, key in enumerate(('cpu', 'gpu', 'ram', 'storage', 'battery', 'windows')):
                refs = self._component_cards.get(key)
                if not refs:
                    continue
                row, col = divmod(idx, columns)
                row += 2
                left_pad = 0 if col == 0 else 3
                right_pad = 0 if col == columns - 1 else 3
                refs['card'].grid_configure(
                    row=row, column=col, sticky='nsew',
                    padx=(left_pad, right_pad), pady=3,
                )
                if columns == 3:
                    wrap = 220
                elif columns == 2:
                    wrap = 300 if mode == 'wide' else 260
                else:
                    wrap = 430
                refs['summary'].configure(wraplength=wrap)
                refs['evidence'].configure(wraplength=wrap)
        except Exception:
            pass

        self._last_layout_signature = signature
        self._layout_mode = signature
        try:
            self.details_scroll._schedule_geometry(0 if not getattr(self.app, 'is_resizing', False) else 90)
        except Exception:
            pass

    def _load_identity_async(self):
        cached = getattr(self.app, '_device_identity_cache', None)
        if isinstance(cached, dict):
            self._apply_identity(cached)
            return

        def worker():
            try:
                identity = collect_device_identity()
            except Exception:
                identity = {}
            try:
                self.app._device_identity_cache = identity
            except Exception:
                pass
            try:
                self.after(0, lambda: self._apply_identity(identity))
            except Exception:
                pass
        threading.Thread(target=worker, daemon=True, name='CorePulse-DeviceIdentity').start()

    def _apply_identity(self, identity):
        if self._closed:
            return
        self._identity_name, self._identity_type = _device_display(identity)
        prefix = 'Equipo analizado:' if self._finished else 'Analizando'
        self.lbl_device.configure(text=f'{prefix} {self._identity_name} · {self._identity_type}')

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color='transparent')
        header.grid(row=0, column=0, sticky='ew', padx=6, pady=(0, 2))
        header.grid_columnconfigure(0, weight=1)
        left = ctk.CTkFrame(header, fg_color='transparent')
        left.grid(row=0, column=0, sticky='w')
        hero = build_title_block(
            left,
            eyebrow='Diagnóstico certificado',
            title='Diagnóstico del sistema',
            subtitle='Evidencia real del sistema · sin valores simulados.',
            accent=CYAN,
            badges=(('REAL_OR_NA', GREEN), ('Trazabilidad', CYAN), ('Sin simulación', YELLOW)),
            title_size=21,
        )
        hero['frame'].pack(anchor='w')
        self.lbl_title = hero['title']
        self.lbl_subtitle = hero['subtitle']
        self.lbl_device = ctk.CTkLabel(left, text='Analizando equipo · identificando modelo real…', font=('Segoe UI', 9, 'bold'), text_color=CYAN, anchor='w')
        self.lbl_device.pack(anchor='w', pady=(4, 0))
        self.btn_sensors = ctk.CTkButton(
            header, text='Sensores y compatibilidad', width=168, height=32, corner_radius=8,
            fg_color=theme_color('#102a3d'), hover_color=theme_color('#174e72'),
            border_width=1, border_color=theme_color('#20506d'), text_color=TEXT,
            font=('Segoe UI', 8, 'bold'), command=self._open_sensor_compatibility
        )
        self.btn_sensors.grid(row=0, column=1, sticky='e', padx=(10, 0))
        self.btn_cancel = ctk.CTkButton(
            header, text='Cancelar', width=88, height=32, corner_radius=8,
            fg_color=theme_color('#301923'), hover_color=theme_color('#49202d'),
            border_width=1, border_color=theme_color('#6b2b3b'), text_color=TEXT,
            font=('Segoe UI', 8, 'bold'), command=getattr(self.app, 'cancel_diagnostic_session', lambda: None)
        )
        self.btn_cancel.grid(row=0, column=2, sticky='e', padx=(8, 0))
        self.btn_cancel.grid_remove()
        self.btn_back = ctk.CTkButton(header, text='Volver al monitoreo', width=145, height=32, corner_radius=8, fg_color=theme_color('#13253a'), hover_color=theme_color('#19324e'), border_width=1, border_color=BORDER, text_color=TEXT, font=('Segoe UI', 8, 'bold'), command=self.close)
        self.btn_back.grid(row=0, column=3, sticky='e', padx=(8, 0))

    def _open_sensor_compatibility(self):
        opener = getattr(self.app, 'open_telemetry_details', None)
        if callable(opener):
            opener()

    def _metric_card(self, parent, title, height=70):
        card = ctk.CTkFrame(parent, fg_color=SURFACE_2, border_width=1, border_color=BORDER, corner_radius=10, height=height)
        card.grid_propagate(False)
        card.grid_columnconfigure(0, weight=1)
        title_label = ctk.CTkLabel(card, text=title, font=('Segoe UI', 7, 'bold'), text_color=MUTED, anchor='w')
        title_label.grid(row=0, column=0, sticky='ew', padx=12, pady=(8, 0))
        value = ctk.CTkLabel(card, text='N/A', font=('Segoe UI', 14, 'bold'), text_color=TEXT, anchor='w')
        value.grid(row=1, column=0, sticky='ew', padx=12, pady=(0, 8))
        return (card, title_label, value)

    def _chip_card(self, parent, title, value, color=TEXT):
        chip = ctk.CTkFrame(parent, fg_color=theme_color('#0e1726'), border_width=1, border_color=theme_color('#17314c'), corner_radius=9)
        chip.grid_columnconfigure(0, weight=1)
        title_label = ctk.CTkLabel(chip, text=title, font=('Segoe UI', 7, 'bold'), text_color=MUTED)
        title_label.grid(row=0, column=0, sticky='ew', padx=10, pady=(7, 0))
        value_label = ctk.CTkLabel(chip, text=value, font=('Segoe UI', 9, 'bold'), text_color=color)
        value_label.grid(row=1, column=0, sticky='ew', padx=10, pady=(1, 7))
        return (chip, value_label)

    def _summary_row(self, parent, title, color):
        wrap = ctk.CTkFrame(parent, fg_color='transparent')
        wrap.grid_columnconfigure(1, weight=1)
        title_label = ctk.CTkLabel(wrap, text=title, font=('Segoe UI', 8, 'bold'), text_color=DIM, width=108, anchor='w')
        title_label.grid(row=0, column=0, sticky='w')
        bar = ctk.CTkProgressBar(wrap, height=7, corner_radius=4, fg_color=theme_color('#14263c'), progress_color=color)
        bar.grid(row=0, column=1, sticky='ew', padx=(8, 9))
        bar.set(0)
        value = ctk.CTkLabel(wrap, text='N/A', font=('Segoe UI', 8, 'bold'), text_color=color, width=48, anchor='e')
        value.grid(row=0, column=2, sticky='e')
        detail = ctk.CTkLabel(wrap, text='', font=('Segoe UI', 7), text_color=MUTED, anchor='w')
        detail.grid(row=1, column=1, columnspan=2, sticky='ew', padx=(8, 0), pady=(2, 0))
        return (wrap, title_label, bar, value, detail)

    def _finding_row(self, parent):
        row = ctk.CTkFrame(parent, fg_color='transparent')
        dot = ctk.CTkLabel(row, text='●', font=('Segoe UI', 9, 'bold'), text_color=CYAN, width=14)
        dot.pack(side='left')
        text = ctk.CTkLabel(row, text='Esperando finalización del análisis…', font=('Segoe UI', 8), text_color=DIM, anchor='w', justify='left')
        text.pack(side='left', fill='x', expand=True)
        return (row, dot, text)

    def _build_body(self):
        shell = ctk.CTkFrame(self, fg_color=SURFACE, border_width=1, border_color=BORDER, corner_radius=13)
        shell.grid(row=1, column=0, sticky='nsew', padx=6, pady=(3, 4))
        shell.grid_columnconfigure(0, weight=8)
        shell.grid_columnconfigure(1, weight=13)
        shell.grid_rowconfigure(0, weight=1)
        self._shell = shell
        left_outer = ctk.CTkFrame(shell, fg_color='transparent')
        left_outer.grid(row=0, column=0, sticky='nsew', padx=(12, 6), pady=10)
        left_outer.grid_columnconfigure(0, weight=1)
        self._left_outer = left_outer
        gauge_side = ctk.CTkFrame(left_outer, fg_color=BG, corner_radius=14, border_width=1, border_color=theme_color('#12243a'), width=380, height=438)
        gauge_side.grid(row=0, column=0)
        gauge_side.grid_propagate(False)
        gauge_side.grid_columnconfigure(0, weight=1)
        self._gauge_side = gauge_side
        top_line = ctk.CTkFrame(gauge_side, fg_color='transparent')
        top_line.grid(row=0, column=0, sticky='ew', padx=18, pady=(16, 8))
        top_line.grid_columnconfigure(1, weight=1)
        self.lbl_phase = ctk.CTkLabel(top_line, text='PREPARANDO DIAGNÓSTICO', font=('Segoe UI', 8, 'bold'), text_color=CYAN)
        self.lbl_phase.grid(row=0, column=0, sticky='w')
        self.status_badge = ctk.CTkLabel(top_line, text='EVIDENCIA REAL', font=('Segoe UI', 8, 'bold'), text_color=CYAN, fg_color=theme_color('#0f2437'), corner_radius=12, padx=12, pady=4)
        self.status_badge.grid(row=0, column=1, sticky='e')
        self.gauge = DiagnosticGauge(gauge_side, size=254)
        self.gauge.grid(row=1, column=0, padx=32, pady=(0, 2))
        chip_row = ctk.CTkFrame(gauge_side, fg_color='transparent')
        chip_row.grid(row=2, column=0, sticky='ew', padx=22, pady=(2, 8))
        for i in range(3):
            chip_row.grid_columnconfigure(i, weight=1)
        self.chip_duration, self.lbl_chip_duration = self._chip_card(chip_row, 'Tiempo', '0 s', CYAN)
        self.chip_duration.grid(row=0, column=0, sticky='ew', padx=(0, 6))
        self.chip_samples, self.lbl_chip_samples = self._chip_card(chip_row, 'Muestras', '0 / 25', TEXT)
        self.chip_samples.grid(row=0, column=1, sticky='ew', padx=3)
        self.chip_confidence, self.lbl_chip_confidence = self._chip_card(chip_row, 'ETA', '~0 s', GREEN)
        self.chip_confidence.grid(row=0, column=2, sticky='ew', padx=(6, 0))
        self.progress_bar = ctk.CTkProgressBar(gauge_side, height=8, corner_radius=4, fg_color=theme_color('#14263c'), progress_color=CYAN)
        self.progress_bar.grid(row=3, column=0, sticky='ew', padx=40, pady=(0, 6))
        self.progress_bar.set(0)
        self.lbl_quality = ctk.CTkLabel(gauge_side, text='Sesión en preparación · telemetría real · resultados sin simulación.', font=('Segoe UI', 8), text_color=DIM, wraplength=400, justify='center')
        self.lbl_quality.grid(row=4, column=0, pady=(0, 6))
        self.lbl_hint = ctk.CTkLabel(gauge_side, text='CorePulse mide evidencia real y finaliza al reunir cobertura suficiente.', font=('Segoe UI', 7), text_color=MUTED, wraplength=400, justify='center')
        self.lbl_hint.grid(row=5, column=0, pady=(0, 14))
        # V147 — el informe puede superar la altura disponible incluso maximizado.
        # StableScrollHost usa Canvas nativo + rueda rápida y evita reconstruir
        # widgets mientras se desplaza, por lo que no introduce el scroll lento
        # que sufrían algunas vistas CTk densas.
        self.details_scroll = StableScrollHost(
            shell, fg_color=SURFACE, wheel_pixels=96, scroll_hold_ms=160
        )
        self.details_scroll.grid(row=0, column=1, sticky='nsew', padx=(6, 10), pady=8)
        details = self.details_scroll.content
        self._details = details
        details.grid_columnconfigure(0, weight=1)
        details.grid_columnconfigure(1, weight=1)
        self.lbl_details_title = ctk.CTkLabel(details, text='EVIDENCIA EN TIEMPO REAL', font=('Segoe UI', 8, 'bold'), text_color=MUTED, anchor='w')
        self.lbl_details_title.grid(row=0, column=0, columnspan=2, sticky='ew', pady=(2, 5))
        self.card_elapsed, self.lbl_elapsed_title, self.lbl_elapsed = self._metric_card(details, 'TIEMPO')
        self.card_context, self.lbl_context_title, self.lbl_context = self._metric_card(details, 'CONTEXTO')
        self.card_samples, self.lbl_samples_title, self.lbl_samples = self._metric_card(details, 'MUESTRAS')
        self.card_eta, self.lbl_eta_title, self.lbl_eta = self._metric_card(details, 'ETA')
        for card, row, col in ((self.card_elapsed, 1, 0), (self.card_context, 1, 1), (self.card_samples, 2, 0), (self.card_eta, 2, 1)):
            card.grid(row=row, column=col, sticky='ew', padx=(0 if col == 0 else 4, 4 if col == 0 else 0), pady=4)
        self.findings_card = ctk.CTkFrame(details, fg_color=SURFACE_3, border_width=1, border_color=theme_color('#172b43'), corner_radius=10)
        self.findings_card.grid(row=3, column=0, sticky='nsew', padx=(0, 4), pady=(7, 4))
        self.findings_title = ctk.CTkLabel(self.findings_card, text='HALLAZGOS CLAVE', font=('Segoe UI', 7, 'bold'), text_color=MUTED, anchor='w')
        self.findings_title.pack(fill='x', padx=10, pady=(8, 5))
        findings_body = ctk.CTkFrame(self.findings_card, fg_color='transparent')
        findings_body.pack(fill='both', expand=True, padx=10, pady=(0, 8))
        for _ in range(4):
            row, dot, label = self._finding_row(findings_body)
            row.pack(fill='x', pady=1)
            self._finding_rows.append((dot, label))
        self.observed_card = ctk.CTkFrame(details, fg_color=SURFACE_3, border_width=1, border_color=theme_color('#172b43'), corner_radius=10)
        self.observed_card.grid(row=3, column=1, sticky='nsew', padx=(4, 0), pady=(7, 4))
        self.observed_title = ctk.CTkLabel(self.observed_card, text='MÉTRICAS OBSERVADAS', font=('Segoe UI', 7, 'bold'), text_color=MUTED, anchor='w')
        self.observed_title.pack(fill='x', padx=10, pady=(8, 5))
        observed_body = ctk.CTkFrame(self.observed_card, fg_color='transparent')
        observed_body.pack(fill='both', expand=True, padx=10, pady=(0, 8))
        for i, name in enumerate(('CPU máx', 'CPU GHz prom', 'GPU monitoreadas', 'Unidades')):
            row = ctk.CTkFrame(observed_body, fg_color='transparent')
            row.pack(fill='x', pady=2)
            title = ctk.CTkLabel(row, text=name, font=('Segoe UI', 8, 'bold'), text_color=DIM, anchor='w')
            title.pack(side='left')
            self._observed_title_labels.append(title)
            value = ctk.CTkLabel(row, text='N/A', font=('Segoe UI', 8, 'bold'), text_color=TEXT, anchor='e')
            value.pack(side='right')
            self._observed_value_labels.append(value)
        self.summary_card = ctk.CTkFrame(details, fg_color=SURFACE_3, border_width=1, border_color=theme_color('#172b43'), corner_radius=10)
        self.summary_card.grid(row=4, column=0, columnspan=2, sticky='ew', pady=(4, 4))
        self.summary_card.grid_columnconfigure(0, weight=1)
        self.lbl_summary_title = ctk.CTkLabel(self.summary_card, text='COBERTURA DE EVIDENCIA', font=('Segoe UI', 7, 'bold'), text_color=MUTED, anchor='w')
        self.lbl_summary_title.grid(row=0, column=0, sticky='ew', padx=10, pady=(8, 3))
        self.cpu_summary_row, self.lbl_cpu_summary_title, self.bar_cpu, self.lbl_cpu, self.lbl_cpu_detail = self._summary_row(self.summary_card, 'Cobertura CPU', CYAN)
        self.cpu_summary_row.grid(row=1, column=0, sticky='ew', padx=10, pady=(4, 5))
        self.ram_summary_row, self.lbl_ram_summary_title, self.bar_ram, self.lbl_ram, self.lbl_ram_detail = self._summary_row(self.summary_card, 'Cobertura RAM', GREEN)
        self.ram_summary_row.grid(row=2, column=0, sticky='ew', padx=10, pady=(5, 8))
        self._apply_simplified_live_layout(details)

        # V146 — informe vivo por componente + prioridad accionable.
        # Durante la ejecución permanece oculto; al finalizar sustituye el
        # resumen por fases técnicas sin crear scores ni rankings.
        self.component_report = ctk.CTkFrame(details, fg_color='transparent')
        self.component_report.grid_columnconfigure(0, weight=1, uniform='diag_component')
        self.component_report.grid_columnconfigure(1, weight=1, uniform='diag_component')

        self.priority_card = ctk.CTkFrame(
            self.component_report, fg_color=theme_color('#0d1b2a'),
            border_width=1, border_color=theme_color('#20506d'), corner_radius=10
        )
        self.priority_card.grid(row=0, column=0, columnspan=2, sticky='ew', pady=(2, 4))
        self.priority_card.grid_columnconfigure(1, weight=1)
        self.lbl_priority_tag = ctk.CTkLabel(
            self.priority_card, text='SIGUIENTE PASO', font=('Segoe UI', 7, 'bold'),
            text_color=CYAN, width=86, anchor='w'
        )
        self.lbl_priority_tag.grid(row=0, column=0, padx=(9, 7), pady=6, sticky='w')
        self.lbl_priority_text = ctk.CTkLabel(
            self.priority_card, text='Esperando resultado…', font=('Segoe UI', 8, 'bold'),
            text_color=TEXT, anchor='w', justify='left', wraplength=330
        )
        self.lbl_priority_text.grid(row=0, column=1, sticky='ew', pady=6)
        self.btn_priority = ctk.CTkButton(
            self.priority_card, text='Revisar', width=118, height=28, corner_radius=7,
            fg_color=theme_color('#123e5c'), hover_color=theme_color('#174e72'),
            border_width=1, border_color=theme_color('#20506d'), text_color=TEXT,
            font=('Segoe UI', 8, 'bold')
        )
        self.btn_priority.grid(row=0, column=2, padx=8, pady=5, sticky='e')
        self.lbl_overview = ctk.CTkLabel(
            self.priority_card, text='Resumen integral: pendiente',
            font=('Segoe UI', 7, 'bold'), text_color=DIM, anchor='w', justify='left'
        )
        self.lbl_overview.grid(row=1, column=0, columnspan=3, sticky='ew', padx=9, pady=(0, 2))
        self.lbl_comparison = ctk.CTkLabel(
            self.priority_card, text='Comparación anterior: pendiente',
            font=('Segoe UI', 7), text_color=MUTED, anchor='w', justify='left'
        )
        self.lbl_comparison.grid(row=2, column=0, columnspan=3, sticky='ew', padx=9, pady=(0, 6))

        # V149 — evidencia explicable in-place. Se crea una sola superficie y
        # se rellena únicamente al pedirla; no añade trabajo al resize normal.
        self.evidence_card = ctk.CTkFrame(
            self.component_report, fg_color=theme_color('#0b1726'),
            border_width=1, border_color=theme_color('#20506d'), corner_radius=10
        )
        self.evidence_card.grid_columnconfigure(0, weight=1)
        evidence_head = ctk.CTkFrame(self.evidence_card, fg_color='transparent')
        evidence_head.grid(row=0, column=0, sticky='ew', padx=9, pady=(7, 3))
        evidence_head.grid_columnconfigure(0, weight=1)
        self.lbl_evidence_title = ctk.CTkLabel(
            evidence_head, text='EVIDENCIA', font=('Segoe UI', 9, 'bold'),
            text_color=CYAN, anchor='w'
        )
        self.lbl_evidence_title.grid(row=0, column=0, sticky='w')
        self.lbl_evidence_status = ctk.CTkLabel(
            evidence_head, text='N/A', font=('Segoe UI', 8, 'bold'),
            text_color=DIM, fg_color=theme_color('#0f2437'), corner_radius=10,
            padx=7, pady=1
        )
        self.lbl_evidence_status.grid(row=0, column=1, sticky='e', padx=(6, 6))
        self.btn_close_evidence = ctk.CTkButton(
            evidence_head, text='Cerrar', width=62, height=24, corner_radius=7,
            fg_color=theme_color('#17263a'), hover_color=theme_color('#203650'),
            border_width=1, border_color=BORDER, text_color=TEXT,
            font=('Segoe UI', 7, 'bold'), command=self._hide_component_evidence
        )
        self.btn_close_evidence.grid(row=0, column=2, sticky='e')
        self.lbl_evidence_summary = ctk.CTkLabel(
            self.evidence_card, text='', font=('Segoe UI', 8, 'bold'),
            text_color=TEXT, anchor='w', justify='left', wraplength=640
        )
        self.lbl_evidence_summary.grid(row=1, column=0, sticky='ew', padx=9, pady=(0, 4))
        self.evidence_body = ctk.CTkFrame(self.evidence_card, fg_color='transparent')
        self.evidence_body.grid(row=2, column=0, sticky='ew', padx=9, pady=(0, 7))
        self.evidence_body.grid_columnconfigure(0, weight=1)
        self.evidence_card.grid_remove()
        self._evidence_open_key = None

        self._component_cards = {}
        for idx, key in enumerate(('cpu', 'gpu', 'ram', 'storage', 'battery', 'windows')):
            row, col = divmod(idx, 2)
            row += 1
            card = ctk.CTkFrame(self.component_report, fg_color=SURFACE_3, border_width=1, border_color=theme_color('#172b43'), corner_radius=10)
            card.grid(row=row, column=col, sticky='nsew', padx=(0 if col == 0 else 4, 4 if col == 0 else 0), pady=4)
            card.grid_columnconfigure(0, weight=1)
            head = ctk.CTkFrame(card, fg_color='transparent')
            head.grid(row=0, column=0, sticky='ew', padx=9, pady=(6, 1))
            head.grid_columnconfigure(0, weight=1)
            title = ctk.CTkLabel(head, text=key.upper(), font=('Segoe UI', 9, 'bold'), text_color=TEXT, anchor='w')
            title.grid(row=0, column=0, sticky='w')
            badge = ctk.CTkLabel(head, text='N/A', font=('Segoe UI', 8, 'bold'), text_color=DIM, fg_color=theme_color('#0f2437'), corner_radius=10, padx=7, pady=1)
            badge.grid(row=0, column=1, sticky='e')
            summary = ctk.CTkLabel(card, text='Pendiente', font=('Segoe UI', 8, 'bold'), text_color=DIM, anchor='w', justify='left', wraplength=300)
            summary.grid(row=1, column=0, sticky='ew', padx=9, pady=(0, 1))

            facets = ctk.CTkFrame(card, fg_color='transparent')
            facets.grid(row=2, column=0, sticky='ew', padx=9, pady=(1, 2))
            facet_refs = []
            for facet_idx in range(3):
                facets.grid_columnconfigure(facet_idx, weight=1, uniform='diag_facet')
                cell = ctk.CTkFrame(facets, fg_color=theme_color('#0d1828'), corner_radius=6)
                cell.grid(row=0, column=facet_idx, sticky='ew', padx=(0 if facet_idx == 0 else 2, 0 if facet_idx == 2 else 2))
                facet_title = ctk.CTkLabel(cell, text='—', font=('Segoe UI', 6, 'bold'), text_color=MUTED, anchor='center')
                facet_title.pack(fill='x', padx=3, pady=(3, 0))
                facet_value = ctk.CTkLabel(cell, text='N/A', font=('Segoe UI', 7, 'bold'), text_color=DIM, anchor='center')
                facet_value.pack(fill='x', padx=3, pady=(0, 3))
                facet_refs.append((facet_title, facet_value))

            evidence = ctk.CTkLabel(card, text='', font=('Segoe UI', 7), text_color=MUTED, anchor='w', justify='left', wraplength=300)
            evidence.grid(row=3, column=0, sticky='ew', padx=9, pady=(0, 3))
            action_row = ctk.CTkFrame(card, fg_color='transparent')
            action_row.grid(row=4, column=0, sticky='ew', padx=9, pady=(0, 6))
            action_row.grid_columnconfigure(0, weight=1)
            action_row.grid_columnconfigure(1, weight=1)
            evidence_action = ctk.CTkButton(
                action_row, text='Ver evidencia', height=24, corner_radius=7,
                fg_color=theme_color('#0f2c42'), hover_color=theme_color('#174e72'),
                border_width=1, border_color=theme_color('#20506d'), text_color=TEXT,
                font=('Segoe UI', 8, 'bold')
            )
            evidence_action.grid(row=0, column=0, sticky='ew', padx=(0, 3))
            action = ctk.CTkButton(action_row, text='Ver detalle', height=24, corner_radius=7, fg_color=theme_color('#102a3d'), hover_color=theme_color('#174e72'), border_width=1, border_color=theme_color('#20506d'), text_color=TEXT, font=('Segoe UI', 8, 'bold'))
            action.grid(row=0, column=1, sticky='ew', padx=(3, 0))
            self._component_cards[key] = {
                'card': card, 'title': title, 'badge': badge, 'summary': summary,
                'facets': facet_refs, 'evidence': evidence,
                'evidence_action': evidence_action, 'action': action
            }
        self.component_report.grid_remove()

        self.interpretation_card = ctk.CTkFrame(details, fg_color=SURFACE_3, border_width=1, border_color=theme_color('#172b43'), corner_radius=10)
        self.interpretation_card.grid(row=5, column=0, columnspan=2, sticky='ew', pady=(4, 4))
        self.interpretation_card.grid_columnconfigure(0, weight=3)
        self.interpretation_card.grid_columnconfigure(1, weight=2)
        self.lbl_interpretation = ctk.CTkLabel(self.interpretation_card, text='La interpretación profesional se habilita cuando el diagnóstico termina.', font=('Segoe UI', 8), text_color=DIM, anchor='w', justify='left', wraplength=360)
        self.lbl_interpretation.grid(row=0, column=0, columnspan=2, sticky='ew', padx=10, pady=9)
        self.result_actions = ctk.CTkFrame(self.interpretation_card, fg_color='transparent')
        self.result_actions.grid(row=0, column=1, sticky='e', padx=(8, 10), pady=7)
        self.result_actions.grid_columnconfigure(0, weight=1)
        self.result_actions.grid_columnconfigure(1, weight=1)
        self.result_actions.grid_remove()
        self.btn_pdf = ctk.CTkButton(self.result_actions, text='Generar PDF', width=126, height=34, corner_radius=8, fg_color=theme_color('#123e5c'), hover_color=theme_color('#174e72'), text_color=TEXT, font=('Segoe UI', 8, 'bold'), command=self._export_pdf_from_panel)
        self.btn_pdf.grid(row=0, column=0, sticky='ew', padx=(0, 4), pady=(0, 4))
        self.btn_repeat = ctk.CTkButton(self.result_actions, text='Diagnosticar de nuevo', width=146, height=34, corner_radius=8, fg_color=theme_color('#17263a'), hover_color=theme_color(theme_color('#203650')), border_width=1, border_color=BORDER, text_color=TEXT, font=('Segoe UI', 8, 'bold'), command=self._repeat)
        self.btn_repeat.grid(row=0, column=1, sticky='ew', padx=(4, 0), pady=(0, 4))
        self.btn_open_pdf = ctk.CTkButton(self.result_actions, text='Abrir último PDF', width=126, height=30, corner_radius=8, fg_color=theme_color('#102a3d'), hover_color=theme_color('#174e72'), border_width=1, border_color=theme_color('#20506d'), text_color=TEXT, font=('Segoe UI', 8, 'bold'), command=self._open_last_pdf_from_panel, state='disabled')
        self.btn_open_pdf.grid(row=1, column=0, sticky='ew', padx=(0, 4), pady=(0, 0))
        self.btn_pdf_folder = ctk.CTkButton(self.result_actions, text='Abrir carpeta de informes', width=146, height=30, corner_radius=8, fg_color=theme_color('#17263a'), hover_color=theme_color('#203650'), border_width=1, border_color=BORDER, text_color=TEXT, font=('Segoe UI', 8, 'bold'), command=self._show_pdf_folder_from_panel, state='normal')
        self.btn_pdf_folder.grid(row=1, column=1, sticky='ew', padx=(4, 0), pady=(0, 0))

    def _apply_simplified_live_layout(self, details):
        """Aplica la operación `apply_simplified_live_layout` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
        try:
            self.card_eta.grid_remove()
        except Exception:
            pass
        try:
            self.card_samples.grid_configure(columnspan=2, padx=(0, 0))
        except Exception:
            pass
        try:
            self.progress_bar.grid_remove()
        except Exception:
            pass
        try:
            self.summary_card.grid_remove()
        except Exception:
            pass

    def _open_health_area(self, tab, windows_section=None):
        """Navegación profunda atómica hacia Centro de salud (V144)."""
        opener = getattr(self.app, 'open_health_center', None)
        if not callable(opener):
            return
        try:
            opener(tab=tab, windows_section=windows_section)
        except TypeError:
            # Compatibilidad defensiva con shells antiguos.
            try:
                opener()
            except Exception:
                pass
        except Exception:
            pass

    def _hide_component_evidence(self):
        self._evidence_open_key = None
        try:
            self.evidence_card.grid_remove()
            self._apply_responsive_layout(force=True)
        except Exception:
            pass

    def _show_component_evidence(self, key, result):
        """Muestra trazabilidad real sin abandonar la pantalla del diagnóstico."""
        try:
            detail = build_component_evidence(result if isinstance(result, dict) else {}, key)
        except Exception as exc:
            detail = {
                'title': str(key or '').upper(), 'status': 'NO_EVALUABLE',
                'summary': 'No se pudo construir la evidencia detallada.',
                'reason': f'{type(exc).__name__}: {exc}', 'sections': [],
            }
        status = str(detail.get('status') or 'NO_EVALUABLE').upper()
        color = STATUS_COLORS.get(status, DIM)
        self._evidence_open_key = str(key or '')
        self.lbl_evidence_title.configure(text=f"EVIDENCIA · {str(detail.get('title') or key).upper()}")
        self.lbl_evidence_status.configure(
            text={'NORMAL': 'SIN ALERTAS', 'WARNING': 'REVISAR', 'CRITICAL': 'CRÍTICO', 'INFO': 'INFORMATIVO', 'NO_EVALUABLE': 'N/A'}.get(status, status),
            text_color=color,
        )
        summary = str(detail.get('summary') or 'Evidencia parcial')
        reason = str(detail.get('reason') or '').strip()
        if reason and reason.casefold() not in summary.casefold():
            summary = f'{summary} · {reason}'
        self.lbl_evidence_summary.configure(text=summary)
        for child in list(self.evidence_body.winfo_children()):
            try:
                child.destroy()
            except Exception:
                pass
        sections = [x for x in (detail.get('sections') or []) if isinstance(x, dict)]
        for section_idx, section in enumerate(sections):
            block = ctk.CTkFrame(
                self.evidence_body, fg_color=theme_color('#0d1828'),
                border_width=1, border_color=theme_color('#172b43'), corner_radius=8
            )
            block.grid(row=section_idx, column=0, sticky='ew', pady=(0 if section_idx == 0 else 3, 3))
            block.grid_columnconfigure(1, weight=1)
            title = ctk.CTkLabel(
                block, text=str(section.get('title') or 'Evidencia').upper(),
                font=('Segoe UI', 7, 'bold'), text_color=CYAN, anchor='w'
            )
            title.grid(row=0, column=0, columnspan=2, sticky='ew', padx=8, pady=(5, 2))
            rows = [x for x in (section.get('rows') or []) if isinstance(x, dict)]
            for row_idx, row in enumerate(rows, 1):
                label = ctk.CTkLabel(
                    block, text=str(row.get('label') or 'Dato'), font=('Segoe UI', 7),
                    text_color=MUTED, anchor='w'
                )
                label.grid(row=row_idx, column=0, sticky='w', padx=(8, 6), pady=1)
                value = ctk.CTkLabel(
                    block, text=str(row.get('value') or 'N/A'), font=('Segoe UI', 7, 'bold'),
                    text_color=TEXT, anchor='e', justify='right', wraplength=480
                )
                value.grid(row=row_idx, column=1, sticky='e', padx=(6, 8), pady=1)
            note = str(section.get('note') or '').strip()
            if note:
                note_label = ctk.CTkLabel(
                    block, text=note, font=('Segoe UI', 6), text_color=MUTED,
                    anchor='w', justify='left', wraplength=620
                )
                note_label.grid(row=len(rows) + 1, column=0, columnspan=2, sticky='ew', padx=8, pady=(3, 5))
        if not sections:
            ctk.CTkLabel(
                self.evidence_body, text='No hay evidencia adicional disponible para este componente.',
                font=('Segoe UI', 8), text_color=DIM, anchor='w'
            ).grid(row=0, column=0, sticky='ew', pady=6)
        try:
            self.evidence_card.grid(row=1, column=0, sticky='ew', pady=(2, 4))
            self._apply_responsive_layout(force=True)
            self.update_idletasks()
            self.details_scroll._schedule_geometry(1)
        except Exception:
            pass

    def _component_action(self, key, result):
        if key == 'cpu':
            fn = getattr(self.app, 'open_cpu_details', None)
            return fn if callable(fn) else None
        if key == 'gpu':
            fn = getattr(self.app, 'open_gpu_details', None)
            return fn if callable(fn) else None
        if key == 'ram':
            fn = getattr(self.app, 'open_ram_details', None)
            return fn if callable(fn) else None
        if key == 'storage':
            fn = getattr(self.app, 'open_storage_details', None)
            return (lambda: fn(0)) if callable(fn) else None
        if key == 'battery':
            return lambda: self._open_health_area('battery')
        if key == 'windows':
            finding = _worst_finding_for(result, {'WINDOWS', 'WINDOWS_STARTUP', 'DRIVERS'})
            component = str((finding or {}).get('component') or '').upper()
            section = 'drivers' if component == 'DRIVERS' else 'startup' if component == 'WINDOWS_STARTUP' else 'crashes' if component == 'WINDOWS' else 'summary'
            return lambda: self._open_health_area('windows', section)
        return None

    def _show_component_report(self, result):
        reports = _component_reports(result)
        self._hide_component_evidence()
        try:
            for widget in (self.card_elapsed, self.card_context, self.card_samples, self.card_eta, self.findings_card, self.observed_card, self.summary_card):
                widget.grid_remove()
        except Exception:
            pass
        try:
            self.lbl_details_title.configure(text='RESULTADO INTEGRAL · ESCRITORIO + BENCHMARK + TELEMETRÍA BAJO CARGA + WINDOWS')
            self.component_report.grid(row=1, column=0, columnspan=2, sticky='nsew', pady=(2, 4))
            self.interpretation_card.grid_configure(row=2, column=0, columnspan=2, sticky='ew', pady=(4, 4))
            self._apply_responsive_layout()
            self.details_scroll.yview_moveto(0.0)
        except Exception:
            pass

        badge_labels = {
            'NORMAL': 'SIN ALERTAS', 'WARNING': 'REVISAR', 'CRITICAL': 'CRÍTICO',
            'NO_EVALUABLE': 'N/A', 'INFO': 'INFORMATIVO',
        }

        # V146: una única prioridad visible responde "¿y ahora qué hago?".
        priority = select_priority_assessment(reports)
        if priority:
            p_status = str(priority.get('status') or 'WARNING').upper()
            p_color = STATUS_COLORS.get(p_status, YELLOW)
            action = self._component_action(priority.get('key'), result)
            self.lbl_priority_tag.configure(text='PRIORIDAD', text_color=p_color)
            self.lbl_priority_text.configure(
                text=f"{priority.get('title')}: {priority.get('summary')}",
                text_color=TEXT,
            )
            self.btn_priority.configure(
                text=str(priority.get('action_text') or 'Revisar'),
                command=action, state='normal' if callable(action) else 'disabled'
            )
        else:
            self.lbl_priority_tag.configure(text='SIGUIENTE PASO', text_color=GREEN)
            self.lbl_priority_text.configure(
                text='Sin acciones prioritarias basadas en la evidencia disponible. Consulta las áreas N/A si faltaron mediciones.',
                text_color=DIM,
            )
            self.btn_priority.configure(text='Sin acción urgente', command=lambda: None, state='disabled')

        overview = build_diagnostic_overview(result)
        overview_color = RED if overview.get('critical_count') else YELLOW if overview.get('warning_count') else DIM if overview.get('na_count') else GREEN
        try:
            self.lbl_overview.configure(
                text='Resumen integral: ' + str(overview.get('headline') or 'N/A'),
                text_color=overview_color,
            )
        except Exception:
            pass

        comparison = ((result.get('complete_diagnostic') or {}).get('comparison') or {}) if isinstance(result, dict) else {}
        if isinstance(comparison, dict) and comparison.get('available'):
            changes = [x for x in (comparison.get('component_changes') or []) if isinstance(x, dict)]
            if changes:
                parts = [f"{x.get('title')}: {str(x.get('previous') or 'N/A').replace('_', ' ')} → {str(x.get('current') or 'N/A').replace('_', ' ')}" for x in changes[:3]]
                extra = len(changes) - len(parts)
                suffix = f' · +{extra} cambio(s)' if extra > 0 else ''
                self.lbl_comparison.configure(text='Comparación anterior: ' + ' · '.join(parts) + suffix, text_color=CYAN)
            else:
                self.lbl_comparison.configure(text='Comparación anterior: sin cambios de estado en CPU/GPU/RAM/almacenamiento/batería/Windows.', text_color=MUTED)
        else:
            self.lbl_comparison.configure(text='Comparación anterior: no hay un diagnóstico completo previo comparable.', text_color=MUTED)

        facet_color = {
            'NORMAL': GREEN, 'WARNING': YELLOW, 'CRITICAL': RED,
            'INFO': CYAN, 'NO_EVALUABLE': DIM,
        }
        for report in reports:
            key = report['key']
            refs = self._component_cards.get(key)
            if not refs:
                continue
            status = str(report.get('status') or 'NO_EVALUABLE').upper()
            color = STATUS_COLORS.get(status, DIM)
            refs['title'].configure(text=str(report.get('title') or key).upper())
            refs['badge'].configure(text=badge_labels.get(status, status), text_color=color)
            refs['summary'].configure(
                text=str(report.get('summary') or 'Evidencia parcial'),
                text_color=TEXT if status in {'CRITICAL', 'WARNING'} else DIM
            )
            facets = list(report.get('facets') or [])
            for idx, pair in enumerate(refs.get('facets') or []):
                title_label, value_label = pair
                if idx < len(facets):
                    item = facets[idx]
                    label = str(item[0] if len(item) > 0 else '—')
                    value = str(item[1] if len(item) > 1 else 'N/A')
                    facet_status = str(item[2] if len(item) > 2 else 'NO_EVALUABLE').upper()
                    title_label.configure(text=label.upper())
                    value_label.configure(text=value, text_color=facet_color.get(facet_status, DIM))
                else:
                    title_label.configure(text='—')
                    value_label.configure(text='N/A', text_color=DIM)
            evidence = list(report.get('evidence') or [])
            evidence_text = ' · '.join(str(x) for x in evidence[:2]) if evidence else str(report.get('reason') or 'Sin evidencia adicional disponible para mostrar.')
            if len(evidence_text) > 150:
                evidence_text = evidence_text[:147].rstrip() + '…'
            refs['evidence'].configure(text=evidence_text)
            action = self._component_action(key, result)
            refs['evidence_action'].configure(
                text='Ver evidencia',
                command=lambda k=key, r=result: self._show_component_evidence(k, r),
                state='normal'
            )
            refs['action'].configure(
                text=str(report.get('action_text') or 'Ver detalle'),
                command=action, state='normal' if callable(action) else 'disabled'
            )


    def _export_pdf_from_panel(self):
        """Exporta la operación `export_pdf_from_panel` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
        if self._closed:
            return
        exporter = getattr(self.app, 'export_pdf_report', None)
        if not callable(exporter):
            try:
                self.btn_pdf.configure(state='normal', text='Generar PDF')
            except Exception:
                pass
            return
        # El callback de CTkButton ya se ejecuta en el hilo principal de Tkinter.
        # Llamar al exportador directamente evita callbacks after_idle perdidos
        # durante cambios de foco o navegación interna.
        exporter()

    def _open_last_pdf_from_panel(self):
        opener = getattr(self.app, 'open_last_pdf_report', None)
        if callable(opener):
            opener()
        self.refresh_report_access()

    def _show_pdf_folder_from_panel(self):
        opener = getattr(self.app, 'show_last_pdf_report_folder', None)
        if callable(opener):
            opener()
        self.refresh_report_access()

    def refresh_report_access(self):
        """Habilita accesos persistentes sólo si el último PDF todavía existe."""
        getter = getattr(self.app, 'get_last_pdf_report_path', None)
        path = getter() if callable(getter) else None
        state = 'normal' if path else 'disabled'
        try:
            self.btn_open_pdf.configure(state=state)
            self.btn_pdf_folder.configure(state='normal')
        except Exception:
            pass
        return bool(path)

    def set_pdf_busy(self):
        try:
            self.btn_pdf.configure(state='disabled', text='Generando PDF…')
        except Exception:
            pass

    def set_pdf_ready(self):
        try:
            self.btn_pdf.configure(state='normal', text='Generar PDF')
        except Exception:
            pass

    def show_cancelled(self):
        """Estado final de una cancelación solicitada por el usuario."""
        if self._closed:
            return
        self._finished = True
        self._hide_component_evidence()
        self.progress_bar.set(0)
        self._set_findings_placeholder('Sesión cancelada; sin conclusiones finales.')
        self._set_observed_values([(None, 'N/A')] * 4)
        self.lbl_quality.configure(text='Ejecución cancelada · PDF no disponible')
        self.lbl_eta.configure(text='Cancelado')
        self.lbl_interpretation.grid_configure(columnspan=1, padx=(10, 8))
        try:
            self.btn_cancel.configure(
                text='Diagnosticar de nuevo', width=142, state='normal',
                command=self._repeat, fg_color=theme_color('#123e5c'),
                hover_color=theme_color('#174e72'),
            )
            self.btn_cancel.grid()
        except Exception:
            pass
        try:
            self.component_report.grid_remove()
        except Exception:
            pass
        self.lbl_title.configure(text='Diagnóstico cancelado')
        self.lbl_subtitle.configure(text='La ejecución se detuvo por solicitud del usuario. No se publicó un diagnóstico parcial como resultado final.')
        self.lbl_phase.configure(text='CANCELADO', text_color=YELLOW)
        self.status_badge.configure(text='SIN RESULTADO FINAL', text_color=YELLOW, fg_color=theme_color('#0f2437'))
        self.gauge.set_state(0, 'Cancelado', value_text='—', sub_text='Puedes repetirlo', accent=YELLOW)
        self.lbl_details_title.configure(text='EJECUCIÓN INTERRUMPIDA')
        self.lbl_hint.configure(text='Pulsa “Diagnosticar de nuevo” para iniciar otra sesión. Ninguna reparación se ejecutó automáticamente.')
        self.lbl_interpretation.configure(text='La evidencia parcial de esta ejecución no se usa para declarar que un componente está bien o mal.')
        try:
            self.btn_repeat.configure(text='Diagnosticar de nuevo', state='normal')
        except Exception:
            pass
        self.result_actions.grid()
        try:
            self.btn_pdf.configure(state='disabled', text='PDF no disponible')
            self.btn_open_pdf.configure(state='disabled')
        except Exception:
            pass

    def reset_for_run(self):
        """Restablece la vista reutilizada tanto desde el sidebar como desde Repetir."""
        self._closed = False
        self._finished = False
        self._hide_component_evidence()
        self.component_report.grid_remove()
        self.result_actions.grid_remove()
        for widget in (self.card_elapsed, self.card_context, self.card_samples,
                       self.findings_card, self.observed_card):
            widget.grid()
        self.interpretation_card.grid_configure(row=5, column=0, columnspan=2)
        self.lbl_interpretation.grid_configure(columnspan=2, padx=10)
        self.btn_cancel.configure(text='Cancelar', width=90, state='normal',
                                  command=self.app.cancel_diagnostic_session,
                                  fg_color=theme_color('#301923'), hover_color=theme_color('#49202d'))
        self.btn_cancel.grid()
        self.btn_pdf.configure(state='disabled', text='PDF · al finalizar')
        self.btn_open_pdf.configure(state='disabled')
        self._set_findings_placeholder()
        self._set_observed_values([(None, 'N/A')] * 4)
        self.progress_bar.set(0)
        self._last_layout_signature = None
        self._apply_responsive_layout(force=True)
        self.details_scroll.yview_moveto(0.0)

    def show_error(self, detail):
        self.show_cancelled()
        self.lbl_title.configure(text='Diagnóstico interrumpido')
        self.lbl_phase.configure(text='ERROR', text_color=RED)
        self.lbl_subtitle.configure(text='No se guardó un resultado final. Puedes iniciar otra sesión.')
        self.lbl_hint.configure(text=str(detail))

    def _repeat(self):
        self.app.start_diagnostic_session(force_new=True)

    def close(self):
        """Volver al monitoreo conserva la vista para reapertura inmediata."""
        try:
            from gui.internal_navigation import show_dashboard
            show_dashboard(self.app)
        except Exception:
            pass

    def _set_findings_placeholder(self, text='Esperando finalización del análisis…'):
        for idx, (dot, label) in enumerate(self._finding_rows):
            dot.configure(text_color=CYAN if idx == 0 else MUTED)
            label.configure(text=text if idx == 0 else '', text_color=DIM if idx == 0 else MUTED)

    def _set_observed_values(self, pairs):
        for label, (_name, value) in zip(self._observed_value_labels, pairs):
            label.configure(text=value)

    def update_progress(self, info, state=None):
        if self._closed or self._finished:
            return
        try:
            self.btn_cancel.grid()
        except Exception:
            pass
        info = info if isinstance(info, dict) else {}
        progress = _pct(float(info.get('progress', 0.0)) * 100.0)
        stage = readiness_stage(info)
        eta = max(0, int(info.get('eta_seconds', 0) or 0))
        elapsed = max(0, int(round(float(info.get('elapsed_seconds', 0) or 0))))
        samples = max(0, int(info.get('sample_count', 0) or 0))
        minimum = max(0, int(info.get('minimum_samples', 0) or 0))
        context = str(info.get('context') or 'N/A')
        coverage = info.get('coverage') or {}
        cpu_cov = _pct(float(coverage.get('cpu', 0.0) or 0.0) * 100.0)
        ram_cov = _pct(float(coverage.get('ram', 0.0) or 0.0) * 100.0)
        waiting = list(info.get('waiting_for') or [])
        accent = CYAN
        phase = 'RECOPILANDO EVIDENCIA'
        complete_stage = str(info.get('complete_stage') or '').strip()
        badge = 'EVIDENCIA REAL'
        if 'confirmando alertas' in waiting:
            accent = YELLOW
            phase = 'CONFIRMANDO CONDICIÓN'
            badge = 'VALIDANDO ALERTAS'
        elif 'observación de juego' in waiting or 'estabilizando contexto' in waiting:
            accent = PURPLE
            phase = 'ESTABILIZANDO CONTEXTO'
            badge = 'ANÁLISIS DE CONTEXTO'
        elif 'cobertura de sensores' in waiting:
            phase = 'VALIDANDO SENSORES'
            badge = 'COBERTURA EN CURSO'
        elif progress >= 90:
            accent = GREEN
            phase = 'VALIDANDO RESULTADO'
            badge = 'CIERRE DE SESIÓN'
        self.lbl_title.configure(text='Diagnóstico completo')
        self.lbl_subtitle.configure(text='Escritorio → Hardware → Windows → Benchmark y telemetría → Resultado.')
        if complete_stage:
            phase = complete_stage.upper()
            badge = 'FASE 1 · OBSERVACIÓN'
        self.lbl_details_title.configure(text='EVIDENCIA EN TIEMPO REAL')
        self.lbl_summary_title.configure(text='COBERTURA DE EVIDENCIA')
        self.lbl_cpu_summary_title.configure(text='Cobertura CPU')
        self.lbl_ram_summary_title.configure(text='Cobertura RAM')
        self.lbl_eta_title.configure(text='ETA')
        self.lbl_phase.configure(text=phase, text_color=accent)
        self.status_badge.configure(text=badge, text_color=accent)
        self.status_badge.configure(fg_color=theme_color('#0f2437'))
        self.gauge.set_state(progress, stage, value_text=f'{progress:.0f}%', sub_text='', accent=accent)
        self.progress_bar.configure(progress_color=accent)
        self.progress_bar.set(progress / 100.0)
        self.lbl_elapsed.configure(text=f'{elapsed} s')
        self.lbl_eta.configure(text=f'~{eta} s' if eta > 0 else 'Cerrando')
        self.lbl_samples.configure(text=f'{samples} / {minimum}')
        self.lbl_context.configure(text=context.replace('_', ' '))
        self.lbl_chip_duration.configure(text=f'{elapsed} s')
        self.lbl_chip_samples.configure(text=f'{samples} / {minimum}')
        self.lbl_chip_confidence.configure(text=f'~{eta} s' if eta > 0 else 'Listo', text_color=GREEN if eta == 0 else TEXT)
        self.bar_cpu.set(cpu_cov / 100.0)
        self.bar_ram.set(ram_cov / 100.0)
        self.lbl_cpu.configure(text=f'{cpu_cov:.0f}%')
        self.lbl_ram.configure(text=f'{ram_cov:.0f}%')
        self.lbl_cpu_detail.configure(text=f'{samples} muestras acumuladas')
        self.lbl_ram_detail.configure(text=f'{samples} muestras acumuladas')
        self.lbl_quality.configure(text=f"Sesión en progreso · {context.replace('_', ' ')} · cobertura CPU {cpu_cov:.0f}% · cobertura RAM {ram_cov:.0f}%.")
        self.lbl_hint.configure(text=_progress_hint(info))
        self._set_findings_placeholder('Los hallazgos se consolidan al finalizar la sesión.')
        self._set_observed_values([('CPU máx', f'{cpu_cov:.0f}% cobertura'), ('CPU GHz prom', f'{ram_cov:.0f}% cobertura'), ('GPU monitoreadas', str(len(waiting))), ('Unidades', str(minimum))])
        self.lbl_interpretation.configure(text='CorePulse sigue reuniendo evidencia antes de emitir una lectura final de la sesión.')

    def update_complete_progress(self, info):
        if self._closed or self._finished:
            return
        try:
            self.btn_cancel.grid()
        except Exception:
            pass
        info = info if isinstance(info, dict) else {}
        fraction = max(0.0, min(1.0, float(info.get('progress', 0.0) or 0.0)))
        progress = fraction * 100.0
        stage = str(info.get('stage') or 'Diagnóstico completo')
        detail = str(info.get('detail') or 'CorePulse continúa consolidando evidencia real.')
        started = getattr(self.app, '_complete_diagnostic_started_at', None)
        elapsed = max(0, int(time.time() - started)) if isinstance(started, (int, float)) else 0
        self.lbl_title.configure(text='Diagnóstico completo')
        self.lbl_subtitle.configure(text='Un solo flujo. Las herramientas de reparación siguen separadas.')
        self.lbl_phase.configure(text=stage.upper(), text_color=CYAN)
        self.status_badge.configure(text='EVIDENCIA REAL', text_color=CYAN, fg_color=theme_color('#0f2437'))
        self.gauge.set_state(progress, stage, value_text=f'{progress:.0f}%', sub_text='Diagnóstico integral', accent=CYAN)
        self.progress_bar.configure(progress_color=CYAN)
        self.progress_bar.set(fraction)
        self.lbl_details_title.configure(text='FASE ACTUAL')
        self.lbl_elapsed.configure(text=f'{elapsed} s')
        self.lbl_context.configure(text='DIAGNÓSTICO COMPLETO')
        samples = int(getattr(getattr(self.app, 'diagnostic_session', None), 'result', {}).get('sample_count', 0) or 0) if getattr(getattr(self.app, 'diagnostic_session', None), 'result', None) else 0
        self.lbl_samples.configure(text=str(samples))
        self.lbl_eta_title.configure(text='ESTADO')
        self.lbl_eta.configure(text='En curso')
        self.lbl_chip_duration.configure(text=f'{elapsed} s')
        self.lbl_chip_samples.configure(text=str(samples))
        self.lbl_chip_confidence.configure(text=f'{progress:.0f}%', text_color=CYAN)
        self.lbl_quality.configure(text='Escritorio, Windows, rendimiento y telemetría durante benchmark conservan su evidencia.')
        self.lbl_hint.configure(text=detail)
        self._set_findings_placeholder('Los hallazgos se correlacionan cuando todas las fases terminan.')
        if self._observed_title_labels:
            for label, name in zip(self._observed_title_labels, ('Escritorio', 'Windows', 'Benchmark', 'Bajo carga')):
                label.configure(text=name)
        phase_values = _running_phase_values(getattr(getattr(self.app, '_diagnostic_run', None), 'state', None))
        self._set_observed_values(list(zip(('Escritorio', 'Windows', 'Benchmark', 'Bajo carga'), phase_values)))
        self.lbl_interpretation.configure(text='CorePulse todavía no emite una conclusión final: primero termina todas las fases y luego correlaciona la evidencia.')

    def show_complete(self, result):
        if self._closed:
            return
        from core.diagnostic_lifecycle import is_finalized_result
        result = result if isinstance(result, dict) else {}
        if result.get('complete_diagnostic') and not is_finalized_result(result):
            self.show_cancelled()
            return
        self._finished = True
        result = result if isinstance(result, dict) else {}
        status = str(result.get('overall_status') or 'NO_EVALUABLE').upper()
        adaptive = result.get('adaptive_diagnostic') or {}
        confidence = _number(adaptive.get('confidence_percent'))
        complete = result.get('complete_diagnostic') if isinstance(result.get('complete_diagnostic'), dict) else {}
        duration = int(round(float(result.get('complete_duration_seconds') or result.get('duration_seconds') or 0)))
        samples = int(result.get('sample_count', 0) or 0)
        accent = STATUS_COLORS.get(status, DIM)
        try:
            self.btn_cancel.grid_remove()
        except Exception:
            pass
        self.lbl_title.configure(text='Diagnóstico completo finalizado' if complete else 'Diagnóstico completado')
        self.lbl_device.configure(text=f'Equipo analizado: {self._identity_name} · {self._identity_type}')
        self.lbl_subtitle.configure(text='Qué encontró CorePulse, qué evidencia lo respalda y dónde revisarlo.' if complete else 'Resumen profesional de la evidencia real reunida en esta sesión.')
        self.lbl_phase.configure(text='RESULTADO INTEGRAL' if complete else 'RESULTADO DEL DIAGNÓSTICO', text_color=accent)
        self.status_badge.configure(text=STATUS_LABELS.get(status, status.replace('_', ' ')).upper(), text_color=accent, fg_color=theme_color('#0f2437'))
        self.gauge.set_state(100, 'Resultado', value_text=status.replace('_', ' '), sub_text='', accent=accent)
        self.progress_bar.configure(progress_color=accent)
        self.progress_bar.set(1.0)
        self.lbl_details_title.configure(text='ESTADO POR COMPONENTE' if complete else 'RESUMEN DE LA SESIÓN')
        self.lbl_elapsed.configure(text=f'{duration} s')
        self.lbl_context.configure(text=str(adaptive.get('context') or 'N/A').replace('_', ' '))
        self.lbl_samples.configure(text=str(samples))
        coverage = complete.get('phase_coverage') if isinstance(complete.get('phase_coverage'), dict) else {}
        completed_phases = int(coverage.get('completed') or 0)
        total_phases = int(coverage.get('total') or 0)
        if complete and total_phases:
            coverage_text = f'{completed_phases}/{total_phases}'
            self.lbl_eta_title.configure(text='COBERTURA')
            self.lbl_eta.configure(text=coverage_text)
            chip_text = coverage_text
        else:
            self.lbl_eta_title.configure(text='CONFIANZA')
            self.lbl_eta.configure(text=f'{confidence:.0f}%' if confidence is not None else 'N/A')
            chip_text = f'{confidence:.0f}%' if confidence is not None else 'N/A'
        self.lbl_chip_duration.configure(text=f'{duration} s')
        self.lbl_chip_samples.configure(text=str(samples))
        self.lbl_chip_confidence.configure(text=chip_text, text_color=accent)
        self.lbl_quality.configure(text=(f'Diagnóstico completo · {completed_phases}/{total_phases} fases registradas · sin reparaciones automáticas · PDF opcional.' if complete and total_phases else ('Diagnóstico completo · sin reparaciones automáticas · PDF opcional.' if complete else 'Sesión válida · datos reales certificados · PDF habilitado.')))
        cpu_stats = _session_stat(result, 'cpu', 'usage_percent')
        ram_stats = _session_stat(result, 'ram', 'usage_percent')
        self.lbl_summary_title.configure(text='USO REAL DURANTE EL DIAGNÓSTICO')
        self.lbl_cpu_summary_title.configure(text='CPU promedio')
        self.lbl_ram_summary_title.configure(text='RAM promedio')
        if cpu_stats:
            cpu_avg = _pct(cpu_stats['avg'])
            self.bar_cpu.set(cpu_avg / 100.0)
            self.lbl_cpu.configure(text=f'{cpu_avg:.1f}%')
            peak = _fmt(cpu_stats.get('max'), 1, '%')
            self.lbl_cpu_detail.configure(text=f"Pico {peak} · {cpu_stats.get('samples', 0)} muestras")
        else:
            self.bar_cpu.set(0)
            self.lbl_cpu.configure(text='N/A')
            self.lbl_cpu_detail.configure(text='Sin muestras válidas')
        if ram_stats:
            ram_avg = _pct(ram_stats['avg'])
            self.bar_ram.set(ram_avg / 100.0)
            self.lbl_ram.configure(text=f'{ram_avg:.1f}%')
            mn = _fmt(ram_stats.get('min'), 1, '%')
            mx = _fmt(ram_stats.get('max'), 1, '%')
            self.lbl_ram_detail.configure(text=f"Rango {mn}–{mx} · {ram_stats.get('samples', 0)} muestras")
        else:
            self.bar_ram.set(0)
            self.lbl_ram.configure(text='N/A')
            self.lbl_ram_detail.configure(text='Sin muestras válidas')
        display_findings = _complete_findings(result, limit=4) if complete else _finding_lines(result, limit=4)
        for idx, item in enumerate(display_findings):
            if idx >= len(self._finding_rows):
                break
            dot, label = self._finding_rows[idx]
            color = STATUS_COLORS.get(item['status'], CYAN)
            dot.configure(text_color=color)
            label.configure(text=item['text'], text_color=TEXT if item['status'] in {'CRITICAL', 'WARNING'} else DIM)
        for idx in range(len(display_findings), len(self._finding_rows)):
            dot, label = self._finding_rows[idx]
            dot.configure(text_color=MUTED)
            label.configure(text='', text_color=MUTED)
        if complete:
            # V143 — el usuario termina viendo componentes y acciones, no fases internas.
            self._show_component_report(result)
            self.lbl_interpretation.configure(text=_complete_interpretation(result))
            self.lbl_hint.configure(text='Revisa el componente que requiera atención. CorePulse no aplica reparaciones automáticamente; el PDF sigue siendo opcional.')
        else:
            self._set_observed_values(_observed_metrics(result))
            self.lbl_interpretation.configure(text=_interpretation_text(result))
            self.lbl_hint.configure(text='Las barras representan el promedio real de las muestras de esta sesión. El informe PDF está habilitado.')
        self.lbl_interpretation.grid_configure(columnspan=1, padx=(10, 8))
        self.set_pdf_ready()
        self.refresh_report_access()
        self.result_actions.grid()

def show_diagnostic_experience(app):
    from gui.internal_navigation import activate_internal_page, commit_internal_page, abort_internal_page
    host, reused = activate_internal_page(app, 'diagnostic')
    existing = getattr(app, 'diagnostic_experience_panel', None)
    try:
        if reused and existing is not None and existing.winfo_exists():
            existing.lift()
            return existing
    except Exception:
        pass

    panel = None
    try:
        panel = DiagnosticExperiencePanel(app)
        if (getattr(app, 'diagnostic_result', None)
                and getattr(getattr(app, 'diagnostic_session', None), 'completed', False)
                and (not getattr(getattr(app, 'diagnostic_session', None), 'active', False))
                and (not getattr(app, '_complete_diagnostic_running', False))):
            panel.show_complete(app.diagnostic_result)
        elif getattr(app, '_complete_diagnostic_running', False):
            panel.update_complete_progress({
                'progress': getattr(app, '_complete_diagnostic_progress', 0.22),
                'stage': getattr(app, '_complete_diagnostic_stage', None) or 'Diagnóstico completo',
                'detail': 'CorePulse continúa consolidando evidencia real.',
            })
        if not commit_internal_page(app, 'diagnostic', host, panel):
            raise RuntimeError('La navegación de diagnóstico fue invalidada antes del commit.')
        return panel
    except Exception:
        abort_internal_page(app, 'diagnostic', host, panel)
        raise

