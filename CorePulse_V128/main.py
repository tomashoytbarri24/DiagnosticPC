"""Punto de entrada de CorePulse. Coordina interfaz, telemetría, diagnóstico, base de datos, overlay y reporte."""
import sys
from core.python_compat import enforce_minimum_python
enforce_minimum_python()
from core.theme_manager import color as theme_color, get_ctk_appearance_mode, brand_symbol_path, theme_action_label, role_color
# Código refactorizado: nombres estables y documentación en español.
from pathlib import Path
from core.runtime_logging import configure_runtime_logging, get_logger, install_exception_hooks
from core.runtime_paths import resource_root, data_path, diagnostics_dir
RUNTIME_LOG_PATH = configure_runtime_logging()
install_exception_hooks()
logger = get_logger('main')
import customtkinter as ctk
import threading
import time
import psutil
import os
import platform
import copy
import math
from core.version import VERSION_LABEL
COREPULSE_ENV_STATUS = {"status": "DEFERRED", "loaded": False}
IS_WINDOWS = platform.system() == 'Windows'
from collections import deque
from tkinter import messagebox, filedialog
from datetime import datetime
from PIL import Image, ImageTk
from gui.dashboard import apply_professional_dashboard, refresh_professional_charts
from gui.thermal_health_binding import apply_thermal_health_semantics
from gui.live_health_binding import apply_live_health_authority
from gui.dashboard_layout import apply_dashboard_architecture, render_agent_card
from gui.sidebar import apply_clean_text_sidebar
from gui.hardware_storage_view import apply_hardware_storage_information_architecture
from gui.stable_scroll import StableScrollHost
from gui.monitoring_status import apply_monitoring_service_agent_separation
from gui.dialogs import info as cp_info, warning as cp_warning, error as cp_error
from gui.ui_consistency import apply_ui_consistency, refresh_navigation_state
from gui.integration import apply_runtime_integration
from gui.adaptive_window import apply_preferred_launch_geometry
from gui.internal_navigation import activate_internal_page, commit_internal_page, attach_internal_page_panel, abort_internal_page, clear_internal_page, show_dashboard
from core.overlay_preferences import load_overlay_preferences
from core.global_hotkeys import CAPTURE_VERSION, GlobalHotkeyManager

# Configuración visual global de la aplicación.
ctk.set_appearance_mode(get_ctk_appearance_mode())
# V128: roles estructurales directos; el primer frame nace ya con la misma
# paleta exacta que la previsualización y no depende de inferencias posteriores.
BG_MAIN = role_color('bg')
BG_CARD = role_color('surface')
BG_SIDEBAR = role_color('sidebar')
BORDER_COLOR = role_color('border')
COLOR_CPU = role_color('accent')
COLOR_RAM = '#10b981'
COLOR_GPU = '#a855f7'
COLOR_TEXT_DIM = role_color('muted')

class _DeferredAgent:
    """Estado neutro hasta que el agente real termine de iniciar en background."""
    thread = None
    running = False

    def get_state(self):
        return {
            'mode': 'DESKTOP', 'context': 'DESKTOP', 'overall': 'UNKNOWN',
            'game': None, 'alerts': {'active': [], 'history': []},
            'findings': [], 'timestamp': time.time(),
        }

    def stop(self):
        return None


class _DeferredTray:
    """No-op seguro mientras el icono de bandeja real se carga de forma progresiva."""
    available = False
    running = False

    def notify_game_boost(self, *_args, **_kwargs):
        return False

    def notify_state(self):
        return None

    def notify_minimized(self):
        return None

    def stop(self):
        return None


# Coordinador principal: conecta interfaz, telemetría, diagnóstico, persistencia y reporte.
class App(ctk.CTk):

    def toggle_ui_theme(self):
        """Compatibilidad: el antiguo toggle ahora abre la galería Temas."""
        return self.open_themes()

    def open_update_center(self):
        """Abre el centro manual de GitHub Releases para pruebas internas."""
        try:
            from gui.update_dialog import show_update_dialog
            return show_update_dialog(self)
        except Exception as exc:
            cp_error(self, 'Actualizaciones', f'No se pudo abrir el centro de actualizaciones:\n\n{exc}')
            return None

    def open_themes(self):
        """Abre Temas como módulo interno, sin crear una ventana adicional."""
        if not self.is_running:
            return
        host = None
        try:
            host, reused = activate_internal_page(self, 'themes')
            if reused and getattr(self, 'theme_panel', None) is not None:
                return
            if host is None:
                return
            from gui.theme_panel import ThemePanel
            panel = ThemePanel(self, host)
            self.theme_panel = panel
            if not commit_internal_page(self, 'themes', host, panel):
                self.theme_panel = None
        except Exception as exc:
            self.theme_panel = None
            abort_internal_page(self, 'themes', host)
            cp_error(self, 'Temas', f'No se pudo abrir el selector de temas:\n\n{exc}')

    def _open_generated_pdf(self, pdf_path):
        try:
            path = Path(pdf_path).resolve()
            if not path.is_file():
                return False
            if sys.platform.startswith('win'):
                os.startfile(str(path))
                return True
            return False
        except Exception as exc:
            logger.warning('PDF guardado, pero no se pudo abrir automáticamente: %s', exc)
            return False

    def _remember_last_pdf_report(self, pdf_path):
        """Conserva el último PDF válido para reabrirlo desde Diagnóstico."""
        try:
            path = Path(pdf_path).expanduser().resolve()
            if not path.is_file():
                return None
            self.last_pdf_report_path = str(path)
            pointer = Path(data_path('last_pdf_report.txt'))
            pointer.parent.mkdir(parents=True, exist_ok=True)
            pointer.write_text(str(path), encoding='utf-8')
            panel = getattr(self, 'diagnostic_experience_panel', None)
            try:
                if panel is not None and panel.winfo_exists():
                    panel.refresh_report_access()
            except Exception:
                pass
            return str(path)
        except Exception as exc:
            logger.warning('No se pudo recordar el último PDF: %s', exc)
            return None

    def get_last_pdf_report_path(self):
        """Devuelve únicamente un PDF que todavía exista en disco."""
        candidates = [getattr(self, 'last_pdf_report_path', None)]
        try:
            pointer = Path(data_path('last_pdf_report.txt'))
            if pointer.is_file():
                candidates.append(pointer.read_text(encoding='utf-8').strip())
        except Exception:
            pass
        for candidate in candidates:
            if not candidate:
                continue
            try:
                path = Path(candidate).expanduser().resolve()
                if path.is_file() and path.suffix.lower() == '.pdf':
                    self.last_pdf_report_path = str(path)
                    return str(path)
            except Exception:
                continue

        # Si el puntero no existe (por ejemplo tras actualizar CorePulse), busca el
        # informe más reciente en la carpeta autoritativa de Diagnóstico/AppData.
        try:
            reports = sorted(
                Path(diagnostics_dir()).glob('Reporte_CorePulse_*.pdf'),
                key=lambda item: item.stat().st_mtime,
                reverse=True,
            )
            if reports:
                self.last_pdf_report_path = str(reports[0].resolve())
                return self.last_pdf_report_path
        except Exception:
            pass
        return None

    def open_last_pdf_report(self):
        """Abre desde CorePulse el último informe PDF que siga disponible."""
        path = self.get_last_pdf_report_path()
        if not path:
            cp_warning(self, 'Reportes', 'Todavía no hay un informe PDF disponible para abrir. Genera uno desde el diagnóstico.')
            return False
        opened = self._open_generated_pdf(path)
        if not opened:
            cp_warning(self, 'Reportes', f'El PDF existe, pero Windows no pudo abrirlo automáticamente:\n\n{path}')
        return opened

    def show_last_pdf_report_folder(self):
        """Abre la carpeta fija de informes de CorePulse en AppData."""
        try:
            folder = Path(diagnostics_dir()).resolve()
            folder.mkdir(parents=True, exist_ok=True)
            if sys.platform.startswith('win'):
                os.startfile(str(folder))
                return True
        except Exception as exc:
            logger.warning('No se pudo abrir la carpeta de informes: %s', exc)
        cp_warning(self, 'Reportes', f'No se pudo abrir la carpeta automáticamente.\n\nRuta de informes:\n{diagnostics_dir()}')
        return False

    def _log_throttled_exception(self, key, message, interval_seconds=15.0):
        """Registra fallos repetitivos sin inundar el log durante el monitoreo."""
        now = time.monotonic()
        stamps = getattr(self, '_runtime_error_log_stamps', None)
        if not isinstance(stamps, dict):
            stamps = {}
            self._runtime_error_log_stamps = stamps
        last = float(stamps.get(str(key), 0.0) or 0.0)
        if now - last >= float(interval_seconds):
            stamps[str(key)] = now
            logger.exception(message)

    def __init__(self):
        super().__init__()
        # V119 — marcador de sesión persistente. Si el proceso muere antes de
        # ``on_close``, el siguiente inicio podrá distinguir un cierre anormal
        # de un cierre normal sin tocar tweaks persistentes del usuario.
        self.session_recovery = None
        self.session_recovery_status = {}
        self._recovery_heartbeat_after = None
        try:
            from core.session_recovery import SessionRecoveryManager
            self.session_recovery = SessionRecoveryManager()
            self.session_recovery_status = self.session_recovery.begin_session()
        except Exception:
            logger.exception('[RECOVERY] No se pudo iniciar el marcador de sesión')
        # La ventana principal permanece bloqueada hasta que terminen los hitos
        # reales del arranque. La pantalla de preparación es la primera UI visible.
        self._startup_gate_active = True
        self._startup_gate = None
        self._startup_reveal_scheduled = False
        self._startup_gate_started_at = time.monotonic()
        self._startup_integrity_watchdog_after = None
        self._startup_integrity_ok = None
        self._startup_integrity_detail = ''
        self._startup_parts = {'layout': 0.0, 'charts': 0.0, 'services': 0.0, 'integrity': 0.0}
        self._startup_weights = {'layout': 0.24, 'charts': 0.18, 'services': 0.33, 'integrity': 0.20}
        try:
            self.withdraw()
        except Exception:
            pass
        try:
            from core.startup_profiler import startup_mark
            startup_mark('app_init_begin')
        except Exception:
            pass
        self.title('CorePulse — Hardware Monitoring & Diagnostics')
        self.resizable(True, True)
        self.configure(fg_color=BG_MAIN)
        # V113: CorePulse usa chrome propio integrado en la app.
        # El cierre desde el botón X interno cierra la aplicación; minimizar se
        # maneja de forma explícita con el botón del título.
        self.protocol('WM_DELETE_WINDOW', self.on_close)
        self._custom_chrome_enabled = False
        self._custom_maximized = False
        self._custom_restore_geometry = None
        self._titlebar_drag_origin = None
        self._titlebar_height = 36
        try:
            from gui.startup_gate import StartupGate
            self._startup_gate = StartupGate(self)
            self._startup_gate.show()
            self._startup_mark('startup_gate_visible')
            self.update_startup_component('layout', 0.12, 'Preparando interfaz…')
        except Exception:
            logger.exception('[STARTUP] No se pudo mostrar la pantalla de preparación')
            # Mantiene la raíz oculta durante el resto del constructor para no
            # exponer una interfaz parcial. El fallback se publica al terminar el layout.
            self._startup_gate = None
            self._startup_gate_active = True
        project_root = resource_root()
        icon_path = project_root / 'assets' / 'app_icon.ico'
        symbol_path = project_root / 'assets' / 'CorePulseWindowIcon.png'
        if icon_path.exists():
            try:
                self.iconbitmap(str(icon_path))
            except Exception:
                pass
        if symbol_path.exists():
            try:
                self._corepulse_window_icon = ImageTk.PhotoImage(Image.open(symbol_path).convert('RGBA').resize((64, 64), Image.Resampling.LANCZOS))
                self.iconphoto(True, self._corepulse_window_icon)
            except Exception:
                pass
        self.is_fullscreen = False
        self.is_resizing = False
        self.resize_timer = None
        # V0.10.2.81w: el primer frame no espera base de datos, agente, Gaming,
        # batería, SMART, IA ni capacidades opcionales. Todos esos servicios se
        # inicializan después de publicar el layout profesional.
        self.is_running = True
        self._services_ready = False
        self._services_booting = False
        self._charts_ready = False
        self._runtime_integrity_ready = False
        # 64w: el gate no se libera al iniciar el hilo de telemetría. Debe existir
        # al menos una muestra real adquirida y aplicada completamente a la UI.
        self._startup_first_telemetry_acquired = False
        self._startup_first_telemetry_applied = False
        self._telemetry_ui_apply_count = 0
        self.realtime_agent = _DeferredAgent()
        self.game_detector = None
        self.performance_manager = None
        self.alert_history_store = None
        self.alert_history_panel = None
        self.agent_status_panel = None
        self.diagnostic_explainer = None
        self.smart_alert_panel = None
        self.smart_alert_window = None
        self.alert_history_window = None
        self.lbl_alert_summary = None
        self.tray_service = _DeferredTray()
        self._tray_ram_cleanup_running = False
        self.agent_after_id = None
        self.overlay_window = None
        self.overlay_config_window = None
        self.overlay_config_panel = None
        self.gaming_panel = None
        self.benchmark_panel = None
        self.overlay_hotkey_manager = GlobalHotkeyManager(callback=self._on_overlay_hotkey)
        self._minimized_to_tray = False
        self.latest_telemetry = None
        self.latest_disks = []
        self.latest_score = None
        self.session_trend_collector = None
        self.session_trends_window = None
        self.session_trends_panel = None
        self._internal_page_host = None
        self._active_internal_page = None
        self.storage_detail_panel = None
        self.telemetry_detail_panel = None
        self.cpu_detail_panel = None
        self.gpu_detail_panel = None
        self.ram_detail_panel = None
        self.network_detail_panel = None
        self.windows_tweaks_panel = None
        self.health_center_panel = None
        self.health_history_store = None
        self.thermal_throttling_detector = None
        self.thermal_throttling_state = {'cpu': {'state': 'N/A'}, 'gpu': {'state': 'N/A'}}
        self._health_history_last_record = 0.0
        self.battery_health_cache = None
        self.battery_health_cache_timestamp = 0.0
        self.battery_presence_cache = None
        self._battery_health_refresh_running = False
        self._battery_health_refresh_after_id = None
        self.health_center_hardware_cache = None
        self.health_center_hardware_cache_timestamp = 0.0
        self._health_center_prewarm_started = False
        self._navigation_modules_prewarm_started = False
        self.storage_health_cache = {}
        self._storage_health_refresh_running = False
        self._prime_battery_presence_cache()
        self.diagnostic_session = None
        self.max_points = 25
        self.cpu_history = deque([float('nan')] * self.max_points, maxlen=self.max_points)
        self.ram_history = deque([float('nan')] * self.max_points, maxlen=self.max_points)
        self.gpu_history = deque([float('nan')] * self.max_points, maxlen=self.max_points)
        self.db_counter = 0
        self._pdf_export_in_progress = False
        self._pdf_export_job = None
        self.last_pdf_report_path = None
        self.diagnostic_result = None
        self.current_recommendation_pipeline = None
        self.diagnostic_json_path = None
        self.diagnostic_telemetry_snapshot = None
        self.diagnostic_disks_snapshot = None
        try:
            self.after(1200, self._configure_overlay_hotkey)
        except Exception:
            pass
        self.diagnostic_score_snapshot = None
        self.diagnostic_after_id = None
        self.diagnostic_experience_panel = None
        self.telemetry_lock = threading.Lock()
        self.pending_telemetry = None
        self.pending_disks = []
        self.telemetry_after_id = None
        self.chart_after_id = None
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.sidebar = ctk.CTkFrame(self, fg_color=BG_SIDEBAR, corner_radius=0, width=230)
        self.sidebar.grid(row=0, column=0, sticky='nsew')
        self.sidebar.grid_propagate(False)
        self.frame_logo = ctk.CTkFrame(self.sidebar, fg_color='transparent')
        # 61w: no legacy pack; dashboard.py publica el sidebar una sola vez.
        logo_img_path = None
        project_root = resource_root()
        for possible_path in [brand_symbol_path(project_root), project_root / 'assets' / 'CorePulseIcon.png']:
            if possible_path.exists():
                logo_img_path = str(possible_path)
                break
        if logo_img_path:
            try:
                pil_img = Image.open(logo_img_path)
                self.ctk_logo = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(28, 28))
                self.lbl_logo_icon = ctk.CTkLabel(self.frame_logo, image=self.ctk_logo, text='')
                self.lbl_logo_icon.pack(side='left', padx=(0, 8))
            except Exception:
                pass
        # Branding minimalista: los labels se conservan como referencias de compatibilidad,
        # pero no se muestran. La barra lateral deja únicamente el símbolo de CorePulse.
        self.lbl_brand = ctk.CTkLabel(self.frame_logo, text='', font=('Segoe UI', 18, 'bold'), text_color=theme_color('#f8fafc'))
        self.lbl_subtitle = ctk.CTkLabel(self.sidebar, text='', font=('Segoe UI', 10), text_color=COLOR_TEXT_DIM)
        self.card_health_sidebar = ctk.CTkFrame(self.sidebar, fg_color=BG_CARD, border_width=1, border_color=BORDER_COLOR, corner_radius=10)
        ctk.CTkLabel(self.card_health_sidebar, text='SALUD DEL SISTEMA', font=('Segoe UI', 9, 'bold'), text_color=COLOR_TEXT_DIM).pack(anchor='w', padx=12, pady=(10, 2))
        self.lbl_health_val = ctk.CTkLabel(self.card_health_sidebar, text='--%', font=('Segoe UI', 22, 'bold'), text_color=COLOR_RAM)
        self.lbl_health_val.pack(anchor='w', padx=12, pady=(0, 2))
        self.lbl_health_status = ctk.CTkLabel(self.card_health_sidebar, text='Evaluando...', font=('Segoe UI', 10, 'bold'), text_color=theme_color('#f8fafc'))
        self.lbl_health_status.pack(anchor='w', padx=12, pady=(0, 10))
        self.btn_overlay = ctk.CTkButton(self.sidebar, text='Gaming', fg_color='transparent', hover_color=theme_color('#14253b'), text_color=theme_color('#f4f7fb'), font=('Segoe UI', 11, 'bold'), height=34, corner_radius=8, command=self.open_gaming)
        self.btn_benchmark = ctk.CTkButton(self.sidebar, text='Benchmark', fg_color='transparent', hover_color=theme_color('#14253b'), text_color=theme_color('#f4f7fb'), font=('Segoe UI', 11, 'bold'), height=34, corner_radius=8, command=self.open_benchmark)
        self.btn_diagnostic = ctk.CTkButton(self.sidebar, text='Iniciar diagnóstico', fg_color='transparent', hover_color=theme_color('#14253b'), text_color=theme_color('#f4f7fb'), font=('Segoe UI', 11, 'bold'), height=34, corner_radius=8, command=self.start_diagnostic_session)
        self.btn_health_center = ctk.CTkButton(self.sidebar, text='Centro de salud', fg_color='transparent', hover_color=theme_color('#14253b'), text_color=theme_color('#f4f7fb'), font=('Segoe UI', 11, 'bold'), height=34, corner_radius=8, command=self.open_health_center)
        self.btn_pdf = ctk.CTkButton(self.sidebar, text='Reportes', fg_color='transparent', hover_color=theme_color('#14253b'), text_color=theme_color('#66788f'), font=('Segoe UI', 11, 'bold'), height=34, corner_radius=8, command=self.export_pdf_report, state='disabled')
        self.btn_cleanup = ctk.CTkButton(self.sidebar, text='🧹 Limpieza de Sistema', fg_color='#8b5cf6', hover_color='#7c3aed', text_color='#ffffff', font=('Segoe UI', 11, 'bold'), height=34, corner_radius=8, command=self.run_cleanup)
        self.btn_tweaks = ctk.CTkButton(self.sidebar, text='Tweaks Windows 11', fg_color='transparent', hover_color=theme_color('#14253b'), text_color=theme_color('#f4f7fb'), font=('Segoe UI', 11, 'bold'), height=34, corner_radius=8, command=self.open_windows_tweaks)
        self.btn_network = ctk.CTkButton(self.sidebar, text='Red avanzada', fg_color='transparent', hover_color=theme_color('#14253b'), text_color=theme_color('#f4f7fb'), font=('Segoe UI', 11, 'bold'), height=34, corner_radius=8, command=self.open_network_details)
        self.btn_smart_alerts = ctk.CTkButton(self.sidebar, text='🚨 Alertas y Diagnóstico', fg_color='#1d4ed8', hover_color='#1e40af', text_color='#ffffff', font=('Segoe UI', 11, 'bold'), height=34, corner_radius=8, command=self.open_smart_alert_window)
        self.btn_alert_history = ctk.CTkButton(self.sidebar, text='🕘 Historial de Alertas', fg_color='#334155', hover_color='#475569', text_color='#ffffff', font=('Segoe UI', 11, 'bold'), height=34, corner_radius=8, command=self.open_alert_history_window)
        self.btn_session_trends = ctk.CTkButton(self.sidebar, text='📈 Tendencias de Sesiones', fg_color='#334155', hover_color='#475569', text_color='#ffffff', font=('Segoe UI', 11, 'bold'), height=34, corner_radius=8, command=self.open_session_trends_window)
        self._legacy_shortcuts_label = ctk.CTkLabel(self.sidebar, text='[F11] Pantalla Completa\n[Esc] Modo Ventana', font=('Segoe UI', 9), text_color=COLOR_TEXT_DIM, justify='center')
        self.main_content = ctk.CTkFrame(self, fg_color='transparent')
        self.main_content.grid(row=0, column=1, sticky='nsew', padx=15, pady=15)
        self.frame_meters = ctk.CTkFrame(self.main_content, fg_color='transparent')
        self.card_cpu = self.create_metric_card(self.frame_meters, 'CPU')
        self.card_cpu.pack(side='left', expand=True, fill='both', padx=(0, 5))
        self.lbl_cpu, self.bar_cpu, self.lbl_cpu_temp, self.lbl_cpu_title = self.build_card_content(self.card_cpu, COLOR_CPU)
        self.card_ram = self.create_metric_card(self.frame_meters, 'MEMORIA RAM')
        self.card_ram.pack(side='left', expand=True, fill='both', padx=3)
        self.lbl_ram, self.bar_ram, self.lbl_ram_gb, self.lbl_ram_title = self.build_card_content(self.card_ram, COLOR_RAM)
        self.card_gpu = self.create_metric_card(self.frame_meters, 'GPU')
        self.card_gpu.pack(side='left', expand=True, fill='both', padx=(5, 0))
        self.lbl_gpu, self.bar_gpu, self.lbl_gpu_temp, self.lbl_gpu_title = self.build_card_content(self.card_gpu, COLOR_GPU)
        self.alert_summary_bar = ctk.CTkFrame(self.main_content, fg_color=BG_CARD, border_width=1, border_color=BORDER_COLOR, corner_radius=10)
        self.lbl_alert_summary = ctk.CTkLabel(self.alert_summary_bar, text='MONITOREO INICIANDO', font=('Segoe UI', 11, 'bold'), text_color=COLOR_RAM)
        self.lbl_alert_summary.pack(side='left', padx=12, pady=9)
        self.btn_alert_summary = ctk.CTkButton(self.alert_summary_bar, text='Ver diagnóstico', width=120, height=26, fg_color=theme_color('#1e3a5f'), hover_color=theme_color('#284f7a'), text_color=theme_color('#f8fafc'), font=('Segoe UI', 10, 'bold'), command=self.open_smart_alert_window)
        self.btn_alert_summary.pack(side='right', padx=8, pady=6)
        self.storage_section_label = ctk.CTkLabel(self.main_content, text='UNIDADES DE ALMACENAMIENTO DETECTADAS', font=('Segoe UI', 10, 'bold'), text_color=COLOR_TEXT_DIM)
        self.scroll_disks = StableScrollHost(self.main_content, fg_color=theme_color('#06111f'), height=120)
        # V0.10.2.28w: el Canvas interno de StableScrollHost solicita una altura
        # propia. Sin bloquear la propagación GRID, esa altura agranda el host y
        # deja un bloque vacío entre Almacenamiento y los gráficos. La altura del
        # viewport debe obedecer al Dashboard, no al request del Canvas interno.
        self.scroll_disks.grid_propagate(False)
        self.disk_widgets = {}
        self.frame_charts = ctk.CTkFrame(self.main_content, fg_color=role_color('surface_2'), border_width=1, border_color=BORDER_COLOR, corner_radius=10)
        # 61w: Matplotlib/TkAgg no pertenece al first frame. El contenedor sí
        # existe para que la geometría profesional sea estable desde el inicio.
        self.fig = None
        self.ax_cpu = self.ax_ram = self.ax_gpu = None
        self.line_cpu = self.line_ram = self.line_gpu = None
        self.canvas = None
        self.background = None
        apply_professional_dashboard(self)
        apply_thermal_health_semantics(self)
        apply_live_health_authority(self)
        apply_dashboard_architecture(self)
        apply_clean_text_sidebar(self)
        apply_hardware_storage_information_architecture(self)
        apply_monitoring_service_agent_separation(self)
        apply_preferred_launch_geometry(self)
        apply_ui_consistency(self)
        apply_runtime_integration(self)
        self._startup_mark('professional_layout_ready')
        self.update_startup_component(
            'layout', 1.0, 'Interfaz principal preparada',
            'Iniciando componentes reales en segundo plano…'
        )
        if self._startup_gate is None and self._startup_gate_active:
            # Fallback extremo: si el gate visual no pudo crearse, publica sólo
            # el layout profesional ya terminado; nunca una construcción parcial.
            self._startup_gate_active = False
            try:
                self.deiconify()
            except Exception:
                pass
        self.telemetry_thread = None
        # El primer callback idle sólo marca/publica el frame. Las tareas costosas
        # se encadenan después para que ninguna capacidad opcional tenga autoridad
        # sobre el tiempo de aparición de la ventana.
        self.after_idle(self._after_first_frame)
        logger.info('[CORE] First-frame layout preparado version=%s python=%s', VERSION_LABEL, platform.python_version())

    def _startup_mark(self, stage, **meta):
        try:
            from core.startup_profiler import startup_mark
            startup_mark(stage, **meta)
        except Exception:
            pass

    def update_startup_component(self, component, fraction, message, detail=None):
        """Actualiza la carga usando hitos reales; no crea telemetría ni resultados ficticios."""
        if component not in getattr(self, '_startup_parts', {}):
            return
        try:
            fraction = min(1.0, max(0.0, float(fraction)))
        except Exception:
            fraction = 0.0
        self._startup_parts[component] = max(float(self._startup_parts.get(component, 0.0)), fraction)
        progress = 0.05
        for key, weight in self._startup_weights.items():
            progress += float(weight) * float(self._startup_parts.get(key, 0.0))
        progress = min(1.0, max(0.0, progress))
        gate = getattr(self, '_startup_gate', None)
        if gate is not None and getattr(self, '_startup_gate_active', False):
            gate.update_stage(message, progress, detail)
        self._maybe_finish_startup_gate()

    def _maybe_finish_startup_gate(self):
        """Libera la UI cuando el núcleo real está listo, sin deadlock por auditorías opcionales.

        Layout, gráficos y la primera telemetría aplicada siguen siendo obligatorios.
        La auditoría profunda de integridad intenta terminar antes de liberar el gate,
        pero nunca puede retener la aplicación indefinidamente: después de 12 s se
        continúa en segundo plano. El launch gate y el runtime autocurable ya validan
        los requisitos esenciales antes de llegar aquí.
        """
        if not getattr(self, '_startup_gate_active', False):
            return
        parts = getattr(self, '_startup_parts', {})
        core_keys = ('layout', 'charts', 'services')
        if not parts or not all(float(parts.get(key, 0.0)) >= 1.0 for key in core_keys):
            return
        if getattr(self, '_startup_reveal_scheduled', False):
            return

        integrity_ready = float(parts.get('integrity', 0.0)) >= 1.0
        elapsed = max(0.0, time.monotonic() - float(getattr(self, '_startup_gate_started_at', time.monotonic())))
        max_wait = 12.0
        if not integrity_ready and elapsed < max_wait:
            if getattr(self, '_startup_integrity_watchdog_after', None) is None:
                delay_ms = max(100, int((max_wait - elapsed) * 1000))
                try:
                    self._startup_integrity_watchdog_after = self.after(delay_ms, self._startup_integrity_watchdog)
                except Exception:
                    self._startup_integrity_watchdog_after = None
            return

        self._startup_reveal_scheduled = True
        limited = self._startup_integrity_ok is False
        integrity_deferred = not integrity_ready
        gate = getattr(self, '_startup_gate', None)
        if gate is not None:
            if integrity_deferred:
                gate.update_stage(
                    'CorePulse está listo', 1.0,
                    'La comprobación profunda continúa en segundo plano sin bloquear el panel.'
                )
            else:
                gate.mark_ready(limited=limited)
        self._startup_mark(
            'startup_gate_complete', limited=limited,
            integrity_deferred=integrity_deferred,
            gate_elapsed_seconds=round(elapsed, 3),
        )
        try:
            self.after(180, self._reveal_main_window)
        except Exception:
            self._reveal_main_window()

    def _startup_integrity_watchdog(self):
        self._startup_integrity_watchdog_after = None
        if not getattr(self, '_startup_gate_active', False):
            return
        self._maybe_finish_startup_gate()

    def _reveal_main_window(self):
        if not getattr(self, '_startup_gate_active', False):
            return
        watchdog = getattr(self, '_startup_integrity_watchdog_after', None)
        if watchdog is not None:
            try:
                self.after_cancel(watchdog)
            except Exception:
                pass
            self._startup_integrity_watchdog_after = None
        self._startup_gate_active = False
        gate = getattr(self, '_startup_gate', None)
        if gate is not None:
            gate.close()
        self._startup_gate = None
        try:
            self.deiconify()
            self.lift()
            self.focus_force()
        except Exception:
            pass
        self._startup_mark('main_window_revealed')
        self._persist_startup_metrics()
        if self._startup_integrity_ok is False and self._startup_integrity_detail:
            detail = self._startup_integrity_detail
            try:
                self.after(150, lambda: cp_error(
                    self, 'CorePulse — instalación incompleta',
                    detail or 'La comprobación interna de integridad no fue satisfactoria.'
                ))
            except Exception:
                pass

    def _after_first_frame(self):
        """Punto de entrega visual: todo lo posterior es carga progresiva."""
        if not getattr(self, 'is_running', False):
            return
        self._startup_mark('first_frame_idle')
        self.update_startup_component(
            'layout', 1.0, 'Activando monitoreo real…',
            'CorePulse prepara sensores y servicios sin bloquear la interfaz.'
        )
        try:
            self.after(1, self._initialize_charts_deferred)
            self.after(12, self._start_background_services)
            self.after(2500, self._persist_startup_metrics)
        except Exception:
            pass

    def _initialize_charts_deferred(self):
        """Importa y monta Matplotlib sólo después del primer frame."""
        if not getattr(self, 'is_running', False) or getattr(self, '_charts_ready', False):
            return
        self._startup_mark('charts_import_begin')
        self.update_startup_component('charts', 0.18, 'Cargando gráficos…')
        try:
            import matplotlib
            matplotlib.use('TkAgg')
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            from matplotlib.figure import Figure
            self.fig = Figure(figsize=(9.4, 3.6), dpi=96, facecolor=BG_CARD)
            self.ax_cpu = self.fig.add_subplot(131, facecolor=BG_CARD)
            self.ax_ram = self.fig.add_subplot(132, facecolor=BG_CARD)
            self.ax_gpu = self.fig.add_subplot(133, facecolor=BG_CARD)
            cpu_x, cpu_series, cpu_count = self._chart_series_for_display(self.cpu_history)
            ram_x, ram_series, ram_count = self._chart_series_for_display(self.ram_history)
            gpu_x, gpu_series, gpu_count = self._chart_series_for_display(self.gpu_history)
            initial_visible_count = max(cpu_count, ram_count, gpu_count)
            self.line_cpu, = self.ax_cpu.plot(cpu_x, cpu_series, color=COLOR_CPU, linewidth=2.6, animated=True)
            self.line_ram, = self.ax_ram.plot(ram_x, ram_series, color=COLOR_RAM, linewidth=2.6, animated=True)
            self.line_gpu, = self.ax_gpu.plot(gpu_x, gpu_series, color=COLOR_GPU, linewidth=2.6, animated=True)
            self.format_axes(self.ax_cpu, 'CPU (%)')
            self.format_axes(self.ax_ram, 'RAM (%)')
            self.format_axes(self.ax_gpu, 'GPU (%)')
            self.fig.subplots_adjust(left=0.052, right=0.985, top=0.86, bottom=0.22, wspace=0.18)
            self._refresh_trend_axis_labels(initial_visible_count)
            self.canvas = FigureCanvasTkAgg(self.fig, master=self.frame_charts)
            canvas_widget = self.canvas.get_tk_widget()
            canvas_widget.configure(bg=BG_CARD, highlightthickness=0)
            canvas_widget.pack(fill='both', expand=True, padx=14, pady=(8, 10))
            self.canvas.mpl_connect('draw_event', self.on_draw)
            refresh_professional_charts(self)
            try:
                from gui.dashboard_layout import request_chart_reflow
                request_chart_reflow(self, redraw=False)
            except Exception:
                pass
            self.canvas.draw_idle()
            self._charts_ready = True
            self.chart_after_id = self.after(200, self.update_charts_fast)
            self._startup_mark('charts_ready')
            self.update_startup_component('charts', 1.0, 'Gráficos preparados')
        except Exception:
            self._charts_ready = False
            logger.exception('[STARTUP] Gráficos diferidos no disponibles; Dashboard continúa sin datos inventados')
            self._startup_mark('charts_unavailable')
            self.update_startup_component(
                'charts', 1.0, 'Gráficos no disponibles',
                'CorePulse continuará sin inventar datos; las métricas no disponibles quedarán en N/A.'
            )

    def _start_background_services(self):
        if not getattr(self, 'is_running', False) or self._services_ready or self._services_booting:
            return
        self._services_booting = True
        self._startup_mark('services_background_begin')
        self.update_startup_component('services', 0.08, 'Iniciando sensores y servicios…')
        threading.Thread(target=self._background_services_worker, daemon=True, name='CorePulse-StartupServices').start()

    def _background_services_worker(self):
        """Inicializa capacidades reales sin tocar Tk desde el worker."""
        global COREPULSE_ENV_STATUS
        payload = {}
        try:
            from core.env_config import load_corepulse_env
            COREPULSE_ENV_STATUS = load_corepulse_env()
        except Exception as exc:
            COREPULSE_ENV_STATUS = {'status': 'N/A', 'loaded': False, 'error': f'{type(exc).__name__}: {exc}'}
        try:
            from database.telemetry_repository import initialize_database
            initialize_database()
            payload['database_ready'] = True
        except Exception as exc:
            payload['database_error'] = f'{type(exc).__name__}: {exc}'
        try:
            self.after(0, lambda: self.update_startup_component('services', 0.24, 'Preparando datos locales…'))
        except Exception:
            pass
        try:
            from core.realtime_agent import RealTimeAgent
            payload['realtime_agent'] = RealTimeAgent()
            from performance.game_detector import GameDetector
            payload['game_detector'] = GameDetector(rtss_hint_provider=lambda: (payload['realtime_agent'].get_state().get('game') or {}))
            from performance.profile_manager import PerformanceProfileManager
            payload['performance_manager'] = PerformanceProfileManager(game_detector=payload['game_detector'])
        except Exception as exc:
            payload['agent_error'] = f'{type(exc).__name__}: {exc}'
        try:
            self.after(0, lambda: self.update_startup_component('services', 0.50, 'Activando monitoreo del sistema…'))
        except Exception:
            pass
        try:
            from core.alert_history_store import AlertHistoryStore
            agent = payload.get('realtime_agent') or self.realtime_agent
            payload['alert_history_store'] = AlertHistoryStore(agent)
        except Exception as exc:
            payload['history_error'] = f'{type(exc).__name__}: {exc}'
        try:
            self.after(0, lambda: self.update_startup_component('services', 0.68, 'Preparando historial y estado…'))
        except Exception:
            pass
        try:
            from core.diagnostic_explainer import DiagnosticExplainer
            payload['diagnostic_explainer'] = DiagnosticExplainer()
            from core.session_trends import SessionTrendCollector
            payload['session_trend_collector'] = SessionTrendCollector()
            from core.health_history import HealthHistoryStore
            payload['health_history_store'] = HealthHistoryStore()
            from core.thermal_throttling import ThermalThrottlingDetector
            payload['thermal_throttling_detector'] = ThermalThrottlingDetector()
            from core.adaptive_diagnostic import AdaptiveDiagnosticSession
            payload['diagnostic_session'] = AdaptiveDiagnosticSession(
                min_seconds=30, max_seconds=90, min_samples=25,
                context_stability_seconds=8, alert_stability_seconds=12,
            )
        except Exception as exc:
            payload['secondary_error'] = f'{type(exc).__name__}: {exc}'
        try:
            self.after(0, lambda: self.update_startup_component('services', 0.84, 'Terminando servicios secundarios…'))
        except Exception:
            pass
        try:
            self.after(0, lambda p=payload: self._commit_background_services(p))
        except Exception:
            self._services_booting = False

    def _commit_background_services(self, payload):
        if not getattr(self, 'is_running', False):
            return
        real_agent = payload.get('realtime_agent')
        if real_agent is not None:
            self.realtime_agent = real_agent
        self.game_detector = payload.get('game_detector')
        self.performance_manager = payload.get('performance_manager')
        self.alert_history_store = payload.get('alert_history_store')
        self.diagnostic_explainer = payload.get('diagnostic_explainer')
        self.session_trend_collector = payload.get('session_trend_collector')
        self.health_history_store = payload.get('health_history_store')
        self.thermal_throttling_detector = payload.get('thermal_throttling_detector')
        self.diagnostic_session = payload.get('diagnostic_session')
        try:
            from core.tray_service import CorePulseTray
            self.tray_service = CorePulseTray(self, self.realtime_agent)
            self.tray_service.start()
        except Exception:
            self.tray_service = _DeferredTray()
        try:
            if self.performance_manager is not None:
                self.performance_manager.set_notifier(self.tray_service.notify_game_boost)
        except Exception:
            logger.exception('[GAMEBOOST] No se pudo conectar el notificador de bandeja')
        # V119 — los subsistemas de Gaming ya restauran sus cambios temporales
        # desde backups propios. Registramos el resultado para que Recuperación
        # pueda explicar qué ocurrió después de un cierre brusco.
        try:
            recovery = getattr(self, 'session_recovery', None)
            manager = getattr(self, 'performance_manager', None)
            boost = manager.boost_status() if manager is not None else {}
            recovered = boost.get('recovery_status') if isinstance(boost, dict) else None
            if recovery is not None and isinstance(recovered, dict) and recovered:
                proc_restore = recovered.get('process_restore') if isinstance(recovered.get('process_restore'), dict) else {}
                restored_any = bool(recovered.get('restored')) or int(proc_restore.get('restored') or 0) > 0
                failed_any = recovered.get('success') is False or int(proc_restore.get('failed') or 0) > 0
                success = bool(restored_any and not failed_any)
                parts = []
                if recovered.get('message'):
                    parts.append(str(recovered.get('message')))
                if proc_restore.get('message'):
                    parts.append(str(proc_restore.get('message')))
                message = ' '.join(parts) or ('Game Boost restaurado tras la sesión anterior.' if success else 'Game Boost revisó un rollback pendiente de la sesión anterior.')
                recovery.record_recovery_action('Game Boost', success, message)
                self.session_recovery_status = recovery.status()
        except Exception:
            logger.exception('[RECOVERY] No se pudo registrar recuperación de Game Boost')
        # Sólo iniciamos adquisición cuando todas sus autoridades de estado ya
        # existen. Si alguna capacidad secundaria falta, la telemetría conserva N/A.
        if self.session_trend_collector is None:
            try:
                from core.session_trends import SessionTrendCollector
                self.session_trend_collector = SessionTrendCollector()
            except Exception:
                pass
        if self.health_history_store is None:
            try:
                from core.health_history import HealthHistoryStore
                self.health_history_store = HealthHistoryStore()
            except Exception:
                pass
        if self.thermal_throttling_detector is None:
            try:
                from core.thermal_throttling import ThermalThrottlingDetector
                self.thermal_throttling_detector = ThermalThrottlingDetector()
            except Exception:
                pass
        self._services_ready = True
        self._services_booting = False
        self.telemetry_thread = threading.Thread(target=self.telemetry_loop, daemon=True, name='CorePulse-Telemetry')
        self.telemetry_thread.start()
        self.telemetry_after_id = self.after(250, self.process_pending_telemetry)
        self.agent_after_id = self.after(350, self._update_agent_ui)
        self.after(180, self._schedule_battery_health_refresh)
        self.after(650, self._prewarm_health_center_module)
        self.after(1200, self._prewarm_navigation_modules)
        self.after(1800, self._schedule_storage_health_refresh)
        if getattr(self, '_recovery_heartbeat_after', None) is None:
            try:
                self._recovery_heartbeat_after = self.after(5000, self._session_recovery_heartbeat)
            except Exception:
                self._recovery_heartbeat_after = None
        degraded = bool(payload.get('agent_error') or payload.get('secondary_error'))
        self._startup_mark('services_ready', degraded=degraded)
        # No declaramos services=1.0 todavía: un hilo vivo no prueba que ya exista
        # telemetría visible. La última fracción se completa únicamente después de
        # aplicar la primera muestra real al Dashboard y cebar los gráficos.
        self.update_startup_component(
            'services', 0.90,
            'Leyendo la primera muestra real…' if not degraded else 'Leyendo telemetría con capacidades limitadas…',
            'CorePulse abrirá el panel cuando el monitoreo ya esté entregando datos reales.'
        )
        self._persist_startup_metrics()

    def _session_recovery_heartbeat(self):
        manager = getattr(self, 'session_recovery', None)
        if manager is not None and getattr(self, 'is_running', False):
            try:
                manager.heartbeat()
                self.session_recovery_status = manager.status()
            except Exception:
                self._log_throttled_exception('session_recovery_heartbeat', 'Fallo en heartbeat de recuperación', 60.0)
        if getattr(self, 'is_running', False):
            try:
                self._recovery_heartbeat_after = self.after(10000, self._session_recovery_heartbeat)
            except Exception:
                self._recovery_heartbeat_after = None

    def _persist_startup_metrics(self):
        try:
            from core.startup_profiler import persist_startup_metrics
            persist_startup_metrics()
        except Exception:
            pass

    def handle_runtime_integrity_result(self, ok=True, detail=''):
        """Cierra el gate de integridad sin falsear capacidades ni mostrar el Dashboard antes de tiempo."""
        self._runtime_integrity_ready = bool(ok)
        self._startup_integrity_ok = bool(ok)
        self._startup_integrity_detail = str(detail or '')
        self._startup_mark('runtime_integrity_ready' if ok else 'runtime_integrity_failed')
        self.update_startup_component(
            'integrity', 1.0,
            'Integridad verificada' if ok else 'Integridad verificada con limitaciones',
            None if ok else 'Las funciones sensibles permanecerán deshabilitadas hasta corregir la instalación.'
        )
        self._persist_startup_metrics()
        if not ok and getattr(self, 'is_running', False):
            # Conserva la GUI para informar el problema, pero no habilita rutas
            # sensibles sobre un bundle cuya integridad no pudo confirmarse.
            for button in (getattr(self, 'btn_diagnostic', None), getattr(self, 'btn_overlay', None), getattr(self, 'btn_tweaks', None)):
                try:
                    if button is not None:
                        button.configure(state='disabled')
                except Exception:
                    pass
            # El diálogo se difiere hasta que el gate libere la ventana principal.
            if not getattr(self, '_startup_gate_active', False):
                try:
                    cp_error(self, 'CorePulse — instalación incompleta', detail or 'La comprobación interna de integridad no fue satisfactoria.')
                except Exception:
                    pass

    def _prime_battery_presence_cache(self, device_identity=None):
        """Resuelve presencia de batería sin lanzar inventarios pesados."""
        try:
            from core.battery_health import probe_battery_presence
            telemetry = copy.deepcopy(getattr(self, 'latest_telemetry', {}) or {})
            identity = device_identity if isinstance(device_identity, dict) else getattr(self, '_device_identity_cache', None)
            result = probe_battery_presence(telemetry, identity if isinstance(identity, dict) else None)
            current = getattr(self, 'battery_presence_cache', None)
            if isinstance(result, dict) and (result.get('resolved') or not isinstance(current, dict)):
                self.battery_presence_cache = result
            return self.battery_presence_cache
        except Exception:
            return getattr(self, 'battery_presence_cache', None)

    def _prewarm_health_center_module(self):
        """Importa el módulo en background una vez iniciado CorePulse."""
        if getattr(self, '_health_center_prewarm_started', False):
            return
        self._health_center_prewarm_started = True
        def worker():
            try:
                import gui.health_center_panel  # noqa: F401
            except Exception:
                self._log_throttled_exception('health_center_prewarm', 'No se pudo precargar Centro de Salud')
        threading.Thread(target=worker, daemon=True, name='CorePulse-HealthCenterPrewarm').start()

    def _prewarm_navigation_modules(self):
        """Precarga sólo código Python de vistas frecuentes, nunca widgets Tk.

        La importación ocurre fuera del hilo UI para reducir la primera apertura
        sin construir páginas ocultas ni iniciar consultas de hardware. Tk sigue
        creando widgets únicamente cuando el usuario entra a la vista.
        """
        if getattr(self, '_navigation_modules_prewarm_started', False):
            return
        self._navigation_modules_prewarm_started = True

        def worker():
            modules = (
                'gui.windows_tweaks_panel',
                'gui.network_detail_panel',
                'gui.cleaning_center',
                'gui.alert_panel',
                'gui.alert_history_panel',
                'gui.session_trends_panel',
                'gui.gaming_panel',
                'gui.overlay_config_panel',
            )
            import importlib
            for name in modules:
                if not getattr(self, 'is_running', False):
                    return
                try:
                    importlib.import_module(name)
                except Exception:
                    self._log_throttled_exception('navigation_prewarm', f'No se pudo precargar {name}')

        threading.Thread(target=worker, daemon=True, name='CorePulse-NavigationPrewarm').start()

    def _arm_battery_health_refresh(self):
        if not getattr(self, 'is_running', False) or getattr(self, '_battery_health_refresh_after_id', None) is not None:
            return
        try:
            def tick():
                self._battery_health_refresh_after_id = None
                self._schedule_battery_health_refresh()
            self._battery_health_refresh_after_id = self.after(300000, tick)
        except Exception:
            self._battery_health_refresh_after_id = None

    def _schedule_battery_health_refresh(self, force=False):
        """Mantiene un único cache de batería compartido por toda la aplicación."""
        if not getattr(self, 'is_running', False):
            return
        presence = self._prime_battery_presence_cache()
        if isinstance(presence, dict) and presence.get('resolved') and presence.get('present') is False:
            if not isinstance(getattr(self, 'battery_health_cache', None), dict):
                self.battery_health_cache = {
                    'present': False, 'health_percent': None, 'sources': [presence.get('source')] if presence.get('source') else [],
                    'presence_source': presence.get('source'), 'policy': 'REAL_OR_NA',
                }
                self.battery_health_cache_timestamp = time.time()
            self._arm_battery_health_refresh()
            return

        age = time.time() - float(getattr(self, 'battery_health_cache_timestamp', 0.0) or 0.0)
        if not force and isinstance(getattr(self, 'battery_health_cache', None), dict) and age < 300.0:
            self._arm_battery_health_refresh()
            return
        if getattr(self, '_battery_health_refresh_running', False):
            self._arm_battery_health_refresh()
            return

        self._battery_health_refresh_running = True
        telemetry = copy.deepcopy(getattr(self, 'latest_telemetry', {}) or {})

        def worker():
            try:
                from core.battery_health import collect_battery_health
                result = collect_battery_health(telemetry)
                error = None
            except Exception:
                self._log_throttled_exception('battery_health_refresh', 'Fallo al actualizar Battery Health')
                result = None
                error = True

            def done():
                self._battery_health_refresh_running = False
                if isinstance(result, dict):
                    self.battery_health_cache = result
                    self.battery_health_cache_timestamp = time.time()
                    self.battery_presence_cache = {
                        'present': bool(result.get('present')), 'resolved': True,
                        'source': result.get('presence_source') or 'battery_health_cache', 'captured_at': time.time(),
                    }
                    panel = getattr(self, 'health_center_panel', None)
                    if panel is not None and hasattr(panel, 'apply_battery_health_cache'):
                        try:
                            panel.apply_battery_health_cache(result)
                        except Exception:
                            pass
                self._arm_battery_health_refresh()
            try:
                self.after(0, done)
            except Exception:
                self._battery_health_refresh_running = False

        threading.Thread(target=worker, daemon=True, name='CorePulse-BatteryHealth').start()
        self._arm_battery_health_refresh()

    def _schedule_storage_health_refresh(self):
        """Consulta SMART/Storage Reliability fuera del hilo UI.

        Es una capacidad secundaria: nunca bloquea el startup ni el ciclo de
        telemetría. El Dashboard consume el último cache real disponible.
        """
        if not getattr(self, 'is_running', False):
            return
        if not getattr(self, '_storage_health_refresh_running', False):
            self._storage_health_refresh_running = True
            telemetry = copy.deepcopy(getattr(self, 'latest_telemetry', {}) or {})

            def worker():
                try:
                    from core.storage_summary_health import collect_storage_summary_health
                    result = collect_storage_summary_health(telemetry)
                    if isinstance(result, dict):
                        self.storage_health_cache = result
                except Exception:
                    self._log_throttled_exception('storage_health_refresh', 'Fallo al actualizar salud de almacenamiento')
                finally:
                    self._storage_health_refresh_running = False

            threading.Thread(target=worker, daemon=True, name='CorePulse-StorageHealth').start()
        try:
            self.after(300000, self._schedule_storage_health_refresh)
        except Exception:
            pass

    def _defer_ui_call(self, callback, delay=1):
        """Ejecuta refrescos secundarios después de publicar la página.

        La navegación nunca espera a consultas o rerenders que no son necesarios
        para mostrar el primer frame de la vista.
        """
        if not callable(callback):
            return
        try:
            self.after(max(1, int(delay)), callback)
        except Exception:
            try:
                callback()
            except Exception:
                pass

    def run_cleanup(self):
        if not self.is_running:
            return
        from gui.cleaning_center import show_cleaning_center
        show_cleaning_center(self)

    def open_windows_tweaks(self):
        """Abre Tweaks de Windows 11 como vista interna de CorePulse."""
        if not self.is_running:
            return
        host = None
        try:
            host, reused = activate_internal_page(self, 'tweaks')
            if reused and self.windows_tweaks_panel is not None:
                self._defer_ui_call(self.windows_tweaks_panel.refresh)
                return
            if host is None:
                return
            from gui.windows_tweaks_panel import WindowsTweaksPanel
            panel = WindowsTweaksPanel(self, host)
            self.windows_tweaks_panel = panel
            if not commit_internal_page(self, 'tweaks', host, panel):
                self.windows_tweaks_panel = None
        except Exception as exc:
            self.windows_tweaks_panel = None
            abort_internal_page(self, 'tweaks', host)
            cp_error(self, 'Tweaks de Windows 11', f'No se pudo abrir la vista de Tweaks:\n\n{exc}')

    def open_benchmark(self):
        """Abre el benchmark visual como módulo principal independiente."""
        if not self.is_running:
            return
        if not self._services_ready:
            cp_info(self, 'Benchmark', 'CorePulse está terminando de iniciar los servicios de monitoreo. Intenta nuevamente en un momento.')
            return
        host = None
        try:
            host, reused = activate_internal_page(self, 'benchmark')
            if reused and self.benchmark_panel is not None:
                self._defer_ui_call(self.benchmark_panel.refresh)
                return
            if host is None:
                return
            from gui.benchmark_panel import BenchmarkPanel
            panel = BenchmarkPanel(self, host)
            self.benchmark_panel = panel
            if not commit_internal_page(self, 'benchmark', host, panel):
                self.benchmark_panel = None
        except Exception as exc:
            self.benchmark_panel = None
            abort_internal_page(self, 'benchmark', host)
            cp_error(self, 'Benchmark', f'No se pudo abrir el Benchmark:\n\n{exc}')

    def open_health_center(self):
        """Abre el Centro de Salud avanzado como página interna."""
        if not self.is_running:
            return
        # La presencia de batería ya debe estar resuelta antes de construir la
        # grilla para evitar que el Centro de Salud cambie de forma tras abrirse.
        self._prime_battery_presence_cache(getattr(self, '_device_identity_cache', None))
        host = None
        try:
            host, reused = activate_internal_page(self, 'health_center')
            if reused and self.health_center_panel is not None:
                self._defer_ui_call(self.health_center_panel.refresh)
                return
            if host is None:
                return
            from gui.health_center_panel import HealthCenterPanel
            panel = HealthCenterPanel(self, host)
            self.health_center_panel = panel
            if not commit_internal_page(self, 'health_center', host, panel):
                self.health_center_panel = None
        except Exception as exc:
            self.health_center_panel = None
            abort_internal_page(self, 'health_center', host)
            cp_error(self, 'Centro de Salud', f'No se pudo abrir el Centro de Salud:\n\n{exc}')

    def open_gaming(self, tab='performance'):
        """Abre Gaming consolidado o su vista separada de Overlay."""
        if not self.is_running:
            return
        if not self._services_ready:
            cp_info(self, 'Gaming', 'CorePulse está terminando de iniciar los servicios de Gaming. Intenta nuevamente en un momento.')
            return
        requested_tab = str(tab or 'performance').lower().strip()
        if requested_tab not in {'performance', 'overlay'}:
            requested_tab = 'performance'
        host = None
        try:
            host, reused = activate_internal_page(self, 'gaming')
            if reused and self.gaming_panel is not None:
                self.gaming_panel.select_tab(requested_tab)
                return
            if host is None:
                return
            from gui.gaming_panel import GamingPanel
            panel = GamingPanel(self, host, initial_tab=requested_tab)
            self.gaming_panel = panel
            if not commit_internal_page(self, 'gaming', host, panel):
                self.gaming_panel = None
        except Exception as exc:
            self.gaming_panel = None
            abort_internal_page(self, 'gaming', host)
            cp_error(self, 'Gaming', f'No se pudo abrir la vista Gaming:\n\n{exc}')

    def open_network_details(self):
        """Abre Red avanzada como vista interna de CorePulse."""
        if not self.is_running:
            return
        host = None
        try:
            host, reused = activate_internal_page(self, 'network')
            if reused and self.network_detail_panel is not None:
                self._defer_ui_call(self.network_detail_panel.refresh)
                return
            if host is None:
                return
            from gui.network_detail_panel import NetworkDetailPanel
            panel = NetworkDetailPanel(self, host)
            self.network_detail_panel = panel
            if not commit_internal_page(self, 'network', host, panel):
                self.network_detail_panel = None
        except Exception as exc:
            self.network_detail_panel = None
            abort_internal_page(self, 'network', host)
            cp_error(self, 'Red avanzada', f'No se pudo abrir la vista de red:\n\n{exc}')

    # Inicia una sesión de diagnóstico sin mezclarla con el estado histórico.
    def start_diagnostic_session(self, force_new=False):
        if not self.is_running:
            return
        if self.diagnostic_session is None or not self._services_ready:
            cp_info(self, 'Diagnóstico', 'CorePulse está terminando de iniciar el monitoreo. Intenta nuevamente en un momento.')
            return
        from gui.diagnostic_view import show_diagnostic_experience
        if self.diagnostic_session.active:
            try:
                panel = show_diagnostic_experience(self)
                state = self.realtime_agent.get_state()
                panel.update_progress(self.diagnostic_session.readiness(state), state)
                panel.lift()
            except Exception:
                pass
            return
        if not force_new and self.diagnostic_result and self.diagnostic_session.completed:
            try:
                panel = show_diagnostic_experience(self)
                panel.show_complete(self.diagnostic_result)
                panel.lift()
            except Exception:
                pass
            return
        if not self.latest_telemetry:
            cp_warning(self, 'Diagnóstico', 'Aún no hay telemetría disponible. Espera unos segundos y vuelve a iniciar el diagnóstico.')
            return
        self.diagnostic_result = None
        self.current_recommendation_pipeline = None
        self.diagnostic_json_path = None
        self.diagnostic_telemetry_snapshot = None
        self.diagnostic_disks_snapshot = None
        self.diagnostic_score_snapshot = None
        self.diagnostic_session.start()
        diagnostic_panel = show_diagnostic_experience(self)
        try:
            diagnostic_panel.lift()
        except Exception:
            pass
        try:
            self.btn_diagnostic.configure(width=220)
        except Exception:
            pass
        self.btn_pdf.configure(state='disabled', text='PDF · preparando')
        self.btn_diagnostic.configure(state='normal', text='Diagnóstico 0%', fg_color='transparent', hover_color=theme_color('#14253b'), text_color=theme_color('#b8c4d4'))
        refresh_navigation_state(self)
        self._update_diagnostic_countdown()

    def _update_diagnostic_countdown(self):
        if not self.is_running:
            return
        if self.diagnostic_session.active:
            try:
                state = self.realtime_agent.get_state()
            except Exception:
                state = {}
            info = self.diagnostic_session.readiness(state)
            progress = int(round(float(info.get('progress', 0.0)) * 100.0))
            progress = max(0, min(100, progress))
            eta = max(0, int(info.get('eta_seconds', 0) or 0))
            from core.adaptive_diagnostic import readiness_stage
            stage = readiness_stage(info)
            panel = getattr(self, 'diagnostic_experience_panel', None)
            try:
                if panel is not None and panel.winfo_exists():
                    panel.update_progress(info, state)
            except Exception:
                pass
            self.btn_diagnostic.configure(width=220, text=f'Diagnóstico {progress:3d}%', fg_color='transparent', hover_color=theme_color('#14253b'), text_color=theme_color('#b8c4d4'))
            self.btn_pdf.configure(state='disabled')
            if self.diagnostic_session.should_finish(state):
                self._finish_diagnostic_session()
                return
            self.diagnostic_after_id = self.after(500, self._update_diagnostic_countdown)
            return
        self.diagnostic_after_id = None

    def _finish_diagnostic_session(self):
        if not self.is_running:
            return
        try:
            state = self.realtime_agent.get_state()
        except Exception:
            state = {}
        result = self.diagnostic_session.finish(state)
        self.diagnostic_result = result
        self.diagnostic_telemetry_snapshot = copy.deepcopy(self.latest_telemetry if isinstance(self.latest_telemetry, dict) else {})
        self.diagnostic_disks_snapshot = copy.deepcopy(self.latest_disks if isinstance(self.latest_disks, list) else [])
        self.diagnostic_score_snapshot = self.latest_score
        try:
            from core.diagnostic_pipeline import integrate_current_diagnostic_pipeline
            self.current_recommendation_pipeline = integrate_current_diagnostic_pipeline(result, copy.deepcopy(self.diagnostic_telemetry_snapshot or {}), copy.deepcopy(self.diagnostic_disks_snapshot or []), output_path=str(data_path('current_diagnostic_recommendations.json')))
            result['_intelligent_recommendations'] = self.current_recommendation_pipeline
        except Exception as recommendation_error:
            self.current_recommendation_pipeline = {'version': VERSION_LABEL, 'status': 'ERROR', 'scope': 'CURRENT_DIAGNOSTIC_ONLY', 'error': str(recommendation_error), 'recommendation_count': 0, 'history_used_as_current_fault_source': False}
            result['_intelligent_recommendations'] = self.current_recommendation_pipeline
        self.diagnostic_json_path = self.diagnostic_session.save_json()
        try:
            self.session_trend_collector.record_diagnostic(result, state=state)
            self._refresh_session_trends_ui()
        except Exception:
            pass
        status = result.get('overall_status', 'NO_EVALUABLE')
        adaptive = result.get('adaptive_diagnostic') or {}
        confidence = adaptive.get('confidence_percent')
        reason = adaptive.get('finish_reason', 'EVIDENCE_READY')
        self.btn_diagnostic.configure(width=220, state='normal', text='Ver diagnóstico', fg_color='transparent', hover_color=theme_color('#14253b'), text_color=theme_color('#f4f7fb'))
        self.btn_pdf.configure(state='normal', text='Generar PDF · listo')
        duration = int(result.get('duration_seconds', 0) or 0)
        samples = int(result.get('sample_count', 0) or 0)
        confidence_text = f'{float(confidence):.0f}%' if isinstance(confidence, (int, float)) else 'N/A'
        reason_text = 'evidencia suficiente' if reason == 'EVIDENCE_READY' else 'límite de seguridad alcanzado'
        refresh_navigation_state(self)
        panel = getattr(self, 'diagnostic_experience_panel', None)
        panel_visible = False
        try:
            panel_visible = bool(panel is not None and panel.winfo_exists() and panel.winfo_viewable())
            if panel_visible:
                panel.show_complete(result)
                panel.lift()
        except Exception:
            panel_visible = False
        if not panel_visible:
            cp_info(self, 'Diagnóstico completado', f'CorePulse reunió evidencia suficiente para cerrar el diagnóstico.\n\nResultado del diagnóstico: {status}\nDuración real: {duration} s\nMuestras reales: {samples}\nConfianza de evidencia: {confidence_text}\nFinalización: {reason_text}\n\nEl informe PDF ya está habilitado.\nEvidencia guardada en:\n{self.diagnostic_json_path}')

    # Exporta exactamente la evidencia congelada del diagnóstico completado.
    def export_pdf_report(self):
        """Genera el PDF sin bloquear Tkinter y sin tocar widgets desde el hilo de trabajo."""
        if self._pdf_export_in_progress:
            cp_info(self, 'Reportes', 'CorePulse ya está generando un informe PDF. Espera a que termine la operación actual.')
            return
        if not self.diagnostic_session.completed or not self.diagnostic_result:
            if self.diagnostic_session.active:
                try:
                    state = self.realtime_agent.get_state()
                except Exception:
                    state = {}
                info = self.diagnostic_session.readiness(state)
                eta = max(0, int(info.get('eta_seconds', 0) or 0))
                from core.adaptive_diagnostic import readiness_stage
                stage = readiness_stage(info)
                detail = f'CorePulse todavía está {stage.lower()}.\nTiempo estimado restante: ~{eta} s.\n\nEl PDF se habilitará automáticamente cuando exista evidencia suficiente.'
            else:
                detail = 'Inicia el diagnóstico rápido de CorePulse.\n\nEn un sistema estable, el informe puede habilitarse desde ~30 segundos. Si CorePulse necesita confirmar una condición, observará más tiempo hasta un máximo de seguridad de 90 segundos.'
            cp_warning(self, 'Informe aún no disponible', detail)
            return
        if not self.is_running or not self.latest_telemetry:
            cp_warning(self, 'Reportes', 'Aún no hay datos de telemetría para exportar.')
            return

        # V115: los informes vuelven a una ruta estable dentro de AppData.
        # No se abre un selector de carpetas ni se genera nada por el simple hecho
        # de entrar al diagnóstico: el usuario decide cuándo crear el PDF.
        try:
            output_dir = Path(diagnostics_dir()).resolve()
            output_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            cp_error(self, 'Reportes', f'No se pudo preparar la carpeta de informes de CorePulse:\n{exc}')
            return
        default_filename = f"Reporte_CorePulse_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        file_path = str(output_dir / default_filename)

        diagnostic_result_snapshot = copy.deepcopy(self.diagnostic_result)
        telemetry_snapshot = copy.deepcopy(self.diagnostic_telemetry_snapshot if isinstance(self.diagnostic_telemetry_snapshot, dict) else self.latest_telemetry)
        telemetry_snapshot['_diagnostic_session'] = diagnostic_result_snapshot
        telemetry_snapshot['_diagnostic_json_path'] = self.diagnostic_json_path
        disks_snapshot = copy.deepcopy(self.diagnostic_disks_snapshot if isinstance(self.diagnostic_disks_snapshot, list) else self.latest_disks)
        score_snapshot = self.diagnostic_score_snapshot if self.diagnostic_telemetry_snapshot is not None else self.latest_score

        self._pdf_export_in_progress = True
        self._set_pdf_export_busy()
        job = {
            'done': threading.Event(),
            'path': file_path,
            'error': None,
        }
        self._pdf_export_job = job

        def generate_worker():
            # IMPORTANTE: este hilo no toca Tk/CustomTkinter.
            try:
                from core.report_generator import generate_pdf_report
                generate_pdf_report(
                    telemetry_snapshot,
                    disks_snapshot,
                    score_snapshot,
                    output_path=file_path,
                    diagnostic_result=diagnostic_result_snapshot,
                )
            except Exception as exc:
                job['error'] = str(exc)
            finally:
                job['done'].set()

        threading.Thread(target=generate_worker, daemon=True, name='CorePulse-PDF-Worker').start()
        self.after(100, self._poll_pdf_export_job)

    def _set_pdf_export_busy(self):
        try:
            self.btn_pdf.configure(state='disabled', text='Generando PDF...')
        except Exception:
            pass
        panel = getattr(self, 'diagnostic_experience_panel', None)
        try:
            if panel is not None and panel.winfo_exists():
                panel.set_pdf_busy()
        except Exception:
            pass
        refresh_navigation_state(self)

    def _poll_pdf_export_job(self):
        """Consulta el worker desde el hilo principal de Tkinter."""
        job = self._pdf_export_job
        if not isinstance(job, dict):
            return
        done = job.get('done')
        if done is None or not done.is_set():
            if self.is_running:
                self.after(100, self._poll_pdf_export_job)
            return

        self._pdf_export_job = None
        self._pdf_export_in_progress = False
        error = job.get('error')
        file_path = str(job.get('path') or '')
        self._restore_pdf_button()

        if error:
            self._show_pdf_error(error)
            return
        if not file_path or not Path(file_path).is_file():
            self._show_pdf_error('La generación terminó sin producir un archivo PDF válido.')
            return

        self._remember_last_pdf_report(file_path)
        self._show_pdf_success(file_path)

    def _show_pdf_success(self, file_path, opened=None):
        if self.is_running:
            cp_info(
                self,
                'Reporte creado',
                f'El informe PDF fue generado correctamente en la carpeta de CorePulse:\n\n{file_path}'
                '\n\nPuedes abrir el último PDF o mostrar la carpeta desde la pantalla de Diagnóstico.'
            )

    def _show_pdf_error(self, error):
        if self.is_running:
            cp_error(self, 'Reportes', f'No se pudo generar el reporte PDF:\n{error}')

    def _restore_pdf_button(self):
        if self.is_running:
            try:
                self.btn_pdf.configure(state='normal', text='Generar PDF · listo')
            except Exception:
                pass
            panel = getattr(self, 'diagnostic_experience_panel', None)
            try:
                if panel is not None and panel.winfo_exists():
                    panel.set_pdf_ready()
            except Exception:
                pass
            refresh_navigation_state(self)

    def clean_ram_from_tray(self):
        """Ejecuta la liberación profunda de RAM desde la bandeja, sin navegar de página."""
        if not getattr(self, 'is_running', False):
            return
        if getattr(self, '_tray_ram_cleanup_running', False):
            try:
                notifier = getattr(getattr(self, 'tray_service', None), 'notify_action', None)
                if callable(notifier):
                    notifier('CorePulse · RAM profunda', 'La liberación profunda de RAM ya está en ejecución.')
            except Exception:
                pass
            return

        self._tray_ram_cleanup_running = True

        def worker():
            try:
                from core.ram_optimizer import optimize_ram_deep
                result = optimize_ram_deep(
                    settle_seconds=1.15,
                    snapshot_samples=5,
                    purge_standby=True,
                )
                if not result.get('success'):
                    title = 'CorePulse · RAM profunda'
                    message = str(result.get('message') or 'No se pudo ejecutar la liberación profunda de RAM.')
                else:
                    recovered = float(result.get('measured_recovered_mb') or 0.0)
                    before = result.get('before') or {}
                    after = result.get('after') or {}
                    before_pct = float(before.get('used_percent') or 0.0)
                    after_pct = float(after.get('used_percent') or 0.0)
                    regions_done = int(result.get('regions_completed') or 0)
                    regions_total = int(result.get('regions_attempted') or 0)
                    trimmed = int(result.get('working_sets_trimmed') or 0)
                    if recovered > 0.05:
                        message = (
                            f'{recovered:.1f} MB recuperados · RAM {before_pct:.1f}% → {after_pct:.1f}% · '
                            f'regiones {regions_done}/{regions_total} · procesos recortados {trimmed}.'
                        )
                    else:
                        message = (
                            f'Liberación profunda completada · RAM {before_pct:.1f}% → {after_pct:.1f}% · '
                            f'regiones {regions_done}/{regions_total} · sin recuperación adicional medible.'
                        )
                    title = 'CorePulse · RAM profunda completada'
            except Exception as exc:
                logger.exception('[RAM] Falló la limpieza profunda desde la bandeja')
                title = 'CorePulse · RAM profunda'
                message = f'No se pudo completar la limpieza profunda: {type(exc).__name__}: {exc}'
            finally:
                self._tray_ram_cleanup_running = False

            def notify():
                try:
                    notifier = getattr(getattr(self, 'tray_service', None), 'notify_action', None)
                    if callable(notifier):
                        notifier(title, message)
                except Exception:
                    pass

            try:
                self.after(0, notify)
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True, name='CorePulse-TrayRAMDeepCleanup').start()

    def _close_overlay_config_window(self):
        """Compatibilidad: ya no existe una ventana/página Overlay independiente."""
        self.overlay_config_window = None
        self.overlay_config_panel = None

    def _on_overlay_hotkey(self):
        if not self.is_running:
            return
        try:
            self.after(0, self.toggle_overlay)
        except Exception:
            pass

    def _configure_overlay_hotkey(self):
        prefs = load_overlay_preferences(force=True)
        config = prefs.get('toggle_hotkey') or {}
        manager = getattr(self, 'overlay_hotkey_manager', None)
        if manager is None:
            return
        # Atajos heredados de la captura antigua no se registran para evitar
        # conservar un Alt/Mod1 residual. El usuario los certifica grabándolos una vez.
        try:
            capture_version = int(config.get('capture_version', 1) or 1)
        except Exception:
            capture_version = 1
        if capture_version < CAPTURE_VERSION:
            manager.stop()
            return
        manager.update(config)

    def open_overlay_config_window(self):
        """Compatibilidad pública: abre directamente Gaming > Overlay."""
        self.open_gaming('overlay')

    def toggle_overlay(self):
        if not self.is_running:
            return
        try:
            if self.overlay_window is None or not self.overlay_window.winfo_exists():
                from gui.overlay import GameOverlay
                self.overlay_window = GameOverlay(master=self)
                return
            self.close_overlay()
        except Exception as exc:
            self.overlay_window = None
            cp_error(self, 'Overlay', f'No se pudo iniciar el overlay.\n\nError: {exc}')

    def close_overlay(self):
        try:
            if self.overlay_window and self.overlay_window.winfo_exists():
                self.overlay_window.destroy()
        except Exception:
            pass
        finally:
            self.overlay_window = None

    def _build_custom_titlebar(self):
        """Compatibilidad: V113 vuelve al borde nativo de Windows."""
        return

    def _apply_custom_window_chrome(self):
        """Con borde nativo, no se fuerza overrideredirect."""
        self._custom_chrome_enabled = False
        self._refresh_window_maximize_button()

    def _suspend_custom_window_chrome(self):
        self._custom_chrome_enabled = False

    def _handle_custom_chrome_map(self, event=None):
        return

    def _begin_titlebar_drag(self, event=None):
        self._titlebar_drag_origin = None

    def _perform_titlebar_drag(self, event=None):
        return

    def _end_titlebar_drag(self, event=None):
        self._titlebar_drag_origin = None

    def _is_window_zoomed(self):
        try:
            return str(self.state()) == 'zoomed' or bool(getattr(self, '_custom_maximized', False))
        except Exception:
            return bool(getattr(self, '_custom_maximized', False))

    def _refresh_window_maximize_button(self):
        return

    def _minimize_window_to_taskbar(self):
        try:
            self.iconify()
        except Exception:
            pass

    def _toggle_window_maximize(self, event=None):
        if getattr(self, 'is_fullscreen', False):
            return 'break'
        try:
            if str(self.state()) == 'zoomed':
                self.state('normal')
            else:
                self.state('zoomed')
        except Exception:
            pass
        return 'break'

    def _maximize_window(self):
        try:
            self.state('zoomed')
        except Exception:
            pass

    def _restore_from_maximize(self):
        try:
            self.state('normal')
        except Exception:
            pass

    def create_metric_card(self, parent, title):
        card = ctk.CTkFrame(parent, fg_color=BG_CARD, border_width=1, border_color=BORDER_COLOR, corner_radius=10)
        ctk.CTkLabel(card, text=title, font=('Segoe UI', 9, 'bold'), text_color=COLOR_TEXT_DIM).pack(anchor='w', padx=10, pady=(6, 1))
        return card

    def build_card_content(self, card, color):
        lbl_val = ctk.CTkLabel(card, text='N/A', font=('Segoe UI', 16, 'bold'), text_color=theme_color('#f8fafc'), height=29)
        lbl_val.pack(anchor='w', padx=10, pady=(0, 0))
        bar = ctk.CTkProgressBar(card, height=5, progress_color=color, fg_color=theme_color('#0f172a'))
        bar.set(0)
        lbl_sub = ctk.CTkLabel(card, text='--', font=('Segoe UI', 9, 'bold'), text_color=color, height=18, anchor='w')
        lbl_sub.pack(fill='x', padx=10, pady=(0, 5))
        children = card.winfo_children()
        return (lbl_val, bar, lbl_sub, children[0] if children else None)

    def format_axes(self, ax, title):
        ax.set_title(title, color=theme_color('#e2e8f0'), fontsize=9, fontweight='bold', pad=10)
        ax.set_ylim(0, 100)
        ax.set_xlim(0, self.max_points - 1)
        ax.set_facecolor(theme_color('#0f1827'))
        ax.tick_params(axis='x', colors=COLOR_TEXT_DIM, labelsize=8, length=0, pad=6)
        ax.tick_params(axis='y', colors=COLOR_TEXT_DIM, labelsize=8, length=0, pad=6)
        ax.set_yticks([25, 50, 75, 100])
        for side, spine in ax.spines.items():
            spine.set_visible(True)
            spine.set_linewidth(1.0 if side in ('left', 'bottom') else 0.9)
            spine.set_color(theme_color('#23324d') if side in ('top', 'right') else theme_color('#2f4669'))
        ax.grid(False)
        ax.yaxis.grid(True, color='#1e293b', linestyle='-', linewidth=0.55, alpha=0.65)
        try:
            ax.set_axisbelow(True)
            ax.margins(x=0.02, y=0.10)
        except Exception:
            pass


    def _chart_series_for_display(self, values):
        """Ajusta la serie visible para evitar media gráfica vacía al inicio.

        No inventa muestras: recorta sólo el tramo previo sin datos reales y
        redistribuye las muestras existentes sobre el ancho disponible.
        """
        try:
            raw = list(values or [])
        except Exception:
            raw = []
        if not raw:
            return list(range(self.max_points)), [float('nan')] * int(self.max_points), 0
        first_real = None
        for index, value in enumerate(raw):
            try:
                number = float(value)
            except Exception:
                continue
            if math.isfinite(number):
                first_real = index
                break
        if first_real is None:
            return list(range(self.max_points)), [float('nan')] * int(self.max_points), 0
        visible = raw[first_real:]
        count = len(visible)
        last = max(0, int(self.max_points) - 1)
        if count <= 1:
            x_data = [last]
        else:
            step = last / float(count - 1)
            x_data = [i * step for i in range(count)]
        return x_data, visible, count

    def _trend_tick_labels_for_count(self, visible_count):
        total = max(2, int(self.max_points or 2))
        count = max(0, int(visible_count or 0))
        full_span_seconds = 60
        if count <= 1:
            span_seconds = 5
        elif count >= total:
            span_seconds = full_span_seconds
        else:
            span_seconds = max(5, int(round(((count - 1) / max(1, total - 1)) * full_span_seconds)))
        checkpoints = [span_seconds, int(round(span_seconds * 0.75)), int(round(span_seconds * 0.5)), int(round(span_seconds * 0.25))]
        labels = []
        for seconds in checkpoints:
            seconds = max(1, int(seconds))
            labels.append(f'-{seconds}s')
        labels.append('Ahora')
        return labels

    def _refresh_trend_axis_labels(self, visible_count):
        labels = self._trend_tick_labels_for_count(visible_count)
        try:
            last = max(1, int(self.max_points) - 1)
            ticks = [1, round(last * 0.28), round(last * 0.56), round(last * 0.80), last]
            deduped = []
            for value in ticks:
                value = max(1, min(last, int(value)))
                if value not in deduped:
                    deduped.append(value)
            while len(deduped) < 5:
                deduped.append(last)
            for ax in (self.ax_cpu, self.ax_ram, self.ax_gpu):
                if ax is None:
                    continue
                ax.set_xticks(deduped[:5])
                ax.set_xticklabels(labels)
        except Exception:
            pass

    def _refresh_trend_chart_frames(self):
        """Compatibilidad: ya no dibujamos parches extra; el marco es el propio eje."""
        return

    def on_draw(self, event):
        if not self.is_running or event.canvas != self.canvas:
            return
        try:
            self.background = self.canvas.copy_from_bbox(self.fig.bbox)
            self.ax_cpu.draw_artist(self.line_cpu)
            self.ax_ram.draw_artist(self.line_ram)
            self.ax_gpu.draw_artist(self.line_gpu)
            self.canvas.blit(self.fig.bbox)
        except Exception:
            self.background = None

    def update_charts_fast(self):
        if not self.is_running:
            return
        if not self._charts_ready or self.canvas is None:
            return
        try:
            if self.background is None and (not self.is_resizing):
                self.canvas.draw_idle()
            if self.background is not None and (not self.is_resizing):
                with self.telemetry_lock:
                    cpu_data = list(self.cpu_history)
                    ram_data = list(self.ram_history)
                    gpu_data = list(self.gpu_history)
                cpu_x, cpu_series, cpu_count = self._chart_series_for_display(cpu_data)
                ram_x, ram_series, ram_count = self._chart_series_for_display(ram_data)
                gpu_x, gpu_series, gpu_count = self._chart_series_for_display(gpu_data)
                visible_count = max(cpu_count, ram_count, gpu_count)
                self.line_cpu.set_data(cpu_x, cpu_series)
                self.line_ram.set_data(ram_x, ram_series)
                self.line_gpu.set_data(gpu_x, gpu_series)
                self._refresh_trend_axis_labels(visible_count)
                self.canvas.restore_region(self.background)
                self.ax_cpu.draw_artist(self.line_cpu)
                self.ax_ram.draw_artist(self.line_ram)
                self.ax_gpu.draw_artist(self.line_gpu)
                self.canvas.blit(self.fig.bbox)
        except Exception:
            self.background = None
        if self.is_running:
            self.chart_after_id = self.after(200, self.update_charts_fast)

    def open_storage_details(self, disk_index):
        """Abre la ficha interna de una unidad física detectada."""
        if not self.is_running:
            return
        try:
            from gui.storage_detail_panel import show_storage_details
            show_storage_details(self, int(disk_index))
        except Exception as exc:
            cp_error(self, 'Almacenamiento', f'No se pudieron abrir los detalles de la unidad:\n{exc}')

    def _open_deferred_hardware_detail(self, page_key, *, title, subtitle, panel_attr, factory):
        """Publica el primer frame antes de construir una ficha de hardware pesada.

        Tk/CustomTkinter debe crear widgets en el hilo UI, pero eso no obliga a que
        el clic espere a que exista todo el árbol. Primero se publica un shell
        mínimo y, en el frame siguiente, se construye la ficha real dentro del
        mismo host. La página queda cacheada para reaperturas instantáneas.
        """
        host, reused = activate_internal_page(self, page_key)
        if reused:
            panel = getattr(self, panel_attr, None)
            # Las páginas cacheadas con ciclo de vida propio se reactivan dentro
            # de activate_internal_page(); evita refrescos duplicados en el clic.
            if panel is not None and not hasattr(panel, 'set_active'):
                refresh = getattr(panel, 'refresh', None)
                if callable(refresh):
                    self._defer_ui_call(refresh, 1)
            return panel
        if host is None:
            return None

        shell = None
        try:
            shell = ctk.CTkFrame(host, fg_color=theme_color('#06111f'), corner_radius=0)
            shell.place(relx=0, rely=0, relwidth=1, relheight=1)
            box = ctk.CTkFrame(
                shell,
                fg_color=theme_color('#0d1828'),
                border_width=1,
                border_color=theme_color('#1b3048'),
                corner_radius=12,
            )
            box.place(relx=0.5, rely=0.46, anchor='center')
            ctk.CTkLabel(
                box, text=title, font=('Segoe UI', 15, 'bold'),
                text_color=theme_color('#f4f7fb'),
            ).pack(padx=34, pady=(22, 5))
            ctk.CTkLabel(
                box, text=subtitle, font=('Segoe UI', 9),
                text_color=theme_color('#7f91a8'),
            ).pack(padx=34, pady=(0, 22))

            # 83w: el shell se publica AHORA. No se llama update_idletasks() ni
            # se construye la ficha completa antes del primer cambio visible.
            if not commit_internal_page(self, page_key, host, panel=None):
                return None
        except Exception:
            logger.exception('No se pudo publicar la vista inicial de %s', page_key)
            clear_internal_page(self)
            show_dashboard(self)
            return None

        def build_panel():
            panel = None
            try:
                if not self.is_running or not host.winfo_exists():
                    return
                panel = factory(host)
                if not attach_internal_page_panel(self, page_key, host, panel):
                    try:
                        panel.destroy()
                    except Exception:
                        pass
                    return
                try:
                    if shell is not None and shell.winfo_exists():
                        shell.destroy()
                except Exception:
                    pass
                try:
                    panel_widget = panel.widget() if hasattr(panel, 'widget') else None
                    if panel_widget is not None:
                        panel_widget.lift()
                except Exception:
                    pass
            except Exception:
                logger.exception('No se pudo construir la vista avanzada %s', page_key)
                try:
                    if shell is not None and shell.winfo_exists():
                        for child in shell.winfo_children():
                            try:
                                child.destroy()
                            except Exception:
                                pass
                        ctk.CTkLabel(
                            shell,
                            text='No se pudo preparar esta vista.',
                            font=('Segoe UI', 13, 'bold'),
                            text_color=theme_color('#ef4444'),
                        ).place(relx=0.5, rely=0.46, anchor='center')
                except Exception:
                    pass

        # Un frame real de margen permite que Windows pinte el shell antes de la
        # creación del árbol CTk. 16 ms no añade espera perceptible al usuario.
        self._defer_ui_call(build_panel, 16)
        return None

    def open_cpu_details(self):
        """Abre CPU con respuesta inmediata y construcción diferida."""
        def factory(host):
            from gui.cpu_detail_panel import CPUDetailPanel
            return CPUDetailPanel(self, host)
        return self._open_deferred_hardware_detail(
            'cpu_details',
            title='Cargando información del procesador…',
            subtitle='Preparando especificaciones y telemetría CPU',
            panel_attr='cpu_detail_panel',
            factory=factory,
        )

    def open_ram_details(self):
        """Abre RAM con respuesta inmediata y construcción diferida."""
        def factory(host):
            from gui.ram_detail_panel import RAMDetailPanel
            return RAMDetailPanel(self, host)
        return self._open_deferred_hardware_detail(
            'ram_details',
            title='Cargando información de memoria…',
            subtitle='Preparando módulos, slots y telemetría RAM',
            panel_attr='ram_detail_panel',
            factory=factory,
        )

    def open_gpu_details(self):
        """Abre GPU con respuesta inmediata y construcción diferida."""
        def factory(host):
            from gui.gpu_detail_panel import GPUDetailPanel
            return GPUDetailPanel(self, host)
        return self._open_deferred_hardware_detail(
            'gpu_details',
            title='Cargando información gráfica…',
            subtitle='Preparando adaptadores, controlador y telemetría GPU',
            panel_attr='gpu_detail_panel',
            factory=factory,
        )

    def open_telemetry_details(self):
        """Abre una vista interna con la trazabilidad de las métricas certificadas."""
        host, reused = activate_internal_page(self, 'telemetry_details')
        if reused:
            panel = getattr(self, 'telemetry_detail_panel', None)
            if panel is not None:
                try:
                    panel.refresh()
                except Exception:
                    logger.exception('No se pudo refrescar la vista de trazabilidad de telemetría')
            return
        if host is None:
            return
        try:
            from gui.telemetry_detail_panel import TelemetryDetailPanel
            panel = TelemetryDetailPanel(self, host)
            self.telemetry_detail_panel = panel
            if not commit_internal_page(self, 'telemetry_details', host, panel):
                self.telemetry_detail_panel = None
        except Exception:
            logger.exception('No se pudo construir la vista de trazabilidad de telemetría')
            abort_internal_page(self, 'telemetry_details', host)

    def update_disks_ui(self, disks_data):
        if not self.is_running or not self.winfo_exists():
            return
        active_indexes = {d['index'] for d in disks_data}
        for idx in list(self.disk_widgets.keys()):
            if idx not in active_indexes:
                try:
                    self.disk_widgets[idx]['card'].destroy()
                except Exception:
                    pass
                del self.disk_widgets[idx]
        for d in disks_data:
            try:
                idx = d['index']
                if idx not in self.disk_widgets:
                    disk_parent = getattr(self.scroll_disks, 'content', self.scroll_disks)
                    card = ctk.CTkFrame(disk_parent, fg_color=BG_CARD, border_width=1, border_color=BORDER_COLOR, corner_radius=8)
                    card.pack(fill='x', pady=3, padx=2)
                    header = ctk.CTkFrame(card, fg_color='transparent')
                    header.pack(fill='x', padx=10, pady=(6, 2))
                    lbl_name = ctk.CTkLabel(header, text='', font=('Segoe UI', 10, 'bold'), text_color=theme_color('#f8fafc'))
                    lbl_name.pack(side='left')
                    btn_details = ctk.CTkButton(
                        header, text='Ver detalles', width=92, height=24,
                        fg_color=theme_color('#0d2942'), hover_color=theme_color('#164f7d'), text_color=theme_color('#75d2f7'),
                        border_width=1, border_color=theme_color('#1d5278'),
                        font=('Segoe UI', 8, 'bold'), corner_radius=7,
                        command=lambda disk_index=idx: self.open_storage_details(disk_index),
                    )
                    btn_details.pack(side='right', padx=(8, 0))
                    lbl_badge = ctk.CTkLabel(header, text='', font=('Segoe UI', 10, 'bold'))
                    lbl_badge.pack(side='right')
                    lbl_exact = ctk.CTkLabel(card, text='', font=('Segoe UI', 9), text_color=COLOR_CPU)
                    lbl_exact.pack(anchor='w', padx=10, pady=(0, 3))
                    bar = ctk.CTkProgressBar(card, height=5, progress_color=COLOR_CPU, fg_color=theme_color('#0f172a'))
                    bar.set(0)
                    bar.pack(fill='x', padx=10, pady=(0, 6))
                    self.disk_widgets[idx] = {'card': card, 'lbl_name': lbl_name, 'lbl_badge': lbl_badge, 'lbl_exact': lbl_exact, 'bar': bar, 'btn_details': btn_details}
                w = self.disk_widgets[idx]
                total_raw = d.get('total_gb')
                total_text = f'{float(total_raw):.2f} GB' if isinstance(total_raw, (int, float)) else 'N/A'
                w['lbl_name'].configure(text=f"💾 Disco {idx}: {d.get('model') or 'N/A'} [{d.get('mount_points') or 'N/A'}] ({total_text})")
                health_raw = d.get('health')
                if isinstance(health_raw, (int, float)):
                    health = float(health_raw)
                    h_color = COLOR_RAM if health >= 90 else '#f59e0b' if health >= 70 else '#ef4444'
                    w['lbl_badge'].configure(text=f'Salud: {health:.0f}%', text_color=h_color)
                else:
                    w['lbl_badge'].configure(text='Salud: N/A', text_color=COLOR_TEXT_DIM)
                used_percent = d.get('used_percent')
                used_gb = d.get('used_gb')
                used_mb = d.get('used_mb')
                used_kb = d.get('used_kb')
                if isinstance(used_percent, (int, float)):
                    exact_parts = [f'Usado: {float(used_percent):.1f}%']
                    if isinstance(used_gb, (int, float)):
                        exact_parts.append(f'{float(used_gb):.2f} GB')
                    if isinstance(used_mb, (int, float)):
                        exact_parts.append(f'{int(used_mb):,} MB')
                    if isinstance(used_kb, (int, float)):
                        exact_parts.append(f'{int(used_kb):,} KB')
                    w['lbl_exact'].configure(text='  ·  '.join(exact_parts))
                    percent = max(0.0, min(100.0, float(used_percent)))
                    if not w['bar'].winfo_manager():
                        w['bar'].pack(fill='x', padx=10, pady=(0, 6))
                    w['bar'].set(percent / 100.0)
                else:
                    w['lbl_exact'].configure(text='Uso: N/A')
                    w['bar'].pack_forget()
            except Exception:
                continue

    def _build_fast_disk_snapshot(self, telemetry):
        """Construye la operación `build_fast_disk_snapshot` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
        result = []
        devices = telemetry.get('_storage_devices') or []
        mount_points = []
        try:
            for part in psutil.disk_partitions(all=False):
                opts = str(getattr(part, 'opts', '')).lower()
                if 'cdrom' in opts:
                    continue
                mp = getattr(part, 'mountpoint', None)
                if mp and mp not in mount_points:
                    mount_points.append(mp)
        except Exception:
            mount_points = []
        for idx, device in enumerate(devices):
            try:
                model = device.get('name') or device.get('model') or f'Unidad {idx}'
                enrichment = (getattr(self, 'storage_health_cache', {}) or {}).get(idx, {})
                os_inventory = device.get('os_inventory') if isinstance(device.get('os_inventory'), dict) else {}
                total = device.get('total_space_gb')
                try:
                    if total is not None and float(total) <= 0:
                        total = None
                except Exception:
                    total = None
                if total is None:
                    total = enrichment.get('total_gb')
                if total is None:
                    size_bytes = os_inventory.get('size_bytes_os')
                    try:
                        total = float(size_bytes) / (1024 ** 3) if size_bytes is not None else None
                    except Exception:
                        total = None
                free = device.get('free_space_gb')
                used_percent = device.get('used_space_percent')
                # storage_health_cache aplica autoridad y validación de fuentes.
                # Si aún no existe cache, 0% se considera ambiguo y no debe generar
                # un crítico falso durante los primeros segundos de la sesión.
                life = enrichment.get('health') if isinstance(enrichment, dict) else None
                if life is None:
                    raw_life = device.get('life_percent')
                    try:
                        life = float(raw_life) if raw_life is not None and float(raw_life) > 0.0 else None
                    except Exception:
                        life = None
                total = float(total) if total is not None else None
                free = float(free) if free is not None else None
                if used_percent is None and total and (free is not None) and (total > 0):
                    used_percent = (total - free) / total * 100.0
                if used_percent is not None:
                    used_percent = max(0.0, min(100.0, float(used_percent)))
                used_gb = total * used_percent / 100.0 if total is not None and used_percent is not None else None
                mounts_text = enrichment.get('mount_points') or (', '.join(mount_points) if len(devices) == 1 and mount_points else 'N/A')
                temp = enrichment.get('temperature_c') if isinstance(enrichment, dict) else None
                if temp is None:
                    raw_temp = device.get('temperature_c')
                    try:
                        temp = float(raw_temp) if raw_temp is not None and float(raw_temp) > 0.0 else None
                    except Exception:
                        temp = None
                result.append({
                    'index': idx,
                    'model': str(model),
                    'mount_points': mounts_text,
                    'total_gb': round(total, 2) if total is not None else None,
                    'health': float(life) if life is not None else None,
                    'health_label': enrichment.get('health_label'),
                    'health_source': enrichment.get('health_source'),
                    'health_derived': bool(enrichment.get('health_derived')),
                    'windows_health_status': enrichment.get('windows_health_status'),
                    'wear_percent': enrichment.get('wear_percent'),
                    'used_percent': round(used_percent, 1) if used_percent is not None else None,
                    'used_gb': round(used_gb, 2) if used_gb is not None else None,
                    'used_mb': int(used_gb * 1024) if used_gb is not None else None,
                    'used_kb': int(used_gb * 1024 * 1024) if used_gb is not None else None,
                    'temperature_c': temp,
                    'source': device.get('source', 'LibreHardwareMonitor'),
                    'quality': device.get('quality', 'VALID'),
                })
            except Exception:
                continue
        return result

    # Adquiere telemetría en segundo plano para no bloquear la interfaz.
    def telemetry_loop(self):
        from core.telemetry import get_system_telemetry, calculate_preliminary_score
        from database.telemetry_repository import save_telemetry_record
        pythoncom = None
        if IS_WINDOWS:
            try:
                import pythoncom as _pythoncom
                pythoncom = _pythoncom
            except Exception:
                pythoncom = None
        if IS_WINDOWS and pythoncom:
            try:
                pythoncom.CoInitialize()
            except Exception:
                pass
        try:
            psutil.cpu_percent(interval=None)
            disks = []
            while self.is_running:
                cycle_start = time.monotonic()
                try:
                    telemetry = get_system_telemetry()
                    disks = self._build_fast_disk_snapshot(telemetry)
                    score = calculate_preliminary_score(telemetry['cpu_usage'], telemetry['ram_usage'], telemetry['cpu_temp'], telemetry['gpu_temp'], disks)
                    try:
                        if self.thermal_throttling_detector is not None:
                            self.thermal_throttling_state = self.thermal_throttling_detector.add_sample(telemetry)
                    except Exception:
                        self._log_throttled_exception('throttling_detector', 'Fallo al evaluar throttling')
                    try:
                        now_hist = time.time()
                        if now_hist - float(getattr(self, '_health_history_last_record', 0.0) or 0.0) >= 60.0:
                            cached_battery = getattr(self, 'battery_health_cache', None)
                            battery_health_value = cached_battery.get('health_percent') if isinstance(cached_battery, dict) else None
                            if self.health_history_store is not None:
                                self.health_history_store.record_snapshot(
                                    telemetry, disks, score, ts=now_hist,
                                    battery_health_override=battery_health_value,
                                    context={'process_count': len(psutil.pids())},
                                )
                            self._health_history_last_record = now_hist
                    except Exception:
                        self._log_throttled_exception('health_history', 'Fallo al persistir historial de salud')
                    if self.diagnostic_session is not None and self.diagnostic_session.active:
                        self.diagnostic_session.add_sample(telemetry, disks)
                    with self.telemetry_lock:
                        self.pending_telemetry = telemetry
                        self.pending_disks = list(disks)
                        self.latest_score = score
                        self.cpu_history.append(telemetry['cpu_usage'] if telemetry['cpu_usage'] is not None else float('nan'))
                        self.ram_history.append(telemetry['ram_usage'] if telemetry['ram_usage'] is not None else float('nan'))
                        self.gpu_history.append(telemetry['gpu_usage'] if telemetry['gpu_usage'] is not None else float('nan'))
                    if not self._startup_first_telemetry_acquired:
                        self._startup_first_telemetry_acquired = True
                        primary_keys = ('cpu_usage', 'ram_usage', 'gpu_usage', 'cpu_temp', 'gpu_temp', 'cpu_ghz')
                        available = sum(1 for key in primary_keys if telemetry.get(key) is not None)
                        self._startup_mark('first_telemetry_acquired', available_primary_metrics=available)
                    self.db_counter += 1
                    if self.db_counter >= 20:
                        save_telemetry_record(telemetry['cpu_usage'], telemetry['ram_usage'], None, None, score)
                        self.db_counter = 0
                except Exception:
                    self._log_throttled_exception('telemetry_loop', 'Fallo durante un ciclo de adquisición de telemetría')
                elapsed = time.monotonic() - cycle_start
                sleep_time = max(0.2, 1.0 - elapsed)
                end_time = time.monotonic() + sleep_time
                while self.is_running and time.monotonic() < end_time:
                    remaining = end_time - time.monotonic()
                    if remaining <= 0:
                        break
                    time.sleep(min(0.05, remaining))
        finally:
            if IS_WINDOWS and pythoncom:
                try:
                    pythoncom.CoUninitialize()
                except Exception:
                    pass

    def _prime_startup_charts_from_real_history(self):
        """Dibuja la primera historia real antes de revelar el Dashboard.

        No crea muestras: sólo consume los deques que llenó telemetry_loop. Si
        Matplotlib no está disponible, el resto de CorePulse mantiene REAL_OR_NA.
        """
        if not getattr(self, '_charts_ready', False) or getattr(self, 'canvas', None) is None:
            return False
        try:
            with self.telemetry_lock:
                cpu_data = list(self.cpu_history)
                ram_data = list(self.ram_history)
                gpu_data = list(self.gpu_history)
            cpu_x, cpu_series, cpu_count = self._chart_series_for_display(cpu_data)
            ram_x, ram_series, ram_count = self._chart_series_for_display(ram_data)
            gpu_x, gpu_series, gpu_count = self._chart_series_for_display(gpu_data)
            visible_count = max(cpu_count, ram_count, gpu_count)
            self.line_cpu.set_data(cpu_x, cpu_series)
            self.line_ram.set_data(ram_x, ram_series)
            self.line_gpu.set_data(gpu_x, gpu_series)
            self._refresh_trend_axis_labels(visible_count)
            # draw() es intencional sólo una vez durante el gate: garantiza que el
            # primer frame visible ya contiene la muestra que acaba de llegar.
            self.canvas.draw()
            return True
        except Exception:
            self._log_throttled_exception('startup_chart_prime', 'No se pudo cebar el primer frame de gráficos')
            return False

    def _complete_startup_after_first_telemetry(self, telemetry):
        """Completa el gate sólo después de una muestra real renderizada."""
        if self._startup_first_telemetry_applied or not isinstance(telemetry, dict):
            return
        self._startup_first_telemetry_applied = True
        primary_keys = ('cpu_usage', 'ram_usage', 'gpu_usage', 'cpu_temp', 'gpu_temp', 'cpu_ghz')
        available = sum(1 for key in primary_keys if telemetry.get(key) is not None)
        charts_primed = self._prime_startup_charts_from_real_history()
        self._startup_mark(
            'first_telemetry_ui_ready',
            available_primary_metrics=available,
            charts_primed=bool(charts_primed),
        )
        detail = (
            f'Primera lectura aplicada · {available} métricas principales disponibles.'
            if available
            else 'Monitoreo activo; los sensores no expuestos por este equipo permanecerán en N/A.'
        )
        self.update_startup_component('services', 1.0, 'Monitoreo en tiempo real activo', detail)
        self._persist_startup_metrics()

    # Consume de forma segura las muestras pendientes y actualiza la interfaz.
    def process_pending_telemetry(self):
        if not self.is_running:
            return
        telemetry = None
        disks = None
        try:
            with self.telemetry_lock:
                if self.pending_telemetry is not None:
                    telemetry = self.pending_telemetry
                    disks = list(self.pending_disks)
                    self.pending_telemetry = None
            if telemetry is not None:
                before = int(getattr(self, '_telemetry_ui_apply_count', 0) or 0)
                self.apply_telemetry_to_ui(telemetry, disks)
                after = int(getattr(self, '_telemetry_ui_apply_count', 0) or 0)
                if after > before:
                    # Importante: esta llamada ocurre después del wrapper profesional,
                    # por lo que tarjetas, títulos y cobertura ya reflejan la muestra.
                    self._complete_startup_after_first_telemetry(telemetry)
        except Exception:
            self._log_throttled_exception('telemetry_ui_dispatch', 'Fallo al entregar telemetría a la interfaz')
        if self.is_running:
            self.telemetry_after_id = self.after(250, self.process_pending_telemetry)

    # Presenta solo valores reales o N/A; nunca convierte ausencia de datos en cero.
    def apply_telemetry_to_ui(self, telemetry, disks):
        if not self.is_running or not self.winfo_exists():
            return
        from core.telemetry import calculate_preliminary_score
        try:
            self.latest_telemetry = telemetry
            try:
                trend_state = self.realtime_agent.get_state() if hasattr(self, 'realtime_agent') else {}
            except Exception:
                trend_state = {}
            if self.session_trend_collector is not None:
                self.session_trend_collector.add_sample(telemetry, state=trend_state)
            self.latest_disks = list(disks)
            self.lbl_cpu_title.configure(text=f"CPU: {telemetry['cpu_name']}")
            cpu_raw = telemetry.get('cpu_usage')
            cpu_usage = max(0.0, min(100.0, float(cpu_raw))) if cpu_raw is not None else None
            self.lbl_cpu.configure(text=f'{cpu_usage:.1f}%' if cpu_usage is not None else 'N/A')
            if cpu_usage is not None:
                if not self.bar_cpu.winfo_manager():
                    self.bar_cpu.pack(fill='x', padx=10, pady=(0, 4), before=self.lbl_cpu_temp)
                self.bar_cpu.set(cpu_usage / 100.0)
            else:
                self.bar_cpu.pack_forget()
            cpu_temp = telemetry.get('cpu_temp')
            self.lbl_cpu_temp.configure(text=f'Temp: {cpu_temp:.1f} °C' if cpu_temp is not None else 'Temp: N/A')
            ram_raw = telemetry.get('ram_usage')
            ram_usage = max(0.0, min(100.0, float(ram_raw))) if ram_raw is not None else None
            self.lbl_ram.configure(text=f'{ram_usage:.1f}%' if ram_usage is not None else 'N/A')
            if ram_usage is not None:
                if not self.bar_ram.winfo_manager():
                    self.bar_ram.pack(fill='x', padx=10, pady=(0, 4), before=self.lbl_ram_gb)
                self.bar_ram.set(ram_usage / 100.0)
            else:
                self.bar_ram.pack_forget()
            ram_used = telemetry.get('ram_used_gb')
            ram_total = telemetry.get('ram_total_gb')
            self.lbl_ram_gb.configure(text=f'{ram_used:.2f} GB / {ram_total:.2f} GB' if ram_used is not None and ram_total is not None else 'N/A')
            self.lbl_gpu_title.configure(text=f"GPU: {telemetry['gpu_name']}")
            gpu_raw = telemetry.get('gpu_usage')
            gpu_usage = max(0.0, min(100.0, float(gpu_raw))) if gpu_raw is not None else None
            self.lbl_gpu.configure(text=f'{gpu_usage:.1f}%' if gpu_usage is not None else 'N/A')
            if gpu_usage is not None:
                if not self.bar_gpu.winfo_manager():
                    self.bar_gpu.pack(fill='x', padx=10, pady=(0, 4), before=self.lbl_gpu_temp)
                self.bar_gpu.set(gpu_usage / 100.0)
            else:
                self.bar_gpu.pack_forget()
            gpu_temp = telemetry.get('gpu_temp')
            self.lbl_gpu_temp.configure(text=f'Temp: {gpu_temp:.1f} °C' if gpu_temp is not None else 'Temp: N/A')
            try:
                disk_signature = tuple(((d.get('index'), d.get('name'), d.get('used_percent'), d.get('health'), d.get('temperature'), d.get('used_gb'), d.get('total_gb')) for d in disks or []))
            except Exception:
                disk_signature = None
            if disk_signature != getattr(self, '_disk_ui_signature', None):
                self._disk_ui_signature = disk_signature
                self.update_disks_ui(disks)
            score = calculate_preliminary_score(telemetry['cpu_usage'], telemetry['ram_usage'], telemetry['cpu_temp'], telemetry['gpu_temp'], disks)
            self.latest_score = score
            if isinstance(score, (int, float)):
                self.lbl_health_val.configure(text=f'{score:.1f}%')
                if score < 50:
                    self.lbl_health_status.configure(text='ESTADO CRÍTICO', text_color='#ef4444')
                    self.lbl_health_val.configure(text_color='#ef4444')
                elif score < 70:
                    self.lbl_health_status.configure(text='ADVERTENCIA', text_color='#f59e0b')
                    self.lbl_health_val.configure(text_color='#f59e0b')
                elif score < 85:
                    self.lbl_health_status.configure(text='ESTADO ESTABLE', text_color='#38bdf8')
                    self.lbl_health_val.configure(text_color='#38bdf8')
                else:
                    self.lbl_health_status.configure(text='ESTADO ÓPTIMO', text_color=COLOR_RAM)
                    self.lbl_health_val.configure(text_color=COLOR_RAM)
            else:
                self.lbl_health_val.configure(text='N/A', text_color=COLOR_TEXT_DIM)
                self.lbl_health_status.configure(text='NO EVALUABLE', text_color=COLOR_TEXT_DIM)
            # Contador de commit visual. Sólo aumenta si la muestra atravesó todo
            # el render base sin excepción; el gate 64w depende de este commit.
            self._telemetry_ui_apply_count = int(getattr(self, '_telemetry_ui_apply_count', 0) or 0) + 1
        except Exception:
            self._log_throttled_exception('telemetry_ui_apply', 'Fallo al renderizar una muestra de telemetría')

    def _close_smart_alert_window(self):
        self.smart_alert_window = None
        self.smart_alert_panel = None
        if getattr(self, '_active_internal_page', None) == 'alerts':
            clear_internal_page(self)

    def open_smart_alert_window(self):
        """Muestra Alertas como página interna con commit síncrono."""
        if not getattr(self, 'is_running', False):
            return
        host = None
        panel = None
        try:
            host, reused = activate_internal_page(self, 'alerts')
            if reused and self.smart_alert_panel is not None:
                def refresh_alerts():
                    state = self.realtime_agent.get_state()
                    diagnostic = self.diagnostic_explainer.explain_state(state)
                    self.smart_alert_panel.render(state, diagnostic)
                self._defer_ui_call(refresh_alerts)
                return
            self.smart_alert_window = None
            from gui.alert_panel import SmartAlertPanel
            panel = SmartAlertPanel(host)
            widget = panel.widget()
            if widget is not None:
                widget.pack(fill='both', expand=True)
            if not commit_internal_page(self, 'alerts', host, panel):
                raise RuntimeError('La navegación de Alertas fue invalidada antes del commit.')
            def initial_alert_render():
                if self.smart_alert_panel is not panel or getattr(self, '_active_internal_page', None) != 'alerts':
                    return
                state = self.realtime_agent.get_state()
                diagnostic = self.diagnostic_explainer.explain_state(state)
                panel.render(state, diagnostic)
            self._defer_ui_call(initial_alert_render)
        except Exception as exc:
            self.smart_alert_window = None
            abort_internal_page(self, 'alerts', host, panel)
            cp_error(self, 'Alertas y diagnóstico', f'No se pudo abrir Alertas y Diagnóstico:\n\n{exc}')

    def _refresh_smart_alert_ui(self, state=None):
        if not getattr(self, 'is_running', False):
            return
        try:
            if state is None:
                state = self.realtime_agent.get_state()
            diagnostic = self.diagnostic_explainer.explain_state(state)
            explanations = diagnostic.get('explanations') or []
            overall = state.get('overall', 'UNKNOWN')
            colors = {'CRITICAL': '#ef4444', 'WARNING': '#f59e0b', 'INFO': '#38bdf8', 'OBSERVING': '#60a5fa', 'NORMAL': COLOR_RAM, 'UNKNOWN': COLOR_TEXT_DIM}
            if self.lbl_alert_summary is not None:
                if explanations:
                    top = explanations[0]
                    self.lbl_alert_summary.configure(text=f"{overall} • {top.get('component', 'SYSTEM')} • {top.get('title', 'Alerta activa')}", text_color=colors.get(overall, COLOR_TEXT_DIM))
                elif overall == 'OBSERVING':
                    self.lbl_alert_summary.configure(text='◉ AGENTE OBSERVANDO SESIÓN DE JUEGO', text_color=colors['OBSERVING'])
                else:
                    self.lbl_alert_summary.configure(text='MONITOREO INICIANDO', text_color=COLOR_RAM)
            if self.smart_alert_panel is not None and getattr(self, '_active_internal_page', None) == 'alerts':
                try:
                    widget = self.smart_alert_panel.widget()
                    if widget is not None and widget.winfo_exists():
                        self.smart_alert_panel.render(state, diagnostic)
                except Exception:
                    self.smart_alert_panel = None
        except Exception:
            pass

    def _ensure_agent_status_panel(self):
        if not getattr(self, 'is_running', False):
            return
        try:
            render_agent_card(self)
        except Exception:
            pass

    def _refresh_agent_status_panel(self, state=None):
        if not getattr(self, 'is_running', False):
            return
        try:
            if state is None:
                state = self.realtime_agent.get_state()
            render_agent_card(self, state)
        except Exception:
            pass

    def _close_alert_history_window(self):
        self.alert_history_window = None
        self.alert_history_panel = None
        if getattr(self, '_active_internal_page', None) == 'history':
            clear_internal_page(self)

    def open_alert_history_window(self):
        """Muestra el historial dentro de CorePulse con commit síncrono."""
        if not getattr(self, 'is_running', False):
            return
        if self.alert_history_store is None:
            cp_info(self, 'Historial de alertas', 'El historial se está inicializando. Intenta nuevamente en un momento.')
            return
        host = None
        panel = None
        try:
            host, reused = activate_internal_page(self, 'history')
            if reused and self.alert_history_panel is not None:
                def refresh_history():
                    rows = self.alert_history_store.refresh()
                    summary = self.alert_history_store.summary()
                    self.alert_history_panel.render(rows, summary)
                self._defer_ui_call(refresh_history)
                return
            self.alert_history_window = None
            from gui.alert_history_panel import AlertHistoryPanel
            panel = AlertHistoryPanel(host)
            widget = panel.widget()
            if widget is not None:
                widget.pack(fill='both', expand=True)
            if not commit_internal_page(self, 'history', host, panel):
                raise RuntimeError('La navegación de Historial fue invalidada antes del commit.')
            def initial_history_render():
                if self.alert_history_panel is not panel or getattr(self, '_active_internal_page', None) != 'history':
                    return
                rows = self.alert_history_store.refresh()
                summary = self.alert_history_store.summary()
                panel.render(rows, summary)
            self._defer_ui_call(initial_history_render)
        except Exception as exc:
            self.alert_history_window = None
            abort_internal_page(self, 'history', host, panel)
            cp_error(self, 'Historial de alertas', f'No se pudo abrir Historial de Alertas:\n\n{exc}')

    def _refresh_alert_history_ui(self):
        if not getattr(self, 'is_running', False):
            return
        if not hasattr(self, 'alert_history_store'):
            return
        now = time.monotonic()
        last = float(getattr(self, '_history_ui_last_refresh', 0.0) or 0.0)
        if now - last < 0.85:
            return
        self._history_ui_last_refresh = now
        try:
            rows = self.alert_history_store.refresh()
            summary = self.alert_history_store.summary()
            panel = self.alert_history_panel
            if panel is None:
                return
            if hasattr(panel, 'is_visible') and (not panel.is_visible()):
                return
            panel.render(rows, summary)
        except Exception:
            pass

    def _close_session_trends_window(self):
        self.session_trends_window = None
        self.session_trends_panel = None
        if getattr(self, '_active_internal_page', None) == 'trends':
            clear_internal_page(self)

    def open_session_trends_window(self):
        """Muestra Tendencias como vista interna con commit síncrono."""
        if not getattr(self, 'is_running', False):
            return
        if self.session_trend_collector is None:
            cp_info(self, 'Tendencias', 'El historial de sesiones se está inicializando. Intenta nuevamente en un momento.')
            return
        host = None
        panel = None
        try:
            host, reused = activate_internal_page(self, 'trends')
            if reused and self.session_trends_panel is not None:
                self._defer_ui_call(self._refresh_session_trends_ui)
                return
            self.session_trends_window = None
            from gui.session_trends_panel import SessionTrendsPanel
            panel = SessionTrendsPanel(host)
            widget = panel.widget()
            if widget is not None:
                widget.pack(fill='both', expand=True)
            if not commit_internal_page(self, 'trends', host, panel):
                raise RuntimeError('La navegación de Tendencias fue invalidada antes del commit.')
            def initial_trends_render():
                if self.session_trends_panel is not panel or getattr(self, '_active_internal_page', None) != 'trends':
                    return
                sessions = self.session_trend_collector.load_sessions(limit=10)
                from core.session_trends import SessionTrendAnalyzer
                summary = SessionTrendAnalyzer(sessions).summary(limit=10)
                panel.render(sessions, summary)
            self._defer_ui_call(initial_trends_render)
        except Exception as exc:
            self.session_trends_window = None
            abort_internal_page(self, 'trends', host, panel)
            cp_error(self, 'Tendencias', f'No se pudo abrir Tendencias:\n\n{exc}')

    def _refresh_session_trends_ui(self):
        if self.session_trends_panel is None:
            return
        try:
            sessions = self.session_trend_collector.load_sessions(limit=10)
            from core.session_trends import SessionTrendAnalyzer
            summary = SessionTrendAnalyzer(sessions).summary(limit=10)
            self.session_trends_panel.render(sessions, summary)
        except Exception:
            pass

    def restore_from_tray(self):
        if not getattr(self, 'is_running', False):
            return
        self._minimized_to_tray = False
        try:
            self.deiconify()
            self.lift()
            self.focus_force()
        except Exception:
            pass
        try:
            refresh_navigation_state(self)
        except Exception:
            pass

    def minimize_to_tray(self):
        if not getattr(self, 'is_running', False):
            return
        tray = getattr(self, 'tray_service', None)
        tray_ready = bool(tray is not None and getattr(tray, 'available', False) and getattr(tray, 'running', False))
        self._minimized_to_tray = tray_ready
        try:
            if tray_ready:
                self.withdraw()
                tray.notify_minimized()
            else:
                self.iconify()
        except Exception:
            try:
                self.iconify()
            except Exception:
                pass

    def _update_agent_ui(self):
        if not getattr(self, 'is_running', False):
            return
        try:
            state = self.realtime_agent.get_state()
            mode = state.get('mode', 'UNKNOWN')
            overall = state.get('overall', 'UNKNOWN')
            game = state.get('game') or {}
            if mode == 'GAME':
                game_name = str(game.get('name') or '').replace('\\', '/').split('/')[-1]
                status_text = f"MODO JUEGO • {game_name or '3D'} • {overall}"
            else:
                status_text = f'AGENTE ACTIVO • {overall}'
            colors = {'NORMAL': '#22c55e', 'INFO': '#38bdf8', 'WARNING': '#f59e0b', 'CRITICAL': '#ef4444', 'ERROR': '#ef4444', 'UNKNOWN': theme_color('#94a3b8')}
            self.tray_service.notify_state()
            self._refresh_agent_status_panel(state)
            self._refresh_smart_alert_ui(state)
            self._refresh_alert_history_ui()
        except Exception:
            self._log_throttled_exception('agent_ui', 'Fallo al refrescar el estado visual del agente')
        if getattr(self, 'is_running', False):
            self.agent_after_id = self.after(1500, self._update_agent_ui)

    # Cierra hilos y proveedores de sensores antes de destruir la ventana principal.
    def on_close(self):
        logger.info('[CORE] Cierre solicitado; restaurando cambios temporales y apagando servicios')
        if getattr(self, '_shutdown_started', False):
            return
        self._shutdown_started = True
        self.is_running = False
        for attr in ('resize_timer', 'telemetry_after_id', 'chart_after_id', 'diagnostic_after_id', 'agent_after_id', '_battery_health_refresh_after_id', '_recovery_heartbeat_after'):
            after_id = getattr(self, attr, None)
            if after_id:
                try:
                    self.after_cancel(after_id)
                except Exception:
                    pass
                try:
                    setattr(self, attr, None)
                except Exception:
                    pass
        try:
            if hasattr(self, 'session_trend_collector'):
                self.session_trend_collector.clear_session()
        except Exception:
            pass
        try:
            if hasattr(self, 'alert_history_store'):
                self.alert_history_store.close_session()
        except Exception:
            pass
        try:
            self.close_overlay()
        except Exception:
            pass
        try:
            manager = getattr(self, 'overlay_hotkey_manager', None)
            if manager is not None:
                manager.stop()
        except Exception:
            pass
        try:
            clear_internal_page(self)
        except Exception:
            pass
        for fn_name in ('_close_smart_alert_window', '_close_alert_history_window', '_close_session_trends_window', '_close_overlay_config_window'):
            try:
                fn = getattr(self, fn_name, None)
                if callable(fn):
                    fn()
            except Exception:
                pass
        try:
            from core.safe_shutdown import shutdown_corepulse_services
            shutdown_corepulse_services(agent=getattr(self, 'realtime_agent', None), tray=getattr(self, 'tray_service', None), overlay=getattr(self, 'rtss_overlay_service', None), performance=getattr(self, 'performance_manager', None), verbose=False)
        except Exception:
            pass
        try:
            if hasattr(self, 'telemetry_thread') and self.telemetry_thread.is_alive():
                self.telemetry_thread.join(timeout=3.0)
        except Exception:
            pass
        try:
            from core.pythonnet_shutdown import wait_for_named_threads, shutdown_telemetry_provider
            self._shutdown_thread_result = wait_for_named_threads(names=('CorePulse-Telemetry',), timeout=1.0)
        except Exception:
            self._shutdown_thread_result = {'ok': False}
        try:
            from core.pythonnet_shutdown import shutdown_telemetry_provider
            self._shutdown_sensor_result = shutdown_telemetry_provider(join_timeout=2.5, verbose=False)
        except Exception as exc:
            self._shutdown_sensor_result = {'ok': False, 'error': f'{type(exc).__name__}: {exc}'}

        # Última autoridad de energía del proceso. El video de la regresión 86w
        # mostró que el GUID podía cambiar durante los segundos de teardown.
        # Por eso esta comprobación se ejecuta DESPUÉS de detener telemetría y
        # sensores, inmediatamente antes de destruir la aplicación.
        try:
            manager = getattr(self, 'performance_manager', None)
            finalize = getattr(manager, 'finalize_persistent_plan', None) if manager is not None else None
            if callable(finalize):
                self._shutdown_power_persistence_result = finalize()
                if not (self._shutdown_power_persistence_result or {}).get('success'):
                    logger.error(
                        '[POWER] Verificación final de persistencia falló antes de salir: %s',
                        (self._shutdown_power_persistence_result or {}).get('message'),
                    )
                else:
                    logger.info(
                        '[POWER] Plan persistente verificado como última operación antes de salir: %s',
                        (self._shutdown_power_persistence_result or {}).get('windows_plan_guid'),
                    )
        except Exception as exc:
            self._shutdown_power_persistence_result = {'success': False, 'message': f'{type(exc).__name__}: {exc}'}
            logger.exception('[POWER] Falló la verificación final del plan antes de destruir CorePulse')
        # El marcador se limpia sólo después de terminar los rollbacks y de
        # verificar el plan persistente. Si el proceso muere antes, V119 lo
        # tratará correctamente como cierre no limpio en el siguiente arranque.
        try:
            recovery = getattr(self, 'session_recovery', None)
            if recovery is not None:
                self.session_recovery_status = recovery.mark_clean_shutdown()
        except Exception:
            logger.exception('[RECOVERY] No se pudo marcar el cierre como limpio')
        try:
            self.destroy()
        except Exception:
            pass
if __name__ == '__main__':
    app = App()
    # Ejecutar main.py directamente conserva el mismo gate de integridad que el EXE.
    # No se marca integridad como lista por suposición.
    try:
        from corepulse_launcher import _schedule_deferred_integrity
        app.after_idle(lambda: _schedule_deferred_integrity(app))
    except Exception as exc:
        app.after_idle(lambda e=exc: app.handle_runtime_integrity_result(False, f'{type(e).__name__}: {e}'))
    app.mainloop()
