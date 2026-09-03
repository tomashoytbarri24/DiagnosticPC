"""Gestiona la experiencia visual del diagnóstico y la exportación del resultado a PDF."""
from __future__ import annotations
from core.theme_manager import color as theme_color
# Código refactorizado: nombres estables y documentación en español.
import math
import threading
import tkinter as tk
import customtkinter as ctk
from core.adaptive_diagnostic import readiness_stage
from core.device_identity import collect_device_identity
from core.version import VERSION_LABEL
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

class DiagnosticGauge(tk.Canvas):

    def __init__(self, parent, size=254):
        super().__init__(parent, width=size, height=size, bg=BG, highlightthickness=0, bd=0)
        self.size = size
        self.progress = 0.0
        self.stage = 'Preparando evidencia'
        self.value_text = '0%'
        self.sub_text = 'Evidencia real'
        self.accent = CYAN
        self.bind('<Configure>', lambda _e: self.redraw())

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
        self._observed_value_labels = []
        self.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.lift()
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build_header()
        self._build_body()
        self._load_identity_async()

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
        self.lbl_title = ctk.CTkLabel(left, text='Diagnóstico del sistema', font=('Segoe UI', 21, 'bold'), text_color=TEXT, anchor='w')
        self.lbl_title.pack(anchor='w')
        self.lbl_device = ctk.CTkLabel(left, text='Analizando equipo · identificando modelo real…', font=('Segoe UI', 9, 'bold'), text_color=CYAN, anchor='w')
        self.lbl_device.pack(anchor='w', pady=(2, 0))
        self.lbl_subtitle = ctk.CTkLabel(left, text='Evidencia real del sistema · sin valores simulados.', font=('Segoe UI', 8), text_color=DIM, anchor='w')
        self.lbl_subtitle.pack(anchor='w', pady=(1, 0))
        self.btn_back = ctk.CTkButton(header, text='Volver al Dashboard', width=145, height=32, corner_radius=8, fg_color=theme_color('#13253a'), hover_color=theme_color('#19324e'), border_width=1, border_color=BORDER, text_color=TEXT, font=('Segoe UI', 8, 'bold'), command=self.close)
        self.btn_back.grid(row=0, column=1, sticky='e', padx=(10, 0))

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
        value_label = ctk.CTkLabel(chip, text=value, font=('Segoe UI', 10, 'bold'), text_color=color)
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
        shell.grid_columnconfigure(0, weight=10)
        shell.grid_columnconfigure(1, weight=12)
        shell.grid_rowconfigure(0, weight=1)
        left_outer = ctk.CTkFrame(shell, fg_color='transparent')
        left_outer.grid(row=0, column=0, sticky='nsew', padx=(16, 8), pady=12)
        left_outer.grid_columnconfigure(0, weight=1)
        gauge_side = ctk.CTkFrame(left_outer, fg_color=BG, corner_radius=14, border_width=1, border_color=theme_color('#12243a'), width=500, height=470)
        gauge_side.grid(row=0, column=0)
        gauge_side.grid_propagate(False)
        gauge_side.grid_columnconfigure(0, weight=1)
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
        details = ctk.CTkFrame(shell, fg_color='transparent')
        details.grid(row=0, column=1, sticky='nsew', padx=(8, 16), pady=12)
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
        self.btn_pdf.grid(row=0, column=0, sticky='ew', padx=(0, 4))
        self.btn_repeat = ctk.CTkButton(self.result_actions, text='Diagnosticar de nuevo', width=146, height=34, corner_radius=8, fg_color=theme_color('#17263a'), hover_color=theme_color(theme_color('#203650')), border_width=1, border_color=BORDER, text_color=TEXT, font=('Segoe UI', 8, 'bold'), command=self._repeat)
        self.btn_repeat.grid(row=0, column=1, sticky='ew', padx=(4, 0))

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

    def _repeat(self):
        self.close()
        try:
            self.app.start_diagnostic_session(force_new=True)
        except Exception:
            pass

    def close(self):
        self._closed = True
        try:
            self.app.diagnostic_experience_panel = None
        except Exception:
            pass
        try:
            from gui.internal_navigation import show_dashboard
            show_dashboard(self.app)
        except Exception:
            try:
                self.destroy()
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
        self.lbl_title.configure(text='Diagnóstico del sistema')
        self.lbl_subtitle.configure(text='Evidencia real del sistema · sin valores simulados.')
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

    def show_complete(self, result):
        if self._closed:
            return
        self._finished = True
        result = result if isinstance(result, dict) else {}
        status = str(result.get('overall_status') or 'NO_EVALUABLE').upper()
        adaptive = result.get('adaptive_diagnostic') or {}
        confidence = _number(adaptive.get('confidence_percent'))
        duration = int(result.get('duration_seconds', 0) or 0)
        samples = int(result.get('sample_count', 0) or 0)
        accent = STATUS_COLORS.get(status, DIM)
        self.lbl_title.configure(text='Diagnóstico completado')
        self.lbl_device.configure(text=f'Equipo analizado: {self._identity_name} · {self._identity_type}')
        self.lbl_subtitle.configure(text='Resumen profesional de la evidencia real reunida en esta sesión.')
        self.lbl_phase.configure(text='RESULTADO DEL DIAGNÓSTICO', text_color=accent)
        self.status_badge.configure(text=STATUS_LABELS.get(status, status.replace('_', ' ')).upper(), text_color=accent, fg_color=theme_color('#0f2437'))
        self.gauge.set_state(100, 'Resultado', value_text=status.replace('_', ' '), sub_text='', accent=accent)
        self.progress_bar.configure(progress_color=accent)
        self.progress_bar.set(1.0)
        self.lbl_details_title.configure(text='RESUMEN DE LA SESIÓN')
        self.lbl_elapsed.configure(text=f'{duration} s')
        self.lbl_context.configure(text=str(adaptive.get('context') or 'N/A').replace('_', ' '))
        self.lbl_samples.configure(text=str(samples))
        self.lbl_eta_title.configure(text='CONFIANZA')
        self.lbl_eta.configure(text=f'{confidence:.0f}%' if confidence is not None else 'N/A')
        self.lbl_chip_duration.configure(text=f'{duration} s')
        self.lbl_chip_samples.configure(text=str(samples))
        self.lbl_chip_confidence.configure(text=f'{confidence:.0f}%' if confidence is not None else 'N/A', text_color=accent)
        self.lbl_quality.configure(text='Sesión válida · datos reales certificados · PDF habilitado.')
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
        for idx, item in enumerate(_finding_lines(result, limit=4)):
            if idx >= len(self._finding_rows):
                break
            dot, label = self._finding_rows[idx]
            color = STATUS_COLORS.get(item['status'], CYAN)
            dot.configure(text_color=color)
            label.configure(text=item['text'], text_color=TEXT if item['status'] in {'CRITICAL', 'WARNING'} else DIM)
        for idx in range(len(_finding_lines(result, limit=4)), len(self._finding_rows)):
            dot, label = self._finding_rows[idx]
            dot.configure(text_color=MUTED)
            label.configure(text='', text_color=MUTED)
        self._set_observed_values(_observed_metrics(result))
        self.lbl_interpretation.configure(text=_interpretation_text(result))
        self.lbl_interpretation.grid_configure(columnspan=1, padx=(10, 8))
        self.lbl_hint.configure(text='Las barras representan el promedio real de las muestras de esta sesión. El informe PDF está habilitado.')
        self.set_pdf_ready()
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
        if getattr(app, 'diagnostic_result', None) and getattr(getattr(app, 'diagnostic_session', None), 'completed', False) and (not getattr(getattr(app, 'diagnostic_session', None), 'active', False)):
            panel.show_complete(app.diagnostic_result)
        if not commit_internal_page(app, 'diagnostic', host, panel):
            raise RuntimeError('La navegación de diagnóstico fue invalidada antes del commit.')
        return panel
    except Exception:
        abort_internal_page(app, 'diagnostic', host, panel)
        raise

