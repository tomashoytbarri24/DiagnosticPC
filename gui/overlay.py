import customtkinter as ctk
import ctypes
import threading
import time
from core.telemetry import get_system_telemetry, get_all_disks_data

class GameOverlay(ctk.CTkToplevel):
    def __init__(self, master=None):
        super().__init__(master)

        # 1. Configuración de ventana sin bordes
        self.overrideredirect(True)
        self.attributes("-topmost", True)

        # Transparencia total del fondo (remueve bordes negros exteriores)
        self.attributes("-transparentcolor", "black")
        self.configure(fg_color="black")

        # Posición inicial y tamaño
        self.geometry("260x130+25+25")

        # Variables para mover con el ratón (Drag & Drop)
        self._offsetx = 0
        self._offsety = 0

        # Cache de datos para evitar lag en la interfaz
        self.latest_text = "⚡ Cargando Overlay..."
        self.is_running = True

        # 2. UI - Tarjeta Gamer Neón
        self.card = ctk.CTkFrame(
            self,
            fg_color="#0d1322",
            border_width=2,
            border_color="#00FFCC",
            corner_radius=10
        )
        self.card.pack(fill="both", expand=True, padx=2, pady=2)

        self.lbl_telemetry = ctk.CTkLabel(
            self.card,
            text=self.latest_text,
            font=("Consolas", 12, "bold"),
            text_color="#00FFCC",
            justify="left"
        )
        self.lbl_telemetry.pack(padx=12, pady=10, fill="both", expand=True)

        # 3. Eventos del ratón para arrastrar la ventana en pantalla
        self.card.bind("<ButtonPress-1>", self.start_move)
        self.card.bind("<B1-Motion>", self.do_move)
        self.lbl_telemetry.bind("<ButtonPress-1>", self.start_move)
        self.lbl_telemetry.bind("<B1-Motion>", self.do_move)

        # 4. Forzar permanencia al frente con Win32 API
        self.after(200, self.force_topmost_windows_native)

        # 5. Hilo en segundo plano para telemetría (Cero Latencia / Cero Lag)
        self.thread = threading.Thread(target=self._async_telemetry_reader, daemon=True)
        self.thread.start()

        # 6. Bucle ultra fluido de actualización visual
        self.update_ui_loop()

    def start_move(self, event):
        """Guarda las coordenadas iniciales donde se hizo clic."""
        self._offsetx = event.x
        self._offsety = event.y

    def do_move(self, event):
        """Desplaza la ventana siguiendo el puntero del ratón."""
        x = self.winfo_pointerx() - self._offsetx
        y = self.winfo_pointery() - self._offsety
        self.geometry(f"+{x}+{y}")

    def force_topmost_windows_native(self):
        """Aplica atributos avanzados a nivel de Win32 API para maximizar la visibilidad sobre juegos."""
        try:
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            if hwnd == 0:
                hwnd = self.winfo_id()

            GWL_EXSTYLE = -20
            WS_EX_TOPMOST = 0x00000008
            WS_EX_TOOLWINDOW = 0x00000080  # Evita que se oculte al minimizar y fuerza prioridad
            
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_SHOWWINDOW = 0x0040
            HWND_TOPMOST = -1

            # Aplicar los estilos extendidos de la API de Windows
            current_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, current_style | WS_EX_TOPMOST | WS_EX_TOOLWINDOW)

            # Posicionar por encima de todas las capas de ventanas
            ctypes.windll.user32.SetWindowPos(
                hwnd, HWND_TOPMOST, 0, 0, 0, 0, 
                SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW
            )
        except Exception as e:
            print(f"Error fijando Z-Order avanzado de Windows: {e}")

    def _async_telemetry_reader(self):
        """Hilo secundario para no congelar la GUI durante la lectura de sensores."""
        while self.is_running:
            try:
                telemetry = get_system_telemetry()
                disks = get_all_disks_data()
                disk_health = disks[0]["health"] if disks else 100

                self.latest_text = (
                    f"⚡ DIAGNOSTIC PC OVERLAY\n"
                    f"----------------------------\n"
                    f"CPU  : {telemetry['cpu_usage']:>5.1f}% | {telemetry['cpu_temp']}°C\n"
                    f"RAM  : {telemetry['ram_usage']:>5.1f}% ({telemetry['ram_used_gb']}/{telemetry['ram_total_gb']} GB)\n"
                    f"GPU  : {telemetry['gpu_usage']:>5.1f}% | {telemetry['gpu_temp']}°C\n"
                    f"SSD  : Salud {disk_health}%"
                )
            except Exception as e:
                pass
            time.sleep(0.5)

    def update_ui_loop(self):
        """Refresca la UI sin bloqueos de rendimiento."""
        if self.winfo_exists():
            self.lbl_telemetry.configure(text=self.latest_text)
            self.after(100, self.update_ui_loop)

    def destroy(self):
        self.is_running = False
        super().destroy()