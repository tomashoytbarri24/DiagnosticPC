"""Centro de Salud avanzado: batería, throttling, benchmarks, Windows, historial y rollback."""
from __future__ import annotations

import copy
import threading
import time
import datetime as dt
import logging
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, filedialog

import customtkinter as ctk
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from PIL import Image, ImageTk, ImageDraw

from core.theme_manager import color as theme_color
from core.battery_health import collect_battery_health, probe_battery_presence
from core.benchmark_engine import run_benchmark_suite, benchmark_profile_info
from core.benchmark_presentation import benchmark_card_data, benchmark_delta_data, benchmark_component_conclusion, benchmark_overall_summary
from core.before_after import capture_metrics, save_snapshot, load_snapshots, compare
from core.device_identity import collect_hardware_inventory
from core.windows_commands import is_admin, request_elevation, looks_like_access_denied
from performance.game_presentation import load_game_artwork, fallback_game_icon
from core.windows_health import (
    analyze_startup, analyze_services, analyze_crashes, analyze_drivers,
    compare_hardware_inventory, save_hardware_baseline, restore_point_status, create_restore_point,
)
from core.windows_repair import (
    repair_capabilities, run_integrity_diagnostic, run_windows_repair,
)
from gui.internal_navigation import show_dashboard
from gui.stable_scroll import StableScrollHost
from gui.professional_visuals import build_title_block

BG = theme_color('#06111f')
CARD = theme_color('#0d1828')
CARD2 = theme_color('#0a1524')
BORDER = theme_color('#1b3048')
TEXT = theme_color('#f4f7fb')
TEXT2 = theme_color('#b8c4d4')
MUTED = theme_color('#94a3b8')
CYAN = '#14b8ff'; GREEN = '#10b981'; AMBER = '#f59e0b'; RED = '#ef4444'; PURPLE = '#a855f7'
FONT = 'Segoe UI'
logger = logging.getLogger('CorePulse.HealthCenter')
ACTION_BG = theme_color('#0d2942')
ACTION_HOVER = theme_color('#164f7d')
ACTION_BORDER = theme_color('#1d5278')
ACTION_TEXT = theme_color('#75d2f7')
TAB_ACTIVE = theme_color('#164f7d')
TAB_HOVER = theme_color('#1b5c8f')
ERROR_BG = theme_color('#2b1d26')
ERROR_BORDER = theme_color('#693343')



def _num(v):
    try: return float(v) if v is not None else None
    except Exception: return None


def _fmt(v, unit='', digits=1):
    n = _num(v)
    return f'{n:.{digits}f}{unit}' if n is not None else 'N/A'


def _short(text, n=120):
    s = str(text or '').replace('\r',' ').replace('\n',' ').strip()
    return s if len(s) <= n else s[:n-1] + '…'


def _benchmark_live_metrics(telemetry):
    """Extrae telemetría real para el benchmark con fallbacks internos.

    La UI principal puede tener un valor válido en la estructura detallada aunque
    el alias de nivel superior aún no se haya actualizado. Este helper sólo elige
    entre lecturas reales ya presentes; no estima temperaturas.
    """
    tele = telemetry if isinstance(telemetry, dict) else {}
    cpu = tele.get('_cpu') if isinstance(tele.get('_cpu'), dict) else {}
    gpus = tele.get('_gpus') if isinstance(tele.get('_gpus'), list) else []

    def first_number(*values):
        for value in values:
            number = _num(value)
            if number is not None:
                return number
        return None

    gpu_temp = first_number(tele.get('gpu_temp'))
    gpu_usage = first_number(tele.get('gpu_usage'))
    if gpu_temp is None or gpu_usage is None:
        for gpu in gpus:
            if not isinstance(gpu, dict):
                continue
            if gpu_temp is None:
                gpu_temp = first_number(gpu.get('temperature_c'), gpu.get('hotspot_c'))
            if gpu_usage is None:
                gpu_usage = first_number(gpu.get('usage_percent'))
            if gpu_temp is not None and gpu_usage is not None:
                break

    # Temperatura CPU: primero usa aliases certificados; si el modelo concreto
    # no publica Package como alias, inspecciona el inventario real de sensores
    # y por último consulta el proveedor LHM compartido. No se estima nada.
    cpu_temp = first_number(tele.get('cpu_temp'), cpu.get('package_temp_c'), cpu.get('core_max_temp_c'), cpu.get('core_average_temp_c'))
    if cpu_temp is None:
        sensor_rows = cpu.get('sensors') if isinstance(cpu.get('sensors'), list) else []
        preferred = []
        fallback = []
        for row in sensor_rows:
            if not isinstance(row, dict):
                continue
            sensor_type = str(row.get('type') or row.get('sensor_type') or '').casefold()
            name = str(row.get('name') or row.get('sensor_name') or '').casefold()
            value = first_number(row.get('value'))
            if sensor_type != 'temperature' or value is None or not (0.0 < value < 125.0):
                continue
            fallback.append(value)
            if any(token in name for token in ('cpu package', 'package', 'core max', 'tctl', 'tdie')):
                preferred.append(value)
        if preferred:
            cpu_temp = max(preferred)
        elif fallback:
            cpu_temp = max(fallback)
    if cpu_temp is None:
        try:
            from core.lhm_provider import get_lhm_provider
            direct = get_lhm_provider().cpu_temperature() or {}
            cpu_temp = first_number(direct.get('value')) if isinstance(direct, dict) else None
        except Exception:
            cpu_temp = None

    cpu_ghz = first_number(tele.get('cpu_ghz'), cpu.get('clock_avg_ghz'), cpu.get('clock_max_ghz'))
    if cpu_ghz is None:
        try:
            import psutil
            freq = psutil.cpu_freq()
            current = getattr(freq, 'current', None) if freq else None
            cpu_ghz = float(current) / 1000.0 if current else None
        except Exception:
            cpu_ghz = None

    return {
        'cpu_temp': cpu_temp,
        'cpu_ghz': cpu_ghz,
        'cpu_usage': first_number(tele.get('cpu_usage'), cpu.get('total_load_percent')),
        'ram_usage': first_number(tele.get('ram_usage')),
        'gpu_temp': gpu_temp,
        'gpu_usage': gpu_usage,
    }


def _benchmark_observation_fallback(key, suite):
    """Presenta min/promedio/máximo muestreado si antes/después no existe."""
    summary = suite.get('telemetry_summary') if isinstance(suite, dict) else {}
    row = summary.get(key) if isinstance(summary, dict) else None
    if not isinstance(row, dict):
        return None
    lo = _num(row.get('min')); avg = _num(row.get('avg')); hi = _num(row.get('max'))
    if lo is None and avg is None and hi is None:
        return None
    meta = {
        'cpu_temp': ('Temperatura del CPU', '°C', 1),
        'cpu_ghz': ('Velocidad del CPU', 'GHz', 2),
        'ram_usage': ('Uso de memoria RAM', '%', 1),
        'gpu_temp': ('Temperatura de la GPU', '°C', 1),
    }
    label, unit, digits = meta.get(key, (key, '', 1))
    vals = [v for v in (lo, avg, hi) if v is not None]
    value = f"{min(vals):.{digits}f} {unit} → {max(vals):.{digits}f} {unit}".replace('  ', ' ')
    change = f"Promedio {avg:.{digits}f} {unit} · Pico {max(vals):.{digits}f} {unit} durante el benchmark.".replace('  ', ' ') if avg is not None else 'Lecturas reales observadas durante el benchmark.'
    tone = 'cyan'
    peak = max(vals)
    if key in {'cpu_temp', 'gpu_temp'} and peak >= 90:
        tone = 'red'
    elif key in {'cpu_temp', 'gpu_temp'} and peak >= 80:
        tone = 'amber'
    return {'label': label, 'value': value, 'change': change, 'tone': tone}


def _game_source_label(value):
    raw = str(value or 'N/A').upper().strip()
    return {
        'MANUAL': 'Agregado manualmente',
        'STEAM': 'Detectado por Steam',
        'EPIC': 'Detectado por Epic',
        'RTSS': 'Detectado por RTSS',
        'LEARNED': 'Detectado anteriormente',
        'N/A': 'N/A',
    }.get(raw, raw.title() if raw else 'N/A')


def _state_label(value):
    raw = str(value or 'N/A').strip().upper()
    return {
        'CONFIRMED': 'Confirmado',
        'SUSPECTED': 'Sospechado',
        'WATCHING': 'Observando',
        'NO_EVIDENCE': 'Sin evidencia',
        'NONE': 'Sin evidencia',
        'N/A': 'N/A',
    }.get(raw, str(value or 'N/A'))


def _reason_label(value):
    raw = str(value or '').strip().upper()
    return {
        'THERMAL': 'Límite térmico',
        'THERMAL_HEADROOM': 'Margen térmico reducido',
        'POWER': 'Límite de potencia',
        'POWER_OR_PLATFORM_LIMIT': 'Potencia o límite de plataforma',
    }.get(raw, str(value or 'Sin evidencia'))


def _confidence_label(value):
    raw = str(value or 'N/A').strip().upper()
    return {'LOW': 'Baja', 'MEDIUM': 'Media', 'HIGH': 'Alta', 'N/A': 'N/A'}.get(raw, str(value or 'N/A'))



def _impact_label(value):
    raw = str(value or 'N/A').strip().upper()
    return {
        'ALTO (EVENTO DE DEGRADACIÓN)': 'Alto · Windows registró degradación',
        'MEDIO': 'Medio', 'BAJO': 'Bajo', 'NO_MEDIDO': 'No medido', 'N/A': 'N/A',
    }.get(raw, str(value or 'N/A'))


def _service_state_label(value):
    raw = str(value or 'N/A').strip().upper()
    return {'RUNNING':'En ejecución','STOPPED':'Detenido','PAUSED':'Pausado','START PENDING':'Iniciando','STOP PENDING':'Deteniendo','N/A':'N/A'}.get(raw, str(value or 'N/A'))


def _start_mode_label(value):
    raw = str(value or 'N/A').strip().upper()
    return {'AUTO':'Automático','AUTOMATIC':'Automático','MANUAL':'Manual','DISABLED':'Deshabilitado','BOOT':'Arranque','SYSTEM':'Sistema','N/A':'N/A'}.get(raw, str(value or 'N/A'))


def _driver_status_label(value):
    raw = str(value or 'N/A').strip().upper()
    return {'DEVICE_PROBLEM':'Problema del dispositivo','UNSIGNED':'No firmado','OLD':'Antiguo','OK':'Correcto','N/A':'N/A'}.get(raw, str(value or 'N/A'))


def _severity_label(value):
    raw = str(value or 'N/A').strip().upper()
    return {'CRITICAL':'Crítica','WARNING':'Advertencia','INFO':'Informativa','NORMAL':'Normal','N/A':'N/A'}.get(raw, str(value or 'N/A'))


def _bench_provider_label(value):
    raw = str(value or 'N/A')
    return {
        'CorePulse SHA-256 workload': 'Carga SHA-256 de CorePulse',
        'CorePulse memory copy': 'Copia de memoria de CorePulse',
        'CorePulse sustained memory copy': 'Memoria sostenida de CorePulse',
        'CorePulse sequential file I/O': 'E/S secuencial de CorePulse',
        'Windows WinSAT D3D': 'Windows WinSAT · gráficos 3D',
        'CorePulse OpenGL render workload': 'Carga gráfica OpenGL de CorePulse',
    }.get(raw, raw)


def _source_label(value):
    raw = str(value or 'N/A')
    return {
        'root/WMI Battery* classes': 'Windows WMI · batería',
        'powercfg /batteryreport /xml': 'Informe de batería de Windows',
        'psutil.sensors_battery': 'API de batería del sistema',
        'LibreHardwareMonitor': 'LibreHardwareMonitor',
    }.get(raw, raw)


def _profile_label(value):
    raw = str(value or 'UNKNOWN').upper()
    return {
        'BALANCED': 'Equilibrado', 'HIGH_PERFORMANCE': 'Alto rendimiento', 'MAXIMUM_PERFORMANCE': 'Máximo rendimiento', 'POWER_SAVER': 'Ahorro de energía',
        'GAMING': 'Máximo rendimiento', 'COOL': 'Ahorro de energía', 'AUTO': 'Automático (legado)',
        'UNKNOWN': 'Leyendo plan de Windows…', 'N/A': 'N/A',
    }.get(raw, raw)


class HealthCenterPanel:
    TABS = (
        ('summary', 'Estado general'), ('battery', 'Batería'),
        ('windows', 'Windows'), ('repair', 'Reparación'),
        ('history', 'Historial'), ('recovery', 'Recuperación'),
    )

    def __init__(self, app, host, *, performance_only=False, external_scroll=None):
        self.app = app; self.host = host; self._alive = True; self._visible = True; self._performance_only = bool(performance_only); self._external_scroll = external_scroll; self._tab='performance' if self._performance_only else 'summary'; self._jobs=set()
        self._battery=None; self._startup=None; self._services=None; self._crashes=None; self._drivers=None; self._hw=None; self._restore=None; self._bench=None
        self._seed_preloaded_battery_state()
        self._repair_diagnostic=None; self._repair_result=None; self._repair_progress=None; self.lbl_repair_progress=None
        self.btn_repair_diag=None; self.btn_repair_fix=None; self.repair_progress_bar=None
        self._health_chart_photo = None
        # Referencias CTkImage + cache por identidad/ruta para portadas sin parpadeo.
        self._game_artwork_cache = {}
        self._game_artwork_images = []
        self._game_artwork_generation = 0
        self._game_artwork_worker = None
        self._game_placeholder_cache = {}
        self._game_action_popup = None
        self._bench_compare = None
        self._benchmark_progress = 0.0
        self._benchmark_stage = 'Listo para iniciar'
        self._benchmark_detail = 'Elige duración y componentes antes de iniciar.'
        self._benchmark_profile_key = 'standard'
        self._benchmark_component_flags = {'cpu': True, 'ram': True, 'ssd': True, 'gpu': True}
        self._benchmark_profile_var = None
        self._benchmark_component_vars = {}
        self._benchmark_selection_label = None
        self.bench_progress_bar = None
        self.lbl_bench_progress = None
        self._performance_after_id = None
        self._last_performance_generation = None
        self._performance_section = 'home'
        self._game_library_filter = 'all'
        # V0.10.2.81w — Servicios de Windows se muestran completos mediante
        # paginación para no crear cientos de widgets en un único frame.
        self._services_page = 0
        self._services_page_size = 40
        # V113 — Controladores completos mediante paginación. Se conserva el
        # orden de prioridad del hardware sin limitar la vista a 12 filas.
        self._drivers_page = 0
        self._drivers_page_size = 40
        # V0.10.2.81w — eventos de estabilidad paginados para mantener la UI
        # fluida aunque Windows tenga muchos registros en el período analizado.
        self._stability_page = 0
        self._stability_page_size = 25
        self._stability_show_technical = False
        # V0.10.2.89w — Windows deja de ser una vista monolítica. Cada bloque
        # vive en una sección interna y el resumen sólo muestra estado + acceso.
        self._windows_section = 'summary'

        # Render stability preserved — coalesced rebuilds for Gaming/Health Center
        # Juego, benchmark y perfiles pueden disparar varios cambios casi juntos.
        # Coalescemos rebuilds para no destruir/recrear el árbol CTk en ráfaga.
        self._rendering = False
        self._render_pending = False
        self._render_after_id = None
        self._restore_scroll_fraction = None

        self._build()
        # Primer frame con estructura local y placeholders. Inventarios/lecturas
        # secundarias se cargan después de publicar la página para que el cambio
        # de pestaña no espere a trabajo que no es necesario para verla.
        self._render()
        try:
            self.frame.after_idle(self.refresh)
        except Exception:
            self.refresh()
        if self._performance_only:
            self._schedule_performance_status_tick()

    def _seed_preloaded_battery_state(self):
        """Fija presencia antes del primer render para que la grilla no salte."""
        cached = getattr(self.app, 'battery_health_cache', None)
        if isinstance(cached, dict):
            self._battery = copy.deepcopy(cached)
            return
        presence = getattr(self.app, 'battery_presence_cache', None)
        if not isinstance(presence, dict) or not presence.get('resolved'):
            try:
                presence = probe_battery_presence(
                    getattr(self.app, 'latest_telemetry', {}) or {},
                    getattr(self.app, '_device_identity_cache', None),
                )
                if isinstance(presence, dict):
                    self.app.battery_presence_cache = presence
            except Exception:
                presence = None
        if isinstance(presence, dict) and presence.get('resolved'):
            self._battery = {
                'present': bool(presence.get('present')),
                '_presence_only': bool(presence.get('present')),
                'presence_source': presence.get('source'),
                'sources': [presence.get('source')] if presence.get('source') else [],
                'policy': 'REAL_OR_NA',
            }

    def _sync_preloaded_battery_state(self):
        cached = getattr(self.app, 'battery_health_cache', None)
        if isinstance(cached, dict) and cached != self._battery:
            self._battery = copy.deepcopy(cached)
            return True
        return False

    def apply_battery_health_cache(self, result):
        if not self._alive or not isinstance(result, dict):
            return
        self._battery = copy.deepcopy(result)
        if self._visible and self._tab in ('summary', 'battery'):
            self._request_render(1)

    def widget(self): return self.frame

    def _build(self):
        self.frame = ctk.CTkFrame(self.host, fg_color=BG, corner_radius=0)
        self.frame.pack(fill='both', expand=True)

        self.tab_buttons = {}
        if not self._performance_only:
            header = ctk.CTkFrame(self.frame, fg_color='transparent')
            header.pack(fill='x', padx=20, pady=(12, 4))
            self.btn_header_back = self._button(
                header, 'Volver al monitoreo', lambda: show_dashboard(self.app),
                variant='ghost', width=172, height=31
            )
            self.btn_header_back.pack(side='left', pady=(8, 0))

            titles = ctk.CTkFrame(header, fg_color='transparent')
            titles.pack(side='left', fill='x', expand=True, padx=(14, 12))
            self.header_hero = build_title_block(
                titles,
                eyebrow='Estado y mantenimiento preventivo',
                title='Centro de salud',
                subtitle='Mantenimiento, estabilidad y recuperación en un solo lugar.',
                accent=GREEN,
                badges=(),
                title_size=22,
            )
            self.header_hero['frame'].pack(anchor='w', fill='x')

            status = ctk.CTkFrame(
                header, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=8
            )
            status.pack(side='right', padx=(8, 0), pady=(8, 0))
            ctk.CTkLabel(status, text='●', font=(FONT, 9, 'bold'), text_color=GREEN).pack(side='left', padx=(10, 5), pady=7)
            self.lbl_status = ctk.CTkLabel(
                status, text='Datos reales · REAL_OR_NA', font=(FONT, 9, 'bold'), text_color=TEXT2
            )
            self.lbl_status.pack(side='left', padx=(0, 10), pady=7)
            self._sync_header_context()

        # Gaming puede suministrar su propio StableScrollHost. De ese modo el
        # resumen del hub + perfiles + Game Boost + biblioteca + diagnóstico
        # comparten UN solo scroll vertical, sin scroll anidado.
        if self._performance_only and self._external_scroll is not None:
            self.scroll = self._external_scroll
            self.body = ctk.CTkFrame(self.frame, fg_color=BG, corner_radius=0)
            self.body.pack(fill='x', expand=False)
        else:
            self.scroll = StableScrollHost(self.frame, fg_color=BG)
            self.scroll.pack(fill='both', expand=True, padx=15 if not self._performance_only else 0, pady=(0, 10))
            self.body = self.scroll.content
        self._apply_tab_style()

    def _header_context(self):
        contexts = {
            'summary': {
                'button_text': 'Volver al monitoreo',
                'button_width': 172,
                'button_command': lambda: show_dashboard(self.app),
                'eyebrow': 'Estado y mantenimiento preventivo',
                'title': 'Centro de salud',
                'subtitle': 'Mantenimiento, estabilidad y recuperación en un solo lugar.',
            },
            'battery': {
                'button_text': 'Volver a Centro de salud',
                'button_width': 186,
                'button_command': lambda: self._select_tab('summary'),
                'eyebrow': 'Autonomía y desgaste',
                'title': 'Salud de batería',
                'subtitle': 'Capacidad, desgaste, ciclos y autonomía usando únicamente fuentes disponibles del sistema.',
            },
            'windows': {
                'button_text': 'Volver a Centro de salud',
                'button_width': 186,
                'button_command': lambda: self._select_tab('summary'),
                'eyebrow': 'Diagnóstico de Windows',
                'title': 'Análisis de Windows',
                'subtitle': 'Revisa inicio, servicios, estabilidad y controladores por separado, sin saturar una sola pantalla.',
            },
            'repair': {
                'button_text': 'Volver a Centro de salud',
                'button_width': 186,
                'button_command': lambda: self._select_tab('summary'),
                'eyebrow': 'DISM y SFC',
                'title': 'Reparación de Windows',
                'subtitle': 'Diagnóstico de integridad y reparación guiada con DISM y SFC, sin mezclarlo con Tweaks.',
            },
            'history': {
                'button_text': 'Volver a Centro de salud',
                'button_width': 186,
                'button_command': lambda: self._select_tab('summary'),
                'eyebrow': 'Comparativas',
                'title': 'Historial y cambios',
                'subtitle': 'Antes vs Después, benchmark e inventario comparado del hardware con evidencia local.',
            },
            'recovery': {
                'button_text': 'Volver a Centro de salud',
                'button_width': 186,
                'button_command': lambda: self._select_tab('summary'),
                'eyebrow': 'Protección y rollback',
                'title': 'Recuperación y rollback',
                'subtitle': 'Protección antes de cambios delicados. CorePulse no habilita Restaurar sistema sin tu autorización.',
            },
            'performance': {
                'button_text': 'Volver a Centro de salud',
                'button_width': 186,
                'button_command': lambda: self._select_tab('summary'),
                'eyebrow': 'Gaming y perfiles',
                'title': 'Rendimiento y throttling térmico',
                'subtitle': 'Perfiles de energía seguros, detección automática de juegos y evidencia real de throttling.',
            },
        }
        return contexts.get(self._tab, contexts['summary'])

    def _sync_header_context(self):
        if self._performance_only:
            return
        ctx = self._header_context()
        try:
            self.btn_header_back.configure(
                text=ctx['button_text'],
                command=ctx['button_command'],
                width=ctx.get('button_width', 172),
            )
        except Exception:
            pass
        try:
            self.header_hero['eyebrow'].configure(text=ctx['eyebrow'])
            self.header_hero['title'].configure(text=ctx['title'])
            self.header_hero['subtitle'].configure(text=ctx['subtitle'])
        except Exception:
            pass

    def _apply_tab_style(self):
        for key, b in self.tab_buttons.items():
            active = key == self._tab
            try:
                b.configure(
                    fg_color=TAB_ACTIVE if active else 'transparent',
                    hover_color=TAB_HOVER if active else theme_color('#102840'),
                    border_color=ACTION_BORDER if active else BORDER,
                    text_color=TEXT if active else TEXT2,
                )
            except Exception:
                pass

    def _button(self, parent, text, command, *, variant='secondary', width=None, height=31):
        common = dict(
            text=text, command=command, height=height, corner_radius=7,
            border_width=1, font=(FONT, 10, 'bold')
        )
        if width is not None:
            common['width'] = width
        if variant == 'primary':
            common.update(fg_color=TAB_ACTIVE, hover_color=TAB_HOVER, border_color=ACTION_BORDER, text_color=TEXT)
        elif variant == 'ghost':
            common.update(fg_color='transparent', hover_color=theme_color('#102840'), border_color=BORDER, text_color=TEXT2)
        elif variant == 'tab':
            common.update(fg_color='transparent', hover_color=theme_color('#102840'), border_color=BORDER, text_color=TEXT2)
        else:
            common.update(fg_color=ACTION_BG, hover_color=ACTION_HOVER, border_color=ACTION_BORDER, text_color=ACTION_TEXT)
        return ctk.CTkButton(parent, **common)

    def _select_tab(self,key):
        previous = self._tab
        self._tab=key
        if key == 'windows' and previous != 'windows':
            self._windows_section = 'summary'
        self._apply_tab_style()
        self._sync_header_context()
        self._render()
        self._lazy_load(key)

    def _clear(self):
        for child in list(self.body.winfo_children()):
            try: child.destroy()
            except Exception: pass

    def _title(self, text, sub=None):
        # V0.10.2.81w — el contexto principal de cada módulo de salud vive en el
        # encabezado superior. En vistas internas evitamos duplicar el mismo
        # título y el mismo retorno dentro del cuerpo.
        if not self._performance_only and self._tab != 'summary':
            return

        ctk.CTkLabel(
            self.body, text=text, font=(FONT, 16, 'bold'), text_color=TEXT, anchor='w'
        ).pack(fill='x', padx=10, pady=((6 if self._tab != 'summary' else 8), 2))
        if sub:
            ctk.CTkLabel(
                self.body, text=sub, font=(FONT, 10), text_color=MUTED, anchor='w',
                justify='left', wraplength=1120
            ).pack(fill='x', padx=10, pady=(0, 9))

    def _card(self, parent=None):
        return ctk.CTkFrame(
            parent or self.body, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=9
        )

    def _kv(self, parent, label, value, color=TEXT):
        """Fila clave/valor estable. Evita que textos largos queden pegados o fuera de la tarjeta."""
        row = ctk.CTkFrame(parent, fg_color='transparent')
        row.pack(fill='x', padx=14, pady=4)
        row.grid_columnconfigure(0, weight=0, minsize=210)
        row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            row, text=label, font=(FONT, 9), text_color=MUTED,
            anchor='w', justify='left', width=200
        ).grid(row=0, column=0, sticky='nw', padx=(0, 12))
        ctk.CTkLabel(
            row, text=str(value), font=(FONT, 10, 'bold'), text_color=color,
            anchor='e', justify='right', wraplength=760
        ).grid(row=0, column=1, sticky='ne')


    def _render_compact_table(self, parent, columns, rows, empty_text):
        frame = ctk.CTkFrame(parent, fg_color=theme_color('#071626'), border_width=1, border_color=BORDER, corner_radius=8)
        frame.pack(fill='x', padx=14, pady=(6, 12))

        grid = ctk.CTkFrame(frame, fg_color='transparent')
        grid.pack(fill='x', padx=0, pady=0)

        weights = []
        wraps = []
        for col in columns:
            weights.append(int(col.get('weight', 1)))
            wraps.append(int(col.get('wrap', 220)))
        for idx, weight in enumerate(weights):
            grid.grid_columnconfigure(idx, weight=weight, uniform='health_table_cols')

        header_bg = theme_color('#0f253a')
        for idx, col in enumerate(columns):
            ctk.CTkLabel(
                grid,
                text=str(col.get('title', '')).upper(),
                font=(FONT, 8, 'bold'),
                text_color=TEXT2,
                fg_color=header_bg,
                anchor='w',
                justify='left',
                padx=8,
                pady=6,
                corner_radius=0,
            ).grid(row=0, column=idx, sticky='nsew', padx=(1 if idx else 0, 0), pady=(0, 1))

        if not rows:
            ctk.CTkLabel(
                grid, text=empty_text, font=(FONT, 9), text_color=MUTED,
                anchor='w', justify='left', wraplength=980,
            ).grid(row=1, column=0, columnspan=len(columns), sticky='ew', padx=10, pady=10)
            return

        for r_idx, row_values in enumerate(rows, start=1):
            bg = theme_color('#0a1b2d') if r_idx % 2 else theme_color('#0c2035')
            for c_idx, value in enumerate(row_values):
                ctk.CTkLabel(
                    grid,
                    text=str(value),
                    font=(FONT, 8),
                    text_color=TEXT,
                    fg_color=bg,
                    anchor='w',
                    justify='left',
                    wraplength=wraps[c_idx],
                    padx=8,
                    pady=7,
                ).grid(row=r_idx, column=c_idx, sticky='nsew', padx=(1 if c_idx else 0, 0), pady=(0, 1))

    def _summary_box(self, parent, title, value, detail, color):
        f = self._card(parent)
        f.pack(side='left', fill='both', expand=True, padx=5)
        ctk.CTkLabel(
            f, text=title, font=(FONT, 9, 'bold'), text_color=TEXT2, anchor='w'
        ).pack(fill='x', padx=14, pady=(12, 3))
        ctk.CTkLabel(
            f, text=value, font=(FONT, 22, 'bold'), text_color=color, anchor='w'
        ).pack(fill='x', padx=14)
        ctk.CTkLabel(
            f, text=detail, font=(FONT, 9), text_color=MUTED, anchor='w',
            wraplength=275, justify='left'
        ).pack(fill='x', padx=14, pady=(3, 12))

    def _battery_summary_card(self, parent, column, title, value, detail, accent, *, progress=None):
        """Tarjeta de batería con la misma jerarquía visual del Resumen principal."""
        card = ctk.CTkFrame(
            parent, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=12
        )
        card.grid(row=0, column=column, sticky='nsew', padx=(0 if column == 0 else 5, 0 if column == 3 else 5))
        ctk.CTkLabel(
            card, text=str(title).upper(), font=(FONT, 9, 'bold'),
            text_color=TEXT2, anchor='w', justify='left'
        ).pack(fill='x', padx=14, pady=(12, 2))
        ctk.CTkLabel(
            card, text=str(value), font=(FONT, 26, 'bold'),
            text_color=TEXT, anchor='w', justify='left'
        ).pack(fill='x', padx=14)
        ctk.CTkLabel(
            card, text=str(detail), font=(FONT, 9, 'bold'),
            text_color=accent, anchor='w', justify='left', wraplength=245
        ).pack(fill='x', padx=14, pady=(2, 7))
        if progress is not None:
            try:
                amount = max(0.0, min(1.0, float(progress)))
            except Exception:
                amount = 0.0
            bar = ctk.CTkProgressBar(
                card, height=5, corner_radius=999,
                fg_color=theme_color('#14283b'), progress_color=accent
            )
            bar.pack(fill='x', padx=14, pady=(0, 12))
            bar.set(amount)
        else:
            # Conserva el remate/acento del Resumen sin inventar una escala para
            # métricas como ciclos o autonomía.
            ctk.CTkFrame(card, height=5, fg_color=accent, corner_radius=999).pack(
                fill='x', padx=14, pady=(0, 12)
            )
        return card

    def _battery_detail_card(self, parent, row, column, title, value, accent, detail=''):
        """Estadística secundaria compacta; sólo presenta evidencia ya recolectada."""
        card = ctk.CTkFrame(
            parent, fg_color=CARD2, border_width=1, border_color=BORDER, corner_radius=10
        )
        card.grid(row=row, column=column, sticky='nsew', padx=5, pady=5)
        ctk.CTkLabel(
            card, text=str(title).upper(), font=(FONT, 8, 'bold'),
            text_color=MUTED, anchor='w'
        ).pack(fill='x', padx=13, pady=(10, 2))
        ctk.CTkLabel(
            card, text=str(value), font=(FONT, 17, 'bold'),
            text_color=TEXT, anchor='w'
        ).pack(fill='x', padx=13)
        if detail:
            ctk.CTkLabel(
                card, text=str(detail), font=(FONT, 8, 'bold'),
                text_color=accent, anchor='w', justify='left', wraplength=320
            ).pack(fill='x', padx=13, pady=(2, 10))
        else:
            ctk.CTkFrame(card, height=3, fg_color=accent, corner_radius=999).pack(
                fill='x', padx=13, pady=(7, 11)
            )
        return card


    def _battery_wear_visual(self, wear):
        """Color visual del desgaste. No convierte el color en diagnóstico de fallo."""
        value = _num(wear)
        if value is None:
            return MUTED
        # Bandas visuales deliberadamente simples: cuanto mayor es la capacidad
        # perdida frente al diseño, más cálido es el acento. No son umbrales de
        # avería ni sustituyen el porcentaje real reportado/calculado.
        if value < 20.0:
            return GREEN
        if value < 35.0:
            return AMBER
        return RED

    def _battery_wear_state_label(self, wear):
        """Etiqueta visual breve; nunca sustituye el porcentaje real de desgaste."""
        value = _num(wear)
        if value is None:
            return 'Sin datos'
        if value < 20.0:
            return 'Bajo'
        if value < 35.0:
            return 'Moderado'
        return 'Alto'

    def _battery_wear_card(self, parent, row, column, wear):
        """Tarjeta vertical de desgaste con composición interna centrada y limpia."""
        accent = self._battery_wear_visual(wear)
        value = _fmt(wear, '%')
        state = self._battery_wear_state_label(wear)
        card = ctk.CTkFrame(
            parent, fg_color=CARD2, border_width=1, border_color=BORDER, corner_radius=10
        )
        card.grid(
            row=row, column=column, rowspan=2, sticky='nsew',
            padx=5, pady=5
        )
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(1, weight=1)

        # Conserva el encabezado en la misma posición que las demás tarjetas.
        ctk.CTkLabel(
            card, text='DESGASTE', font=(FONT, 8, 'bold'),
            text_color=MUTED, anchor='w'
        ).grid(row=0, column=0, sticky='ew', padx=15, pady=(14, 0))

        # El porcentaje y su lectura breve ocupan el centro útil de la tarjeta.
        # Así la tarjeta mantiene exactamente su forma exterior pero deja de
        # acumular todo el contenido en la esquina superior izquierda.
        content = ctk.CTkFrame(card, fg_color='transparent')
        content.grid(row=1, column=0, sticky='nsew', padx=15, pady=(0, 12))
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(0, weight=1)
        content.grid_rowconfigure(3, weight=1)
        ctk.CTkLabel(
            content, text=value, font=(FONT, 31, 'bold'),
            text_color=accent if value != 'N/A' else MUTED, anchor='center'
        ).grid(row=1, column=0, sticky='ew', pady=(0, 2))
        ctk.CTkLabel(
            content, text=state, font=(FONT, 10, 'bold'),
            text_color=accent if value != 'N/A' else MUTED, anchor='center'
        ).grid(row=2, column=0, sticky='ew')
        return card


    def _health_tone(self, severity):
        raw = str(severity or 'UNKNOWN').upper()
        if raw in ('CRITICAL', 'ERROR'):
            return RED
        if raw in ('WARNING', 'ELEVATED'):
            return AMBER
        if raw in ('NORMAL',):
            return GREEN
        if raw in ('INFO', 'OBSERVING'):
            return CYAN
        return MUTED

    def _health_authority_label(self, value):
        raw = str(value or '').upper()
        return {
            'INSTANT_CERTIFIED_TELEMETRY': 'Telemetría certificada actual',
            'REALTIME_AGENT_ROLLING_EVIDENCE': 'Agente · evidencia sostenida',
            'INSTANT_AND_ROLLING_EVIDENCE': 'Telemetría + evidencia sostenida',
        }.get(raw, 'Evidencia aún no consolidada')

    def _live_health_for_summary(self):
        """Usa la autoridad ya calculada por CorePulse; no recalcula ni estima."""
        result = getattr(self.app, 'current_live_health', None)
        return result if isinstance(result, dict) else {}

    def _compact_metric_row(self, parent, label, value, detail='', color=TEXT2):
        row = ctk.CTkFrame(parent, fg_color=CARD2, border_width=1, border_color=BORDER, corner_radius=7)
        row.pack(fill='x', padx=10, pady=3)
        row.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            row, text=label, font=(FONT, 9, 'bold'), text_color=TEXT2,
            anchor='w', justify='left'
        ).grid(row=0, column=0, sticky='w', padx=(10, 8), pady=(7, 0))
        ctk.CTkLabel(
            row, text=str(value), font=(FONT, 10, 'bold'), text_color=color,
            anchor='e', justify='right'
        ).grid(row=0, column=1, sticky='e', padx=(8, 10), pady=(7, 0))
        if detail:
            ctk.CTkLabel(
                row, text=str(detail), font=(FONT, 8), text_color=MUTED,
                anchor='w', justify='left', wraplength=300
            ).grid(row=1, column=0, columnspan=2, sticky='ew', padx=10, pady=(1, 7))
        else:
            row.grid_rowconfigure(1, minsize=5)
        return row

    def _health_module_visual_profile(self, title):
        profiles = {
            'Batería': {
                'icon': '🔋', 'category': 'Autonomía y desgaste', 'accent': AMBER,
                'bg': theme_color('#2d2413'), 'border': theme_color('#6d5421'),
                'tags': ('Salud', 'Ciclos', 'Autonomía')
            },
            'Windows': {
                'icon': '🪟', 'category': 'Inicio y servicios', 'accent': CYAN,
                'bg': theme_color('#11283a'), 'border': theme_color('#2f6084'),
                'tags': ('Inicio', 'Servicios', 'Drivers')
            },
            'Reparación': {
                'icon': '🛠', 'category': 'DISM y SFC', 'accent': AMBER,
                'bg': theme_color('#2b2216'), 'border': theme_color('#6d4d1f'),
                'tags': ('Integridad', 'DISM', 'SFC')
            },
            'Historial y cambios': {
                'icon': '📈', 'category': 'Comparativas', 'accent': CYAN,
                'bg': theme_color('#122433'), 'border': theme_color('#2d617b'),
                'tags': ('Antes/Después', 'Benchmark', 'Cambios HW')
            },
            'Recuperación': {
                'icon': '🛡', 'category': 'Protección y rollback', 'accent': GREEN,
                'bg': theme_color('#13271f'), 'border': theme_color('#245d43'),
                'tags': ('Restauración', 'Rollback', 'Seguridad')
            },
            'Rendimiento': {
                'icon': '🎮', 'category': 'Gaming y perfiles', 'accent': theme_color('#d28bff'),
                'bg': theme_color('#271733'), 'border': theme_color('#5c3d7d'),
                'tags': ('Throttling', 'Benchmark', 'Perfiles')
            },
        }
        return profiles.get(title, {
            'icon': '•', 'category': 'Módulo', 'accent': TEXT2,
            'bg': CARD2, 'border': BORDER, 'tags': ()
        })

    def _health_module_card(self, parent, row, column, title, description, status, color, command, button_text='Abrir'):
        card = self._card(parent)
        card.grid(row=row, column=column, sticky='nsew', padx=5, pady=5)
        card.grid_columnconfigure(0, weight=1)

        profile = self._health_module_visual_profile(title)
        icon_text = profile['icon']
        chip_text = profile['category']
        accent_color = profile['accent']
        accent_bg = profile['bg']
        accent_border = profile['border']
        tags = tuple(profile.get('tags') or ())

        top = ctk.CTkFrame(card, fg_color='transparent')
        top.pack(fill='x', padx=13, pady=(11, 3))

        icon_label = ctk.CTkLabel(
            top, text=icon_text, font=(FONT, 24, 'bold'), text_color=accent_color,
            anchor='center', justify='center', width=30
        )
        icon_label.pack(side='left', padx=(0, 7), pady=(3, 0))

        text_col = ctk.CTkFrame(top, fg_color='transparent')
        text_col.pack(side='left', fill='x', expand=True)
        ctk.CTkLabel(
            text_col, text=chip_text, font=(FONT, 8, 'bold'), text_color=accent_color,
            anchor='w', justify='left'
        ).pack(fill='x', pady=(1, 1))
        ctk.CTkLabel(
            text_col, text=title, font=(FONT, 13, 'bold'), text_color=TEXT,
            anchor='w', justify='left'
        ).pack(fill='x')

        ctk.CTkLabel(
            card, text=description, font=(FONT, 9), text_color=MUTED,
            anchor='w', justify='left', wraplength=300
        ).pack(fill='x', padx=13, pady=(0, 8))

        if tags:
            tags_row = ctk.CTkFrame(card, fg_color='transparent')
            tags_row.pack(fill='x', padx=12, pady=(0, 8))
            for idx, tag in enumerate(tags):
                pill = ctk.CTkFrame(
                    tags_row, fg_color=accent_bg, border_width=1, border_color=accent_border, corner_radius=999
                )
                pill.pack(side='left', padx=(0, 6 if idx < len(tags) - 1 else 0), pady=0)
                ctk.CTkLabel(
                    pill, text=str(tag), font=(FONT, 8, 'bold'), text_color=accent_color,
                    anchor='center', justify='center'
                ).pack(padx=9, pady=4)

        status_box = ctk.CTkFrame(
            card, fg_color=CARD2, border_width=1, border_color=BORDER, corner_radius=6
        )
        status_box.pack(fill='x', padx=12, pady=(0, 9))
        ctk.CTkLabel(
            status_box, text='Estado actual', font=(FONT, 8, 'bold'),
            text_color=TEXT2, anchor='w', justify='left'
        ).pack(fill='x', padx=9, pady=(5, 0))
        ctk.CTkLabel(
            status_box, text=str(status), font=(FONT, 9, 'bold'),
            text_color=color, anchor='w', justify='left', wraplength=275
        ).pack(fill='x', padx=9, pady=(1, 5))
        self._button(card, button_text, command, variant='secondary', height=29).pack(
            fill='x', padx=12, pady=(0, 12)
        )
        return card

    def _capture_scroll_fraction(self):
        try:
            first, _last = self.scroll.yview()
            return max(0.0, min(1.0, float(first)))
        except Exception:
            return 0.0

    def _request_render(self, delay=0):
        """Agrupa renders dinámicos y espera al scroll si está en movimiento."""
        if not self._alive:
            return
        if self._rendering:
            self._render_pending = True
            return
        if self._render_after_id is not None:
            return
        try:
            if self.scroll.is_scrolling():
                self.scroll.defer_until_idle(self._request_render)
                return
        except Exception:
            pass

        def run():
            self._render_after_id = None
            if self._alive:
                self._render()

        try:
            self._render_after_id = self.app.after(max(0, int(delay)), run)
        except Exception:
            self._render_after_id = None
            run()

    def _finalize_render(self):
        if not self._alive:
            self._rendering = False
            return
        try:
            self.body.update_idletasks()
            self.frame.update_idletasks()
        except Exception:
            pass

        # El árbol nuevo ya tiene geometría: recién ahora recalcular scrollregion.
        try:
            self.scroll._refresh_geometry()
        except Exception:
            try:
                self.scroll._schedule_geometry(0)
            except Exception:
                pass

        fraction = self._restore_scroll_fraction
        self._restore_scroll_fraction = None
        if fraction is not None:
            try:
                self.scroll.canvas.yview_moveto(max(0.0, min(1.0, float(fraction))))
            except Exception:
                try:
                    self.scroll.yview_moveto(fraction)
                except Exception:
                    pass

        # Invalida también píxeles de widgets destruidos dentro del Canvas en Windows.
        try:
            self.scroll._flush_repaint(strong=True)
        except Exception:
            pass

        self._rendering = False
        if self._render_pending:
            self._render_pending = False
            self._request_render(1)

    def _render(self):
        if not self._alive:
            return
        if self._rendering:
            self._render_pending = True
            return

        self._rendering = True
        self._restore_scroll_fraction = self._capture_scroll_fraction()
        try:
            self._clear()
            renderer = {
                'summary': self._render_summary,
                'battery': self._render_battery,
                'performance': self._render_performance,
                'windows': self._render_windows,
                'repair': self._render_repair,
                'history': self._render_history,
                'recovery': self._render_recovery,
            }.get(self._tab, self._render_summary)
            renderer()
        except Exception:
            self._rendering = False
            raise

        try:
            self.app.after_idle(self._finalize_render)
        except Exception:
            self._finalize_render()

    def _render_summary(self):
        # V0.10.2.81w — La portada del Centro de Salud queda todavía más directa:
        # sin bloque introductorio redundante, para que las tarjetas comiencen antes
        # y la pestaña funcione como acceso rápido a sus módulos.
        modules = ctk.CTkFrame(self.body, fg_color='transparent')
        modules.pack(fill='x', padx=5, pady=(2, 8))

        for col in range(3):
            modules.grid_columnconfigure(col, weight=1, uniform='health_module_cards')
        for row_index in range(2):
            modules.grid_rowconfigure(row_index, weight=1)

        batt = self._battery or {}
        present = batt.get('present')
        if self._battery is None:
            battery_status, battery_tone = 'Comprobando disponibilidad…', MUTED
        elif present:
            hp = _num(batt.get('health_percent'))
            if batt.get('_presence_only') and hp is None:
                battery_status, battery_tone = 'Batería detectada · cargando datos', CYAN
            else:
                battery_status = f"Salud {_fmt(hp, '%')}"
                battery_tone = GREEN if hp is not None and hp >= 80 else AMBER if hp is not None else MUTED
        else:
            battery_status, battery_tone = 'Batería no detectada', MUTED

        windows_results = [self._startup, self._services, self._crashes, self._drivers]
        windows_done = sum(1 for item in windows_results if isinstance(item, dict))
        windows_status = f'{windows_done} de 4 análisis realizados' if windows_done else 'Sin analizar'
        windows_tone = CYAN if windows_done else MUTED

        if isinstance(self._repair_diagnostic, dict):
            repair_status, repair_tone = 'Diagnóstico disponible', CYAN
        elif isinstance(self._repair_result, dict):
            repair_status, repair_tone = 'Última reparación registrada', CYAN
        else:
            repair_status, repair_tone = 'Sin diagnóstico', MUTED

        hist = getattr(self.app, 'health_history_store', None)
        summ = hist.summary(7) if hist else {'samples': 0}
        samples = int(summ.get('samples') or 0)
        history_status = f'{samples} muestras locales' if samples else 'Sin muestras recientes'
        history_tone = CYAN if samples else MUTED

        if isinstance(self._restore, dict):
            if self._restore.get('error'):
                recovery_status, recovery_tone = 'No verificable', AMBER
            else:
                recovery_status, recovery_tone = 'Estado verificado', GREEN
        else:
            recovery_status, recovery_tone = 'Sin verificar', MUTED

        throttle = getattr(self.app, 'thermal_throttling_state', {}) or {}
        cpu = throttle.get('cpu') or {}
        throttle_state = str(cpu.get('state') or 'N/A').upper()
        throttle_color = RED if throttle_state == 'CONFIRMED' else AMBER if throttle_state in ('SUSPECTED', 'WATCHING') else GREEN if throttle_state == 'NO_EVIDENCE' else MUTED

        # V0.10.2.81w — La tarjeta Batería sólo existe cuando la presencia
        # de una batería física ya fue confirmada por una fuente real. En equipos
        # de escritorio la grilla se recompone automáticamente sin dejar huecos.
        module_specs = []
        if self._battery is not None and present:
            module_specs.append((
                'Batería',
                'Capacidad, desgaste, ciclos y autonomía cuando Windows expone datos reales.',
                battery_status, battery_tone, lambda: self._select_tab('battery')
            ))
        module_specs.extend((
            (
                'Windows',
                'Inicio, servicios, estabilidad, eventos críticos y controladores.',
                windows_status, windows_tone, lambda: self._select_tab('windows')
            ),
            (
                'Reparación',
                'Diagnóstico de integridad y reparación guiada con DISM/SFC.',
                repair_status, repair_tone, lambda: self._select_tab('repair')
            ),
            (
                'Historial y cambios',
                'Antes vs Después, benchmark e inventario comparado del hardware.',
                history_status, history_tone, lambda: self._select_tab('history')
            ),
            (
                'Recuperación',
                'Puntos de restauración y protección previa a cambios en Windows.',
                recovery_status, recovery_tone, lambda: self._select_tab('recovery')
            ),
            (
                'Rendimiento',
                'Throttling, benchmark, perfiles de energía y herramientas Gaming.',
                _state_label(throttle_state), throttle_color,
                lambda: getattr(self.app, 'open_gaming', lambda *_: None)('performance')
            ),
        ))
        for index, spec in enumerate(module_specs):
            row_index, column_index = divmod(index, 3)
            self._health_module_card(modules, row_index, column_index, *spec)


    def _render_battery(self):
        self._title('Salud de batería','Capacidad, desgaste, ciclos y autonomía usando únicamente fuentes disponibles del sistema.')
        b=self._battery
        if b is None:
            self._loading('Analizando batería…'); return
        if not b.get('present'):
            self._notice('Este equipo no reporta una batería. En un PC de escritorio esto es normal.',MUTED); return
        if b.get('_presence_only'):
            self._notice('Batería detectada. CorePulse está cargando capacidad, desgaste, ciclos y autonomía en segundo plano.', CYAN)
            return

        # V0.10.2.94w — las estadísticas de batería adoptan la misma jerarquía
        # visual del Resumen: título compacto, valor principal, contexto y acento.
        health = _num(b.get('health_percent'))
        charge = _num(b.get('charge_percent'))
        health_accent = GREEN if health is not None and health >= 80 else AMBER if health is not None else MUTED
        charge_accent = GREEN if b.get('power_plugged') else CYAN
        secs = _num(b.get('estimated_seconds_left'))
        runtime = f'{int(secs)//3600} h {(int(secs)%3600)//60} min' if secs is not None and secs > 0 else 'N/A'

        primary = ctk.CTkFrame(self.body, fg_color='transparent')
        primary.pack(fill='x', padx=8, pady=(2, 8))
        for idx in range(4):
            primary.grid_columnconfigure(idx, weight=1, uniform='battery_primary')
        self._battery_summary_card(
            primary, 0, 'Salud', _fmt(health, '%'),
            'Capacidad útil frente al diseño', health_accent,
            progress=(health / 100.0) if health is not None else None,
        )
        self._battery_summary_card(
            primary, 1, 'Carga', _fmt(charge, '%'),
            'Conectada' if b.get('power_plugged') else 'Funcionando con batería', charge_accent,
            progress=(charge / 100.0) if charge is not None else None,
        )
        self._battery_summary_card(
            primary, 2, 'Ciclos', str(b.get('cycle_count')) if b.get('cycle_count') is not None else 'N/A',
            'Reportado por el sistema', PURPLE,
        )
        self._battery_summary_card(
            primary, 3, 'Autonomía', runtime,
            'Estimación real del sistema', CYAN,
        )

        ctk.CTkLabel(
            self.body, text='DETALLES DE BATERÍA', font=(FONT, 8, 'bold'),
            text_color=MUTED, anchor='w'
        ).pack(fill='x', padx=12, pady=(6, 1))

        details = ctk.CTkFrame(self.body, fg_color='transparent')
        details.pack(fill='x', padx=3, pady=(0, 5))
        for idx in range(4):
            details.grid_columnconfigure(idx, weight=1, uniform='battery_details')

        current_text = _fmt(b.get('current_ma'),' mA',0)
        current_detail = 'Calculada desde Rate/Voltage reales' if current_text != 'N/A' and b.get('current_derived_from_real') else ''
        # V0.10.2.94w — Desgaste conserva su tarjeta vertical, pero su contenido
        # interno queda centrado y ordenado: porcentaje + estado visual breve.
        # No se modifica el cálculo ni se añade una falsa barra de progreso.
        first_row = (
            ('Capacidad de diseño', _fmt(b.get('designed_capacity_mwh'),' mWh',0), CYAN, ''),
            ('Carga completa', _fmt(b.get('full_charge_capacity_mwh'),' mWh',0), GREEN, ''),
            ('Capacidad restante', _fmt(b.get('remaining_capacity_mwh'),' mWh',0), CYAN, ''),
        )
        second_row = (
            ('Voltaje', _fmt(b.get('voltage_v'),' V',3), PURPLE, ''),
            ('Corriente', current_text, CYAN, current_detail),
            ('Carga / descarga', _fmt(b.get('charge_discharge_rate_w'),' W',2), GREEN if (_num(b.get('charge_discharge_rate_w')) or 0) >= 0 else CYAN, ''),
        )
        for column, (label, value, accent, detail) in enumerate(first_row):
            self._battery_detail_card(details, 0, column, label, value, accent, detail)
        for column, (label, value, accent, detail) in enumerate(second_row):
            self._battery_detail_card(details, 1, column, label, value, accent, detail)
        self._battery_wear_card(details, 0, 3, b.get('degradation_percent'))

        sources = ' · '.join(_source_label(x) for x in (b.get('sources') or [])) or 'N/A'
        source_card = ctk.CTkFrame(self.body, fg_color=CARD2, border_width=1, border_color=BORDER, corner_radius=10)
        source_card.pack(fill='x', padx=8, pady=(3, 8))
        ctk.CTkLabel(
            source_card, text='FUENTE DE LOS DATOS', font=(FONT, 8, 'bold'), text_color=MUTED, anchor='w'
        ).pack(fill='x', padx=13, pady=(9, 1))
        ctk.CTkLabel(
            source_card, text=sources, font=(FONT, 9, 'bold'), text_color=TEXT2,
            anchor='w', justify='left', wraplength=1040
        ).pack(fill='x', padx=13, pady=(1, 9))





    def _render_performance(self):
        """Gaming mantiene una jerarquía corta: Inicio / Biblioteca / Estabilidad / Overlay."""
        if not self._performance_only:
            self._title(
                'Rendimiento y throttling térmico',
                'Perfiles de energía seguros, detección automática de juegos y evidencia real de throttling.'
            )
            self._render_performance_profiles(include_library=True)
            self._render_gaming_stability_section()
            self._render_gaming_benchmark_section()
            return

        section = str(self._performance_section or 'home').lower()
        if section == 'library':
            self._render_gaming_library_section()
        elif section == 'stability':
            self._render_gaming_stability_section()
        elif section == 'benchmark':
            self._render_gaming_detail_header(
                'Benchmark',
                'Prueba local para comparar este mismo PC entre ejecuciones.',
                back_section='stability',
                back_text='Volver a Estabilidad',
            )
            self._render_gaming_benchmark_section()
        elif section == 'boost':
            self._render_gaming_detail_header(
                'Game Boost',
                'Ajustes temporales y reversibles para la sesión de juego.',
                back_section='home',
                back_text='Volver a Inicio',
            )
            self._render_game_boost_config_section()
        else:
            self._render_gaming_comfort_home()

    def _render_gaming_detail_header(self, title, subtitle, *, back_section='home', back_text='Volver a Inicio'):
        top = ctk.CTkFrame(self.body, fg_color='transparent')
        top.pack(fill='x', padx=8, pady=(4, 8))
        self._button(
            top, back_text, lambda: self._select_performance_section(back_section),
            variant='ghost', height=30, width=150
        ).pack(side='left')
        text = ctk.CTkFrame(top, fg_color='transparent')
        text.pack(side='left', fill='x', expand=True, padx=(12, 0))
        ctk.CTkLabel(text, text=title, font=(FONT, 15, 'bold'), text_color=TEXT, anchor='w').pack(anchor='w')
        ctk.CTkLabel(
            text, text=subtitle, font=(FONT, 8), text_color=MUTED,
            anchor='w', justify='left', wraplength=780
        ).pack(anchor='w', pady=(2, 0))

    def _gaming_live_snapshot(self):
        """Une estado de sesión + telemetría ya disponible sin iniciar sensores nuevos."""
        state = {}
        try:
            agent = getattr(self.app, 'realtime_agent', None)
            if agent is not None and hasattr(agent, 'get_state'):
                state = agent.get_state() or {}
        except Exception:
            state = {}
        sample = state.get('sample') if isinstance(state.get('sample'), dict) else {}
        tele = getattr(self.app, 'latest_telemetry', {}) or {}
        if not isinstance(tele, dict):
            tele = {}

        def pick(sample_key, tele_key=None):
            value = sample.get(sample_key)
            if _num(value) is not None:
                return value
            value = tele.get(tele_key or sample_key)
            return value if _num(value) is not None else None

        game = state.get('game') if isinstance(state.get('game'), dict) else {}
        fps = sample.get('fps') if bool(state.get('game_detected')) else None
        if _num(fps) is None:
            fps = None

        ram_used = tele.get('ram_used_gb')
        ram_total = tele.get('ram_total_gb')
        return {
            'state': state,
            'game': game,
            'fps': fps,
            'cpu_usage': pick('cpu_usage'),
            'cpu_temp': pick('cpu_temp'),
            'gpu_usage': pick('gpu_usage'),
            'gpu_temp': pick('gpu_temp'),
            'ram_usage': pick('ram_usage'),
            'ram_used_gb': ram_used if _num(ram_used) is not None else None,
            'ram_total_gb': ram_total if _num(ram_total) is not None else None,
            'session_seconds': sample.get('session_seconds') if _num(sample.get('session_seconds')) is not None else None,
            'overall': str(state.get('overall') or 'UNKNOWN').upper(),
            'context': str(state.get('context') or 'UNKNOWN').upper(),
            'active_alerts': list(((state.get('alerts') or {}).get('active') or [])),
        }

    def _render_gaming_comfort_home(self):
        manager = getattr(self.app, 'performance_manager', None)
        status = manager.status() if manager is not None else {}
        games = status.get('active_games') or []
        boost = status.get('game_boost') or {}
        requested_mode = str(status.get('requested_mode') or 'UNKNOWN').upper()
        live = self._gaming_live_snapshot()

        game_name = 'Ningún juego detectado'
        if games:
            first = games[0] if isinstance(games[0], dict) else {}
            game_name = str(first.get('display_name') or first.get('name') or 'Juego').strip() or 'Juego'
        elif live.get('game'):
            game_name = str(live['game'].get('display_name') or live['game'].get('name') or 'Juego').strip() or 'Juego'
        if game_name.lower().endswith('.exe'):
            game_name = game_name[:-4]
        if len(games) > 1:
            game_name = f'{game_name} +{len(games)-1}'

        game_active = bool(games or live.get('game'))
        boost_active = bool(boost.get('session_active'))

        # HERO: una sola lectura de la sesión. Todo lo técnico secundario sale de portada.
        hero = ctk.CTkFrame(
            self.body, fg_color=theme_color('#091a28'), border_width=1,
            border_color=theme_color('#12324b'), corner_radius=13
        )
        hero.pack(fill='x', padx=8, pady=(3, 10))

        top = ctk.CTkFrame(hero, fg_color='transparent')
        top.pack(fill='x', padx=16, pady=(13, 4))
        left = ctk.CTkFrame(top, fg_color='transparent')
        left.pack(side='left', fill='x', expand=True)
        ctk.CTkLabel(
            left, text='SESIÓN DE JUEGO', font=(FONT, 8, 'bold'),
            text_color=GREEN if game_active else MUTED, anchor='w'
        ).pack(anchor='w')
        ctk.CTkLabel(
            left, text=game_name, font=(FONT, 19, 'bold'),
            text_color=TEXT if game_active else TEXT2, anchor='w'
        ).pack(anchor='w', pady=(2, 0))
        state_text = 'Juego detectado' if game_active else 'Esperando un juego'
        ctk.CTkLabel(
            top, text=state_text, font=(FONT, 9, 'bold'),
            text_color=GREEN if game_active else MUTED
        ).pack(side='right', padx=(12, 0))

        metrics = ctk.CTkFrame(hero, fg_color=CARD2, border_width=1, border_color=BORDER, corner_radius=9)
        metrics.pack(fill='x', padx=13, pady=(7, 9))
        for col in range(4):
            metrics.grid_columnconfigure(col, weight=1, uniform='gaming_session_metrics')

        fps_text = _fmt(live.get('fps'), '', 0)
        cpu_text = (
            f"{_fmt(live.get('cpu_temp'),' °C',0)} · {_fmt(live.get('cpu_usage'),'% ',0).strip()}"
            if _num(live.get('cpu_temp')) is not None or _num(live.get('cpu_usage')) is not None else 'N/A'
        )
        gpu_text = (
            f"{_fmt(live.get('gpu_temp'),' °C',0)} · {_fmt(live.get('gpu_usage'),'% ',0).strip()}"
            if _num(live.get('gpu_temp')) is not None or _num(live.get('gpu_usage')) is not None else 'N/A'
        )
        if _num(live.get('ram_used_gb')) is not None and _num(live.get('ram_total_gb')) is not None:
            ram_text = f"{float(live['ram_used_gb']):.1f} / {float(live['ram_total_gb']):.1f} GB"
        else:
            ram_text = _fmt(live.get('ram_usage'), '%', 0)

        for col, (label, value, accent) in enumerate((
            ('FPS', fps_text, GREEN if fps_text != 'N/A' else MUTED),
            ('CPU', cpu_text, CYAN if cpu_text != 'N/A' else MUTED),
            ('GPU', gpu_text, PURPLE if gpu_text != 'N/A' else MUTED),
            ('RAM', ram_text, TEXT if ram_text != 'N/A' else MUTED),
        )):
            cell = ctk.CTkFrame(metrics, fg_color='transparent')
            cell.grid(row=0, column=col, sticky='nsew', padx=10, pady=9)
            ctk.CTkLabel(cell, text=label, font=(FONT, 8, 'bold'), text_color=MUTED, anchor='w').pack(fill='x')
            ctk.CTkLabel(cell, text=value, font=(FONT, 11, 'bold'), text_color=accent, anchor='w').pack(fill='x', pady=(2, 0))

        actions = ctk.CTkFrame(hero, fg_color='transparent')
        actions.pack(fill='x', padx=13, pady=(0, 12))
        profile_chip = ctk.CTkFrame(
            actions, fg_color=theme_color('#0b2232'), border_width=1,
            border_color=CYAN, corner_radius=8
        )
        profile_chip.pack(side='left')
        ctk.CTkLabel(
            profile_chip, text=f"Perfil: {_profile_label(requested_mode)}",
            font=(FONT, 9, 'bold'), text_color=CYAN
        ).pack(padx=10, pady=6)
        self._button(
            actions, 'Configurar Game Boost',
            lambda: self._select_performance_section('boost'),
            variant='ghost', height=31
        ).pack(side='right', padx=(6, 0))
        self._button(
            actions, 'Abrir Overlay',
            lambda: getattr(self.app, 'open_gaming', lambda *_: None)('overlay'),
            variant='ghost', height=31
        ).pack(side='right')

        # PERFIL: tres decisiones principales y Ahorro como opción secundaria.
        modes = self._card()
        modes.pack(fill='x', padx=8, pady=(0, 10))
        mhead = ctk.CTkFrame(modes, fg_color='transparent')
        mhead.pack(fill='x', padx=14, pady=(11, 7))
        ctk.CTkLabel(mhead, text='Perfil de rendimiento', font=(FONT, 12, 'bold'), text_color=TEXT).pack(side='left')
        windows_sync = bool(status.get('windows_plan_in_sync'))
        windows_verified = bool(status.get('windows_plan_verified'))
        sync_text = 'Windows sincronizado' if windows_sync else ('Plan verificado' if windows_verified else 'Plan no verificado')
        ctk.CTkLabel(
            mhead, text=sync_text, font=(FONT, 8, 'bold'),
            text_color=GREEN if windows_sync else AMBER if windows_verified else MUTED
        ).pack(side='right')

        row = ctk.CTkFrame(modes, fg_color='transparent')
        row.pack(fill='x', padx=10, pady=(0, 7))
        running = 'profile_change' in self._jobs
        profile_specs = (
            ('BALANCED', 'Equilibrado', 'Uso diario y gaming estable', GREEN),
            ('HIGH_PERFORMANCE', 'Rendimiento', 'Más respuesta durante el juego', CYAN),
            ('MAXIMUM_PERFORMANCE', 'Máximo', 'Prioriza rendimiento disponible', PURPLE),
        )
        for col, (mode, label, detail, accent) in enumerate(profile_specs):
            row.grid_columnconfigure(col, weight=1, uniform='gaming_profile_choices')
            active = requested_mode == mode
            text = f"{'✓ ' if active else ''}{label}\n{detail}"
            btn = self._button(
                row, text, lambda m=mode: self._apply_performance_mode(m),
                variant='primary' if active else 'ghost', height=48
            )
            try:
                btn.configure(
                    border_color=accent if active else BORDER,
                    text_color=TEXT if active else TEXT2,
                )
                if running or active:
                    btn.configure(state='disabled')
            except Exception:
                pass
            btn.grid(row=0, column=col, sticky='ew', padx=4)

        secondary = ctk.CTkFrame(modes, fg_color='transparent')
        secondary.pack(fill='x', padx=13, pady=(0, 10))
        ctk.CTkLabel(
            secondary, text='El plan seleccionado queda activo en Windows hasta que tú lo cambies.',
            font=(FONT, 8), text_color=MUTED, anchor='w'
        ).pack(side='left', fill='x', expand=True)
        saver_active = requested_mode == 'POWER_SAVER'
        saver = self._button(
            secondary,
            ('✓ ' if saver_active else '') + 'Ahorro de energía',
            lambda: self._apply_performance_mode('POWER_SAVER'),
            variant='primary' if saver_active else 'ghost', height=28
        )
        if running or saver_active:
            try: saver.configure(state='disabled')
            except Exception: pass
        saver.pack(side='right')

        # GAME BOOST: estado + una acción; nada de toggles en la portada.
        boost_card = ctk.CTkFrame(
            self.body, fg_color=theme_color('#0b1c26'), border_width=1,
            border_color=theme_color('#10352e'), corner_radius=11
        )
        boost_card.pack(fill='x', padx=8, pady=(0, 10))
        bleft = ctk.CTkFrame(boost_card, fg_color='transparent')
        bleft.pack(side='left', fill='x', expand=True, padx=14, pady=11)
        ctk.CTkLabel(bleft, text='Game Boost', font=(FONT, 12, 'bold'), text_color=TEXT, anchor='w').pack(anchor='w')
        if boost_active:
            count = int(boost.get('optimized_processes') or 0)
            boost_note = f'Activo · {count} proceso' + ('' if count == 1 else 's') + ' bajo control de sesión'
            if boost.get('runtime_backup_pending'):
                boost_note += ' · rollback protegido'
            boost_tone = GREEN
        elif game_active and requested_mode in ('HIGH_PERFORMANCE', 'MAXIMUM_PERFORMANCE'):
            boost_note = 'Juego detectado · preparando acciones compatibles'
            boost_tone = AMBER
        else:
            boost_note = 'Preparado para activarse con un juego y un perfil de rendimiento'
            boost_tone = MUTED
        ctk.CTkLabel(
            bleft, text=boost_note, font=(FONT, 9),
            text_color=boost_tone, anchor='w', justify='left'
        ).pack(anchor='w', pady=(3, 0))
        self._button(
            boost_card, 'Configurar',
            lambda: self._select_performance_section('boost'),
            variant='ghost', height=31, width=112
        ).pack(side='right', padx=13, pady=12)

    def _render_game_boost_config_section(self):
        manager = getattr(self.app, 'performance_manager', None)
        if manager is None:
            card = self._card(); card.pack(fill='x', padx=8, pady=6)
            self._line(card, 'El gestor de rendimiento no está disponible en esta sesión.')
            return

        status = manager.status()
        boost = status.get('game_boost') or {}
        settings = boost.get('settings') or manager.boost_settings()
        active = bool(boost.get('session_active'))
        backup = bool(boost.get('runtime_backup_pending'))

        shell = ctk.CTkFrame(self.body, fg_color='transparent')
        shell.pack(fill='x', padx=8, pady=(2, 10))
        shell.grid_columnconfigure(0, weight=4, uniform='boost_shell')
        shell.grid_columnconfigure(1, weight=6, uniform='boost_shell')

        summary = ctk.CTkFrame(
            shell, fg_color=theme_color('#0b1c26'), border_width=1,
            border_color=theme_color('#10352e'), corner_radius=11
        )
        summary.grid(row=0, column=0, sticky='nsew', padx=(0, 5))
        ctk.CTkLabel(summary, text='Estado de Game Boost', font=(FONT, 12, 'bold'), text_color=TEXT, anchor='w').pack(fill='x', padx=14, pady=(12, 2))
        ctk.CTkLabel(
            summary, text='ACTIVO' if active else 'EN ESPERA',
            font=(FONT, 18, 'bold'), text_color=GREEN if active else MUTED, anchor='w'
        ).pack(fill='x', padx=14, pady=(2, 4))
        if active:
            detail = f"{int(boost.get('optimized_processes') or 0)} proceso(s) gestionado(s)"
        else:
            detail = 'Se activa cuando un juego compatible entra en una sesión de rendimiento.'
        ctk.CTkLabel(summary, text=detail, font=(FONT, 9), text_color=TEXT2, anchor='w', justify='left', wraplength=360).pack(fill='x', padx=14)
        rollback_text = 'Rollback protegido' if backup else 'Sin rollback pendiente'
        ctk.CTkLabel(
            summary, text=rollback_text, font=(FONT, 9, 'bold'),
            text_color=GREEN if backup else MUTED, anchor='w'
        ).pack(fill='x', padx=14, pady=(9, 12))

        actions = self._card(shell)
        actions.grid(row=0, column=1, sticky='nsew', padx=(5, 0))
        ctk.CTkLabel(actions, text='Acciones de la sesión', font=(FONT, 12, 'bold'), text_color=TEXT, anchor='w').pack(fill='x', padx=14, pady=(11, 2))
        ctk.CTkLabel(
            actions,
            text='Activa sólo lo que quieras. CorePulse conserva rollback cuando una acción modifica Windows.',
            font=(FONT, 8), text_color=MUTED, anchor='w', justify='left', wraplength=620
        ).pack(fill='x', padx=14, pady=(0, 7))

        specs = (
            ('high_process_priority', 'Prioridad del juego', 'Prioridad Alta sólo para el proceso del juego.'),
            ('disable_power_throttling', 'HighQoS', 'Desactiva Power Throttling para el proceso cuando Windows lo permite.'),
            ('windows_game_mode', 'Game Mode de Windows', 'Activa Game Mode temporalmente y restaura el valor original.'),
            ('clean_standby_memory', 'Limpiar RAM standby', 'Acción opcional al iniciar sesión; mide el resultado real.'),
            ('notifications', 'Notificaciones', 'Muestra un resumen cuando Game Boost entra en acción.'),
        )
        self._boost_vars = {}
        for key, title, detail in specs:
            row = ctk.CTkFrame(actions, fg_color=CARD2, border_width=1, border_color=BORDER, corner_radius=8)
            row.pack(fill='x', padx=11, pady=3)
            labels = ctk.CTkFrame(row, fg_color='transparent')
            labels.pack(side='left', fill='x', expand=True, padx=(10, 4), pady=7)
            ctk.CTkLabel(labels, text=title, font=(FONT, 9, 'bold'), text_color=TEXT, anchor='w').pack(anchor='w')
            ctk.CTkLabel(labels, text=detail, font=(FONT, 8), text_color=MUTED, anchor='w', justify='left').pack(anchor='w')
            var = ctk.BooleanVar(value=bool(settings.get(key, True)))
            self._boost_vars[key] = var
            ctk.CTkSwitch(
                row, text='', width=42, variable=var,
                command=lambda k=key, v=var: self._set_game_boost_option(k, v),
                progress_color=CYAN, button_color=ACTION_TEXT, button_hover_color=CYAN,
            ).pack(side='right', padx=10)

        last = boost.get('last_result') or {}
        if last.get('message'):
            footer = self._card(); footer.pack(fill='x', padx=8, pady=(0, 8))
            self._kv(footer, 'Última sesión', _short(last.get('message'), 180), TEXT2)

    def _render_gaming_section_nav(self):
        manager = getattr(self.app, 'performance_manager', None)
        status = manager.status() if manager is not None else {}
        games = status.get('active_games') or []
        detector = getattr(self.app, 'game_detector', None)
        try:
            registered = detector.registered_games(games) if detector is not None and hasattr(detector, 'registered_games') else []
        except Exception:
            registered = []
        throttle = getattr(self.app, 'thermal_throttling_state', {}) or {}
        cpu = throttle.get('cpu') or {}
        throttle_state = str(cpu.get('state') or 'NO_EVIDENCE').upper()
        throttle_color = RED if throttle_state == 'CONFIRMED' else AMBER if throttle_state in ('SUSPECTED', 'WATCHING') else GREEN
        bench_text = 'En curso…' if 'benchmark' in self._jobs else ('Disponible' if self._bench else 'Sin ejecutar')
        bench_color = AMBER if 'benchmark' in self._jobs else (CYAN if self._bench else MUTED)

        shell = ctk.CTkFrame(self.body, fg_color='transparent')
        shell.pack(fill='x', padx=8, pady=(3, 10))
        for idx in range(4):
            shell.grid_columnconfigure(idx, weight=1, uniform='gaming_section_nav')

        specs = (
            ('home', 'Inicio', 'Perfil, Game Boost y estado actual', f'{_profile_label(status.get("requested_mode"))}', CYAN),
            ('library', 'Biblioteca', 'Juegos registrados y portada', f'{len(registered)} juego' + ('' if len(registered) == 1 else 's'), GREEN),
            ('stability', 'Estabilidad', 'Throttling y evidencia térmica', _state_label(throttle_state), throttle_color),
            ('benchmark', 'Benchmark', 'Pruebas rápidas y resultados', bench_text, bench_color),
        )
        for idx, (key, title, detail, value, accent) in enumerate(specs):
            active = key == self._performance_section
            card = ctk.CTkFrame(
                shell,
                fg_color=theme_color('#0d2130') if active else CARD2,
                border_width=1,
                border_color=accent if active else BORDER,
                corner_radius=10,
            )
            card.grid(row=0, column=idx, sticky='nsew', padx=4, pady=4)
            ctk.CTkLabel(card, text=title, font=(FONT, 10, 'bold'), text_color=TEXT, anchor='w').pack(fill='x', padx=11, pady=(10, 1))
            ctk.CTkLabel(card, text=detail, font=(FONT, 8), text_color=MUTED, anchor='w', justify='left', wraplength=190).pack(fill='x', padx=11, pady=(0, 6))
            ctk.CTkLabel(card, text=value, font=(FONT, 9, 'bold'), text_color=accent, anchor='w').pack(fill='x', padx=11, pady=(0, 8))
            btn = self._button(
                card,
                'Abierto' if active else 'Abrir',
                lambda k=key: self._select_performance_section(k),
                variant='primary' if active else 'ghost',
                height=28,
            )
            if active:
                try:
                    btn.configure(state='disabled')
                except Exception:
                    pass
            btn.pack(fill='x', padx=9, pady=(0, 9))

    def _select_performance_section(self, key):
        key = str(key or 'home').strip().lower()
        if key not in ('home', 'library', 'stability', 'benchmark', 'boost'):
            key = 'home'
        self._performance_section = key
        self._render()

    def _render_gaming_home_shortcuts(self):
        card = self._card(); card.pack(fill='x', padx=8, pady=(2, 10))
        ctk.CTkLabel(card, text='Accesos rápidos', font=(FONT, 12, 'bold'), text_color=TEXT).pack(anchor='w', padx=14, pady=(11, 2))
        ctk.CTkLabel(
            card,
            text='La portada Gaming ahora concentra sólo el control principal. Biblioteca, estabilidad y benchmark quedan en vistas dedicadas para evitar sobrecarga visual.',
            font=(FONT, 9), text_color=MUTED, anchor='w', justify='left', wraplength=1040
        ).pack(fill='x', padx=14, pady=(0, 8))
        row = ctk.CTkFrame(card, fg_color='transparent')
        row.pack(fill='x', padx=10, pady=(0, 10))
        for idx, (title, detail, _accent, key) in enumerate((
            ('Biblioteca', 'Gestiona juegos detectados y manuales.', GREEN, 'library'),
            ('Estabilidad', 'Revisa evidencia de throttling sin mezclarla con la biblioteca.', AMBER, 'stability'),
            ('Benchmark', 'Ejecuta y consulta resultados en una vista aparte.', PURPLE, 'benchmark'),
        )):
            row.grid_columnconfigure(idx, weight=1, uniform='gaming_home_shortcuts')
            box = ctk.CTkFrame(row, fg_color=CARD2, border_width=1, border_color=BORDER, corner_radius=9)
            box.grid(row=0, column=idx, sticky='nsew', padx=4, pady=4)
            ctk.CTkLabel(box, text=title, font=(FONT, 10, 'bold'), text_color=TEXT, anchor='w').pack(fill='x', padx=10, pady=(9, 2))
            ctk.CTkLabel(box, text=detail, font=(FONT, 8), text_color=MUTED, anchor='w', justify='left', wraplength=250).pack(fill='x', padx=10, pady=(0, 8))
            self._button(box, 'Abrir', lambda k=key: self._select_performance_section(k), variant='ghost', height=28).pack(fill='x', padx=9, pady=(0, 9))

    def _render_gaming_stability_section(self):
        """Vista compacta de estabilidad: estado actual + evidencia + benchmark."""
        live = self._gaming_live_snapshot()
        state = live.get('state') or {}
        th = getattr(self.app, 'thermal_throttling_state', {}) or {}
        cpu = th.get('cpu') or {}
        gpu = th.get('gpu') or {}
        alerts = live.get('active_alerts') or []

        overall = str(live.get('overall') or 'UNKNOWN').upper()
        overall_label = {
            'NORMAL': 'Sin alertas activas',
            'OBSERVING': 'Observando sesión',
            'INFO': 'En observación',
            'WARNING': 'Requiere atención',
            'CRITICAL': 'Crítico',
            'ERROR': 'No evaluable',
        }.get(overall, 'Sin evidencia suficiente')
        overall_color = RED if overall == 'CRITICAL' else AMBER if overall in ('WARNING', 'OBSERVING') else GREEN if overall == 'NORMAL' else MUTED

        summary = self._card()
        summary.pack(fill='x', padx=8, pady=(3, 9))
        head = ctk.CTkFrame(summary, fg_color='transparent')
        head.pack(fill='x', padx=14, pady=(11, 7))
        ctk.CTkLabel(head, text='Estabilidad de la sesión', font=(FONT, 12, 'bold'), text_color=TEXT).pack(side='left')
        ctk.CTkLabel(head, text=overall_label, font=(FONT, 9, 'bold'), text_color=overall_color).pack(side='right')

        grid = ctk.CTkFrame(summary, fg_color=CARD2, border_width=1, border_color=BORDER, corner_radius=8)
        grid.pack(fill='x', padx=12, pady=(0, 10))
        for col in range(4):
            grid.grid_columnconfigure(col, weight=1, uniform='gaming_stability_metrics')

        cpu_state = str(cpu.get('state') or 'NO_EVIDENCE').upper()
        gpu_state = str(gpu.get('state') or 'NO_EVIDENCE').upper()
        cpu_color = RED if cpu_state == 'CONFIRMED' else AMBER if cpu_state in ('SUSPECTED', 'WATCHING') else GREEN if cpu_state == 'NO_EVIDENCE' else MUTED
        gpu_color = RED if gpu_state == 'CONFIRMED' else AMBER if gpu_state in ('SUSPECTED', 'WATCHING') else GREEN if gpu_state == 'NO_EVIDENCE' else MUTED
        session = live.get('session_seconds')
        session_text = 'N/A'
        if _num(session) is not None:
            seconds = int(float(session))
            session_text = f'{seconds // 60} min {seconds % 60:02d} s'

        specs = (
            ('CPU', _state_label(cpu_state), cpu_color),
            ('GPU', _state_label(gpu_state), gpu_color),
            ('Alertas activas', str(len(alerts)), AMBER if alerts else GREEN),
            ('Sesión', session_text, CYAN if session_text != 'N/A' else MUTED),
        )
        for col, (label, value, color) in enumerate(specs):
            cell = ctk.CTkFrame(grid, fg_color='transparent')
            cell.grid(row=0, column=col, sticky='nsew', padx=10, pady=9)
            ctk.CTkLabel(cell, text=label, font=(FONT, 8, 'bold'), text_color=MUTED, anchor='w').pack(fill='x')
            ctk.CTkLabel(cell, text=value, font=(FONT, 10, 'bold'), text_color=color, anchor='w').pack(fill='x', pady=(2, 0))

        if alerts:
            alert = alerts[0] if isinstance(alerts[0], dict) else {}
            ctk.CTkLabel(
                summary,
                text=_short(alert.get('title') or alert.get('detail') or 'Hay una condición activa que requiere revisión.', 160),
                font=(FONT, 9), text_color=AMBER, anchor='w', justify='left'
            ).pack(fill='x', padx=14, pady=(0, 10))
        elif not state.get('game_detected'):
            ctk.CTkLabel(
                summary, text='No hay un juego activo. CorePulse seguirá observando la próxima sesión.',
                font=(FONT, 9), text_color=MUTED, anchor='w'
            ).pack(fill='x', padx=14, pady=(0, 10))

        benchmark = ctk.CTkFrame(
            self.body, fg_color=theme_color('#0d1728'), border_width=1,
            border_color=BORDER, corner_radius=11
        )
        benchmark.pack(fill='x', padx=8, pady=(0, 9))
        info = ctk.CTkFrame(benchmark, fg_color='transparent')
        info.pack(side='left', fill='x', expand=True, padx=14, pady=11)
        ctk.CTkLabel(info, text='Benchmark del sistema', font=(FONT, 12, 'bold'), text_color=TEXT, anchor='w').pack(anchor='w')
        if 'benchmark' in self._jobs:
            bench_status = f"{int(self._benchmark_progress * 100)}% · {self._benchmark_stage}"
            bench_color = AMBER
        elif self._bench:
            bench_status = 'Resultado disponible'
            bench_color = GREEN
        else:
            bench_status = 'Aún no ejecutado'
            bench_color = MUTED
        ctk.CTkLabel(info, text=bench_status, font=(FONT, 9, 'bold'), text_color=bench_color, anchor='w').pack(anchor='w', pady=(3, 0))
        if 'benchmark' in self._jobs:
            btn = self._button(benchmark, 'En ejecución…', lambda: None, variant='ghost', height=31, width=122)
            try: btn.configure(state='disabled')
            except Exception: pass
        elif self._bench:
            btn = self._button(
                benchmark, 'Ver resultado',
                lambda: self._select_performance_section('benchmark'),
                variant='ghost', height=31, width=122
            )
        else:
            btn = self._button(
                benchmark, 'Configurar',
                lambda: self._select_performance_section('benchmark'),
                variant='primary', height=31, width=122
            )
        self.btn_bench = btn
        btn.pack(side='right', padx=13, pady=12)

    def _benchmark_profile_label(self):
        return benchmark_profile_info(self._benchmark_profile_key).get('label') or 'Estándar'

    def _benchmark_selected_components(self):
        selected = []
        for key in ('cpu', 'ram', 'ssd', 'gpu'):
            var = self._benchmark_component_vars.get(key)
            if var is not None:
                try:
                    self._benchmark_component_flags[key] = bool(var.get())
                except Exception:
                    pass
            if self._benchmark_component_flags.get(key, False):
                selected.append(key)
        return selected

    def _benchmark_selection_text(self):
        info = benchmark_profile_info(self._benchmark_profile_key)
        selected = self._benchmark_selected_components()
        names = ' · '.join(key.upper() for key in selected) if selected else 'Ningún componente seleccionado'
        return f"{info['label']} {info['duration_label']} · {names}"

    def _on_benchmark_profile_change(self, label):
        mapping = {'Rápido': 'quick', 'Estándar': 'standard', 'Extendido': 'extended'}
        self._benchmark_profile_key = mapping.get(str(label), 'standard')
        try:
            if self._benchmark_selection_label is not None and self._benchmark_selection_label.winfo_exists():
                self._benchmark_selection_label.configure(text=self._benchmark_selection_text(), text_color=TEXT2)
        except Exception:
            pass
        self._refresh_benchmark_action_state()

    def _on_benchmark_component_change(self, key):
        var = self._benchmark_component_vars.get(key)
        if var is not None:
            try:
                self._benchmark_component_flags[key] = bool(var.get())
            except Exception:
                pass
        try:
            if self._benchmark_selection_label is not None and self._benchmark_selection_label.winfo_exists():
                selected = self._benchmark_selected_components()
                self._benchmark_selection_label.configure(
                    text=self._benchmark_selection_text(),
                    text_color=TEXT2 if selected else AMBER,
                )
        except Exception:
            pass
        self._refresh_benchmark_action_state()

    def _refresh_benchmark_action_state(self):
        """Habilita ejecutar sólo cuando la configuración previa es válida."""
        btn = getattr(self, 'btn_bench', None)
        if btn is None:
            return
        try:
            if 'benchmark' in self._jobs:
                btn.configure(text='Benchmark en ejecución…', state='disabled')
                return
            selected = self._benchmark_selected_components()
            btn.configure(
                text='Ejecutar benchmark' if not self._bench else 'Ejecutar nuevamente',
                state='normal' if selected else 'disabled',
            )
        except Exception:
            pass

    def _render_gaming_benchmark_section(self):
        bench = self._card(); bench.pack(fill='x', padx=8, pady=(3, 7))
        bench_head = ctk.CTkFrame(bench, fg_color='transparent')
        bench_head.pack(fill='x', padx=14, pady=(12, 9))
        info = ctk.CTkFrame(bench_head, fg_color='transparent')
        info.pack(side='left', fill='x', expand=True)
        ctk.CTkLabel(info, text='Benchmark del sistema', font=(FONT, 13, 'bold'), text_color=TEXT, anchor='w').pack(anchor='w')
        ctk.CTkLabel(
            info,
            text='Primero configuras la prueba. CorePulse sólo comienza cuando confirmas el perfil y los componentes.',
            font=(FONT, 9), text_color=MUTED, anchor='w', justify='left'
        ).pack(anchor='w', pady=(2, 0))
        bench_running = 'benchmark' in self._jobs

        chooser = ctk.CTkFrame(bench, fg_color=CARD2, border_width=1, border_color=BORDER, corner_radius=11)
        chooser.pack(fill='x', padx=12, pady=(0, 10))

        step1 = ctk.CTkFrame(chooser, fg_color='transparent')
        step1.pack(fill='x', padx=12, pady=(11, 6))
        ctk.CTkLabel(
            step1, text='1', width=24, height=24, corner_radius=12,
            fg_color=theme_color('#164f7d'), text_color=TEXT, font=(FONT, 9, 'bold')
        ).pack(side='left')
        ctk.CTkLabel(step1, text='Elige el tipo de prueba', font=(FONT, 10, 'bold'), text_color=TEXT2).pack(side='left', padx=(8, 0))
        ctk.CTkLabel(
            step1, text='Rápido = comprobación · Estándar = equilibrio · Extendido = carga sostenida',
            font=(FONT, 8), text_color=MUTED
        ).pack(side='right')

        if self._benchmark_profile_var is None:
            self._benchmark_profile_var = ctk.StringVar(value=self._benchmark_profile_label())
        else:
            try:
                self._benchmark_profile_var.set(self._benchmark_profile_label())
            except Exception:
                pass
        profile_selector = ctk.CTkSegmentedButton(
            chooser, values=['Rápido', 'Estándar', 'Extendido'], variable=self._benchmark_profile_var,
            command=self._on_benchmark_profile_change, height=36,
            selected_color=theme_color('#164f7d'), selected_hover_color=theme_color('#1b5c8f'),
            unselected_color=theme_color('#0b1726'), unselected_hover_color=theme_color('#102840')
        )
        profile_selector.pack(fill='x', padx=12, pady=(0, 12))
        try:
            profile_selector.configure(state='disabled' if bench_running else 'normal')
        except Exception:
            pass

        divider = ctk.CTkFrame(chooser, fg_color=BORDER, height=1)
        divider.pack(fill='x', padx=12, pady=(0, 10))

        step2 = ctk.CTkFrame(chooser, fg_color='transparent')
        step2.pack(fill='x', padx=12, pady=(0, 6))
        ctk.CTkLabel(
            step2, text='2', width=24, height=24, corner_radius=12,
            fg_color=theme_color('#164f7d'), text_color=TEXT, font=(FONT, 9, 'bold')
        ).pack(side='left')
        ctk.CTkLabel(step2, text='Selecciona qué componentes medir', font=(FONT, 10, 'bold'), text_color=TEXT2).pack(side='left', padx=(8, 0))
        ctk.CTkLabel(step2, text='Puedes elegir uno, varios o todos.', font=(FONT, 8), text_color=MUTED).pack(side='right')

        comp_row = ctk.CTkFrame(chooser, fg_color='transparent')
        comp_row.pack(fill='x', padx=8, pady=(0, 10))
        component_meta = {
            'cpu': ('CPU', '1 hilo + multinúcleo'),
            'ram': ('RAM', 'Ancho de banda sostenido'),
            'ssd': ('SSD', 'Lectura + escritura'),
            'gpu': ('GPU', 'Carga gráfica OpenGL'),
        }
        for col, key in enumerate(('cpu', 'ram', 'ssd', 'gpu')):
            comp_row.grid_columnconfigure(col, weight=1, uniform='bench_components')
            if key not in self._benchmark_component_vars:
                self._benchmark_component_vars[key] = ctk.BooleanVar(value=bool(self._benchmark_component_flags.get(key, True)))
            card = ctk.CTkFrame(comp_row, fg_color=theme_color('#0b1726'), border_width=1, border_color=BORDER, corner_radius=9)
            card.grid(row=0, column=col, sticky='nsew', padx=4)
            top = ctk.CTkFrame(card, fg_color='transparent'); top.pack(fill='x', padx=9, pady=(8, 2))
            ctk.CTkLabel(top, text=component_meta[key][0], font=(FONT, 9, 'bold'), text_color=TEXT).pack(side='left')
            switch = ctk.CTkSwitch(
                top, text='', width=38, variable=self._benchmark_component_vars[key],
                command=lambda k=key: self._on_benchmark_component_change(k), progress_color=CYAN
            )
            switch.pack(side='right')
            try:
                switch.configure(state='disabled' if bench_running else 'normal')
            except Exception:
                pass
            ctk.CTkLabel(card, text=component_meta[key][1], font=(FONT, 7), text_color=MUTED, anchor='w', justify='left').pack(fill='x', padx=9, pady=(0, 8))

        confirm = ctk.CTkFrame(chooser, fg_color=theme_color('#091827'), border_width=1, border_color=BORDER, corner_radius=9)
        confirm.pack(fill='x', padx=12, pady=(0, 11))
        confirm_text = ctk.CTkFrame(confirm, fg_color='transparent')
        confirm_text.pack(side='left', fill='x', expand=True, padx=11, pady=9)
        ctk.CTkLabel(confirm_text, text='Configuración lista', font=(FONT, 9, 'bold'), text_color=TEXT2, anchor='w').pack(anchor='w')
        self._benchmark_selection_label = ctk.CTkLabel(
            confirm_text, text=self._benchmark_selection_text(), font=(FONT, 8, 'bold'),
            text_color=TEXT2 if self._benchmark_selected_components() else AMBER, anchor='w'
        )
        self._benchmark_selection_label.pack(anchor='w', pady=(2, 0))

        self.btn_bench = self._button(
            confirm,
            'Benchmark en ejecución…' if bench_running else ('Ejecutar nuevamente' if self._bench else 'Ejecutar benchmark'),
            self._run_benchmark, variant='primary', height=36, width=165
        )
        self.btn_bench.pack(side='right', padx=11, pady=9)
        self._refresh_benchmark_action_state()

        progress_shell = ctk.CTkFrame(bench, fg_color=CARD2, border_width=1, border_color=BORDER, corner_radius=8)
        progress_shell.pack(fill='x', padx=12, pady=(0, 10))
        progress_top = ctk.CTkFrame(progress_shell, fg_color='transparent')
        progress_top.pack(fill='x', padx=12, pady=(9, 4))
        self.lbl_bench_progress = ctk.CTkLabel(
            progress_top,
            text=(f"{int(self._benchmark_progress * 100)}% · {self._benchmark_stage}" if bench_running else 'Esperando confirmación'),
            font=(FONT, 9, 'bold'), text_color=CYAN if bench_running else TEXT2, anchor='w'
        )
        self.lbl_bench_progress.pack(side='left', fill='x', expand=True)
        ctk.CTkLabel(
            progress_top, text='Carga real · protección térmica activa', font=(FONT, 8), text_color=MUTED
        ).pack(side='right')
        self.bench_progress_bar = ctk.CTkProgressBar(
            progress_shell, height=7, corner_radius=999, progress_color=CYAN,
            fg_color=theme_color('#132741')
        )
        self.bench_progress_bar.pack(fill='x', padx=12, pady=(0, 5))
        self.bench_progress_bar.set(self._benchmark_progress if bench_running else (1.0 if self._bench else 0.0))
        self.lbl_bench_progress_detail = ctk.CTkLabel(
            progress_shell,
            text=(self._benchmark_detail if bench_running else 'Configura arriba y pulsa Ejecutar benchmark cuando estés listo.'),
            font=(FONT, 8), text_color=MUTED, anchor='w', justify='left'
        )
        self.lbl_bench_progress_detail.pack(fill='x', padx=12, pady=(0, 9))

        if self._bench:
            self._render_benchmark_results()
        else:
            empty = ctk.CTkFrame(bench, fg_color=CARD2, border_width=1, border_color=BORDER, corner_radius=8)
            empty.pack(fill='x', padx=12, pady=(0, 10))
            ctk.CTkLabel(empty, text='Aún no hay una prueba ejecutada en esta sesión.', font=(FONT, 10, 'bold'), text_color=TEXT2, anchor='w').pack(fill='x', padx=12, pady=(10, 2))
            ctk.CTkLabel(
                empty,
                text='Primero selecciona perfil y componentes. Nada se ejecuta automáticamente al entrar a esta vista.',
                font=(FONT, 8), text_color=MUTED, anchor='w', justify='left', wraplength=1020
            ).pack(fill='x', padx=12, pady=(0, 10))

    def _render_gaming_library_section(self):
        manager = getattr(self.app, 'performance_manager', None)
        status = manager.status() if manager is not None else {}
        active_games = status.get('active_games') or []
        detector = getattr(self.app, 'game_detector', None)
        try:
            registered = detector.registered_games(active_games) if detector is not None and hasattr(detector, 'registered_games') else []
        except Exception:
            logger.exception('[GAME_UI] No se pudo preparar la biblioteca')
            registered = []

        shell = ctk.CTkFrame(self.body, fg_color='transparent', corner_radius=0)
        shell.pack(fill='x', padx=8, pady=(2, 12))

        total = len(registered)
        running = sum(1 for game in registered if game.get('active'))
        manual = sum(1 for game in registered if game.get('manual'))

        toolbar = ctk.CTkFrame(shell, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=10)
        toolbar.pack(fill='x', padx=4, pady=(0, 10))

        summary = ctk.CTkFrame(toolbar, fg_color='transparent')
        summary.pack(side='left', padx=11, pady=8)
        ctk.CTkLabel(
            summary, text=f'{total} juego' + ('' if total == 1 else 's'),
            font=(FONT, 10, 'bold'), text_color=TEXT
        ).pack(side='left')
        if running:
            ctk.CTkLabel(
                summary, text=f'  ·  {running} en ejecución',
                font=(FONT, 9, 'bold'), text_color=GREEN
            ).pack(side='left')
        if manual:
            ctk.CTkLabel(
                summary, text=f'  ·  {manual} manual' + ('' if manual == 1 else 'es'),
                font=(FONT, 8), text_color=MUTED
            ).pack(side='left')

        filters = ctk.CTkFrame(toolbar, fg_color='transparent')
        filters.pack(side='left', padx=(6, 0), pady=8)
        for key, label in (
            ('all', 'Todos'), ('detected', 'Detectados'),
            ('manual', 'Manuales'), ('running', 'En ejecución'),
        ):
            active = self._game_library_filter == key
            self._button(
                filters, label, lambda k=key: self._set_game_library_filter(k),
                variant='primary' if active else 'ghost', height=28,
            ).pack(side='left', padx=2)

        actions = ctk.CTkFrame(toolbar, fg_color='transparent')
        actions.pack(side='right', padx=9, pady=8)
        self._button(actions, 'Buscar juegos', self._refresh_games_now, variant='ghost', height=28).pack(side='left', padx=2)
        self._button(actions, '+ Agregar juego', self._add_manual_game, variant='primary', height=28).pack(side='left', padx=2)
        self._button(actions, 'Excluir', self._exclude_manual_game, variant='ghost', height=28).pack(side='left', padx=2)

        self.performance_exe_entry = None
        self._render_registered_games(shell, active_games, status, registered=registered)

    def _set_game_library_filter(self, key):
        key = str(key or 'all').strip().lower()
        if key not in ('all', 'detected', 'manual', 'running'):
            key = 'all'
        if self._game_library_filter == key:
            return
        self._game_library_filter = key
        self._render()

    def _benchmark_tone_color(self, tone):
        return {
            'green': GREEN, 'cyan': CYAN, 'purple': PURPLE, 'amber': AMBER,
            'red': RED, 'muted': MUTED,
        }.get(str(tone or '').lower(), TEXT2)

    def _render_benchmark_results(self):
        """Resumen visual del benchmark con lenguaje simple y detalles en segundo plano."""
        suite = self._bench if isinstance(self._bench, dict) else {}
        if suite.get('error'):
            card = self._card(); card.pack(fill='x', padx=8, pady=5)
            ctk.CTkLabel(card, text='Benchmark no completado', font=(FONT, 13, 'bold'), text_color=AMBER).pack(anchor='w', padx=14, pady=(11, 3))
            ctk.CTkLabel(
                card, text=_short(suite.get('error'), 180), font=(FONT, 9), text_color=TEXT2,
                anchor='w', justify='left', wraplength=1030
            ).pack(fill='x', padx=14, pady=(0, 11))
            return

        overall, overall_detail, overall_tone, statuses = benchmark_overall_summary(suite)
        overall_color = self._benchmark_tone_color(overall_tone)
        compare_data = self._bench_compare if isinstance(self._bench_compare, dict) else {}

        summary = self._card(); summary.pack(fill='x', padx=8, pady=(5, 7))
        ctk.CTkLabel(summary, text='Resumen del benchmark', font=(FONT, 13, 'bold'), text_color=TEXT).pack(anchor='w', padx=14, pady=(11, 2))
        ctk.CTkLabel(summary, text=overall, font=(FONT, 20, 'bold'), text_color=overall_color).pack(anchor='w', padx=14, pady=(0, 2))
        ctk.CTkLabel(
            summary, text=overall_detail, font=(FONT, 9), text_color=TEXT2,
            anchor='w', justify='left', wraplength=1040
        ).pack(fill='x', padx=14, pady=(0, 8))

        status_row = ctk.CTkFrame(summary, fg_color=CARD2, border_width=1, border_color=BORDER, corner_radius=7)
        status_row.pack(fill='x', padx=12, pady=(0, 10))
        for i, key in enumerate(('cpu', 'ram', 'ssd', 'gpu')):
            status_row.grid_columnconfigure(i, weight=1, uniform='benchmark_summary_status')
            data = statuses[key]
            block = ctk.CTkFrame(status_row, fg_color='transparent')
            block.grid(row=0, column=i, sticky='ew', padx=8, pady=8)
            ctk.CTkLabel(block, text=data['title'], font=(FONT, 9, 'bold'), text_color=TEXT2).pack(anchor='w')
            ctk.CTkLabel(
                block, text=data.get('short_status') or data['status'], font=(FONT, 10, 'bold'),
                text_color=self._benchmark_tone_color(data.get('tone'))
            ).pack(anchor='w', pady=(1, 0))

        duration_total = suite.get('duration_s')
        profile = str(suite.get('profile') or '')
        if duration_total is not None:
            ctk.CTkLabel(
                summary,
                text=f"Duración total: {float(duration_total):.1f} s · Perfil: {'Estándar sostenido' if profile == 'STANDARD_SUSTAINED' else profile or 'Local'}",
                font=(FONT, 8, 'bold'), text_color=CYAN, anchor='w'
            ).pack(fill='x', padx=14, pady=(0, 6))

        telemetry_summary = suite.get('telemetry_summary') if isinstance(suite.get('telemetry_summary'), dict) else {}
        if telemetry_summary:
            thermal = ctk.CTkFrame(summary, fg_color=CARD2, border_width=1, border_color=BORDER, corner_radius=7)
            thermal.pack(fill='x', padx=12, pady=(0, 9))
            ctk.CTkLabel(thermal, text='Durante la carga', font=(FONT, 8, 'bold'), text_color=MUTED).pack(anchor='w', padx=10, pady=(7, 3))
            metrics = []
            cpu_temp = telemetry_summary.get('cpu_temp') or {}
            gpu_temp = telemetry_summary.get('gpu_temp') or {}
            cpu_usage = telemetry_summary.get('cpu_usage') or {}
            gpu_usage = telemetry_summary.get('gpu_usage') or {}
            if cpu_temp.get('max') is not None: metrics.append(f"CPU máx {cpu_temp['max']:.1f} °C")
            if cpu_usage.get('max') is not None: metrics.append(f"CPU uso máx {cpu_usage['max']:.0f}%")
            if gpu_temp.get('max') is not None: metrics.append(f"GPU máx {gpu_temp['max']:.1f} °C")
            if gpu_usage.get('max') is not None: metrics.append(f"GPU uso máx {gpu_usage['max']:.0f}%")
            samples = int(telemetry_summary.get('sample_count') or 0)
            metrics.append(f'{samples} muestras térmicas')
            ctk.CTkLabel(
                thermal, text='  ·  '.join(metrics), font=(FONT, 9, 'bold'), text_color=TEXT2,
                anchor='w', justify='left', wraplength=1030
            ).pack(fill='x', padx=10, pady=(0, 7))
            if telemetry_summary.get('safety_stop'):
                ctk.CTkLabel(
                    thermal, text=str(telemetry_summary.get('safety_stop')), font=(FONT, 9, 'bold'), text_color=RED,
                    anchor='w', justify='left'
                ).pack(fill='x', padx=10, pady=(0, 7))

        ctk.CTkLabel(
            summary,
            text='Los valores sirven principalmente para comparar este mismo PC entre ejecuciones. CorePulse no inventa rankings ni sustituye datos ausentes.',
            font=(FONT, 8), text_color=MUTED, anchor='w', justify='left', wraplength=1040
        ).pack(fill='x', padx=14, pady=(0, 10))

        grid = ctk.CTkFrame(self.body, fg_color='transparent')
        grid.pack(fill='x', padx=3, pady=(0, 4))
        for col in range(2):
            grid.grid_columnconfigure(col, weight=1, uniform='benchmark_result_cards')

        for index, key in enumerate(('cpu', 'ram', 'ssd', 'gpu')):
            data = statuses[key]
            conclusion, conclusion_tone = benchmark_component_conclusion(key, suite, compare_data)
            card = self._card(grid)
            card.grid(row=index // 2, column=index % 2, sticky='nsew', padx=5, pady=5)
            card.grid_columnconfigure(0, weight=1)

            top = ctk.CTkFrame(card, fg_color='transparent')
            top.pack(fill='x', padx=14, pady=(11, 1))
            ctk.CTkLabel(top, text=data['title'], font=(FONT, 14, 'bold'), text_color=TEXT).pack(side='left')
            badge = ctk.CTkFrame(top, fg_color=CARD2, border_width=1, border_color=BORDER, corner_radius=6)
            badge.pack(side='right')
            ctk.CTkLabel(
                badge, text=data.get('short_status') or data['status'], font=(FONT, 8, 'bold'),
                text_color=self._benchmark_tone_color(data.get('tone'))
            ).pack(padx=8, pady=3)

            ctk.CTkLabel(
                card, text=data['subtitle'], font=(FONT, 9), text_color=MUTED,
                anchor='w', justify='left'
            ).pack(fill='x', padx=14, pady=(0, 7))

            ctk.CTkLabel(
                card, text=data.get('display_headline') or data['headline'], font=(FONT, 19, 'bold'), text_color=self._benchmark_tone_color(data.get('tone')),
                anchor='w', justify='left', wraplength=480
            ).pack(fill='x', padx=14, pady=(0, 2))
            if data.get('display_secondary') or data.get('secondary'):
                ctk.CTkLabel(
                    card, text=data.get('display_secondary') or data['secondary'], font=(FONT, 10, 'bold'), text_color=TEXT2,
                    anchor='w', justify='left', wraplength=480
                ).pack(fill='x', padx=14, pady=(0, 8))

            insight = ctk.CTkFrame(card, fg_color=CARD2, border_width=1, border_color=BORDER, corner_radius=7)
            insight.pack(fill='x', padx=12, pady=(0, 7))
            ctk.CTkLabel(
                insight, text='Qué significa', font=(FONT, 8, 'bold'), text_color=MUTED,
                anchor='w'
            ).pack(fill='x', padx=10, pady=(7, 1))
            ctk.CTkLabel(
                insight, text=data.get('meaning') or data.get('interpretation') or '', font=(FONT, 9), text_color=TEXT2,
                anchor='w', justify='left', wraplength=455
            ).pack(fill='x', padx=10, pady=(0, 6))

            ctk.CTkLabel(
                card, text=conclusion, font=(FONT, 9, 'bold'), text_color=self._benchmark_tone_color(conclusion_tone),
                anchor='w', justify='left', wraplength=480
            ).pack(fill='x', padx=14, pady=(0, 5))
            if data.get('technical_detail'):
                ctk.CTkLabel(
                    card, text=f"Detalle: {data['technical_detail']}", font=(FONT, 8), text_color=MUTED,
                    anchor='w', justify='left', wraplength=480
                ).pack(fill='x', padx=14, pady=(0, 10))

        if isinstance(self._bench_compare, dict) and self._bench_compare.get('available'):
            compare_card = self._card(); compare_card.pack(fill='x', padx=8, pady=(5, 8))
            ctk.CTkLabel(compare_card, text='Qué cambió durante la prueba', font=(FONT, 12, 'bold'), text_color=TEXT).pack(anchor='w', padx=14, pady=(11, 2))
            ctk.CTkLabel(
                compare_card,
                text='Comparamos una lectura justo antes con otra al terminar. No son máximos/mínimos del benchmark y por sí solas no diagnostican throttling.',
                font=(FONT, 9), text_color=MUTED, anchor='w', justify='left', wraplength=1040
            ).pack(fill='x', padx=14, pady=(0, 6))
            deltas = self._bench_compare.get('deltas') or {}
            for key in ('cpu_temp', 'cpu_ghz', 'ram_usage', 'gpu_temp'):
                info = benchmark_delta_data(key, deltas.get(key) or {})
                if info.get('value') == 'N/A':
                    observed = _benchmark_observation_fallback(key, self._bench or {})
                    if observed is not None:
                        info = observed
                row = ctk.CTkFrame(compare_card, fg_color=CARD2, border_width=1, border_color=BORDER, corner_radius=6)
                row.pack(fill='x', padx=12, pady=3)
                row.grid_columnconfigure(1, weight=1)
                ctk.CTkLabel(
                    row, text=info['label'], font=(FONT, 9, 'bold'), text_color=TEXT2,
                    anchor='w', width=190
                ).grid(row=0, column=0, rowspan=2, sticky='nw', padx=(10, 12), pady=8)
                ctk.CTkLabel(
                    row, text=info['value'], font=(FONT, 10, 'bold'), text_color=TEXT,
                    anchor='w', justify='left'
                ).grid(row=0, column=1, sticky='ew', padx=(0, 10), pady=(7, 0))
                ctk.CTkLabel(
                    row, text=info['change'], font=(FONT, 9), text_color=self._benchmark_tone_color(info.get('tone')),
                    anchor='w', justify='left', wraplength=760
                ).grid(row=1, column=1, sticky='ew', padx=(0, 10), pady=(0, 7))
        elif self._bench:
            note = self._card(); note.pack(fill='x', padx=8, pady=(5, 8))
            ctk.CTkLabel(note, text='Cambios durante la prueba', font=(FONT, 11, 'bold'), text_color=TEXT).pack(anchor='w', padx=14, pady=(10, 2))
            ctk.CTkLabel(
                note, text='No hubo telemetría suficiente para comparar una lectura antes y otra al finalizar. CorePulse muestra N/A en lugar de estimar valores.',
                font=(FONT, 9), text_color=MUTED, anchor='w', justify='left', wraplength=1040
            ).pack(fill='x', padx=14, pady=(0, 10))


    def _render_performance_profiles(self, include_library=True):
        manager = getattr(self.app, 'performance_manager', None)
        if manager is None:
            card = self._card(); card.pack(fill='x', padx=8, pady=(2, 8))
            self._line(card, 'El gestor de perfiles no está disponible en esta sesión.')
            return

        status = manager.status()
        self._last_performance_generation = status.get('generation')
        requested_mode = str(status.get('requested_mode') or 'UNKNOWN').upper()
        effective = _profile_label(status.get('effective_profile'))
        windows_mode = str(status.get('windows_plan_mode') or '').upper()
        windows_plan_name = str(status.get('windows_plan_name') or 'No verificado')
        windows_sync = bool(status.get('windows_plan_in_sync'))
        windows_verified = bool(status.get('windows_plan_verified'))
        games = status.get('active_games') or []
        boost = status.get('game_boost') or {}
        boost_settings = boost.get('settings') or manager.boost_settings()

        # Estado principal de la sesión Gaming.
        session = ctk.CTkFrame(
            self.body, fg_color=theme_color('#091a28'), border_width=1,
            border_color=theme_color('#0f2b40'), corner_radius=11
        )
        session.pack(fill='x', padx=8, pady=(2, 8))
        head = ctk.CTkFrame(session, fg_color='transparent'); head.pack(fill='x', padx=14, pady=(11, 7))
        ctk.CTkLabel(head, text='Estado de la sesión', font=(FONT, 12, 'bold'), text_color=TEXT).pack(side='left')
        state_grid = ctk.CTkFrame(session, fg_color='transparent'); state_grid.pack(fill='x', padx=10, pady=(0, 10))
        windows_value = _profile_label(windows_mode) if windows_mode else windows_plan_name
        if windows_verified:
            windows_value += ' ✓' if windows_sync else ' · externo'
        active_game_text = 'Ninguno'
        if games:
            first = games[0] if isinstance(games[0], dict) else {}
            active_game_text = str(first.get('display_name') or first.get('name') or 'Juego').strip() or 'Juego'
            if active_game_text.lower().endswith('.exe'):
                active_game_text = active_game_text[:-4]
            if len(games) > 1:
                active_game_text = f'{active_game_text} +{len(games) - 1}'

        session_specs = (
            ('MODO COREPULSE', _profile_label(requested_mode), CYAN),
            ('PLAN DE WINDOWS', windows_value, GREEN if windows_sync else (AMBER if windows_verified else TEXT2)),
            ('JUEGO ACTIVO', active_game_text, GREEN if games else TEXT2),
            ('CAMBIOS TEMPORALES', 'Game Boost protegido' if boost.get('runtime_backup_pending') else 'Ninguno', AMBER if boost.get('runtime_backup_pending') else GREEN),
        )
        for i, (label, value, color) in enumerate(session_specs):
            state_grid.grid_columnconfigure(i, weight=1, uniform='gaming_session')
            cell = ctk.CTkFrame(state_grid, fg_color=CARD2, border_width=1, border_color=BORDER, corner_radius=8)
            cell.grid(row=0, column=i, sticky='nsew', padx=4)
            ctk.CTkLabel(cell, text=label, font=(FONT, 8, 'bold'), text_color=MUTED, anchor='w').pack(fill='x', padx=10, pady=(7, 1))
            ctk.CTkLabel(cell, text=value, font=(FONT, 10, 'bold'), text_color=color, anchor='w', wraplength=230).pack(fill='x', padx=10, pady=(0, 7))
        if status.get('last_error'):
            ctk.CTkLabel(session, text='⚠ ' + _short(status.get('last_error'), 180), font=(FONT, 9, 'bold'), text_color=RED, anchor='w', justify='left').pack(fill='x', padx=14, pady=(0, 9))

        # Perfiles como opciones comprensibles, no cuatro botones sin contexto.
        profiles = self._card(); profiles.pack(fill='x', padx=8, pady=(0, 8))
        ctk.CTkLabel(profiles, text='Perfil de rendimiento', font=(FONT, 12, 'bold'), text_color=TEXT).pack(anchor='w', padx=14, pady=(11, 2))
        ctk.CTkLabel(
            profiles, text='Elige un modo y CorePulse activará el plan equivalente en Opciones de energía de Windows. El plan queda activo aunque cierres CorePulse y sólo cambia cuando tú eliges otro plan aquí o desde Windows.',
            font=(FONT, 9), text_color=MUTED, anchor='w', justify='left', wraplength=1040
        ).pack(fill='x', padx=14, pady=(0, 8))
        profile_grid = ctk.CTkFrame(profiles, fg_color='transparent'); profile_grid.pack(fill='x', padx=9, pady=(0, 10))
        profile_specs = (
            ('BALANCED', 'Equilibrado', 'Activa el plan Equilibrado real de Windows para uso diario.', GREEN),
            ('HIGH_PERFORMANCE', 'Alto rendimiento', 'Activa Alto rendimiento en Windows y lo mantiene como plan activo hasta que tú lo cambies.', CYAN),
            ('MAXIMUM_PERFORMANCE', 'Máximo rendimiento', 'Activa Máximo rendimiento (Ultimate Performance). Si falta, CorePulse intenta crear una copia compatible que también queda disponible en Windows.', PURPLE),
            ('POWER_SAVER', 'Ahorro de energía', 'Activa el plan de ahorro de Windows y prioriza eficiencia cuando el equipo lo soporta.', AMBER),
        )
        running = 'profile_change' in self._jobs
        for i, (mode, title, description, accent) in enumerate(profile_specs):
            row, col = divmod(i, 2)
            profile_grid.grid_columnconfigure(col, weight=1, uniform='gaming_profile_cards')
            active = requested_mode == mode
            box = ctk.CTkFrame(
                profile_grid, fg_color=theme_color('#0d2130') if active else CARD2,
                border_width=1, border_color=accent if active else BORDER, corner_radius=9
            )
            box.grid(row=row, column=col, sticky='nsew', padx=4, pady=4)
            ctk.CTkLabel(box, text=title, font=(FONT, 11, 'bold'), text_color=accent if active else TEXT, anchor='w').pack(fill='x', padx=10, pady=(9, 2))
            ctk.CTkLabel(box, text=description, font=(FONT, 8), text_color=MUTED, anchor='w', justify='left', wraplength=215).pack(fill='x', padx=10, pady=(0, 8))
            b = self._button(
                box, 'Activo' if active and not running else ('Aplicando…' if active and running else 'Usar perfil'),
                lambda m=mode: self._apply_performance_mode(m),
                variant='primary' if active else 'ghost', height=29
            )
            if running or active:
                try: b.configure(state='disabled' if running or active else 'normal')
                except Exception: pass
            b.pack(fill='x', padx=9, pady=(0, 9))

        # Game Boost independiente, con estado y opciones claras.
        boost_box = ctk.CTkFrame(
            self.body, fg_color=theme_color('#0b1c26'), border_width=1,
            border_color=theme_color('#10352e'), corner_radius=11
        )
        boost_box.pack(fill='x', padx=8, pady=(0, 8))
        boost_head = ctk.CTkFrame(boost_box, fg_color='transparent'); boost_head.pack(fill='x', padx=14, pady=(11, 4))
        ctk.CTkLabel(boost_head, text='Game Boost', font=(FONT, 12, 'bold'), text_color=TEXT).pack(side='left')
        boost_active = bool(boost.get('session_active'))
        ctk.CTkLabel(
            boost_head, text='ACTIVO' if boost_active else 'EN ESPERA', font=(FONT, 9, 'bold'),
            text_color=GREEN if boost_active else MUTED
        ).pack(side='right')
        ctk.CTkLabel(
            boost_box,
            text='Al detectar el juego principal, CorePulse aplica sólo las acciones habilitadas. Game Boost es temporal y se restaura al cerrar el juego o CorePulse.',
            font=(FONT, 9), text_color=MUTED, anchor='w', justify='left', wraplength=1040
        ).pack(fill='x', padx=14, pady=(0, 7))
        switch_grid = ctk.CTkFrame(boost_box, fg_color=CARD2, border_width=1, border_color=BORDER, corner_radius=8)
        switch_grid.pack(fill='x', padx=12, pady=(0, 7))
        boost_options = (
            ('clean_standby_memory', 'Limpiar RAM standby'),
            ('high_process_priority', 'Prioridad Alta'),
            ('disable_power_throttling', 'HighQoS'),
            ('windows_game_mode', 'Game Mode Windows'),
            ('notifications', 'Notificaciones'),
        )
        self._boost_vars = {}
        for i, (key, label) in enumerate(boost_options):
            row, col = divmod(i, 3)
            switch_grid.grid_columnconfigure(col, weight=1, uniform='game_boost_options')
            var = ctk.BooleanVar(value=bool(boost_settings.get(key, True)))
            self._boost_vars[key] = var
            sw = ctk.CTkSwitch(
                switch_grid, text=label, variable=var,
                command=lambda k=key, v=var: self._set_game_boost_option(k, v),
                font=(FONT, 9, 'bold'), text_color=TEXT2, progress_color=CYAN,
                button_color=ACTION_TEXT, button_hover_color=CYAN,
            )
            sw.grid(row=row, column=col, sticky='w', padx=10, pady=7)
        if boost_active:
            detail = f"{int(boost.get('optimized_processes') or 0)} proceso principal optimizado"
            if boost.get('memory_cleaned'):
                detail += ' · standby RAM procesada'
            if boost.get('runtime_backup_pending'):
                detail += ' · rollback protegido'
            self._kv(boost_box, 'Sesión actual', detail, GREEN)
        else:
            note = 'Se activará cuando haya un juego y el modo sea Alto rendimiento o Máximo rendimiento'
            if boost_settings.get('clean_standby_memory') and not is_admin():
                note += ' · limpieza standby requiere administrador'
            self._kv(boost_box, 'Estado', note, TEXT2)
        last_boost = boost.get('last_result') or {}
        if last_boost.get('message'):
            self._kv(boost_box, 'Última acción', _short(last_boost.get('message'), 170), TEXT2)
        recovery = boost.get('recovery_status') or {}
        if recovery.get('message'):
            self._kv(boost_box, 'Recuperación', _short(recovery.get('message'), 170), GREEN if recovery.get('success') else AMBER)


        if include_library:
            self._render_gaming_library_section()

        return status

    def _game_artwork_for(self, game, size=(304, 171)):
        path = str((game or {}).get('exe') or '').strip()
        override = str((game or {}).get('artwork_override') or '').strip()
        identity = str((game or {}).get('name') or '').strip().lower()
        key = (identity, path.lower(), override.lower(), tuple(size))
        pil = self._game_artwork_cache.get(key)
        if pil is None:
            pil, source, resolved_path = load_game_artwork(
                path, size=size, override_path=override or None,
            )
            self._game_artwork_cache[key] = (pil, source, resolved_path)
        else:
            pil, source, resolved_path = pil
        image = ctk.CTkImage(light_image=pil, dark_image=pil, size=size)
        self._game_artwork_images.append(image)
        return image, source, resolved_path

    def _game_library_geometry(self):
        """Grid launcher responsive con ancho consistente y wrap real por filas."""
        try:
            available = int(self.body.winfo_width())
        except Exception:
            available = 0
        if available < 420:
            try:
                available = max(720, int(self.app.winfo_width()) - 330)
            except Exception:
                available = 1080

        usable = max(300, available - 18)
        gap = 14
        if usable >= 1030:
            columns = 3
        elif usable >= 680:
            columns = 2
        else:
            columns = 1

        card_width = int((usable - gap * (columns - 1)) // columns)
        card_width = max(286, min(360, card_width))
        art_width = card_width
        art_height = int(round(art_width * 9 / 16))
        return columns, card_width, (art_width, art_height)

    def _placeholder_game_image(self, size):
        """Placeholder ligero de CorePulse mientras la portada real carga."""
        key = tuple(size)
        pil = self._game_placeholder_cache.get(key)
        if pil is None:
            width, height = map(int, size)
            pil = Image.new('RGBA', (width, height), (7, 16, 27, 255))
            draw = ImageDraw.Draw(pil)
            draw.rounded_rectangle(
                (0, 0, width - 1, height - 1), radius=10,
                fill=(7, 16, 27, 255), outline=(25, 53, 78, 255), width=1,
            )
            # Fondo discreto: no pretende ser una portada del juego.
            glow_y = int(height * 0.72)
            draw.rectangle((0, glow_y, width, height), fill=(8, 24, 39, 255))
            icon_size = max(42, min(68, int(height * 0.36)))
            icon = fallback_game_icon(icon_size)
            pil.alpha_composite(icon, ((width - icon_size) // 2, (height - icon_size) // 2 - 4))
            self._game_placeholder_cache[key] = pil
        image = ctk.CTkImage(light_image=pil, dark_image=pil, size=size)
        self._game_artwork_images.append(image)
        return image

    def _bind_game_card_hover(self, widgets, card, *, action_widget=None, active=False, excluded=False):
        """Resalta la card y revela acciones sólo mientras el puntero está dentro."""
        normal = GREEN if active else (AMBER if excluded else theme_color('#26354d'))
        hover = GREEN if active else (AMBER if excluded else CYAN)
        hide_job = {'id': None}

        def show_action():
            if action_widget is None:
                return
            try:
                if not action_widget.winfo_ismapped():
                    action_widget.pack(side='right', padx=(4, 0))
            except Exception:
                pass

        def hide_if_outside():
            hide_job['id'] = None
            try:
                x, y = card.winfo_pointerx(), card.winfo_pointery()
                x0, y0 = card.winfo_rootx(), card.winfo_rooty()
                inside = x0 <= x < x0 + card.winfo_width() and y0 <= y < y0 + card.winfo_height()
            except Exception:
                inside = False
            if inside:
                return
            try: card.configure(border_color=normal)
            except Exception: pass
            if action_widget is not None:
                try: action_widget.pack_forget()
                except Exception: pass

        def enter(_event=None):
            if hide_job['id'] is not None:
                try: self.app.after_cancel(hide_job['id'])
                except Exception: pass
                hide_job['id'] = None
            try: card.configure(border_color=hover)
            except Exception: pass
            show_action()

        def leave(_event=None):
            if hide_job['id'] is not None:
                return
            try:
                hide_job['id'] = self.app.after(70, hide_if_outside)
            except Exception:
                hide_if_outside()

        bound = list(widgets)
        if action_widget is not None:
            bound.append(action_widget)
        for widget in bound:
            try:
                widget.bind('<Enter>', enter, add='+')
                widget.bind('<Leave>', leave, add='+')
            except Exception:
                pass

    def _start_game_artwork_jobs(self, jobs, generation):
        if not jobs:
            return
        def worker():
            for job in jobs:
                if not self._alive or generation != self._game_artwork_generation:
                    return
                key = job['key']
                try:
                    payload = load_game_artwork(job['path'], size=job['size'], override_path=job['override'] or None)
                except Exception:
                    logger.debug('[GAME_UI] No se pudo cargar portada en background: %s', job['path'], exc_info=True)
                    continue
                self._game_artwork_cache[key] = payload
                try:
                    self.app.after(0, lambda j=job, p=payload, g=generation: self._apply_async_game_artwork(j, p, g))
                except Exception:
                    return
        thread = threading.Thread(target=worker, name='CorePulseGameArtwork', daemon=True)
        self._game_artwork_worker = thread
        thread.start()

    def _apply_async_game_artwork(self, job, payload, generation):
        if not self._alive or generation != self._game_artwork_generation:
            return
        label = job.get('label')
        try:
            if label is None or not label.winfo_exists():
                return
        except Exception:
            return
        try:
            pil, _source, _resolved = payload
            image = ctk.CTkImage(light_image=pil, dark_image=pil, size=job['size'])
            self._game_artwork_images.append(image)
            label.configure(image=image, text='')
        except Exception:
            logger.debug('[GAME_UI] No se pudo aplicar portada cargada', exc_info=True)

    def _close_game_actions(self):
        popup = self._game_action_popup
        self._game_action_popup = None
        if popup is not None:
            try: popup.destroy()
            except Exception: pass

    def _show_game_actions(self, game, anchor):
        self._close_game_actions()
        try:
            popup = ctk.CTkToplevel(self.app)
            self._game_action_popup = popup
            popup.withdraw()
            popup.overrideredirect(True)
            popup.configure(fg_color=CARD)
            popup.transient(self.app)
            shell = ctk.CTkFrame(popup, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=9)
            shell.pack(fill='both', expand=True)
            title = _short(str((game or {}).get('display_name') or 'Juego'), 34)
            ctk.CTkLabel(shell, text=title, font=(FONT, 10, 'bold'), text_color=TEXT, anchor='w').pack(fill='x', padx=10, pady=(9, 5))
            def action(label, command):
                def run():
                    self._close_game_actions()
                    command()
                self._button(shell, label, run, variant='ghost', height=29).pack(fill='x', padx=7, pady=2)
            action('Cambiar imagen', lambda g=dict(game): self._choose_game_artwork(g))
            if game.get('artwork_override'):
                action('Usar imagen automática', lambda exe=game.get('name'): self._clear_game_artwork(exe))
            if game.get('manual'):
                action('Quitar de biblioteca', lambda exe=game.get('name'): self._remove_manual_game(exe))
            self._button(shell, 'Cerrar', self._close_game_actions, variant='ghost', height=28).pack(fill='x', padx=7, pady=(4, 7))
            popup.update_idletasks()
            width = 220
            height = max(118, int(shell.winfo_reqheight()))
            x = int(anchor.winfo_rootx() + anchor.winfo_width() - width)
            y = int(anchor.winfo_rooty() + anchor.winfo_height() + 4)
            try:
                sw, sh = int(popup.winfo_screenwidth()), int(popup.winfo_screenheight())
                x = max(8, min(x, sw - width - 8)); y = max(8, min(y, sh - height - 8))
            except Exception:
                pass
            popup.geometry(f'{width}x{height}+{x}+{y}')
            popup.deiconify(); popup.lift(); popup.focus_force()
            popup.bind('<Escape>', lambda _e: self._close_game_actions(), add='+')
            popup.bind('<FocusOut>', lambda _e: self.app.after(120, self._close_game_actions), add='+')
        except Exception:
            self._close_game_actions()

    def _render_registered_games(self, parent, active_games, status, registered=None):
        """Biblioteca tipo launcher: portada + nombre + estado; acciones sólo en hover."""
        detector = getattr(self.app, 'game_detector', None)
        if registered is None:
            if detector is None or not hasattr(detector, 'registered_games'):
                return
            try:
                registered = detector.registered_games(active_games)
            except Exception:
                logger.exception('[HEALTH_CENTER] No se pudo construir el catálogo visible de juegos')
                registered = []
        else:
            registered = list(registered or [])

        full_catalog = list(registered)
        filter_key = str(self._game_library_filter or 'all').lower()
        if filter_key == 'manual':
            registered = [game for game in registered if game.get('manual')]
        elif filter_key == 'detected':
            registered = [game for game in registered if not game.get('manual')]
        elif filter_key == 'running':
            registered = [game for game in registered if game.get('active')]

        self._game_artwork_generation += 1
        generation = self._game_artwork_generation
        self._game_artwork_images = []

        if not full_catalog:
            empty = ctk.CTkFrame(parent, fg_color=CARD2, border_width=1, border_color=BORDER, corner_radius=12)
            empty.pack(fill='x', padx=4, pady=(2, 8))
            empty.grid_columnconfigure(1, weight=1)
            icon = ctk.CTkFrame(
                empty, width=56, height=56, fg_color=theme_color('#10263a'),
                border_width=1, border_color=theme_color('#23577c'), corner_radius=13
            )
            icon.grid(row=0, column=0, rowspan=3, sticky='nw', padx=(14, 11), pady=14)
            icon.grid_propagate(False)
            ctk.CTkLabel(icon, text='🎮', font=(FONT, 25), text_color=CYAN).pack(expand=True, fill='both')
            ctk.CTkLabel(empty, text='No hay juegos en la biblioteca', font=(FONT, 13, 'bold'), text_color=TEXT, anchor='w').grid(row=0, column=1, sticky='ew', padx=(0, 12), pady=(14, 2))
            ctk.CTkLabel(
                empty, text='Busca juegos instalados o agrega un ejecutable manualmente.',
                font=(FONT, 9), text_color=MUTED, anchor='w', justify='left'
            ).grid(row=1, column=1, sticky='ew', padx=(0, 12), pady=(0, 8))
            actions = ctk.CTkFrame(empty, fg_color='transparent')
            actions.grid(row=2, column=1, sticky='w', padx=(0, 12), pady=(0, 14))
            self._button(actions, 'Buscar juegos', self._refresh_games_now, variant='primary', height=29).pack(side='left', padx=(0, 5))
            self._button(actions, '+ Agregar juego', self._add_manual_game, variant='ghost', height=29).pack(side='left')
            return

        if not registered:
            empty = ctk.CTkFrame(parent, fg_color=CARD2, border_width=1, border_color=BORDER, corner_radius=10)
            empty.pack(fill='x', padx=4, pady=(2, 8))
            ctk.CTkLabel(empty, text='No hay juegos en este filtro', font=(FONT, 11, 'bold'), text_color=TEXT, anchor='w').pack(fill='x', padx=13, pady=(11, 2))
            self._button(empty, 'Mostrar todos', lambda: self._set_game_library_filter('all'), variant='ghost', height=28).pack(anchor='w', padx=12, pady=(5, 11))
            return

        library = ctk.CTkFrame(parent, fg_color='transparent')
        library.pack(fill='x', padx=4, pady=(0, 8))
        columns, card_width, art_size = self._game_library_geometry()
        gap = 14
        artwork_jobs = []
        row_inner = None

        for index, game in enumerate(registered):
            if index % columns == 0:
                row_frame = ctk.CTkFrame(library, fg_color='transparent')
                row_frame.pack(fill='x', pady=(0, gap))
                row_inner = ctk.CTkFrame(row_frame, fg_color='transparent')
                row_inner.pack(anchor='w')

            active = bool(game.get('active'))
            excluded = bool(game.get('excluded'))
            manual = bool(game.get('manual'))
            border = GREEN if active else (AMBER if excluded else theme_color('#26354d'))
            card = ctk.CTkFrame(
                row_inner, width=card_width, height=art_size[1] + 80,
                fg_color=theme_color('#111d2e'), border_width=1,
                border_color=border, corner_radius=10,
            )
            is_row_end = ((index + 1) % columns == 0) or (index == len(registered) - 1)
            card.pack(side='left', anchor='n', padx=(0, 0 if is_row_end else gap))
            card.pack_propagate(False)

            art_host = ctk.CTkFrame(
                card, width=art_size[0], height=art_size[1],
                fg_color=theme_color('#08111f'), corner_radius=0
            )
            art_host.pack(side='top', fill='x')
            art_host.pack_propagate(False)
            art_label = ctk.CTkLabel(
                art_host, text='', width=art_size[0], height=art_size[1],
                fg_color='transparent', corner_radius=0
            )
            art_label.pack(fill='both', expand=True)

            path = str((game or {}).get('exe') or '').strip()
            override = str((game or {}).get('artwork_override') or '').strip()
            identity = str((game or {}).get('name') or '').strip().lower()
            key = (identity, path.lower(), override.lower(), tuple(art_size))
            cached = self._game_artwork_cache.get(key)
            if cached is not None:
                try:
                    pil, _source, _resolved = cached
                    image = ctk.CTkImage(light_image=pil, dark_image=pil, size=art_size)
                    self._game_artwork_images.append(image)
                    art_label.configure(image=image)
                except Exception:
                    art_label.configure(image=self._placeholder_game_image(art_size))
            else:
                art_label.configure(image=self._placeholder_game_image(art_size))
                artwork_jobs.append({
                    'key': key, 'path': path, 'override': override,
                    'size': art_size, 'label': art_label,
                })

            if active:
                ctk.CTkLabel(
                    art_host, text='EN EJECUCIÓN', font=(FONT, 8, 'bold'),
                    text_color=GREEN, fg_color=theme_color('#08111f'),
                    corner_radius=7, padx=8, pady=3,
                ).place(x=9, y=9)

            body = ctk.CTkFrame(card, fg_color=theme_color('#172338'), corner_radius=0)
            body.pack(side='bottom', fill='both', expand=True)

            visible_name = str(game.get('display_name') or '').strip()
            if not visible_name:
                visible_name = str(game.get('name') or 'Juego').strip()
                if visible_name.lower().endswith('.exe'):
                    visible_name = visible_name[:-4]
            visible_name = visible_name or 'Juego'

            name_row = ctk.CTkFrame(body, fg_color='transparent')
            name_row.pack(fill='x', padx=11, pady=(9, 2))
            name = ctk.CTkLabel(
                name_row, text=_short(visible_name, 36), font=(FONT, 11, 'bold'),
                text_color=TEXT, anchor='w', justify='left'
            )
            name.pack(side='left', fill='x', expand=True)

            menu_btn = self._button(name_row, '⋯', lambda: None, variant='ghost', width=32, height=25)
            menu_btn.configure(
                command=lambda g=dict(game), b=menu_btn: self._show_game_actions(g, b),
                border_width=0, corner_radius=6, font=(FONT, 14, 'bold'),
                hover_color=theme_color('#26344f'), text_color=TEXT2
            )
            # Intencionalmente NO se empaqueta aquí: aparece sólo en hover.

            meta_row = ctk.CTkFrame(body, fg_color='transparent')
            meta_row.pack(fill='x', padx=11, pady=(1, 8))
            kind_text = 'Manual' if manual else 'Detectado'
            kind_color = PURPLE if manual else CYAN
            ctk.CTkLabel(
                meta_row, text=kind_text, font=(FONT, 8, 'bold'),
                text_color=kind_color, anchor='w'
            ).pack(side='left')
            state_text = 'Jugando ahora' if active else ('Excluido' if excluded else 'Disponible')
            state_color = GREEN if active else (AMBER if excluded else MUTED)
            ctk.CTkLabel(
                meta_row, text=state_text, font=(FONT, 8, 'bold'),
                text_color=state_color, anchor='e'
            ).pack(side='right')

            self._bind_game_card_hover(
                (card, art_host, art_label, body, name_row, name, meta_row),
                card, action_widget=menu_btn, active=active, excluded=excluded
            )

        self._start_game_artwork_jobs(artwork_jobs, generation)

    def _choose_game_artwork(self, game):
        detector = getattr(self.app, 'game_detector', None)
        if detector is None or not hasattr(detector, 'set_game_artwork'):
            return
        path = filedialog.askopenfilename(
            title=f'Portada · {str((game or {}).get("display_name") or "Juego")}',
            filetypes=[
                ('Imágenes', '*.jpg *.jpeg *.png *.webp *.bmp'),
                ('Todos los archivos', '*.*'),
            ],
        )
        if not path:
            return
        if detector.set_game_artwork((game or {}).get('name'), path):
            self._game_artwork_cache.clear()
            self._render()
        else:
            messagebox.showwarning('CorePulse · Juegos', 'La imagen seleccionada no es válida o ya no está disponible.')

    def _clear_game_artwork(self, exe_name):
        detector = getattr(self.app, 'game_detector', None)
        if detector is None or not hasattr(detector, 'clear_game_artwork'):
            return
        if detector.clear_game_artwork(exe_name):
            self._game_artwork_cache.clear()
            self._render()

    def _remove_manual_game(self, exe_name):
        detector = getattr(self.app, 'game_detector', None)
        if detector is None or not hasattr(detector, 'remove_manual_game'):
            return
        if detector.remove_manual_game(exe_name):
            self._render()

    def _apply_performance_mode(self, mode):
        manager = getattr(self.app, 'performance_manager', None)
        if manager is None or 'profile_change' in self._jobs:
            return
        previous = manager.status()
        def done(result, worker_error):
            payload = result if isinstance(result, dict) else {'success': False, 'message': worker_error or 'No se recibió resultado.'}
            if not payload.get('success'):
                message = str(payload.get('message') or 'No se pudo aplicar el perfil.')
                if (not is_admin()) and looks_like_access_denied(message):
                    if messagebox.askyesno('CorePulse · Rendimiento', message + '\n\n¿Quieres reiniciar CorePulse como administrador?'):
                        self._request_admin_restart()
                else:
                    messagebox.showwarning('CorePulse · Rendimiento', message)
        self._async('profile_change', lambda: manager.set_mode(mode), done)

    def _set_game_boost_option(self, key, variable):
        manager = getattr(self.app, 'performance_manager', None)
        if manager is None:
            return
        try:
            value = bool(variable.get())
            if not manager.set_boost_option(str(key), value):
                messagebox.showwarning('CorePulse · Game Boost', 'No se pudo guardar esa opción.')
        except Exception:
            logger.exception('[HEALTH_CENTER] No se pudo cambiar opción Game Boost: %s', key)

    def _entry_exe(self):
        try:
            entry = getattr(self, 'performance_exe_entry', None)
            return str(entry.get() or '').strip() if entry is not None else ''
        except Exception:
            return ''

    def _add_manual_game(self):
        detector = getattr(self.app, 'game_detector', None)
        if detector is None: return
        value = self._entry_exe()
        if not value:
            path = filedialog.askopenfilename(title='Selecciona el ejecutable del juego', filetypes=[('Ejecutables','*.exe'),('Todos los archivos','*.*')])
            value = path
        if detector.add_manual_game(value):
            messagebox.showinfo('CorePulse · Juegos', f'{Path(value).name} agregado a detección manual.')
            self._render()
            self._refresh_games_now()
        else:
            messagebox.showwarning('CorePulse · Juegos', 'No se pudo agregar ese ejecutable. Puede estar vacío o pertenecer a la lista segura de exclusión.')

    def _exclude_manual_game(self):
        detector = getattr(self.app, 'game_detector', None)
        if detector is None: return
        value = self._entry_exe()
        if not value:
            value = filedialog.askopenfilename(
                title='Selecciona el ejecutable que quieres excluir',
                filetypes=[('Ejecutables', '*.exe'), ('Todos los archivos', '*.*')],
            )
        if not value:
            return
        if detector.exclude(value):
            messagebox.showinfo('CorePulse · Juegos', f'{Path(value).name} quedó excluido de la activación automática.')
            self._render()
            self._refresh_games_now()

    def _refresh_games_now(self):
        manager = getattr(self.app, 'performance_manager', None)
        if manager is None or 'game_scan' in self._jobs: return
        self._async('game_scan', manager.poll_games_once, lambda r,e: None)

    def _request_admin_restart(self):
        if not messagebox.askyesno('CorePulse', '¿Reiniciar CorePulse solicitando privilegios de administrador?\n\nEl plan de energía elegido se conservará. CorePulse sólo restaurará los cambios temporales de Game Boost.'):
            return
        manager = getattr(self.app, 'performance_manager', None)
        if manager is not None:
            result = manager.shutdown(restore=False)
            if not result.get('success'):
                messagebox.showwarning('CorePulse', 'No se pudo cerrar completamente Game Boost antes de elevar. Revisa los logs.')
                return
        result = request_elevation()
        if result.get('success') and not result.get('already_admin'):
            try: self.app.on_close()
            except Exception: pass
        elif not result.get('success'):
            messagebox.showwarning('CorePulse', str(result.get('message') or 'No se pudo solicitar elevación.'))

    def _set_windows_section(self, section):
        valid = {'summary', 'startup', 'services', 'crashes', 'drivers'}
        key = str(section or 'summary').strip().lower()
        if key not in valid:
            key = 'summary'
        if key == self._windows_section:
            return
        self._windows_section = key
        # Cada cambio de sección comienza arriba; evita heredar el scroll de una
        # tabla larga de Servicios/Estabilidad.
        self._restore_scroll_fraction = 0.0
        self._request_render(1)

    def _windows_section_status(self, section):
        if section == 'startup':
            data = self._startup
            if data is None:
                return 'Sin analizar', MUTED
            if data.get('error'):
                return 'No disponible', AMBER
            return f"{int(data.get('count') or 0)} elementos revisados", CYAN

        if section == 'services':
            data = self._services
            if data is None:
                return 'Sin analizar', MUTED
            if data.get('error'):
                return 'No disponible', AMBER
            return f"{int(data.get('count') or len(data.get('items') or []))} servicios revisados", CYAN

        if section == 'crashes':
            data = self._crashes
            if data is None:
                return 'Sin analizar', MUTED
            if data.get('error'):
                return 'No disponible', AMBER
            severity = str(data.get('severity') or 'NORMAL').upper()
            if severity == 'CRITICAL':
                return 'Requiere atención', RED
            if severity == 'WARNING':
                return 'Conviene revisar', AMBER
            if severity == 'INFO':
                issues = int(data.get('app_issue_count') or 0)
                return (f'{issues} fallos de aplicaciones' if issues else 'Sin fallos críticos'), AMBER if issues else GREEN
            return 'Sin fallos críticos', GREEN

        if section == 'drivers':
            data = self._drivers
            if data is None:
                return 'Sin analizar', MUTED
            if data.get('error'):
                return 'No disponible', AMBER
            problems = int(data.get('device_problems') or 0) + int(data.get('unsigned') or 0)
            if problems:
                return f'{problems} elementos para revisar', AMBER
            return f"{int(data.get('count') or 0)} controladores revisados", GREEN

        done = sum(1 for item in (self._startup, self._services, self._crashes, self._drivers) if isinstance(item, dict))
        return (f'{done} de 4 análisis realizados' if done else 'Aún sin analizar'), CYAN if done else MUTED

    def _render_windows_nav(self):
        nav = ctk.CTkFrame(self.body, fg_color='transparent')
        nav.pack(fill='x', padx=8, pady=(3, 9))
        entries = (
            ('summary', 'Resumen'),
            ('startup', 'Inicio'),
            ('services', 'Servicios'),
            ('crashes', 'Estabilidad'),
            ('drivers', 'Controladores'),
        )
        current = str(getattr(self, '_windows_section', 'summary') or 'summary')
        for i, (key, label) in enumerate(entries):
            nav.grid_columnconfigure(i, weight=1, uniform='windows_sections')
            btn = self._button(
                nav, label, lambda k=key: self._set_windows_section(k),
                variant='tab', height=32
            )
            if key == current:
                try:
                    btn.configure(
                        fg_color=TAB_ACTIVE, hover_color=TAB_HOVER,
                        border_color=ACTION_BORDER, text_color=TEXT
                    )
                except Exception:
                    pass
            btn.grid(
                row=0, column=i, sticky='ew',
                padx=(0 if i == 0 else 4, 0 if i == len(entries) - 1 else 4)
            )

    def _render_windows_summary(self):
        section_head = ctk.CTkFrame(self.body, fg_color='transparent')
        section_head.pack(fill='x', padx=10, pady=(0, 4))
        ctk.CTkLabel(
            section_head, text='Elige qué quieres revisar', font=(FONT, 12, 'bold'),
            text_color=TEXT, anchor='w', justify='left'
        ).pack(anchor='w')
        ctk.CTkLabel(
            section_head, text='Cada análisis tiene su propia vista. CorePulse no mezcla tablas ni resultados distintos en una sola pantalla.',
            font=(FONT, 9), text_color=MUTED, anchor='w', justify='left', wraplength=1040
        ).pack(fill='x', pady=(2, 6))

        grid = ctk.CTkFrame(self.body, fg_color='transparent')
        grid.pack(fill='x', padx=3, pady=(0, 5))
        for col in range(2):
            grid.grid_columnconfigure(col, weight=1, uniform='windows_summary_cards')

        specs = (
            ('startup', 'Inicio', 'Programas que arrancan con Windows y su impacto observado.', CYAN),
            ('services', 'Servicios', 'Servicios instalados, estado, inicio y consumo de memoria.', CYAN),
            ('crashes', 'Estabilidad', 'BSOD, WHEA, apagados inesperados y cierres de aplicaciones.', AMBER),
            ('drivers', 'Controladores', 'Estado de dispositivos, firma y antigüedad de controladores.', GREEN),
        )
        for index, (key, title, description, accent) in enumerate(specs):
            row, col = divmod(index, 2)
            status, status_color = self._windows_section_status(key)
            card = self._card(grid)
            card.grid(row=row, column=col, sticky='nsew', padx=5, pady=5)
            head = ctk.CTkFrame(card, fg_color='transparent')
            head.pack(fill='x', padx=13, pady=(12, 4))
            ctk.CTkLabel(
                head, text=title, font=(FONT, 12, 'bold'), text_color=TEXT,
                anchor='w', justify='left'
            ).pack(side='left', fill='x', expand=True)
            ctk.CTkLabel(
                head, text=status, font=(FONT, 9, 'bold'), text_color=status_color,
                anchor='e', justify='right'
            ).pack(side='right', padx=(8, 0))
            ctk.CTkLabel(
                card, text=description, font=(FONT, 9), text_color=MUTED,
                anchor='w', justify='left', wraplength=440
            ).pack(fill='x', padx=13, pady=(0, 10))
            self._button(
                card, 'Abrir', lambda k=key: self._set_windows_section(k),
                variant='secondary', height=29
            ).pack(fill='x', padx=12, pady=(0, 12))

    def _render_windows(self):
        self._title('Análisis de Windows','Inicio, servicios, estabilidad y controladores en vistas separadas.')
        # V0.10.2.89w — Windows usa navegación interna en vez de apilar los
        # cuatro análisis completos en una sola vista vertical.
        self._render_windows_nav()
        section = str(getattr(self, '_windows_section', 'summary') or 'summary')
        if section == 'summary':
            self._render_windows_summary()
            return

        config = {
            'startup': ('Inicio', 'Analizar inicio', 'startup', analyze_startup, self._startup),
            'services': ('Servicios', 'Analizar servicios', 'services', analyze_services, self._services),
            'crashes': ('Estabilidad de Windows', 'Analizar estabilidad', 'crashes', lambda: analyze_crashes(7), self._crashes),
            'drivers': ('Controladores', 'Revisar controladores', 'drivers', analyze_drivers, self._drivers),
        }
        title, action_text, job_name, fn, data = config.get(section, config['startup'])

        controls = ctk.CTkFrame(self.body, fg_color='transparent')
        controls.pack(fill='x', padx=8, pady=(0, 2))
        running = job_name in self._jobs
        self._windows_buttons = {}
        action = self._button(
            controls, 'Analizando…' if running else action_text,
            lambda n=job_name, f=fn: self._run_windows(n, f),
            variant='secondary', width=176, height=32
        )
        action.pack(side='right')
        if running:
            try:
                action.configure(state='disabled')
            except Exception:
                pass
        self._windows_buttons[job_name] = action
        self._render_analyzer(title, data, job_name)

    def _render_analyzer(self, title, data, kind):
        card = self._card(); card.pack(fill='x', padx=8, pady=6)
        head = ctk.CTkFrame(card, fg_color='transparent')
        head.pack(fill='x', padx=14, pady=(11, 5))
        ctk.CTkLabel(head, text=title, font=(FONT, 12, 'bold'), text_color=TEXT).pack(side='left')
        if data is None:
            status_text, status_color = 'Pendiente', MUTED
        elif data.get('error'):
            status_text, status_color = 'No disponible', AMBER
        else:
            status_text, status_color = 'Completado', GREEN
        ctk.CTkLabel(head, text=status_text, font=(FONT, 9, 'bold'), text_color=status_color).pack(side='right')

        if data is None:
            ctk.CTkLabel(
                card, text='Aún no se ha ejecutado este análisis.', font=(FONT, 10),
                text_color=MUTED
            ).pack(anchor='w', padx=14, pady=(0, 12))
            return

        if data.get('error'):
            err = ctk.CTkFrame(card, fg_color=ERROR_BG, border_width=1, border_color=ERROR_BORDER, corner_radius=7)
            err.pack(fill='x', padx=14, pady=(2, 12))
            ctk.CTkLabel(
                err, text='No se pudo completar este análisis', font=(FONT, 10, 'bold'),
                text_color=AMBER
            ).pack(anchor='w', padx=12, pady=(9, 2))
            ctk.CTkLabel(
                err, text=str(data.get('error')), font=(FONT, 10), text_color=TEXT2,
                wraplength=1000, justify='left', anchor='w'
            ).pack(fill='x', padx=12, pady=(0, 4))
            ctk.CTkLabel(
                err, text='CorePulse no mostrará ceros ni estados normales cuando la consulta haya fallado.',
                font=(FONT, 9), text_color=MUTED, wraplength=1000, justify='left', anchor='w'
            ).pack(fill='x', padx=12, pady=(0, 9))
            return

        if kind == 'startup':
            self._kv(card, 'Elementos detectados', data.get('count', 0))
            items = data.get('items', [])[:12]
            rows = [
                [
                    i,
                    x.get('name') or 'N/A',
                    _impact_label(x.get('impact')),
                    _fmt(x.get('running_memory_mb'),' MB'),
                    _short(x.get('location'), 58),
                ]
                for i, x in enumerate(items, start=1)
            ]
            self._render_compact_table(
                card,
                columns=[
                    {'title': '#', 'weight': 1, 'wrap': 24},
                    {'title': 'Elemento', 'weight': 5, 'wrap': 210},
                    {'title': 'Impacto', 'weight': 4, 'wrap': 190},
                    {'title': 'RAM actual', 'weight': 3, 'wrap': 100},
                    {'title': 'Ubicación', 'weight': 6, 'wrap': 360},
                ],
                rows=rows,
                empty_text='No se detectaron elementos de inicio en esta consulta.',
            )
        elif kind == 'services':
            all_items = list(data.get('items') or [])
            total = len(all_items)
            self._kv(card, 'Servicios analizados', data.get('count', total))

            page_size = max(1, int(getattr(self, '_services_page_size', 40) or 40))
            page_count = max(1, (total + page_size - 1) // page_size)
            page = max(0, min(int(getattr(self, '_services_page', 0) or 0), page_count - 1))
            self._services_page = page
            start = page * page_size
            end = min(total, start + page_size)
            items = all_items[start:end]

            pager = ctk.CTkFrame(card, fg_color='transparent')
            pager.pack(fill='x', padx=14, pady=(2, 4))
            shown_text = (
                f'Mostrando {start + 1}–{end} de {total} · Página {page + 1} de {page_count}'
                if total else 'No hay servicios para mostrar'
            )
            ctk.CTkLabel(
                pager, text=shown_text, font=(FONT, 9), text_color=MUTED,
                anchor='w', justify='left'
            ).pack(side='left', fill='x', expand=True)
            if page_count > 1:
                next_btn = self._button(
                    pager, 'Siguiente', lambda: self._set_services_page(page + 1),
                    variant='ghost', width=92, height=27
                )
                next_btn.pack(side='right', padx=(6, 0))
                prev_btn = self._button(
                    pager, 'Anterior', lambda: self._set_services_page(page - 1),
                    variant='ghost', width=92, height=27
                )
                prev_btn.pack(side='right')
                if page <= 0:
                    try: prev_btn.configure(state='disabled')
                    except Exception: pass
                if page >= page_count - 1:
                    try: next_btn.configure(state='disabled')
                    except Exception: pass

            rows = []
            for i, x in enumerate(items, start=start + 1):
                load = {'PESADO':'Consumo elevado','NORMAL':'Normal','N/A':'N/A'}.get(str(x.get('load_flag') or 'N/A').upper(), str(x.get('load_flag') or 'N/A'))
                rows.append([
                    i,
                    x.get('DisplayName') or x.get('Name') or 'N/A',
                    _service_state_label(x.get('State')),
                    _start_mode_label(x.get('StartMode')),
                    _fmt(x.get('memory_mb'),' MB'),
                    load,
                ])
            self._render_compact_table(
                card,
                columns=[
                    {'title': '#', 'weight': 1, 'wrap': 24},
                    {'title': 'Servicio', 'weight': 6, 'wrap': 260},
                    {'title': 'Estado', 'weight': 3, 'wrap': 130},
                    {'title': 'Inicio', 'weight': 3, 'wrap': 130},
                    {'title': 'RAM', 'weight': 2, 'wrap': 90},
                    {'title': 'Carga', 'weight': 3, 'wrap': 150},
                ],
                rows=rows,
                empty_text='No se encontraron servicios en esta consulta.',
            )
        elif kind == 'crashes':
            sev = str(data.get('severity', 'N/A')).upper()
            status_label = {
                'CRITICAL': 'Requiere atención',
                'WARNING': 'Conviene revisar',
                'INFO': 'Sistema sin fallos críticos · revisar aplicaciones',
                'NORMAL': 'Sin eventos críticos detectados',
            }.get(sev, 'N/A')
            status_color = RED if sev == 'CRITICAL' else AMBER if sev in ('WARNING', 'INFO') else GREEN if sev == 'NORMAL' else MUTED
            self._kv(card, 'Estado general', status_label, status_color)
            self._kv(card, 'Período revisado', f"Últimos {int(data.get('days') or 7)} días")

            explanation = ctk.CTkFrame(
                card, fg_color=CARD2, border_width=1, border_color=BORDER, corner_radius=8
            )
            explanation.pack(fill='x', padx=14, pady=(5, 8))
            ctk.CTkLabel(
                explanation, text='Qué significa', font=(FONT, 10, 'bold'),
                text_color=TEXT, anchor='w', justify='left'
            ).pack(fill='x', padx=12, pady=(9, 2))
            ctk.CTkLabel(
                explanation, text=str(data.get('summary') or 'No hay una interpretación disponible.'),
                font=(FONT, 9), text_color=TEXT2, anchor='w', justify='left', wraplength=1040
            ).pack(fill='x', padx=12, pady=(0, 9))

            counts = data.get('counts') or {}
            self._kv(card, 'Pantallazos azules (BSOD)', counts.get('bsod_bugcheck', 0), RED if counts.get('bsod_bugcheck') else GREEN)
            self._kv(card, 'Errores de hardware (WHEA)', counts.get('whea', 0), RED if counts.get('whea') else GREEN)
            self._kv(card, 'Apagados o reinicios no limpios', data.get('power_event_count', 0), AMBER if data.get('power_event_count') else GREEN)
            self._kv(card, 'Registros de cierres/bloqueos de aplicaciones', data.get('app_issue_count', 0), AMBER if data.get('app_issue_count') else GREEN)
            self._kv(card, 'Aplicaciones afectadas', data.get('affected_app_count', 0), AMBER if data.get('affected_app_count') else GREEN)

            # V112: resumen visual y plan de acción legible. La lógica de análisis
            # permanece en core/windows_health.py; aquí sólo reducimos ruido técnico.
            quick = ctk.CTkFrame(card, fg_color='transparent')
            quick.pack(fill='x', padx=10, pady=(4, 7))
            quick_specs = (
                (
                    'SISTEMA',
                    'Sin BSOD/WHEA' if not (counts.get('bsod_bugcheck') or counts.get('whea'))
                    else f"{int(counts.get('bsod_bugcheck') or 0)} BSOD · {int(counts.get('whea') or 0)} WHEA",
                    GREEN if not (counts.get('bsod_bugcheck') or counts.get('whea')) else RED,
                ),
                (
                    'APLICACIONES',
                    'Sin incidentes' if not data.get('app_issue_count')
                    else f"{int(data.get('app_issue_count') or 0)} incidentes · {int(data.get('affected_app_count') or 0)} apps",
                    GREEN if not data.get('app_issue_count') else AMBER,
                ),
                (
                    'REINICIOS',
                    'Sin incidentes' if not data.get('power_event_count')
                    else f"{int(data.get('power_event_count') or 0)} no limpios",
                    GREEN if not data.get('power_event_count') else AMBER,
                ),
            )
            for index, (label, value, tone) in enumerate(quick_specs):
                quick.grid_columnconfigure(index, weight=1, uniform='stability_quick')
                cell = ctk.CTkFrame(quick, fg_color=CARD2, border_width=1, border_color=BORDER, corner_radius=8)
                cell.grid(row=0, column=index, sticky='nsew', padx=4)
                ctk.CTkLabel(cell, text=label, font=(FONT, 8, 'bold'), text_color=MUTED, anchor='w').pack(fill='x', padx=10, pady=(8, 1))
                ctk.CTkLabel(cell, text=value, font=(FONT, 10, 'bold'), text_color=tone, anchor='w').pack(fill='x', padx=10, pady=(0, 8))

            action_plan = [x for x in (data.get('action_plan') or []) if isinstance(x, dict)]
            if action_plan:
                action_box = ctk.CTkFrame(
                    card, fg_color=CARD2, border_width=1, border_color=BORDER, corner_radius=8
                )
                action_box.pack(fill='x', padx=14, pady=(7, 8))
                ctk.CTkLabel(
                    action_box, text='Qué conviene revisar', font=(FONT, 11, 'bold'),
                    text_color=TEXT, anchor='w', justify='left'
                ).pack(fill='x', padx=12, pady=(10, 2))
                ctk.CTkLabel(
                    action_box,
                    text='Empieza por la primera recomendación y sólo avanza si el problema se repite. El registro técnico queda más abajo por si necesitas comprobar fechas, módulos o códigos.',
                    font=(FONT, 8), text_color=MUTED, anchor='w', justify='left', wraplength=1040
                ).pack(fill='x', padx=12, pady=(0, 7))

                for action in action_plan[:4]:
                    kind_name = str(action.get('kind') or '').lower()
                    tone = RED if kind_name in ('whea', 'bsod') else AMBER if kind_name in ('power', 'application') else GREEN
                    badge_text = (
                        'PRIORIDAD ALTA' if kind_name in ('whea', 'bsod') else
                        'REVISAR' if kind_name in ('power', 'application') else
                        'SIN ACCIÓN'
                    )
                    row = ctk.CTkFrame(action_box, fg_color=BG, border_width=1, border_color=BORDER, corner_radius=8)
                    row.pack(fill='x', padx=10, pady=(3, 6))
                    head = ctk.CTkFrame(row, fg_color='transparent')
                    head.pack(fill='x', padx=11, pady=(8, 4))
                    ctk.CTkLabel(
                        head, text=str(action.get('title') or 'Hallazgo'),
                        font=(FONT, 10, 'bold'), text_color=tone, anchor='w', justify='left'
                    ).pack(side='left', fill='x', expand=True)
                    ctk.CTkLabel(
                        head, text=badge_text, font=(FONT, 8, 'bold'),
                        text_color=tone, fg_color=CARD2, corner_radius=7, padx=8, pady=3,
                    ).pack(side='right', padx=(8, 0))

                    def _simple_line(label, value, *, value_color=TEXT2, bottom=3):
                        line = ctk.CTkFrame(row, fg_color='transparent')
                        line.pack(fill='x', padx=11, pady=(0, bottom))
                        ctk.CTkLabel(
                            line, text=label, font=(FONT, 8, 'bold'), text_color=MUTED,
                            anchor='w', justify='left', width=104
                        ).pack(side='left', anchor='nw', padx=(0, 8))
                        ctk.CTkLabel(
                            line, text=str(value or 'N/A'), font=(FONT, 8), text_color=value_color,
                            anchor='w', justify='left', wraplength=900
                        ).pack(side='left', fill='x', expand=True)

                    _simple_line('Qué pasó', action.get('finding'))
                    _simple_line('Qué significa', action.get('interpretation'))
                    _simple_line('Haz esto primero', action.get('action'), value_color=TEXT)
                    _simple_line('Si se repite', action.get('escalation'))
                    _simple_line('Dato técnico', action.get('evidence'), value_color=MUTED, bottom=8)

            events = list(data.get('items') or [])
            total = len(events)
            technical_head = ctk.CTkFrame(card, fg_color='transparent')
            technical_head.pack(fill='x', padx=14, pady=(4, 5))
            ctk.CTkLabel(
                technical_head, text='Registro técnico', font=(FONT, 10, 'bold'),
                text_color=TEXT, anchor='w'
            ).pack(side='left')
            self._button(
                technical_head,
                ('Ocultar detalle' if self._stability_show_technical else f'Ver {total} evento(s)'),
                self._toggle_stability_technical,
                variant='ghost', width=116, height=27,
            ).pack(side='right')
            ctk.CTkLabel(
                card,
                text=('Fechas, fuentes, módulos y mensajes originales de Windows.' if self._stability_show_technical
                      else 'Opcional. Ábrelo sólo si necesitas revisar evidencia técnica concreta.'),
                font=(FONT, 8), text_color=MUTED, anchor='w', justify='left', wraplength=1050
            ).pack(fill='x', padx=14, pady=(0, 7))

            if not self._stability_show_technical:
                return

            page_size = max(1, int(getattr(self, '_stability_page_size', 25) or 25))
            page_count = max(1, (total + page_size - 1) // page_size)
            page = max(0, min(int(getattr(self, '_stability_page', 0) or 0), page_count - 1))
            self._stability_page = page
            start = page * page_size
            end = min(total, start + page_size)
            visible_events = events[start:end]

            pager = ctk.CTkFrame(card, fg_color='transparent')
            pager.pack(fill='x', padx=14, pady=(2, 4))
            shown_text = (
                f'Mostrando {start + 1}–{end} de {total} eventos detallados · Página {page + 1} de {page_count}'
                if total else 'No hay eventos para mostrar'
            )
            if data.get('details_truncated'):
                shown_text += f" · Windows encontró {int(data.get('matched_total') or total)} registros; se muestran los más recientes"
            ctk.CTkLabel(
                pager, text=shown_text, font=(FONT, 9), text_color=MUTED,
                anchor='w', justify='left'
            ).pack(side='left', fill='x', expand=True)
            if page_count > 1:
                next_btn = self._button(
                    pager, 'Siguiente', lambda: self._set_stability_page(page + 1),
                    variant='ghost', width=92, height=27
                )
                next_btn.pack(side='right', padx=(6, 0))
                prev_btn = self._button(
                    pager, 'Anterior', lambda: self._set_stability_page(page - 1),
                    variant='ghost', width=92, height=27
                )
                prev_btn.pack(side='right')
                if page <= 0:
                    try: prev_btn.configure(state='disabled')
                    except Exception: pass
                if page >= page_count - 1:
                    try: next_btn.configure(state='disabled')
                    except Exception: pass

            rows = [
                [
                    i,
                    x.get('display_time') or 'N/A',
                    x.get('user_label') or 'Evento relacionado',
                    x.get('component_name') or 'N/A',
                    x.get('ProviderName') or 'N/A',
                    x.get('user_detail') or x.get('user_summary') or 'Sin explicación disponible.',
                ]
                for i, x in enumerate(visible_events, start=start + 1)
            ]
            self._render_compact_table(
                card,
                columns=[
                    {'title': '#', 'weight': 1, 'wrap': 24},
                    {'title': 'Fecha y hora', 'weight': 3, 'wrap': 130},
                    {'title': 'Qué ocurrió', 'weight': 4, 'wrap': 180},
                    {'title': 'Aplicación / componente', 'weight': 4, 'wrap': 190},
                    {'title': 'Fuente de Windows', 'weight': 4, 'wrap': 190},
                    {'title': 'Detalle', 'weight': 7, 'wrap': 360},
                ],
                rows=rows,
                empty_text='No se encontraron BSOD, errores WHEA, apagados inesperados ni fallos de aplicaciones en el período analizado.',
            )
        elif kind == 'drivers':
            self._kv(card, 'Controladores revisados', data.get('count', 0))
            self._kv(card, 'Hardware relevante detectado', data.get('important_count', 0), CYAN if data.get('important_count') else TEXT)
            self._kv(card, 'Problemas de dispositivo', data.get('device_problems', 0), RED if data.get('device_problems') else GREEN)
            self._kv(card, 'No firmados', data.get('unsigned', 0), RED if data.get('unsigned') else GREEN)
            self._kv(card, 'Antiguos de terceros (>5 años)', data.get('older_than_5y', 0), AMBER if data.get('older_than_5y') else TEXT)

            all_items = list(data.get('items') or [])
            total = len(all_items)
            page_size = max(1, int(getattr(self, '_drivers_page_size', 40) or 40))
            page_count = max(1, (total + page_size - 1) // page_size)
            page = max(0, min(int(getattr(self, '_drivers_page', 0) or 0), page_count - 1))
            self._drivers_page = page
            start = page * page_size
            end = min(total, start + page_size)
            items = all_items[start:end]

            pager = ctk.CTkFrame(card, fg_color='transparent')
            pager.pack(fill='x', padx=14, pady=(2, 4))
            shown_text = (
                f'Mostrando {start + 1}–{end} de {total} · Página {page + 1} de {page_count}'
                if total else 'No hay controladores para mostrar'
            )
            ctk.CTkLabel(
                pager, text=shown_text, font=(FONT, 9), text_color=MUTED,
                anchor='w', justify='left'
            ).pack(side='left', fill='x', expand=True)
            if page_count > 1:
                next_btn = self._button(
                    pager, 'Siguiente', lambda: self._set_drivers_page(page + 1),
                    variant='ghost', width=92, height=27
                )
                next_btn.pack(side='right', padx=(6, 0))
                prev_btn = self._button(
                    pager, 'Anterior', lambda: self._set_drivers_page(page - 1),
                    variant='ghost', width=92, height=27
                )
                prev_btn.pack(side='right')
                if page <= 0:
                    try: prev_btn.configure(state='disabled')
                    except Exception: pass
                if page >= page_count - 1:
                    try: next_btn.configure(state='disabled')
                    except Exception: pass

            rows = [
                [
                    i,
                    x.get('DeviceName') or 'N/A',
                    x.get('DriverProviderName') or 'N/A',
                    x.get('DriverVersion') or 'N/A',
                    _driver_status_label(x.get('status')),
                ]
                for i, x in enumerate(items, start=start + 1)
            ]
            self._render_compact_table(
                card,
                columns=[
                    {'title': '#', 'weight': 1, 'wrap': 24},
                    {'title': 'Dispositivo', 'weight': 6, 'wrap': 260},
                    {'title': 'Proveedor', 'weight': 4, 'wrap': 180},
                    {'title': 'Versión', 'weight': 3, 'wrap': 130},
                    {'title': 'Estado', 'weight': 3, 'wrap': 140},
                ],
                rows=rows,
                empty_text='No se encontraron controladores en esta consulta.',
            )

    def _repair_state_label(self, value):
        raw = str(value or 'UNKNOWN').upper()
        return {
            'CLEAN': 'Sin corrupción detectada',
            'REPAIR_RECOMMENDED': 'Reparación recomendada',
            'REPAIRED': 'Reparación completada',
            'COMPLETED': 'Completado',
            'ATTENTION_REQUIRED': 'Requiere revisión',
            'ADMIN_REQUIRED': 'Requiere administrador',
            'UNAVAILABLE': 'No disponible',
            'UNKNOWN': 'No concluyente',
            'REPAIRABLE': 'Reparable',
            'UNREPAIRED': 'No reparado',
            'NOT_REPAIRABLE': 'No reparable',
            'FAILED': 'Falló',
            'TIMEOUT': 'Tiempo agotado',
            'COMPLETED_UNCLASSIFIED': 'Completado · salida no clasificada',
        }.get(raw, raw.replace('_', ' ').title())

    def _repair_state_color(self, value):
        raw = str(value or '').upper()
        if raw in ('CLEAN', 'REPAIRED', 'COMPLETED'):
            return GREEN
        if raw in ('REPAIR_RECOMMENDED', 'REPAIRABLE', 'COMPLETED_UNCLASSIFIED', 'UNKNOWN', 'ADMIN_REQUIRED'):
            return AMBER
        if raw in ('ATTENTION_REQUIRED', 'UNREPAIRED', 'NOT_REPAIRABLE', 'FAILED', 'TIMEOUT'):
            return RED
        return MUTED

    def _render_repair(self):
        self._title(
            'Reparación de Windows',
            'DISM y SFC para comprobar o reparar componentes de Windows. Esta función es independiente del rollback de Tweaks.'
        )
        caps = repair_capabilities()

        info = self._card(); info.pack(fill='x', padx=8, pady=(0, 7))
        head = ctk.CTkFrame(info, fg_color='transparent'); head.pack(fill='x', padx=14, pady=(11, 5))
        ctk.CTkLabel(head, text='Integridad del sistema', font=(FONT, 12, 'bold'), text_color=TEXT).pack(side='left')
        ctk.CTkLabel(
            head,
            text='ADMIN' if caps.get('admin') else 'SIN ELEVACIÓN',
            font=(FONT, 9, 'bold'),
            text_color=GREEN if caps.get('admin') else AMBER,
        ).pack(side='right')
        self._kv(info, 'Plataforma', 'Windows' if caps.get('windows') else 'No compatible')
        self._kv(info, 'Privilegios', 'Administrador' if caps.get('admin') else 'Usuario estándar', GREEN if caps.get('admin') else AMBER)
        self._kv(info, 'Política', 'Sólo por acción explícita del usuario')
        self._kv(info, 'Rollback de Tweaks', 'Separado · DISM/SFC no restauran snapshots de Tweaks')
        ctk.CTkLabel(
            info,
            text='El diagnóstico ejecuta CheckHealth + ScanHealth + SFC VerifyOnly. La reparación ejecuta RestoreHealth + SFC ScanNow y una comprobación posterior.',
            font=(FONT, 9), text_color=MUTED, anchor='w', justify='left', wraplength=1000,
        ).pack(fill='x', padx=14, pady=(5, 8))

        actions = ctk.CTkFrame(info, fg_color='transparent')
        actions.pack(fill='x', padx=10, pady=(0, 12))
        running_diag = 'windows_repair_diagnostic' in self._jobs
        running_fix = 'windows_repair_apply' in self._jobs
        busy = running_diag or running_fix
        actions.grid_columnconfigure(0, weight=1, uniform='repair_actions')
        actions.grid_columnconfigure(1, weight=1, uniform='repair_actions')
        btn_diag = self._button(
            actions,
            'Diagnóstico en ejecución…' if running_diag else 'Diagnosticar integridad',
            self._run_integrity_diagnostic,
            variant='secondary', height=34,
        )
        btn_diag.grid(row=0, column=0, sticky='ew', padx=(0, 4))
        btn_fix = self._button(
            actions,
            'Reparación en ejecución…' if running_fix else 'Reparar Windows',
            self._run_windows_repair,
            variant='primary', height=34,
        )
        btn_fix.grid(row=0, column=1, sticky='ew', padx=(4, 0))
        self.btn_repair_diag = btn_diag
        self.btn_repair_fix = btn_fix
        if busy:
            try: btn_diag.configure(state='disabled'); btn_fix.configure(state='disabled')
            except Exception: pass

        self.lbl_repair_progress = ctk.CTkLabel(
            info,
            text=self._repair_progress_text(),
            font=(FONT, 9), text_color=CYAN if busy else MUTED,
            anchor='w', justify='left', wraplength=1000,
        )
        self.lbl_repair_progress.pack(fill='x', padx=14, pady=(0, 6))

        # V0.10.2.33w: feedback visible inmediato. Esta barra representa
        # avance por ETAPAS (no pretende estimar el tiempo restante de DISM/SFC).
        self.repair_progress_bar = ctk.CTkProgressBar(
            info, height=6, progress_color=CYAN, fg_color=BORDER,
        )
        self.repair_progress_bar.pack(fill='x', padx=14, pady=(0, 11))
        try:
            self.repair_progress_bar.set(self._repair_progress_fraction() if busy else 0.0)
        except Exception:
            pass

        if not caps.get('windows'):
            self._notice('La reparación de Windows sólo está disponible al ejecutar CorePulse en Windows.', AMBER)
            return
        if not caps.get('admin'):
            note = self._card(); note.pack(fill='x', padx=8, pady=5)
            ctk.CTkLabel(note, text='Se requiere administrador', font=(FONT, 11, 'bold'), text_color=AMBER).pack(anchor='w', padx=14, pady=(11, 3))
            ctk.CTkLabel(
                note,
                text='Las operaciones online de DISM/SFC necesitan elevación. CorePulse no intentará ejecutarlas ni simular resultados sin esos permisos.',
                font=(FONT, 9), text_color=TEXT2, wraplength=1000, justify='left', anchor='w',
            ).pack(fill='x', padx=14, pady=(0, 7))
            self._button(note, 'Reiniciar como administrador', self._request_admin_restart, variant='secondary', height=30).pack(anchor='w', padx=14, pady=(0, 11))

        self._render_repair_result('Último diagnóstico', self._repair_diagnostic)
        self._render_repair_result('Última reparación', self._repair_result)

        safety = self._card(); safety.pack(fill='x', padx=8, pady=6)
        ctk.CTkLabel(safety, text='Qué NO hace esta herramienta', font=(FONT, 11, 'bold'), text_color=TEXT).pack(anchor='w', padx=14, pady=(11, 4))
        self._line(safety, 'No usa DISM/SFC para revertir Tweaks de CorePulse.')
        self._line(safety, 'No ejecuta reparaciones en segundo plano ni automáticamente.')
        self._line(safety, 'No afirma que Windows está sano si la salida real no puede clasificarse.')
        self._line(safety, 'No elimina snapshots de rollback ni modifica el historial de Tweaks.')
        ctk.CTkLabel(safety, text='', height=4).pack()

    def _repair_progress_text(self):
        progress = self._repair_progress or {}
        if not progress:
            return 'Las operaciones pueden tardar varios minutos. CorePulse conservará la salida real en logs.'
        label = progress.get('label') or 'Windows'
        index = progress.get('index')
        total = progress.get('total')
        if progress.get('event') == 'done':
            state = self._repair_state_label(progress.get('state'))
            return f'Etapa {index}/{total}: {label} · {state}'
        return f'Etapa {index}/{total}: {label}…'

    def _render_repair_result(self, title, data):
        card = self._card(); card.pack(fill='x', padx=8, pady=5)
        head = ctk.CTkFrame(card, fg_color='transparent'); head.pack(fill='x', padx=14, pady=(11, 5))
        ctk.CTkLabel(head, text=title, font=(FONT, 11, 'bold'), text_color=TEXT).pack(side='left')
        if not data:
            ctk.CTkLabel(head, text='Sin ejecutar', font=(FONT, 9, 'bold'), text_color=MUTED).pack(side='right')
            ctk.CTkLabel(card, text='Todavía no hay resultados en esta sesión.', font=(FONT, 9), text_color=MUTED).pack(anchor='w', padx=14, pady=(0, 11))
            return
        state = str(data.get('overall_state') or 'UNKNOWN')
        ctk.CTkLabel(
            head, text=self._repair_state_label(state), font=(FONT, 9, 'bold'), text_color=self._repair_state_color(state)
        ).pack(side='right')
        self._kv(card, 'Resultado', self._repair_state_label(state), self._repair_state_color(state))
        self._kv(card, 'Resumen', data.get('summary') or 'N/A')
        self._kv(card, 'Duración', _fmt(data.get('duration_s'), ' s', 1))
        self._kv(card, 'Posible reinicio', 'Sí' if data.get('restart_maybe_required') else 'No indicado por la salida')
        if data.get('error'):
            self._kv(card, 'Error', _short(data.get('error'), 180), RED)
        for step in data.get('steps') or []:
            st = str(step.get('state') or 'UNKNOWN')
            self._line(card, f"{step.get('label') or step.get('key')} · {self._repair_state_label(st)} · {step.get('duration_s', 0)} s · {_short(step.get('message'), 170)}")
        if data.get('log_path'):
            self._kv(card, 'Log técnico', data.get('log_path'))
        ctk.CTkLabel(card, text='', height=3).pack()

    def _repair_progress_fraction(self):
        """Avance por etapas; no estima el porcentaje interno de DISM/SFC."""
        progress = self._repair_progress or {}
        try:
            index = max(1, int(progress.get('index') or 1))
            total = max(1, int(progress.get('total') or 1))
        except Exception:
            return 0.05 if progress else 0.0
        if progress.get('event') == 'done':
            return max(0.0, min(1.0, index / total))
        # Al iniciar una etapa, deja claro visualmente que existe trabajo activo
        # sin fingir que conocemos el progreso interno del comando.
        return max(0.04, min(0.98, ((index - 1) + 0.12) / total))

    def _sync_repair_live_ui(self):
        """Actualiza la UI existente sin reconstruir el StableScrollHost."""
        if not self._alive:
            return
        running_diag = 'windows_repair_diagnostic' in self._jobs
        running_fix = 'windows_repair_apply' in self._jobs
        busy = running_diag or running_fix

        try:
            if self.btn_repair_diag is not None and self.btn_repair_diag.winfo_exists():
                self.btn_repair_diag.configure(
                    text='Diagnóstico en ejecución…' if running_diag else 'Diagnosticar integridad',
                    state='disabled' if busy else 'normal',
                )
        except Exception:
            pass
        try:
            if self.btn_repair_fix is not None and self.btn_repair_fix.winfo_exists():
                self.btn_repair_fix.configure(
                    text='Reparación en ejecución…' if running_fix else 'Reparar Windows',
                    state='disabled' if busy else 'normal',
                )
        except Exception:
            pass
        try:
            if self.lbl_repair_progress is not None and self.lbl_repair_progress.winfo_exists():
                self.lbl_repair_progress.configure(
                    text=self._repair_progress_text(),
                    text_color=CYAN if busy else MUTED,
                )
        except Exception:
            pass
        try:
            if self.repair_progress_bar is not None and self.repair_progress_bar.winfo_exists():
                self.repair_progress_bar.set(self._repair_progress_fraction() if busy else 0.0)
        except Exception:
            pass

        # Fuerza únicamente el pintado pendiente; NO entra en un nuevo mainloop
        # ni ejecuta callbacks arbitrarios como lo haría update().
        try:
            self.app.update_idletasks()
        except Exception:
            pass

    def _repair_progress_callback(self, event):
        self._repair_progress = dict(event or {})
        try:
            self.app.after(0, self._sync_repair_live_ui)
        except Exception:
            pass

    def _ensure_repair_admin(self):
        caps = repair_capabilities()
        if not caps.get('windows'):
            messagebox.showwarning('CorePulse', 'Esta herramienta sólo está disponible en Windows.')
            return False
        if caps.get('admin'):
            return True
        self._request_admin_restart()
        return False

    def _run_integrity_diagnostic(self):
        if 'windows_repair_diagnostic' in self._jobs or 'windows_repair_apply' in self._jobs:
            return
        if not self._ensure_repair_admin():
            return
        if not messagebox.askyesno(
            'CorePulse · Diagnóstico de Windows',
            '¿Ejecutar DISM CheckHealth + ScanHealth y SFC VerifyOnly?\n\nNo es un rollback de Tweaks y puede tardar varios minutos.'
        ):
            return
        self._repair_progress = {'event':'start','index':1,'total':3,'label':'Preparando diagnóstico'}
        def work():
            return run_integrity_diagnostic(progress=self._repair_progress_callback)
        def done(result, error):
            self._repair_progress = None
            self._repair_diagnostic = result if isinstance(result, dict) else {'overall_state':'UNKNOWN','summary':error or 'Sin resultado','steps':[]}
            state = str(self._repair_diagnostic.get('overall_state') or '')
            if state == 'REPAIR_RECOMMENDED':
                messagebox.showwarning('CorePulse', 'El diagnóstico encontró evidencia reparable. Puedes usar “Reparar Windows”.')
            elif state == 'CLEAN':
                messagebox.showinfo('CorePulse', 'El diagnóstico no encontró corrupción en las comprobaciones reconocidas.')
            elif state in ('ATTENTION_REQUIRED', 'UNKNOWN'):
                messagebox.showwarning('CorePulse', 'El diagnóstico terminó con un estado que requiere revisión. Consulta el detalle y el log técnico.')
        self._async('windows_repair_diagnostic', work, done, on_started=self._sync_repair_live_ui)

    def _run_windows_repair(self):
        if 'windows_repair_diagnostic' in self._jobs or 'windows_repair_apply' in self._jobs:
            return
        if not self._ensure_repair_admin():
            return
        if not messagebox.askyesno(
            'CorePulse · Reparar Windows',
            '¿Ejecutar DISM RestoreHealth y SFC ScanNow?\n\nEstas herramientas pueden modificar componentes/archivos protegidos de Windows y pueden tardar bastante. No revierten Tweaks de CorePulse.'
        ):
            return
        self._repair_progress = {'event':'start','index':1,'total':3,'label':'Preparando reparación'}
        def work():
            return run_windows_repair(progress=self._repair_progress_callback)
        def done(result, error):
            self._repair_progress = None
            self._repair_result = result if isinstance(result, dict) else {'overall_state':'UNKNOWN','summary':error or 'Sin resultado','steps':[]}
            state = str(self._repair_result.get('overall_state') or '')
            if state == 'REPAIRED':
                messagebox.showinfo('CorePulse', 'Windows informó que la reparación se completó. Revisa el resultado por etapa y reinicia si Windows lo solicita.')
            elif state == 'COMPLETED':
                messagebox.showinfo('CorePulse', 'Las operaciones finalizaron sin un error técnico confirmado. Revisa el detalle para ver la clasificación real de cada etapa.')
            else:
                messagebox.showwarning('CorePulse', 'La reparación terminó con elementos que requieren revisión. CorePulse conservó la salida real en el log técnico.')
        self._async('windows_repair_apply', work, done, on_started=self._sync_repair_live_ui)

    def _render_history(self):
        self._title('Historial de salud · Antes vs Después · Cambios de hardware','CorePulse registra una muestra espaciada de salud y permite cuantificar diferencias observadas sin atribuir causalidad automáticamente.')
        store=getattr(self.app,'health_history_store',None)
        row=ctk.CTkFrame(self.body,fg_color='transparent'); row.pack(fill='x',padx=4,pady=(0,8))
        for days in (1,7,30):
            s=store.summary(days) if store else {'samples':0,'metrics':{}}; m=s.get('metrics',{})
            detail=f"CPU temp máx {_fmt((m.get('cpu_temp') or {}).get('max'),' °C')} · SSD salud mín {_fmt((m.get('storage_health') or {}).get('min'),'%')}"
            self._summary_box(row,f'{days} DÍAS',str(s.get('samples',0))+' muestras',detail,CYAN)
        if store:
            self._render_health_chart(store.query(30, limit=3000))
            benches=store.latest_benchmarks(12)
            if benches:
                bench_card=self._card(); bench_card.pack(fill='x',padx=8,pady=5)
                ctk.CTkLabel(bench_card,text='Historial de rendimiento',font=(FONT,11,'bold'),text_color=TEXT).pack(anchor='w',padx=12,pady=(10,4))
                for b in benches:
                    payload=b.get('payload') or {}; value=payload.get('value')
                    if str(payload.get('kind')).upper()=='SSD':
                        txt=f"SSD · Escritura {_fmt(payload.get('write_mbps'),' MB/s')} · Lectura {_fmt(payload.get('read_mbps'),' MB/s')}"
                    else:
                        txt=f"{payload.get('kind') or b.get('kind')} · {_fmt(value,' '+str(payload.get('unit') or b.get('unit') or ''))} · {payload.get('provider') or b.get('provider')}"
                    self._line(bench_card,txt)
        ba=self._card(); ba.pack(fill='x',padx=8,pady=5)
        ctk.CTkLabel(ba,text='Antes vs Después',font=(FONT,11,'bold'),text_color=TEXT).pack(anchor='w',padx=12,pady=(10,4))
        buttons=ctk.CTkFrame(ba,fg_color='transparent'); buttons.pack(fill='x',padx=8,pady=4)
        self._button(buttons,'Capturar ANTES',lambda:self._capture_slot('before'),variant='secondary',height=30).pack(side='left',padx=4)
        self._button(buttons,'Capturar DESPUÉS',lambda:self._capture_slot('after'),variant='secondary',height=30).pack(side='left',padx=4)
        comp=compare(); snaps=load_snapshots(); self._kv(ba,'Snapshot ANTES','Disponible' if snaps.get('before') else 'No'); self._kv(ba,'Snapshot DESPUÉS','Disponible' if snaps.get('after') else 'No')
        if comp.get('available'):
            for key in ('cpu_temp','cpu_ghz','ram_usage','gpu_temp','battery_health'):
                d=(comp.get('deltas') or {}).get(key) or {}; self._kv(ba,key,f"{_fmt(d.get('before'))} → {_fmt(d.get('after'))} · Δ {_fmt(d.get('delta'))}")
            ctk.CTkLabel(ba,text=comp.get('note'),font=(FONT,8),text_color=AMBER).pack(anchor='w',padx=12,pady=(4,10))
        hw=self._card(); hw.pack(fill='x',padx=8,pady=5)
        ctk.CTkLabel(hw,text='Cambios de hardware',font=(FONT,11,'bold'),text_color=TEXT).pack(anchor='w',padx=12,pady=(10,4))
        data=self._hw
        if data is None: ctk.CTkLabel(hw,text='Comparación pendiente.',font=(FONT,9),text_color=MUTED).pack(anchor='w',padx=12,pady=(0,8))
        else:
            changes=data.get('changes') or []; self._kv(hw,'Baseline previo','Sí' if data.get('baseline_exists') else 'No'); self._kv(hw,'Cambios detectados',len(changes),AMBER if changes else GREEN)
            for c in changes: self._line(hw,f"{c.get('component')}: cambió desde el baseline guardado")
        self._button(hw,'Guardar hardware actual como nuevo baseline',self._save_hw_baseline,variant='secondary',height=30).pack(anchor='w',padx=12,pady=(5,11))

    def _render_health_chart(self, rows):
        card=self._card(); card.pack(fill='x',padx=8,pady=5)
        ctk.CTkLabel(card,text='Evolución de salud · últimos 30 días',font=(FONT,11,'bold'),text_color=TEXT).pack(anchor='w',padx=12,pady=(10,3))
        if not rows:
            ctk.CTkLabel(card,text='Aún no hay suficientes muestras. CorePulse registra una muestra aproximadamente cada 60 s mientras está abierto.',font=(FONT,9),text_color=MUTED).pack(anchor='w',padx=12,pady=(0,12)); return
        width_px=1040; height_px=360; dpi=100
        fig=Figure(figsize=(width_px/dpi,height_px/dpi),dpi=dpi,facecolor=CARD)
        ax1=fig.add_subplot(211,facecolor=CARD); ax2=fig.add_subplot(212,facecolor=CARD)
        xs=[dt.datetime.fromtimestamp(float(r['ts'])) for r in rows]
        def series(key): return [r.get(key) if isinstance(r.get(key),(int,float)) else float('nan') for r in rows]
        ax1.plot(xs,series('cpu_temp'),color=CYAN,linewidth=1.7,label='CPU °C')
        ax1.plot(xs,series('gpu_temp'),color=PURPLE,linewidth=1.7,label='GPU °C')
        ax2.plot(xs,series('storage_health'),color=GREEN,linewidth=1.7,label='SSD salud %')
        ax2.plot(xs,series('battery_health'),color=AMBER,linewidth=1.7,label='Batería salud %')
        ax2.plot(xs,series('system_score'),color=CYAN,linewidth=1.3,alpha=.8,label='Índice sistema')
        for ax in (ax1,ax2):
            ax.grid(True,color=theme_color('#334155'),linewidth=.5,alpha=.55)
            ax.tick_params(colors=MUTED,labelsize=7)
            for spine in ax.spines.values(): spine.set_color(BORDER)
            leg=ax.legend(fontsize=7,loc='best',facecolor=CARD,edgecolor=BORDER)
            for t in leg.get_texts(): t.set_color(TEXT)
        ax1.set_ylabel('Temperatura',color=TEXT2,fontsize=8); ax2.set_ylabel('Salud / índice',color=TEXT2,fontsize=8)
        fig.autofmt_xdate(rotation=0,ha='center'); fig.tight_layout(pad=1.2)
        agg=FigureCanvasAgg(fig); agg.draw(); size=agg.get_width_height(); image=Image.frombuffer('RGBA',size,agg.buffer_rgba(),'raw','RGBA',0,1).copy()
        photo=ImageTk.PhotoImage(image=image,master=card); self._health_chart_photo=photo
        lbl=tk.Label(card,image=photo,bg=CARD,bd=0,highlightthickness=0); lbl.pack(fill='x',padx=10,pady=(0,10))
        fig.clear()

    def _render_recovery(self):
        self._title('Restauración y rollback','Protección antes de cambios delicados. CorePulse no habilita Restaurar sistema sin tu autorización.')
        r=self._restore
        card=self._card(); card.pack(fill='x',padx=8,pady=5)
        self._kv(card,'Administrador','Sí' if (r or {}).get('admin') else 'No')
        self._kv(card,'Restaurar sistema','Disponible' if (r or {}).get('available') else 'No disponible / pendiente',GREEN if (r or {}).get('available') else AMBER)
        if r and r.get('error'): self._kv(card,'Detalle',_short(r.get('error'),180),AMBER)
        pts=(r or {}).get('points') or []
        for p in pts[:5]: self._line(card,f"{p.get('Description') or 'Punto de restauración'} · Secuencia #{p.get('SequenceNumber') or 'N/A'}")
        self.btn_restore=self._button(card,'Crear punto de restauración',self._create_restore,variant='primary',height=32); self.btn_restore.pack(anchor='w',padx=12,pady=(7,11))
        note=self._card(); note.pack(fill='x',padx=8,pady=5)
        ctk.CTkLabel(note,text='Reversión de Tweaks',font=(FONT,11,'bold'),text_color=TEXT).pack(anchor='w',padx=12,pady=(10,3))
        ctk.CTkLabel(note,text='Los tweaks de Registro conservan su valor previo exacto. Para cambios delicados, usa además el punto de restauración.',font=(FONT,9),text_color=MUTED,wraplength=1000,justify='left').pack(anchor='w',padx=12,pady=(0,6))
        self._button(note,'Abrir Tweaks Windows 11',getattr(self.app,'open_windows_tweaks',lambda:None),variant='secondary',height=30).pack(anchor='w',padx=12,pady=(0,11))

    def _line(self, parent, text):
        ctk.CTkLabel(
            parent, text='• ' + str(text), font=(FONT, 9), text_color=TEXT2,
            anchor='w', justify='left', wraplength=1000
        ).pack(fill='x', padx=14, pady=3)

    def _notice(self,text,color=MUTED):
        c=self._card(); c.pack(fill='x',padx=8,pady=7); ctk.CTkLabel(c,text=text,font=(FONT,10),text_color=color,wraplength=1050,justify='left').pack(anchor='w',padx=14,pady=14)
    def _loading(self,text): self._notice(text,CYAN)

    def _async(self,name,fn,on_done,on_started=None):
        if name in self._jobs: return False
        # Registrar ANTES de pintar: la vista puede saber de inmediato que el
        # trabajo existe, incluso antes de que el worker ejecute el primer comando.
        self._jobs.add(name)
        if on_started is not None:
            try:
                on_started()
            except Exception:
                logger.exception('[HEALTH_CENTER] Falló feedback inicial de %s', name)
        def worker():
            try:
                result=fn(); error=None
            except Exception:
                logger.exception('[HEALTH_CENTER] Falló el trabajo asíncrono %s', name)
                result=None
                error='La operación encontró un error interno. El detalle técnico fue registrado en los logs.'
            def done():
                self._jobs.discard(name)
                if not self._alive:
                    return
                on_done(result, error)
                # Benchmark/juego/perfil no reconstruyen el Canvas en el mismo
                # callback que termina el worker. Se agenda un render estable.
                self._request_render(1)
            try: self.app.after(0,done)
            except Exception: pass
        threading.Thread(target=worker,daemon=True,name='CorePulse-Health-'+name).start()
        return True

    def _lazy_load(self,key):
        if key in ('summary','battery'):
            self._sync_preloaded_battery_state()
            if self._battery is None:
                self._seed_preloaded_battery_state()
            if isinstance(self._battery, dict) and self._battery.get('present') and self._battery.get('_presence_only'):
                scheduler = getattr(self.app, '_schedule_battery_health_refresh', None)
                if callable(scheduler):
                    scheduler(False)
                elif 'battery' not in self._jobs:
                    snap=copy.deepcopy(getattr(self.app,'latest_telemetry',{}) or {})
                    self._async('battery',lambda:collect_battery_health(snap),lambda r,e:setattr(self,'_battery',r or {'present':False,'error':e}))
        # El inventario comparado no participa en la portada. Se calcula sólo
        # cuando el usuario entra a Historial, evitando una consulta cara al abrir.
        if key == 'history' and self._hw is None:
            self._load_hw_compare()
        if key=='recovery' and self._restore is None:
            self._async('restore',restore_point_status,lambda r,e:setattr(self,'_restore',r or {'error':e}))

    def _load_hw_compare(self):
        cache = getattr(self.app, 'health_center_hardware_cache', None)
        stamp = float(getattr(self.app, 'health_center_hardware_cache_timestamp', 0.0) or 0.0)
        if isinstance(cache, dict) and (time.time() - stamp) < 300.0:
            self._hw = copy.deepcopy(cache)
            return
        tele=copy.deepcopy(getattr(self.app,'latest_telemetry',{}) or {}); disks=copy.deepcopy(getattr(self.app,'latest_disks',[]) or [])
        def work(): return compare_hardware_inventory(collect_hardware_inventory(tele,disks))
        def done(r,e):
            value = r or {'changes':[],'error':e}
            self._hw = value
            if isinstance(value, dict):
                self.app.health_center_hardware_cache = copy.deepcopy(value)
                self.app.health_center_hardware_cache_timestamp = time.time()
        self._async('hardware',work,done)

    def _toggle_stability_technical(self):
        self._stability_show_technical = not bool(getattr(self, '_stability_show_technical', False))
        self._restore_scroll_fraction = self._capture_scroll_fraction()
        self._request_render(1)

    def _set_stability_page(self, page):
        items = list((self._crashes or {}).get('items') or [])
        page_size = max(1, int(getattr(self, '_stability_page_size', 25) or 25))
        page_count = max(1, (len(items) + page_size - 1) // page_size)
        self._stability_page = max(0, min(int(page), page_count - 1))
        self._request_render(1)

    def _set_services_page(self, page):
        items = list((self._services or {}).get('items') or [])
        page_size = max(1, int(getattr(self, '_services_page_size', 40) or 40))
        page_count = max(1, (len(items) + page_size - 1) // page_size)
        self._services_page = max(0, min(int(page), page_count - 1))
        self._request_render(1)

    def _set_drivers_page(self, page):
        items = list((self._drivers or {}).get('items') or [])
        page_size = max(1, int(getattr(self, '_drivers_page_size', 40) or 40))
        page_count = max(1, (len(items) + page_size - 1) // page_size)
        self._drivers_page = max(0, min(int(page), page_count - 1))
        self._request_render(1)

    def _run_windows(self, name, fn):
        attr = '_' + name
        btn = getattr(self, '_windows_buttons', {}).get(name)
        try:
            if btn is not None:
                btn.configure(text='Analizando…', state='disabled')
        except Exception:
            pass
        def done(result, worker_error):
            if isinstance(result, dict):
                payload = result
            else:
                payload = {'error': worker_error or 'El análisis no devolvió un resultado válido.', 'items': []}
            setattr(self, attr, payload)
            if name == 'services':
                self._services_page = 0
            elif name == 'drivers':
                self._drivers_page = 0
            elif name == 'crashes':
                self._stability_page = 0
        self._async(name, fn, done)

    def _set_benchmark_progress(self, fraction, stage, detail=''):
        try:
            fraction = max(0.0, min(1.0, float(fraction)))
        except Exception:
            fraction = 0.0
        self._benchmark_progress = fraction
        self._benchmark_stage = str(stage or 'Benchmark en ejecución')
        self._benchmark_detail = str(detail or '')
        try:
            if self.bench_progress_bar is not None and self.bench_progress_bar.winfo_exists():
                self.bench_progress_bar.set(fraction)
        except Exception:
            pass
        try:
            if self.lbl_bench_progress is not None and self.lbl_bench_progress.winfo_exists():
                self.lbl_bench_progress.configure(text=f"{int(fraction * 100)}% · {self._benchmark_stage}", text_color=CYAN)
        except Exception:
            pass
        try:
            label = getattr(self, 'lbl_bench_progress_detail', None)
            if label is not None and label.winfo_exists():
                label.configure(text=self._benchmark_detail)
        except Exception:
            pass

    def _run_benchmark(self):
        if 'benchmark' in self._jobs:
            return
        selected = self._benchmark_selected_components()
        if not selected:
            self._benchmark_stage = 'Selecciona componentes'
            self._benchmark_detail = 'Activa al menos CPU, RAM, SSD o GPU antes de iniciar.'
            self._set_benchmark_progress(0.0, self._benchmark_stage, self._benchmark_detail)
            try:
                if self._benchmark_selection_label is not None:
                    self._benchmark_selection_label.configure(text='Selecciona al menos un componente.', text_color=AMBER)
            except Exception:
                pass
            return

        profile_key = self._benchmark_profile_key
        profile = benchmark_profile_info(profile_key)
        component_text = ' · '.join(key.upper() for key in selected)
        self._benchmark_progress = 0.0
        self._benchmark_stage = f"Preparando {profile['label'].lower()}"
        self._benchmark_detail = f"{profile['duration_label']} con {component_text}. La duración baja si ejecutas menos componentes."
        try:
            self.btn_bench.configure(text='Ejecutando benchmark…', state='disabled')
        except Exception:
            pass
        self._set_benchmark_progress(0.01, self._benchmark_stage, self._benchmark_detail)

        tele_before = copy.deepcopy(getattr(self.app, 'latest_telemetry', {}) or {})
        disks_before = copy.deepcopy(getattr(self.app, 'latest_disks', []) or [])
        before_snapshot = capture_metrics(tele_before, disks_before, None, label='benchmark_before')

        def progress(fraction, stage, detail=''):
            try:
                self.app.after(0, lambda f=fraction, s=stage, d=detail: self._set_benchmark_progress(f, s, d))
            except Exception:
                pass

        def telemetry_sample():
            tele = copy.deepcopy(getattr(self.app, 'latest_telemetry', {}) or {})
            return _benchmark_live_metrics(tele)

        def work():
            return run_benchmark_suite(
                profile_key, selected,
                progress_callback=progress, telemetry_sampler=telemetry_sample
            )

        def done(r, e):
            self._bench = r or {'error': e}
            tele_after = copy.deepcopy(getattr(self.app, 'latest_telemetry', {}) or {})
            disks_after = copy.deepcopy(getattr(self.app, 'latest_disks', []) or [])
            self._bench_compare = compare(before_snapshot, capture_metrics(tele_after, disks_after, None, label='benchmark_after'))
            store = getattr(self.app, 'health_history_store', None)
            if store and isinstance(r, dict):
                for key in ('cpu', 'ram', 'ssd', 'gpu'):
                    try:
                        result = r.get(key) or {}
                        if str(result.get('status') or '').upper() != 'SKIPPED':
                            store.record_benchmark(result)
                    except Exception:
                        pass
            self._benchmark_progress = 1.0
            self._benchmark_stage = 'Benchmark completado' if not e else 'Benchmark finalizado con aviso'
            self._benchmark_detail = f"{profile['label']} · {component_text} · resultados listos para revisar."
            self._refresh_benchmark_action_state()

        self._async('benchmark', work, done)

    def _capture_slot(self,slot):
        tele=copy.deepcopy(getattr(self.app,'latest_telemetry',{}) or {}); disks=copy.deepcopy(getattr(self.app,'latest_disks',[]) or [])
        batt=self._battery or collect_battery_health(tele)
        save_snapshot(capture_metrics(tele,disks,batt,label=slot),slot=slot); self._render()

    def _save_hw_baseline(self):
        tele=copy.deepcopy(getattr(self.app,'latest_telemetry',{}) or {}); disks=copy.deepcopy(getattr(self.app,'latest_disks',[]) or [])
        def work(): return save_hardware_baseline(collect_hardware_inventory(tele,disks))
        self._async('save_hw',work,lambda r,e:(setattr(self,'_hw',{'baseline_exists':True,'changes':[],'current':r}) if r else None))

    def _create_restore(self):
        if not messagebox.askyesno('CorePulse','¿Crear un punto de restauración de Windows antes de realizar cambios?\n\nPuede requerir privilegios de administrador.'):
            return
        try: self.btn_restore.configure(text='Creando…',state='disabled')
        except Exception: pass
        def done(r,e):
            if r and r.get('ok'): messagebox.showinfo('CorePulse','Punto de restauración creado correctamente.')
            else: messagebox.showwarning('CorePulse','No se pudo crear el punto de restauración.\n\n'+str((r or {}).get('error') or e or 'Error desconocido'))
            self._restore=None; self._lazy_load('recovery')
        self._async('create_restore',lambda:create_restore_point('CorePulse - antes de cambios'),done)

    def _schedule_performance_status_tick(self):
        if not self._alive or not self._visible:
            return
        try:
            self._performance_after_id = self.app.after(1200, self._performance_status_tick)
        except Exception:
            self._performance_after_id = None

    def _performance_status_tick(self):
        self._performance_after_id = None
        if not self._alive or not self._visible:
            return
        try:
            if not self.frame.winfo_exists():
                self._alive = False
                return
        except Exception:
            self._alive = False
            return
        manager = getattr(self.app, 'performance_manager', None)
        dynamic_blockers = {'profile_change', 'benchmark', 'game_scan'}
        if manager is not None and self._tab == 'performance' and not (dynamic_blockers & self._jobs):
            try:
                generation = manager.status().get('generation')
                if generation != self._last_performance_generation:
                    self._last_performance_generation = generation
                    self._request_render(1)
            except Exception:
                logger.exception('[HEALTH_CENTER] No se pudo refrescar el estado de perfiles')
        self._schedule_performance_status_tick()

    def set_active(self, active):
        """Pausa el refresco periódico cuando la subvista Gaming está oculta."""
        self._visible = bool(active)
        if not self._visible and self._performance_after_id is not None:
            try: self.app.after_cancel(self._performance_after_id)
            except Exception: pass
            self._performance_after_id = None
        elif self._visible and self._performance_only and self._performance_after_id is None and self._alive:
            self._schedule_performance_status_tick()

    def refresh(self):
        """Actualiza datos sin reconstruir la vista si visualmente no cambió nada."""
        battery_changed = self._sync_preloaded_battery_state()
        self._lazy_load(self._tab)
        # V111: volver a una página cacheada no destruye/recrea el árbol CTk.
        # Los jobs asíncronos ya solicitan render cuando llegan datos nuevos; aquí
        # sólo es necesario reconstruir si la presencia/estado de batería cambió.
        if battery_changed:
            self._request_render(1)

    def destroy(self):
        self._alive=False
        if self._render_after_id is not None:
            try:
                self.app.after_cancel(self._render_after_id)
            except Exception:
                pass
            self._render_after_id = None
        self._game_artwork_generation += 1
        self._close_game_actions()
        if self._performance_after_id is not None:
            try: self.app.after_cancel(self._performance_after_id)
            except Exception: pass
            self._performance_after_id = None
        try: self.frame.destroy()
        except Exception: pass
