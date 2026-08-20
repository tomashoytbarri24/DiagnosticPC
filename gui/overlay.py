# gui/overlay.py

import os
import platform
import threading
import time
import tkinter as tk

from core.telemetry import (
    get_system_telemetry,
    get_all_disks_data
)


# =========================================================
# SISTEMA
# =========================================================

IS_WINDOWS = platform.system() == "Windows"

if IS_WINDOWS:
    import ctypes


# =========================================================
# COLORES
# =========================================================

BG = "#080d17"
CARD = "#0d1422"
CARD_2 = "#111a2b"

BORDER = "#1e3047"

TEXT = "#f8fafc"
TEXT_DIM = "#71839b"

CYAN = "#00e5ff"
GREEN = "#00ff9d"
PURPLE = "#a855f7"
ORANGE = "#f59e0b"
RED = "#ef4444"


# =========================================================
# FPS TRACKER WINDOWS
# =========================================================

class WindowsFPSTracker:
    """
    Obtiene una estimación del ritmo de frames presentados
    por el Desktop Window Manager.

    IMPORTANTE:
    Esto NO es el FPS interno de un videojuego.

    Representa el ritmo de composición/presentación que
    Windows puede observar a nivel del escritorio.

    Para FPS exacto de un juego habría que instrumentar
    el juego/renderizador o utilizar APIs específicas.
    """

    def __init__(self):

        self.running = True

        self.fps = None
        self.refresh_rate = None
        self.dropped = 0
        self.missed = 0

        self._lock = threading.Lock()

        self._dwmapi = None

        if IS_WINDOWS:

            try:

                self._dwmapi = ctypes.WinDLL(
                    "dwmapi.dll"
                )

            except Exception:

                self._dwmapi = None

        self.thread = threading.Thread(
            target=self._loop,
            daemon=True,
            name="DiagnosticPC-FPS"
        )

        self.thread.start()

    # -----------------------------------------------------
    # ESTRUCTURAS DWM
    # -----------------------------------------------------

    def _create_structures(self):

        class UNSIGNED_RATIO(ctypes.Structure):

            _fields_ = [
                (
                    "uiNumerator",
                    ctypes.c_uint32
                ),
                (
                    "uiDenominator",
                    ctypes.c_uint32
                )
            ]

        class DWM_TIMING_INFO(ctypes.Structure):

            _fields_ = [

                (
                    "cbSize",
                    ctypes.c_uint32
                ),

                (
                    "rateRefresh",
                    UNSIGNED_RATIO
                ),

                (
                    "qpcRefreshPeriod",
                    ctypes.c_uint64
                ),

                (
                    "rateCompose",
                    UNSIGNED_RATIO
                ),

                (
                    "qpcVBlank",
                    ctypes.c_uint64
                ),

                (
                    "cRefresh",
                    ctypes.c_uint64
                ),

                (
                    "cDXRefresh",
                    ctypes.c_uint32
                ),

                (
                    "qpcCompose",
                    ctypes.c_uint64
                ),

                (
                    "cFrame",
                    ctypes.c_uint64
                ),

                (
                    "cDXPresent",
                    ctypes.c_uint32
                ),

                (
                    "cRefreshFrame",
                    ctypes.c_uint64
                ),

                (
                    "cFrameSubmitted",
                    ctypes.c_uint64
                ),

                (
                    "cDXPresentSubmitted",
                    ctypes.c_uint32
                ),

                (
                    "cFrameConfirmed",
                    ctypes.c_uint64
                ),

                (
                    "cDXPresentConfirmed",
                    ctypes.c_uint32
                ),

                (
                    "cRefreshConfirmed",
                    ctypes.c_uint64
                ),

                (
                    "cDXRefreshConfirmed",
                    ctypes.c_uint32
                ),

                (
                    "cFramesLate",
                    ctypes.c_uint64
                ),

                (
                    "cFramesOutstanding",
                    ctypes.c_uint32
                ),

                (
                    "cFrameDisplayed",
                    ctypes.c_uint64
                ),

                (
                    "qpcFrameDisplayed",
                    ctypes.c_uint64
                ),

                (
                    "cRefreshFrameDisplayed",
                    ctypes.c_uint64
                ),

                (
                    "cFrameComplete",
                    ctypes.c_uint64
                ),

                (
                    "qpcFrameComplete",
                    ctypes.c_uint64
                ),

                (
                    "cFramePending",
                    ctypes.c_uint64
                ),

                (
                    "qpcFramePending",
                    ctypes.c_uint64
                ),

                (
                    "cFramesDisplayed",
                    ctypes.c_uint64
                ),

                (
                    "cFramesComplete",
                    ctypes.c_uint64
                ),

                (
                    "cFramesPending",
                    ctypes.c_uint64
                ),

                (
                    "cFramesAvailable",
                    ctypes.c_uint64
                ),

                (
                    "cFramesDropped",
                    ctypes.c_uint64
                ),

                (
                    "cFramesMissed",
                    ctypes.c_uint64
                ),

                (
                    "cRefreshNextDisplayed",
                    ctypes.c_uint64
                ),

                (
                    "cRefreshNextPresented",
                    ctypes.c_uint64
                ),

                (
                    "cRefreshesDisplayed",
                    ctypes.c_uint64
                ),

                (
                    "cRefreshesPresented",
                    ctypes.c_uint64
                ),

                (
                    "cRefreshStarted",
                    ctypes.c_uint64
                ),

                (
                    "cPixelsReceived",
                    ctypes.c_uint64
                ),

                (
                    "cPixelsDrawn",
                    ctypes.c_uint64
                ),

                (
                    "cBuffersEmpty",
                    ctypes.c_uint32
                )
            ]

        return DWM_TIMING_INFO

    # -----------------------------------------------------
    # READ DWM
    # -----------------------------------------------------

    def _read_dwm(self):

        if not IS_WINDOWS:
            return None

        if self._dwmapi is None:
            return None

        try:

            DWM_TIMING_INFO = (
                self._create_structures()
            )

            info = DWM_TIMING_INFO()

            info.cbSize = ctypes.sizeof(
                DWM_TIMING_INFO
            )

            function = (
                self._dwmapi.DwmGetCompositionTimingInfo
            )

            function.argtypes = [
                ctypes.c_void_p,
                ctypes.POINTER(DWM_TIMING_INFO)
            ]

            function.restype = ctypes.c_long

            # Windows 8.1+ requiere NULL.
            result = function(
                None,
                ctypes.byref(info)
            )

            if result != 0:
                return None

            refresh = None

            if (
                info.rateRefresh.uiDenominator
                != 0
            ):

                refresh = (
                    info.rateRefresh.uiNumerator
                    /
                    info.rateRefresh.uiDenominator
                )

            return {
                "frames_displayed":
                    int(info.cFramesDisplayed),

                "frames_complete":
                    int(info.cFramesComplete),

                "frames_dropped":
                    int(info.cFramesDropped),

                "frames_missed":
                    int(info.cFramesMissed),

                "refresh":
                    refresh
            }

        except Exception:

            return None

    # -----------------------------------------------------
    # TRACKER LOOP
    # -----------------------------------------------------

    def _loop(self):

        previous = self._read_dwm()
        previous_time = time.perf_counter()

        while self.running:

            time.sleep(0.5)

            current = self._read_dwm()
            current_time = time.perf_counter()

            if (
                current is not None
                and previous is not None
            ):

                elapsed = (
                    current_time
                    - previous_time
                )

                if elapsed > 0:

                    delta = (
                        current["frames_displayed"]
                        -
                        previous["frames_displayed"]
                    )

                    if delta >= 0:

                        measured = (
                            delta / elapsed
                        )

                        # Evitar valores absurdos.
                        if 0 <= measured <= 1000:

                            with self._lock:

                                self.fps = measured

                                self.refresh_rate = (
                                    current["refresh"]
                                )

                                self.dropped = (
                                    current["frames_dropped"]
                                )

                                self.missed = (
                                    current["frames_missed"]
                                )

            previous = current
            previous_time = current_time

        # Fin thread

    # -----------------------------------------------------
    # GET
    # -----------------------------------------------------

    def get_data(self):

        with self._lock:

            return {
                "fps": self.fps,
                "refresh": self.refresh_rate,
                "dropped": self.dropped,
                "missed": self.missed
            }

    # -----------------------------------------------------
    # STOP
    # -----------------------------------------------------

    def stop(self):

        self.running = False


# =========================================================
# OVERLAY
# =========================================================

class GameOverlay(tk.Toplevel):

    def __init__(
        self,
        master=None
    ):

        super().__init__(master)

        self.master_app = master

        self.running = True

        self._drag_x = 0
        self._drag_y = 0

        self._last_data = {}

        # -------------------------------------------------
        # WINDOW
        # -------------------------------------------------

        self.overrideredirect(True)

        self.title(
            "DiagnosticPC Overlay"
        )

        self.geometry(
            "340x215+30+30"
        )

        self.minsize(
            340,
            215
        )

        self.configure(
            bg=BG
        )

        self.wm_attributes(
            "-topmost",
            True
        )

        if IS_WINDOWS:

            try:

                self.wm_attributes(
                    "-transparentcolor",
                    BG
                )

            except Exception:
                pass

        else:

            try:

                self.attributes(
                    "-alpha",
                    0.96
                )

            except Exception:
                pass

        # -------------------------------------------------
        # FPS
        # -------------------------------------------------

        self.fps_tracker = (
            WindowsFPSTracker()
        )

        # -------------------------------------------------
        # ROOT CARD
        # -------------------------------------------------

        self.card = tk.Frame(
            self,
            bg=CARD,
            highlightbackground=BORDER,
            highlightthickness=1,
            bd=0
        )

        self.card.pack(
            fill="both",
            expand=True,
            padx=2,
            pady=2
        )

        # -------------------------------------------------
        # HEADER
        # -------------------------------------------------

        self.header = tk.Frame(
            self.card,
            bg=CARD
        )

        self.header.pack(
            fill="x",
            padx=12,
            pady=(10, 4)
        )

        self.title_label = tk.Label(
            self.header,
            text="DIAGNOSTICPC",
            font=(
                "Segoe UI",
                11,
                "bold"
            ),
            fg=TEXT,
            bg=CARD
        )

        self.title_label.pack(
            side="left"
        )

        self.status_dot = tk.Label(
            self.header,
            text="●",
            font=(
                "Segoe UI",
                10,
                "bold"
            ),
            fg=GREEN,
            bg=CARD
        )

        self.status_dot.pack(
            side="right"
        )

        # -------------------------------------------------
        # FPS
        # -------------------------------------------------

        self.fps_frame = tk.Frame(
            self.card,
            bg=CARD_2
        )

        self.fps_frame.pack(
            fill="x",
            padx=10,
            pady=(3, 7)
        )

        self.fps_caption = tk.Label(
            self.fps_frame,
            text="RENDER / PRESENT",
            font=(
                "Segoe UI",
                8,
                "bold"
            ),
            fg=TEXT_DIM,
            bg=CARD_2
        )

        self.fps_caption.pack(
            anchor="w",
            padx=10,
            pady=(7, 0)
        )

        self.fps_value = tk.Label(
            self.fps_frame,
            text="--",
            font=(
                "Consolas",
                24,
                "bold"
            ),
            fg=CYAN,
            bg=CARD_2
        )

        self.fps_value.pack(
            side="left",
            padx=(10, 4),
            pady=(0, 5)
        )

        self.fps_unit = tk.Label(
            self.fps_frame,
            text="FPS",
            font=(
                "Segoe UI",
                9,
                "bold"
            ),
            fg=TEXT_DIM,
            bg=CARD_2
        )

        self.fps_unit.pack(
            side="left",
            pady=(9, 5)
        )

        self.refresh_label = tk.Label(
            self.fps_frame,
            text="",
            font=(
                "Segoe UI",
                8
            ),
            fg=TEXT_DIM,
            bg=CARD_2
        )

        self.refresh_label.pack(
            side="right",
            padx=10
        )

        # -------------------------------------------------
        # METRICS
        # -------------------------------------------------

        self.metrics = tk.Frame(
            self.card,
            bg=CARD
        )

        self.metrics.pack(
            fill="x",
            padx=10,
            pady=(0, 7)
        )

        self.cpu_label = self._create_metric(
            self.metrics,
            "CPU",
            CYAN
        )

        self.ram_label = self._create_metric(
            self.metrics,
            "RAM",
            GREEN
        )

        self.gpu_label = self._create_metric(
            self.metrics,
            "GPU",
            PURPLE
        )

        self.disk_label = self._create_metric(
            self.metrics,
            "SSD",
            ORANGE
        )

        # -------------------------------------------------
        # FOOTER
        # -------------------------------------------------

        self.footer = tk.Label(
            self.card,
            text="Arrastra para mover • DiagnosticPC",
            font=(
                "Segoe UI",
                7
            ),
            fg=TEXT_DIM,
            bg=CARD
        )

        self.footer.pack(
            pady=(0, 8)
        )

        # -------------------------------------------------
        # DRAG
        # -------------------------------------------------

        self._bind_drag(
            self.card
        )

        # -------------------------------------------------
        # UPDATE
        # -------------------------------------------------

        self.after(
            100,
            self._update_ui
        )

        # -------------------------------------------------
        # TELEMETRY THREAD
        # -------------------------------------------------

        self.telemetry_thread = threading.Thread(
            target=self._telemetry_loop,
            daemon=True,
            name="DiagnosticPC-Overlay"
        )

        self.telemetry_thread.start()

        # -------------------------------------------------
        # WINDOWS STYLE
        # -------------------------------------------------

        self.hwnd = None

        if IS_WINDOWS:

            self.after(
                50,
                self._configure_windows
            )

    # =====================================================
    # CREATE METRIC
    # =====================================================

    def _create_metric(
        self,
        parent,
        name,
        color
    ):

        frame = tk.Frame(
            parent,
            bg=CARD
        )

        frame.pack(
            side="left",
            fill="x",
            expand=True
        )

        label = tk.Label(
            frame,
            text=f"{name}\n--",
            justify="left",
            anchor="w",
            font=(
                "Consolas",
                8,
                "bold"
            ),
            fg=color,
            bg=CARD
        )

        label.pack(
            fill="x",
            padx=3
        )

        return label

    # =====================================================
    # DRAG
    # =====================================================

    def _bind_drag(
        self,
        widget
    ):

        widget.bind(
            "<ButtonPress-1>",
            self._start_drag
        )

        widget.bind(
            "<B1-Motion>",
            self._drag
        )

        for child in widget.winfo_children():

            self._bind_drag(
                child
            )

    def _start_drag(
        self,
        event
    ):

        self._drag_x = event.x_root
        self._drag_y = event.y_root

        self._window_x = self.winfo_x()
        self._window_y = self.winfo_y()

    def _drag(
        self,
        event
    ):

        dx = (
            event.x_root
            - self._drag_x
        )

        dy = (
            event.y_root
            - self._drag_y
        )

        x = self._window_x + dx
        y = self._window_y + dy

        self.geometry(
            f"+{x}+{y}"
        )

    # =====================================================
    # WINDOWS CONFIG
    # =====================================================

    def _configure_windows(self):

        if not IS_WINDOWS:
            return

        try:

            self.update_idletasks()

            self.hwnd = (
                self.winfo_id()
            )

            user32 = (
                ctypes.windll.user32
            )

            GWL_EXSTYLE = -20

            WS_EX_TOPMOST = (
                0x00000008
            )

            WS_EX_TOOLWINDOW = (
                0x00000080
            )

            WS_EX_NOACTIVATE = (
                0x08000000
            )

            current = (
                user32.GetWindowLongW(
                    self.hwnd,
                    GWL_EXSTYLE
                )
            )

            user32.SetWindowLongW(
                self.hwnd,
                GWL_EXSTYLE,
                current
                | WS_EX_TOPMOST
                | WS_EX_TOOLWINDOW
                | WS_EX_NOACTIVATE
            )

            # TOPMOST sin activar.
            HWND_TOPMOST = -1

            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_NOACTIVATE = 0x0010
            SWP_SHOWWINDOW = 0x0040

            user32.SetWindowPos(
                self.hwnd,
                HWND_TOPMOST,
                0,
                0,
                0,
                0,
                SWP_NOMOVE
                | SWP_NOSIZE
                | SWP_NOACTIVATE
                | SWP_SHOWWINDOW
            )

        except Exception:

            pass

    # =====================================================
    # TELEMETRY THREAD
    # =====================================================

    def _telemetry_loop(self):

        while self.running:

            try:

                telemetry = (
                    get_system_telemetry()
                )

                disks = (
                    get_all_disks_data()
                )

                disk_health = 100

                if disks:

                    health_values = []

                    for disk in disks:

                        try:

                            health_values.append(
                                float(
                                    disk.get(
                                        "health",
                                        100
                                    )
                                )
                            )

                        except Exception:
                            pass

                    if health_values:

                        disk_health = min(
                            health_values
                        )

                fps_data = (
                    self.fps_tracker.get_data()
                )

                self._last_data = {

                    "cpu":
                        float(
                            telemetry.get(
                                "cpu_usage",
                                0
                            )
                        ),

                    "ram":
                        float(
                            telemetry.get(
                                "ram_usage",
                                0
                            )
                        ),

                    "gpu":
                        float(
                            telemetry.get(
                                "gpu_usage",
                                0
                            )
                        ),

                    "disk":
                        disk_health,

                    "cpu_temp":
                        telemetry.get(
                            "cpu_temp",
                            "--"
                        ),

                    "gpu_temp":
                        telemetry.get(
                            "gpu_temp",
                            "--"
                        ),

                    "fps":
                        fps_data.get(
                            "fps"
                        ),

                    "refresh":
                        fps_data.get(
                            "refresh"
                        ),

                    "dropped":
                        fps_data.get(
                            "dropped",
                            0
                        ),

                    "missed":
                        fps_data.get(
                            "missed",
                            0
                        )
                }

            except Exception:

                pass

            # 2 Hz es suficiente para el overlay.
            for _ in range(5):

                if not self.running:
                    break

                time.sleep(
                    0.1
                )

    # =====================================================
    # UI UPDATE
    # =====================================================

    def _update_ui(self):

        if not self.running:
            return

        try:

            data = dict(
                self._last_data
            )

            # ---------------------------------------------
            # FPS
            # ---------------------------------------------

            fps = data.get(
                "fps"
            )

            if fps is None:

                fps_text = "--"

            else:

                fps_text = (
                    f"{fps:.0f}"
                )

            self.fps_value.configure(
                text=fps_text
            )

            refresh = data.get(
                "refresh"
            )

            if refresh:

                self.refresh_label.configure(
                    text=(
                        f"{refresh:.0f} Hz"
                    )
                )

            else:

                self.refresh_label.configure(
                    text=""
                )

            # ---------------------------------------------
            # FPS COLOR
            # ---------------------------------------------

            if fps is None:

                fps_color = TEXT_DIM

            elif fps >= 120:

                fps_color = GREEN

            elif fps >= 60:

                fps_color = CYAN

            elif fps >= 30:

                fps_color = ORANGE

            else:

                fps_color = RED

            self.fps_value.configure(
                fg=fps_color
            )

            # ---------------------------------------------
            # CPU
            # ---------------------------------------------

            cpu = data.get(
                "cpu",
                0
            )

            cpu_temp = data.get(
                "cpu_temp",
                "--"
            )

            self.cpu_label.configure(
                text=(
                    f"CPU\n"
                    f"{cpu:.0f}% "
                    f"{cpu_temp}°"
                )
            )

            # ---------------------------------------------
            # RAM
            # ---------------------------------------------

            ram = data.get(
                "ram",
                0
            )

            self.ram_label.configure(
                text=(
                    f"RAM\n"
                    f"{ram:.0f}%"
                )
            )

            # ---------------------------------------------
            # GPU
            # ---------------------------------------------

            gpu = data.get(
                "gpu",
                0
            )

            gpu_temp = data.get(
                "gpu_temp",
                "--"
            )

            self.gpu_label.configure(
                text=(
                    f"GPU\n"
                    f"{gpu:.0f}% "
                    f"{gpu_temp}°"
                )
            )

            # ---------------------------------------------
            # DISK
            # ---------------------------------------------

            disk = data.get(
                "disk",
                100
            )

            self.disk_label.configure(
                text=(
                    f"SSD\n"
                    f"Salud {disk:.0f}%"
                )
            )

            # ---------------------------------------------
            # STATUS
            # ---------------------------------------------

            dropped = data.get(
                "dropped",
                0
            )

            missed = data.get(
                "missed",
                0
            )

            if dropped > 0 or missed > 0:

                self.status_dot.configure(
                    fg=ORANGE
                )

            else:

                self.status_dot.configure(
                    fg=GREEN
                )

        except Exception:

            pass

        try:

            self.after(
                100,
                self._update_ui
            )

        except Exception:

            pass

    # =====================================================
    # CLOSE
    # =====================================================

    def destroy(self):

        if not self.running:

            try:
                return super().destroy()
            except Exception:
                return

        self.running = False

        try:

            self.fps_tracker.stop()

        except Exception:
            pass

        try:

            if hasattr(
                self,
                "telemetry_thread"
            ):

                if (
                    self.telemetry_thread.is_alive()
                ):

                    self.telemetry_thread.join(
                        timeout=0.25
                    )

        except Exception:
            pass

        try:

            super().destroy()

        except Exception:

            pass
