"""Punto de entrada de CorePulse. Coordina interfaz, telemetría, diagnóstico, base de datos, overlay y reporte."""
import sys
from core.python_compat import enforce_minimum_python
enforce_minimum_python()

from core.theme_manager import color as theme_color, get_ctk_appearance_mode, brand_symbol_path, toggle_theme, theme_action_label, restart_application
# Código refactorizado: nombres estables y documentación en español.
from pathlib import Path
from core.runtime_logging import configure_runtime_logging, get_logger, install_exception_hooks
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
from core.env_config import load_corepulse_env
from core.version import VERSION_LABEL
COREPULSE_ENV_STATUS = load_corepulse_env()
from collections import deque
from tkinter import messagebox, filedialog
from datetime import datetime
from PIL import Image, ImageTk
try:
    from customtkinter.windows.widgets import ctk_scrollable_frame
    _original_check_scroll = ctk_scrollable_frame.CTkScrollableFrame._check_if_valid_scroll

    def _patched_check_scroll(self, widget):
        if isinstance(widget, str):
            try:
                widget = self.nametowidget(widget)
            except Exception:
                return False
        return _original_check_scroll(self, widget)
    ctk_scrollable_frame.CTkScrollableFrame._check_if_valid_scroll = _patched_check_scroll
except Exception:
    pass
IS_WINDOWS = platform.system() == 'Windows'
if IS_WINDOWS:
    try:
        import pythoncom
    except ImportError:
        pythoncom = None
else:
    pythoncom = None
import matplotlib
matplotlib.use('TkAgg')
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from core.diagnostic_pipeline import integrate_current_diagnostic_pipeline
from core.report_generator import generate_pdf_report
from core.realtime_agent import RealTimeAgent
from core.diagnostic_explainer import DiagnosticExplainer
from gui.alert_panel import SmartAlertPanel
from core.alert_history_store import AlertHistoryStore
from gui.alert_history_panel import AlertHistoryPanel
from core.safe_shutdown import shutdown_corepulse_services
from core.pythonnet_shutdown import shutdown_telemetry_provider, wait_for_named_threads
from core.tray_service import CorePulseTray
from core.telemetry import get_system_telemetry, calculate_preliminary_score
from core.session_trends import SessionTrendCollector, SessionTrendAnalyzer
from core.health_history import HealthHistoryStore
from core.thermal_throttling import ThermalThrottlingDetector
from core.battery_health import collect_battery_health
from gui.session_trends_panel import SessionTrendsPanel
from core.adaptive_diagnostic import AdaptiveDiagnosticSession, readiness_stage
from core.diagnostic_session import DiagnosticSession, SESSION_SECONDS
from database.telemetry_repository import initialize_database, save_telemetry_record
from gui.overlay import GameOverlay
from gui.dashboard import apply_professional_dashboard
from gui.thermal_health_binding import apply_thermal_health_semantics
from gui.live_health_binding import apply_live_health_authority
from gui.dashboard_layout import apply_dashboard_architecture, render_agent_card
from gui.sidebar import apply_clean_text_sidebar
from gui.hardware_storage_view import apply_hardware_storage_information_architecture
from gui.storage_detail_panel import show_storage_details
from gui.telemetry_detail_panel import TelemetryDetailPanel
from gui.cpu_detail_panel import CPUDetailPanel
from gui.gpu_detail_panel import GPUDetailPanel
from gui.ram_detail_panel import RAMDetailPanel
from gui.network_detail_panel import NetworkDetailPanel
from gui.windows_tweaks_panel import WindowsTweaksPanel
from gui.health_center_panel import HealthCenterPanel
from gui.monitoring_status import apply_monitoring_service_agent_separation
from gui.overlay_config_panel import OverlayConfigPanel
from gui.dialogs import info as cp_info, warning as cp_warning, error as cp_error, ask_pdf_directory
from gui.ui_consistency import apply_ui_consistency, refresh_navigation_state
from gui.integration import apply_runtime_integration
from gui.adaptive_window import apply_preferred_launch_geometry
from gui.diagnostic_view import show_diagnostic_experience
from gui.internal_navigation import activate_internal_page, commit_internal_page, abort_internal_page, clear_internal_page, show_dashboard
# Configuración visual global de la aplicación.
ctk.set_appearance_mode(get_ctk_appearance_mode())
BG_MAIN = theme_color('#0b0f19')
BG_CARD = theme_color('#151c2c')
BG_SIDEBAR = theme_color('#0d1322')
BORDER_COLOR = theme_color('#232f48')
COLOR_CPU = '#38bdf8'
COLOR_RAM = '#10b981'
COLOR_GPU = '#a855f7'
COLOR_TEXT_DIM = theme_color('#94a3b8')

# Coordinador principal: conecta interfaz, telemetría, diagnóstico, persistencia y reporte.
class App(ctk.CTk):

    def toggle_ui_theme(self):
        """Alterna claro/oscuro y reinicia la UI con una paleta coherente."""
        button = getattr(self, '_theme_toggle_button', None)
        try:
            if button is not None:
                button.configure(text='Aplicando tema…', state='disabled')
            self.update_idletasks()
        except Exception:
            pass
        try:
            toggle_theme()
        except Exception:
            logger.exception('No se pudo guardar la preferencia de tema')
            try:
                if button is not None:
                    button.configure(text=theme_action_label(), state='normal')
            except Exception:
                pass
            return
        restart_application()

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
        self.title('CorePulse — Hardware Monitoring & Diagnostics')
        self.resizable(True, True)
        self.configure(fg_color=BG_MAIN)
        self.protocol('WM_DELETE_WINDOW', self.minimize_to_tray)
        project_root = Path(__file__).resolve().parent
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
        initialize_database()
        self.is_running = True
        self.realtime_agent = RealTimeAgent()
        self.alert_history_store = AlertHistoryStore(self.realtime_agent)
        self.alert_history_panel = None
        self.agent_status_panel = None
        self.diagnostic_explainer = DiagnosticExplainer()
        self.smart_alert_panel = None
        self.smart_alert_window = None
        self.alert_history_window = None
        self.lbl_alert_summary = None
        self.tray_service = CorePulseTray(self, self.realtime_agent)
        self.tray_service.start()
        self.agent_after_id = None
        self.after(1000, self._update_agent_ui)
        self.overlay_window = None
        self.overlay_config_window = None
        self.overlay_config_panel = None
        self._minimized_to_tray = False
        self.latest_telemetry = None
        self.latest_disks = []
        self.latest_score = None
        self.session_trend_collector = SessionTrendCollector()
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
        self.health_history_store = HealthHistoryStore()
        self.thermal_throttling_detector = ThermalThrottlingDetector()
        self.thermal_throttling_state = {'cpu': {'state': 'N/A'}, 'gpu': {'state': 'N/A'}}
        self._health_history_last_record = 0.0
        self.battery_health_cache = None
        self._battery_health_refresh_running = False
        self.after(3500, self._schedule_battery_health_refresh)
        self.max_points = 25
        self.cpu_history = deque([float('nan')] * self.max_points, maxlen=self.max_points)
        self.ram_history = deque([float('nan')] * self.max_points, maxlen=self.max_points)
        self.gpu_history = deque([float('nan')] * self.max_points, maxlen=self.max_points)
        self.db_counter = 0
        self.diagnostic_session = AdaptiveDiagnosticSession(min_seconds=30, max_seconds=90, min_samples=25, context_stability_seconds=8, alert_stability_seconds=12)
        self._pdf_export_in_progress = False
        self._pdf_export_job = None
        self.diagnostic_result = None
        self.current_recommendation_pipeline = None
        self.diagnostic_json_path = None
        self.diagnostic_telemetry_snapshot = None
        self.diagnostic_disks_snapshot = None
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
        self.frame_logo.pack(anchor='w', padx=15, pady=(20, 2), fill='x')
        logo_img_path = None
        project_root = Path(__file__).resolve().parent
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
        self.card_health_sidebar.pack(fill='x', padx=12, pady=5)
        ctk.CTkLabel(self.card_health_sidebar, text='SALUD DEL SISTEMA', font=('Segoe UI', 9, 'bold'), text_color=COLOR_TEXT_DIM).pack(anchor='w', padx=12, pady=(10, 2))
        self.lbl_health_val = ctk.CTkLabel(self.card_health_sidebar, text='--%', font=('Segoe UI', 22, 'bold'), text_color=COLOR_RAM)
        self.lbl_health_val.pack(anchor='w', padx=12, pady=(0, 2))
        self.lbl_health_status = ctk.CTkLabel(self.card_health_sidebar, text='Evaluando...', font=('Segoe UI', 10, 'bold'), text_color=theme_color('#f8fafc'))
        self.lbl_health_status.pack(anchor='w', padx=12, pady=(0, 10))
        self.btn_overlay = ctk.CTkButton(self.sidebar, text='Overlay In-Game', fg_color='transparent', hover_color=theme_color('#14253b'), text_color=theme_color('#f4f7fb'), font=('Segoe UI', 11, 'bold'), height=34, corner_radius=8, command=self.open_overlay_config_window)
        self.btn_overlay.pack(fill='x', padx=12, pady=(15, 5))
        self.btn_diagnostic = ctk.CTkButton(self.sidebar, text='Iniciar diagnóstico', fg_color='transparent', hover_color=theme_color('#14253b'), text_color=theme_color('#f4f7fb'), font=('Segoe UI', 11, 'bold'), height=34, corner_radius=8, command=self.start_diagnostic_session)
        self.btn_health_center = ctk.CTkButton(self.sidebar, text='Centro de salud', fg_color='transparent', hover_color=theme_color('#14253b'), text_color=theme_color('#f4f7fb'), font=('Segoe UI', 11, 'bold'), height=34, corner_radius=8, command=self.open_health_center)
        self.btn_diagnostic.pack(fill='x', padx=12, pady=5)
        self.btn_pdf = ctk.CTkButton(self.sidebar, text='Reportes', fg_color='transparent', hover_color=theme_color('#14253b'), text_color=theme_color('#66788f'), font=('Segoe UI', 11, 'bold'), height=34, corner_radius=8, command=self.export_pdf_report, state='disabled')
        self.btn_cleanup = ctk.CTkButton(self.sidebar, text='🧹 Limpieza de Sistema', fg_color='#8b5cf6', hover_color='#7c3aed', text_color='#ffffff', font=('Segoe UI', 11, 'bold'), height=34, corner_radius=8, command=self.run_cleanup)
        self.btn_cleanup.pack(fill='x', padx=12, pady=5)
        self.btn_tweaks = ctk.CTkButton(self.sidebar, text='Tweaks Windows 11', fg_color='transparent', hover_color=theme_color('#14253b'), text_color=theme_color('#f4f7fb'), font=('Segoe UI', 11, 'bold'), height=34, corner_radius=8, command=self.open_windows_tweaks)
        self.btn_tweaks.pack(fill='x', padx=12, pady=5)
        self.btn_network = ctk.CTkButton(self.sidebar, text='Red avanzada', fg_color='transparent', hover_color=theme_color('#14253b'), text_color=theme_color('#f4f7fb'), font=('Segoe UI', 11, 'bold'), height=34, corner_radius=8, command=self.open_network_details)
        self.btn_network.pack(fill='x', padx=12, pady=5)
        self.btn_smart_alerts = ctk.CTkButton(self.sidebar, text='🚨 Alertas y Diagnóstico', fg_color='#1d4ed8', hover_color='#1e40af', text_color='#ffffff', font=('Segoe UI', 11, 'bold'), height=34, corner_radius=8, command=self.open_smart_alert_window)
        self.btn_smart_alerts.pack(fill='x', padx=12, pady=5)
        self.btn_alert_history = ctk.CTkButton(self.sidebar, text='🕘 Historial de Alertas', fg_color='#334155', hover_color='#475569', text_color='#ffffff', font=('Segoe UI', 11, 'bold'), height=34, corner_radius=8, command=self.open_alert_history_window)
        self.btn_alert_history.pack(fill='x', padx=12, pady=5)
        self.btn_session_trends = ctk.CTkButton(self.sidebar, text='📈 Tendencias de Sesiones', fg_color='#334155', hover_color='#475569', text_color='#ffffff', font=('Segoe UI', 11, 'bold'), height=34, corner_radius=8, command=self.open_session_trends_window)
        self.btn_session_trends.pack(fill='x', padx=12, pady=5)
        ctk.CTkLabel(self.sidebar, text='[F11] Pantalla Completa\n[Esc] Modo Ventana', font=('Segoe UI', 9), text_color=COLOR_TEXT_DIM, justify='center').pack(side='bottom', pady=12, padx=10)
        self.main_content = ctk.CTkFrame(self, fg_color='transparent')
        self.main_content.grid(row=0, column=1, sticky='nsew', padx=15, pady=15)
        self.frame_meters = ctk.CTkFrame(self.main_content, fg_color='transparent')
        self.frame_meters.pack(fill='x', pady=(0, 10))
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
        self.alert_summary_bar.pack(fill='x', pady=(0, 10))
        self.lbl_alert_summary = ctk.CTkLabel(self.alert_summary_bar, text='MONITOREO INICIANDO', font=('Segoe UI', 11, 'bold'), text_color=COLOR_RAM)
        self.lbl_alert_summary.pack(side='left', padx=12, pady=9)
        self.btn_alert_summary = ctk.CTkButton(self.alert_summary_bar, text='Ver diagnóstico', width=120, height=26, fg_color=theme_color('#1e3a5f'), hover_color=theme_color('#284f7a'), text_color=theme_color('#f8fafc'), font=('Segoe UI', 10, 'bold'), command=self.open_smart_alert_window)
        self.btn_alert_summary.pack(side='right', padx=8, pady=6)
        ctk.CTkLabel(self.main_content, text='UNIDADES DE ALMACENAMIENTO DETECTADAS', font=('Segoe UI', 10, 'bold'), text_color=COLOR_TEXT_DIM).pack(anchor='w', pady=(0, 4))
        self.scroll_disks = ctk.CTkScrollableFrame(self.main_content, fg_color='transparent', height=120)
        self.scroll_disks.pack(fill='x', pady=(0, 10))
        self.disk_widgets = {}
        self.frame_charts = ctk.CTkFrame(self.main_content, fg_color=BG_CARD, border_width=1, border_color=BORDER_COLOR, corner_radius=10)
        self.frame_charts.pack(fill='both', expand=True)
        self.fig = Figure(figsize=(7, 2.0), dpi=85, facecolor=BG_CARD)
        self.ax_cpu = self.fig.add_subplot(131, facecolor=BG_CARD)
        self.ax_ram = self.fig.add_subplot(132, facecolor=BG_CARD)
        self.ax_gpu = self.fig.add_subplot(133, facecolor=BG_CARD)
        self.line_cpu, = self.ax_cpu.plot(list(range(self.max_points)), list(self.cpu_history), color=COLOR_CPU, linewidth=2, animated=True)
        self.line_ram, = self.ax_ram.plot(list(range(self.max_points)), list(self.ram_history), color=COLOR_RAM, linewidth=2, animated=True)
        self.line_gpu, = self.ax_gpu.plot(list(range(self.max_points)), list(self.gpu_history), color=COLOR_GPU, linewidth=2, animated=True)
        self.format_axes(self.ax_cpu, 'Historial CPU (%)')
        self.format_axes(self.ax_ram, 'Historial RAM (%)')
        self.format_axes(self.ax_gpu, 'Historial GPU (%)')
        self.fig.tight_layout()
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.frame_charts)
        self.canvas.get_tk_widget().configure(bg=BG_CARD, highlightthickness=0)
        self.canvas.get_tk_widget().pack(fill='both', expand=True, padx=8, pady=6)
        self.canvas.draw_idle()
        self.background = None
        self.canvas.mpl_connect('draw_event', self.on_draw)
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
        self.telemetry_thread = threading.Thread(target=self.telemetry_loop, daemon=True, name='CorePulse-Telemetry')
        self.telemetry_thread.start()
        self.telemetry_after_id = self.after(250, self.process_pending_telemetry)
        self.chart_after_id = self.after(200, self.update_charts_fast)

    def _schedule_battery_health_refresh(self):
        """Actualiza Battery Health fuera del hilo UI y a baja frecuencia."""
        if not getattr(self, 'is_running', False):
            return
        if not getattr(self, '_battery_health_refresh_running', False):
            self._battery_health_refresh_running = True
            telemetry = copy.deepcopy(getattr(self, 'latest_telemetry', {}) or {})
            def worker():
                try:
                    result = collect_battery_health(telemetry)
                    self.battery_health_cache = result if isinstance(result, dict) else None
                except Exception:
                    self._log_throttled_exception('battery_health_refresh', 'Fallo al actualizar Battery Health')
                finally:
                    self._battery_health_refresh_running = False
            threading.Thread(target=worker, daemon=True, name='CorePulse-BatteryHealth').start()
        try:
            self.after(300000, self._schedule_battery_health_refresh)
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
                self.windows_tweaks_panel.refresh()
                return
            if host is None:
                return
            panel = WindowsTweaksPanel(self, host)
            self.windows_tweaks_panel = panel
            if not commit_internal_page(self, 'tweaks', host, panel):
                self.windows_tweaks_panel = None
        except Exception as exc:
            self.windows_tweaks_panel = None
            abort_internal_page(self, 'tweaks', host)
            cp_error(self, 'Tweaks de Windows 11', f'No se pudo abrir la vista de Tweaks:\n\n{exc}')

    def open_health_center(self):
        """Abre el Centro de Salud avanzado como página interna."""
        if not self.is_running:
            return
        host = None
        try:
            host, reused = activate_internal_page(self, 'health_center')
            if reused and self.health_center_panel is not None:
                self.health_center_panel.refresh()
                return
            if host is None:
                return
            panel = HealthCenterPanel(self, host)
            self.health_center_panel = panel
            if not commit_internal_page(self, 'health_center', host, panel):
                self.health_center_panel = None
        except Exception as exc:
            self.health_center_panel = None
            abort_internal_page(self, 'health_center', host)
            cp_error(self, 'Centro de Salud', f'No se pudo abrir el Centro de Salud:\n\n{exc}')

    def open_network_details(self):
        """Abre Red avanzada como vista interna de CorePulse."""
        if not self.is_running:
            return
        host = None
        try:
            host, reused = activate_internal_page(self, 'network')
            if reused and self.network_detail_panel is not None:
                self.network_detail_panel.refresh()
                return
            if host is None:
                return
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
            self.current_recommendation_pipeline = integrate_current_diagnostic_pipeline(result, copy.deepcopy(self.diagnostic_telemetry_snapshot or {}), copy.deepcopy(self.diagnostic_disks_snapshot or []), output_path=os.path.join('data', 'current_diagnostic_recommendations.json'))
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
                stage = readiness_stage(info)
                detail = f'CorePulse todavía está {stage.lower()}.\nTiempo estimado restante: ~{eta} s.\n\nEl PDF se habilitará automáticamente cuando exista evidencia suficiente.'
            else:
                detail = 'Inicia el diagnóstico rápido de CorePulse.\n\nEn un sistema estable, el informe puede habilitarse desde ~30 segundos. Si CorePulse necesita confirmar una condición, observará más tiempo hasta un máximo de seguridad de 90 segundos.'
            cp_warning(self, 'Informe aún no disponible', detail)
            return
        if not self.is_running or not self.latest_telemetry:
            cp_warning(self, 'Reportes', 'Aún no hay datos de telemetría para exportar.')
            return

        # El usuario elige la carpeta; CorePulse conserva un nombre único y predecible.
        output_dir = ask_pdf_directory(self)
        if not output_dir:
            return
        try:
            output_dir = str(Path(output_dir).expanduser().resolve())
            if not Path(output_dir).is_dir():
                raise RuntimeError('La carpeta seleccionada no existe.')
        except Exception as exc:
            cp_error(self, 'Reportes', f'La carpeta seleccionada no es válida:\n{exc}')
            return
        default_filename = f"Reporte_CorePulse_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        file_path = str(Path(output_dir) / default_filename)

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

        opened = self._open_generated_pdf(file_path)
        self._show_pdf_success(file_path, opened=opened)

    def _show_pdf_success(self, file_path, opened=True):
        if self.is_running:
            extra = '' if opened else '\n\nEl archivo fue guardado, pero Windows no pudo abrirlo automáticamente.'
            cp_info(self, 'Reporte creado', f'El informe PDF fue generado correctamente:\n\n{file_path}{extra}')

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

    def _close_overlay_config_window(self):
        try:
            if self.overlay_config_panel is not None:
                self.overlay_config_panel.destroy()
        except Exception:
            pass
        self.overlay_config_window = None
        self.overlay_config_panel = None
        if getattr(self, '_active_internal_page', None) == 'overlay':
            clear_internal_page(self)

    def open_overlay_config_window(self):
        """Muestra Overlay como página interna; commit síncrono y sin hosts huérfanos."""
        if not self.is_running:
            return
        host = None
        panel = None
        try:
            host, reused = activate_internal_page(self, 'overlay')
            if reused and self.overlay_config_panel is not None:
                widget = self.overlay_config_panel.widget()
                if widget is not None and widget.winfo_exists():
                    widget.lift()
                    return
            self.overlay_config_window = None
            panel = OverlayConfigPanel(host, self)
            widget = panel.widget()
            if widget is not None:
                widget.pack(fill='both', expand=True)
            if not commit_internal_page(self, 'overlay', host, panel):
                raise RuntimeError('La navegación de Overlay fue invalidada antes del commit.')
        except Exception as exc:
            self.overlay_config_window = None
            abort_internal_page(self, 'overlay', host, panel)
            cp_error(self, 'Overlay', f'No se pudo abrir la configuración del overlay.\n\nError: {exc}')

    def toggle_overlay(self):
        if not self.is_running:
            return
        try:
            if self.overlay_window is None or not self.overlay_window.winfo_exists():
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
        ax.set_title(title, color=theme_color('#e2e8f0'), fontsize=8, fontweight='bold', pad=6)
        ax.set_ylim(0, 100)
        ax.set_xlim(0, self.max_points - 1)
        ax.tick_params(colors=COLOR_TEXT_DIM, labelsize=7)
        for spine in ax.spines.values():
            spine.set_color('#1e293b')
        ax.grid(True, color='#1e293b', linestyle='--', linewidth=0.5)

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
        try:
            if self.background is None and (not self.is_resizing):
                self.canvas.draw_idle()
            if self.background is not None and (not self.is_resizing):
                with self.telemetry_lock:
                    cpu_data = list(self.cpu_history)
                    ram_data = list(self.ram_history)
                    gpu_data = list(self.gpu_history)
                x_data = list(range(self.max_points))
                self.line_cpu.set_data(x_data, cpu_data)
                self.line_ram.set_data(x_data, ram_data)
                self.line_gpu.set_data(x_data, gpu_data)
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
            show_storage_details(self, int(disk_index))
        except Exception as exc:
            cp_error(self, 'Almacenamiento', f'No se pudieron abrir los detalles de la unidad:\n{exc}')

    def open_cpu_details(self):
        """Abre la ficha avanzada de la CPU sin detener el monitoreo del Dashboard."""
        host, reused = activate_internal_page(self, 'cpu_details')
        if reused:
            panel = getattr(self, 'cpu_detail_panel', None)
            if panel is not None:
                try:
                    panel.refresh()
                except Exception:
                    logger.exception('No se pudo refrescar la vista avanzada de CPU')
            return
        if host is None:
            return
        loader = None
        try:
            # CPU Advanced Details: cubre el Dashboard de inmediato con una transición limpia.
            # La página CPU se construye debajo y sólo se retira el loader cuando
            # todos sus widgets están listos, evitando el solapamiento visual visto
            # en equipos donde CustomTkinter tarda algunos frames en maquetar.
            loader = ctk.CTkFrame(host, fg_color=theme_color('#06111f'), corner_radius=0)
            loader.place(relx=0, rely=0, relwidth=1, relheight=1)
            loading_box = ctk.CTkFrame(loader, fg_color=theme_color('#0d1828'), border_width=1, border_color=theme_color('#1b3048'), corner_radius=12)
            loading_box.place(relx=0.5, rely=0.46, anchor='center')
            ctk.CTkLabel(
                loading_box,
                text='Cargando información del procesador…',
                font=('Segoe UI', 15, 'bold'),
                text_color=theme_color('#f4f7fb'),
            ).pack(padx=34, pady=(22, 5))
            ctk.CTkLabel(
                loading_box,
                text='Preparando especificaciones y telemetría CPU',
                font=('Segoe UI', 9),
                text_color=theme_color('#7f91a8'),
            ).pack(padx=34, pady=(0, 22))
            host.lift()
            self.update_idletasks()

            panel = CPUDetailPanel(self, host)
            self.cpu_detail_panel = panel
            try:
                loader.destroy()
                loader = None
            except Exception:
                pass
            self.update_idletasks()
            if not commit_internal_page(self, 'cpu_details', host, panel):
                self.cpu_detail_panel = None
        except Exception:
            logger.exception('No se pudo construir la vista avanzada de CPU')
            abort_internal_page(self, 'cpu_details', host)

    def open_ram_details(self):
        """Abre la ficha avanzada de memoria RAM sin detener el monitoreo."""
        host, reused = activate_internal_page(self, 'ram_details')
        if reused:
            panel = getattr(self, 'ram_detail_panel', None)
            if panel is not None:
                try:
                    panel.refresh()
                except Exception:
                    logger.exception('No se pudo refrescar la vista avanzada de RAM')
            return
        if host is None:
            return
        loader = None
        try:
            loader = ctk.CTkFrame(host, fg_color=theme_color('#06111f'), corner_radius=0)
            loader.place(relx=0, rely=0, relwidth=1, relheight=1)
            loading_box = ctk.CTkFrame(loader, fg_color=theme_color('#0d1828'), border_width=1, border_color=theme_color('#1b3048'), corner_radius=12)
            loading_box.place(relx=0.5, rely=0.46, anchor='center')
            ctk.CTkLabel(
                loading_box,
                text='Cargando información de memoria…',
                font=('Segoe UI', 15, 'bold'),
                text_color=theme_color('#f4f7fb'),
            ).pack(padx=34, pady=(22, 5))
            ctk.CTkLabel(
                loading_box,
                text='Preparando módulos, slots y telemetría RAM',
                font=('Segoe UI', 9),
                text_color=theme_color('#7f91a8'),
            ).pack(padx=34, pady=(0, 22))
            host.lift()
            self.update_idletasks()

            panel = RAMDetailPanel(self, host)
            self.ram_detail_panel = panel
            try:
                loader.destroy()
                loader = None
            except Exception:
                pass
            self.update_idletasks()
            if not commit_internal_page(self, 'ram_details', host, panel):
                self.ram_detail_panel = None
        except Exception:
            logger.exception('No se pudo construir la vista avanzada de RAM')
            abort_internal_page(self, 'ram_details', host)

    def open_gpu_details(self):
        """Abre la ficha avanzada multi-GPU sin detener el monitoreo."""
        host, reused = activate_internal_page(self, 'gpu_details')
        if reused:
            panel = getattr(self, 'gpu_detail_panel', None)
            if panel is not None:
                try:
                    panel.refresh()
                except Exception:
                    logger.exception('No se pudo refrescar la vista avanzada de GPU')
            return
        if host is None:
            return
        loader = None
        try:
            loader = ctk.CTkFrame(host, fg_color=theme_color('#06111f'), corner_radius=0)
            loader.place(relx=0, rely=0, relwidth=1, relheight=1)
            loading_box = ctk.CTkFrame(loader, fg_color=theme_color('#0d1828'), border_width=1, border_color=theme_color('#1b3048'), corner_radius=12)
            loading_box.place(relx=0.5, rely=0.46, anchor='center')
            ctk.CTkLabel(
                loading_box,
                text='Cargando información gráfica…',
                font=('Segoe UI', 15, 'bold'),
                text_color=theme_color('#f4f7fb'),
            ).pack(padx=34, pady=(22, 5))
            ctk.CTkLabel(
                loading_box,
                text='Preparando adaptadores, controlador y telemetría GPU',
                font=('Segoe UI', 9),
                text_color=theme_color('#7f91a8'),
            ).pack(padx=34, pady=(0, 22))
            host.lift()
            self.update_idletasks()

            panel = GPUDetailPanel(self, host)
            self.gpu_detail_panel = panel
            try:
                loader.destroy()
                loader = None
            except Exception:
                pass
            self.update_idletasks()
            if not commit_internal_page(self, 'gpu_details', host, panel):
                self.gpu_detail_panel = None
        except Exception:
            logger.exception('No se pudo construir la vista avanzada de GPU')
            abort_internal_page(self, 'gpu_details', host)

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
                    card = ctk.CTkFrame(self.scroll_disks, fg_color=BG_CARD, border_width=1, border_color=BORDER_COLOR, corner_radius=8)
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
                total = device.get('total_space_gb')
                free = device.get('free_space_gb')
                used_percent = device.get('used_space_percent')
                life = device.get('life_percent')
                total = float(total) if total is not None else None
                free = float(free) if free is not None else None
                if used_percent is None and total and (free is not None) and (total > 0):
                    used_percent = (total - free) / total * 100.0
                if used_percent is not None:
                    used_percent = max(0.0, min(100.0, float(used_percent)))
                used_gb = total * used_percent / 100.0 if total is not None and used_percent is not None else None
                mounts_text = ', '.join(mount_points) if len(devices) == 1 and mount_points else 'N/A'
                result.append({'index': idx, 'model': str(model), 'mount_points': mounts_text, 'total_gb': round(total, 2) if total is not None else None, 'health': float(life) if life is not None else None, 'used_percent': round(used_percent, 1) if used_percent is not None else None, 'used_gb': round(used_gb, 2) if used_gb is not None else None, 'used_mb': int(used_gb * 1024) if used_gb is not None else None, 'used_kb': int(used_gb * 1024 * 1024) if used_gb is not None else None, 'temperature_c': device.get('temperature_c'), 'source': device.get('source', 'LibreHardwareMonitor'), 'quality': device.get('quality', 'VALID')})
            except Exception:
                continue
        return result

    # Adquiere telemetría en segundo plano para no bloquear la interfaz.
    def telemetry_loop(self):
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
                        self.thermal_throttling_state = self.thermal_throttling_detector.add_sample(telemetry)
                    except Exception:
                        self._log_throttled_exception('throttling_detector', 'Fallo al evaluar throttling')
                    try:
                        now_hist = time.time()
                        if now_hist - float(getattr(self, '_health_history_last_record', 0.0) or 0.0) >= 60.0:
                            cached_battery = getattr(self, 'battery_health_cache', None)
                            battery_health_value = cached_battery.get('health_percent') if isinstance(cached_battery, dict) else None
                            self.health_history_store.record_snapshot(telemetry, disks, score, ts=now_hist, battery_health_override=battery_health_value)
                            self._health_history_last_record = now_hist
                    except Exception:
                        self._log_throttled_exception('health_history', 'Fallo al persistir historial de salud')
                    if self.diagnostic_session.active:
                        self.diagnostic_session.add_sample(telemetry, disks)
                    with self.telemetry_lock:
                        self.pending_telemetry = telemetry
                        self.pending_disks = list(disks)
                        self.latest_score = score
                        self.cpu_history.append(telemetry['cpu_usage'] if telemetry['cpu_usage'] is not None else float('nan'))
                        self.ram_history.append(telemetry['ram_usage'] if telemetry['ram_usage'] is not None else float('nan'))
                        self.gpu_history.append(telemetry['gpu_usage'] if telemetry['gpu_usage'] is not None else float('nan'))
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
                self.apply_telemetry_to_ui(telemetry, disks)
        except Exception:
            self._log_throttled_exception('telemetry_ui_dispatch', 'Fallo al entregar telemetría a la interfaz')
        if self.is_running:
            self.telemetry_after_id = self.after(250, self.process_pending_telemetry)

    # Presenta solo valores reales o N/A; nunca convierte ausencia de datos en cero.
    def apply_telemetry_to_ui(self, telemetry, disks):
        if not self.is_running or not self.winfo_exists():
            return
        try:
            self.latest_telemetry = telemetry
            try:
                trend_state = self.realtime_agent.get_state() if hasattr(self, 'realtime_agent') else {}
            except Exception:
                trend_state = {}
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
                state = self.realtime_agent.get_state()
                diagnostic = self.diagnostic_explainer.explain_state(state)
                self.smart_alert_panel.render(state, diagnostic)
                return
            self.smart_alert_window = None
            panel = SmartAlertPanel(host)
            widget = panel.widget()
            if widget is not None:
                widget.pack(fill='both', expand=True)
            state = self.realtime_agent.get_state()
            diagnostic = self.diagnostic_explainer.explain_state(state)
            panel.render(state, diagnostic)
            if not commit_internal_page(self, 'alerts', host, panel):
                raise RuntimeError('La navegación de Alertas fue invalidada antes del commit.')
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
        host = None
        panel = None
        try:
            host, reused = activate_internal_page(self, 'history')
            if reused and self.alert_history_panel is not None:
                rows = self.alert_history_store.refresh()
                summary = self.alert_history_store.summary()
                self.alert_history_panel.render(rows, summary)
                return
            self.alert_history_window = None
            panel = AlertHistoryPanel(host)
            widget = panel.widget()
            if widget is not None:
                widget.pack(fill='both', expand=True)
            rows = self.alert_history_store.refresh()
            summary = self.alert_history_store.summary()
            panel.render(rows, summary)
            if not commit_internal_page(self, 'history', host, panel):
                raise RuntimeError('La navegación de Historial fue invalidada antes del commit.')
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
        host = None
        panel = None
        try:
            host, reused = activate_internal_page(self, 'trends')
            if reused and self.session_trends_panel is not None:
                self._refresh_session_trends_ui()
                return
            self.session_trends_window = None
            panel = SessionTrendsPanel(host)
            widget = panel.widget()
            if widget is not None:
                widget.pack(fill='both', expand=True)
            sessions = self.session_trend_collector.load_sessions(limit=10)
            summary = SessionTrendAnalyzer(sessions).summary(limit=10)
            panel.render(sessions, summary)
            if not commit_internal_page(self, 'trends', host, panel):
                raise RuntimeError('La navegación de Tendencias fue invalidada antes del commit.')
        except Exception as exc:
            self.session_trends_window = None
            abort_internal_page(self, 'trends', host, panel)
            cp_error(self, 'Tendencias', f'No se pudo abrir Tendencias:\n\n{exc}')

    def _refresh_session_trends_ui(self):
        if self.session_trends_panel is None:
            return
        try:
            sessions = self.session_trend_collector.load_sessions(limit=10)
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
        if getattr(self, '_shutdown_started', False):
            return
        self._shutdown_started = True
        self.is_running = False
        for attr in ('resize_timer', 'telemetry_after_id', 'chart_after_id', 'diagnostic_after_id', 'agent_after_id'):
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
            shutdown_corepulse_services(agent=getattr(self, 'realtime_agent', None), tray=getattr(self, 'tray_service', None), overlay=getattr(self, 'rtss_overlay_service', None), verbose=False)
        except Exception:
            pass
        try:
            if hasattr(self, 'telemetry_thread') and self.telemetry_thread.is_alive():
                self.telemetry_thread.join(timeout=3.0)
        except Exception:
            pass
        try:
            self._shutdown_thread_result = wait_for_named_threads(names=('CorePulse-Telemetry',), timeout=1.0)
        except Exception:
            self._shutdown_thread_result = {'ok': False}
        try:
            self._shutdown_sensor_result = shutdown_telemetry_provider(join_timeout=2.5, verbose=False)
        except Exception as exc:
            self._shutdown_sensor_result = {'ok': False, 'error': f'{type(exc).__name__}: {exc}'}
        try:
            self.destroy()
        except Exception:
            pass
if __name__ == '__main__':
    app = App()
    app.mainloop()
