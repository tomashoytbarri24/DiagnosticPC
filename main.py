import customtkinter as ctk
import threading
import time
import psutil
import pythoncom
from collections import deque

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from core.telemetry import get_system_telemetry, get_disk_smart_data, calculate_preliminary_score
from database.db import init_db, save_telemetry_record

# Configuración Visual Global
ctk.set_appearance_mode("Dark")

# Paleta de Colores "Dark Slate / Neon"
BG_MAIN = "#0b0f19"       # Fondo general
BG_CARD = "#151c2c"       # Fondo de tarjetas
BG_SIDEBAR = "#0d1322"    # Fondo de barra lateral
BORDER_COLOR = "#232f48"  # Bordes sutiles

COLOR_CPU = "#38bdf8"     # Cyan
COLOR_RAM = "#10b981"     # Emerald Green
COLOR_GPU = "#a855f7"     # Purple
COLOR_TEXT_DIM = "#94a3b8"# Texto secundario

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("DiagnosticPC - Predictive Analytics Dashboard")
        self.geometry("1100x680")
        self.resizable(False, False)
        self.configure(fg_color=BG_MAIN)

        init_db()

        # Buffer para las últimas 25 lecturas
        self.max_points = 25
        self.cpu_history = deque([0]*self.max_points, maxlen=self.max_points)
        self.ram_history = deque([0]*self.max_points, maxlen=self.max_points)
        self.gpu_history = deque([0]*self.max_points, maxlen=self.max_points)

        # ----------------------------------------------------
        # 1. LAYOUT PRINCIPAL (Sidebar + Main Content)
        # ----------------------------------------------------
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # BARRA LATERAL (SIDEBAR)
        self.sidebar = ctk.CTkFrame(self, fg_color=BG_SIDEBAR, corner_radius=0, width=240)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)

        # Logo / Título Software
        self.lbl_brand = ctk.CTkLabel(
            self.sidebar, 
            text="⚡ DiagnosticPC", 
            font=("Segoe UI", 20, "bold"),
            text_color="#f8fafc"
        )
        self.lbl_brand.pack(anchor="w", padx=20, pady=(25, 5))

        self.lbl_subtitle = ctk.CTkLabel(
            self.sidebar, 
            text="Predictive Telemetry Engine", 
            font=("Segoe UI", 11),
            text_color=COLOR_TEXT_DIM
        )
        self.lbl_subtitle.pack(anchor="w", padx=20, pady=(0, 25))

        # Tarjeta de Salud Global en Sidebar
        self.card_health_sidebar = ctk.CTkFrame(
            self.sidebar, 
            fg_color=BG_CARD, 
            border_width=1, 
            border_color=BORDER_COLOR,
            corner_radius=12
        )
        self.card_health_sidebar.pack(fill="x", padx=15, pady=10)

        self.lbl_health_title = ctk.CTkLabel(
            self.card_health_sidebar, 
            text="SALUD DEL SISTEMA",
            font=("Segoe UI", 10, "bold"),
            text_color=COLOR_TEXT_DIM
        )
        self.lbl_health_title.pack(anchor="w", padx=15, pady=(12, 2))

        self.lbl_health_val = ctk.CTkLabel(
            self.card_health_sidebar, 
            text="--%", 
            font=("Segoe UI", 24, "bold"), 
            text_color=COLOR_RAM
        )
        self.lbl_health_val.pack(anchor="w", padx=15, pady=(0, 2))

        self.lbl_health_status = ctk.CTkLabel(
            self.card_health_sidebar, 
            text="Evaluando...", 
            font=("Segoe UI", 11, "bold"), 
            text_color="#f8fafc"
        )
        self.lbl_health_status.pack(anchor="w", padx=15, pady=(0, 12))

        # ----------------------------------------------------
        # 2. CONTENIDO PRINCIPAL
        # ----------------------------------------------------
        self.main_content = ctk.CTkFrame(self, fg_color="transparent")
        self.main_content.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)

        # METRICAS RÁPIDAS (CPU, RAM, GPU)
        self.frame_meters = ctk.CTkFrame(self.main_content, fg_color="transparent")
        self.frame_meters.pack(fill="x", pady=(0, 15))

        # CPU Card
        self.card_cpu = self.create_metric_card(self.frame_meters, "PROCESADOR (CPU)", COLOR_CPU)
        self.card_cpu.pack(side="left", expand=True, fill="both", padx=(0, 8))
        self.lbl_cpu, self.bar_cpu, self.lbl_cpu_temp = self.build_card_content(self.card_cpu, COLOR_CPU)

        # RAM Card
        self.card_ram = self.create_metric_card(self.frame_meters, "MEMORIA RAM", COLOR_RAM)
        self.card_ram.pack(side="left", expand=True, fill="both", padx=4)
        self.lbl_ram, self.bar_ram, _ = self.build_card_content(self.card_ram, COLOR_RAM, hide_temp=True)

        # GPU Card
        self.card_gpu = self.create_metric_card(self.frame_meters, "GRÁFICA (GPU)", COLOR_GPU)
        self.card_gpu.pack(side="left", expand=True, fill="both", padx=(8, 0))
        self.lbl_gpu, self.bar_gpu, self.lbl_gpu_temp = self.build_card_content(self.card_gpu, COLOR_GPU)

        # TARJETA DISCO DEDICADA
        self.card_smart = ctk.CTkFrame(
            self.main_content, 
            fg_color=BG_CARD, 
            border_width=1, 
            border_color=BORDER_COLOR, 
            corner_radius=12
        )
        self.card_smart.pack(fill="x", pady=(0, 15))

        self.frame_disk_header = ctk.CTkFrame(self.card_smart, fg_color="transparent")
        self.frame_disk_header.pack(fill="x", padx=15, pady=(10, 4))

        self.lbl_disk_model = ctk.CTkLabel(
            self.frame_disk_header, 
            text="💽 Leyendo Disco Principal...", 
            font=("Segoe UI", 12, "bold"),
            text_color="#f8fafc"
        )
        self.lbl_disk_model.pack(side="left")

        self.lbl_disk_health_badge = ctk.CTkLabel(
            self.frame_disk_header, 
            text="Salud: --%", 
            font=("Segoe UI", 11, "bold"), 
            text_color=COLOR_RAM
        )
        self.lbl_disk_health_badge.pack(side="right")

        self.lbl_disk_usage = ctk.CTkLabel(
            self.card_smart, 
            text="Almacenamiento Usado: --%", 
            font=("Segoe UI", 11),
            text_color=COLOR_TEXT_DIM
        )
        self.lbl_disk_usage.pack(anchor="w", padx=15, pady=(0, 4))

        self.bar_disk = ctk.CTkProgressBar(self.card_smart, height=8, progress_color=COLOR_CPU, fg_color="#0f172a")
        self.bar_disk.set(0)
        self.bar_disk.pack(fill="x", padx=15, pady=(0, 12))

        # CONTENEDOR DE GRÁFICOS
        self.frame_charts = ctk.CTkFrame(
            self.main_content, 
            fg_color=BG_CARD, 
            border_width=1, 
            border_color=BORDER_COLOR, 
            corner_radius=12
        )
        self.frame_charts.pack(fill="both", expand=True)

        # FIGURA MATPLOTLIB ESTILIZADA
        self.fig = Figure(figsize=(8, 2.5), dpi=90, facecolor=BG_CARD)

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
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=8)

        self.background = None
        self.canvas.mpl_connect("draw_event", self.on_draw)

        # Hilo de telemetría y loop de refresco
        self.is_running = True
        self.db_counter = 0

        self.thread = threading.Thread(target=self.telemetry_loop, daemon=True)
        self.thread.start()

        self.update_charts_fast()

    def create_metric_card(self, parent, title, color):
        card = ctk.CTkFrame(parent, fg_color=BG_CARD, border_width=1, border_color=BORDER_COLOR, corner_radius=12)
        lbl_title = ctk.CTkLabel(card, text=title, font=("Segoe UI", 10, "bold"), text_color=COLOR_TEXT_DIM)
        lbl_title.pack(anchor="w", padx=12, pady=(10, 2))
        return card

    def build_card_content(self, card, color, hide_temp=False):
        lbl_val = ctk.CTkLabel(card, text="0%", font=("Segoe UI", 18, "bold"), text_color="#f8fafc")
        lbl_val.pack(anchor="w", padx=12, pady=(0, 4))

        bar = ctk.CTkProgressBar(card, height=6, progress_color=color, fg_color="#0f172a")
        bar.set(0)
        bar.pack(fill="x", padx=12, pady=(0, 8))

        lbl_temp = None
        if not hide_temp:
            lbl_temp = ctk.CTkLabel(card, text="-- °C", font=("Segoe UI", 11, "bold"), text_color=color)
            lbl_temp.pack(anchor="w", padx=12, pady=(0, 8))

        return lbl_val, bar, lbl_temp

    def format_axes(self, ax, title):
        ax.set_title(title, color="#e2e8f0", fontsize=9, fontweight="bold", pad=8)
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
        if self.is_running and self.background is not None:
            self.canvas.restore_region(self.background)

            self.line_cpu.set_ydata(list(self.cpu_history))
            self.line_ram.set_ydata(list(self.ram_history))
            self.line_gpu.set_ydata(list(self.gpu_history))

            self.ax_cpu.draw_artist(self.line_cpu)
            self.ax_ram.draw_artist(self.line_ram)
            self.ax_gpu.draw_artist(self.line_gpu)

            self.canvas.blit(self.fig.bbox)

        if self.is_running:
            self.after(33, self.update_charts_fast)

    def telemetry_loop(self):
        pythoncom.CoInitialize()
        psutil.cpu_percent(interval=None)

        while self.is_running:
            t = get_system_telemetry()
            smart = get_disk_smart_data()

            score = calculate_preliminary_score(
                t["cpu_usage"], t["ram_usage"], t["cpu_temp"], t["gpu_temp"], smart
            )

            self.cpu_history.append(t["cpu_usage"])
            self.ram_history.append(t["ram_usage"])
            self.gpu_history.append(t["gpu_usage"])

            self.db_counter += 1
            if self.db_counter >= 15:
                save_telemetry_record(
                    t["cpu_usage"], 
                    t["ram_usage"], 
                    smart.get("smart_5_reallocated", 0), 
                    smart.get("smart_197_pending", 0), 
                    score
                )
                self.db_counter = 0

            # Actualizar Interfaz
            self.lbl_cpu.configure(text=f"{t['cpu_usage']}%")
            self.bar_cpu.set(t["cpu_usage"] / 100.0)
            self.lbl_cpu_temp.configure(text=f"Temp: {t['cpu_temp']} °C")

            self.lbl_ram.configure(text=f"{t['ram_usage']}%")
            self.bar_ram.set(t["ram_usage"] / 100.0)

            self.lbl_gpu.configure(text=f"{t['gpu_usage']}%")
            self.bar_gpu.set(t["gpu_usage"] / 100.0)
            self.lbl_gpu_temp.configure(text=f"Temp: {t['gpu_temp']} °C")

            self.lbl_disk_model.configure(
                text=f"💽 {smart['drive_model']} ({smart['total_gb']} GB)"
            )
            
            health_pct = smart['disk_health']
            health_status = "Bueno" if health_pct >= 90 else ("Atención" if health_pct >= 60 else "Riesgo")
            badge_color = COLOR_RAM if health_pct >= 90 else ("#f59e0b" if health_pct >= 60 else "#ef4444")
            
            self.lbl_disk_health_badge.configure(
                text=f"Salud: {health_pct}% [{health_status}]",
                text_color=badge_color
            )

            self.lbl_disk_usage.configure(text=f"Almacenamiento Usado: {smart['used_percent']}%")
            self.bar_disk.set(smart['used_percent'] / 100.0)

            self.lbl_health_val.configure(text=f"{score:.1f}%")
            if score < 70:
                self.lbl_health_status.configure(text="ADVERTENCIA DE SALUD", text_color="#f59e0b")
                self.lbl_health_val.configure(text_color="#f59e0b")
            else:
                self.lbl_health_status.configure(text="ESTADO ÓPTIMO", text_color=COLOR_RAM)
                self.lbl_health_val.configure(text_color=COLOR_RAM)

            time.sleep(0.25)

if __name__ == "__main__":
    app = App()
    app.mainloop()