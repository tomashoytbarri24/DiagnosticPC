import customtkinter as ctk
import threading
import time
import psutil
import pythoncom
import os
from collections import deque
from tkinter import messagebox, filedialog
from datetime import datetime
from PIL import Image

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from core.telemetry import get_system_telemetry, get_all_disks_data, calculate_preliminary_score
from core.report_generator import generate_pdf_report
from database.db import init_db, save_telemetry_record
from gui.overlay import GameOverlay

ctk.set_appearance_mode("Dark")

BG_MAIN = "#0b0f19"       
BG_CARD = "#151c2c"       
BG_SIDEBAR = "#0d1322"    
BORDER_COLOR = "#232f48"  

COLOR_CPU = "#38bdf8"     
COLOR_RAM = "#10b981"     
COLOR_GPU = "#a855f7"     
COLOR_TEXT_DIM = "#94a3b8"

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("DiagnosticPC - Predictive Analytics Dashboard")
        self.geometry("1000x700")
        self.resizable(True, True)
        self.configure(fg_color=BG_MAIN)

        icon_path = os.path.join("assets", "app_icon.ico")
        if os.path.exists(icon_path):
            try:
                self.iconbitmap(icon_path)
            except Exception:
                pass

        self.is_fullscreen = False
        self.bind("<F11>", self.toggle_fullscreen)
        self.bind("<Escape>", self.exit_fullscreen)

        # Anti-lag estricto al redimensionar con el mouse
        self.is_resizing = False
        self.resize_timer = None
        self.bind("<Configure>", self.on_window_resize)

        init_db()

        self.overlay_window = None
        self.latest_telemetry = None
        self.latest_disks = []
        self.latest_score = 100.0

        self.max_points = 25
        self.cpu_history = deque([0]*self.max_points, maxlen=self.max_points)
        self.ram_history = deque([0]*self.max_points, maxlen=self.max_points)
        self.gpu_history = deque([0]*self.max_points, maxlen=self.max_points)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # SIDEBAR
        self.sidebar = ctk.CTkFrame(self, fg_color=BG_SIDEBAR, corner_radius=0, width=230)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)

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
                self.ctk_logo = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(28, 28))
                self.lbl_logo_icon = ctk.CTkLabel(self.frame_logo, image=self.ctk_logo, text="")
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

        self.card_health_sidebar = ctk.CTkFrame(
            self.sidebar,
            fg_color=BG_CARD,
            border_width=1,
            border_color=BORDER_COLOR,
            corner_radius=10
        )
        self.card_health_sidebar.pack(fill="x", padx=12, pady=5)

        self.lbl_health_title = ctk.CTkLabel(
            self.card_health_sidebar,
            text="SALUD DEL SISTEMA",
            font=("Segoe UI", 9, "bold"),
            text_color=COLOR_TEXT_DIM
        )
        self.lbl_health_title.pack(anchor="w", padx=12, pady=(10, 2))

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
        self.btn_pdf.pack(fill="x", padx=12, pady=(5, 0))

        self.lbl_footer = ctk.CTkLabel(
            self.sidebar,
            text="[F11] Pantalla Completa\n[Esc] Modo Ventana",
            font=("Segoe UI", 9),
            text_color=COLOR_TEXT_DIM,
            justify="center"
        )
        self.lbl_footer.pack(side="bottom", pady=12, padx=10)

        # MAIN CONTENT
        self.main_content = ctk.CTkFrame(self, fg_color="transparent")
        self.main_content.grid(row=0, column=1, sticky="nsew", padx=15, pady=15)

        self.frame_meters = ctk.CTkFrame(self.main_content, fg_color="transparent")
        self.frame_meters.pack(fill="x", pady=(0, 10))

        self.card_cpu = self.create_metric_card(self.frame_meters, "CPU", COLOR_CPU)
        self.card_cpu.pack(side="left", expand=True, fill="both", padx=(0, 5))
        self.lbl_cpu, self.bar_cpu, self.lbl_cpu_temp = self.build_card_content(self.card_cpu, COLOR_CPU)

        self.card_ram = self.create_metric_card(self.frame_meters, "MEMORIA RAM", COLOR_RAM)
        self.card_ram.pack(side="left", expand=True, fill="both", padx=3)
        self.lbl_ram, self.bar_ram, self.lbl_ram_gb = self.build_card_content(self.card_ram, COLOR_RAM, hide_sublabel=False)

        self.card_gpu = self.create_metric_card(self.frame_meters, "GPU", COLOR_GPU)
        self.card_gpu.pack(side="left", expand=True, fill="both", padx=(5, 0))
        self.lbl_gpu, self.bar_gpu, self.lbl_gpu_temp = self.build_card_content(self.card_gpu, COLOR_GPU)

        self.lbl_disks_header = ctk.CTkLabel(
            self.main_content,
            text="UNIDADES DE ALMACENAMIENTO DETECTADAS",
            font=("Segoe UI", 10, "bold"),
            text_color=COLOR_TEXT_DIM
        )
        self.lbl_disks_header.pack(anchor="w", pady=(0, 4))

        self.scroll_disks = ctk.CTkScrollableFrame(
            self.main_content,
            fg_color="transparent",
            height=120
        )
        self.scroll_disks.pack(fill="x", pady=(0, 10))
        self.disk_widgets = {}

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

        self.line_cpu, = self.ax_cpu.plot(list(self.cpu_history), color=COLOR_CPU, linewidth=2, animated=True)
        self.line_ram, = self.ax_ram.plot(list(self.ram_history), color=COLOR_RAM, linewidth=2, animated=True)
        self.line_gpu, = self.ax_gpu.plot(list(self.gpu_history), color=COLOR_GPU, linewidth=2, animated=True)

        self.format_axes(self.ax_cpu, "Historial CPU (%)")
        self.format_axes(self.ax_ram, "Historial RAM (%)")
        self.format_axes(self.ax_gpu, "Historial GPU (%)")

        self.fig.tight_layout()

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.frame_charts)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=6)

        self.background = None
        self.canvas.mpl_connect("draw_event", self.on_draw)

        self.is_running = True
        self.db_counter = 0

        self.thread = threading.Thread(target=self.telemetry_loop, daemon=True)
        self.thread.start()

        self.update_charts_fast()

    def on_window_resize(self, event):
        if event.widget == self:
            self.is_resizing = True
            if self.resize_timer:
                self.after_cancel(self.resize_timer)
            # Pausa el renderizado 300ms hasta soltar el borde
            self.resize_timer = self.after(300, self.finish_resizing)

    def finish_resizing(self):
        self.is_resizing = False
        self.background = None

    def toggle_fullscreen(self, event=None):
        self.is_fullscreen = not self.is_fullscreen
        self.attributes("-fullscreen", self.is_fullscreen)

    def exit_fullscreen(self, event=None):
        if self.is_fullscreen:
            self.is_fullscreen = False
            self.attributes("-fullscreen", False)

    def export_pdf_report(self):
        if not self.latest_telemetry:
            messagebox.showwarning("DiagnosticPC", "Aún no hay datos de telemetría para exportar.")
            return

        default_filename = f"Reporte_DiagnosticPC_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        file_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("Archivos PDF", "*.pdf")],
            initialfile=default_filename,
            title="Guardar Reporte PDF"
        )

        if file_path:
            try:
                generate_pdf_report(
                    self.latest_telemetry,
                    self.latest_disks,
                    self.latest_score,
                    output_path=file_path
                )
                messagebox.showinfo("Reporte Creado", f"El archivo fue guardado exitosamente en:\n{file_path}")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo generar el reporte PDF:\n{e}")

    def toggle_overlay(self):
        if self.overlay_window is None or not self.overlay_window.winfo_exists():
            self.overlay_window = GameOverlay(master=self)
            self.btn_overlay.configure(text="❌ Cerrar Overlay", fg_color="#ef4444", hover_color="#dc2626")
        else:
            self.overlay_window.destroy()
            self.overlay_window = None
            self.btn_overlay.configure(text="🎮 Overlay In-Game", fg_color="#10b981", hover_color="#059669")

    def create_metric_card(self, parent, title, color):
        card = ctk.CTkFrame(parent, fg_color=BG_CARD, border_width=1, border_color=BORDER_COLOR, corner_radius=10)
        lbl_title = ctk.CTkLabel(card, text=title, font=("Segoe UI", 9, "bold"), text_color=COLOR_TEXT_DIM)
        lbl_title.pack(anchor="w", padx=10, pady=(8, 2))
        return card

    def build_card_content(self, card, color, hide_sublabel=False):
        lbl_val = ctk.CTkLabel(card, text="0%", font=("Segoe UI", 16, "bold"), text_color="#f8fafc")
        lbl_val.pack(anchor="w", padx=10, pady=(0, 2))

        bar = ctk.CTkProgressBar(card, height=5, progress_color=color, fg_color="#0f172a")
        bar.set(0)
        bar.pack(fill="x", padx=10, pady=(0, 6))

        lbl_sub = None
        if not hide_sublabel:
            lbl_sub = ctk.CTkLabel(card, text="--", font=("Segoe UI", 10, "bold"), text_color=color)
            lbl_sub.pack(anchor="w", padx=10, pady=(0, 6))

        return lbl_val, bar, lbl_sub

    def format_axes(self, ax, title):
        ax.set_title(title, color="#e2e8f0", fontsize=8, fontweight="bold", pad=6)
        ax.set_ylim(0, 100)
        ax.set_xlim(0, self.max_points - 1)
        ax.tick_params(colors=COLOR_TEXT_DIM, labelsize=7)
        for spine in ax.spines.values():
            spine.set_color("#1e293b")
        ax.grid(True, color="#1e293b", linestyle="--", linewidth=0.5)

    def on_draw(self, event):
        if event.canvas == self.canvas:
            self.background = self.canvas.copy_from_bbox(self.fig.bbox)

    def update_charts_fast(self):
        if self.is_running and self.background is not None and not self.is_resizing:
            try:
                self.canvas.restore_region(self.background)

                self.line_cpu.set_ydata(list(self.cpu_history))
                self.line_ram.set_ydata(list(self.ram_history))
                self.line_gpu.set_ydata(list(self.gpu_history))

                self.ax_cpu.draw_artist(self.line_cpu)
                self.ax_ram.draw_artist(self.line_ram)
                self.ax_gpu.draw_artist(self.line_gpu)

                self.canvas.blit(self.fig.bbox)
            except Exception:
                pass

        if self.is_running:
            self.after(33, self.update_charts_fast)

    def update_disks_ui(self, disks_data):
        for d in disks_data:
            idx = d["index"]

            if idx not in self.disk_widgets:
                card = ctk.CTkFrame(self.scroll_disks, fg_color=BG_CARD, border_width=1, border_color=BORDER_COLOR, corner_radius=8)
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

            health = d["health"]
            h_color = COLOR_RAM if health >= 90 else ("#f59e0b" if health >= 70 else "#ef4444")
            w["lbl_badge"].configure(text=f"Salud: {health}%", text_color=h_color)

            w["lbl_exact"].configure(
                text=f"Usado: {d['used_percent']}%  -->  {d['used_gb']} GB  |  {d['used_mb']:,} MB  |  {d['used_kb']:,} KB"
            )
            w["bar"].set(d["used_percent"] / 100.0)

    def telemetry_loop(self):
        pythoncom.CoInitialize()
        psutil.cpu_percent(interval=None)

        disk_timer = 0
        disks = []

        while self.is_running:
            t = get_system_telemetry()

            if disk_timer % 20 == 0 or not disks:
                disks = get_all_disks_data()
            disk_timer += 1

            score = calculate_preliminary_score(
                t["cpu_usage"], t["ram_usage"], t["cpu_temp"], t["gpu_temp"], disks
            )

            self.latest_telemetry = t
            self.latest_disks = disks
            self.latest_score = score

            self.cpu_history.append(t["cpu_usage"])
            self.ram_history.append(t["ram_usage"])
            self.gpu_history.append(t["gpu_usage"])

            self.db_counter += 1
            if self.db_counter >= 20:
                save_telemetry_record(
                    t["cpu_usage"],
                    t["ram_usage"],
                    0,
                    0,
                    score
                )
                self.db_counter = 0

            # Actualización UI con nombres exactos de Hardware
            self.card_cpu.winfo_children()[0].configure(text=f"CPU: {t['cpu_name']}")
            self.lbl_cpu.configure(text=f"{t['cpu_usage']}%")
            self.bar_cpu.set(t["cpu_usage"] / 100.0)
            self.lbl_cpu_temp.configure(text=f"Temp: {t['cpu_temp']} °C")

            self.lbl_ram.configure(text=f"{t['ram_usage']}%")
            self.bar_ram.set(t["ram_usage"] / 100.0)
            self.lbl_ram_gb.configure(text=f"{t['ram_used_gb']} GB / {t['ram_total_gb']} GB")

            self.card_gpu.winfo_children()[0].configure(text=f"GPU: {t['gpu_name']}")
            self.lbl_gpu.configure(text=f"{t['gpu_usage']}%")
            self.bar_gpu.set(t["gpu_usage"] / 100.0)
            self.lbl_gpu_temp.configure(text=f"Temp: {t['gpu_temp']} °C")

            self.update_disks_ui(disks)

            self.lbl_health_val.configure(text=f"{score:.1f}%")
            if score < 70:
                self.lbl_health_status.configure(text="ADVERTENCIA", text_color="#f59e0b")
                self.lbl_health_val.configure(text_color="#f59e0b")
            else:
                self.lbl_health_status.configure(text="ESTADO ÓPTIMO", text_color=COLOR_RAM)
                self.lbl_health_val.configure(text_color=COLOR_RAM)

            time.sleep(0.25)

if __name__ == "__main__":
    app = App()
    app.mainloop()
