import customtkinter as ctk
import threading
import time
import psutil
import pythoncom
from core.telemetry import get_system_telemetry, get_disk_smart_data, calculate_preliminary_score
from database.db import init_db, save_telemetry_record

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Predictive Diagnostics Software v0.7 - Multi-Thread WMI Fixed")
        self.geometry("800x560")
        self.resizable(False, False)

        init_db()

        # Encabezado Principal
        self.lbl_title = ctk.CTkLabel(
            self, 
            text="Sistema de Mantenimiento Predictivo", 
            font=("Segoe UI", 18, "bold")
        )
        self.lbl_title.pack(pady=15)

        # Tarjeta de Salud Global
        self.card_health = ctk.CTkFrame(self)
        self.card_health.pack(fill="x", padx=20, pady=5)

        self.lbl_health_title = ctk.CTkLabel(
            self.card_health, 
            text="Índice de Salud General del Equipo",
            font=("Segoe UI", 12)
        )
        self.lbl_health_title.pack(anchor="w", padx=15, pady=(10, 0))

        self.lbl_health_val = ctk.CTkLabel(
            self.card_health, 
            text="Calculando...", 
            font=("Segoe UI", 22, "bold"), 
            text_color="#22c55e"
        )
        self.lbl_health_val.pack(anchor="w", padx=15, pady=(0, 10))

        # Contenedor de Métricas en Tiempo Real (CPU / RAM / GPU)
        self.frame_meters = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_meters.pack(fill="x", padx=20, pady=10)

        # 1. Módulo CPU
        self.card_cpu = ctk.CTkFrame(self.frame_meters)
        self.card_cpu.pack(side="left", expand=True, fill="both", padx=3)
        self.lbl_cpu = ctk.CTkLabel(self.card_cpu, text="CPU: 0%", font=("Segoe UI", 12, "bold"))
        self.lbl_cpu.pack(pady=5)
        self.bar_cpu = ctk.CTkProgressBar(self.card_cpu, width=110)
        self.bar_cpu.set(0)
        self.bar_cpu.pack(pady=(0, 5), padx=5)
        self.lbl_cpu_temp = ctk.CTkLabel(self.card_cpu, text="-- °C", font=("Segoe UI", 12, "bold"), text_color="#38bdf8")
        self.lbl_cpu_temp.pack(pady=(0, 5))

        # 2. Módulo RAM
        self.card_ram = ctk.CTkFrame(self.frame_meters)
        self.card_ram.pack(side="left", expand=True, fill="both", padx=3)
        self.lbl_ram = ctk.CTkLabel(self.card_ram, text="RAM: 0%", font=("Segoe UI", 12, "bold"))
        self.lbl_ram.pack(pady=5)
        self.bar_ram = ctk.CTkProgressBar(self.card_ram, width=110)
        self.bar_ram.set(0)
        self.bar_ram.pack(pady=(0, 15), padx=5)

        # 3. Módulo GPU
        self.card_gpu = ctk.CTkFrame(self.frame_meters)
        self.card_gpu.pack(side="left", expand=True, fill="both", padx=3)
        self.lbl_gpu = ctk.CTkLabel(self.card_gpu, text="GPU: 0%", font=("Segoe UI", 12, "bold"))
        self.lbl_gpu.pack(pady=5)
        self.bar_gpu = ctk.CTkProgressBar(self.card_gpu, width=110)
        self.bar_gpu.set(0)
        self.bar_gpu.pack(pady=(0, 5), padx=5)
        self.lbl_gpu_temp = ctk.CTkLabel(self.card_gpu, text="-- °C", font=("Segoe UI", 12, "bold"), text_color="#a855f7")
        self.lbl_gpu_temp.pack(pady=(0, 5))

        # Tarjeta Estilo CrystalDiskInfo para Almacenamiento Real
        self.card_smart = ctk.CTkFrame(self)
        self.card_smart.pack(fill="x", padx=20, pady=10)

        # Cabecera del Disco: Modelo, Capacidad Real y Salud (%)
        self.frame_disk_header = ctk.CTkFrame(self.card_smart, fg_color="transparent")
        self.frame_disk_header.pack(fill="x", padx=15, pady=(10, 5))

        self.lbl_disk_model = ctk.CTkLabel(
            self.frame_disk_header, 
            text="💾 Leyendo Disco...", 
            font=("Segoe UI", 13, "bold")
        )
        self.lbl_disk_model.pack(side="left")

        self.lbl_disk_health_badge = ctk.CTkLabel(
            self.frame_disk_header, 
            text="Salud: --%", 
            font=("Segoe UI", 12, "bold"), 
            text_color="#22c55e"
        )
        self.lbl_disk_health_badge.pack(side="right")

        # Barra de Uso de Almacenamiento
        self.lbl_disk_usage = ctk.CTkLabel(
            self.card_smart, 
            text="Espacio de Almacenamiento Usado: --%", 
            font=("Segoe UI", 11)
        )
        self.lbl_disk_usage.pack(anchor="w", padx=15, pady=(0, 5))

        self.bar_disk = ctk.CTkProgressBar(self.card_smart, width=730)
        self.bar_disk.set(0)
        self.bar_disk.pack(padx=15, pady=(0, 12))

        # Hilo secundario para monitoreo continuo
        self.is_running = True
        self.db_counter = 0
        self.thread = threading.Thread(target=self.telemetry_loop, daemon=True)
        self.thread.start()

    def telemetry_loop(self):
        # Inicializar COM para llamadas WMI dentro de este hilo
        pythoncom.CoInitialize()
        psutil.cpu_percent(interval=None)

        while self.is_running:
            t = get_system_telemetry()
            smart = get_disk_smart_data()

            score = calculate_preliminary_score(
                t["cpu_usage"], t["ram_usage"], t["cpu_temp"], t["gpu_temp"], smart
            )

            # Guardado en SQLite cada ~2 segundos
            self.db_counter += 1
            if self.db_counter >= 20:
                save_telemetry_record(
                    t["cpu_usage"], 
                    t["ram_usage"], 
                    smart.get("smart_5_reallocated", 0), 
                    smart.get("smart_197_pending", 0), 
                    score
                )
                self.db_counter = 0

            # UI Update: CPU, RAM, GPU
            self.lbl_cpu.configure(text=f"CPU: {t['cpu_usage']}%")
            self.bar_cpu.set(t["cpu_usage"] / 100.0)
            self.lbl_cpu_temp.configure(text=f"Temp: {t['cpu_temp']} °C")

            self.lbl_ram.configure(text=f"RAM: {t['ram_usage']}%")
            self.bar_ram.set(t["ram_usage"] / 100.0)

            self.lbl_gpu.configure(text=f"GPU: {t['gpu_usage']}%")
            self.bar_gpu.set(t["gpu_usage"] / 100.0)
            self.lbl_gpu_temp.configure(text=f"Temp: {t['gpu_temp']} °C")

            # UI Update: Almacenamiento
            self.lbl_disk_model.configure(
                text=f"💾 {smart['drive_model']} ({smart['total_gb']} GB)"
            )
            
            health_pct = smart['disk_health']
            health_status = "Bueno" if health_pct >= 90 else ("Atención" if health_pct >= 60 else "Riesgo")
            badge_color = "#22c55e" if health_pct >= 90 else ("#f59e0b" if health_pct >= 60 else "#ef4444")
            
            self.lbl_disk_health_badge.configure(
                text=f"Salud: {health_pct}% [{health_status}]",
                text_color=badge_color
            )

            self.lbl_disk_usage.configure(text=f"Espacio de Almacenamiento Usado: {smart['used_percent']}%")
            self.bar_disk.set(smart['used_percent'] / 100.0)

            # Estado global
            if score < 70:
                self.lbl_health_val.configure(text=f"{score:.1f}% - ADVERTENCIA", text_color="#f59e0b")
            else:
                self.lbl_health_val.configure(text=f"{score:.1f}% - ESTADO ÓPTIMO", text_color="#22c55e")

            time.sleep(0.1)

if __name__ == "__main__":
    app = App()
    app.mainloop()