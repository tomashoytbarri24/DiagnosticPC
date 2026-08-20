import sys
import os
import platform
import tkinter as tk
import threading
import time
from core.telemetry import get_system_telemetry, get_all_disks_data

IS_WINDOWS = platform.system() == "Windows"

if IS_WINDOWS:
    import ctypes
    import ctypes.wintypes


# ==============================================================================
# MEDIDOR MULTIPLATAFORMA DE FPS / RENDER
# ==============================================================================
class RealTimeFPSCounter:
    def __init__(self):
        self.frame_count = 0
        self.current_fps = 60  # Valor por defecto/simulado si no hay API de bajo nivel
        self.last_time = time.time()
        self.is_running = True

        self.dwmapi = None
        if IS_WINDOWS:
            try:
                self.dwmapi = ctypes.windll.dwmapi
            except Exception:
                self.dwmapi = None

        self.thread = threading.Thread(target=self._tracker_loop, daemon=True)
        self.thread.start()

    def _get_kernel_presents(self):
        """Consulta el contador acumulativo real de cuadros si se ejecuta en Windows."""
        if not IS_WINDOWS or not self.dwmapi:
            return None

        try:
            class UNSIGNED_RATIO(ctypes.Structure):
                _fields_ = [("uiNumerator", ctypes.c_uint32), ("uiDenominator", ctypes.c_uint32)]

            class DWM_TIMING_INFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", ctypes.c_uint32),
                    ("rateRefresh", UNSIGNED_RATIO),
                    ("qpcRefreshPeriod", ctypes.c_uint64),
                    ("rateCompose", UNSIGNED_RATIO),
                    ("qpcInsert", ctypes.c_uint64),
                    ("cFrame", ctypes.c_uint64),
                    ("cDXBuffer", ctypes.c_uint32),
                    ("qpcCompose", ctypes.c_uint64),
                    ("cFrameSubmitted", ctypes.c_uint64),
                    ("cDXBufferSubmitted", ctypes.c_uint32),
                    ("cFramePended", ctypes.c_uint64),
                    ("cDXBufferPended", ctypes.c_uint32),
                    ("cFramesDisplayed", ctypes.c_uint64),
                    ("cDXBuffersDisplayed", ctypes.c_uint32),
                    ("cFramesDropped", ctypes.c_uint64),
                    ("cFramesMissed", ctypes.c_uint64),
                ]

            info = DWM_TIMING_INFO()
            info.cbSize = ctypes.sizeof(DWM_TIMING_INFO)

            if self.dwmapi.DwmGetCompositionTimingInfo(0, ctypes.byref(info)) == 0:
                if info.cFrameSubmitted > 0:
                    return info.cFrameSubmitted
                elif info.cFramesDisplayed > 0:
                    return info.cFramesDisplayed
                elif info.cFrame > 0:
                    return info.cFrame
        except Exception:
            pass
        return None

    def _tracker_loop(self):
        last_frames = self._get_kernel_presents()
        last_time = time.perf_counter()

        while self.is_running:
            time.sleep(0.25)
            now = time.perf_counter()
            current_frames = self._get_kernel_presents()

            if current_frames is not None and last_frames is not None:
                delta_frames = current_frames - last_frames
                delta_time = now - last_time

                if delta_time > 0 and delta_frames >= 0:
                    calculated_fps = int(delta_frames / delta_time)
                    if 0 <= calculated_fps <= 360:
                        self.current_fps = calculated_fps
            else:
                # Si estamos en Linux / macOS donde no hay DWM Present API
                self.current_fps = "N/A"

            last_frames = current_frames
            last_time = now

    def stop(self):
        self.is_running = False


# ==============================================================================
# OVERLAY MULTIPLATAFORMA EN TIEMPO REAL
# ==============================================================================
class GameOverlay(tk.Toplevel):
    def __init__(self, master=None):
        super().__init__(master)

        self.overrideredirect(True)
        self.TRANS_COLOR = "#000001"
        self.configure(bg=self.TRANS_COLOR)
        self.wm_attributes("-topmost", True)

        if IS_WINDOWS:
            try:
                self.wm_attributes("-transparentcolor", self.TRANS_COLOR)
            except Exception:
                pass
        else:
            self.attributes("-alpha", 0.88)

        self.geometry("270x150+30+30")

        self._offsetx = 0
        self._offsety = 0
        self.latest_text = "⚡ Cargando Overlay..."
        self.is_running = True

        self.fps_tracker = RealTimeFPSCounter()

        # Marco Principal
        self.card = tk.Frame(
            self,
            bg="#0d1322",
            highlightbackground="#00FFCC",
            highlightthickness=2,
            bd=0
        )
        self.card.pack(fill="both", expand=True, padx=2, pady=2)

        self.lbl_telemetry = tk.Label(
            self.card,
            text=self.latest_text,
            font=("Consolas", 10, "bold"),
            fg="#00FFCC",
            bg="#0d1322",
            justify="left"
        )
        self.lbl_telemetry.pack(padx=8, pady=6, fill="both", expand=True)

        # Mover ventana arrastrando con mouse
        self.card.bind("<ButtonPress-1>", self.start_move)
        self.card.bind("<B1-Motion>", self.do_move)
        self.lbl_telemetry.bind("<ButtonPress-1>", self.start_move)
        self.lbl_telemetry.bind("<B1-Motion>", self.do_move)

        if IS_WINDOWS:
            try:
                self.hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
                if self.hwnd == 0:
                    self.hwnd = self.winfo_id()
                self._apply_initial_win32_styles()
            except Exception:
                self.hwnd = None
        else:
            self.hwnd = None

        threading.Thread(target=self._telemetry_worker, daemon=True).start()
        self.update_ui_loop()

    def start_move(self, event):
        self._offsetx = event.x
        self._offsety = event.y

    def do_move(self, event):
        x = self.winfo_pointerx() - self._offsetx
        y = self.winfo_pointery() - self._offsety
        self.geometry(f"+{x}+{y}")

    def _apply_initial_win32_styles(self):
        if not IS_WINDOWS or not self.hwnd:
            return
        try:
            GWL_EXSTYLE = -20
            WS_EX_TOPMOST = 0x00000008
            WS_EX_TOOLWINDOW = 0x00000080
            WS_EX_NOACTIVATE = 0x08000000

            current_style = ctypes.windll.user32.GetWindowLongW(self.hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(
                self.hwnd, 
                GWL_EXSTYLE, 
                current_style | WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
            )
        except Exception:
            pass

    def _telemetry_worker(self):
        SWP_NOMOVE = 0x0002
        SWP_NOSIZE = 0x0001
        SWP_NOACTIVATE = 0x0010
        SWP_SHOWWINDOW = 0x0040
        HWND_TOPMOST = -1

        while self.is_running:
            try:
                if IS_WINDOWS and self.hwnd:
                    try:
                        ctypes.windll.user32.SetWindowPos(
                            self.hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW
                        )
                    except Exception:
                        pass

                t = get_system_telemetry()
                disks = get_all_disks_data()
                disk_health = disks[0]["health"] if disks else 100

                fps_val = self.fps_tracker.current_fps

                self.latest_text = (
                    f"⚡ OVERLAY DIAGNOSTIC PC\n"
                    f"----------------------------\n"
                    f"FPS  : {fps_val}\n"
                    f"CPU  : {t['cpu_usage']:>5.1f}% | {t['cpu_temp']}°C\n"
                    f"RAM  : {t['ram_usage']:>5.1f}% ({t['ram_used_gb']}/{t['ram_total_gb']} GB)\n"
                    f"GPU  : {t['gpu_usage']:>5.1f}% | {t['gpu_temp']}°C\n"
                    f"SSD  : Salud {disk_health}%"
                )
            except Exception:
                pass

            time.sleep(1.0)

    def update_ui_loop(self):
        if self.winfo_exists():
            self.lbl_telemetry.config(text=self.latest_text)
            self.after(250, self.update_ui_loop)

    def destroy(self):
        self.is_running = False
        self.fps_tracker.stop()
        super().destroy()