import customtkinter as ctk
import threading
import time
import psutil
import os
import platform

from collections import deque
from tkinter import messagebox, filedialog
from datetime import datetime

from PIL import Image

# Parche de compatibilidad para CustomTkinter en Python 3.14 (evita AttributeError en event.widget)
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


# =========================================================
# SISTEMA OPERATIVO
# =========================================================

IS_WINDOWS = platform.system() == "Windows"

if IS_WINDOWS:
    try:
        import pythoncom
    except ImportError:
        pythoncom = None
else:
    pythoncom = None


# =========================================================
# MATPLOTLIB
# =========================================================

import matplotlib

matplotlib.use("TkAgg")

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure


# =========================================================
# CORE
# =========================================================

from core.telemetry import (
    get_system_telemetry,
    get_all_disks_data,
    calculate_preliminary_score
)

from core.report_generator import (
    generate_pdf_report
)

from database.db import (
    init_db,
    save_telemetry_record
)

from gui.overlay import GameOverlay


# =========================================================
# APARIENCIA
# =========================================================

ctk.set_appearance_mode("Dark")

BG_MAIN = "#0b0f19"
BG_CARD = "#151c2c"
BG_SIDEBAR = "#0d1322"
BORDER_COLOR = "#232f48"

COLOR_CPU = "#38bdf8"
COLOR_RAM = "#10b981"
COLOR_GPU = "#a855f7"
COLOR_TEXT_DIM = "#94a3b8"


# =========================================================
# APP PRINCIPAL
# =========================================================

class App(ctk.CTk):

    def __init__(self):
        super().__init__()

        # CONFIGURACIÓN
        self.title("DiagnosticPC - Predictive Analytics Dashboard")
        self.geometry("1000x700")
        self.minsize(850, 600)
        self.resizable(True, True)
        self.configure(fg_color=BG_MAIN)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # ICONO
        icon_path = os.path.join("assets", "app_icon.ico")
        if os.path.exists(icon_path):
            try:
                self.iconbitmap(icon_path)
            except Exception:
                pass

        # FULLSCREEN & RESIZE
        self.is_fullscreen = False
        self.bind("<F11>", self.toggle_fullscreen)
        self.bind("<Escape>", self.exit_fullscreen)

        self.is_resizing = False
        self.resize_timer = None
        self.bind("<Configure>", self.on_window_resize)

        # DATABASE & ESTADO
        init_db()

        self.is_running = True
        self.overlay_window = None

        self.latest_telemetry = None
        self.latest_disks = []
        self.latest_score = 100.0

        self.max_points = 25
        self.cpu_history = deque([0] * self.max_points, maxlen=self.max_points)
        self.ram_history = deque([0] * self.max_points, maxlen=self.max_points)
        self.gpu_history = deque([0] * self.max_points, maxlen=self.max_points)

        self.db_counter = 0

        # THREAD SAFE LOCKS & QUEUES
        self.telemetry_lock = threading.Lock()
        self.pending_telemetry = None
        self.pending_disks = []

        self.telemetry_after_id = None
        self.chart_after_id = None

        # GRID
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # SIDEBAR
        self.sidebar = ctk.CTkFrame(
            self,
            fg_color=BG_SIDEBAR,
            corner_radius=0,
            width=230
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)

        # LOGO
        self.frame_logo = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.frame_logo.pack(anchor="w", padx=15, pady=(20, 2), fill="x")

        logo_img_path = None
        for possible_path in [
            os.path.join("assets", "logo_neon_pulse.png"),
            os.path.join("assets", "logo_shield_health.png"),
            os.path.join("assets", "logo.png")
        ]:
            if os.path.exists(possible_path):
                logo_img_path = possible_path
                break

        if logo_img_path:
            try:
                pil_img = Image.open(logo_img_path)
                self.ctk_logo = ctk.CTkImage(
                    light_image=pil_img,
                    dark_image=pil_img,
                    size=(28, 28)
                )
                self.lbl_logo_icon = ctk.CTkLabel(
                    self.frame_logo,
                    image=self.ctk_logo,
                    text=""
                )
                self.lbl_logo_icon.pack(side="left", padx=(0, 8))
            except Exception:
                pass

        self.lbl_brand = ctk.CTkLabel(
            self.frame_logo,
            text="DiagnosticPC",
            font=("Segoe UI", 18, "bold"),
            text_color="#f8fafc"
        )
        self.lbl_brand.pack(side="left")

        self.lbl_subtitle = ctk.CTkLabel(
            self.sidebar,
            text="Predictive Telemetry Engine",
            font=("Segoe UI", 10),
            text_color=COLOR_TEXT_DIM
        )
        self.lbl_subtitle.pack(anchor="w", padx=15, pady=(0, 15))

        # HEALTH CARD
        self.card_health_sidebar = ctk.CTkFrame(
            self.sidebar,
            fg_color=BG_CARD,
            border_width=1,
            border_color=BORDER_COLOR,
            corner_radius=10
        )
        self.card_health_sidebar.pack(fill="x", padx=12, pady=5)

        ctk.CTkLabel(
            self.card_health_sidebar,
            text="SALUD DEL SISTEMA",
            font=("Segoe UI", 9, "bold"),
            text_color=COLOR_TEXT_DIM
        ).pack(anchor="w", padx=12, pady=(10, 2))

        self.lbl_health_val = ctk.CTkLabel(
            self.card_health_sidebar,
            text="--%",
            font=("Segoe UI", 22, "bold"),
            text_color=COLOR_RAM
        )
        self.lbl_health_val.pack(anchor="w", padx=12, pady=(0, 2))

        self.lbl_health_status = ctk.CTkLabel(
            self.card_health_sidebar,
            text="Evaluando...",
            font=("Segoe UI", 10, "bold"),
            text_color="#f8fafc"
        )
        self.lbl_health_status.pack(anchor="w", padx=12, pady=(0, 10))

        # ACCIONES SIDEBAR
        self.btn_overlay = ctk.CTkButton(
            self.sidebar,
            text="🎮 Overlay In-Game",
            fg_color="#10b981",
            hover_color="#059669",
            text_color="#ffffff",
            font=("Segoe UI", 11, "bold"),
            height=34,
            corner_radius=8,
            command=self.toggle_overlay
        )
        self.btn_overlay.pack(fill="x", padx=12, pady=(15, 5))

        self.btn_pdf = ctk.CTkButton(
            self.sidebar,
            text="📄 Exportar PDF",
            fg_color="#3b82f6",
            hover_color="#2563eb",
            text_color="#ffffff",
            font=("Segoe UI", 11, "bold"),
            height=34,
            corner_radius=8,
            command=self.export_pdf_report
        )
        self.btn_pdf.pack(fill="x", padx=12, pady=5)

        # BOTÓN DE LIMPIEZA
        self.btn_cleanup = ctk.CTkButton(
            self.sidebar,
            text="🧹 Limpieza de Sistema",
            fg_color="#8b5cf6",
            hover_color="#7c3aed",
            text_color="#ffffff",
            font=("Segoe UI", 11, "bold"),
            height=34,
            corner_radius=8,
            command=self.run_cleanup
        )
        self.btn_cleanup.pack(fill="x", padx=12, pady=5)

        # FOOTER
        ctk.CTkLabel(
            self.sidebar,
            text="[F11] Pantalla Completa\n[Esc] Modo Ventana",
            font=("Segoe UI", 9),
            text_color=COLOR_TEXT_DIM,
            justify="center"
        ).pack(side="bottom", pady=12, padx=10)

        # MAIN PANEL
        self.main_content = ctk.CTkFrame(self, fg_color="transparent")
        self.main_content.grid(row=0, column=1, sticky="nsew", padx=15, pady=15)

        # METRIC CARDS
        self.frame_meters = ctk.CTkFrame(self.main_content, fg_color="transparent")
        self.frame_meters.pack(fill="x", pady=(0, 10))

        # CPU
        self.card_cpu = self.create_metric_card(self.frame_meters, "CPU")
        self.card_cpu.pack(side="left", expand=True, fill="both", padx=(0, 5))
        (self.lbl_cpu, self.bar_cpu, self.lbl_cpu_temp, self.lbl_cpu_title) = self.build_card_content(
            self.card_cpu, COLOR_CPU
        )

        # RAM
        self.card_ram = self.create_metric_card(self.frame_meters, "MEMORIA RAM")
        self.card_ram.pack(side="left", expand=True, fill="both", padx=3)
        (self.lbl_ram, self.bar_ram, self.lbl_ram_gb, self.lbl_ram_title) = self.build_card_content(
            self.card_ram, COLOR_RAM
        )

        # GPU
        self.card_gpu = self.create_metric_card(self.frame_meters, "GPU")
        self.card_gpu.pack(side="left", expand=True, fill="both", padx=(5, 0))
        (self.lbl_gpu, self.bar_gpu, self.lbl_gpu_temp, self.lbl_gpu_title) = self.build_card_content(
            self.card_gpu, COLOR_GPU
        )

        # DISKS SECTION
        ctk.CTkLabel(
            self.main_content,
            text="UNIDADES DE ALMACENAMIENTO DETECTADAS",
            font=("Segoe UI", 10, "bold"),
            text_color=COLOR_TEXT_DIM
        ).pack(anchor="w", pady=(0, 4))

        self.scroll_disks = ctk.CTkScrollableFrame(
            self.main_content,
            fg_color="transparent",
            height=120
        )
        self.scroll_disks.pack(fill="x", pady=(0, 10))
        self.disk_widgets = {}

        # CHARTS SECTION
        self.frame_charts = ctk.CTkFrame(
            self.main_content,
            fg_color=BG_CARD,
            border_width=1,
            border_color=BORDER_COLOR,
            corner_radius=10
        )
        self.frame_charts.pack(fill="both", expand=True)

        self.fig = Figure(figsize=(7, 2.0), dpi=85, facecolor=BG_CARD)
        self.ax_cpu = self.fig.add_subplot(131, facecolor=BG_CARD)
        self.ax_ram = self.fig.add_subplot(132, facecolor=BG_CARD)
        self.ax_gpu = self.fig.add_subplot(133, facecolor=BG_CARD)

        self.line_cpu, = self.ax_cpu.plot(list(self.cpu_history), color=COLOR_CPU, linewidth=2)
        self.line_ram, = self.ax_ram.plot(list(self.ram_history), color=COLOR_RAM, linewidth=2)
        self.line_gpu, = self.ax_gpu.plot(list(self.gpu_history), color=COLOR_GPU, linewidth=2)

        self.format_axes(self.ax_cpu, "Historial CPU (%)")
        self.format_axes(self.ax_ram, "Historial RAM (%)")
        self.format_axes(self.ax_gpu, "Historial GPU (%)")

        self.fig.tight_layout()

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.frame_charts)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=6)
        self.canvas.draw()

        self.background = None
        self.canvas.mpl_connect("draw_event", self.on_draw)

        # HILO TELEMETRÍA
        self.telemetry_thread = threading.Thread(
            target=self.telemetry_loop,
            daemon=True,
            name="DiagnosticPC-Telemetry"
        )
        self.telemetry_thread.start()

        # POLLING LOOPS UI
        self.telemetry_after_id = self.after(100, self.process_pending_telemetry)
        self.chart_after_id = self.after(33, self.update_charts_fast)

    # ACCIONES GENERALES
    def run_cleanup(self):
        if not self.is_running:
            return
        messagebox.showinfo(
            "DiagnosticPC - Limpieza",
            "Iniciando tareas de mantenimiento y limpieza de archivos temporales...",
            parent=self
        )

    def on_window_resize(self, event):
        if event.widget != self or not self.is_running:
            return

        self.is_resizing = True
        if self.resize_timer:
            try:
                self.after_cancel(self.resize_timer)
            except Exception:
                pass

        self.resize_timer = self.after(300, self.finish_resizing)

    def finish_resizing(self):
        if not self.is_running:
            return
        self.is_resizing = False
        self.resize_timer = None
        self.background = None
        try:
            self.canvas.draw()
        except Exception:
            pass

    def toggle_fullscreen(self, event=None):
        if not self.is_running:
            return
        self.is_fullscreen = not self.is_fullscreen
        try:
            self.attributes("-fullscreen", self.is_fullscreen)
        except Exception:
            pass

    def exit_fullscreen(self, event=None):
        if not self.is_running or not self.is_fullscreen:
            return
        self.is_fullscreen = False
        try:
            self.attributes("-fullscreen", False)
        except Exception:
            pass

    def export_pdf_report(self):
        if not self.is_running or not self.latest_telemetry:
            messagebox.showwarning("DiagnosticPC", "Aún no hay datos de telemetría para exportar.", parent=self)
            return

        default_filename = f"Reporte_DiagnosticPC_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        file_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("Archivos PDF", "*.pdf")],
            initialfile=default_filename,
            title="Guardar Reporte PDF",
            parent=self
        )

        if not file_path:
            return

        self.btn_pdf.configure(state="disabled", text="⏳ Generando...")

        telemetry_snapshot = self.latest_telemetry.copy()
        disks_snapshot = list(self.latest_disks)
        score_snapshot = self.latest_score

        def generate_thread():
            try:
                generate_pdf_report(
                    telemetry_snapshot,
                    disks_snapshot,
                    score_snapshot,
                    output_path=file_path
                )
                if self.is_running:
                    self.after(0, lambda: self._show_pdf_success(file_path))
            except Exception as e:
                if self.is_running:
                    self.after(0, lambda: self._show_pdf_error(str(e)))
            finally:
                if self.is_running:
                    self.after(0, self._restore_pdf_button)

        threading.Thread(target=generate_thread, daemon=True, name="DiagnosticPC-PDF").start()

    def _show_pdf_success(self, file_path):
        if self.is_running:
            messagebox.showinfo("Reporte Creado", f"El informe PDF fue generado correctamente:\n\n{file_path}", parent=self)

    def _show_pdf_error(self, error):
        if self.is_running:
            messagebox.showerror("Error", f"No se pudo generar el reporte PDF:\n{error}", parent=self)

    def _restore_pdf_button(self):
        if self.is_running:
            self.btn_pdf.configure(state="normal", text="📄 Exportar PDF")

    def toggle_overlay(self):
        if not self.is_running:
            return
        try:
            if self.overlay_window is None or not self.overlay_window.winfo_exists():
                self.overlay_window = GameOverlay(master=self)
                self.btn_overlay.configure(text="❌ Cerrar Overlay", fg_color="#ef4444", hover_color="#dc2626")
                return
            self.close_overlay()
        except Exception as e:
            self.overlay_window = None
            self.btn_overlay.configure(text="🎮 Overlay In-Game", fg_color="#10b981", hover_color="#059669")
            messagebox.showerror("DiagnosticPC - Overlay", f"No se pudo iniciar el overlay.\n\nError: {e}", parent=self)

    def close_overlay(self):
        try:
            if self.overlay_window and self.overlay_window.winfo_exists():
                self.overlay_window.destroy()
        except Exception:
            pass
        finally:
            self.overlay_window = None
            self.btn_overlay.configure(text="🎮 Overlay In-Game", fg_color="#10b981", hover_color="#059669")

    def create_metric_card(self, parent, title):
        card = ctk.CTkFrame(
            parent,
            fg_color=BG_CARD,
            border_width=1,
            border_color=BORDER_COLOR,
            corner_radius=10
        )
        ctk.CTkLabel(
            card,
            text=title,
            font=("Segoe UI", 9, "bold"),
            text_color=COLOR_TEXT_DIM
        ).pack(anchor="w", padx=10, pady=(8, 2))
        return card

    def build_card_content(self, card, color):
        lbl_val = ctk.CTkLabel(card, text="0%", font=("Segoe UI", 16, "bold"), text_color="#f8fafc")
        lbl_val.pack(anchor="w", padx=10, pady=(0, 2))

        bar = ctk.CTkProgressBar(card, height=5, progress_color=color, fg_color="#0f172a")
        bar.set(0)
        bar.pack(fill="x", padx=10, pady=(0, 6))

        lbl_sub = ctk.CTkLabel(card, text="--", font=("Segoe UI", 10, "bold"), text_color=color)
        lbl_sub.pack(anchor="w", padx=10, pady=(0, 6))

        children = card.winfo_children()
        return (lbl_val, bar, lbl_sub, children[0] if children else None)

    def format_axes(self, ax, title):
        ax.set_title(title, color="#e2e8f0", fontsize=8, fontweight="bold", pad=6)
        ax.set_ylim(0, 100)
        ax.set_xlim(0, self.max_points - 1)
        ax.tick_params(colors=COLOR_TEXT_DIM, labelsize=7)
        for spine in ax.spines.values():
            spine.set_color("#1e293b")
        ax.grid(True, color="#1e293b", linestyle="--", linewidth=0.5)

    def on_draw(self, event):
        if self.is_running and event.canvas == self.canvas:
            try:
                self.background = self.canvas.copy_from_bbox(self.fig.bbox)
            except Exception:
                self.background = None

    def update_charts_fast(self):
        if not self.is_running:
            return
        try:
            if self.background is not None and not self.is_resizing:
                with self.telemetry_lock:
                    cpu_data = list(self.cpu_history)
                    ram_data = list(self.ram_history)
                    gpu_data = list(self.gpu_history)

                self.canvas.restore_region(self.background)
                self.line_cpu.set_ydata(cpu_data)
                self.line_ram.set_ydata(ram_data)
                self.line_gpu.set_ydata(gpu_data)

                self.ax_cpu.draw_artist(self.line_cpu)
                self.ax_ram.draw_artist(self.line_ram)
                self.ax_gpu.draw_artist(self.line_gpu)

                self.canvas.blit(self.fig.bbox)
        except Exception:
            self.background = None

        if self.is_running:
            self.chart_after_id = self.after(33, self.update_charts_fast)

    def update_disks_ui(self, disks_data):
        if not self.is_running or not self.winfo_exists():
            return

        active_indexes = {d["index"] for d in disks_data}

        # Eliminar inactivos
        for idx in list(self.disk_widgets.keys()):
            if idx not in active_indexes:
                try:
                    self.disk_widgets[idx]["card"].destroy()
                except Exception:
                    pass
                del self.disk_widgets[idx]

        # Crear o actualizar
        for d in disks_data:
            try:
                idx = d["index"]
                if idx not in self.disk_widgets:
                    card = ctk.CTkFrame(
                        self.scroll_disks,
                        fg_color=BG_CARD,
                        border_width=1,
                        border_color=BORDER_COLOR,
                        corner_radius=8
                    )
                    card.pack(fill="x", pady=3, padx=2)

                    header = ctk.CTkFrame(card, fg_color="transparent")
                    header.pack(fill="x", padx=10, pady=(6, 2))

                    lbl_name = ctk.CTkLabel(header, text="", font=("Segoe UI", 10, "bold"), text_color="#f8fafc")
                    lbl_name.pack(side="left")

                    lbl_badge = ctk.CTkLabel(header, text="", font=("Segoe UI", 10, "bold"))
                    lbl_badge.pack(side="right")

                    lbl_exact = ctk.CTkLabel(card, text="", font=("Segoe UI", 9), text_color=COLOR_CPU)
                    lbl_exact.pack(anchor="w", padx=10, pady=(0, 3))

                    bar = ctk.CTkProgressBar(card, height=5, progress_color=COLOR_CPU, fg_color="#0f172a")
                    bar.set(0)
                    bar.pack(fill="x", padx=10, pady=(0, 6))

                    self.disk_widgets[idx] = {
                        "card": card,
                        "lbl_name": lbl_name,
                        "lbl_badge": lbl_badge,
                        "lbl_exact": lbl_exact,
                        "bar": bar
                    }

                w = self.disk_widgets[idx]
                w["lbl_name"].configure(text=f"💾 Disco {idx}: {d['model']} [{d['mount_points']}] ({d['total_gb']} GB)")

                health = float(d.get("health", 100))
                h_color = COLOR_RAM if health >= 90 else ("#f59e0b" if health >= 70 else "#ef4444")
                w["lbl_badge"].configure(text=f"Salud: {health:.0f}%", text_color=h_color)

                w["lbl_exact"].configure(
                    text=f"Usado: {d['used_percent']}%  -->  {d['used_gb']} GB  |  {d['used_mb']:,} MB  |  {d['used_kb']:,} KB"
                )
                percent = max(0.0, min(100.0, float(d["used_percent"])))
                w["bar"].set(percent / 100.0)

            except Exception:
                continue

    def telemetry_loop(self):
        if IS_WINDOWS and pythoncom:
            try:
                pythoncom.CoInitialize()
            except Exception:
                pass

        try:
            psutil.cpu_percent(interval=None)
            disk_timer = 0
            disks = []

            while self.is_running:
                cycle_start = time.monotonic()
                try:
                    telemetry = get_system_telemetry()

                    if disk_timer % 20 == 0 or not disks:
                        disks = get_all_disks_data()
                    disk_timer += 1

                    score = calculate_preliminary_score(
                        telemetry["cpu_usage"],
                        telemetry["ram_usage"],
                        telemetry["cpu_temp"],
                        telemetry["gpu_temp"],
                        disks
                    )

                    with self.telemetry_lock:
                        self.pending_telemetry = telemetry
                        self.pending_disks = list(disks)
                        self.latest_score = score

                        self.cpu_history.append(telemetry["cpu_usage"])
                        self.ram_history.append(telemetry["ram_usage"])
                        self.gpu_history.append(telemetry["gpu_usage"])

                    self.db_counter += 1
                    if self.db_counter >= 20:
                        save_telemetry_record(
                            telemetry["cpu_usage"],
                            telemetry["ram_usage"],
                            0,
                            0,
                            score
                        )
                        self.db_counter = 0

                except Exception:
                    pass

                elapsed = time.monotonic() - cycle_start
                sleep_time = max(0.05, 0.25 - elapsed)
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
            pass

        if self.is_running:
            self.telemetry_after_id = self.after(100, self.process_pending_telemetry)

    def apply_telemetry_to_ui(self, telemetry, disks):
        if not self.is_running or not self.winfo_exists():
            return

        try:
            self.latest_telemetry = telemetry
            self.latest_disks = list(disks)

            # CPU
            self.lbl_cpu_title.configure(text=f"CPU: {telemetry['cpu_name']}")
            cpu_usage = max(0.0, min(100.0, float(telemetry["cpu_usage"])))
            self.lbl_cpu.configure(text=f"{cpu_usage:.1f}%")
            self.bar_cpu.set(cpu_usage / 100.0)
            self.lbl_cpu_temp.configure(text=f"Temp: {telemetry['cpu_temp']} °C")

            # RAM
            ram_usage = max(0.0, min(100.0, float(telemetry["ram_usage"])))
            self.lbl_ram.configure(text=f"{ram_usage:.1f}%")
            self.bar_ram.set(ram_usage / 100.0)
            self.lbl_ram_gb.configure(text=f"{telemetry['ram_used_gb']} GB / {telemetry['ram_total_gb']} GB")

            # GPU
            self.lbl_gpu_title.configure(text=f"GPU: {telemetry['gpu_name']}")
            gpu_usage = max(0.0, min(100.0, float(telemetry["gpu_usage"])))
            self.lbl_gpu.configure(text=f"{gpu_usage:.1f}%")
            self.bar_gpu.set(gpu_usage / 100.0)
            self.lbl_gpu_temp.configure(text=f"Temp: {telemetry['gpu_temp']} °C")

            # DISKS & HEALTH
            self.update_disks_ui(disks)

            score = calculate_preliminary_score(
                telemetry["cpu_usage"],
                telemetry["ram_usage"],
                telemetry["cpu_temp"],
                telemetry["gpu_temp"],
                disks
            )
            self.latest_score = score
            self.lbl_health_val.configure(text=f"{score:.1f}%")

            if score < 50:
                self.lbl_health_status.configure(text="ESTADO CRÍTICO", text_color="#ef4444")
                self.lbl_health_val.configure(text_color="#ef4444")
            elif score < 70:
                self.lbl_health_status.configure(text="ADVERTENCIA", text_color="#f59e0b")
                self.lbl_health_val.configure(text_color="#f59e0b")
            elif score < 85:
                self.lbl_health_status.configure(text="ESTADO ESTABLE", text_color="#38bdf8")
                self.lbl_health_val.configure(text_color="#38bdf8")
            else:
                self.lbl_health_status.configure(text="ESTADO ÓPTIMO", text_color=COLOR_RAM)
                self.lbl_health_val.configure(text_color=COLOR_RAM)

        except Exception:
            pass

    def on_close(self):
        if not self.is_running:
            return

        self.is_running = False

        if self.resize_timer:
            try:
                self.after_cancel(self.resize_timer)
            except Exception:
                pass

        if self.telemetry_after_id:
            try:
                self.after_cancel(self.telemetry_after_id)
            except Exception:
                pass

        if self.chart_after_id:
            try:
                self.after_cancel(self.chart_after_id)
            except Exception:
                pass

        self.close_overlay()

        try:
            if hasattr(self, "telemetry_thread") and self.telemetry_thread.is_alive():
                self.telemetry_thread.join(timeout=1.0)
        except Exception:
            pass

        try:
            self.destroy()
        except Exception:
            pass


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":
    app = App()
    app.mainloop()