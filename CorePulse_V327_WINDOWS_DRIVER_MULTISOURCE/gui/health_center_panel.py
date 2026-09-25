"""Centro de Salud avanzado: batería, throttling, benchmark 3D, Windows, historial y rollback."""
from __future__ import annotations

import copy
import ctypes
import re
import threading
import time
import datetime as dt
import logging
import os
import webbrowser
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, filedialog

import customtkinter as ctk
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from PIL import Image, ImageTk, ImageDraw

from core.theme_manager import color as theme_color
from core.battery_health import collect_battery_health, probe_battery_presence
from core.directx_benchmark import gpu_profile_info
from core.benchmark_engine import run_benchmark_suite, benchmark_profile_info, BENCHMARK_METHOD_ID
from core.benchmark_version import GPU_BENCHMARK_LABEL, GPU_PROVIDER, GPU_POLICY
from core.benchmark_presentation import benchmark_component_reading, benchmark_run_conclusion
from core.sensor_diagnostics import build_sensor_diagnostics
from core.health_intelligence import build_health_intelligence
from core.startup_analyzer import disable_startup_item, restore_startup_item
from core.before_after import capture_metrics, save_snapshot, load_snapshots, compare, latest_operations
from core.device_identity import collect_hardware_inventory
from core.windows_commands import is_admin, request_elevation, looks_like_access_denied
from performance.game_presentation import load_game_artwork, fallback_game_icon
from core.windows_health import (
    analyze_startup, analyze_services, analyze_crashes, analyze_drivers,
    compare_hardware_inventory, save_hardware_baseline, restore_point_status, create_restore_point,
)
from core.driver_updates import (
    DriverUpdateError, scan_driver_updates, download_driver_update, install_driver_update,
    download_all_driver_updates, install_all_driver_updates,
)
from core.windows_repair import (
    repair_capabilities, run_integrity_diagnostic_visible, run_windows_repair_visible,
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
BENCH_ACCENT = '#2aa9e9'
BENCH_ACCENT_HOVER = '#1788c4'
BENCH_ACCENT_DARK = theme_color('#0e2a40')
BENCH_ACCENT_BORDER = theme_color('#2f7ba5')
BENCH_ACCENT_TEXT = theme_color('#7dd8ff')
BENCH_BORDER = theme_color('#27435f')
BENCH_SURFACE = theme_color('#081827')
BENCH_SURFACE_RAISED = theme_color('#0b1d2f')
BENCH_SURFACE_SOFT = theme_color('#0b1726')
BENCH_RADIUS_CARD = 12
BENCH_RADIUS_CONTROL = 9
BENCH_FONT_METRIC = 22
BENCH_FONT_SCENE_VALUE = 15
BENCH_FONT_TITLE = 16
BENCH_FONT_SECTION = 11
BENCH_FONT_BODY = 10
BENCH_FONT_META = 9
BENCH_FONT_MICRO = 8



class _BenchmarkHudOverlay:
    """HUD CorePulse externo al renderer DirectX.

    V195 mantiene la medición real separada del HUD: el HUD consume únicamente callbacks
    reales ya producidos por DirectX y nunca participa en la región medida.
    La presentación se alinea con la identidad azul/cian de CorePulse y el cursor
    del HWND DirectX se suprime a nivel de clase de ventana para evitar el aro
    de espera que Windows volvía a publicar sobre la escena.
    """

    DX_WINDOW_TITLE = f'CorePulse Benchmark {GPU_BENCHMARK_LABEL} — DirectX 11'
    _GCLP_HCURSOR = -12

    def __init__(self, root):
        self.root = root
        self._left = None
        self._right = None
        self._left_canvas = None
        self._right_canvas = None
        self._left_scene_id = None
        self._right_value_id = None
        self._right_state_id = None
        self._visible = False
        self._cursor_restore_calls = 0
        self._dx_cursor_hwnd = None
        self._dx_cursor_previous = None
        self._cursor_guard_after = None
        self._cursor_guard_active = False

    @staticmethod
    def _rounded_panel(canvas, width, height, *, accent=False):
        border = '#285f80'
        fill = '#071522'
        r = 12
        outer = [
            r, 1, width-r, 1, width-1, 1, width-1, r,
            width-1, height-r, width-1, height-1, width-r, height-1,
            r, height-1, 1, height-1, 1, height-r, 1, r, 1, 1
        ]
        inner = [
            r, 2, width-r, 2, width-2, 2, width-2, r,
            width-2, height-r, width-2, height-2, width-r, height-2,
            r, height-2, 2, height-2, 2, height-r, 2, r, 2, 2
        ]
        canvas.create_polygon(outer, smooth=True, splinesteps=24, fill=border, outline='')
        canvas.create_polygon(inner, smooth=True, splinesteps=24, fill=fill, outline='')
        if accent:
            canvas.create_rectangle(2, 11, 5, height-11, fill='#2aa9e9', outline='')

    def _make_window(self, width, kind):
        height = 64
        win = tk.Toplevel(self.root)
        win.withdraw()
        try: win.overrideredirect(True)
        except Exception: pass
        try: win.attributes('-topmost', True)
        except Exception: pass
        try: win.attributes('-alpha', 0.97)
        except Exception: pass
        try: win.wm_attributes('-toolwindow', True)
        except Exception: pass
        try: win.wm_attributes('-disabled', True)
        except Exception: pass

        key = '#010203'
        win.configure(bg=key)
        try:
            win.wm_attributes('-transparentcolor', key)
        except Exception:
            pass
        canvas = tk.Canvas(
            win, width=int(width), height=height, bg=key,
            highlightthickness=0, bd=0, relief='flat',
        )
        canvas.pack(fill='both', expand=True)
        self._rounded_panel(canvas, int(width), height, accent=(kind == 'left'))

        if kind == 'left':
            canvas.create_text(
                18, 18, text=f'COREPULSE  ·  BENCHMARK GPU {GPU_BENCHMARK_LABEL}',
                anchor='w', fill='#7dd8ff', font=('Segoe UI', 9, 'bold')
            )
            scene_id = canvas.create_text(
                18, 43, text='PREPARANDO GPU',
                anchor='w', fill='#f4f7fb', font=('Segoe UI', 12, 'bold')
            )
            return win, canvas, scene_id, None
        canvas.create_text(
            int(width)-16, 17, text='FPS REAL',
            anchor='e', fill='#94a3b8', font=('Segoe UI', 9, 'bold')
        )
        value_id = canvas.create_text(
            int(width)-16, 42, text='N/A',
            anchor='e', fill='#f4f7fb', font=('Segoe UI', 18, 'bold')
        )
        state_id = canvas.create_text(
            14, 42, text='',
            anchor='w', fill='#7dd8ff', font=('Segoe UI', 8, 'bold')
        )
        return win, canvas, value_id, state_id

    def _ensure(self):
        if self._left is None:
            self._left, self._left_canvas, self._left_scene_id, _ = self._make_window(390, 'left')
        if self._right is None:
            self._right, self._right_canvas, self._right_value_id, self._right_state_id = self._make_window(182, 'right')

    def _hide_cursor_windows(self):
        if self._cursor_restore_calls:
            return
        try:
            user32 = ctypes.WinDLL('user32.dll')
            user32.ShowCursor.argtypes = [ctypes.c_int]
            user32.ShowCursor.restype = ctypes.c_int
            calls = 0
            while calls < 16:
                calls += 1
                if int(user32.ShowCursor(False)) < 0:
                    break
            self._cursor_restore_calls = calls
        except Exception:
            self._cursor_restore_calls = 0

    def _suppress_directx_window_cursor(self):
        """Anula el cursor de la clase HWND DirectX sin tocar el renderer vigente."""
        try:
            user32 = ctypes.WinDLL('user32.dll')
            user32.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
            user32.FindWindowW.restype = ctypes.c_void_p
            hwnd = user32.FindWindowW(None, self.DX_WINDOW_TITLE)
            if not hwnd:
                return False
            get_class = getattr(user32, 'GetClassLongPtrW', None) or getattr(user32, 'GetClassLongW')
            set_class = getattr(user32, 'SetClassLongPtrW', None) or getattr(user32, 'SetClassLongW')
            get_class.argtypes = [ctypes.c_void_p, ctypes.c_int]
            get_class.restype = ctypes.c_void_p
            set_class.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
            set_class.restype = ctypes.c_void_p
            if self._dx_cursor_hwnd != hwnd:
                self._dx_cursor_hwnd = hwnd
                self._dx_cursor_previous = get_class(hwnd, self._GCLP_HCURSOR)
            set_class(hwnd, self._GCLP_HCURSOR, None)
            try:
                user32.SetCursor.argtypes = [ctypes.c_void_p]
                user32.SetCursor.restype = ctypes.c_void_p
                user32.SetCursor(None)
            except Exception:
                pass
            return True
        except Exception:
            return False

    def _cursor_guard_tick(self):
        self._cursor_guard_after = None
        if not self._cursor_guard_active:
            return
        self._hide_cursor_windows()
        self._suppress_directx_window_cursor()
        try:
            self._cursor_guard_after = self.root.after(120, self._cursor_guard_tick)
        except Exception:
            self._cursor_guard_after = None

    def _start_cursor_guard(self):
        self._cursor_guard_active = True
        if self._cursor_guard_after is None:
            try:
                self._cursor_guard_after = self.root.after(20, self._cursor_guard_tick)
            except Exception:
                self._cursor_guard_tick()

    def _restore_directx_window_cursor(self):
        hwnd = self._dx_cursor_hwnd
        previous = self._dx_cursor_previous
        self._dx_cursor_hwnd = None
        self._dx_cursor_previous = None
        if not hwnd or previous is None:
            return
        try:
            user32 = ctypes.WinDLL('user32.dll')
            set_class = getattr(user32, 'SetClassLongPtrW', None) or getattr(user32, 'SetClassLongW')
            set_class.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
            set_class.restype = ctypes.c_void_p
            set_class(hwnd, self._GCLP_HCURSOR, previous)
        except Exception:
            pass

    def _restore_cursor_windows(self):
        calls = int(self._cursor_restore_calls or 0)
        self._cursor_restore_calls = 0
        if not calls:
            return
        try:
            user32 = ctypes.WinDLL('user32.dll')
            user32.ShowCursor.argtypes = [ctypes.c_int]
            user32.ShowCursor.restype = ctypes.c_int
            for _ in range(calls):
                user32.ShowCursor(True)
        except Exception:
            pass

    @staticmethod
    def _scene_text(stage):
        raw = str(stage or '').split('·', 1)[-1].strip()
        folded = raw.casefold()
        # 'Valle completo / Extreme' contiene la palabra valle. Extreme debe
        # evaluarse primero o el HUD lo etiqueta erróneamente como Escena 1/4.
        mapping = (
            ('extreme', 'EXTREME', 'ESCENA 4/4'),
            ('bosque', 'BOSQUE', 'ESCENA 2/4'),
            ('lago', 'LAGO', 'ESCENA 3/4'),
            ('valle', 'VALLE', 'ESCENA 1/4'),
        )
        for token, label, idx in mapping:
            if token in folded:
                return f'{label}  ·  {idx}'
        return (raw or 'GPU').upper()

    def update(self, stage, detail=''):
        stage = str(stage or '')
        if not stage.startswith('GPU ·'):
            self.hide()
            return
        self._ensure()
        detail_text = str(detail or '')
        match = re.search(r'([0-9]+(?:[\.,][0-9]+)?)\s*FPS\b', detail_text, flags=re.I)
        if match:
            value = match.group(1).replace(',', '.')
            state = ''
        elif 'warm-up' in detail_text.casefold() or 'calentamiento' in detail_text.casefold():
            value, state = 'N/A', 'WARM-UP'
        elif 'estabil' in detail_text.casefold():
            value, state = 'N/A', 'SETTLE'
        else:
            value, state = 'N/A', ''
        try:
            self._left_canvas.itemconfigure(self._left_scene_id, text=self._scene_text(stage))
            self._right_canvas.itemconfigure(self._right_value_id, text=value + (' FPS' if value != 'N/A' else ''))
            self._right_canvas.itemconfigure(self._right_state_id, text=state)
            sw = max(640, int(self.root.winfo_screenwidth()))
            self._left.geometry('390x64+20+20')
            self._right.geometry(f'182x64+{max(20, sw-202)}+20')
            for win in (self._left, self._right):
                win.deiconify(); win.lift()
                try: win.attributes('-topmost', True)
                except Exception: pass
            self._visible = True
            self._start_cursor_guard()
            self._suppress_directx_window_cursor()
        except Exception:
            self.hide()

    def prepare_gpu(self):
        self._hide_cursor_windows()
        self._start_cursor_guard()

    def hide(self):
        for win in (self._left, self._right):
            try:
                if win is not None and win.winfo_exists():
                    win.withdraw()
            except Exception:
                pass
        self._visible = False
        self._cursor_guard_active = False
        if self._cursor_guard_after is not None:
            try: self.root.after_cancel(self._cursor_guard_after)
            except Exception: pass
            self._cursor_guard_after = None
        self._restore_directx_window_cursor()
        self._restore_cursor_windows()

    def destroy(self):
        self.hide()
        for win in (self._left, self._right):
            try:
                if win is not None and win.winfo_exists():
                    win.destroy()
            except Exception:
                pass
        self._left = self._right = None
        self._left_canvas = self._right_canvas = None
        self._left_scene_id = self._right_value_id = self._right_state_id = None

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
    gpu_hotspot = first_number(tele.get('gpu_hotspot'))
    gpu_usage = first_number(tele.get('gpu_usage'))
    gpu_vram_used_mb = None
    gpu_vram_usage_percent = None
    gpu_temp_limit = None
    gpu_hotspot_limit = None
    for gpu in gpus:
        if not isinstance(gpu, dict):
            continue
        if gpu_temp is None:
            gpu_temp = first_number(gpu.get('temperature_c'), gpu.get('hotspot_c'))
        if gpu_hotspot is None:
            gpu_hotspot = first_number(gpu.get('hotspot_c'))
        if gpu_usage is None:
            gpu_usage = first_number(gpu.get('usage_percent'))
        if gpu_vram_used_mb is None:
            gpu_vram_used_mb = first_number(gpu.get('memory_used_mb'))
        if gpu_vram_usage_percent is None:
            gpu_vram_usage_percent = first_number(gpu.get('memory_usage_percent'))
        sensor_rows = gpu.get('sensors') if isinstance(gpu.get('sensors'), list) else []
        for row in sensor_rows:
            if not isinstance(row, dict):
                continue
            name = str(row.get('name') or row.get('sensor_name') or '').casefold()
            sensor_type = str(row.get('type') or row.get('sensor_type') or '').casefold()
            value = first_number(row.get('value'))
            if value is None or not (20.0 <= value <= 150.0):
                continue
            is_temp_limit = (
                ('limit' in name or 'critical' in name)
                and ('temp' in name or 'thermal' in name or sensor_type == 'temperature')
            )
            if not is_temp_limit:
                continue
            if 'hot' in name and gpu_hotspot_limit is None:
                gpu_hotspot_limit = value
            elif gpu_temp_limit is None:
                gpu_temp_limit = value

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
        'cpu_tjmax_distance': first_number(
            cpu.get('distance_to_tjmax_min_c'), tele.get('cpu_distance_to_tjmax_min_c'),
            tele.get('distance_to_tjmax_min_c')
        ),
        'cpu_ghz': cpu_ghz,
        'cpu_usage': first_number(tele.get('cpu_usage'), cpu.get('total_load_percent')),
        'ram_usage': first_number(tele.get('ram_usage')),
        'gpu_temp': gpu_temp,
        'gpu_hotspot': gpu_hotspot,
        'gpu_temp_limit': gpu_temp_limit,
        'gpu_hotspot_limit': gpu_hotspot_limit,
        'gpu_usage': gpu_usage,
        'gpu_vram_used_mb': gpu_vram_used_mb,
        'gpu_vram_usage_percent': gpu_vram_usage_percent,
    }



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
    return {'DEVICE_PROBLEM':'Incidencia de Windows','UNSIGNED':'Sin firma reconocida','OLD':'Antiguo · comprobar versión','OK':'Correcto','N/A':'N/A'}.get(raw, str(value or 'N/A'))


def _driver_status_detail(item):
    status = str((item or {}).get('status') or 'N/A').strip().upper()
    base = _driver_status_label(status)
    if status == 'DEVICE_PROBLEM':
        detail = str((item or {}).get('problem_detail') or '').strip()
        return f'{base} · {detail}' if detail else base
    if status == 'OLD':
        try:
            years = float((item or {}).get('age_years'))
            return f'{base} · {years:.0f} años'
        except Exception:
            return base
    return base


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

    def __init__(self, app, host, *, performance_only=False, external_scroll=None, benchmark_only=False, initial_tab=None, initial_windows_section=None):
        self.app = app; self.host = host; self._alive = True; self._visible = True; self._performance_only = bool(performance_only); self._benchmark_only = bool(benchmark_only); self._external_scroll = external_scroll
        if self._performance_only:
            self._tab = 'performance'
        else:
            requested_tab = str(initial_tab or 'summary').strip().lower()
            self._tab = requested_tab if requested_tab in {'summary', 'battery', 'windows', 'repair', 'history', 'recovery', 'corepulse', 'audio'} else 'summary'
        self._initial_windows_section = str(initial_windows_section or 'summary').strip().lower()
        self._jobs=set()
        self._battery=None; self._startup=None; self._services=None; self._crashes=None; self._drivers=None; self._hw=None; self._restore=None
        self._driver_updates = None
        cached_drivers = getattr(app, 'driver_inventory_cache', None)
        cached_drivers_ts = float(getattr(app, 'driver_inventory_cache_timestamp', 0.0) or 0.0)
        if isinstance(cached_drivers, dict) and (time.time() - cached_drivers_ts) < 600.0:
            self._drivers = copy.deepcopy(cached_drivers)
        self._driver_update_last_message = ''
        self._driver_update_selected = set()
        self._driver_attention_selected = set()
        self._driver_attention_initialized = False
        self._driver_attention_search_button = None
        self._driver_attention_scanning_ids = set()
        self._driver_attention_widgets = {}
        self._driver_summary_updates_value = None
        self._driver_summary_updates_detail = None
        self._show_driver_inventory = False
        # V144 — autodiagnóstico de capacidades. Se calcula en background sólo
        # al entrar a su módulo; la portada nunca bloquea por probes opcionales.
        self._corepulse_diag=None
        # Benchmark dedicado no necesita sondear batería al abrir. Evita trabajo
        # irrelevante en el primer clic y deja la respuesta visual inmediata.
        if not self._benchmark_only:
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
        # V145 — El benchmark se configura ANTES de ejecutar. GPU usa la
        # escena 3D visible; CPU/RAM/SSD usan cargas sostenidas independientes.
        self._benchmark_profile_key = 'standard'
        self._benchmark_profile_var = None
        self._benchmark_component_flags = {'gpu': True, 'cpu': True, 'ram': True, 'ssd': True}
        self._benchmark_component_vars = {}
        self._benchmark_selection_label = None
        self._benchmark_start_button = None
        self._visual_bench = None
        self._visual_benchmark_progress = 0.0
        self._visual_benchmark_stage = 'Listo para iniciar'
        self._visual_benchmark_detail = 'La prueba abrirá una escena 3D real en una ventana separada.'
        self.btn_visual_bench = None
        self.visual_bench_progress_bar = None
        self.lbl_visual_bench_progress = None
        self.lbl_visual_bench_detail = None
        self._benchmark_history_cache = None
        # V187 — resultados por divulgación progresiva. El resumen es la vista
        # predeterminada; GPU/Sistema/Evidencia se abren sólo cuando el usuario
        # los solicita, evitando una pared de métricas y scroll innecesario.
        self._benchmark_result_view = 'summary'
        self._benchmark_result_view_buttons = {}
        self._benchmark_setup_collapsed = False
        self._benchmark_component_shell = None
        self._benchmark_action_shell = None
        self._benchmark_hint_shell = None
        self._benchmark_intro_title = None
        self._benchmark_intro_subtitle = None
        self._visual_benchmark_card_shell = None
        self._visual_benchmark_progress_row = None
        self._visual_benchmark_completed_label = None
        self._benchmark_evidence_sensors_expanded = False
        self._benchmark_detail_flags = {'gpu': False, 'system': False, 'evidence': False}
        self._benchmark_hud = None
        self._performance_after_id = None
        self._last_performance_generation = None
        self._performance_section = 'benchmark' if self._benchmark_only else 'home'
        self._game_library_filter = 'all'
        # V146 — Inicio también se pagina: “Ver más” debe permitir recorrer
        # TODOS los elementos devueltos por el diagnóstico, no sólo los primeros.
        self._startup_page = 0
        self._startup_page_size = 30
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
        _valid_windows_sections = {'summary', 'startup', 'services', 'crashes', 'drivers'}
        self._windows_section = (
            self._initial_windows_section
            if self._tab == 'windows' and self._initial_windows_section in _valid_windows_sections
            else 'summary'
        )

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
        if self._performance_only and not self._benchmark_only:
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
            # V186: la página dedicada Benchmark usa un viewport normal +
            # desplazamiento por place. Esto evita en Windows el desfase de
            # pintura entre Canvas.create_window y los widgets CTk densos.
            scroll_backend = 'place' if self._benchmark_only else 'canvas'
            self.scroll = StableScrollHost(self.frame, fg_color=BG, backend=scroll_backend)
            self.scroll.pack(fill='both', expand=True, padx=15 if not self._performance_only else 0, pady=(0, 10))
            self.body = self.scroll.content

        # V193: el resultado final del Benchmark dedicado usa una superficie
        # estática separada del scroll de configuración/progreso. En Windows,
        # desplazar muchos widgets CTk inmediatamente tras publicar resultados
        # podía dejar píxeles antiguos durante unos frames.
        self._benchmark_static_results = None
        self._benchmark_results_static_active = False
        if self._benchmark_only and self._external_scroll is None:
            self._benchmark_static_results = ctk.CTkFrame(
                self.frame, fg_color=BG, corner_radius=0, border_width=0
            )
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
            'audio': {
                'button_text': 'Volver a Centro de salud',
                'button_width': 186,
                'button_command': lambda: self._select_tab('summary'),
                'eyebrow': 'Verificación manual',
                'title': 'Test de Audio',
                'subtitle': 'Salida, canales y micrófono · grabación local sólo al pulsar Grabar.',
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
            'corepulse': {
                'button_text': 'Volver a Centro de salud',
                'button_width': 186,
                'button_command': lambda: self._select_tab('summary'),
                'eyebrow': 'Compatibilidad del equipo actual',
                'title': 'Estado de CorePulse',
                'subtitle': 'Comprueba runtime, herramientas y sensores disponibles sin convertir capacidades N/A en fallos.',
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
            text=text, command=command, height=height, corner_radius=9,
            border_width=1, font=(FONT, 10, 'bold')
        )
        if width is not None:
            common['width'] = width
        if variant == 'primary':
            common.update(
                fg_color=TAB_ACTIVE, hover_color=TAB_HOVER, border_color=ACTION_BORDER,
                text_color='#ffffff', text_color_disabled='#e7eef7',
            )
        elif variant == 'ghost':
            common.update(
                fg_color='transparent', hover_color=theme_color('#102840'), border_color=BORDER,
                text_color=TEXT, text_color_disabled=MUTED,
            )
        elif variant == 'tab':
            common.update(
                fg_color='transparent', hover_color=theme_color('#102840'), border_color=BORDER,
                text_color=TEXT, text_color_disabled=MUTED,
            )
        else:
            # V325: nunca usar el acento como texto sobre accent_2. En temas como
            # Grafito/Oro/Eléctrico ambos podían quedar demasiado próximos.
            common.update(
                fg_color=ACTION_BG, hover_color=ACTION_HOVER, border_color=ACTION_BORDER,
                text_color='#ffffff', text_color_disabled='#d8e2ee',
            )
        return ctk.CTkButton(parent, **common)

    def navigate_to(self, key='summary', windows_section=None):
        """Cambia de destino en un solo render, sin publicar vistas intermedias.

        V144: los accesos profundos desde Diagnóstico pueden preparar Windows →
        Controladores (u otra sección) mientras el host todavía está oculto. Así
        el primer frame visible ya corresponde al destino final.
        """
        if self._performance_only:
            return False
        valid_tabs = {'summary', 'battery', 'windows', 'repair', 'history', 'recovery', 'corepulse', 'audio'}
        target = str(key or 'summary').strip().lower()
        if target not in valid_tabs:
            target = 'summary'

        valid_sections = {'summary', 'startup', 'services', 'crashes', 'drivers'}
        current_tab = self._tab
        current_section = self._windows_section
        if target == 'windows':
            requested_section = str(windows_section or ('summary' if current_tab != 'windows' else current_section)).strip().lower()
            if requested_section not in valid_sections:
                requested_section = 'summary'
            target_section = requested_section
        else:
            target_section = 'summary'

        changed = target != current_tab or target_section != current_section
        self._tab = target
        self._windows_section = target_section
        if changed:
            self._restore_scroll_fraction = 0.0
            self._apply_tab_style()
            self._sync_header_context()
            self._render()
        self._lazy_load(target)
        return True

    def _select_tab(self,key):
        return self.navigate_to(key)

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
            parent or self.body, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=15
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
            'Test de Audio': {
                'icon': '🎧', 'category': 'Sonido y micrófono', 'accent': CYAN,
                'bg': theme_color('#11283a'), 'border': theme_color('#2f6084'),
                'tags': ('Canales', 'Micrófono', 'Grabación')
            },
            'CorePulse': {
                'icon': '◆', 'category': 'Capacidades reales', 'accent': GREEN,
                'bg': theme_color('#13271f'), 'border': theme_color('#245d43'),
                'tags': ('Runtime', 'Sensores', 'Herramientas')
            },
        }
        return profiles.get(title, {
            'icon': '•', 'category': 'Módulo', 'accent': TEXT2,
            'bg': CARD2, 'border': BORDER, 'tags': ()
        })

    def _health_module_card(self, parent, row, column, title, description, status, color, command, button_text='Abrir'):
        """Tarjeta de módulo con la misma jerarquía visual del Resumen principal."""
        profile = self._health_module_visual_profile(title)
        accent_color = profile['accent']

        card = ctk.CTkFrame(
            parent, fg_color=CARD, border_width=1, border_color=BORDER,
            corner_radius=15
        )
        card.grid(row=row, column=column, sticky='nsew', padx=5, pady=5)

        shell = ctk.CTkFrame(card, fg_color='transparent')
        shell.pack(fill='both', expand=True)
        accent = ctk.CTkFrame(shell, fg_color=accent_color, width=4, corner_radius=14)
        accent.pack(side='left', fill='y', padx=(1, 0), pady=1)

        content = ctk.CTkFrame(shell, fg_color='transparent')
        content.pack(side='left', fill='both', expand=True, padx=(12, 12), pady=(10, 11))

        top = ctk.CTkFrame(content, fg_color='transparent')
        top.pack(fill='x')

        icon_bg = profile.get('bg') or CARD2
        icon = ctk.CTkLabel(
            top, text=profile['icon'], width=42, height=42, corner_radius=13,
            fg_color=icon_bg, text_color=accent_color,
            font=(FONT, 17, 'bold')
        )
        icon.pack(side='left', padx=(0, 10))

        identity = ctk.CTkFrame(top, fg_color='transparent')
        identity.pack(side='left', fill='x', expand=True)
        ctk.CTkLabel(
            identity, text=str(profile['category']).upper(), font=(FONT, 8, 'bold'),
            text_color=accent_color, anchor='w'
        ).pack(fill='x')
        ctk.CTkLabel(
            identity, text=title, font=(FONT, 15, 'bold'), text_color=TEXT,
            anchor='w', justify='left'
        ).pack(fill='x', pady=(2, 0))

        status_box = ctk.CTkFrame(top, fg_color='transparent')
        status_box.pack(side='right', padx=(8, 0), anchor='n')
        ctk.CTkLabel(
            status_box, text='●', width=10, font=(FONT, 8, 'bold'), text_color=color
        ).pack(side='left', padx=(0, 4))
        ctk.CTkLabel(
            status_box, text=str(status), font=(FONT, 8, 'bold'), text_color=color,
            anchor='e', justify='right', wraplength=145
        ).pack(side='left')

        ctk.CTkLabel(
            content, text=description, font=(FONT, 9), text_color=TEXT2,
            anchor='w', justify='left', wraplength=330
        ).pack(fill='x', pady=(8, 9))

        action = self._button(
            content, f'{button_text}   →', command,
            variant='secondary', height=31
        )
        action.pack(fill='x', pady=(1, 0))
        return card

    def _capture_scroll_fraction(self):
        try:
            first, _last = self.scroll.yview()
            return max(0.0, min(1.0, float(first)))
        except Exception:
            return 0.0

    def _request_render(self, delay=0):
        """Agrupa renders dinámicos y espera al scroll si está en movimiento."""
        if not self._alive or self._tab == 'audio':
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
                self.scroll.yview_moveto(max(0.0, min(1.0, float(fraction))))
            except Exception:
                try:
                    self.scroll.canvas.yview_moveto(max(0.0, min(1.0, float(fraction))))
                except Exception:
                    pass

        # Invalida también píxeles de widgets destruidos dentro del Canvas en Windows.
        try:
            self.scroll._flush_repaint(strong=True)
        except Exception:
            pass
        # El backend Canvas histórico conserva su flush adicional. V186 no lo
        # necesita en Benchmark porque el contenido ya no vive en create_window.
        if getattr(self.scroll, 'backend', 'canvas') == 'canvas':
            try:
                canvas = getattr(self.scroll, '_canvas', None) or getattr(self.scroll, 'canvas', None)
                if canvas is not None and canvas.winfo_exists():
                    canvas.update_idletasks()
                    canvas.update()
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
                'audio': self._render_audio,
                'battery': self._render_battery,
                'performance': self._render_performance,
                'windows': self._render_windows,
                'repair': self._render_repair,
                'history': self._render_history,
                'recovery': self._render_recovery,
                'corepulse': self._render_corepulse_diagnostics,
            }.get(self._tab, self._render_summary)
            renderer()
        except Exception:
            self._rendering = False
            raise

        try:
            self.app.after_idle(self._finalize_render)
        except Exception:
            self._finalize_render()

    def _health_intelligence_snapshot(self):
        tele = copy.deepcopy(getattr(self.app, 'latest_telemetry', {}) or {})
        disks = copy.deepcopy(getattr(self.app, 'latest_disks', []) or [])
        alerts = []
        try:
            agent = getattr(self.app, 'realtime_agent', None)
            state = agent.get_state() if agent is not None and hasattr(agent, 'get_state') else {}
            alerts = ((state or {}).get('alerts') or {}).get('active') or []
        except Exception:
            alerts = []
        return build_health_intelligence(
            tele, disks, preliminary_score=getattr(self.app, 'latest_score', None),
            battery=self._battery if isinstance(self._battery, dict) else None,
            throttling=getattr(self.app, 'thermal_throttling_state', {}) or {},
            crashes=self._crashes if isinstance(self._crashes, dict) else None,
            active_alerts=alerts,
        )

    def _render_audio(self):
        from gui.audio_test_panel import AudioTestPanel
        self._audio_panel = AudioTestPanel(self.body)
        self._audio_panel.pack(fill='x', padx=8, pady=8)

    def _render_health_intelligence_card(self):
        """Resumen general compacto y explicable.

        V141 elimina el gran bloque vacío, el índice poco contextual y textos de
        política repetidos. La evidencia accionable queda visible con tipografía
        mayor y en una sola tarjeta de altura contenida.
        """
        data = self._health_intelligence_snapshot()
        state = str(data.get('state') or 'NO_EVALUABLE').upper()
        accent = RED if state == 'CRITICAL' else AMBER if state in ('WARNING', 'ATTENTION') else GREEN if state == 'NORMAL' else MUTED
        card = self._card(); card.pack(fill='x', padx=8, pady=(2, 8))

        header = ctk.CTkFrame(card, fg_color='transparent')
        header.pack(fill='x', padx=15, pady=(12, 4))
        left = ctk.CTkFrame(header, fg_color='transparent')
        left.pack(side='left', fill='x', expand=True)
        ctk.CTkLabel(
            left, text='ESTADO GENERAL', font=(FONT, 9, 'bold'), text_color=MUTED,
            anchor='w'
        ).pack(fill='x')
        ctk.CTkLabel(
            left, text=str(data.get('title') or 'Evidencia insuficiente'),
            font=(FONT, 20, 'bold'), text_color=accent, anchor='w'
        ).pack(fill='x', pady=(2, 0))

        coverage = data.get('coverage') or []
        coverage_text = f"{len(coverage)} fuente{'s' if len(coverage) != 1 else ''}" if coverage else 'Sin cobertura suficiente'
        ctk.CTkLabel(
            header, text=coverage_text, font=(FONT, 9, 'bold'), text_color=TEXT2,
            anchor='e', justify='right'
        ).pack(side='right', padx=(12, 0), pady=(2, 0))

        summary = str(data.get('summary') or '').strip()
        if summary:
            ctk.CTkLabel(
                card, text=summary, font=(FONT, 11), text_color=TEXT2,
                anchor='w', justify='left', wraplength=1080
            ).pack(fill='x', padx=15, pady=(0, 7))

        factors = list(data.get('factors') or [])[:3]
        if factors:
            evidence = ctk.CTkFrame(card, fg_color=CARD2, border_width=1, border_color=BORDER, corner_radius=7)
            evidence.pack(fill='x', padx=14, pady=(0, 8))
            for idx, factor in enumerate(factors):
                lvl = str(factor.get('level') or '').upper()
                tone = RED if lvl == 'CRITICAL' else AMBER if lvl in ('WARNING', 'ATTENTION') else GREEN if lvl == 'NORMAL' else TEXT2
                row = ctk.CTkFrame(evidence, fg_color='transparent')
                row.pack(fill='x', padx=10, pady=(7 if idx == 0 else 3, 7 if idx == len(factors) - 1 else 3))
                area = str(factor.get('area') or 'Sistema')
                text = str(factor.get('text') or '')
                ctk.CTkLabel(
                    row, text=area, font=(FONT, 10, 'bold'), text_color=tone,
                    anchor='w', width=100
                ).pack(side='left', padx=(0, 8))
                ctk.CTkLabel(
                    row, text=text, font=(FONT, 10), text_color=TEXT2,
                    anchor='w', justify='left', wraplength=900
                ).pack(side='left', fill='x', expand=True)

        if coverage:
            ctk.CTkLabel(
                card, text='Evidencia: ' + ' · '.join(coverage), font=(FONT, 9),
                text_color=MUTED, anchor='w', justify='left', wraplength=1080
            ).pack(fill='x', padx=15, pady=(0, 11))
        else:
            ctk.CTkLabel(
                card, text='CorePulse mostrará una conclusión cuando existan lecturas reales suficientes.',
                font=(FONT, 8), text_color=MUTED, anchor='w', justify='left'
            ).pack(fill='x', padx=15, pady=(0, 11))

    def _render_summary(self):
        # V0.10.2.81w — La portada del Centro de Salud queda todavía más directa:
        # sin bloque introductorio redundante, para que las tarjetas comiencen antes
        # y la pestaña funcione como acceso rápido a sus módulos.
        self._render_health_intelligence_card()

        section = ctk.CTkFrame(self.body, fg_color='transparent')
        section.pack(fill='x', padx=6, pady=(6, 2))
        ctk.CTkLabel(
            section, text='Áreas de mantenimiento y diagnóstico',
            font=(FONT, 15, 'bold'), text_color=TEXT, anchor='w'
        ).pack(fill='x')
        ctk.CTkLabel(
            section, text='Revisa el estado de cada área y abre sólo la herramienta que necesites.',
            font=(FONT, 9), text_color=MUTED, anchor='w'
        ).pack(fill='x', pady=(1, 4))

        modules = ctk.CTkFrame(self.body, fg_color='transparent')
        modules.pack(fill='x', padx=5, pady=(0, 8))
        for col in range(3):
            modules.grid_columnconfigure(col, weight=1, uniform='health_module_cards')

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

        session_recovery = getattr(self.app, 'session_recovery_status', {}) or {}
        previous_abnormal = session_recovery.get('previous_abnormal') if isinstance(session_recovery, dict) else None
        if isinstance(previous_abnormal, dict):
            recovery_status, recovery_tone = 'Cierre no limpio detectado', AMBER
        elif isinstance(self._restore, dict):
            if self._restore.get('error'):
                recovery_status, recovery_tone = 'No verificable', AMBER
            else:
                recovery_status, recovery_tone = 'Estado verificado', GREEN
        else:
            recovery_status, recovery_tone = 'Sin incidencias de sesión', GREEN

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
                'Throttling, perfiles de energía y herramientas Gaming.',
                _state_label(throttle_state), throttle_color,
                lambda: getattr(self.app, 'open_gaming', lambda *_: None)('performance')
            ),
        ))
        from gui.audio_test_panel import open_audio_test
        module_specs.append((
            'Test de Audio', 'Canales izquierdo/derecho y micrófono con confirmación manual.',
            'Prueba guiada · local', CYAN, lambda: open_audio_test(self.app)
        ))
        for index, spec in enumerate(module_specs):
            row_index, column_index = divmod(index, 3)
            self._health_module_card(modules, row_index, column_index, *spec)


    def _corepulse_state_style(self, state):
        raw = str(state or 'N/A').upper()
        return {
            'AVAILABLE': ('Disponible', GREEN),
            'PARTIAL': ('Parcial', AMBER),
            'ERROR': ('Error', RED),
            'INFO': ('Info', CYAN),
            'N/A': ('N/A', MUTED),
        }.get(raw, ('N/A', MUTED))

    def _corepulse_runtime_context(self):
        agent = getattr(self.app, 'realtime_agent', None)
        return {
            'agent_running': bool(getattr(agent, 'running', False)),
            'telemetry_snapshot': bool(getattr(self.app, 'latest_telemetry', {}) or {}),
        }

    def _load_corepulse_diagnostics(self, force=False):
        if force:
            self._corepulse_diag = None
        if 'corepulse_diagnostics' in self._jobs:
            return False
        snap = copy.deepcopy(getattr(self.app, 'latest_telemetry', {}) or {})
        context = self._corepulse_runtime_context()
        def work():
            # V141: el autodiagnóstico técnico ya no forma parte de la portada.
            # Importarlo sólo bajo demanda reduce trabajo al abrir Centro de salud.
            from core.corepulse_diagnostics import collect_corepulse_diagnostics
            return collect_corepulse_diagnostics(snap, runtime_context=context, persist=True)
        def done(result, error):
            if isinstance(result, dict):
                self._corepulse_diag = result
            else:
                self._corepulse_diag = {
                    'ready': False, 'overall_state': 'ERROR',
                    'title': 'No se pudo completar el autodiagnóstico',
                    'counts': {'ERROR': 1}, 'runtime': [], 'optional': [], 'sensors': [],
                    'note': error or 'El detalle técnico fue registrado en los logs.',
                }
        started = self._async('corepulse_diagnostics', work, done)
        if started:
            self._request_render(1)
        return started

    def _corepulse_diag_row(self, parent, item):
        state_text, tone = self._corepulse_state_style(item.get('state'))
        row = ctk.CTkFrame(parent, fg_color=CARD2, border_width=1, border_color=BORDER, corner_radius=8)
        row.pack(fill='x', padx=12, pady=4)
        row.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            row, text=str(item.get('label') or 'Capacidad'), font=(FONT, 9, 'bold'),
            text_color=TEXT, anchor='w', justify='left'
        ).grid(row=0, column=0, sticky='ew', padx=(11, 8), pady=(8, 1))
        badge = ctk.CTkFrame(row, fg_color='transparent', border_width=1, border_color=tone, corner_radius=999)
        badge.grid(row=0, column=1, sticky='e', padx=(6, 11), pady=(6, 1))
        ctk.CTkLabel(badge, text=state_text, font=(FONT, 8, 'bold'), text_color=tone).pack(padx=8, pady=2)
        detail = str(item.get('detail') or 'Sin detalle adicional.')
        ctk.CTkLabel(
            row, text=detail, font=(FONT, 8), text_color=MUTED, anchor='w',
            justify='left', wraplength=900
        ).grid(row=1, column=0, columnspan=2, sticky='ew', padx=11, pady=(1, 8))
        return row

    def _render_corepulse_diagnostics(self):
        self._title(
            'Estado de CorePulse',
            'Comprueba qué puede usar CorePulse en este equipo. N/A significa no instalado, no presente o no expuesto; no equivale a un fallo.'
        )
        data = self._corepulse_diag
        if data is None:
            self._loading('Comprobando runtime, herramientas y sensores…')
            if 'corepulse_diagnostics' not in self._jobs:
                self._load_corepulse_diagnostics()
            return

        ready = bool(data.get('ready'))
        counts = data.get('counts') or {}
        available = int(counts.get('AVAILABLE') or 0)
        partial = int(counts.get('PARTIAL') or 0)
        na_count = int(counts.get('N/A') or 0)
        errors = int(counts.get('ERROR') or 0)
        sensor_ok = int(data.get('sensor_metrics_available') or 0)
        sensor_total = int(data.get('sensor_metrics_total') or 0)

        hero = self._card(); hero.pack(fill='x', padx=8, pady=(4, 8))
        top = ctk.CTkFrame(hero, fg_color='transparent'); top.pack(fill='x', padx=14, pady=(12, 6))
        ctk.CTkLabel(
            top, text=str(data.get('title') or ('Núcleo listo' if ready else 'Requiere atención')),
            font=(FONT, 16, 'bold'), text_color=GREEN if ready else RED, anchor='w'
        ).pack(side='left', fill='x', expand=True)
        self._button(top, 'Actualizar diagnóstico', lambda: self._load_corepulse_diagnostics(force=True), variant='secondary', height=30).pack(side='right')
        ctk.CTkLabel(
            hero, text='Política REAL_OR_NA · las capacidades opcionales ausentes se muestran como N/A y no reducen ninguna “salud”.',
            font=(FONT, 9), text_color=MUTED, anchor='w', justify='left', wraplength=1040
        ).pack(fill='x', padx=14, pady=(0, 11))

        stats = ctk.CTkFrame(self.body, fg_color='transparent'); stats.pack(fill='x', padx=5, pady=(0, 8))
        for col in range(4):
            stats.grid_columnconfigure(col, weight=1, uniform='corepulse_diag_stats')
        stat_specs = (
            ('NÚCLEO', 'Listo' if ready else 'Error', 'Dependencias obligatorias', GREEN if ready else RED),
            ('CAPACIDADES', str(available), f'{partial} parcial · {na_count} N/A', CYAN),
            ('SENSORES', f'{sensor_ok}/{sensor_total}' if sensor_total else 'N/A', 'Lecturas certificadas disponibles', GREEN if sensor_ok and sensor_total else MUTED),
            ('ERRORES', str(errors), 'Sólo fallos de comprobaciones reales', RED if errors else GREEN),
        )
        for col, (title, value, detail, tone) in enumerate(stat_specs):
            card = ctk.CTkFrame(stats, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=9)
            card.grid(row=0, column=col, sticky='nsew', padx=5, pady=0)
            ctk.CTkLabel(card, text=title, font=(FONT, 8, 'bold'), text_color=MUTED, anchor='w').pack(fill='x', padx=12, pady=(10, 2))
            ctk.CTkLabel(card, text=value, font=(FONT, 20, 'bold'), text_color=tone, anchor='w').pack(fill='x', padx=12)
            ctk.CTkLabel(card, text=detail, font=(FONT, 8), text_color=TEXT2, anchor='w', justify='left', wraplength=220).pack(fill='x', padx=12, pady=(2, 10))

        sections = (
            ('Núcleo y dependencias obligatorias', data.get('runtime') or []),
            ('Herramientas y capacidades opcionales', data.get('optional') or []),
            ('Sensores expuestos por este equipo', data.get('sensors') or []),
        )
        for title, items in sections:
            card = self._card(); card.pack(fill='x', padx=8, pady=6)
            ctk.CTkLabel(card, text=title, font=(FONT, 11, 'bold'), text_color=TEXT, anchor='w').pack(fill='x', padx=13, pady=(11, 4))
            if items:
                for item in items:
                    if isinstance(item, dict):
                        self._corepulse_diag_row(card, item)
            else:
                ctk.CTkLabel(card, text='No hay datos disponibles para esta sección.', font=(FONT, 9), text_color=MUTED, anchor='w').pack(fill='x', padx=13, pady=(4, 12))
            ctk.CTkFrame(card, height=5, fg_color='transparent').pack()

        report_path = str(data.get('report_path') or '').strip()
        footer = self._card(); footer.pack(fill='x', padx=8, pady=(6, 12))
        ctk.CTkLabel(footer, text='Informe técnico', font=(FONT, 10, 'bold'), text_color=TEXT).pack(anchor='w', padx=13, pady=(10, 2))
        ctk.CTkLabel(
            footer,
            text=(f'Guardado en: {report_path}' if report_path else 'El informe no pudo guardarse en esta sesión.'),
            font=(FONT, 8), text_color=MUTED, anchor='w', justify='left', wraplength=1020
        ).pack(fill='x', padx=13, pady=(0, 10))

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
        for idx in range(3):
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
        """Rendimiento Gaming o benchmark standalone, según el host activo."""
        if self._benchmark_only:
            self._render_gaming_benchmark_section()
            return
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
        ctk.CTkLabel(text, text=title, font=(FONT, BENCH_FONT_SCENE_VALUE, 'bold'), text_color=TEXT, anchor='w').pack(anchor='w')
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

        active_game = {}
        game_name = 'Aún no hay juego activo'
        if games:
            first = games[0] if isinstance(games[0], dict) else {}
            active_game = dict(first) if isinstance(first, dict) else {}
            game_name = str(first.get('display_name') or first.get('name') or 'Juego').strip() or 'Juego'
        elif live.get('game'):
            active_game = dict(live.get('game') or {}) if isinstance(live.get('game'), dict) else {}
            game_name = str(active_game.get('display_name') or active_game.get('name') or 'Juego').strip() or 'Juego'
        if game_name.lower().endswith('.exe'):
            game_name = game_name[:-4]
        if len(games) > 1:
            game_name = f'{game_name} +{len(games)-1}'

        game_active = bool(games or live.get('game'))
        boost_active = bool(boost.get('session_active'))

        # V287: la tarjeta de sesión de juego se retira de la portada.
        # Se mantienen los datos calculados arriba porque Game Boost todavía
        # utiliza game_active / boost_active para su estado real.

        # PERFIL: tres decisiones principales y Ahorro como opción secundaria.
        modes = self._card()
        modes.pack(fill='x', padx=8, pady=(0, 10))
        mode_accent = ctk.CTkFrame(modes, width=4, fg_color=CYAN, corner_radius=14)
        mode_accent.pack(side='left', fill='y', padx=(1, 0), pady=1)
        mode_body = ctk.CTkFrame(modes, fg_color='transparent')
        mode_body.pack(side='left', fill='both', expand=True)
        mhead = ctk.CTkFrame(mode_body, fg_color='transparent')
        mhead.pack(fill='x', padx=14, pady=(10, 5))
        ctk.CTkLabel(mhead, text='Perfil de rendimiento', font=(FONT, 12, 'bold'), text_color=TEXT).pack(side='left')
        windows_sync = bool(status.get('windows_plan_in_sync'))
        windows_verified = bool(status.get('windows_plan_verified'))
        sync_text = 'Windows sincronizado' if windows_sync else ('Plan verificado' if windows_verified else 'Plan no verificado')
        ctk.CTkLabel(
            mhead, text=sync_text, font=(FONT, 8, 'bold'),
            text_color=GREEN if windows_sync else AMBER if windows_verified else MUTED
        ).pack(side='right')

        row = ctk.CTkFrame(mode_body, fg_color='transparent')
        row.pack(fill='x', padx=10, pady=(0, 5))
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
                variant='ghost', height=42
            )
            try:
                btn.configure(
                    border_color=accent if active else BORDER,
                    fg_color=theme_color('#102840') if active else 'transparent',
                    text_color=TEXT if active else TEXT2,
                )
                if running or active:
                    btn.configure(state='disabled')
            except Exception:
                pass
            btn.grid(row=0, column=col, sticky='ew', padx=4)

        secondary = ctk.CTkFrame(mode_body, fg_color='transparent')
        secondary.pack(fill='x', padx=13, pady=(0, 8))
        ctk.CTkLabel(
            secondary, text='El plan seleccionado queda activo en Windows hasta que tú lo cambies.',
            font=(FONT, 8), text_color=MUTED, anchor='w'
        ).pack(side='left', fill='x', expand=True)
        saver_active = requested_mode == 'POWER_SAVER'
        saver = self._button(
            secondary,
            ('✓ ' if saver_active else '') + 'Ahorro de energía',
            lambda: self._apply_performance_mode('POWER_SAVER'),
            variant='primary' if saver_active else 'ghost', height=26
        )
        if running or saver_active:
            try: saver.configure(state='disabled')
            except Exception: pass
        saver.pack(side='right')

        # V289 — Game Boost mantiene la fusión con sesión, pero ahora muestra
        # recursos en tarjetas cuadradas y la carátula real del juego detectado.
        cpu_usage = _num(live.get('cpu_usage'))
        cpu_temp = _num(live.get('cpu_temp'))
        gpu_usage = _num(live.get('gpu_usage'))
        gpu_temp = _num(live.get('gpu_temp'))
        ram_used = _num(live.get('ram_used_gb'))
        ram_total = _num(live.get('ram_total_gb'))
        ram_usage = _num(live.get('ram_usage'))
        fps_value = _num(live.get('fps'))

        cpu_value = (
            f"{_fmt(cpu_temp, ' °C', 0)} · {_fmt(cpu_usage, '%', 0)}"
            if cpu_temp is not None or cpu_usage is not None else 'N/A'
        )
        gpu_value = (
            f"{_fmt(gpu_temp, ' °C', 0)} · {_fmt(gpu_usage, '%', 0)}"
            if gpu_temp is not None or gpu_usage is not None else 'N/A'
        )
        if ram_used is not None and ram_total is not None:
            ram_value = f'{ram_used:.1f} / {ram_total:.1f} GB'
        elif ram_usage is not None:
            ram_value = f'{ram_usage:.0f}%'
        else:
            ram_value = 'N/A'
        fps_text = f'{fps_value:.0f} FPS' if fps_value is not None and game_active else 'FPS N/A'

        if boost_active:
            boost_status = 'ACTIVO'
            boost_tone = GREEN
        elif game_active and requested_mode in ('HIGH_PERFORMANCE', 'MAXIMUM_PERFORMANCE'):
            boost_status = 'PREPARADO'
            boost_tone = AMBER
        else:
            boost_status = 'EN ESPERA'
            boost_tone = MUTED

        boost_card = ctk.CTkFrame(
            self.body, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=15
        )
        boost_card.pack(fill='x', padx=8, pady=(0, 10))

        boost_accent = ctk.CTkFrame(
            boost_card, width=4,
            fg_color=GREEN if boost_active else AMBER if game_active else MUTED,
            corner_radius=14
        )
        boost_accent.pack(side='left', fill='y', padx=(1, 0), pady=1)

        outer = ctk.CTkFrame(boost_card, fg_color='transparent')
        outer.pack(side='left', fill='both', expand=True, padx=18, pady=16)

        boost_head = ctk.CTkFrame(outer, fg_color='transparent')
        boost_head.pack(fill='x', pady=(0, 10))
        ctk.CTkLabel(
            boost_head, text='GAME BOOST', font=(FONT, 12, 'bold'),
            text_color=TEXT, anchor='w'
        ).pack(side='left')
        ctk.CTkLabel(
            boost_head, text=boost_status, font=(FONT, 9, 'bold'),
            text_color=boost_tone, anchor='w'
        ).pack(side='left', padx=(8, 0))
        ctk.CTkButton(
            boost_head, text='⚙', width=30, height=28, corner_radius=8,
            fg_color='transparent', hover_color=theme_color('#102840'),
            border_width=1, border_color=BORDER, text_color=TEXT2,
            font=('Segoe UI Symbol', 11, 'bold'),
            command=lambda: self._select_performance_section('boost')
        ).pack(side='right')

        content = ctk.CTkFrame(outer, fg_color='transparent')
        content.pack(fill='x', expand=True)
        content.grid_columnconfigure(0, weight=0, minsize=392)
        content.grid_columnconfigure(1, weight=1)

        metrics_side = ctk.CTkFrame(content, fg_color='transparent', width=376, height=92)
        metrics_side.grid(row=0, column=0, sticky='nw', padx=(0, 16), pady=(2, 0))
        metrics_side.grid_propagate(False)
        ctk.CTkLabel(
            metrics_side, text='RECURSOS', font=(FONT, 8, 'bold'),
            text_color=MUTED, anchor='w'
        ).pack(fill='x', pady=(0, 8))

        metric_row = ctk.CTkFrame(metrics_side, fg_color='transparent', width=376, height=72)
        metric_row.pack(anchor='w')
        metric_row.pack_propagate(False)

        for idx, (label, value, color) in enumerate((
            ('CPU', cpu_value, CYAN if cpu_value != 'N/A' else MUTED),
            ('GPU', gpu_value, PURPLE if gpu_value != 'N/A' else MUTED),
            ('RAM', ram_value, GREEN if ram_value != 'N/A' else MUTED),
        )):
            metric = ctk.CTkFrame(
                metric_row, width=118, height=72, fg_color=theme_color('#0b1828'),
                border_width=1, border_color=theme_color('#1c3b56'), corner_radius=11
            )
            metric.pack(side='left', padx=(0 if idx == 0 else 8, 0))
            metric.pack_propagate(False)

            accent = ctk.CTkFrame(
                metric, width=4, fg_color=color if value != 'N/A' else theme_color('#31465f'),
                corner_radius=999
            )
            accent.pack(side='left', fill='y', padx=(1, 8), pady=7)

            body = ctk.CTkFrame(metric, fg_color='transparent')
            body.pack(side='left', fill='both', expand=True, padx=(0, 8), pady=8)
            ctk.CTkLabel(
                body, text=label, font=(FONT, 9, 'bold'), text_color=MUTED, anchor='w'
            ).pack(fill='x')
            ctk.CTkLabel(
                body, text=value, font=(FONT, 11, 'bold'), text_color=color,
                anchor='w', justify='left'
            ).pack(fill='x', pady=(6, 0))

        game_box = ctk.CTkFrame(
            content, fg_color=theme_color('#0a1726'), border_width=1,
            border_color=theme_color('#203b59'), corner_radius=14, height=196
        )
        game_box.grid(row=0, column=1, sticky='nsew')
        game_box.grid_propagate(False)
        game_box.grid_columnconfigure(1, weight=1)

        art_wrap = ctk.CTkFrame(game_box, fg_color='transparent', width=238)
        art_wrap.grid(row=0, column=0, sticky='nsw', padx=(18, 12), pady=18)
        art_wrap.grid_propagate(False)

        artwork = None
        if game_active and active_game:
            try:
                artwork, _art_source, _art_path = self._game_artwork_for(active_game, size=(220, 124))
            except Exception:
                artwork = None

        if artwork is not None:
            art_label = ctk.CTkLabel(art_wrap, text='', image=artwork, width=220, height=124)
            art_label.pack(anchor='w')
        else:
            art_fallback = ctk.CTkFrame(
                art_wrap, width=220, height=124, fg_color=theme_color('#0d2130'),
                border_width=1, border_color=theme_color('#1d5278'), corner_radius=12
            )
            art_fallback.pack(anchor='w')
            art_fallback.pack_propagate(False)
            ctk.CTkLabel(
                art_fallback, text='🎮', font=('Segoe UI Emoji', 32), text_color=CYAN
            ).pack(expand=True, fill='both')

        game_info = ctk.CTkFrame(game_box, fg_color='transparent')
        game_info.grid(row=0, column=1, sticky='nsew', pady=18)
        ctk.CTkLabel(
            game_info, text='JUEGO ACTUAL', font=(FONT, 8, 'bold'),
            text_color=CYAN if game_active else MUTED, anchor='w'
        ).pack(fill='x')
        current_game_font = (FONT, 18 if game_active else 14, 'bold')
        current_game_wrap = 340 if game_active else 260
        ctk.CTkLabel(
            game_info, text=game_name, font=current_game_font,
            text_color=TEXT if game_active else TEXT2, anchor='w', justify='left',
            wraplength=current_game_wrap
        ).pack(fill='x', pady=(6, 3))
        status_detail = (
            'Sesión detectada · Game Boost listo para aplicar acciones habilitadas'
            if game_active else
            'Esperando un juego compatible para iniciar la sesión'
        )
        ctk.CTkLabel(
            game_info, text=status_detail, font=(FONT, 9), text_color=MUTED,
            anchor='w', justify='left', wraplength=300
        ).pack(fill='x')

        fps_box = ctk.CTkFrame(game_box, fg_color='transparent')
        fps_box.grid(row=0, column=2, sticky='nse', padx=(10, 18), pady=18)
        ctk.CTkLabel(
            fps_box, text='FPS', font=(FONT, 8, 'bold'), text_color=MUTED
        ).pack(anchor='e')
        ctk.CTkLabel(
            fps_box, text=fps_text, font=(FONT, 13, 'bold'),
            text_color=GREEN if fps_value is not None and game_active else MUTED
        ).pack(anchor='e', pady=(5, 0))

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
        shell = ctk.CTkFrame(self.body, fg_color='transparent')
        shell.pack(fill='x', padx=8, pady=(3, 10))
        for idx in range(4):
            shell.grid_columnconfigure(idx, weight=1, uniform='gaming_section_nav')

        specs = (
            ('home', 'Inicio', 'Perfil, Game Boost y estado actual', f'{_profile_label(status.get("requested_mode"))}', CYAN),
            ('library', 'Biblioteca', 'Juegos registrados y portada', f'{len(registered)} juego' + ('' if len(registered) == 1 else 's'), GREEN),
            ('stability', 'Estabilidad', 'Throttling y evidencia térmica', _state_label(throttle_state), throttle_color),
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
        if key not in ('home', 'library', 'stability', 'boost'):
            key = 'home'
        self._performance_section = key
        self._render()

    def _render_gaming_home_shortcuts(self):
        card = self._card(); card.pack(fill='x', padx=8, pady=(2, 10))
        ctk.CTkLabel(card, text='Accesos rápidos', font=(FONT, 12, 'bold'), text_color=TEXT).pack(anchor='w', padx=14, pady=(11, 2))
        ctk.CTkLabel(
            card,
            text='La portada Gaming concentra sólo el control principal. Biblioteca y estabilidad quedan en vistas dedicadas para evitar sobrecarga visual.',
            font=(FONT, 9), text_color=MUTED, anchor='w', justify='left', wraplength=1040
        ).pack(fill='x', padx=14, pady=(0, 8))
        row = ctk.CTkFrame(card, fg_color='transparent')
        row.pack(fill='x', padx=10, pady=(0, 10))
        for idx, (title, detail, _accent, key) in enumerate((
            ('Biblioteca', 'Gestiona juegos detectados y manuales.', GREEN, 'library'),
            ('Estabilidad', 'Revisa evidencia de throttling sin mezclarla con la biblioteca.', AMBER, 'stability'),
        )):
            row.grid_columnconfigure(idx, weight=1, uniform='gaming_home_shortcuts')
            box = ctk.CTkFrame(row, fg_color=CARD2, border_width=1, border_color=BORDER, corner_radius=9)
            box.grid(row=0, column=idx, sticky='nsew', padx=4, pady=4)
            ctk.CTkLabel(box, text=title, font=(FONT, 10, 'bold'), text_color=TEXT, anchor='w').pack(fill='x', padx=10, pady=(9, 2))
            ctk.CTkLabel(box, text=detail, font=(FONT, 8), text_color=MUTED, anchor='w', justify='left', wraplength=250).pack(fill='x', padx=10, pady=(0, 8))
            self._button(box, 'Abrir', lambda k=key: self._select_performance_section(k), variant='ghost', height=28).pack(fill='x', padx=9, pady=(0, 9))

    def _render_gaming_stability_section(self):
        """Vista compacta de estabilidad Gaming: estado actual + evidencia térmica."""
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


    def _benchmark_profile_label(self):
        return gpu_profile_info('standard').get('label') or 'DirectX 11'

    @staticmethod
    def _benchmark_profile_key_from_label(label):
        raw = str(label or '').strip().casefold()
        if raw.startswith('ráp') or raw.startswith('rap'):
            return 'quick'
        if raw.startswith('ext') or raw.startswith('int'):
            return 'extended'
        return 'standard'

    def _benchmark_selected_components(self):
        return [
            key for key in ('gpu', 'cpu', 'ram', 'ssd')
            if bool((self._benchmark_component_flags or {}).get(key))
        ]

    def _benchmark_estimated_text(self):
        selected = self._benchmark_selected_components()
        if not selected:
            return 'Selecciona al menos un componente'
        visual = gpu_profile_info('standard')
        classic = benchmark_profile_info('standard')
        seconds = 0.0
        if 'gpu' in selected:
            seconds += float(visual.get('seconds') or 0)
        if 'cpu' in selected:
            seconds += float(classic.get('cpu_seconds') or 0)
        if 'ram' in selected:
            seconds += float(classic.get('ram_seconds') or 0)
        if 'ssd' in selected:
            # SSD depende del propio disco; mostramos una banda conservadora.
            seconds += max(4.0, float(classic.get('ssd_size_mb') or 0) / 100.0)
        labels = {'gpu':'GPU 3D', 'cpu':'CPU', 'ram':'RAM', 'ssd':'SSD'}
        items = ' → '.join(labels[k] for k in selected)
        lo = max(1, int(seconds * 0.85))
        hi = max(lo + 2, int(seconds * 1.35) + 1)
        return f"{self._benchmark_profile_label()} · {items} · aprox. {lo}–{hi} s"

    def _refresh_benchmark_configuration_ui(self):
        text = self._benchmark_estimated_text()
        try:
            if self._benchmark_selection_label is not None and self._benchmark_selection_label.winfo_exists():
                self._benchmark_selection_label.configure(text=text)
        except Exception:
            pass
        selected = bool(self._benchmark_selected_components())
        running = 'visual_benchmark' in self._jobs
        try:
            if self._benchmark_start_button is not None and self._benchmark_start_button.winfo_exists():
                self._benchmark_start_button.configure(
                    state='normal' if selected and not running else 'disabled',
                    text='BENCHMARK EN EJECUCIÓN…' if running else 'INICIAR BENCHMARK',
                )
        except Exception:
            pass

    def _set_all_benchmark_components(self, enabled):
        if 'visual_benchmark' in self._jobs:
            return
        value = bool(enabled)
        for key in ('gpu', 'cpu', 'ram', 'ssd'):
            self._benchmark_component_flags[key] = value
            var = (getattr(self, '_benchmark_component_vars', {}) or {}).get(key)
            if var is not None:
                try:
                    var.set(value)
                except Exception:
                    pass
        self._refresh_benchmark_configuration_ui()

    def _on_benchmark_profile_change(self, label):
        if 'visual_benchmark' in self._jobs:
            return
        self._benchmark_profile_key = 'standard'
        self._refresh_benchmark_configuration_ui()

    def _on_benchmark_component_change(self, key, variable):
        if 'visual_benchmark' in self._jobs:
            return
        try:
            self._benchmark_component_flags[str(key)] = bool(variable.get())
        except Exception:
            pass
        self._refresh_benchmark_configuration_ui()

    def _set_benchmark_setup_collapsed(self, collapsed):
        """Compacta por completo la configuración después de una ejecución.

        V187 ocultaba sólo la selección de componentes, dejando el gran bloque
        Ejecutar encima del dashboard. V190 mantiene ambos ocultos y usa las acciones
        compactas del Resumen (Repetir / Cambiar componentes), reduciendo scroll
        y evitando atravesar widgets pesados al revisar resultados.
        """
        self._benchmark_setup_collapsed = bool(collapsed)
        component = getattr(self, '_benchmark_component_shell', None)
        action = getattr(self, '_benchmark_action_shell', None)
        result_shell = getattr(self, '_visual_benchmark_card_shell', None)
        hint = getattr(self, '_benchmark_hint_shell', None)

        def exists(widget):
            try: return widget is not None and bool(widget.winfo_exists())
            except Exception: return False

        try:
            if self._benchmark_setup_collapsed:
                if exists(component): component.pack_forget()
                if exists(action): action.pack_forget()
            else:
                before = result_shell if exists(result_shell) else None
                if exists(action):
                    kwargs = dict(fill='x', padx=12, pady=(0, 10))
                    if before is not None: kwargs['before'] = before
                    action.pack(**kwargs)
                if exists(component):
                    kwargs = dict(fill='x', padx=12, pady=(0, 9))
                    if exists(action): kwargs['before'] = action
                    elif before is not None: kwargs['before'] = before
                    component.pack(**kwargs)
        except Exception:
            pass
        try:
            if exists(hint):
                hint.pack_forget()
        except Exception:
            pass
        try:
            title = getattr(self, '_benchmark_intro_title', None)
            subtitle = getattr(self, '_benchmark_intro_subtitle', None)
            if exists(title):
                title.configure(text='Resultado de esta ejecución' if self._benchmark_setup_collapsed else 'Configurar benchmark')
            if exists(subtitle):
                subtitle.configure(text=(
                    'Resumen primero. Abre GPU 3D, Sistema o Evidencia sólo cuando necesites más detalle.'
                    if self._benchmark_setup_collapsed else
                    'Elige qué medir. CorePulse usa cargas reales y deja N/A cuando una métrica no está disponible.'
                ))
        except Exception:
            pass
        try:
            self.scroll._schedule_geometry(0)
        except Exception:
            pass

    def _show_benchmark_scroll_surface(self):
        """Muestra configuración/progreso y oculta el dashboard estático V192."""
        static = getattr(self, '_benchmark_static_results', None)
        try:
            if static is not None and static.winfo_exists():
                static.pack_forget()
        except Exception:
            pass
        try:
            if self.scroll is not None and self.scroll.winfo_exists() and not self.scroll.winfo_ismapped():
                self.scroll.pack(
                    fill='both', expand=True,
                    padx=15 if not self._performance_only else 0,
                    pady=(0, 10)
                )
        except Exception:
            pass
        self._benchmark_results_static_active = False

    def _show_static_benchmark_results(self):
        """Publica resultados fuera del viewport móvil para evitar ghosting CTk."""
        result = self._visual_bench if isinstance(self._visual_bench, dict) else None
        static = getattr(self, '_benchmark_static_results', None)
        if not result or static is None:
            return False
        try:
            if not static.winfo_exists():
                return False
            for child in list(static.winfo_children()):
                child.destroy()

            # V193: construimos el dashboard mientras la superficie de progreso
            # sigue visible. Sólo hacemos el swap cuando el árbol está listo,
            # evitando el intervalo vacío observado entre 100 % y Resultados.
            host = ctk.CTkFrame(static, fg_color='transparent')
            host.pack(fill='both', expand=True, padx=0, pady=(5, 4))
            self._visual_benchmark_result_host = host
            self._benchmark_result_pages = {}
            self._benchmark_result_page_scrolls = {}
            self._benchmark_result_pages_host = None
            self._build_static_benchmark_result_pages(host, result)
            static.update_idletasks()
            self.scroll.pack_forget()
            static.pack(fill='both', expand=True, padx=0, pady=(0, 10))
            self._benchmark_results_static_active = True
            static.update_idletasks()
            return True
        except Exception:
            logger.exception('[BENCHMARK] No se pudo publicar dashboard estático V192')
            self._show_benchmark_scroll_surface()
            return False

    def _show_benchmark_setup(self):
        self._show_benchmark_scroll_surface()
        self._set_benchmark_setup_collapsed(False)
        try:
            self.scroll.yview_moveto(0.0)
        except Exception:
            pass

    def _render_gaming_benchmark_section(self):
        """Benchmark completo: primero se configura y luego se ejecuta carga real."""
        bench = self._card()
        bench.pack(fill='x', padx=8, pady=(3, 7))

        head = ctk.CTkFrame(bench, fg_color='transparent')
        head.pack(fill='x', padx=14, pady=(10, 5))
        info = ctk.CTkFrame(head, fg_color='transparent')
        info.pack(side='left', fill='x', expand=True)
        self._benchmark_intro_title = ctk.CTkLabel(
            info,
            text='Resultado de esta ejecución' if self._benchmark_setup_collapsed else 'Configurar benchmark',
            font=(FONT, BENCH_FONT_TITLE, 'bold'), text_color=TEXT, anchor='w'
        )
        self._benchmark_intro_title.pack(anchor='w')
        self._benchmark_intro_subtitle = ctk.CTkLabel(
            info,
            text=(
                'Resumen primero. Abre GPU 3D, Sistema o Evidencia sólo cuando necesites más detalle.'
                if self._benchmark_setup_collapsed else
                'Elige qué medir. CorePulse usa cargas reales y deja N/A cuando una métrica no está disponible.'
            ),
            font=(FONT, BENCH_FONT_BODY), text_color=MUTED, anchor='w', justify='left', wraplength=930,
        )
        self._benchmark_intro_subtitle.pack(anchor='w', pady=(2, 0))

        # Un único protocolo público de benchmark, con metodología estándar.
        self._benchmark_profile_key = 'standard'

        # Paso 2: componentes. Cada interruptor controla una carga real distinta.
        comp_shell = ctk.CTkFrame(bench, fg_color=CARD2, border_width=1, border_color=BENCH_BORDER, corner_radius=BENCH_RADIUS_CARD)
        self._benchmark_component_shell = comp_shell
        if not self._benchmark_setup_collapsed:
            comp_shell.pack(fill='x', padx=12, pady=(0, 6))
        comp_head = ctk.CTkFrame(comp_shell, fg_color='transparent')
        comp_head.pack(fill='x', padx=12, pady=(7, 1))
        ctk.CTkLabel(comp_head, text='1 · Qué medir', font=(FONT, BENCH_FONT_SECTION, 'bold'), text_color=TEXT2, anchor='w').pack(side='left')
        quick = ctk.CTkFrame(comp_head, fg_color='transparent')
        quick.pack(side='right')
        self._button(quick, 'Todos', lambda: self._set_all_benchmark_components(True), variant='ghost', height=26).pack(side='left', padx=(0, 5))
        self._button(quick, 'Ninguno', lambda: self._set_all_benchmark_components(False), variant='ghost', height=26).pack(side='left')
        ctk.CTkLabel(
            comp_shell,
            text='Puedes ejecutar sólo una prueba o combinarlas. Nada empieza hasta que pulses “Iniciar benchmark”.',
            font=(FONT, BENCH_FONT_META), text_color=MUTED, anchor='w', justify='left'
        ).pack(fill='x', padx=12, pady=(0, 4))
        grid = ctk.CTkFrame(comp_shell, fg_color='transparent')
        grid.pack(fill='x', padx=8, pady=(0, 6))
        descriptions = {
            'gpu': ('GPU', 'DirectX 11: Valle / Bosque / Lago / Extreme · 49 s medidos + preparación.', BENCH_ACCENT),
            'cpu': ('CPU', 'Rendimiento SHA-256: 1 hilo + multinúcleo.', CYAN),
            'ram': ('RAM', 'Copia continua de bloques grandes de memoria.', GREEN),
            'ssd': ('SSD', 'Escritura + flush + lectura secuencial de archivo temporal.', AMBER),
        }
        self._benchmark_component_vars = {}
        for index, key in enumerate(('gpu', 'cpu', 'ram', 'ssd')):
            row, col = divmod(index, 2)
            grid.grid_columnconfigure(col, weight=1, uniform='benchmark_components')
            title, description, accent = descriptions[key]
            cell = ctk.CTkFrame(grid, fg_color=BENCH_SURFACE_SOFT, border_width=1, border_color=BENCH_BORDER, corner_radius=BENCH_RADIUS_CARD)
            cell.grid(row=row, column=col, sticky='nsew', padx=4, pady=4)
            ctk.CTkFrame(cell, height=2, fg_color=accent, corner_radius=2).pack(fill='x', padx=10, pady=(6, 2))
            var = ctk.BooleanVar(value=bool(self._benchmark_component_flags.get(key, True)))
            self._benchmark_component_vars[key] = var
            sw = ctk.CTkSwitch(
                cell, text=title, variable=var,
                command=lambda k=key, v=var: self._on_benchmark_component_change(k, v),
                progress_color=BENCH_ACCENT, button_color=TEXT, button_hover_color=TEXT2,
                text_color=TEXT, font=(FONT, BENCH_FONT_SECTION, 'bold')
            )
            sw.pack(anchor='w', padx=10, pady=(2, 1))
            if 'visual_benchmark' in self._jobs:
                try: sw.configure(state='disabled')
                except Exception: pass
            ctk.CTkLabel(cell, text=description, font=(FONT, BENCH_FONT_META), text_color=MUTED, anchor='w', justify='left', wraplength=430).pack(fill='x', padx=10, pady=(0, 5))

        # Paso 3: resumen + ejecución prominente.
        action = ctk.CTkFrame(bench, fg_color=BENCH_SURFACE_RAISED, border_width=1, border_color=BENCH_ACCENT_BORDER, corner_radius=BENCH_RADIUS_CARD)
        self._benchmark_action_shell = action
        if not self._benchmark_setup_collapsed:
            action.pack(fill='x', padx=12, pady=(0, 6))
        left = ctk.CTkFrame(action, fg_color='transparent')
        left.pack(side='left', fill='x', expand=True, padx=12, pady=7)
        ctk.CTkLabel(left, text='2 · Ejecutar', font=(FONT, BENCH_FONT_SECTION, 'bold'), text_color=TEXT).pack(anchor='w')
        self._benchmark_selection_label = ctk.CTkLabel(left, text=self._benchmark_estimated_text(), font=(FONT, BENCH_FONT_META, 'bold'), text_color=BENCH_ACCENT_TEXT, anchor='w')
        self._benchmark_selection_label.pack(anchor='w', pady=(2, 0))
        self._benchmark_start_button = ctk.CTkButton(
            action,
            text='INICIAR BENCHMARK' if 'visual_benchmark' not in self._jobs else 'BENCHMARK EN EJECUCIÓN…',
            command=self._run_visual_benchmark,
            width=220, height=44, corner_radius=BENCH_RADIUS_CONTROL,
            fg_color=BENCH_ACCENT, hover_color=BENCH_ACCENT_HOVER,
            border_width=1, border_color=BENCH_ACCENT_BORDER,
            text_color='#ffffff', font=(FONT, BENCH_FONT_BODY, 'bold')
        )
        self._benchmark_start_button.pack(side='right', padx=12, pady=7)
        self._refresh_benchmark_configuration_ui()

        self._render_visual_benchmark_card(bench)

        # V191: la propia configuración y el Estado de la prueba ya explican el
        # flujo. No creamos una tarjeta de ayuda redundante: reduce altura, evita
        # scroll innecesario en 1280x800 y limita repintados de widgets.
        self._benchmark_hint_shell = None

    def _format_visual_metric(self, value, suffix='', digits=1):
        try:
            if value is None:
                return 'N/A'
            return f"{float(value):.{int(digits)}f}{suffix}"
        except Exception:
            return 'N/A'

    def _set_visual_benchmark_progress(self, fraction, stage, detail=''):
        try:
            self._visual_benchmark_progress = max(0.0, min(1.0, float(fraction)))
        except Exception:
            self._visual_benchmark_progress = 0.0
        self._visual_benchmark_stage = str(stage or 'Benchmark visual 3D')
        self._visual_benchmark_detail = str(detail or '')
        try:
            if self.visual_bench_progress_bar is not None and self.visual_bench_progress_bar.winfo_exists():
                self.visual_bench_progress_bar.set(self._visual_benchmark_progress)
        except Exception:
            pass
        try:
            if self.lbl_visual_bench_progress is not None and self.lbl_visual_bench_progress.winfo_exists():
                self.lbl_visual_bench_progress.configure(
                    text=f"{int(self._visual_benchmark_progress * 100)}% · {self._visual_benchmark_stage}",
                    text_color=BENCH_ACCENT_TEXT,
                )
        except Exception:
            pass
        try:
            if self.lbl_visual_bench_detail is not None and self.lbl_visual_bench_detail.winfo_exists():
                self.lbl_visual_bench_detail.configure(text=self._visual_benchmark_detail)
        except Exception:
            pass
        try:
            status = getattr(self, 'lbl_visual_bench_status', None)
            if status is not None and status.winfo_exists() and self._visual_benchmark_progress < 1.0:
                status.configure(text='EN EJECUCIÓN', text_color=BENCH_ACCENT_TEXT)
        except Exception:
            pass

    def _benchmark_hud_overlay(self):
        if self._benchmark_hud is None:
            try:
                self._benchmark_hud = _BenchmarkHudOverlay(self.app)
            except Exception:
                self._benchmark_hud = None
        return self._benchmark_hud

    def _hide_benchmark_hud(self):
        hud = getattr(self, '_benchmark_hud', None)
        if hud is not None:
            try: hud.hide()
            except Exception: pass

    def _accept_visual_benchmark_progress(self, run_id, fraction, stage, detail):
        # Los callbacks encolados no pueden sobrescribir el cierre ni otra ejecución.
        if (not self._alive or run_id != getattr(self, '_visual_benchmark_run_id', None)
                or getattr(self, '_visual_benchmark_finished', False)):
            return
        self._set_visual_benchmark_progress(fraction, stage, detail)
        # HUD V190: usa únicamente FPS real ya calculado por DirectX. Vive fuera
        # del swap-chain y de la región cronometrada; si aún no hay FPS, muestra N/A.
        if str(stage or '').startswith('GPU ·'):
            hud = self._benchmark_hud_overlay()
            if hud is not None:
                try: hud.update(stage, detail)
                except Exception: pass
        else:
            # La suite emite primero "Preparando benchmark…" antes de crear
            # DirectX. Si GPU es el primer componente mantenemos sólo el cursor
            # oculto hasta que llegue el primer callback GPU; no mostramos HUD.
            preparing_gpu = (
                str(stage or '').casefold().startswith('preparando benchmark')
                and bool(self._benchmark_selected_components())
                and self._benchmark_selected_components()[0] == 'gpu'
            )
            if not preparing_gpu:
                self._hide_benchmark_hud()

    @staticmethod
    def _benchmark_gpu_matches_target(target_name, renderer):
        """Compara adaptadores sin depender de fabricante/modelo hardcodeado."""
        import re
        expected = str(target_name or '').casefold()
        actual = str(renderer or '').casefold()
        if not expected or not actual:
            return None
        stop = {'nvidia','geforce','amd','radeon','intel','graphics','graphic','gpu','laptop','mobile','series','corporation','inc','microsoft','render','renderer'}
        expected_tokens = [t for t in re.findall(r'[a-z0-9]+', expected) if len(t) >= 3 and t not in stop]
        actual_tokens = set(re.findall(r'[a-z0-9]+', actual))
        strong = [t for t in expected_tokens if any(ch.isdigit() for ch in t)]
        if strong:
            return any(t in actual_tokens for t in strong)
        if expected_tokens:
            return any(t in actual_tokens for t in expected_tokens)
        return None

    def _render_visual_benchmark_card(self, parent):
        # El porcentaje visible también es autoridad de estado. Así nunca puede
        # aparecer "LISTO" mientras una ejecución ya va, por ejemplo, en 97 %.
        accent_text = globals().get('BENCH_ACCENT_TEXT', PURPLE)
        bench_meta = globals().get('BENCH_FONT_META', 8)
        bench_micro = globals().get('BENCH_FONT_MICRO', 7)
        bench_section = globals().get('BENCH_FONT_SECTION', 11)
        bench_accent = globals().get('BENCH_ACCENT', PURPLE)
        bench_border = globals().get('BENCH_ACCENT_BORDER', theme_color('#2f7ba5'))
        bench_radius = globals().get('BENCH_RADIUS_CARD', 10)
        progress = float(getattr(self, '_visual_benchmark_progress', 0.0) or 0.0)
        run_id = int(getattr(self, '_visual_benchmark_run_id', 0) or 0)
        progress_active = (self._visual_bench is None and run_id > 0 and 0.0 < progress < 1.0)
        running = 'visual_benchmark' in self._jobs or progress_active
        shell = ctk.CTkFrame(parent, fg_color=theme_color('#091827'), border_width=1, border_color=bench_border, corner_radius=bench_radius)
        self._visual_benchmark_card_shell = shell
        shell.pack(fill='x', padx=12, pady=(0, 10))

        head = ctk.CTkFrame(shell, fg_color='transparent')
        head.pack(fill='x', padx=12, pady=(10, 5))
        ctk.CTkLabel(head, text='Estado de la prueba', font=(FONT, bench_section, 'bold'), text_color=accent_text, anchor='w').pack(side='left')
        status_text = 'EN EJECUCIÓN' if running else ('ÚLTIMO RESULTADO' if self._visual_bench else 'LISTO')
        status_color = accent_text if running else (GREEN if self._visual_bench else TEXT2)
        self.lbl_visual_bench_status = ctk.CTkLabel(head, text=status_text, font=(FONT, bench_meta, 'bold'), text_color=status_color)
        self.lbl_visual_bench_status.pack(side='right')

        completed = bool(self._visual_bench) and not running
        self.lbl_visual_bench_progress = None
        self.visual_bench_progress_bar = None
        self.lbl_visual_bench_detail = None
        self._visual_benchmark_progress_row = None
        self._visual_benchmark_completed_label = None
        if completed:
            compact = ctk.CTkLabel(
                shell, text='100% · Benchmark finalizado · abre una vista para profundizar',
                font=(FONT, bench_meta), text_color=TEXT2, anchor='w'
            )
            compact.pack(fill='x', padx=12, pady=(0, 8))
            self._visual_benchmark_completed_label = compact
        else:
            progress_row = ctk.CTkFrame(shell, fg_color='transparent')
            self._visual_benchmark_progress_row = progress_row
            progress_row.pack(fill='x', padx=12, pady=(0, 4))
            self.lbl_visual_bench_progress = ctk.CTkLabel(
                progress_row,
                text=(f"{int(self._visual_benchmark_progress * 100)}% · {self._visual_benchmark_stage}" if running else 'Configura arriba y pulsa INICIAR BENCHMARK'),
                font=(FONT, bench_meta, 'bold'), text_color=accent_text if running else TEXT2, anchor='w'
            )
            self.lbl_visual_bench_progress.pack(side='left', fill='x', expand=True)
            ctk.CTkLabel(progress_row, text='Protección térmica real activa', font=(FONT, bench_micro), text_color=MUTED).pack(side='right')

            self.visual_bench_progress_bar = ctk.CTkProgressBar(
                shell, height=7, corner_radius=999, progress_color=bench_accent,
                fg_color=theme_color('#132741')
            )
            self.visual_bench_progress_bar.pack(fill='x', padx=12, pady=(0, 5))
            self.visual_bench_progress_bar.set(self._visual_benchmark_progress if running else 0.0)
            self.lbl_visual_bench_detail = ctk.CTkLabel(
                shell,
                text=(self._visual_benchmark_detail if running else 'Los resultados sólo aparecen cuando una carga terminó y fue medida.'),
                font=(FONT, bench_meta), text_color=MUTED, anchor='w', justify='left', wraplength=1040
            )
            self.lbl_visual_bench_detail.pack(fill='x', padx=12, pady=(0, 9))

        self._visual_benchmark_result_host = ctk.CTkFrame(shell, fg_color='transparent')
        self._visual_benchmark_result_host.pack(fill='x')
        result = self._visual_bench if isinstance(self._visual_bench, dict) else None
        if result:
            self._render_visual_benchmark_result_body(self._visual_benchmark_result_host, result)

    def _compact_completed_visual_benchmark_chrome(self):
        """Convierte el estado EN EJECUCIÓN en cabecera compacta sin full-render.

        El resultado se publica de forma atómica en su host existente; por eso
        esta rutina sólo oculta los widgets de progreso ya creados y añade una
        línea final antes del dashboard. Evita el salto/blanco que aparecería al
        reconstruir toda la página al 100 %.
        """
        for widget in (
            getattr(self, '_visual_benchmark_progress_row', None),
            getattr(self, 'visual_bench_progress_bar', None),
            getattr(self, 'lbl_visual_bench_detail', None),
        ):
            try:
                if widget is not None and widget.winfo_exists():
                    widget.pack_forget()
            except Exception:
                pass
        try:
            status = getattr(self, 'lbl_visual_bench_status', None)
            if status is not None and status.winfo_exists():
                status.configure(text='ÚLTIMO RESULTADO', text_color=GREEN)
        except Exception:
            pass
        label = getattr(self, '_visual_benchmark_completed_label', None)
        try:
            if label is None or not label.winfo_exists():
                shell = getattr(self, '_visual_benchmark_card_shell', None)
                result_host = getattr(self, '_visual_benchmark_result_host', None)
                if shell is not None and shell.winfo_exists():
                    label = ctk.CTkLabel(
                        shell, text='100% · Benchmark finalizado · abre una vista para profundizar',
                        font=(FONT, BENCH_FONT_META), text_color=TEXT2, anchor='w'
                    )
                    kwargs = dict(fill='x', padx=12, pady=(0, 8))
                    if result_host is not None and result_host.winfo_exists():
                        kwargs['before'] = result_host
                    label.pack(**kwargs)
                    self._visual_benchmark_completed_label = label
        except Exception:
            pass

    def _benchmark_result_payload(self, result):
        result = result if isinstance(result, dict) else {}
        selected = list(result.get('selected_components') or [])
        visual = result.get('visual_gpu') if isinstance(result.get('visual_gpu'), dict) else {}
        suite = result.get('system_suite') if isinstance(result.get('system_suite'), dict) else {}
        tele_visual = visual.get('telemetry') if isinstance(visual.get('telemetry'), dict) else {}
        tele_suite = suite.get('telemetry_summary') if isinstance(suite.get('telemetry_summary'), dict) else {}
        return selected, visual, suite, tele_visual, tele_suite

    def _set_benchmark_result_view(self, view):
        view = str(view or 'summary').strip().lower()
        if view not in {'summary', 'gpu', 'system', 'evidence'}:
            view = 'summary'
        if view == getattr(self, '_benchmark_result_view', 'summary'):
            return
        self._benchmark_result_view = view
        # V195: las cuatro páginas estáticas se construyen una sola vez. Cambiar
        # de pestaña sólo eleva la página ya pintada; no destruye ni reconstruye
        # widgets CTk y evita los frames duplicados observados en V194.
        if getattr(self, '_benchmark_results_static_active', False) and getattr(self, '_benchmark_result_pages', None):
            self._show_static_benchmark_result_page(view)
            return
        self._refresh_visual_benchmark_result_in_place()
        try:
            self.app.after_idle(lambda: self.scroll.yview_moveto(0.0) if self._alive else None)
        except Exception:
            pass

    def _render_benchmark_result_nav(self, shell):
        nav = ctk.CTkFrame(shell, fg_color=BENCH_SURFACE, border_width=1, border_color=BENCH_BORDER, corner_radius=BENCH_RADIUS_CARD)
        nav.pack(fill='x', padx=12, pady=(0, 10))
        labels = (
            ('summary', 'Resumen rápido'),
            ('gpu', 'GPU 3D'),
            ('system', 'Sistema'),
            ('evidence', 'Evidencia'),
        )
        active = str(getattr(self, '_benchmark_result_view', 'summary') or 'summary')
        self._benchmark_result_view_buttons = {}
        for idx, (key, label) in enumerate(labels):
            btn = ctk.CTkButton(
                nav, text=label, height=34, corner_radius=BENCH_RADIUS_CONTROL,
                command=lambda k=key: self._set_benchmark_result_view(k),
                fg_color=BENCH_ACCENT_DARK if key == active else 'transparent',
                hover_color=BENCH_ACCENT_HOVER if key == active else theme_color('#102840'),
                border_width=1, border_color=BENCH_ACCENT_BORDER if key == active else BORDER,
                text_color=BENCH_ACCENT_TEXT if key == active else TEXT2,
                font=(FONT, BENCH_FONT_BODY, 'bold'),
            )
            btn.pack(side='left', fill='x', expand=True, padx=(5 if idx == 0 else 3, 5 if idx == len(labels)-1 else 3), pady=6)
            self._benchmark_result_view_buttons[key] = btn

    def _sync_benchmark_result_nav(self):
        active = str(getattr(self, '_benchmark_result_view', 'summary') or 'summary')
        buttons = getattr(self, '_benchmark_result_view_buttons', {}) or {}
        for key, btn in buttons.items():
            try:
                if btn is None or not btn.winfo_exists():
                    continue
                is_active = key == active
                btn.configure(
                    fg_color=BENCH_ACCENT_DARK if is_active else 'transparent',
                    hover_color=BENCH_ACCENT_HOVER if is_active else theme_color('#102840'),
                    border_color=BENCH_ACCENT_BORDER if is_active else BORDER,
                    text_color=BENCH_ACCENT_TEXT if is_active else TEXT2,
                )
            except Exception:
                pass

    def _render_benchmark_page_content(self, page, key, result):
        if key == 'gpu':
            self._render_benchmark_gpu_view(page, result)
        elif key == 'system':
            self._render_benchmark_system_view(page, result)
        elif key == 'evidence':
            self._render_benchmark_evidence_view(page, result)
        else:
            self._render_benchmark_summary_view(page, result)

    def _build_static_benchmark_result_pages(self, shell, result):
        status = str(result.get('status') or '').upper()
        if status in ('ERROR', 'UNAVAILABLE', 'PARTIAL', 'SAFETY_STOP', 'CANCELLED'):
            color = RED if status in ('ERROR', 'SAFETY_STOP') else AMBER
            title = {
                'ERROR':'Benchmark no completado', 'UNAVAILABLE':'Benchmark no disponible',
                'PARTIAL':'Benchmark completado parcialmente', 'SAFETY_STOP':'Detenido por seguridad térmica',
                'CANCELLED':'Benchmark cancelado',
            }.get(status, status)
            ctk.CTkLabel(
                shell, text=f"{title}: {result.get('reason') or 'revisa los resultados por componente'}",
                font=(FONT, BENCH_FONT_BODY, 'bold'), text_color=color, anchor='w',
                justify='left', wraplength=1020
            ).pack(fill='x', padx=12, pady=(0, 8))

        self._render_benchmark_result_nav(shell)
        pages_host = ctk.CTkFrame(shell, fg_color='transparent', corner_radius=0)
        pages_host.pack(fill='both', expand=True)
        pages_host.grid_rowconfigure(0, weight=1)
        pages_host.grid_columnconfigure(0, weight=1)
        pages = {}
        page_scrolls = {}
        for key in ('summary', 'gpu', 'system', 'evidence'):
            page = ctk.CTkFrame(pages_host, fg_color='transparent', corner_radius=0)
            page.grid(row=0, column=0, sticky='nsew')
            # V200: cada pestaña de resultados tiene su propio viewport estable.
            # La barra de navegación queda fija y el contenido puede crecer todo
            # lo necesario sin quedar recortado por la altura de la ventana.
            page_scroll = StableScrollHost(
                page, fg_color=BG, backend='place', wheel_pixels=54,
                scrollbar_button_color=BENCH_ACCENT_BORDER,
                scrollbar_button_hover_color=BENCH_ACCENT_HOVER,
            )
            page_scroll.pack(fill='both', expand=True, padx=(0, 2), pady=(0, 2))
            self._render_benchmark_page_content(page_scroll.content, key, result)
            pages[key] = page
            page_scrolls[key] = page_scroll
        self._benchmark_result_pages_host = pages_host
        self._benchmark_result_pages = pages
        self._benchmark_result_page_scrolls = page_scrolls
        self._benchmark_result_visible_page = None
        self._show_static_benchmark_result_page(getattr(self, '_benchmark_result_view', 'summary'))

    def _show_static_benchmark_result_page(self, key):
        key = str(key or 'summary').lower()
        pages = getattr(self, '_benchmark_result_pages', {}) or {}
        page = pages.get(key) or pages.get('summary')
        if page is None:
            return
        resolved_key = key if key in pages else 'summary'
        previous_key = getattr(self, '_benchmark_result_visible_page', None)
        self._benchmark_result_view = resolved_key
        try:
            page.tkraise()
            page.update_idletasks()
            page_scroll = (getattr(self, '_benchmark_result_page_scrolls', {}) or {}).get(resolved_key)
            if page_scroll is not None and page_scroll.winfo_exists():
                page_scroll._schedule_geometry(0)
                # Cada vista se abre desde el principio. El usuario nunca cae en
                # mitad de una explicación ni en una zona aparentemente vacía.
                if previous_key != resolved_key:
                    page_scroll.yview_moveto(0.0)
        except Exception:
            pass
        self._benchmark_result_visible_page = resolved_key
        self._sync_benchmark_result_nav()

    def _refresh_static_benchmark_page(self, key=None):
        result = self._visual_bench if isinstance(self._visual_bench, dict) else None
        pages = getattr(self, '_benchmark_result_pages', {}) or {}
        host = getattr(self, '_benchmark_result_pages_host', None)
        key = str(key or getattr(self, '_benchmark_result_view', 'summary') or 'summary').lower()
        old = pages.get(key)
        if result is None or host is None or old is None:
            return False
        try:
            staging = ctk.CTkFrame(host, fg_color='transparent', corner_radius=0)
            staging.grid(row=0, column=0, sticky='nsew')
            staging_scroll = StableScrollHost(
                staging, fg_color=BG, backend='place', wheel_pixels=54,
                scrollbar_button_color=BENCH_ACCENT_BORDER,
                scrollbar_button_hover_color=BENCH_ACCENT_HOVER,
            )
            staging_scroll.pack(fill='both', expand=True, padx=(0, 2), pady=(0, 2))
            self._render_benchmark_page_content(staging_scroll.content, key, result)
            staging.update_idletasks()
            staging_scroll._schedule_geometry(0)
            staging_scroll.yview_moveto(0.0)
            staging.tkraise()
            old.destroy()
            pages[key] = staging
            scrolls = getattr(self, '_benchmark_result_page_scrolls', {}) or {}
            scrolls[key] = staging_scroll
            self._benchmark_result_page_scrolls = scrolls
            self._benchmark_result_pages = pages
            self._benchmark_result_visible_page = key
            self._sync_benchmark_result_nav()
            return True
        except Exception:
            logger.exception('[BENCHMARK] No se pudo refrescar la página estática %s', key)
            return False

    @staticmethod
    def _benchmark_reading_tone(tone):
        tone = str(tone or '').lower()
        if tone == 'red':
            return RED, theme_color('#27151b')
        if tone == 'amber':
            return AMBER, theme_color('#241d12')
        if tone == 'green':
            return GREEN, theme_color('#0b211d')
        if tone in {'cyan', 'blue', 'purple'}:
            return BENCH_ACCENT_TEXT, BENCH_ACCENT_DARK
        return MUTED, theme_color('#111b28')

    def _benchmark_reading_box(self, parent, reading, *, compact=False, show_summary=True, padx=10, pady=(2, 8)):
        reading = reading if isinstance(reading, dict) else {}
        label = str(reading.get('label') or 'NO EVALUABLE')
        summary = str(reading.get('summary') or '').strip()
        scope = str(reading.get('scope') or '').strip()
        accent, bg = self._benchmark_reading_tone(reading.get('tone'))
        if compact:
            # La vista principal responde primero "qué pasó". La explicación
            # larga queda para las vistas de detalle, evitando repetir párrafos.
            holder = ctk.CTkFrame(parent, fg_color='transparent')
            holder.pack(fill='x', padx=padx, pady=pady)
            ctk.CTkLabel(
                holder, text=f'CorePulse · {label}',
                font=(FONT, BENCH_FONT_MICRO, 'bold'), text_color=accent, anchor='w'
            ).pack(fill='x')
            short = str(reading.get('short') or '').strip()
            if show_summary and short:
                ctk.CTkLabel(
                    holder, text=short, font=(FONT, BENCH_FONT_MICRO), text_color=TEXT2,
                    anchor='w', justify='left', wraplength=420
                ).pack(fill='x', pady=(1, 0))
            return holder
        box = ctk.CTkFrame(
            parent, fg_color=bg, border_width=1, border_color=accent,
            corner_radius=BENCH_RADIUS_CONTROL
        )
        box.pack(fill='x', padx=padx, pady=pady)
        ctk.CTkLabel(
            box, text=f'Lectura CorePulse · {label}',
            font=(FONT, BENCH_FONT_META, 'bold'), text_color=accent, anchor='w'
        ).pack(fill='x', padx=9, pady=(6, 1))
        if summary:
            ctk.CTkLabel(
                box, text=summary, font=(FONT, BENCH_FONT_META), text_color=TEXT2,
                anchor='w', justify='left', wraplength=930
            ).pack(fill='x', padx=9, pady=(0, 2 if scope else 6))
        if scope:
            ctk.CTkLabel(
                box, text=scope, font=(FONT, BENCH_FONT_MICRO), text_color=MUTED,
                anchor='w', justify='left', wraplength=930
            ).pack(fill='x', padx=9, pady=(0, 6))
        return box

    def _result_component_card(self, parent, *, title, primary, detail, accent, state='MEDIDO', reading=None):
        card = ctk.CTkFrame(
            parent, fg_color=BENCH_SURFACE_SOFT, border_width=1,
            border_color=BENCH_BORDER, corner_radius=BENCH_RADIUS_CARD
        )
        # Remate de color pequeño: identidad del componente sin convertir toda
        # la tarjeta en un bloque saturado.
        ctk.CTkFrame(card, height=3, fg_color=accent, corner_radius=2).pack(
            fill='x', padx=12, pady=(10, 7)
        )
        head = ctk.CTkFrame(card, fg_color='transparent')
        head.pack(fill='x', padx=12, pady=(0, 2))
        ctk.CTkLabel(
            head, text=title, font=(FONT, BENCH_FONT_SECTION, 'bold'),
            text_color=accent, anchor='w'
        ).pack(side='left')
        state_color = MUTED if state == 'N/A' else (RED if state == 'DETENIDO' else AMBER if state == 'PARCIAL' else BENCH_ACCENT_TEXT)
        state_bg = ctk.CTkFrame(
            head, fg_color=theme_color('#0b2430') if state != 'N/A' else theme_color('#111b28'),
            border_width=1, border_color=state_color, corner_radius=999
        )
        state_bg.pack(side='right')
        ctk.CTkLabel(
            state_bg, text=state, font=(FONT, BENCH_FONT_MICRO, 'bold'),
            text_color=state_color
        ).pack(padx=8, pady=2)
        ctk.CTkLabel(
            card, text=primary, font=(FONT, BENCH_FONT_METRIC, 'bold'), text_color=TEXT, anchor='w'
        ).pack(fill='x', padx=12, pady=(2, 1))
        ctk.CTkLabel(
            card, text=detail, font=(FONT, BENCH_FONT_META), text_color=MUTED,
            anchor='w', justify='left', wraplength=440
        ).pack(fill='x', padx=12, pady=(0, 4 if reading else 12))
        if reading:
            self._benchmark_reading_box(card, reading, compact=True, show_summary=False, padx=10, pady=(2, 9))
        return card

    def _render_benchmark_glance_strip(self, shell, entries, *, title='Lectura rápida'):
        entries = [entry for entry in (entries or []) if entry]
        if not entries:
            return
        box = ctk.CTkFrame(
            shell, fg_color=BENCH_SURFACE, border_width=1,
            border_color=BENCH_BORDER, corner_radius=BENCH_RADIUS_CARD
        )
        box.pack(fill='x', padx=12, pady=(0, 8))
        head = ctk.CTkFrame(box, fg_color='transparent')
        head.pack(fill='x', padx=10, pady=(8, 4))
        ctk.CTkLabel(
            head, text=title, font=(FONT, BENCH_FONT_META, 'bold'),
            text_color=BENCH_ACCENT_TEXT, anchor='w'
        ).pack(side='left')
        ctk.CTkLabel(
            head, text='Lo esencial antes de abrir detalle',
            font=(FONT, BENCH_FONT_MICRO), text_color=MUTED, anchor='e'
        ).pack(side='right')
        grid = ctk.CTkFrame(box, fg_color='transparent')
        grid.pack(fill='x', padx=6, pady=(0, 6))
        cols = 2 if len(entries) > 1 else 1
        for col in range(cols):
            grid.grid_columnconfigure(col, weight=1, uniform='benchmark_glance_strip')
        for idx, entry in enumerate(entries[:4]):
            label, value, detail, accent = entry
            card = ctk.CTkFrame(
                grid, fg_color=BENCH_SURFACE_SOFT, border_width=1,
                border_color=BENCH_BORDER, corner_radius=BENCH_RADIUS_CONTROL
            )
            card.grid(row=idx // cols, column=idx % cols, sticky='nsew', padx=4, pady=4)
            ctk.CTkLabel(
                card, text=label, font=(FONT, BENCH_FONT_MICRO, 'bold'),
                text_color=accent, anchor='w'
            ).pack(fill='x', padx=9, pady=(7, 1))
            ctk.CTkLabel(
                card, text=value, font=(FONT, BENCH_FONT_SECTION, 'bold'),
                text_color=TEXT, anchor='w'
            ).pack(fill='x', padx=9, pady=(0, 1))
            ctk.CTkLabel(
                card, text=detail, font=(FONT, BENCH_FONT_MICRO),
                text_color=MUTED, anchor='w', justify='left', wraplength=430
            ).pack(fill='x', padx=9, pady=(0, 7))

    @staticmethod
    def _benchmark_row_state(row):
        row = row if isinstance(row, dict) else {}
        status = str(row.get('status') or '').upper()
        if status in {'ERROR', 'UNAVAILABLE', 'SKIPPED', 'CANCELLED'}:
            return 'N/A'
        if status == 'SAFETY_STOP':
            return 'DETENIDO'
        if status == 'PARTIAL':
            return 'PARCIAL'
        return 'MEDIDO' if row else 'N/A'

    def _render_benchmark_summary_view(self, shell, result):
        selected, visual, suite, tele_visual, tele_suite = self._benchmark_result_payload(result)
        status = str(result.get('status') or '').upper()
        stop_reason = suite.get('safety_stop')
        gpu_temp = ((tele_visual.get('gpu_temp') or {}).get('max') if isinstance(tele_visual.get('gpu_temp'), dict) else None)
        cpu_temp = ((tele_suite.get('cpu_temp') or {}).get('max') if isinstance(tele_suite.get('cpu_temp'), dict) else None)
        cpu_hot = _num(cpu_temp)
        gpu_hot = _num(gpu_temp)
        thermal_high = (cpu_hot is not None and cpu_hot >= 95.0) or (gpu_hot is not None and gpu_hot >= 88.0)
        headline = 'Benchmark completado · temperatura alta' if thermal_high else 'Benchmark completado'
        headline_color = AMBER if thermal_high else GREEN
        if status == 'SAFETY_STOP' or stop_reason:
            headline, headline_color = 'Detenido por seguridad térmica', RED
        elif status in {'ERROR', 'UNAVAILABLE'}:
            headline, headline_color = 'Benchmark no completado', RED
        elif status in {'PARTIAL', 'CANCELLED'}:
            headline, headline_color = 'Benchmark parcial', AMBER

        top = ctk.CTkFrame(shell, fg_color=BENCH_SURFACE_RAISED, border_width=1, border_color=BENCH_BORDER, corner_radius=BENCH_RADIUS_CARD)
        top.pack(fill='x', padx=12, pady=(0, 9))
        left = ctk.CTkFrame(top, fg_color='transparent')
        left.pack(side='left', fill='x', expand=True, padx=13, pady=11)
        ctk.CTkLabel(left, text=headline, font=(FONT, BENCH_FONT_TITLE, 'bold'), text_color=headline_color, anchor='w').pack(anchor='w')
        ctk.CTkLabel(
            left,
            text=f"{len(selected)} componente{'s' if len(selected) != 1 else ''} medido{'s' if len(selected) != 1 else ''} · sin rankings externos",
            font=(FONT, BENCH_FONT_META), text_color=MUTED, anchor='w'
        ).pack(anchor='w', pady=(2, 0))
        actions = ctk.CTkFrame(top, fg_color='transparent')
        actions.pack(side='right', padx=13)
        ctk.CTkButton(
            actions, text='Repetir prueba', width=128, height=34,
            command=self._run_visual_benchmark, fg_color=BENCH_ACCENT_DARK,
            hover_color=BENCH_ACCENT_HOVER, border_width=1, border_color=BENCH_ACCENT_BORDER,
            text_color='#ffffff', font=(FONT, BENCH_FONT_META, 'bold')
        ).pack(side='left', padx=(0, 6))
        ctk.CTkButton(
            actions, text='Cambiar componentes', width=156, height=34,
            command=self._show_benchmark_setup, fg_color='transparent',
            hover_color=theme_color('#102840'), border_width=1, border_color=BENCH_BORDER,
            text_color=TEXT2, font=(FONT, BENCH_FONT_META, 'bold')
        ).pack(side='left')

        conclusion = benchmark_run_conclusion(
            selected, visual, suite, tele_visual=tele_visual, tele_suite=tele_suite
        )
        concl_accent, concl_bg = self._benchmark_reading_tone(conclusion.get('tone'))
        conclusion_box = ctk.CTkFrame(
            shell, fg_color=concl_bg, border_width=1, border_color=concl_accent,
            corner_radius=BENCH_RADIUS_CARD
        )
        conclusion_box.pack(fill='x', padx=12, pady=(0, 8))
        ctk.CTkLabel(
            conclusion_box, text='Conclusión CorePulse',
            font=(FONT, BENCH_FONT_META, 'bold'), text_color=BENCH_ACCENT_TEXT, anchor='w'
        ).pack(fill='x', padx=11, pady=(8, 1))
        ctk.CTkLabel(
            conclusion_box, text=str(conclusion.get('headline') or 'Resultado disponible'),
            font=(FONT, BENCH_FONT_SECTION, 'bold'), text_color=concl_accent, anchor='w'
        ).pack(fill='x', padx=11, pady=(0, 5))
        items = conclusion.get('items') if isinstance(conclusion.get('items'), list) else []
        item_grid = ctk.CTkFrame(conclusion_box, fg_color='transparent')
        item_grid.pack(fill='x', padx=8, pady=(0, 5))
        for col in range(2):
            item_grid.grid_columnconfigure(col, weight=1, uniform='benchmark_conclusion_items')
        for idx, item in enumerate(items[:3]):
            item_accent, _item_bg = self._benchmark_reading_tone(item.get('tone'))
            cell = ctk.CTkFrame(item_grid, fg_color='transparent')
            cell.grid(row=idx // 2, column=idx % 2, sticky='ew', padx=4, pady=2)
            ctk.CTkLabel(
                cell, text=f"{item.get('component') or 'Componente'} · {item.get('text') or 'Sin lectura'}",
                font=(FONT, BENCH_FONT_META), text_color=TEXT2, anchor='w',
                justify='left', wraplength=500
            ).pack(fill='x')
            ctk.CTkFrame(cell, height=2, fg_color=item_accent, corner_radius=1).pack(fill='x', pady=(3, 0))
        conclusion_note = str(conclusion.get('note') or '').strip()
        if conclusion_note:
            ctk.CTkLabel(
                conclusion_box, text=conclusion_note,
                font=(FONT, BENCH_FONT_MICRO), text_color=MUTED, anchor='w',
                justify='left', wraplength=1000
            ).pack(fill='x', padx=11, pady=(0, 4))
        thermal_row = ctk.CTkFrame(conclusion_box, fg_color='transparent')
        thermal_row.pack(fill='x', padx=11, pady=(0, 7))
        thermal_state = 'detenida por seguridad' if stop_reason else 'sin parada térmica'
        ctk.CTkLabel(
            thermal_row,
            text=f"Protección térmica: {thermal_state} · CPU máx. {self._format_visual_metric(cpu_temp, ' °C', 0)} · GPU máx. {self._format_visual_metric(gpu_temp, ' °C', 0)}",
            font=(FONT, BENCH_FONT_MICRO), text_color=RED if stop_reason else AMBER if thermal_high else MUTED,
            anchor='w'
        ).pack(side='left', fill='x', expand=True)
        if thermal_high or stop_reason:
            ctk.CTkButton(
                thermal_row, text='Ver evidencia térmica', width=138, height=26,
                command=lambda: self._set_benchmark_result_view('evidence'),
                fg_color='transparent', hover_color=BENCH_ACCENT_DARK,
                border_width=1, border_color=BENCH_BORDER, text_color=TEXT2,
                font=(FONT, BENCH_FONT_MICRO, 'bold')
            ).pack(side='right', padx=(8, 0))

        gpu_usage = ((tele_visual.get('gpu_usage') or {}).get('max') if isinstance(tele_visual.get('gpu_usage'), dict) else None)
        gpu_primary = self._format_visual_metric(visual.get('frames_per_s'), ' FPS', 1)
        gpu_detail = f"Extreme · 1% Low {self._format_visual_metric(visual.get('one_percent_low_fps'), ' FPS', 1)} · {self._format_visual_metric(gpu_temp, ' °C', 0)} máx."
        gpu_state = self._benchmark_row_state(visual) if 'gpu' in selected else 'N/A'
        gpu_reading = benchmark_component_reading(
            'gpu', visual, telemetry=tele_visual, safety_stop=stop_reason
        )

        cpu = suite.get('cpu') if isinstance(suite.get('cpu'), dict) else {}
        cpu_primary = self._format_visual_metric(cpu.get('throughput_mbps'), ' MB/s', 0)
        cpu_detail = f"Calidad {str(cpu.get('measurement_quality') or 'N/A')} · {self._format_visual_metric(cpu_temp, ' °C', 0)} máx. total"
        cpu_state = self._benchmark_row_state(cpu) if 'cpu' in selected else 'N/A'
        cpu_reading = benchmark_component_reading(
            'cpu', cpu, telemetry=tele_suite, safety_stop=stop_reason
        )

        ram = suite.get('ram') if isinstance(suite.get('ram'), dict) else {}
        ram_mbps = _num(ram.get('value'))
        ram_primary = self._format_visual_metric((ram_mbps / 1024.0) if ram_mbps is not None else None, ' GB/s', 2)
        ram_detail = f"Integridad {'OK' if ram.get('integrity_ok') is True else 'N/A'} · variación {self._format_visual_metric(ram.get('bandwidth_cv_percent'), '%', 1)}"
        ram_state = self._benchmark_row_state(ram) if 'ram' in selected else 'N/A'
        ram_reading = benchmark_component_reading(
            'ram', ram, telemetry=tele_suite, safety_stop=stop_reason
        )

        ssd = suite.get('ssd') if isinstance(suite.get('ssd'), dict) else {}
        ssd_primary = self._format_visual_metric(ssd.get('read_mbps'), ' MB/s', 0)
        ssd_detail = f"Escritura {self._format_visual_metric(ssd.get('write_mbps'), ' MB/s', 0)} · volumen {str(ssd.get('path_root') or 'N/A')}"
        ssd_state = self._benchmark_row_state(ssd) if 'ssd' in selected else 'N/A'
        ssd_reading = benchmark_component_reading(
            'ssd', ssd, telemetry=tele_suite, safety_stop=stop_reason
        )

        glance_entries = []
        if 'gpu' in selected:
            glance_entries.append(('GPU 3D', gpu_primary, f"1% Low {self._format_visual_metric(visual.get('one_percent_low_fps'), ' FPS', 1)} · {self._format_visual_metric(gpu_temp, ' °C', 0)} máx.", BENCH_ACCENT_TEXT))
        if 'cpu' in selected:
            glance_entries.append(('CPU', cpu_primary, f"SHA-256 · {self._format_visual_metric(cpu_temp, ' °C', 0)} máx. total", CYAN))
        if 'ram' in selected:
            glance_entries.append(('RAM', ram_primary, f"Integridad {'OK' if ram.get('integrity_ok') is True else 'N/A'} · CV {self._format_visual_metric(ram.get('bandwidth_cv_percent'), '%', 1)}", GREEN))
        if 'ssd' in selected:
            glance_entries.append(('SSD', ssd_primary, f"Escritura {self._format_visual_metric(ssd.get('write_mbps'), ' MB/s', 0)} · {str(ssd.get('path_root') or 'N/A')}", AMBER))
        self._render_benchmark_glance_strip(shell, glance_entries)

        # V202: el Resumen rápido termina aquí. Las mismas cifras ya aparecen en
        # "Lectura rápida"; repetir tarjetas completas debajo obligaba a releer
        # información sin aportar contexto. GPU 3D, Sistema y Evidencia conservan
        # el detalle completo, de modo que se reduce carga visual sin perder datos.

        # V193: las escenas GPU se muestran sólo en GPU 3D. Repetirlas en
        # Resumen añadía densidad y forzaba scroll en una vista que debe poder
        # entenderse de un vistazo.

        # V199: la protección térmica se resume dentro de Conclusión CorePulse;
        # la evidencia completa permanece en la pestaña Evidencia.

    def _toggle_benchmark_detail(self, key):
        flags = getattr(self, '_benchmark_detail_flags', None)
        if not isinstance(flags, dict):
            flags = {'gpu': False, 'system': False, 'evidence': False}
            self._benchmark_detail_flags = flags
        key = str(key or '').lower()
        if key in flags:
            flags[key] = not bool(flags.get(key))
        if getattr(self, '_benchmark_results_static_active', False):
            if self._refresh_static_benchmark_page(key):
                return
        self._refresh_visual_benchmark_result_in_place()

    def _benchmark_detail_header(self, shell, key, title, subtitle):
        expanded = bool((getattr(self, '_benchmark_detail_flags', {}) or {}).get(key))
        row = ctk.CTkFrame(
            shell, fg_color=BENCH_SURFACE, border_width=1,
            border_color=BENCH_BORDER, corner_radius=BENCH_RADIUS_CONTROL
        )
        row.pack(fill='x', padx=12, pady=(0, 8))
        text = ctk.CTkFrame(row, fg_color='transparent')
        text.pack(side='left', fill='x', expand=True, padx=11, pady=8)
        ctk.CTkLabel(
            text, text=title, font=(FONT, BENCH_FONT_SECTION, 'bold'),
            text_color=TEXT, anchor='w'
        ).pack(anchor='w')
        ctk.CTkLabel(
            text, text=subtitle, font=(FONT, BENCH_FONT_META),
            text_color=MUTED, anchor='w'
        ).pack(anchor='w', pady=(1, 0))
        ctk.CTkButton(
            row,
            text='Ocultar detalles técnicos' if expanded else 'Ver detalles técnicos',
            width=168, height=32,
            command=lambda k=key: self._toggle_benchmark_detail(k),
            fg_color=BENCH_ACCENT_DARK if expanded else 'transparent',
            hover_color=BENCH_ACCENT_HOVER if expanded else theme_color('#102840'),
            border_width=1,
            border_color=BENCH_ACCENT_BORDER if expanded else BENCH_BORDER,
            text_color=BENCH_ACCENT_TEXT if expanded else TEXT2,
            font=(FONT, BENCH_FONT_META, 'bold'),
            corner_radius=BENCH_RADIUS_CONTROL,
        ).pack(side='right', padx=9, pady=8)
        return expanded

    def _render_benchmark_gpu_view(self, shell, result):
        selected, visual, suite, tele_visual, _tele_suite = self._benchmark_result_payload(result)
        if 'gpu' not in selected or not visual:
            ctk.CTkLabel(
                shell,
                text='GPU no fue incluida o no produjo una medición evaluable.',
                font=(FONT, BENCH_FONT_BODY), text_color=MUTED, anchor='w'
            ).pack(fill='x', padx=12, pady=12)
            return

        advanced = self._benchmark_detail_header(
            shell, 'gpu', 'Escenas GPU',
            'FPS es el promedio. 1% Low resume los frames más lentos; cuanto más cerca del promedio, más uniforme fue la entrega.'
        )
        gpu_reading = benchmark_component_reading(
            'gpu', visual, telemetry=tele_visual, safety_stop=suite.get('safety_stop')
        )
        self._benchmark_reading_box(shell, gpu_reading, compact=not advanced, show_summary=True, padx=12, pady=(0, 8))
        phases = visual.get('phase_results') if isinstance(visual.get('phase_results'), list) else []
        phases = [
            p for p in phases
            if isinstance(p, dict) and str(p.get('key') or '').lower() in {'valley', 'forest', 'lake', 'extreme'}
        ]

        grid = ctk.CTkFrame(shell, fg_color='transparent')
        grid.pack(fill='x', padx=8, pady=(0, 8))
        for col in range(2):
            grid.grid_columnconfigure(col, weight=1, uniform='benchmark_gpu_detail')

        for idx, phase in enumerate(phases[:4]):
            card = ctk.CTkFrame(
                grid, fg_color=BENCH_SURFACE_SOFT, border_width=1,
                border_color=BENCH_BORDER, corner_radius=BENCH_RADIUS_CARD
            )
            card.grid(row=idx // 2, column=idx % 2, sticky='nsew', padx=4, pady=4)
            ctk.CTkFrame(card, height=3, fg_color=BENCH_ACCENT, corner_radius=2).pack(
                fill='x', padx=10, pady=(7, 4)
            )
            ctk.CTkLabel(
                card, text=str(phase.get('label') or phase.get('key') or 'Escena'),
                font=(FONT, BENCH_FONT_SECTION, 'bold'),
                text_color=BENCH_ACCENT_TEXT, anchor='w'
            ).pack(fill='x', padx=10, pady=(1, 1))
            ctk.CTkLabel(
                card, text=self._format_visual_metric(phase.get('frames_per_s'), ' FPS', 1),
                font=(FONT, BENCH_FONT_METRIC, 'bold'), text_color=TEXT, anchor='w'
            ).pack(fill='x', padx=10)
            phase_fps = _num(phase.get('frames_per_s'))
            phase_low = _num(phase.get('one_percent_low_fps'))
            low_ratio = (phase_low / phase_fps * 100.0) if phase_fps and phase_low is not None and phase_fps > 0 else None
            low_text = f"1% Low  {self._format_visual_metric(phase_low, ' FPS', 1)}"
            if low_ratio is not None:
                low_text += f" · {low_ratio:.0f}% del promedio"
            ctk.CTkLabel(
                card, text=low_text,
                font=(FONT, BENCH_FONT_BODY, 'bold'), text_color=TEXT2, anchor='w'
            ).pack(fill='x', padx=10, pady=(2, 7 if not advanced else 2))

            if advanced:
                gpu_ms = self._format_visual_metric(phase.get('gpu_frame_time_avg_ms'), ' ms', 2)
                cpu_present = self._format_visual_metric(phase.get('frametime_avg_ms'), ' ms', 2)
                cv = _num(phase.get('frametime_cv'))
                spikes = _num(phase.get('frametime_spike_ratio'))
                details = [f'Tiempo GPU {gpu_ms}', f'Frame presentado {cpu_present}']
                if cv is not None:
                    details.append(f'Variación {cv*100:.1f}%')
                if spikes is not None:
                    details.append(f'Frames lentos {spikes*100:.1f}%')
                ctk.CTkLabel(
                    card, text=' · '.join(details), font=(FONT, BENCH_FONT_MICRO),
                    text_color=MUTED, anchor='w', wraplength=470
                ).pack(fill='x', padx=10, pady=(0, 7))

        gpu_cov = _num(visual.get('gpu_timestamp_coverage'))
        footer = ctk.CTkFrame(
            shell, fg_color=BENCH_SURFACE, border_width=1,
            border_color=BENCH_BORDER, corner_radius=BENCH_RADIUS_CONTROL
        )
        footer.pack(fill='x', padx=12, pady=(0, 9))
        ctk.CTkLabel(
            footer, text='Renderer real', font=(FONT, BENCH_FONT_META, 'bold'),
            text_color=BENCH_ACCENT_TEXT, anchor='w'
        ).pack(fill='x', padx=10, pady=(7, 1))
        ctk.CTkLabel(
            footer,
            text=f"{visual.get('renderer') or 'N/A'} · {visual.get('resolution') or 'N/A'} · "
                 f"timestamp GPU {'N/A' if gpu_cov is None else f'{gpu_cov*100:.0f}%'}",
            font=(FONT, BENCH_FONT_META), text_color=TEXT2, anchor='w'
        ).pack(fill='x', padx=10, pady=(0, 7))

    def _system_primary_metric(self, parent, label, value, accent, detail='', reading=None):
        ctk.CTkLabel(
            parent, text=label.upper(), font=(FONT, BENCH_FONT_MICRO, 'bold'),
            text_color=accent, anchor='w'
        ).pack(fill='x', padx=11, pady=(1, 0))
        ctk.CTkLabel(
            parent, text=value, font=(FONT, BENCH_FONT_SCENE_VALUE, 'bold'),
            text_color=TEXT, anchor='w'
        ).pack(fill='x', padx=11, pady=(0, 1))
        if detail:
            ctk.CTkLabel(
                parent, text=detail, font=(FONT, BENCH_FONT_META),
                text_color=MUTED, anchor='w', wraplength=320
            ).pack(fill='x', padx=11, pady=(0, 3 if reading else 6))
        if reading:
            self._benchmark_reading_box(parent, reading, compact=True, padx=8, pady=(2, 8))

    def _system_metric_row(self, parent, label, value, accent):
        row = ctk.CTkFrame(parent, fg_color='transparent')
        row.pack(fill='x', padx=10, pady=2)
        ctk.CTkLabel(row, text=label, width=145, font=(FONT, BENCH_FONT_META), text_color=MUTED, anchor='w').pack(side='left')
        ctk.CTkLabel(row, text=value, font=(FONT, BENCH_FONT_META, 'bold'), text_color=TEXT, anchor='e').pack(side='right')

    def _render_benchmark_system_view(self, shell, result):
        selected, _visual, suite, _tele_visual, tele_suite = self._benchmark_result_payload(result)
        system_selected = [key for key in ('cpu', 'ram', 'ssd') if key in selected]
        if not system_selected:
            ctk.CTkLabel(
                shell, text='CPU, RAM y SSD no fueron incluidos en esta ejecución.',
                font=(FONT, BENCH_FONT_BODY), text_color=MUTED, anchor='w'
            ).pack(fill='x', padx=12, pady=12)
            return

        advanced = self._benchmark_detail_header(
            shell, 'system', 'Sistema',
            'Muestra primero el rendimiento principal; IOPS, variación y métricas auxiliares son opcionales.'
        )
        grid = ctk.CTkFrame(shell, fg_color='transparent')
        grid.pack(fill='x', padx=8, pady=(0, 9))
        for col in range(len(system_selected)):
            grid.grid_columnconfigure(col, weight=1, uniform='benchmark_system_detail')

        cpu = suite.get('cpu') if isinstance(suite.get('cpu'), dict) else {}
        ram = suite.get('ram') if isinstance(suite.get('ram'), dict) else {}
        ssd = suite.get('ssd') if isinstance(suite.get('ssd'), dict) else {}
        cpu_temp = ((tele_suite.get('cpu_temp') or {}).get('max') if isinstance(tele_suite.get('cpu_temp'), dict) else None)
        comp = cpu.get('compression') if isinstance(cpu.get('compression'), dict) else {}
        ram_mbps = _num(ram.get('value'))
        stop_reason = suite.get('safety_stop')
        cpu_reading = benchmark_component_reading('cpu', cpu, telemetry=tele_suite, safety_stop=stop_reason)
        ram_reading = benchmark_component_reading('ram', ram, telemetry=tele_suite, safety_stop=stop_reason)
        ssd_reading = benchmark_component_reading('ssd', ssd, telemetry=tele_suite, safety_stop=stop_reason)

        boxes = {}
        accent_map = {'cpu': CYAN, 'ram': GREEN, 'ssd': AMBER}
        title_map = {'cpu': 'CPU', 'ram': 'RAM', 'ssd': 'SSD'}
        for idx, key in enumerate(system_selected):
            box = ctk.CTkFrame(
                grid, fg_color=BENCH_SURFACE_SOFT, border_width=1,
                border_color=BENCH_BORDER, corner_radius=BENCH_RADIUS_CARD
            )
            box.grid(row=0, column=idx, sticky='nsew', padx=4)
            accent = accent_map[key]
            ctk.CTkFrame(box, height=3, fg_color=accent, corner_radius=2).pack(fill='x', padx=10, pady=(7, 4))
            ctk.CTkLabel(box, text=title_map[key], font=(FONT, BENCH_FONT_SECTION, 'bold'), text_color=accent, anchor='w').pack(fill='x', padx=11, pady=(0, 4))
            boxes[key] = box

        if 'cpu' in boxes:
            self._system_primary_metric(
                boxes['cpu'], 'SHA-256', self._format_visual_metric(cpu.get('throughput_mbps'), ' MB/s', 0), CYAN,
                f"Calidad {str(cpu.get('measurement_quality') or 'N/A')} · {self._format_visual_metric(cpu_temp, ' °C', 1)} máx.",
                reading=cpu_reading
            )
            if advanced:
                self._system_metric_row(boxes['cpu'], 'Compresión zlib', self._format_visual_metric(comp.get('compression_mbps'), ' MB/s', 0), CYAN)
                self._system_metric_row(boxes['cpu'], 'Descompresión zlib', self._format_visual_metric(comp.get('decompression_mbps'), ' MB/s', 0), CYAN)

        if 'ram' in boxes:
            self._system_primary_metric(
                boxes['ram'], 'Copia', self._format_visual_metric((ram_mbps / 1024.0) if ram_mbps is not None else None, ' GB/s', 2), GREEN,
                f"Integridad {'OK' if ram.get('integrity_ok') is True else 'N/A'}",
                reading=ram_reading
            )
            if advanced:
                self._system_metric_row(boxes['ram'], 'Variación (CV)', self._format_visual_metric(ram.get('bandwidth_cv_percent'), '%', 2), GREEN)

        if 'ssd' in boxes:
            self._system_primary_metric(
                boxes['ssd'], 'Lectura', self._format_visual_metric(ssd.get('read_mbps'), ' MB/s', 0), AMBER,
                f"Escritura {self._format_visual_metric(ssd.get('write_mbps'), ' MB/s', 0)}",
                reading=ssd_reading
            )
            if advanced:
                self._system_metric_row(boxes['ssd'], 'Random 4K lectura', self._format_visual_metric(ssd.get('random4k_read_iops'), ' IOPS', 0), AMBER)
                self._system_metric_row(boxes['ssd'], 'Random 4K escritura', self._format_visual_metric(ssd.get('random4k_write_iops'), ' IOPS', 0), AMBER)
                self._system_metric_row(boxes['ssd'], 'Volumen', str(ssd.get('path_root') or 'N/A'), AMBER)

        ctk.CTkLabel(
            shell,
            text='Datos de esta ejecución local. CorePulse no rellena valores ausentes ni los convierte en rankings externos.',
            font=(FONT, BENCH_FONT_META), text_color=MUTED, anchor='w', justify='left'
        ).pack(fill='x', padx=12, pady=(0, 8))

    def _render_benchmark_evidence_view(self, shell, result):
        selected, visual, suite, tele_visual, _tele_suite = self._benchmark_result_payload(result)
        saved_path = suite.get('gpu_result_path') if suite.get('gpu_result_saved') else None
        evidence = ctk.CTkFrame(shell, fg_color=BENCH_SURFACE, border_width=1, border_color=BENCH_BORDER, corner_radius=BENCH_RADIUS_CARD)
        evidence.pack(fill='x', padx=12, pady=(0, 8))
        ctk.CTkLabel(evidence, text='Archivo de evidencia', font=(FONT, BENCH_FONT_SECTION, 'bold'), text_color=GREEN, anchor='w').pack(fill='x', padx=10, pady=(8, 3))
        if saved_path:
            saved_path = str(saved_path)
            filename = os.path.basename(saved_path)
            row = ctk.CTkFrame(evidence, fg_color='transparent')
            row.pack(fill='x', padx=10, pady=(0, 4))
            badge = ctk.CTkFrame(
                row, fg_color=BENCH_SURFACE_SOFT, border_width=1,
                border_color=BENCH_BORDER, corner_radius=BENCH_RADIUS_CONTROL
            )
            badge.pack(side='left', fill='x', expand=True, padx=(0, 7))
            ctk.CTkLabel(
                badge, text='Último archivo', font=(FONT, BENCH_FONT_META, 'bold'),
                text_color=TEXT2, anchor='w'
            ).pack(fill='x', padx=10, pady=(6, 0))
            ctk.CTkLabel(
                badge, text=filename, font=(FONT, BENCH_FONT_BODY, 'bold'),
                text_color='#ffffff', anchor='w'
            ).pack(fill='x', padx=10, pady=(0, 6))
            actions = ctk.CTkFrame(row, fg_color='transparent')
            actions.pack(side='right')
            ctk.CTkButton(
                actions, text='Abrir carpeta', width=108, height=34,
                command=lambda p=saved_path: self._open_benchmark_result_folder(p),
                corner_radius=BENCH_RADIUS_CONTROL, fg_color='transparent',
                hover_color=BENCH_ACCENT_DARK, border_width=1,
                border_color=BENCH_BORDER, text_color=TEXT2,
                font=(FONT, BENCH_FONT_META, 'bold')
            ).pack(side='left', padx=(0, 6))
            ctk.CTkButton(
                actions, text='Copiar ruta', width=104, height=34,
                command=lambda p=saved_path: self._copy_benchmark_result_path(p),
                corner_radius=BENCH_RADIUS_CONTROL, fg_color=BENCH_ACCENT_DARK,
                hover_color=BENCH_ACCENT_HOVER, border_width=1,
                border_color=BENCH_ACCENT_BORDER, text_color=BENCH_ACCENT_TEXT,
                font=(FONT, BENCH_FONT_META, 'bold')
            ).pack(side='left')
            ctk.CTkLabel(
                evidence, text=self._compact_benchmark_path(saved_path),
                font=(FONT, BENCH_FONT_META), text_color=MUTED,
                anchor='w', justify='left', wraplength=980
            ).pack(fill='x', padx=10, pady=(0, 8))
        else:
            msg = 'N/A'
            if suite.get('gpu_result_save_error'):
                msg = 'No se pudo guardar: ' + str(suite.get('gpu_result_save_error'))
            ctk.CTkLabel(evidence, text=msg, font=(FONT, BENCH_FONT_META), text_color=AMBER if msg != 'N/A' else MUTED, anchor='w').pack(fill='x', padx=10, pady=(0, 5))

        thermal_audit = tele_visual.get('thermal_audit') if isinstance(tele_visual.get('thermal_audit'), dict) else {}
        if thermal_audit:
            cpu_audit = thermal_audit.get('cpu') if isinstance(thermal_audit.get('cpu'), dict) else {}
            gpu_audit = thermal_audit.get('gpu') if isinstance(thermal_audit.get('gpu'), dict) else {}
            cpu_obs = cpu_audit.get('warning_observation') if isinstance(cpu_audit.get('warning_observation'), dict) else {}
            gpu_obs = gpu_audit.get('warning_observation') if isinstance(gpu_audit.get('warning_observation'), dict) else {}
            cpu_safety = cpu_audit.get('safety_observation') if isinstance(cpu_audit.get('safety_observation'), dict) else {}

            box = ctk.CTkFrame(
                shell, fg_color=BENCH_SURFACE_RAISED, border_width=1,
                border_color=BENCH_BORDER, corner_radius=BENCH_RADIUS_CARD
            )
            box.pack(fill='x', padx=12, pady=(0, 8))
            ctk.CTkLabel(
                box, text='Evidencia térmica · fase GPU',
                font=(FONT, BENCH_FONT_SECTION, 'bold'),
                text_color=AMBER, anchor='w'
            ).pack(fill='x', padx=10, pady=(8, 5))

            thermal_grid = ctk.CTkFrame(box, fg_color='transparent')
            thermal_grid.pack(fill='x', padx=6, pady=(0, 6))
            thermal_grid.grid_columnconfigure(0, weight=1, uniform='thermal_evidence')
            thermal_grid.grid_columnconfigure(1, weight=1, uniform='thermal_evidence')

            def thermal_card(column, title, accent, peak, threshold, count, margin_label, margin_value):
                card = ctk.CTkFrame(
                    thermal_grid, fg_color=BENCH_SURFACE_SOFT,
                    border_width=1, border_color=BENCH_BORDER,
                    corner_radius=BENCH_RADIUS_CONTROL
                )
                card.grid(row=0, column=column, sticky='nsew', padx=4)
                ctk.CTkLabel(
                    card, text=title, font=(FONT, BENCH_FONT_META, 'bold'),
                    text_color=accent, anchor='w'
                ).pack(fill='x', padx=9, pady=(7, 1))
                ctk.CTkLabel(
                    card, text=self._format_visual_metric(peak, ' °C', 1),
                    font=(FONT, BENCH_FONT_SCENE_VALUE, 'bold'),
                    text_color=TEXT, anchor='w'
                ).pack(fill='x', padx=9)
                ctk.CTkLabel(
                    card,
                    text=f"Muestras sobre {self._format_visual_metric(threshold, ' °C', 0)}: {count if count is not None else 'N/A'}",
                    font=(FONT, BENCH_FONT_MICRO), text_color=MUTED, anchor='w'
                ).pack(fill='x', padx=9, pady=(2, 1))
                ctk.CTkLabel(
                    card,
                    text=f"{margin_label}: {self._format_visual_metric(margin_value, ' °C', 1)}",
                    font=(FONT, BENCH_FONT_MICRO), text_color=TEXT2, anchor='w'
                ).pack(fill='x', padx=9, pady=(0, 7))

            thermal_card(
                0, 'CPU durante GPU', CYAN,
                cpu_audit.get('peak_c'), cpu_obs.get('threshold_c'),
                cpu_obs.get('sample_count_at_or_above'),
                'Margen mín. a TjMax', cpu_audit.get('minimum_tjmax_distance_c')
            )
            thermal_card(
                1, 'GPU', GREEN,
                gpu_audit.get('peak_c'), gpu_obs.get('threshold_c'),
                gpu_obs.get('sample_count_at_or_above'),
                'Margen a límite sensor', gpu_audit.get('minimum_margin_to_reported_core_limit_c')
            )

            if cpu_safety:
                trigger = bool(cpu_safety.get('trigger_observed'))
                streak = cpu_safety.get('max_consecutive_sample_count')
                safety_row = ctk.CTkFrame(box, fg_color='transparent')
                safety_row.pack(fill='x', padx=10, pady=(0, 4))
                ctk.CTkLabel(
                    safety_row,
                    text='Protección térmica CPU',
                    font=(FONT, BENCH_FONT_META, 'bold'),
                    text_color=TEXT2, anchor='w'
                ).pack(side='left')
                ctk.CTkLabel(
                    safety_row,
                    text=('ACTIVADA' if trigger else f'Sin gatillo · racha {streak if streak is not None else "N/A"}/3'),
                    font=(FONT, BENCH_FONT_META, 'bold'),
                    text_color=RED if trigger else GREEN, anchor='e'
                ).pack(side='right')

            cpu_warn_count = cpu_obs.get('sample_count_at_or_above')
            gpu_warn_count = gpu_obs.get('sample_count_at_or_above')
            cpu_peak = _num(cpu_audit.get('peak_c'))
            gpu_peak = _num(gpu_audit.get('peak_c'))
            cpu_margin = _num(cpu_audit.get('minimum_tjmax_distance_c'))
            trigger = bool(cpu_safety.get('trigger_observed')) if cpu_safety else False
            streak = cpu_safety.get('max_consecutive_sample_count') if cpu_safety else None
            required = cpu_safety.get('trigger_samples_required') if cpu_safety else None
            safety_threshold = _num(cpu_audit.get('safety_threshold_distance_c'))
            if trigger:
                thermal_reading = {
                    'label': 'PROTECCIÓN ACTIVADA', 'tone': 'red',
                    'summary': 'La CPU cumplió el criterio térmico sostenido de seguridad y CorePulse detuvo la carga.',
                    'scope': 'La parada protege el equipo; esta ejecución no debe compararse con un benchmark completado.'
                }
            elif isinstance(cpu_warn_count, int) and cpu_warn_count > 0:
                margin_text = self._format_visual_metric(cpu_margin, ' °C', 1)
                streak_text = f'{streak}/{required}' if streak is not None and required else 'N/A'
                threshold_text = self._format_visual_metric(safety_threshold, ' °C', 1)
                thermal_reading = {
                    'label': 'TEMPERATURA CPU ALTA · SIN PARADA', 'tone': 'amber',
                    'summary': (
                        f'La CPU alcanzó {self._format_visual_metric(cpu_peak, " °C", 1)} y hubo {cpu_warn_count} muestra(s) sobre el umbral de advertencia. '
                        f'El margen mínimo a TjMax fue {margin_text}; la racha de seguridad quedó en {streak_text}.'
                    ),
                    'scope': f'CorePulse sólo detiene por este criterio cuando observa muestras reales consecutivas dentro de {threshold_text} de TjMax; no interpola lecturas.'
                }
            elif isinstance(gpu_warn_count, int) and gpu_warn_count > 0:
                thermal_reading = {
                    'label': 'TEMPERATURA GPU ALTA', 'tone': 'amber',
                    'summary': f'La GPU alcanzó {self._format_visual_metric(gpu_peak, " °C", 1)} y registró {gpu_warn_count} muestra(s) sobre el umbral de advertencia.',
                    'scope': 'Esto describe la temperatura observada en la fase GPU; no implica por sí solo throttling.'
                }
            else:
                thermal_reading = {
                    'label': 'SIN GATILLO TÉRMICO', 'tone': 'green',
                    'summary': 'No se observó el criterio sostenido que obliga a detener el benchmark.',
                    'scope': 'La ausencia de gatillo no convierte la temperatura en “fría”; revisa los picos y márgenes mostrados arriba.'
                }
            self._benchmark_reading_box(box, thermal_reading, compact=False, padx=10, pady=(2, 7))

            ctk.CTkLabel(
                box,
                text='Sólo incluye muestras de la fase GPU DirectX. La temperatura máxima total de la ejecución puede incluir CPU, RAM y SSD.',
                font=(FONT, BENCH_FONT_MICRO), text_color=MUTED,
                anchor='w', justify='left', wraplength=1000
            ).pack(fill='x', padx=10, pady=(0, 8))

        methodology_expanded = bool((getattr(self, '_benchmark_detail_flags', {}) or {}).get('evidence'))
        technical = ctk.CTkFrame(shell, fg_color=BENCH_SURFACE, border_width=1, border_color=BENCH_BORDER, corner_radius=BENCH_RADIUS_CARD)
        technical.pack(fill='x', padx=12, pady=(0, 8))
        method_head = ctk.CTkFrame(technical, fg_color='transparent')
        method_head.pack(fill='x', padx=10, pady=(7, 4))
        ctk.CTkLabel(method_head, text='Método y trazabilidad', font=(FONT, BENCH_FONT_SECTION, 'bold'), text_color=BENCH_ACCENT_TEXT, anchor='w').pack(side='left')
        ctk.CTkButton(
            method_head, text='Ocultar metodología' if methodology_expanded else 'Ver metodología',
            width=138, height=30, command=lambda: self._toggle_benchmark_detail('evidence'),
            fg_color=BENCH_ACCENT_DARK if methodology_expanded else 'transparent',
            hover_color=BENCH_ACCENT_HOVER if methodology_expanded else theme_color('#102840'),
            border_width=1, border_color=BENCH_ACCENT_BORDER if methodology_expanded else BENCH_BORDER,
            text_color=BENCH_ACCENT_TEXT if methodology_expanded else TEXT2,
            font=(FONT, BENCH_FONT_META, 'bold'), corner_radius=BENCH_RADIUS_CONTROL
        ).pack(side='right')
        gpu_cov = _num(visual.get('gpu_timestamp_coverage'))
        ctk.CTkLabel(
            technical,
            text=f"DirectX 11 · timestamps GPU {'N/A' if gpu_cov is None else f'{gpu_cov*100:.0f}%'} · REAL_OR_NA · VSync {'off' if visual.get('vsync_disabled') is True else 'N/A'}",
            font=(FONT, BENCH_FONT_META, 'bold'), text_color=TEXT2, anchor='w', justify='left', wraplength=1000
        ).pack(fill='x', padx=10, pady=(0, 6 if not methodology_expanded else 3))
        if methodology_expanded:
            ctk.CTkLabel(
                technical,
                text=f"Renderer: {visual.get('renderer') or 'N/A'} · resolución {visual.get('resolution') or 'N/A'}",
                font=(FONT, BENCH_FONT_META), text_color=TEXT2, anchor='w', justify='left', wraplength=1000
            ).pack(fill='x', padx=10, pady=(0, 3))
            ctk.CTkLabel(
                technical,
                text='GPU: warm-up global + settle + prime por fase; medición por reloj de pared. CPU/RAM/SSD usan cargas locales independientes. Lo que no se puede medir queda N/A.',
                font=(FONT, BENCH_FONT_MICRO), text_color=MUTED, anchor='w', justify='left', wraplength=1000
            ).pack(fill='x', padx=10, pady=(0, 6))

        # Compatibilidad de sensores queda bajo demanda. En el primer vistazo
        # no creamos decenas de widgets ni obligamos a recorrer un panel largo.
        snapshot = getattr(self.app, 'latest_telemetry', {}) or {}
        diagnostic = build_sensor_diagnostics(snapshot)
        groups = diagnostic.get('groups') if isinstance(diagnostic, dict) else []
        groups = [g for g in (groups or []) if isinstance(g, dict) and str(g.get('key') or '').lower() in {'cpu','ram','gpu','storage'}]
        total = sum(int(g.get('total') or 0) for g in groups)
        available = sum(int(g.get('available') or 0) for g in groups)
        coverage = (available / total * 100.0) if total else 0.0
        sensor_toggle = ctk.CTkFrame(shell, fg_color=BENCH_SURFACE, border_width=1, border_color=BENCH_BORDER, corner_radius=BENCH_RADIUS_CARD)
        sensor_toggle.pack(fill='x', padx=12, pady=(0, 8))
        ctk.CTkLabel(sensor_toggle, text='Compatibilidad de sensores', font=(FONT, BENCH_FONT_SECTION, 'bold'), text_color=CYAN, anchor='w').pack(side='left', padx=10, pady=9)
        ctk.CTkLabel(sensor_toggle, text=f'{coverage:.0f}% disponible · REAL_OR_NA', font=(FONT, BENCH_FONT_META), text_color=MUTED).pack(side='left', padx=(4, 8))
        ctk.CTkButton(
            sensor_toggle,
            text='Ocultar sensores' if self._benchmark_evidence_sensors_expanded else 'Ver sensores',
            width=124, height=32, command=self._toggle_benchmark_evidence_sensors,
            fg_color='transparent', hover_color=theme_color('#102840'), border_width=1, border_color=BENCH_BORDER,
            text_color=TEXT2, font=(FONT, BENCH_FONT_META, 'bold')
        ).pack(side='right', padx=9, pady=6)
        if self._benchmark_evidence_sensors_expanded:
            self._render_sensor_compatibility(parent=shell)

    def _toggle_benchmark_evidence_sensors(self):
        self._benchmark_evidence_sensors_expanded = not bool(self._benchmark_evidence_sensors_expanded)
        if getattr(self, '_benchmark_results_static_active', False):
            if self._refresh_static_benchmark_page('evidence'):
                return
        self._refresh_visual_benchmark_result_in_place()

    def _render_visual_benchmark_result_body(self, shell, result):
        """Dashboard de resultados V190 con divulgación progresiva y acabado CorePulse.

        El primer frame muestra sólo lo necesario para entender la ejecución.
        GPU, CPU/RAM/SSD y evidencia técnica viven en vistas separadas para evitar
        el scroll largo que además exponía artefactos de repintado en Windows.
        """
        status = str(result.get('status') or '').upper()
        if status in ('ERROR', 'UNAVAILABLE', 'PARTIAL', 'SAFETY_STOP', 'CANCELLED'):
            color = RED if status in ('ERROR', 'SAFETY_STOP') else AMBER
            title = {
                'ERROR':'Benchmark no completado', 'UNAVAILABLE':'Benchmark no disponible',
                'PARTIAL':'Benchmark completado parcialmente', 'SAFETY_STOP':'Detenido por seguridad térmica',
                'CANCELLED':'Benchmark cancelado',
            }.get(status, status)
            ctk.CTkLabel(
                shell, text=f"{title}: {result.get('reason') or 'revisa los resultados por componente'}",
                font=(FONT, BENCH_FONT_BODY, 'bold'), text_color=color, anchor='w', justify='left', wraplength=1020
            ).pack(fill='x', padx=12, pady=(0, 8))

        self._render_benchmark_result_nav(shell)
        view = str(getattr(self, '_benchmark_result_view', 'summary') or 'summary')
        if view == 'gpu':
            self._render_benchmark_gpu_view(shell, result)
        elif view == 'system':
            self._render_benchmark_system_view(shell, result)
        elif view == 'evidence':
            self._render_benchmark_evidence_view(shell, result)
        else:
            self._render_benchmark_summary_view(shell, result)

    def _settle_visual_benchmark_result_paint(self):
        """Sincroniza geometría y repintado después del swap de resultados.

        En Windows el Canvas puede conservar un frame viejo durante el primer
        desplazamiento si se reemplazan muchos widgets de una sola vez. V181
        fuerza un settle fuerte sin reconstruir la vista completa.
        """
        if not self._alive:
            return
        host = getattr(self, '_visual_benchmark_result_host', None)
        try:
            if host is None or not host.winfo_exists():
                return
            host.update_idletasks()
        except Exception:
            return
        try:
            self.scroll._refresh_geometry()
        except Exception:
            try:
                self.scroll._schedule_geometry(0)
            except Exception:
                pass
        try:
            self.scroll._flush_repaint(strong=True)
        except Exception:
            pass
        # V184: no usamos update() reentrante ni repaints tardíos. Esos callbacks
        # podían competir con el primer scroll y volver a presentar píxeles viejos.

    def _schedule_visual_benchmark_result_settle(self):
        # Settle corto: geometría + repaint fuerte antes de la interacción.
        self._settle_visual_benchmark_result_paint()
        try:
            self.scroll.defer_until_idle(self._settle_visual_benchmark_result_paint)
        except Exception:
            pass
        for delay in (32, 96):
            try:
                self.app.after(delay, self._settle_visual_benchmark_result_paint)
            except Exception:
                pass

    def _refresh_visual_benchmark_result_in_place(self):
        """Publica el resultado sin destruir el Canvas completo.

        La vista anterior permanece pintada hasta que el árbol de resultados está
        listo; evita el hueco visible observado al cerrar el worker del benchmark.
        """
        result = self._visual_bench if isinstance(self._visual_bench, dict) else None
        if getattr(self, '_benchmark_results_static_active', False) and getattr(self, '_benchmark_result_pages', None):
            return self._refresh_static_benchmark_page(getattr(self, '_benchmark_result_view', 'summary'))
        host = getattr(self, '_visual_benchmark_result_host', None)
        if not result or host is None:
            return False
        try:
            if not host.winfo_exists():
                return False
        except Exception:
            return False
        try:
            # Construye fuera de la vista y hace swap al final. Así nunca se ve
            # el árbol de resultados a medio crear (tarjetas vacías/valores tardíos).
            staging = ctk.CTkFrame(host, fg_color='transparent')
            self._render_visual_benchmark_result_body(staging, result)
            try:
                staging.update_idletasks()
            except Exception:
                pass
            for child in list(host.winfo_children()):
                if child is not staging:
                    child.destroy()
            staging.pack(fill='both', expand=True)
            if not getattr(self, '_benchmark_results_static_active', False):
                self._schedule_visual_benchmark_result_settle()
            else:
                try:
                    host.update_idletasks()
                except Exception:
                    pass
            status = getattr(self, 'lbl_visual_bench_status', None)
            if status is not None and status.winfo_exists():
                status.configure(text='ÚLTIMO RESULTADO', text_color=GREEN)
            self._refresh_benchmark_configuration_ui()
            try:
                host.update_idletasks()
            except Exception:
                pass
            return True
        except Exception:
            logger.exception('[BENCHMARK] No se pudo publicar resultados en sitio; se usará render normal')
            return False

    def _copy_benchmark_result_path(self, path):
        self.app.clipboard_clear()
        self.app.clipboard_append(path)

    def _compact_benchmark_path(self, path):
        value = str(path or '').strip()
        if not value:
            return 'Ubicación: N/A'
        folder = os.path.dirname(value)
        folder_name = os.path.basename(folder.rstrip('\\/')) or folder
        return f'Carpeta: {folder_name} · la ruta completa está disponible en «Copiar ruta».'

    def _open_benchmark_result_folder(self, path):
        value = str(path or '').strip()
        folder = os.path.dirname(value) if value else ''
        if not folder or not os.path.isdir(folder):
            messagebox.showwarning('CorePulse', 'La carpeta del resultado ya no está disponible.')
            return
        try:
            os.startfile(folder)
        except Exception as exc:
            messagebox.showerror('CorePulse', f'No se pudo abrir la carpeta del resultado:\n{exc}')

    def _run_visual_benchmark(self):
        if 'visual_benchmark' in self._jobs:
            return
        selected = self._benchmark_selected_components()
        if not selected:
            messagebox.showwarning('CorePulse', 'Selecciona al menos un componente antes de iniciar el benchmark.')
            return
        profile_key = 'standard'
        had_previous_result = isinstance(self._visual_bench, dict)
        if had_previous_result:
            # Una repetición vuelve al estado de ejecución; el resultado anterior
            # permanece en Historial y no compite visualmente con el progreso nuevo.
            self._visual_bench = None
            self._show_benchmark_scroll_surface()
        run_id = getattr(self, '_visual_benchmark_run_id', 0) + 1
        self._visual_benchmark_run_id = run_id
        self._visual_benchmark_finished = False
        self._hide_benchmark_hud()
        try: self.app.configure(cursor='')
        except Exception: pass
        visual_profile = gpu_profile_info(profile_key)
        classic_profile = benchmark_profile_info(profile_key)
        self._visual_benchmark_progress = 0.0
        self._visual_benchmark_stage = f'Preparando Benchmark {GPU_BENCHMARK_LABEL}'
        self._visual_benchmark_detail = self._benchmark_estimated_text()
        self._set_visual_benchmark_progress(0.01, self._visual_benchmark_stage, self._visual_benchmark_detail)

        gpu_selected = 'gpu' in selected
        classic_selected = [key for key in ('cpu', 'ram', 'ssd') if key in selected]
        if gpu_selected:
            hud = self._benchmark_hud_overlay()
            if hud is not None:
                try: hud.prepare_gpu()
                except Exception: pass
        gpu_weight = float(visual_profile.get('seconds') or 0.0) if gpu_selected else 0.0
        classic_weights = {
            'cpu': float(classic_profile.get('cpu_seconds') or 0.0),
            'ram': float(classic_profile.get('ram_seconds') or 0.0),
            'ssd': max(4.0, float(classic_profile.get('ssd_size_mb') or 0.0) / 100.0),
        }
        classic_weight = sum(classic_weights[k] for k in classic_selected)
        total_weight = max(1.0, gpu_weight + classic_weight)
        gpu_span = gpu_weight / total_weight if gpu_selected else 0.0

        def push_progress(fraction, stage, detail=''):
            try:
                self.app.after(0, lambda f=fraction, s=stage, d=detail: self._accept_visual_benchmark_progress(run_id, f, s, d))
            except Exception:
                pass

        def telemetry_sample():
            # Se entrega el snapshot completo. El resultado DirectX informa el adaptador
            # real usado y la capa de telemetría intenta enlazar sus sensores.
            return copy.deepcopy(getattr(self.app, 'latest_telemetry', {}) or {})

        def work():
            started = time.perf_counter()
            # El HUD se mantiene fuera de la región cronometrada; no altera FPS ni wall-clock;
            # CPU/RAM/SSD conservan mediciones V4 independientes.
            suite_result = run_benchmark_suite(
                profile_key,
                selected,
                progress_callback=push_progress,
                telemetry_sampler=telemetry_sample,
            )
            gpu_result = suite_result.get('gpu') if isinstance(suite_result, dict) and 'gpu' in selected else None
            return gpu_result, suite_result, time.perf_counter() - started

        def done(payload, error):
            self._hide_benchmark_hud()
            self._visual_benchmark_finished = True
            gpu_result = suite_result = None
            elapsed = 0.0
            if isinstance(payload, tuple) and len(payload) == 3:
                gpu_result, suite_result, elapsed = payload
            statuses = []
            reasons = []
            if gpu_selected:
                gst = str((gpu_result or {}).get('status') or 'ERROR').upper()
                statuses.append(gst)
                if gst not in ('OK',):
                    reasons.append('GPU: ' + str((gpu_result or {}).get('reason') or gst))
            for key in classic_selected:
                row = (suite_result or {}).get(key) if isinstance(suite_result, dict) else None
                st = str((row or {}).get('status') or 'ERROR').upper()
                statuses.append(st)
                if st not in ('OK', 'SKIPPED'):
                    reasons.append(f'{key.upper()}: ' + str((row or {}).get('reason') or st))
            if error:
                statuses.append('ERROR'); reasons.append(str(error))
            if 'SAFETY_STOP' in statuses:
                overall = 'SAFETY_STOP'
            elif statuses and all(st in ('ERROR','UNAVAILABLE') for st in statuses):
                overall = 'ERROR'
            elif any(st in ('ERROR','UNAVAILABLE','PARTIAL') for st in statuses):
                overall = 'PARTIAL'
            elif any(st == 'CANCELLED' for st in statuses):
                overall = 'CANCELLED'
            else:
                overall = 'OK'

            now = time.time()
            combined = {
                'kind': 'COREPULSE_BENCHMARK_SUITE_V173',
                'benchmark_method': BENCHMARK_METHOD_ID,
                'provider': f'CorePulse Benchmark {GPU_BENCHMARK_LABEL} · DirectX 11',
                'timestamp': now,
                'duration_s': float(elapsed or 0.0),
                'profile': profile_key,
                'profile_label': visual_profile.get('label'),
                'selected_components': list(selected),
                'status': overall,
                'reason': ' · '.join(reasons[:4]) if reasons else None,
                'visual_gpu': gpu_result if isinstance(gpu_result, dict) else None,
                'system_suite': suite_result if isinstance(suite_result, dict) else None,
                'policy': f'REAL_OR_NA_BENCHMARK_{GPU_BENCHMARK_LABEL}_WALLCLOCK_GPU_TIMESTAMP_NO_REFERENCE_RANKING',
            }
            self._visual_bench = combined
            # Cada ejecución nueva vuelve al resumen para que el primer vistazo
            # sea comprensible; las métricas técnicas son opt-in.
            self._benchmark_result_view = 'summary'
            self._set_benchmark_setup_collapsed(True)
            if overall == 'OK':
                self._visual_benchmark_stage = 'Benchmark completado'
                saved_path = (suite_result or {}).get('gpu_result_path') if isinstance(suite_result, dict) else None
                self._visual_benchmark_detail = (
                    f'Resultado GPU guardado en: {saved_path}'
                    if saved_path else
                    'Todas las cargas seleccionadas terminaron; GPU se midió con Valle/Bosque/Lago/Extreme y timestamps D3D11 auditados.'
                )
            elif overall == 'SAFETY_STOP':
                self._visual_benchmark_stage = 'Detenido por seguridad térmica'
                self._visual_benchmark_detail = combined.get('reason') or 'CorePulse detuvo la prueba para proteger el hardware.'
            elif overall == 'PARTIAL':
                self._visual_benchmark_stage = 'Benchmark parcialmente completado'
                self._visual_benchmark_detail = combined.get('reason') or 'Una de las cargas no pudo medirse.'
            else:
                self._visual_benchmark_stage = 'Benchmark no completado'
                self._visual_benchmark_detail = combined.get('reason') or error or 'No se obtuvo un resultado válido.'
            self._visual_benchmark_progress = 1.0
            # Actualiza también los widgets existentes: el render puede diferirse.
            self._set_visual_benchmark_progress(
                1.0, self._visual_benchmark_stage, self._visual_benchmark_detail)
            self._compact_completed_visual_benchmark_chrome()

            store = getattr(self.app, 'health_history_store', None)
            if store:
                try:
                    store.record_benchmark(combined)
                except Exception:
                    pass
                try:
                    tele = getattr(self.app, 'latest_telemetry', {}) or {}
                    hardware = {'cpu_name': tele.get('cpu_name'), 'gpu_name': tele.get('gpu_name'), 'renderer': (gpu_result or {}).get('renderer') if isinstance(gpu_result, dict) else None}
                    store.record_benchmark_session(
                        combined,
                        profile=profile_key,
                        components=list(selected),
                        comparison={}, hardware=hardware,
                    )
                    self._benchmark_history_cache = None
                except Exception:
                    logger.exception('[BENCHMARK] No se pudo guardar la sesión V145 en historial')
            # V192 publica el resultado en una superficie estática separada del
            # viewport de configuración. Evita mover widgets CTk complejos durante
            # el primer vistazo y elimina los restos de frames antiguos observados
            # al hacer scroll inmediatamente después del 100 %.
            if not self._show_static_benchmark_results():
                if not self._refresh_visual_benchmark_result_in_place():
                    self._request_render(1)
                try:
                    self.app.after_idle(lambda: self.scroll.yview_moveto(0.0) if self._alive else None)
                except Exception:
                    pass

        started = self._async('visual_benchmark', work, done)
        if started and had_previous_result:
            # Publica una sola vez el estado EN EJECUCIÓN. No reconstruye en cada
            # callback; los siguientes avances actualizan widgets existentes.
            self._request_render(1)

    def _render_sensor_compatibility(self, parent=None):
        """Muestra cobertura de sensores reutilizando el snapshot actual, sin sondeos extra."""
        snapshot = getattr(self.app, 'latest_telemetry', {}) or {}
        diagnostic = build_sensor_diagnostics(snapshot)
        groups = diagnostic.get('groups') if isinstance(diagnostic, dict) else []
        groups = groups if isinstance(groups, list) else []
        # Esta pantalla es específica del benchmark: batería no forma parte de
        # ninguna carga CPU/RAM/GPU/SSD y sólo añadía ruido visual.
        benchmark_keys = {'cpu', 'ram', 'gpu', 'storage'}
        groups = [g for g in groups if isinstance(g, dict) and str(g.get('key') or '').lower() in benchmark_keys]
        relevant_total = sum(int(g.get('total') or 0) for g in groups)
        relevant_available = sum(int(g.get('available') or 0) for g in groups)

        card = self._card(parent)
        card.pack(fill='x', padx=(12 if parent is not None else 8), pady=(4, 8))
        head = ctk.CTkFrame(card, fg_color='transparent')
        head.pack(fill='x', padx=14, pady=(11, 4))
        ctk.CTkLabel(
            head, text='Compatibilidad de sensores', font=(FONT, 12, 'bold'),
            text_color=TEXT, anchor='w'
        ).pack(side='left')
        coverage = (relevant_available / relevant_total * 100.0) if relevant_total else 0.0
        ctk.CTkLabel(
            head, text=f'{coverage:.0f}% de lecturas disponibles',
            font=(FONT, 8, 'bold'),
            text_color=GREEN if coverage >= 80 else CYAN if coverage >= 45 else AMBER,
        ).pack(side='right')

        ctk.CTkLabel(
            card,
            text='Sólo se muestran sensores relevantes para las cargas CPU, RAM, GPU y SSD. N/A significa que el sensor no fue expuesto; CorePulse no lo estima.',
            font=(FONT, 8), text_color=MUTED, anchor='w', justify='left', wraplength=1030
        ).pack(fill='x', padx=14, pady=(0, 7))

        if not groups:
            ctk.CTkLabel(
                card, text='Esperando el primer snapshot certificado de telemetría…',
                font=(FONT, 9), text_color=MUTED, anchor='w'
            ).pack(fill='x', padx=14, pady=(2, 11))
            return

        grid = ctk.CTkFrame(card, fg_color='transparent')
        grid.pack(fill='x', padx=10, pady=(0, 10))
        for col in range(3):
            grid.grid_columnconfigure(col, weight=1, uniform='sensor_diag_groups')

        labels = {'AVAILABLE': 'Completo', 'PARTIAL': 'Parcial', 'UNAVAILABLE': 'N/A'}
        colors = {'AVAILABLE': GREEN, 'PARTIAL': AMBER, 'UNAVAILABLE': MUTED}
        for idx, group in enumerate(groups[:6]):
            state = str(group.get('state') or 'UNAVAILABLE').upper()
            block = ctk.CTkFrame(grid, fg_color=CARD2, border_width=1, border_color=BORDER, corner_radius=8)
            block.grid(row=idx // 3, column=idx % 3, sticky='nsew', padx=4, pady=4)
            top = ctk.CTkFrame(block, fg_color='transparent')
            top.pack(fill='x', padx=9, pady=(8, 2))
            ctk.CTkLabel(
                top, text=str(group.get('label') or 'Sensor'), font=(FONT, 9, 'bold'),
                text_color=TEXT, anchor='w'
            ).pack(side='left')
            ctk.CTkLabel(
                top, text=labels.get(state, state), font=(FONT, 8, 'bold'),
                text_color=colors.get(state, MUTED)
            ).pack(side='right')

            available = int(group.get('available') or 0)
            total = int(group.get('total') or 0)
            detail = str(group.get('detail') or '').strip()
            line = f'{available}/{total} métricas reales' if total else 'Sin métricas certificadas'
            if detail:
                line += f' · {_short(detail, 54)}'
            ctk.CTkLabel(
                block, text=line, font=(FONT, 8), text_color=TEXT2,
                anchor='w', justify='left', wraplength=310
            ).pack(fill='x', padx=9, pady=(0, 3))

            sources = group.get('sources') if isinstance(group.get('sources'), list) else []
            source_text = ' · '.join(str(x) for x in sources[:2]) if sources else 'Fuente no expuesta'
            ctk.CTkLabel(
                block, text=_short(source_text, 72), font=(FONT, 7), text_color=MUTED,
                anchor='w', justify='left', wraplength=310
            ).pack(fill='x', padx=9, pady=(0, 8))

    @staticmethod
    def _benchmark_history_value(suite, key):
        """Normaliza tanto el benchmark visual V113 como el suite clásico V107-V143."""
        suite = suite if isinstance(suite, dict) else {}
        try:
            kind = str(suite.get('kind') or '').upper()
            if kind.startswith('COREPULSE_BENCHMARK_SUITE'):
                visual = suite.get('visual_gpu') if isinstance(suite.get('visual_gpu'), dict) else {}
                classic = suite.get('system_suite') if isinstance(suite.get('system_suite'), dict) else {}
                if key == 'gpu':
                    value = _num(visual.get('frames_per_s') if visual.get('frames_per_s') is not None else visual.get('value'))
                    return (value, f'{value:.1f} FPS') if value is not None else (None, 'N/A')
                result = classic.get(key) if isinstance(classic.get(key), dict) else {}
                status = str(result.get('status') or '').upper()
                if status in ('SKIPPED', 'UNAVAILABLE', 'ERROR'):
                    return None, 'N/A'
                if key == 'cpu':
                    value = _num(result.get('throughput_mbps'))
                    return (value, f'{value:,.0f} MB/s SHA-256'.replace(',', '.')) if value is not None else (None, 'N/A')
                if key == 'ram':
                    value = _num(result.get('value'))
                    return (value, f'{value / 1024.0:.2f} GB/s') if value is not None else (None, 'N/A')
                if key == 'ssd':
                    read_v = _num(result.get('read_mbps')); write_v = _num(result.get('write_mbps'))
                    primary = read_v
                    if read_v is None and write_v is None:
                        return None, 'N/A'
                    return primary, f"L {'N/A' if read_v is None else f'{read_v:.0f}'} · E {'N/A' if write_v is None else f'{write_v:.0f}'} MB/s"
                return None, 'N/A'

            if kind.startswith('HARDWARE_VISUAL'):
                if key == 'gpu':
                    value = _num(suite.get('frames_per_s') if suite.get('frames_per_s') is not None else suite.get('value'))
                    return (value, f'{value:.1f} FPS') if value is not None else (None, 'N/A')
                if key == 'cpu':
                    cpu = suite.get('cpu_benchmark') if isinstance(suite.get('cpu_benchmark'), dict) else {}
                    value = _num(cpu.get('sha256_mb_s'))
                    return (value, f'{value:.1f} MB/s SHA-256') if value is not None else (None, 'N/A')
                if key == 'ram':
                    ram = suite.get('ram_benchmark') if isinstance(suite.get('ram_benchmark'), dict) else {}
                    value = _num(ram.get('copy_gb_s'))
                    return (value, f'{value:.2f} GB/s') if value is not None else (None, 'N/A')
                return None, 'N/A'

            result = suite.get(key) if isinstance(suite.get(key), dict) else {}
            status = str(result.get('status') or '').upper()
            if status in ('SKIPPED', 'UNAVAILABLE', 'ERROR'):
                return None, 'N/A'
            if key == 'cpu':
                value = _num(result.get('throughput_mbps'))
                return (value, f'{value:,.0f} MB/s SHA-256'.replace(',', '.')) if value is not None else (None, 'N/A')
            if key == 'ram':
                value = _num(result.get('value'))
                if value is None:
                    return None, 'N/A'
                return value, (f'{value / 1024.0:.2f} GB/s' if value >= 1024 else f'{value:.0f} MB/s')
            if key == 'ssd':
                read_v = _num(result.get('read_mbps')); write_v = _num(result.get('write_mbps'))
                primary = read_v
                if read_v is None and write_v is None:
                    return None, 'N/A'
                return primary, f"L {'N/A' if read_v is None else f'{read_v:.0f}'} · E {'N/A' if write_v is None else f'{write_v:.0f}'} MB/s"
            if key == 'gpu':
                value = _num(result.get('value'))
                return (value, f'{value:.1f} Mtri/s') if value is not None else (None, 'N/A')
        except Exception:
            return None, 'N/A'
        return None, 'N/A'

    def _benchmark_history_sessions(self, limit=6):
        if isinstance(self._benchmark_history_cache, list):
            return self._benchmark_history_cache[:max(1, int(limit))]
        store = getattr(self.app, 'health_history_store', None)
        if store is None or not hasattr(store, 'latest_benchmark_sessions'):
            return []
        try:
            self._benchmark_history_cache = list(store.latest_benchmark_sessions(limit=max(6, int(limit))))
        except Exception:
            logger.exception('[BENCHMARK] No se pudo leer el historial de sesiones')
            return []
        return self._benchmark_history_cache[:max(1, int(limit))]

    @staticmethod
    def _benchmark_signature(profile, components, suite=None):
        normalized = tuple(sorted(str(x or '').strip().lower() for x in (components or []) if str(x or '').strip()))
        suite = suite if isinstance(suite, dict) else {}
        method = str(suite.get('benchmark_method') or 'LEGACY_UNVERSIONED').strip().upper()
        system = suite.get('system_suite') if isinstance(suite.get('system_suite'), dict) else {}
        ssd = system.get('ssd') if isinstance(system.get('ssd'), dict) else {}
        ssd_identity = (str(ssd.get('path_root') or '').strip().casefold(), str(ssd.get('io_mode') or 'LEGACY').strip().upper()) if 'ssd' in normalized else ('', '')
        return str(profile or '').strip().upper(), normalized, method, ssd_identity

    def _benchmark_previous_equivalent(self, sessions):
        current = self._visual_bench if isinstance(self._visual_bench, dict) else {}
        if not current:
            return None
        current_sig = self._benchmark_signature(
            current.get('profile') or 'standard',
            current.get('selected_components') or ['gpu', 'cpu', 'ram'], current,
        )
        current_ts = _num(current.get('timestamp'))
        live = getattr(self.app, 'latest_telemetry', {}) or {}
        current_cpu = str(live.get('cpu_name') or '').strip().lower()
        current_gpu = str(live.get('gpu_name') or '').strip().lower()
        for session in sessions:
            if not isinstance(session, dict):
                continue
            suite = session.get('suite') if isinstance(session.get('suite'), dict) else {}
            sig = self._benchmark_signature(session.get('profile') or suite.get('profile'), session.get('components') or ['gpu', 'cpu', 'ram'], suite)
            if sig != current_sig:
                continue
            hardware = session.get('hardware') if isinstance(session.get('hardware'), dict) else {}
            old_cpu = str(hardware.get('cpu_name') or '').strip().lower()
            old_gpu = str(hardware.get('gpu_name') or '').strip().lower()
            if current_cpu and old_cpu and current_cpu != old_cpu:
                continue
            if current_gpu and old_gpu and current_gpu != old_gpu:
                continue
            if current_ts is not None and abs(float(session.get('ts') or 0) - current_ts) < 1.0:
                continue
            return session
        return None

    def _render_benchmark_history(self):
        sessions = self._benchmark_history_sessions(limit=6)
        card = self._card(); card.pack(fill='x', padx=8, pady=(5, 10))
        head = ctk.CTkFrame(card, fg_color='transparent'); head.pack(fill='x', padx=14, pady=(11, 3))
        ctk.CTkLabel(head, text='Historial de benchmarks', font=(FONT, 12, 'bold'), text_color=TEXT, anchor='w').pack(side='left')
        ctk.CTkLabel(head, text=f'{len(sessions)} ejecución' + ('' if len(sessions) == 1 else 'es') + ' reciente(s)', font=(FONT, 8, 'bold'), text_color=CYAN if sessions else MUTED).pack(side='right')
        ctk.CTkLabel(card, text='Compara sólo sesiones de este PC con el mismo perfil y hardware compatible. No crea rankings externos.', font=(FONT, 8), text_color=MUTED, anchor='w', justify='left', wraplength=1030).pack(fill='x', padx=14, pady=(0, 7))

        previous = self._benchmark_previous_equivalent(sessions)
        current = self._visual_bench if isinstance(self._visual_bench, dict) else None
        if previous is not None and current:
            prev_suite = previous.get('suite') if isinstance(previous.get('suite'), dict) else {}
            compare_box = ctk.CTkFrame(card, fg_color=theme_color('#091827'), border_width=1, border_color=BORDER, corner_radius=8)
            compare_box.pack(fill='x', padx=12, pady=(0, 8))
            try:
                prev_date = dt.datetime.fromtimestamp(float(previous.get('ts') or 0)).strftime('%d-%m-%Y %H:%M')
            except Exception:
                prev_date = 'prueba anterior'
            ctk.CTkLabel(compare_box, text=f'Comparación con la última prueba equivalente · {prev_date}', font=(FONT, 9, 'bold'), text_color=TEXT2, anchor='w').pack(fill='x', padx=10, pady=(7, 3))
            parts = []
            for key, label in (('gpu', 'GPU/FPS'), ('cpu', 'CPU'), ('ram', 'RAM')):
                new_value, _ = self._benchmark_history_value(current, key)
                old_value, _ = self._benchmark_history_value(prev_suite, key)
                if new_value is None or old_value in (None, 0):
                    continue
                delta = ((new_value - old_value) / abs(old_value)) * 100.0
                parts.append(f"{label} {'+' if delta >= 0 else ''}{delta:.1f}%")
            ctk.CTkLabel(compare_box, text=' · '.join(parts) if parts else 'No hay métricas equivalentes suficientes para calcular variaciones.', font=(FONT, 9, 'bold'), text_color=CYAN if parts else MUTED, anchor='w', justify='left', wraplength=1000).pack(fill='x', padx=10, pady=(0, 7))

        if not sessions:
            ctk.CTkLabel(card, text='Aún no hay sesiones completas guardadas. La próxima ejecución se conservará automáticamente.', font=(FONT, 9), text_color=TEXT2, anchor='w').pack(fill='x', padx=14, pady=(2, 11))
            return

        for session in sessions[:5]:
            suite = session.get('suite') if isinstance(session.get('suite'), dict) else {}
            profile = str(session.get('profile') or suite.get('profile') or 'LOCAL').upper()
            try:
                stamp = dt.datetime.fromtimestamp(float(session.get('ts') or 0)).strftime('%d-%m-%Y · %H:%M')
            except Exception:
                stamp = 'Fecha N/A'
            row = ctk.CTkFrame(card, fg_color=CARD2, border_width=1, border_color=BORDER, corner_radius=7)
            row.pack(fill='x', padx=12, pady=3); row.grid_columnconfigure(1, weight=1)
            left = ctk.CTkFrame(row, fg_color='transparent'); left.grid(row=0, column=0, sticky='nw', padx=(9, 12), pady=7)
            ctk.CTkLabel(left, text=stamp, font=(FONT, 8, 'bold'), text_color=TEXT2, anchor='w').pack(anchor='w')
            ctk.CTkLabel(left, text=profile.title(), font=(FONT, 7), text_color=MUTED, anchor='w').pack(anchor='w', pady=(1, 0))
            values = []
            for key, label in (('gpu', 'GPU'), ('cpu', 'CPU'), ('ram', 'RAM'), ('ssd', 'SSD')):
                _value, display = self._benchmark_history_value(suite, key)
                if display != 'N/A': values.append(f'{label}: {display}')
            ctk.CTkLabel(row, text='  ·  '.join(values) if values else 'Sin métricas válidas guardadas', font=(FONT, 8, 'bold'), text_color=TEXT, anchor='w', justify='left', wraplength=760).grid(row=0, column=1, sticky='ew', padx=(0, 9), pady=9)

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
        path = str((game or {}).get('exe') or (game or {}).get('name') or '').strip()
        override = str((game or {}).get('artwork_override') or '').strip()
        identity = str((game or {}).get('name') or '').strip().lower()
        title_hint = str((game or {}).get('display_name') or '').strip()
        source_hint = str((game or {}).get('source') or '').strip().upper()
        key = (identity, path.lower(), override.lower(), title_hint.casefold(), source_hint, tuple(size))
        pil = self._game_artwork_cache.get(key)
        if pil is None:
            pil, source, resolved_path = load_game_artwork(
                path, size=size, override_path=override or None,
                title_hint=title_hint or None, source_hint=source_hint or None,
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
        # No capamos a 360: al hacerlo, tres cards podían sobrepasar/recortarse
        # con escalado DPI de Windows. El grid reparte el ancho real por igual.
        card_width = max(270, min(520, card_width))
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
                    payload = load_game_artwork(
                        job['path'], size=job['size'], override_path=job['override'] or None,
                        title_hint=job.get('title_hint') or None, source_hint=job.get('source_hint') or None,
                    )
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
            action('Quitar de biblioteca', lambda g=dict(game): self._remove_game_from_library(g))
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
        for col in range(columns):
            library.grid_columnconfigure(col, weight=1, uniform='game_library_cards')

        for index, game in enumerate(registered):
            row, col = divmod(index, columns)
            active = bool(game.get('active'))
            excluded = bool(game.get('excluded'))
            manual = bool(game.get('manual'))
            border = GREEN if active else (AMBER if excluded else theme_color('#26354d'))
            card = ctk.CTkFrame(
                library, width=card_width, height=art_size[1] + 82,
                fg_color=theme_color('#111d2e'), border_width=1,
                border_color=border, corner_radius=10,
            )
            # Grid uniforme: cada card de una fila recibe exactamente el mismo
            # ancho disponible. Evita que la tercera quede recortada por DPI.
            left_pad = 0 if col == 0 else gap // 2
            right_pad = 0 if col == columns - 1 else gap // 2
            card.grid(row=row, column=col, sticky='nsew', padx=(left_pad, right_pad), pady=(0, gap))
            card.grid_propagate(False)
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

            path = str((game or {}).get('exe') or (game or {}).get('name') or '').strip()
            override = str((game or {}).get('artwork_override') or '').strip()
            identity = str((game or {}).get('name') or '').strip().lower()
            title_hint = str((game or {}).get('display_name') or '').strip()
            source_hint = str((game or {}).get('source') or '').strip().upper()
            key = (identity, path.lower(), override.lower(), title_hint.casefold(), source_hint, tuple(art_size))
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
                    'title_hint': title_hint, 'source_hint': source_hint,
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

            remove_btn = self._button(
                name_row, 'Eliminar', lambda g=dict(game): self._remove_game_from_library(g),
                variant='ghost', width=62, height=25,
            )
            remove_btn.configure(
                border_width=0, corner_radius=6, font=(FONT, 8, 'bold'),
                hover_color=theme_color('#55202a'), text_color=theme_color('#f87171'),
            )
            remove_btn.pack(side='right', padx=(5, 0))

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
                (card, art_host, art_label, body, name_row, name, remove_btn, meta_row),
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

    def _remove_game_from_library(self, game):
        detector = getattr(self.app, 'game_detector', None)
        if detector is None or not hasattr(detector, 'remove_game_from_library'):
            return
        game = dict(game or {})
        exe_name = game.get('name')
        title = str(game.get('display_name') or exe_name or 'este juego')
        if not messagebox.askyesno(
            'CorePulse · Biblioteca',
            f'¿Quitar {title} de la biblioteca de CorePulse?\n\nNo se desinstalará el juego ni se borrarán archivos del disco.'
        ):
            return
        if detector.remove_game_from_library(exe_name):
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

    def _windows_summary_metrics(self, section):
        """Resumen REAL_OR_NA para las tarjetas de Windows.

        Nunca estima consumo. "Más pesado" sólo se usa cuando existe RAM medida;
        en Estabilidad/Controladores se muestra el elemento más relevante según la
        clasificación real ya producida por sus analizadores.
        """
        data = {
            'startup': self._startup,
            'services': self._services,
            'crashes': self._crashes,
            'drivers': self._drivers,
        }.get(section)
        count_labels = {
            'startup': 'Elementos analizados',
            'services': 'Servicios analizados',
            'crashes': 'Eventos analizados',
            'drivers': 'Controladores analizados',
        }
        label = count_labels.get(section, 'Elementos analizados')
        if data is None:
            return label, 'Sin ejecutar', 'Más pesado / importante', 'Sin ejecutar'
        if not isinstance(data, dict) or data.get('error'):
            return label, 'N/A', 'Más pesado / importante', 'N/A'

        items = [x for x in (data.get('items') or []) if isinstance(x, dict)]
        if section == 'startup':
            count = int(data.get('count') if data.get('count') is not None else len(items))
            measured = []
            for item in items:
                mem = _num(item.get('running_memory_mb'))
                if mem is not None:
                    measured.append((mem, item))
            if measured:
                mem, item = max(measured, key=lambda pair: pair[0])
                heavy = f"{item.get('name') or 'Elemento'} · {mem:.1f} MB"
                heavy_label = 'Más pesado ahora'
            else:
                high = next((x for x in items if str(x.get('impact') or '').upper().startswith('ALTO')), None)
                if high is not None:
                    heavy = f"{high.get('name') or 'Elemento'} · degradación registrada por Windows"
                    heavy_label = 'Más importante'
                else:
                    heavy = 'N/A · sin RAM medible en ejecución'
                    heavy_label = 'Más pesado ahora'
            return label, str(count), heavy_label, _short(heavy, 78)

        if section == 'services':
            count = int(data.get('count') if data.get('count') is not None else len(items))
            measured = []
            for item in items:
                mem = _num(item.get('memory_mb'))
                if mem is not None:
                    measured.append((mem, item))
            if measured:
                mem, item = max(measured, key=lambda pair: pair[0])
                name = item.get('DisplayName') or item.get('Name') or 'Servicio'
                heavy = f'{name} · {mem:.1f} MB'
            else:
                heavy = 'N/A · sin RAM medible en ejecución'
            return label, str(count), 'Más pesado ahora', _short(heavy, 78)

        if section == 'crashes':
            raw_count = data.get('matched_total')
            count = int(raw_count if raw_count is not None else len(items))
            # Sin puntajes sintéticos: se respeta la clasificación ya existente
            # del analizador (hardware/BSOD -> energía -> aplicación).
            relevant = next((x for x in items if str(x.get('kind') or '').lower() in ('whea', 'bsod_bugcheck')), None)
            if relevant is None:
                relevant = next((x for x in items if str(x.get('kind') or '').lower() in ('kernel_power', 'unexpected_shutdown')), None)
            if relevant is None:
                relevant = next((x for x in items if str(x.get('kind') or '').lower() in ('app_error', 'app_hang')), None)
            if relevant is not None:
                heavy = (
                    relevant.get('component_name') or relevant.get('ApplicationName')
                    or relevant.get('user_label') or relevant.get('ProviderName') or 'Evento registrado'
                )
            else:
                app_stats = [x for x in (data.get('app_stats') or []) if isinstance(x, dict)]
                top_app = max(app_stats, key=lambda x: int(x.get('Total') or 0), default=None)
                if top_app is not None:
                    heavy = f"{top_app.get('ApplicationName') or 'Aplicación'} · {int(top_app.get('Total') or 0)} evento(s)"
                else:
                    heavy = 'N/A · sin evento prioritario detectado'
            return label, str(count), 'Evento más relevante', _short(heavy, 78)

        if section == 'drivers':
            count = int(data.get('count') if data.get('count') is not None else len(items))
            problem = next((x for x in items if str(x.get('status') or '').upper() in ('DEVICE_PROBLEM', 'UNSIGNED')), None)
            # analyze_drivers ya devuelve los elementos en orden de prioridad.
            # No se crea un score adicional para esta tarjeta.
            important = problem or (items[0] if items else None)
            if important is not None:
                name = important.get('DeviceName') or 'Controlador'
                status = _driver_status_label(important.get('status'))
                heavy = f'{name} · {status}' if status and status != 'N/A' else str(name)
            else:
                heavy = 'N/A · sin elemento prioritario disponible'
            return label, str(count), 'Más importante', _short(heavy, 78)

        return label, str(len(items)), 'Más pesado / importante', 'N/A'

    def _windows_summary_job(self, section):
        return {
            'startup': ('startup', analyze_startup),
            'services': ('services', analyze_services),
            'crashes': ('crashes', lambda: analyze_crashes(7)),
            'drivers': ('drivers', analyze_drivers),
        }.get(section, ('startup', analyze_startup))

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
            ('summary', 'Resumen rápido'),
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
        section_head.pack(fill='x', padx=10, pady=(0, 6))
        ctk.CTkLabel(
            section_head, text='Diagnósticos de Windows', font=(FONT, 13, 'bold'),
            text_color=TEXT, anchor='w', justify='left'
        ).pack(anchor='w')
        ctk.CTkLabel(
            section_head,
            text='Ejecuta cada análisis desde su tarjeta. Cuando termine, “Ver más” abre la vista detallada con todos los elementos devueltos por Windows.',
            font=(FONT, 9), text_color=MUTED, anchor='w', justify='left', wraplength=1040
        ).pack(fill='x', pady=(2, 6))

        self._windows_buttons = {}
        grid = ctk.CTkFrame(self.body, fg_color='transparent')
        grid.pack(fill='x', padx=3, pady=(0, 7))
        for col in range(2):
            grid.grid_columnconfigure(col, weight=1, uniform='windows_summary_cards')
        for row in range(2):
            grid.grid_rowconfigure(row, minsize=238, weight=1, uniform='windows_summary_rows')

        specs = (
            ('startup', 'Inicio', 'Programas y entradas que arrancan con Windows.', CYAN),
            ('services', 'Servicios', 'Servicios instalados, estado y consumo RAM observable.', CYAN),
            ('crashes', 'Estabilidad', 'BSOD, WHEA, apagados y fallos de aplicaciones.', AMBER),
            ('drivers', 'Controladores', 'Dispositivos, firma, estado y antigüedad de drivers.', GREEN),
        )
        for index, (key, title, description, accent) in enumerate(specs):
            row, col = divmod(index, 2)
            status, status_color = self._windows_section_status(key)
            count_label, count_value, heavy_label, heavy_value = self._windows_summary_metrics(key)
            job_name, job_fn = self._windows_summary_job(key)
            data = getattr(self, '_' + key, None)
            running = job_name in self._jobs

            card = self._card(grid)
            card.configure(height=238, corner_radius=12)
            card.grid_propagate(False)
            card.grid(row=row, column=col, sticky='nsew', padx=6, pady=6)

            accent_bar = ctk.CTkFrame(card, fg_color=accent, width=4, corner_radius=3)
            accent_bar.pack(side='left', fill='y', padx=(0, 0), pady=12)

            content = ctk.CTkFrame(card, fg_color='transparent')
            content.pack(side='left', fill='both', expand=True, padx=(13, 13), pady=(12, 11))

            head = ctk.CTkFrame(content, fg_color='transparent')
            head.pack(fill='x')
            ctk.CTkLabel(
                head, text=title, font=(FONT, 14, 'bold'), text_color=TEXT,
                anchor='w', justify='left'
            ).pack(side='left', fill='x', expand=True)
            ctk.CTkLabel(
                head, text='Analizando…' if running else status, font=(FONT, 9, 'bold'),
                text_color=accent if running else status_color, anchor='e', justify='right'
            ).pack(side='right', padx=(8, 0))

            ctk.CTkLabel(
                content, text=description, font=(FONT, 9), text_color=MUTED,
                anchor='w', justify='left', wraplength=430
            ).pack(fill='x', pady=(4, 9))

            stats = ctk.CTkFrame(content, fg_color='transparent')
            stats.pack(fill='x', pady=(0, 9))
            stats.grid_columnconfigure(0, weight=2, uniform='windows_card_stats')
            stats.grid_columnconfigure(1, weight=3, uniform='windows_card_stats')

            count_box = ctk.CTkFrame(stats, fg_color=CARD2, border_width=1, border_color=BORDER, corner_radius=8)
            count_box.grid(row=0, column=0, sticky='nsew', padx=(0, 5))
            ctk.CTkLabel(count_box, text=count_label.upper(), font=(FONT, 7, 'bold'), text_color=MUTED, anchor='w').pack(fill='x', padx=9, pady=(7, 1))
            ctk.CTkLabel(count_box, text=count_value, font=(FONT, BENCH_FONT_SCENE_VALUE, 'bold'), text_color=TEXT, anchor='w').pack(fill='x', padx=9, pady=(0, 7))

            heavy_box = ctk.CTkFrame(stats, fg_color=CARD2, border_width=1, border_color=BORDER, corner_radius=8)
            heavy_box.grid(row=0, column=1, sticky='nsew', padx=(5, 0))
            ctk.CTkLabel(heavy_box, text=heavy_label.upper(), font=(FONT, 7, 'bold'), text_color=MUTED, anchor='w').pack(fill='x', padx=9, pady=(7, 1))
            ctk.CTkLabel(
                heavy_box, text=heavy_value, font=(FONT, 9, 'bold'), text_color=TEXT2,
                anchor='w', justify='left', wraplength=245
            ).pack(fill='x', padx=9, pady=(0, 7))

            actions = ctk.CTkFrame(content, fg_color='transparent')
            actions.pack(side='bottom', fill='x', pady=(1, 0))
            actions.grid_columnconfigure(0, weight=1, uniform='windows_card_actions')
            actions.grid_columnconfigure(1, weight=1, uniform='windows_card_actions')

            run_btn = self._button(
                actions,
                'Analizando…' if running else ('Actualizar análisis' if isinstance(data, dict) else 'Ejecutar análisis'),
                lambda n=job_name, f=job_fn: self._run_windows(n, f),
                variant='primary', height=32,
            )
            run_btn.grid(row=0, column=0, sticky='ew', padx=(0, 5))
            self._windows_buttons[job_name] = run_btn
            if running:
                try:
                    run_btn.configure(state='disabled')
                except Exception:
                    pass

            more_btn = self._button(
                actions, 'Ver más', lambda k=key: self._set_windows_section(k),
                variant='secondary', height=32,
            )
            more_btn.grid(row=0, column=1, sticky='ew', padx=(5, 0))
            # La vista detallada representa el diagnóstico ya ejecutado. Antes de
            # tener un resultado real, la tarjeta conserva el acceso bloqueado.
            if not isinstance(data, dict) or running:
                try:
                    more_btn.configure(state='disabled')
                except Exception:
                    pass

    def _render_windows(self):
        self._title('Análisis de Windows','Inicio, servicios, estabilidad y controladores en vistas separadas.')
        # V146 — la portada de Windows son tarjetas grandes. Las tablas completas
        # se abren sólo con “Ver más” y la vista detallada vuelve al resumen.
        section = str(getattr(self, '_windows_section', 'summary') or 'summary')
        if section == 'summary':
            self._render_windows_summary()
            return

        detail_nav = ctk.CTkFrame(self.body, fg_color='transparent')
        detail_nav.pack(fill='x', padx=8, pady=(2, 8))
        self._button(
            detail_nav, 'Volver al resumen de Windows',
            lambda: self._set_windows_section('summary'), variant='ghost', width=208, height=31
        ).pack(side='left')

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
            items = list(data.get('items') or [])
            enabled = int(data.get('enabled_count') if data.get('enabled_count') is not None else sum(1 for x in items if x.get('enabled', True)))
            disabled = int(data.get('disabled_count') or 0)
            self._kv(card, 'Elementos habilitados', enabled)
            self._kv(card, 'Deshabilitados por CorePulse', disabled)
            ctk.CTkLabel(
                card, text='CorePulse sólo permite deshabilitar entradas de usuario reversibles. Componentes globales, Microsoft, seguridad y sistema permanecen en modo observación.',
                font=(FONT, 9), text_color=MUTED, wraplength=990, justify='left', anchor='w'
            ).pack(fill='x', padx=14, pady=(4, 8))

            total = len(items)
            page_size = max(1, int(getattr(self, '_startup_page_size', 30) or 30))
            page_count = max(1, (total + page_size - 1) // page_size)
            page = max(0, min(int(getattr(self, '_startup_page', 0) or 0), page_count - 1))
            self._startup_page = page
            start = page * page_size
            end = min(total, start + page_size)
            visible_items = items[start:end]

            pager = ctk.CTkFrame(card, fg_color='transparent')
            pager.pack(fill='x', padx=14, pady=(0, 5))
            shown_text = (
                f'Mostrando {start + 1}–{end} de {total} · Página {page + 1} de {page_count}'
                if total else 'No hay elementos de inicio para mostrar'
            )
            ctk.CTkLabel(
                pager, text=shown_text, font=(FONT, 9), text_color=MUTED,
                anchor='w', justify='left'
            ).pack(side='left', fill='x', expand=True)
            if page_count > 1:
                next_btn = self._button(
                    pager, 'Siguiente', lambda: self._set_startup_page(page + 1),
                    variant='ghost', width=92, height=27
                )
                next_btn.pack(side='right', padx=(6, 0))
                prev_btn = self._button(
                    pager, 'Anterior', lambda: self._set_startup_page(page - 1),
                    variant='ghost', width=92, height=27
                )
                prev_btn.pack(side='right')
                if page <= 0:
                    try: prev_btn.configure(state='disabled')
                    except Exception: pass
                if page >= page_count - 1:
                    try: next_btn.configure(state='disabled')
                    except Exception: pass

            for item in visible_items:
                row = ctk.CTkFrame(card, fg_color=CARD2, border_width=1, border_color=BORDER, corner_radius=8)
                row.pack(fill='x', padx=12, pady=4)
                left = ctk.CTkFrame(row, fg_color='transparent'); left.pack(side='left', fill='x', expand=True, padx=11, pady=9)
                name = str(item.get('name') or 'Elemento de inicio')
                publisher = str(item.get('publisher') or 'N/A')
                state_label = str(item.get('state') or ('Habilitado' if item.get('enabled', True) else 'Deshabilitado'))
                impact = _impact_label(item.get('impact'))
                state_tone = GREEN if item.get('enabled', True) else AMBER
                ctk.CTkLabel(left, text=name, font=(FONT, 10, 'bold'), text_color=TEXT, anchor='w').pack(fill='x')
                ctk.CTkLabel(left, text=f'{publisher} · {state_label} · Impacto {impact}', font=(FONT, 8, 'bold'), text_color=state_tone, anchor='w').pack(fill='x', pady=(2, 1))
                detail = _short(item.get('command') or 'Comando no disponible', 150)
                ctk.CTkLabel(left, text=detail, font=(FONT, 8), text_color=MUTED, anchor='w', justify='left', wraplength=700).pack(fill='x')
                location = _short(item.get('location') or 'Ubicación no disponible', 120)
                ctk.CTkLabel(left, text=f'Ubicación: {location}', font=(FONT, 8), text_color=MUTED, anchor='w', justify='left', wraplength=700).pack(fill='x', pady=(1, 0))
                source_id = item.get('source_id')
                if item.get('can_restore') and source_id:
                    self._button(row, 'Restaurar', lambda sid=source_id: self._startup_action(sid, restore=True), variant='secondary', width=104, height=28).pack(side='right', padx=10)
                elif item.get('safe_to_disable') and source_id:
                    self._button(row, 'Deshabilitar', lambda sid=source_id, nm=name: self._startup_action(sid, restore=False, name=nm), variant='ghost', width=104, height=28).pack(side='right', padx=10)
                else:
                    ctk.CTkLabel(row, text='Sólo observar', font=(FONT, 8, 'bold'), text_color=MUTED).pack(side='right', padx=12)
            if not items:
                ctk.CTkLabel(card, text='No se detectaron elementos de inicio en esta consulta.', font=(FONT, 9), text_color=MUTED).pack(anchor='w', padx=14, pady=(0, 12))
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
            all_local = list(data.get('items') or [])
            relevant_local = [
                x for x in all_local
                if int(x.get('hardware_priority') or 0) > 0
                or str(x.get('status') or '').upper() in {'DEVICE_PROBLEM', 'UNSIGNED'}
            ]
            problems = int(data.get('device_problems') or 0)
            unsigned = int(data.get('unsigned') or 0)
            updates = self._driver_updates if isinstance(self._driver_updates, dict) else None
            update_count = len(list(updates.get('items') or [])) if updates else None
            scanning = 'driver_updates_scan' in self._jobs

            # V323 Driver Hub 2.0: la pantalla principal prioriza decisiones, no inventario.
            hero = ctk.CTkFrame(card, fg_color='transparent')
            hero.pack(fill='x', padx=12, pady=(4, 8))
            hero_left = ctk.CTkFrame(hero, fg_color='transparent')
            hero_left.pack(side='left', fill='x', expand=True)
            ctk.CTkLabel(hero_left, text='DRIVER HUB 3.0', font=(FONT, 15, 'bold'), text_color=TEXT, anchor='w').pack(fill='x')
            ctk.CTkLabel(
                hero_left,
                text='Búsqueda multi-fuente · fabricante oficial primero cuando puede validarse · Microsoft Catalog como respaldo.',
                font=(FONT, 9), text_color=MUTED, anchor='w', justify='left', wraplength=930,
            ).pack(fill='x', pady=(2, 0))
            hero_state = 'ESCANEANDO' if scanning else 'LISTO'
            hero_color = CYAN if scanning else GREEN
            state_box = ctk.CTkFrame(hero, fg_color=CARD2, border_width=1, border_color=hero_color, corner_radius=7)
            state_box.pack(side='right', padx=(10, 0))
            ctk.CTkLabel(state_box, text=hero_state, font=(FONT, 8, 'bold'), text_color=hero_color).pack(padx=10, pady=5)

            summary = ctk.CTkFrame(card, fg_color='transparent')
            summary.pack(fill='x', padx=10, pady=(0, 8))
            for col in range(3):
                summary.grid_columnconfigure(col, weight=1, uniform='driver_hub_summary')
            local_attention = problems + unsigned
            summary_items = (
                ('HARDWARE IMPORTANTE', str(int(data.get('important_count') or 0)), 'GPU · red · audio · chipset · almacenamiento', CYAN),
                ('REQUIERE ATENCIÓN', str(local_attention), f'{problems} incidencia(s) · {unsigned} sin firma', RED if local_attention else GREEN),
                ('ACTUALIZACIONES', '—' if update_count is None else str(update_count), 'Sin buscar' if update_count is None else ('Compatibles confirmadas' if update_count else 'No confirmadas'), CYAN if update_count else GREEN),
            )
            for idx, (label, value, detail, accent) in enumerate(summary_items):
                cell = ctk.CTkFrame(summary, fg_color=CARD2, border_width=1, border_color=BORDER, corner_radius=10, height=82)
                cell.grid(row=0, column=idx, sticky='ew', padx=4)
                cell.grid_propagate(False)
                ctk.CTkFrame(cell, width=4, fg_color=accent, corner_radius=8).pack(side='left', fill='y', padx=(1, 0), pady=1)
                body = ctk.CTkFrame(cell, fg_color='transparent')
                body.pack(side='left', fill='both', expand=True, padx=10, pady=6)
                ctk.CTkLabel(body, text=label, font=(FONT, 8, 'bold'), text_color=accent, anchor='w').pack(fill='x')
                value_label = ctk.CTkLabel(body, text=value, font=(FONT, 17, 'bold'), text_color=TEXT, anchor='w')
                value_label.pack(fill='x', pady=(2, 0))
                detail_label = ctk.CTkLabel(body, text=detail, font=(FONT, 8), text_color=MUTED, anchor='w')
                detail_label.pack(fill='x', pady=(1, 0))
                if idx == 2:
                    self._driver_summary_updates_value = value_label
                    self._driver_summary_updates_detail = detail_label

            attention = [x for x in relevant_local if str(x.get('status') or '').upper() in {'DEVICE_PROBLEM', 'UNSIGNED'}]
            if attention:
                if not self._driver_attention_initialized:
                    self._driver_attention_selected = {str(x.get('DeviceID') or '') for x in attention if str(x.get('DeviceID') or '')}
                    self._driver_attention_initialized = True
                section = ctk.CTkFrame(card, fg_color='transparent')
                section.pack(fill='x', padx=14, pady=(0, 7))
                section_head = ctk.CTkFrame(section, fg_color='transparent')
                section_head.pack(fill='x', pady=(0, 4))
                head_text = ctk.CTkFrame(section_head, fg_color='transparent')
                head_text.pack(side='left', fill='x', expand=True)
                ctk.CTkLabel(head_text, text='Atención local', font=(FONT, 10, 'bold'), text_color=TEXT, anchor='w').pack(fill='x')
                ctk.CTkLabel(head_text, text='Selecciona qué dispositivos quieres comprobar primero.', font=(FONT, 8), text_color=MUTED, anchor='w').pack(fill='x', pady=(1, 0))
                self._driver_attention_search_button = self._button(
                    section_head, '', self._scan_selected_attention, variant='secondary', width=160, height=29
                )
                self._driver_attention_search_button.pack(side='right', padx=(10, 0))
                self._refresh_attention_search_button()
                self._driver_attention_widgets = {}
                scan_map = {}
                update_map = {}
                if isinstance(self._driver_updates, dict):
                    for scan_item in (self._driver_updates.get('device_results') or []):
                        if isinstance(scan_item, dict):
                            scan_map[str(scan_item.get('instance_id') or '')] = scan_item
                    for update_item in (self._driver_updates.get('items') or []):
                        if isinstance(update_item, dict):
                            update_map[str(update_item.get('instance_id') or '')] = update_item
                checking_ids = set(getattr(self, '_driver_attention_scanning_ids', set()) or set())

                for item in attention[:4]:
                    problem = str(item.get('status') or '').upper() == 'DEVICE_PROBLEM'
                    accent = RED if problem else AMBER
                    device_id = str(item.get('DeviceID') or '')
                    row = ctk.CTkFrame(section, fg_color=CARD2, border_width=1, border_color=BORDER, corner_radius=9, height=76)
                    row.pack(fill='x', pady=2)
                    row.pack_propagate(False)
                    ctk.CTkFrame(row, width=4, fg_color=accent, corner_radius=8).pack(side='left', fill='y', padx=(1, 0), pady=1)
                    var = ctk.BooleanVar(value=device_id in self._driver_attention_selected)
                    check = ctk.CTkCheckBox(
                        row, text='', variable=var, width=24, height=24, checkbox_width=20, checkbox_height=20,
                        corner_radius=5, border_width=2, fg_color=accent, hover_color=accent, border_color=ACTION_BORDER,
                        command=lambda did=device_id, v=var: self._toggle_driver_attention_selection(did, bool(v.get())),
                    )
                    check.pack(side='left', padx=(10, 5))
                    info = ctk.CTkFrame(row, fg_color='transparent')
                    info.pack(side='left', fill='x', expand=True, padx=(5, 10), pady=6)
                    ctk.CTkLabel(info, text=str(item.get('DeviceName') or 'Dispositivo'), font=(FONT, 9, 'bold'), text_color=TEXT, anchor='w').pack(fill='x')
                    detail = str(item.get('problem_detail') or ('Driver sin firma digital' if not problem else 'Windows reporta una incidencia del dispositivo'))
                    ctk.CTkLabel(info, text=detail, font=(FONT, 8), text_color=accent, anchor='w', justify='left').pack(fill='x', pady=(1, 0))

                    scan_item = scan_map.get(device_id)
                    update_item = update_map.get(device_id)
                    if device_id in checking_ids:
                        scan_text, scan_color = 'Buscando una versión compatible…', CYAN
                    elif update_item:
                        scan_text, scan_color = f"Disponible {update_item.get('available_version') or 'versión superior'} · instalada {update_item.get('current_version') or 'N/A'}", GREEN
                    elif scan_item:
                        scan_state = str(scan_item.get('status') or '').upper()
                        if scan_state == 'ERROR':
                            scan_text, scan_color = 'No se pudo verificar online · puedes reintentar', AMBER
                        else:
                            scan_text, scan_color = 'Sin actualización compatible confirmada', GREEN
                    else:
                        scan_text, scan_color = 'Aún no se ha buscado una actualización online', MUTED
                    scan_label = ctk.CTkLabel(info, text=scan_text, font=(FONT, 8, 'bold'), text_color=scan_color, anchor='w', justify='left')
                    scan_label.pack(fill='x', pady=(2, 0))

                    right = ctk.CTkFrame(row, fg_color='transparent')
                    right.pack(side='right', padx=10, pady=7)
                    state = ctk.CTkLabel(
                        right, text='INCIDENCIA' if problem else 'SIN FIRMA', font=(FONT, 8, 'bold'), text_color=accent,
                        fg_color=CARD, corner_radius=6, padx=8, pady=3
                    )
                    state.pack(anchor='e', pady=(0, 5))

                    if update_item:
                        downloaded = bool(update_item.get('is_downloaded'))
                        if downloaded:
                            action_text = 'Instalar'
                            action_cmd = lambda u=update_item: self._install_driver_update(
                                str(u.get('update_id') or ''), int(u.get('revision') or 0), str(u.get('device_name') or ''),
                                firmware=str(u.get('driver_class') or '').upper() == 'FIRMWARE', current_inf=str(u.get('current_inf') or ''), metadata=u
                            )
                        else:
                            action_text = 'Descargar'
                            action_cmd = lambda u=update_item: self._download_driver_update(
                                str(u.get('update_id') or ''), int(u.get('revision') or 0), str(u.get('device_name') or ''), metadata=u
                            )
                    elif device_id in checking_ids:
                        action_text = 'Buscando…'
                        action_cmd = lambda: None
                    elif scan_item:
                        action_text = 'Reintentar'
                        action_cmd = lambda did=device_id: self._scan_one_attention(did)
                    else:
                        action_text = 'Buscar actualización'
                        action_cmd = lambda did=device_id: self._scan_one_attention(did)
                    action_btn = self._button(right, action_text, action_cmd, variant='primary', width=132, height=27)
                    action_btn.pack(anchor='e')
                    if device_id in checking_ids:
                        try: action_btn.configure(state='disabled')
                        except Exception: pass

                    self._driver_attention_widgets[device_id] = {
                        'scan_label': scan_label,
                        'action_button': action_btn,
                        'item': item,
                    }

            self._render_driver_update_center(card)

            inv_head = ctk.CTkFrame(card, fg_color='transparent')
            inv_head.pack(fill='x', padx=14, pady=(5, 4))
            left = ctk.CTkFrame(inv_head, fg_color='transparent')
            left.pack(side='left', fill='x', expand=True)
            ctk.CTkLabel(left, text='Inventario avanzado', font=(FONT, 10, 'bold'), text_color=TEXT, anchor='w').pack(fill='x')
            ctk.CTkLabel(
                left,
                text=f'{len(relevant_local)} controladores relevantes · la edad del paquete no se interpreta como actualización disponible.',
                font=(FONT, 8), text_color=MUTED, anchor='w', justify='left', wraplength=880,
            ).pack(fill='x', pady=(1, 0))
            self._button(
                inv_head, 'Ocultar inventario' if self._show_driver_inventory else 'Abrir inventario',
                self._toggle_driver_inventory, variant='ghost', width=132, height=29,
            ).pack(side='right', padx=(10, 0))

            if self._show_driver_inventory:
                total = len(relevant_local)
                page_size = 20
                page_count = max(1, (total + page_size - 1) // page_size)
                page = max(0, min(int(getattr(self, '_drivers_page', 0) or 0), page_count - 1))
                self._drivers_page = page
                start_i = page * page_size
                end_i = min(total, start_i + page_size)
                items = relevant_local[start_i:end_i]
                pager = ctk.CTkFrame(card, fg_color='transparent')
                pager.pack(fill='x', padx=14, pady=(0, 4))
                ctk.CTkLabel(pager, text=(f'Mostrando {start_i + 1}–{end_i} de {total}' if total else 'Sin controladores relevantes'), font=(FONT, 8), text_color=MUTED, anchor='w').pack(side='left', fill='x', expand=True)
                if page_count > 1:
                    next_btn = self._button(pager, 'Siguiente', lambda: self._set_drivers_page(page + 1), variant='ghost', width=88, height=26)
                    next_btn.pack(side='right', padx=(5, 0))
                    prev_btn = self._button(pager, 'Anterior', lambda: self._set_drivers_page(page - 1), variant='ghost', width=88, height=26)
                    prev_btn.pack(side='right')
                    if page <= 0:
                        try: prev_btn.configure(state='disabled')
                        except Exception: pass
                    if page >= page_count - 1:
                        try: next_btn.configure(state='disabled')
                        except Exception: pass
                rows = [[x.get('DeviceName') or 'N/A', x.get('DriverProviderName') or 'N/A', x.get('DriverVersion') or 'N/A', _driver_status_detail(x)] for x in items]
                self._render_compact_table(
                    card,
                    columns=[
                        {'title': 'Dispositivo', 'weight': 7, 'wrap': 310},
                        {'title': 'Proveedor', 'weight': 4, 'wrap': 170},
                        {'title': 'Versión instalada', 'weight': 3, 'wrap': 140},
                        {'title': 'Estado', 'weight': 5, 'wrap': 260},
                    ],
                    rows=rows,
                    empty_text='No se detectaron controladores relevantes con incidencias.',
                )

    @staticmethod
    def _driver_update_size_text(value):
        try:
            size = max(0, int(value or 0))
        except Exception:
            size = 0
        if not size:
            return 'Tamaño N/A'
        units = ('B', 'KB', 'MB', 'GB')
        amount = float(size)
        index = 0
        while amount >= 1024.0 and index < len(units) - 1:
            amount /= 1024.0
            index += 1
        return f'{amount:.1f} {units[index]}' if index else f'{int(amount)} {units[index]}'

    def _render_driver_update_center(self, parent):
        """Driver Hub 2.0: sólo actualizaciones compatibles y acciones útiles."""
        box = ctk.CTkFrame(parent, fg_color=BENCH_SURFACE_SOFT, border_width=1, border_color=ACTION_BORDER, corner_radius=10)
        box.pack(fill='x', padx=14, pady=(6, 4))

        result = self._driver_updates if isinstance(self._driver_updates, dict) else None
        scanning = 'driver_updates_scan' in self._jobs
        items = list(result.get('items') or []) if result else []
        bulk_busy = 'driver_updates_download_all' in self._jobs or 'driver_updates_install_all' in self._jobs or 'driver_updates_install_selected' in self._jobs

        head = ctk.CTkFrame(box, fg_color='transparent')
        head.pack(fill='x', padx=12, pady=(10, 7))
        title = ctk.CTkFrame(head, fg_color='transparent')
        title.pack(side='left', fill='x', expand=True)
        ctk.CTkLabel(title, text='ACTUALIZACIONES COMPATIBLES', font=(FONT, 10, 'bold'), text_color=CYAN, anchor='w').pack(fill='x')
        ctk.CTkLabel(
            title,
            text='CorePulse cruza la versión instalada con fuentes oficiales del fabricante y Microsoft Catalog. Sólo muestra una versión superior compatible confirmada.',
            font=(FONT, 8), text_color=TEXT2, anchor='w', justify='left', wraplength=790,
        ).pack(fill='x', pady=(2, 0))

        actions = ctk.CTkFrame(head, fg_color='transparent')
        actions.pack(side='right', padx=(10, 0))
        scan = self._button(actions, 'Buscando…' if scanning else 'Buscar hardware principal', self._scan_driver_updates, variant='primary', width=154, height=31)
        scan.pack(side='right')
        if scanning:
            try: scan.configure(state='disabled')
            except Exception: pass

        if items:
            selected = self._selected_driver_update_items()
            install_btn = self._button(
                actions,
                'Instalando…' if 'driver_updates_install_selected' in self._jobs else f'Instalar seleccionados ({len(selected)})',
                self._install_selected_driver_updates,
                variant='primary', width=166, height=31,
            )
            install_btn.pack(side='right', padx=(0, 6))
            download_btn = self._button(
                actions,
                'Descargando…' if 'driver_updates_download_all' in self._jobs else 'Descargar todo',
                self._download_all_driver_updates,
                variant='secondary', width=118, height=31,
            )
            download_btn.pack(side='right', padx=(0, 6))
            if bulk_busy or not selected:
                try: install_btn.configure(state='disabled')
                except Exception: pass
            if bulk_busy or all(bool(x.get('is_downloaded')) for x in items):
                try: download_btn.configure(state='disabled')
                except Exception: pass

        if scanning:
            scan_state = ctk.CTkFrame(box, fg_color=CARD2, border_width=1, border_color=BORDER, corner_radius=8)
            scan_state.pack(fill='x', padx=10, pady=(0, 9))
            ctk.CTkLabel(scan_state, text='Revisando GPU, red, audio, almacenamiento, Bluetooth y plataforma en paralelo…', font=(FONT, 9, 'bold'), text_color=CYAN, anchor='w').pack(fill='x', padx=10, pady=8)
            return

        if result is None:
            empty = ctk.CTkFrame(box, fg_color=CARD2, border_width=1, border_color=BORDER, corner_radius=8)
            empty.pack(fill='x', padx=10, pady=(0, 9))
            ctk.CTkLabel(empty, text='Listo para comprobar el hardware importante.', font=(FONT, 10, 'bold'), text_color=TEXT, anchor='w').pack(fill='x', padx=10, pady=(8, 1))
            ctk.CTkLabel(empty, text='El inventario local ya está hecho. La búsqueda online se ejecuta sólo al pulsar el botón y reutiliza caché reciente.', font=(FONT, 8), text_color=MUTED, anchor='w').pack(fill='x', padx=10, pady=(0, 8))
            return

        error = str(result.get('error') or '').strip()
        if error:
            err = ctk.CTkFrame(box, fg_color=CARD2, border_width=1, border_color=AMBER, corner_radius=8)
            err.pack(fill='x', padx=10, pady=(0, 9))
            ctk.CTkLabel(err, text='No se pudo completar la consulta', font=(FONT, 9, 'bold'), text_color=AMBER, anchor='w').pack(fill='x', padx=10, pady=(7, 1))
            ctk.CTkLabel(err, text=error, font=(FONT, 8), text_color=MUTED, anchor='w', justify='left', wraplength=1000).pack(fill='x', padx=10, pady=(0, 7))
            return

        checked = int(result.get('checked_devices') or 0)
        elapsed = float(result.get('elapsed_seconds') or 0.0)
        cache_hit = bool(result.get('cache_hit'))
        status = ctk.CTkFrame(box, fg_color='transparent')
        status.pack(fill='x', padx=12, pady=(0, 7))
        status_text = (
            f'{len(items)} actualización' + ('es' if len(items) != 1 else '') + ' compatible' + ('s' if len(items) != 1 else '')
            if items else 'No se confirmaron actualizaciones nuevas'
        )
        scope = str(result.get('scope') or 'priority')
        suffix = f' · {checked} dispositivos seleccionados' if scope == 'selected' and checked else (f' · {checked} dispositivos prioritarios' if checked else '')
        if cache_hit:
            suffix += ' · resultado reciente en caché'
        elif elapsed:
            suffix += f' · {elapsed:.1f} s'
        ctk.CTkLabel(status, text=status_text + suffix, font=(FONT, 9, 'bold'), text_color=CYAN if items else GREEN, anchor='w').pack(fill='x')

        if not items:
            ok = ctk.CTkFrame(box, fg_color=CARD2, border_width=1, border_color=BORDER, corner_radius=8)
            ok.pack(fill='x', padx=10, pady=(0, 9))
            ctk.CTkLabel(ok, text='✓ No hay una versión superior compatible confirmada para el hardware comprobado.', font=(FONT, 9, 'bold'), text_color=GREEN, anchor='w').pack(fill='x', padx=10, pady=8)
            return

        normal_items = [x for x in items if str(x.get('driver_class') or '').upper() != 'FIRMWARE']
        firmware_items = [x for x in items if str(x.get('driver_class') or '').upper() == 'FIRMWARE']
        if normal_items:
            ctk.CTkLabel(box, text='Drivers', font=(FONT, 10, 'bold'), text_color=TEXT, anchor='w').pack(fill='x', padx=12, pady=(2, 4))
            for item in normal_items:
                self._render_driver_update_item(box, item, firmware=False, bulk_busy=bulk_busy)
        if firmware_items:
            ctk.CTkLabel(box, text='Firmware · instalación individual', font=(FONT, 10, 'bold'), text_color=AMBER, anchor='w').pack(fill='x', padx=12, pady=(6, 4))
            ctk.CTkLabel(box, text='CorePulse no incluye firmware en instalaciones masivas.', font=(FONT, 8), text_color=MUTED, anchor='w').pack(fill='x', padx=12, pady=(0, 4))
            for item in firmware_items:
                self._render_driver_update_item(box, item, firmware=True, bulk_busy=bulk_busy)

    @staticmethod
    def _driver_class_icon(driver_class):
        cls = str(driver_class or '').upper()
        if cls == 'DISPLAY': return 'GPU'
        if cls == 'NET': return 'NET'
        if cls in {'MEDIA', 'AUDIOENDPOINT'}: return 'AUD'
        if cls in {'HDC', 'SCSIADAPTER', 'DISKDRIVE', 'STORAGEVOLUMES'}: return 'SSD'
        if cls == 'BLUETOOTH': return 'BT'
        if cls == 'FIRMWARE': return 'FW'
        if cls in {'USB', 'USBDEVICE'}: return 'USB'
        return 'SYS'

    def _render_driver_update_item(self, parent, item, *, firmware=False, bulk_busy=False):
        update_id = str(item.get('update_id') or '')
        revision = int(item.get('revision') or 0)
        action_key = 'driver_update_' + re.sub(r'[^a-zA-Z0-9]', '', update_id)[-12:] + '_' + str(revision)
        busy = action_key in self._jobs
        downloaded = bool(item.get('is_downloaded'))
        selected = update_id in self._driver_update_selected and not firmware
        accent = AMBER if firmware else (GREEN if downloaded else CYAN)

        row = ctk.CTkFrame(parent, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=10)
        row.pack(fill='x', padx=10, pady=(0, 6))
        ctk.CTkFrame(row, width=4, fg_color=accent, corner_radius=8).pack(side='left', fill='y', padx=(1, 0), pady=1)

        if not firmware:
            var = ctk.BooleanVar(value=selected)
            chk = ctk.CTkCheckBox(
                row, text='', variable=var, width=24, height=24, checkbox_width=22, checkbox_height=22,
                corner_radius=5, border_width=2, fg_color=CYAN, hover_color=CYAN, border_color=ACTION_BORDER,
                command=lambda uid=update_id, v=var: self._toggle_driver_update_selection(uid, bool(v.get())),
            )
            chk.pack(side='left', padx=(10, 4), pady=12)
            if bulk_busy:
                try: chk.configure(state='disabled')
                except Exception: pass

        icon = ctk.CTkLabel(row, text=self._driver_class_icon(item.get('driver_class')), width=42, height=42, corner_radius=9, fg_color=CARD2, text_color=accent, font=(FONT, 9, 'bold'))
        icon.pack(side='left', padx=(8 if firmware else 4, 10), pady=10)

        info = ctk.CTkFrame(row, fg_color='transparent')
        info.pack(side='left', fill='both', expand=True, pady=8)
        device_name = str(item.get('device_name') or item.get('title') or 'Controlador')
        ctk.CTkLabel(info, text=device_name, font=(FONT, 10, 'bold'), text_color=TEXT, anchor='w', justify='left').pack(fill='x')
        current = str(item.get('current_version') or 'N/A')
        available = str(item.get('available_version') or 'N/A')
        ctk.CTkLabel(info, text=f'Instalado  {current}    →    Disponible  {available}', font=(FONT, 9, 'bold'), text_color=CYAN, anchor='w').pack(fill='x', pady=(2, 0))
        provider = str(item.get('provider') or '').strip()
        official = str(item.get('official_vendor') or '').strip()
        source_parts = [str(item.get('source') or 'Fuente verificada')]
        if provider:
            source_parts.append(provider)
        if official:
            source_parts.append(f'Soporte oficial: {official}')
        size = self._driver_update_size_text(item.get('max_download_size'))
        if size != 'Tamaño N/A':
            source_parts.append(size)
        ctk.CTkLabel(info, text=' · '.join(source_parts), font=(FONT, 8), text_color=MUTED, anchor='w', justify='left').pack(fill='x', pady=(2, 0))

        right = ctk.CTkFrame(row, fg_color='transparent')
        right.pack(side='right', padx=10, pady=8)
        state_text = 'Firmware' if firmware else ('Descargado' if downloaded else 'Disponible')
        state = ctk.CTkFrame(right, fg_color=CARD2, border_width=1, border_color=accent, corner_radius=6)
        state.pack(anchor='e', pady=(0, 5))
        ctk.CTkLabel(state, text=state_text, font=(FONT, 8, 'bold'), text_color=accent).pack(padx=8, pady=3)

        buttons = ctk.CTkFrame(right, fg_color='transparent')
        buttons.pack(anchor='e')
        official_url = str(item.get('official_url') or '').strip()
        if official_url:
            self._button(buttons, 'Fabricante', lambda url=official_url: self._open_driver_vendor_url(url), variant='ghost', width=86, height=28).pack(side='left', padx=(0, 5))
        if downloaded:
            action_text = 'Instalando…' if busy else 'Instalar'
            command = lambda uid=update_id, rev=revision, title=device_name, fw=firmware, inf=str(item.get('current_inf') or ''), meta=item: self._install_driver_update(uid, rev, title, firmware=fw, current_inf=inf, metadata=meta)
            variant = 'primary'
        else:
            action_text = 'Descargando…' if busy else 'Descargar'
            command = lambda uid=update_id, rev=revision, title=device_name, meta=item: self._download_driver_update(uid, rev, title, metadata=meta)
            variant = 'secondary'
        btn = self._button(buttons, action_text, command, variant=variant, width=96, height=28)
        btn.pack(side='left')
        if busy or bulk_busy:
            try: btn.configure(state='disabled')
            except Exception: pass

    def _open_driver_vendor_url(self, url):
        try:
            webbrowser.open(str(url), new=2)
        except Exception:
            pass

    def _toggle_driver_update_selection(self, update_id, selected):
        update_id = str(update_id or '')
        if not update_id:
            return
        if selected:
            self._driver_update_selected.add(update_id)
        else:
            self._driver_update_selected.discard(update_id)
        self._request_render(1)

    def _selected_driver_update_items(self):
        items = list((self._driver_updates or {}).get('items') or [])
        return [x for x in items if str(x.get('update_id') or '') in self._driver_update_selected and bool(x.get('bulk_install_allowed', True))]

    def _scan_driver_updates(self, force=False):
        if 'driver_updates_scan' in self._jobs:
            return
        def work():
            try:
                return scan_driver_updates(max_devices=5, force_refresh=bool(force), local_inventory=self._drivers)
            except DriverUpdateError as exc:
                return {'items': [], 'count': 0, 'source': 'Catálogo directo', 'error': str(exc)}
            except Exception as exc:
                return {'items': [], 'count': 0, 'source': 'Catálogo directo', 'error': f'{type(exc).__name__}: {exc}'}
        def done(result, error):
            self._driver_updates = result if isinstance(result, dict) else {
                'items': [], 'count': 0, 'source': 'Catálogo directo',
                'error': error or 'La búsqueda no devolvió un resultado válido.',
            }
            if isinstance(self._driver_updates, dict):
                self._driver_updates['scope'] = 'priority'
            self._driver_update_selected = {
                str(x.get('update_id') or '') for x in (self._driver_updates.get('items') or [])
                if bool(x.get('bulk_install_allowed', True)) and str(x.get('update_id') or '')
            }
        self._async('driver_updates_scan', work, done)
        self._request_render(1)

    def _refresh_attention_search_button(self):
        btn = getattr(self, '_driver_attention_search_button', None)
        if btn is None:
            return
        count = len(getattr(self, '_driver_attention_selected', set()) or set())
        scanning = bool(getattr(self, '_driver_attention_scanning_ids', set()) or set())
        try:
            btn.configure(
                text=('Buscando…' if scanning else f'Buscar seleccionados ({count})'),
                state='disabled' if scanning or not count else 'normal',
            )
        except Exception:
            pass

    def _toggle_driver_attention_selection(self, device_id, selected):
        device_id = str(device_id or '')
        if not device_id:
            return
        if selected:
            self._driver_attention_selected.add(device_id)
        else:
            self._driver_attention_selected.discard(device_id)
        self._refresh_attention_search_button()

    def _merge_attention_scan_result(self, result, scanned_ids):
        payload = result if isinstance(result, dict) else {
            'items': [], 'count': 0, 'source': 'Catálogo directo',
            'error': 'La búsqueda no devolvió un resultado válido.', 'device_results': [],
        }
        scanned_ids = {str(x) for x in (scanned_ids or set()) if str(x)}
        previous = self._driver_updates if isinstance(self._driver_updates, dict) else {}
        old_items = [
            dict(x) for x in (previous.get('items') or []) if isinstance(x, dict)
            and str(x.get('instance_id') or '') not in scanned_ids
        ]
        new_items = [dict(x) for x in (payload.get('items') or []) if isinstance(x, dict)]
        old_results = [
            dict(x) for x in (previous.get('device_results') or []) if isinstance(x, dict)
            and str(x.get('instance_id') or '') not in scanned_ids
        ]
        new_results = [dict(x) for x in (payload.get('device_results') or []) if isinstance(x, dict)]
        merged = dict(previous)
        merged.update(payload)
        merged['items'] = old_items + new_items
        merged['device_results'] = old_results + new_results
        merged['count'] = len(merged['items'])
        merged['scope'] = 'selected'
        self._driver_updates = merged
        self._driver_update_selected = {
            str(x.get('update_id') or '') for x in merged['items']
            if bool(x.get('bulk_install_allowed', True)) and str(x.get('update_id') or '')
        }
        return merged

    def _apply_attention_scan_feedback(self, device_ids=None):
        wanted = {str(x) for x in (device_ids or self._driver_attention_widgets.keys()) if str(x)}
        result = self._driver_updates if isinstance(self._driver_updates, dict) else {}
        scan_map = {
            str(x.get('instance_id') or ''): x for x in (result.get('device_results') or []) if isinstance(x, dict)
        }
        update_map = {
            str(x.get('instance_id') or ''): x for x in (result.get('items') or []) if isinstance(x, dict)
        }
        scanning_ids = set(getattr(self, '_driver_attention_scanning_ids', set()) or set())
        for device_id in wanted:
            refs = (getattr(self, '_driver_attention_widgets', {}) or {}).get(device_id) or {}
            label = refs.get('scan_label')
            button = refs.get('action_button')
            update_item = update_map.get(device_id)
            scan_item = scan_map.get(device_id)
            if device_id in scanning_ids:
                label_text, label_color, action_text, state = 'Buscando una versión compatible…', CYAN, 'Buscando…', 'disabled'
                action_cmd = lambda: None
            elif update_item:
                downloaded = bool(update_item.get('is_downloaded'))
                label_text = f"Disponible {update_item.get('available_version') or 'versión superior'} · instalada {update_item.get('current_version') or 'N/A'}"
                label_color = GREEN
                if downloaded:
                    action_text = 'Instalar'
                    action_cmd = lambda u=update_item: self._install_driver_update(
                        str(u.get('update_id') or ''), int(u.get('revision') or 0), str(u.get('device_name') or ''),
                        firmware=str(u.get('driver_class') or '').upper() == 'FIRMWARE', current_inf=str(u.get('current_inf') or '')
                    )
                else:
                    action_text = 'Descargar'
                    action_cmd = lambda u=update_item: self._download_driver_update(
                        str(u.get('update_id') or ''), int(u.get('revision') or 0), str(u.get('device_name') or '')
                    )
                state = 'normal'
            elif scan_item:
                scan_state = str(scan_item.get('status') or '').upper()
                if scan_state == 'ERROR':
                    label_text, label_color = 'No se pudo verificar online · puedes reintentar', AMBER
                else:
                    label_text, label_color = 'Sin actualización compatible confirmada', GREEN
                action_text, state = 'Reintentar', 'normal'
                action_cmd = lambda did=device_id: self._scan_one_attention(did)
            else:
                label_text, label_color = 'Aún no se ha buscado una actualización online', MUTED
                action_text, state = 'Buscar actualización', 'normal'
                action_cmd = lambda did=device_id: self._scan_one_attention(did)
            try:
                if label is not None:
                    label.configure(text=label_text, text_color=label_color)
                if button is not None:
                    button.configure(text=action_text, command=action_cmd, state=state)
            except Exception:
                pass

        count = len(list(result.get('items') or []))
        try:
            if self._driver_summary_updates_value is not None:
                self._driver_summary_updates_value.configure(text=str(count))
            if self._driver_summary_updates_detail is not None:
                self._driver_summary_updates_detail.configure(text='Compatibles confirmadas' if count else 'No confirmadas')
        except Exception:
            pass
        self._refresh_attention_search_button()

    def _start_attention_scan(self, selected_ids):
        selected_ids = {str(x) for x in (selected_ids or set()) if str(x)}
        if not selected_ids or 'driver_attention_scan' in self._jobs or 'driver_updates_scan' in self._jobs:
            return
        self._jobs.add('driver_attention_scan')
        self._driver_attention_scanning_ids = set(selected_ids)
        self._apply_attention_scan_feedback(selected_ids)

        def worker():
            try:
                result = scan_driver_updates(
                    max_devices=max(1, len(selected_ids)),
                    force_refresh=False,
                    local_inventory=self._drivers,
                    instance_ids=selected_ids,
                )
                error = None
            except DriverUpdateError as exc:
                result = {'items': [], 'count': 0, 'source': 'Catálogo directo', 'error': str(exc), 'device_results': []}
                error = None
            except Exception as exc:
                result = {'items': [], 'count': 0, 'source': 'Catálogo directo', 'error': f'{type(exc).__name__}: {exc}', 'device_results': []}
                error = None

            def publish():
                self._jobs.discard('driver_attention_scan')
                if not self._alive:
                    return
                self._driver_attention_scanning_ids = set()
                self._merge_attention_scan_result(result, selected_ids)
                self._apply_attention_scan_feedback(selected_ids)
            try:
                self.app.after(0, publish)
            except Exception:
                pass
        threading.Thread(target=worker, daemon=True, name='CorePulse-DriverAttentionScan').start()

    def _scan_one_attention(self, device_id):
        self._start_attention_scan({str(device_id or '')})

    def _scan_selected_attention(self):
        self._start_attention_scan(set(getattr(self, '_driver_attention_selected', set()) or set()))

    def _toggle_driver_inventory(self):
        self._show_driver_inventory = not bool(getattr(self, '_show_driver_inventory', False))
        self._drivers_page = 0
        self._request_render(1)

    def _set_driver_update_downloaded(self, update_id, revision, downloaded=True):
        data = self._driver_updates if isinstance(self._driver_updates, dict) else None
        if not data:
            return
        for item in data.get('items') or []:
            if str(item.get('update_id') or '') == str(update_id) and int(item.get('revision') or 0) == int(revision or 0):
                item['is_downloaded'] = bool(downloaded)
                break

    def _download_driver_update(self, update_id, revision, title='', metadata=None):
        job = 'driver_update_' + re.sub(r'[^a-zA-Z0-9]', '', str(update_id))[-12:] + '_' + str(int(revision or 0))
        if job in self._jobs:
            return
        def work():
            try:
                return download_driver_update(update_id, revision, metadata=metadata)
            except Exception as exc:
                return {'ok': False, 'error': str(exc)}
        def done(result, error):
            payload = result if isinstance(result, dict) else {'ok': False, 'error': error}
            if payload.get('ok'):
                self._set_driver_update_downloaded(update_id, revision, True)
                try: messagebox.showinfo('Controladores', f'“{title or "Controlador"}” quedó descargado en la caché de CorePulse y listo para instalar.', parent=self.frame)
                except Exception: pass
            else:
                detail = payload.get('error') or payload.get('result_label') or error or 'No se pudo completar la descarga.'
                try: messagebox.showwarning('Controladores', f'No se pudo descargar “{title or "este controlador"}”.\n\n{detail}', parent=self.frame)
                except Exception: pass
        self._async(job, work, done)
        self._request_render(1)

    def _install_driver_update(self, update_id, revision, title='', *, firmware=False, current_inf='', metadata=None):
        job = 'driver_update_' + re.sub(r'[^a-zA-Z0-9]', '', str(update_id))[-12:] + '_' + str(int(revision or 0))
        if job in self._jobs:
            return
        warning = '\n\nEste paquete es firmware. Se excluye de las instalaciones masivas y puede requerir reinicio.' if firmware else ''
        try:
            accepted = messagebox.askyesno(
                'Instalar controlador',
                f'¿Instalar “{title or "este controlador"}”?\n\nCorePulse validará el paquete y respaldará el driver OEM actual. Los paquetes del fabricante usan su instalador oficial; los del catálogo usan PnPUtil.{warning}',
                parent=self.frame,
            )
        except Exception:
            accepted = False
        if not accepted:
            return
        def work():
            try:
                return install_driver_update(update_id, revision, current_inf=current_inf, device_name=title, metadata=metadata)
            except Exception as exc:
                return {'ok': False, 'error': str(exc)}
        def done(result, error):
            payload = result if isinstance(result, dict) else {'ok': False, 'error': error}
            if payload.get('ok'):
                reboot = bool(payload.get('reboot_required'))
                message = 'Controlador instalado correctamente.' + (' Windows recomienda reiniciar el equipo.' if reboot else '')
                try: messagebox.showinfo('Controladores', message, parent=self.frame)
                except Exception: pass
                try: self.app.after(900, lambda: self._scan_driver_updates(force=True))
                except Exception: pass
            else:
                detail = payload.get('error') or payload.get('result_label') or error or 'No se pudo completar la instalación.'
                if looks_like_access_denied(str(detail)):
                    detail += '\n\nVuelve a abrir CorePulse como administrador para instalar controladores.'
                try: messagebox.showwarning('Controladores', f'No se pudo instalar “{title or "este controlador"}”.\n\n{detail}', parent=self.frame)
                except Exception: pass
        self._async(job, work, done)
        self._request_render(1)

    def _download_all_driver_updates(self):
        if 'driver_updates_download_all' in self._jobs or 'driver_updates_install_all' in self._jobs:
            return
        items = list((self._driver_updates or {}).get('items') or [])
        pending = [x for x in items if not bool(x.get('is_downloaded'))]
        if not pending:
            return
        def work():
            return download_all_driver_updates(pending)
        def done(result, error):
            payload = result if isinstance(result, dict) else {'ok': False, 'results': [], 'error': error}
            success_ids = {str(x.get('update_id') or '') for x in payload.get('results') or [] if x.get('ok')}
            for item in items:
                if str(item.get('update_id') or '') in success_ids:
                    item['is_downloaded'] = True
            failed = [x for x in payload.get('results') or [] if not x.get('ok')]
            if failed:
                detail = '\n'.join(f"• {x.get('device_name') or 'Controlador'}: {x.get('error') or 'falló'}" for x in failed[:5])
                try: messagebox.showwarning('Descargar todo', f'Se descargaron {len(success_ids)} paquete(s), pero {len(failed)} fallaron.\n\n{detail}', parent=self.frame)
                except Exception: pass
            else:
                try: messagebox.showinfo('Descargar todo', f'{len(success_ids)} paquete(s) descargados y listos para instalar.', parent=self.frame)
                except Exception: pass
        self._async('driver_updates_download_all', work, done)
        self._request_render(1)

    def _install_selected_driver_updates(self):
        if 'driver_updates_install_selected' in self._jobs or 'driver_updates_download_all' in self._jobs:
            return
        selected = self._selected_driver_update_items()
        if not selected:
            return
        firmware_count = sum(
            1 for x in (self._driver_updates or {}).get('items') or []
            if not bool(x.get('bulk_install_allowed', True))
        )
        try:
            message = (
                f'¿Instalar {len(selected)} controlador(es) seleccionado(s)?\n\n'
                'Antes de reemplazar cada paquete OEM, CorePulse intentará exportar el driver actual '
                'con PnPUtil como respaldo. Windows validará firma y compatibilidad.'
            )
            if firmware_count:
                message += f'\n\n{firmware_count} paquete(s) de firmware quedan fuera de esta acción.'
            accepted = messagebox.askyesno('Instalar seleccionados', message, parent=self.frame)
        except Exception:
            accepted = False
        if not accepted:
            return

        def work():
            return install_all_driver_updates(selected)

        def done(result, error):
            payload = result if isinstance(result, dict) else {'ok': False, 'results': [], 'error': error}
            results = list(payload.get('results') or [])
            ok_count = sum(1 for x in results if x.get('ok'))
            failed = [x for x in results if not x.get('ok')]
            reboot = bool(payload.get('reboot_required'))
            if failed:
                detail = '\n'.join(
                    f"• {x.get('device_name') or 'Controlador'}: {x.get('error') or 'falló'}"
                    for x in failed[:5]
                )
                try:
                    messagebox.showwarning(
                        'Instalar seleccionados',
                        f'Se instalaron {ok_count}; {len(failed)} fallaron.\n\n{detail}',
                        parent=self.frame,
                    )
                except Exception:
                    pass
            else:
                message = f'{ok_count} controlador(es) instalados correctamente.'
                if reboot:
                    message += ' Reinicia Windows para completar los cambios.'
                try:
                    messagebox.showinfo('Instalar seleccionados', message, parent=self.frame)
                except Exception:
                    pass
            try:
                self.app.after(1200, lambda: self._scan_driver_updates(force=True))
            except Exception:
                pass

        self._async('driver_updates_install_selected', work, done)
        self._request_render(1)

    def _install_all_driver_updates(self):
        if 'driver_updates_install_all' in self._jobs or 'driver_updates_download_all' in self._jobs:
            return
        items = list((self._driver_updates or {}).get('items') or [])
        installable = [x for x in items if bool(x.get('bulk_install_allowed', True))]
        firmware_count = sum(1 for x in items if not bool(x.get('bulk_install_allowed', True)))
        if not installable:
            return
        try:
            accepted = messagebox.askyesno(
                'Instalar todo',
                f'¿Descargar e instalar {len(installable)} controlador(es) compatibles?\n\nWindows validará cada INF con PnPUtil antes de aplicarlo.' +
                (f'\n\n{firmware_count} paquete(s) de firmware se omitirán por seguridad y sólo pueden instalarse individualmente.' if firmware_count else ''),
                parent=self.frame,
            )
        except Exception:
            accepted = False
        if not accepted:
            return
        def work():
            return install_all_driver_updates(items)
        def done(result, error):
            payload = result if isinstance(result, dict) else {'ok': False, 'results': [], 'error': error}
            results = list(payload.get('results') or [])
            ok_count = sum(1 for x in results if x.get('ok'))
            failed = [x for x in results if not x.get('ok')]
            reboot = bool(payload.get('reboot_required'))
            if failed:
                detail = '\n'.join(f"• {x.get('device_name') or 'Controlador'}: {x.get('error') or 'falló'}" for x in failed[:5])
                message = f'Se instalaron {ok_count} controlador(es); {len(failed)} fallaron.\n\n{detail}'
                try: messagebox.showwarning('Instalar todo', message, parent=self.frame)
                except Exception: pass
            else:
                message = f'{ok_count} controlador(es) instalados correctamente.' + (' Reinicia Windows para completar los cambios.' if reboot else '')
                try: messagebox.showinfo('Instalar todo', message, parent=self.frame)
                except Exception: pass
            try: self.app.after(1200, lambda: self._scan_driver_updates(force=True))
            except Exception: pass
        self._async('driver_updates_install_all', work, done)
        self._request_render(1)

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
            text='ADMIN' if caps.get('admin') else 'UAC AL EJECUTAR',
            font=(FONT, 9, 'bold'),
            text_color=GREEN if caps.get('admin') else CYAN,
        ).pack(side='right')
        self._kv(info, 'Plataforma', 'Windows' if caps.get('windows') else 'No compatible')
        self._kv(
            info, 'Privilegios',
            'Administrador' if caps.get('admin') else 'Usuario estándar · PowerShell solicitará administrador',
            GREEN if caps.get('admin') else CYAN,
        )
        self._kv(info, 'Política', 'Sólo por acción explícita del usuario')
        self._kv(info, 'Rollback de Tweaks', 'Separado · DISM/SFC no restauran snapshots de Tweaks')
        ctk.CTkLabel(
            info,
            text='El diagnóstico ejecuta CheckHealth + ScanHealth + SFC VerifyOnly. La reparación ejecuta RestoreHealth + SFC ScanNow y una comprobación posterior. Al comenzar se abre PowerShell visible para mostrar la ejecución real; si CorePulse no está elevado, Windows solicitará UAC sólo para esa consola.',
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
            ctk.CTkLabel(note, text='Elevación automática de la consola', font=(FONT, 11, 'bold'), text_color=CYAN).pack(anchor='w', padx=14, pady=(11, 3))
            ctk.CTkLabel(
                note,
                text='DISM/SFC requieren administrador. No necesitas reiniciar CorePulse: al ejecutar una acción, Windows mostrará el aviso UAC y abrirá únicamente PowerShell como administrador. La salida se verá en esa consola y, al terminar, CorePulse la incorporará a esta pestaña.',
                font=(FONT, 9), text_color=TEXT2, wraplength=1000, justify='left', anchor='w',
            ).pack(fill='x', padx=14, pady=(0, 7))
            self._button(note, 'Abrir CorePulse completo como administrador · opcional', self._request_admin_restart, variant='secondary', height=30).pack(anchor='w', padx=14, pady=(0, 11))

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
            return 'Al iniciar se abrirá PowerShell visible. CorePulse importará la salida real cuando finalice.'
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
        if data.get('execution_mode'):
            console_admin = data.get('powershell_admin')
            admin_text = 'Sí' if console_admin is True else ('No' if console_admin is False else 'N/A')
            self._kv(card, 'Ejecución', 'PowerShell visible · salida real importada')
            self._kv(card, 'PowerShell administrador', admin_text, GREEN if console_admin is True else (RED if console_admin is False else MUTED))

        raw_parts = []
        for step in data.get('steps') or []:
            raw = str(step.get('stdout') or step.get('stderr') or '').rstrip()
            if raw:
                cmd = ' '.join(str(x) for x in (step.get('command') or []))
                raw_parts.append(f"=== {step.get('label') or step.get('key')} ===\n> {cmd}\n{raw}")
        if raw_parts:
            output_head = ctk.CTkFrame(card, fg_color='transparent')
            output_head.pack(fill='x', padx=14, pady=(8, 4))
            ctk.CTkLabel(output_head, text='Salida real de PowerShell', font=(FONT, 9, 'bold'), text_color=CYAN).pack(side='left')
            ctk.CTkLabel(output_head, text='DISM / SFC', font=(FONT, 8, 'bold'), text_color=MUTED).pack(side='right')
            output = ctk.CTkTextbox(
                card, height=180, corner_radius=8, border_width=1,
                border_color=BORDER, fg_color=CARD2, text_color=TEXT2,
                font=('Consolas', 9), wrap='word',
            )
            output.pack(fill='x', padx=14, pady=(0, 8))
            output.insert('1.0', '\n\n'.join(raw_parts))
            output.configure(state='disabled')
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
        """Comprueba plataforma; la consola DISM/SFC solicita su propio UAC."""
        caps = repair_capabilities()
        if not caps.get('windows'):
            messagebox.showwarning('CorePulse', 'Esta herramienta sólo está disponible en Windows.')
            return False
        return True

    def _run_integrity_diagnostic(self):
        if 'windows_repair_diagnostic' in self._jobs or 'windows_repair_apply' in self._jobs:
            return
        if not self._ensure_repair_admin():
            return
        if not messagebox.askyesno(
            'CorePulse · Diagnóstico de Windows',
            '¿Ejecutar DISM CheckHealth + ScanHealth y SFC VerifyOnly?\n\nSe abrirá una ventana visible de PowerShell. Si hace falta, Windows solicitará permisos de administrador mediante UAC. No es un rollback de Tweaks y puede tardar varios minutos.'
        ):
            return
        self._repair_progress = {'event':'start','index':1,'total':3,'label':'Preparando diagnóstico'}
        def work():
            return run_integrity_diagnostic_visible(progress=self._repair_progress_callback)
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
            '¿Ejecutar DISM RestoreHealth y SFC ScanNow?\n\nSe abrirá PowerShell visible como administrador (Windows puede mostrar UAC). Estas herramientas pueden modificar componentes/archivos protegidos de Windows y pueden tardar bastante. No revierten Tweaks de CorePulse.'
        ):
            return
        self._repair_progress = {'event':'start','index':1,'total':3,'label':'Preparando reparación'}
        def work():
            return run_windows_repair_visible(progress=self._repair_progress_callback)
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
        self._title(
            'Historial de salud · Tendencias · Cambios de hardware',
            'CorePulse conserva lecturas reales por días/semanas y compara períodos equivalentes. Los cambios observados no se presentan como causalidad.'
        )
        store = getattr(self.app, 'health_history_store', None)
        row = ctk.CTkFrame(self.body, fg_color='transparent')
        row.pack(fill='x', padx=4, pady=(0, 8))
        for days in (1, 7, 30):
            summary = store.summary(days) if store else {'samples': 0, 'metrics': {}}
            metrics = summary.get('metrics', {})
            cpu_max = (metrics.get('cpu_temp') or {}).get('max')
            ram_avg = (metrics.get('ram_usage') or {}).get('avg')
            score_avg = (metrics.get('system_score') or {}).get('avg')
            detail = f"CPU máx {_fmt(cpu_max,' °C')} · RAM media {_fmt(ram_avg,'%')} · Índice {_fmt(score_avg)}"
            self._summary_box(row, f'{days} DÍAS', str(summary.get('samples', 0)) + ' muestras', detail, CYAN)

        if store:
            self._render_period_trends(store)
            self._render_health_chart(store.daily_summary(30))
            self._render_stability_history(store)
            benches = store.latest_benchmarks(12)
            if benches:
                bench_card = self._card(); bench_card.pack(fill='x', padx=8, pady=5)
                ctk.CTkLabel(bench_card, text='Historial de rendimiento', font=(FONT,11,'bold'), text_color=TEXT).pack(anchor='w', padx=12, pady=(10,4))
                for b in benches:
                    payload = b.get('payload') or {}; value = payload.get('value')
                    if str(payload.get('kind')).upper() == 'SSD':
                        txt = f"SSD · Escritura {_fmt(payload.get('write_mbps'),' MB/s')} · Lectura {_fmt(payload.get('read_mbps'),' MB/s')}"
                    else:
                        txt = f"{payload.get('kind') or b.get('kind')} · {_fmt(value,' '+str(payload.get('unit') or b.get('unit') or ''))} · {payload.get('provider') or b.get('provider')}"
                    self._line(bench_card, txt)

        ba = self._card(); ba.pack(fill='x', padx=8, pady=5)
        ctk.CTkLabel(ba, text='Antes vs Después', font=(FONT,11,'bold'), text_color=TEXT).pack(anchor='w', padx=12, pady=(10,4))
        buttons = ctk.CTkFrame(ba, fg_color='transparent'); buttons.pack(fill='x', padx=8, pady=4)
        self._button(buttons, 'Capturar ANTES', lambda:self._capture_slot('before'), variant='secondary', height=30).pack(side='left', padx=4)
        self._button(buttons, 'Capturar DESPUÉS', lambda:self._capture_slot('after'), variant='secondary', height=30).pack(side='left', padx=4)
        comp = compare(); snaps = load_snapshots()
        self._kv(ba, 'Snapshot ANTES', 'Disponible' if snaps.get('before') else 'No')
        self._kv(ba, 'Snapshot DESPUÉS', 'Disponible' if snaps.get('after') else 'No')
        if comp.get('available'):
            for key in ('cpu_temp','cpu_ghz','ram_usage','ram_available_gb','process_count','gpu_temp','battery_health'):
                d = (comp.get('deltas') or {}).get(key) or {}
                self._kv(ba, key, f"{_fmt(d.get('before'))} → {_fmt(d.get('after'))} · Δ {_fmt(d.get('delta'))}")
            ctk.CTkLabel(ba, text=comp.get('note'), font=(FONT,8), text_color=AMBER).pack(anchor='w', padx=12, pady=(4,10))

        self._render_optimization_history()

        hw = self._card(); hw.pack(fill='x', padx=8, pady=5)
        ctk.CTkLabel(hw, text='Cambios de hardware', font=(FONT,11,'bold'), text_color=TEXT).pack(anchor='w', padx=12, pady=(10,4))
        data = self._hw
        if data is None:
            ctk.CTkLabel(hw, text='Comparación pendiente.', font=(FONT,9), text_color=MUTED).pack(anchor='w', padx=12, pady=(0,8))
        else:
            changes = data.get('changes') or []
            self._kv(hw, 'Baseline previo', 'Sí' if data.get('baseline_exists') else 'No')
            self._kv(hw, 'Cambios detectados', len(changes), AMBER if changes else GREEN)
            for c in changes:
                self._line(hw, f"{c.get('component')}: cambió desde el baseline guardado")
        self._button(hw, 'Guardar hardware actual como nuevo baseline', self._save_hw_baseline, variant='secondary', height=30).pack(anchor='w', padx=12, pady=(5,11))

    def _render_optimization_history(self):
        card = self._card(); card.pack(fill='x', padx=8, pady=5)
        ctk.CTkLabel(card, text='Antes vs Después automático', font=(FONT,11,'bold'), text_color=TEXT).pack(anchor='w', padx=12, pady=(10,3))
        ctk.CTkLabel(
            card,
            text='CorePulse guarda mediciones alrededor de optimizaciones compatibles. Procesos, RAM, CPU, FPS y latencia sólo aparecen cuando existe una lectura real.',
            font=(FONT,9), text_color=MUTED, wraplength=1000, justify='left'
        ).pack(anchor='w', padx=12, pady=(0,7))
        rows = latest_operations(8)
        if not rows:
            ctk.CTkLabel(card, text='Aún no hay optimizaciones medidas automáticamente.', font=(FONT,9), text_color=MUTED).pack(anchor='w', padx=12, pady=(0,11))
            return
        labels = {
            'ram_usage': ('RAM', '%'),
            'ram_available_gb': ('RAM disponible', ' GB'),
            'process_count': ('Procesos', ''),
            'cpu_usage': ('CPU', '%'),
            'cpu_idle_percent': ('CPU libre', '%'),
            'fps': ('FPS', ''),
            'fps_1pct_low': ('1% low', ' FPS'),
            'network_latency_ms': ('Latencia', ' ms'),
        }
        for row in rows:
            when = dt.datetime.fromtimestamp(float(row.get('finished_at') or row.get('started_at') or 0)).strftime('%d/%m %H:%M')
            action = str(row.get('action') or 'Optimización')
            status = str(row.get('status') or '')
            comparison = row.get('comparison') if isinstance(row.get('comparison'), dict) else {}
            deltas = comparison.get('deltas') if isinstance(comparison.get('deltas'), dict) else {}
            parts = []
            for key in ('ram_usage','ram_available_gb','process_count','cpu_usage','fps','network_latency_ms'):
                d = deltas.get(key) if isinstance(deltas.get(key), dict) else {}
                before, after = _num(d.get('before')), _num(d.get('after'))
                if before is None or after is None:
                    continue
                label, unit = labels[key]
                digits = 0 if key in ('process_count','fps') else 1
                parts.append(f"{label} {before:.{digits}f}→{after:.{digits}f}{unit}")
                if len(parts) >= 3:
                    break
            status_text = 'medición completa' if status == 'completed' and comparison.get('available') else status.replace('_',' ') or 'sin estado'
            self._line(card, f"{when} · {action} · {status_text}")
            if parts:
                ctk.CTkLabel(card, text='   ' + ' · '.join(parts), font=(FONT,8), text_color=TEXT2, anchor='w', justify='left', wraplength=980).pack(fill='x', padx=20, pady=(0,3))
            elif row.get('note'):
                ctk.CTkLabel(card, text='   ' + _short(row.get('note'), 220), font=(FONT,8), text_color=MUTED, anchor='w', justify='left', wraplength=980).pack(fill='x', padx=20, pady=(0,3))
        ctk.CTkLabel(card, text='Las diferencias son mediciones antes/después; CorePulse no las presenta como prueba de causalidad.', font=(FONT,8), text_color=AMBER).pack(anchor='w', padx=12, pady=(4,10))

    def _render_period_trends(self, store):
        card = self._card(); card.pack(fill='x', padx=8, pady=5)
        ctk.CTkLabel(card, text='Tendencias comparables', font=(FONT,11,'bold'), text_color=TEXT).pack(anchor='w', padx=12, pady=(10,3))
        ctk.CTkLabel(
            card,
            text='Compara cada período con el bloque inmediatamente anterior de la misma duración. Sólo usa muestras locales reales.',
            font=(FONT,9), text_color=MUTED, wraplength=1000, justify='left'
        ).pack(anchor='w', padx=12, pady=(0,7))
        any_data = False
        for days in (7, 30):
            comp = store.compare_periods(days)
            current = comp.get('current') or {}
            previous = comp.get('previous') or {}
            if not comp.get('comparable'):
                self._kv(card, f'{days} vs {days} días anteriores', f"Aún sin período previo comparable · {current.get('samples',0)} muestra(s) actuales", MUTED)
                continue
            any_data = True
            metrics = comp.get('metrics') or {}
            cpu = _num((metrics.get('cpu_temp') or {}).get('max_delta'))
            ram = _num((metrics.get('ram_usage') or {}).get('avg_delta'))
            score = _num((metrics.get('system_score') or {}).get('avg_delta'))
            parts = []
            if cpu is not None: parts.append(f'CPU máx {cpu:+.1f} °C')
            if ram is not None: parts.append(f'RAM media {ram:+.1f} pp')
            if score is not None: parts.append(f'Índice {score:+.1f} pts')
            self._kv(card, f'{days} vs {days} días anteriores', ' · '.join(parts) if parts else 'Períodos disponibles; sin métricas comparables', CYAN)
            for insight in store.trend_insights(days)[:4]:
                delta = _num(insight.get('delta'))
                color = AMBER if delta is not None and ((insight.get('metric') in ('cpu_temp','gpu_temp','ram_usage') and delta > 0) or (insight.get('metric') in ('battery_health','storage_health','system_score') and delta < 0)) else TEXT2
                self._line(card, insight.get('text') or '')
        if not any_data:
            ctk.CTkLabel(card, text='El análisis gana valor a medida que CorePulse acumula días de uso.', font=(FONT,8), text_color=MUTED).pack(anchor='w', padx=12, pady=(3,10))
        else:
            ctk.CTkLabel(card, text='Las diferencias son observaciones del período; no demuestran por sí solas la causa.', font=(FONT,8), text_color=AMBER).pack(anchor='w', padx=12, pady=(3,10))

    def _render_stability_history(self, store):
        snapshots = store.latest_stability_snapshots(limit=4, period_days=7)
        card = self._card(); card.pack(fill='x', padx=8, pady=5)
        ctk.CTkLabel(card, text='Estabilidad de Windows registrada', font=(FONT,11,'bold'), text_color=TEXT).pack(anchor='w', padx=12, pady=(10,3))
        if not snapshots:
            ctk.CTkLabel(
                card,
                text='Aún no hay snapshots de estabilidad. Cuando ejecutes “Analizar estabilidad”, CorePulse guardará ese resumen y lo reutilizará aquí sin repetir consultas.',
                font=(FONT,9), text_color=MUTED, wraplength=1000, justify='left'
            ).pack(anchor='w', padx=12, pady=(0,11))
            return
        for snap in snapshots:
            stamp = dt.datetime.fromtimestamp(float(snap.get('ts') or 0)).strftime('%d/%m/%Y %H:%M')
            text = (
                f"{stamp} · BSOD {int(snap.get('bsod_bugcheck') or 0)} · WHEA {int(snap.get('whea') or 0)} · "
                f"Reinicios {int(snap.get('power_incidents') or 0)} · Apps {int(snap.get('app_error') or 0) + int(snap.get('app_hang') or 0)}"
            )
            self._line(card, text)
        ctk.CTkLabel(card, text='Cada fila refleja el análisis real de los 7 días previos a esa captura.', font=(FONT,8), text_color=MUTED).pack(anchor='w', padx=12, pady=(3,10))

    def _render_health_chart(self, rows):
        card = self._card(); card.pack(fill='x', padx=8, pady=5)
        ctk.CTkLabel(card, text='Evolución diaria de salud · últimos 30 días', font=(FONT,11,'bold'), text_color=TEXT).pack(anchor='w', padx=12, pady=(10,3))
        if not rows:
            ctk.CTkLabel(card, text='Aún no hay suficientes muestras. CorePulse registra una muestra aproximadamente cada 60 s mientras está abierto.', font=(FONT,9), text_color=MUTED).pack(anchor='w', padx=12, pady=(0,12))
            return
        width_px = 1040; height_px = 390; dpi = 100
        fig = Figure(figsize=(width_px/dpi, height_px/dpi), dpi=dpi, facecolor=CARD)
        ax1 = fig.add_subplot(211, facecolor=CARD); ax2 = fig.add_subplot(212, facecolor=CARD)
        xs = [dt.datetime.fromisoformat(str(r.get('date'))) for r in rows]
        def series(key, stat):
            values = []
            for row in rows:
                metric = ((row.get('metrics') or {}).get(key) or {})
                value = _num(metric.get(stat))
                values.append(value if value is not None else float('nan'))
            return values
        ax1.plot(xs, series('cpu_temp','max'), color=CYAN, linewidth=1.8, marker='o', markersize=3, label='CPU máx °C')
        ax1.plot(xs, series('gpu_temp','max'), color=PURPLE, linewidth=1.8, marker='o', markersize=3, label='GPU máx °C')
        ax2.plot(xs, series('storage_health','latest'), color=GREEN, linewidth=1.7, marker='o', markersize=3, label='SSD salud %')
        ax2.plot(xs, series('battery_health','latest'), color=AMBER, linewidth=1.7, marker='o', markersize=3, label='Batería salud %')
        ax2.plot(xs, series('system_score','avg'), color=CYAN, linewidth=1.3, alpha=.8, label='Índice medio')
        for ax in (ax1, ax2):
            ax.grid(True, color=theme_color('#334155'), linewidth=.5, alpha=.55)
            ax.tick_params(colors=MUTED, labelsize=7)
            for spine in ax.spines.values(): spine.set_color(BORDER)
            leg = ax.legend(fontsize=7, loc='best', facecolor=CARD, edgecolor=BORDER)
            for t in leg.get_texts(): t.set_color(TEXT)
        ax1.set_ylabel('Temperatura', color=TEXT2, fontsize=8)
        ax2.set_ylabel('Salud / índice', color=TEXT2, fontsize=8)
        fig.autofmt_xdate(rotation=0, ha='center'); fig.tight_layout(pad=1.2)
        agg = FigureCanvasAgg(fig); agg.draw(); size = agg.get_width_height()
        image = Image.frombuffer('RGBA', size, agg.buffer_rgba(), 'raw', 'RGBA', 0, 1).copy()
        photo = ImageTk.PhotoImage(image=image, master=card); self._health_chart_photo = photo
        lbl = tk.Label(card, image=photo, bg=CARD, bd=0, highlightthickness=0); lbl.pack(fill='x', padx=10, pady=(0,10))
        fig.clear()

    def _render_recovery(self):
        self._title('Restauración y rollback','Protección antes de cambios delicados. CorePulse no habilita Restaurar sistema sin tu autorización.')
        recovery_manager = getattr(self.app, 'session_recovery', None)
        recovery_status = recovery_manager.status() if recovery_manager is not None else (getattr(self.app, 'session_recovery_status', {}) or {})
        previous = recovery_status.get('previous_abnormal') if isinstance(recovery_status, dict) else None
        recovery_card = self._card(); recovery_card.pack(fill='x', padx=8, pady=5)
        ctk.CTkLabel(recovery_card, text='RECUPERACIÓN DE SESIÓN', font=(FONT, 8, 'bold'), text_color=MUTED, anchor='w').pack(fill='x', padx=12, pady=(10, 2))
        if isinstance(previous, dict):
            ctk.CTkLabel(recovery_card, text='Se detectó un cierre no limpio en la sesión anterior', font=(FONT, 11, 'bold'), text_color=AMBER, anchor='w').pack(fill='x', padx=12, pady=(0, 3))
            ctk.CTkLabel(recovery_card, text='CorePulse revisó los rollbacks temporales disponibles al iniciar. Los tweaks persistentes elegidos por el usuario NO se revierten automáticamente.', font=(FONT, 9), text_color=TEXT2, anchor='w', justify='left', wraplength=990).pack(fill='x', padx=12, pady=(0, 6))
        else:
            ctk.CTkLabel(recovery_card, text='La sesión anterior cerró correctamente o no existe evidencia de un cierre anormal.', font=(FONT, 10, 'bold'), text_color=GREEN, anchor='w').pack(fill='x', padx=12, pady=(0, 5))
        for action in (recovery_status.get('recovery_actions') or [])[:4] if isinstance(recovery_status, dict) else []:
            self._line(recovery_card, f"{action.get('component')}: {action.get('message') or 'revisión completada'}")
        history = recovery_status.get('history') or [] if isinstance(recovery_status, dict) else []
        abnormal_count = sum(1 for x in history if isinstance(x, dict) and x.get('type') == 'abnormal_shutdown')
        report_path = recovery_status.get('crash_report_path') if isinstance(recovery_status, dict) else None
        if report_path:
            ctk.CTkLabel(recovery_card, text=f'Reporte técnico local: {_short(report_path, 150)}', font=(FONT, 8), text_color=MUTED, anchor='w', justify='left', wraplength=990).pack(fill='x', padx=12, pady=(1, 2))
        ctk.CTkLabel(recovery_card, text=f'Historial reciente: {abnormal_count} cierre(s) no limpio(s) registrado(s) · marcador actual activo', font=(FONT, 8), text_color=MUTED, anchor='w').pack(fill='x', padx=12, pady=(2, 10))
        r=self._restore
        card=self._card(); card.pack(fill='x',padx=8,pady=5)
        head = ctk.CTkFrame(card, fg_color='transparent')
        head.pack(fill='x', padx=12, pady=(10, 4))
        ctk.CTkLabel(head, text='PUNTOS DE RESTAURACIÓN DEL SISTEMA', font=(FONT, 9, 'bold'), text_color=TEXT, anchor='w').pack(side='left')
        self._button(head, 'Actualizar lista', self._refresh_restore_points, variant='ghost', height=28, width=110).pack(side='right')
        self._kv(card,'Administrador','Sí' if (r or {}).get('admin') else 'No')
        self._kv(card,'Restaurar sistema','Disponible' if (r or {}).get('available') else 'No disponible / pendiente',GREEN if (r or {}).get('available') else AMBER)
        if r and r.get('error'):
            self._kv(card,'Detalle',_short(r.get('error'),180),AMBER)
        pts=(r or {}).get('points') or []
        count = int((r or {}).get('count') or len(pts))
        self._kv(card, 'Puntos encontrados', str(count), GREEN if count else TEXT2)
        if pts:
            list_box = ctk.CTkFrame(card, fg_color=CARD2, border_width=1, border_color=BORDER, corner_radius=9)
            list_box.pack(fill='x', padx=12, pady=(6, 7))
            type_names = {
                '0':'Aplicación instalada', '1':'Aplicación desinstalada', '10':'Controlador instalado',
                '12':'Modificación del sistema', '13':'Cancelado', '14':'Copia de seguridad',
                '16':'Modificación del sistema', '17':'Operación de dispositivo', '18':'Modificación del sistema',
            }
            for index, point in enumerate(pts):
                if not isinstance(point, dict):
                    continue
                row = ctk.CTkFrame(list_box, fg_color='transparent')
                row.pack(fill='x', padx=9, pady=(7 if index == 0 else 3, 3))
                left = ctk.CTkFrame(row, fg_color='transparent')
                left.pack(side='left', fill='x', expand=True)
                desc = str(point.get('Description') or 'Punto de restauración')
                created = str(point.get('CreationTime') or 'Fecha no disponible')
                rp_type = str(point.get('RestorePointType') if point.get('RestorePointType') is not None else 'N/A')
                type_label = type_names.get(rp_type, f'Tipo {rp_type}' if rp_type != 'N/A' else 'Tipo N/A')
                ctk.CTkLabel(left, text=desc, font=(FONT, 9, 'bold'), text_color=TEXT, anchor='w').pack(fill='x')
                ctk.CTkLabel(left, text=f'{created} · {type_label}', font=(FONT, 7), text_color=MUTED, anchor='w').pack(fill='x', pady=(1,0))
                ctk.CTkLabel(row, text=f"#{point.get('SequenceNumber') if point.get('SequenceNumber') is not None else 'N/A'}", font=(FONT, 8, 'bold'), text_color=CYAN).pack(side='right', padx=(8,0))
                if index < len(pts)-1:
                    ctk.CTkFrame(list_box, fg_color=BORDER, height=1, corner_radius=0).pack(fill='x', padx=9, pady=(2,0))
        elif r is not None and not r.get('error'):
            ctk.CTkLabel(card, text='Windows no devolvió puntos de restauración existentes.', font=(FONT, 8), text_color=MUTED, anchor='w').pack(fill='x', padx=12, pady=(5,7))
        self.btn_restore=self._button(card,'Crear punto de restauración',self._create_restore,variant='primary',height=34); self.btn_restore.pack(anchor='w',padx=12,pady=(7,11))
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
        job_tab = self._tab
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
                # El benchmark V180 publica sus resultados en el host existente,
                # sin vaciar todo el Canvas. Los demás trabajos mantienen render normal.
                if self._tab == job_tab and self._visible and name != 'visual_benchmark':
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
        if key == 'corepulse' and self._corepulse_diag is None:
            self._load_corepulse_diagnostics()

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

    def _set_startup_page(self, page):
        items = list((self._startup or {}).get('items') or [])
        page_size = max(1, int(getattr(self, '_startup_page_size', 30) or 30))
        page_count = max(1, (len(items) + page_size - 1) // page_size)
        self._startup_page = max(0, min(int(page), page_count - 1))
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
    def _startup_action(self, source_id, *, restore=False, name='Elemento'):
        if 'startup_action' in self._jobs:
            return
        if not restore:
            try:
                ok = messagebox.askyesno(
                    'Inicio de Windows',
                    f'¿Deshabilitar “{name}” del inicio de Windows?\n\nCorePulse guardará una copia reversible y no eliminará la aplicación.',
                    parent=self.frame,
                )
            except Exception:
                ok = False
            if not ok:
                return
        fn = (lambda: restore_startup_item(source_id)) if restore else (lambda: disable_startup_item(source_id))
        def done(result, error):
            message = (result or {}).get('message') if isinstance(result, dict) else error
            if isinstance(result, dict) and result.get('success'):
                try:
                    self._startup = analyze_startup()
                except Exception:
                    pass
                try:
                    messagebox.showinfo('Inicio de Windows', message or 'Operación completada.', parent=self.frame)
                except Exception:
                    pass
            else:
                try:
                    messagebox.showwarning('Inicio de Windows', message or 'No se pudo completar la operación.', parent=self.frame)
                except Exception:
                    pass
        self._async('startup_action', fn, done)

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
            if name == 'startup':
                self._startup_page = 0
            elif name == 'services':
                self._services_page = 0
            elif name == 'drivers':
                self._drivers_page = 0
                if isinstance(payload, dict):
                    try:
                        self.app.driver_inventory_cache = copy.deepcopy(payload)
                        self.app.driver_inventory_cache_timestamp = time.time()
                    except Exception:
                        pass
            elif name == 'crashes':
                self._stability_page = 0
                try:
                    store = getattr(self.app, 'health_history_store', None)
                    if store is not None:
                        store.record_stability_snapshot(payload, period_days=7)
                except Exception:
                    logger.exception('[HEALTH_CENTER] No se pudo persistir snapshot de estabilidad')
        self._async(name, fn, done)

    def _capture_slot(self,slot):
        tele=copy.deepcopy(getattr(self.app,'latest_telemetry',{}) or {}); disks=copy.deepcopy(getattr(self.app,'latest_disks',[]) or [])
        batt=self._battery or collect_battery_health(tele)
        save_snapshot(capture_metrics(tele,disks,batt,label=slot),slot=slot); self._render()

    def _save_hw_baseline(self):
        tele=copy.deepcopy(getattr(self.app,'latest_telemetry',{}) or {}); disks=copy.deepcopy(getattr(self.app,'latest_disks',[]) or [])
        def work(): return save_hardware_baseline(collect_hardware_inventory(tele,disks))
        self._async('save_hw',work,lambda r,e:(setattr(self,'_hw',{'baseline_exists':True,'changes':[],'current':r}) if r else None))

    def _refresh_restore_points(self):
        if 'restore' in self._jobs:
            return
        self._restore = None
        def done(result, error):
            self._restore = result or {'available': False, 'points': [], 'count': 0, 'error': error}
        self._async('restore', restore_point_status, done)

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
        dynamic_blockers = {'profile_change', 'visual_benchmark', 'game_scan'}
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
        if not self._visible and self._tab == 'audio':
            panel = getattr(self, '_audio_panel', None)
            if panel is not None:
                panel.service.cancel.set()
                panel.service.clear_recording()
        if not self._visible and self._performance_after_id is not None:
            try: self.app.after_cancel(self._performance_after_id)
            except Exception: pass
            self._performance_after_id = None
        elif self._visible and self._performance_only and not self._benchmark_only and self._performance_after_id is None and self._alive:
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
        hud = getattr(self, '_benchmark_hud', None)
        if hud is not None:
            try: hud.destroy()
            except Exception: pass
        self._benchmark_hud = None
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
