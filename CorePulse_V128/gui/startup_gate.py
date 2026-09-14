"""Pantalla de preparación de CorePulse.

La barra refleja hitos reales del arranque. No representa telemetría ni inventa
resultados de diagnóstico: únicamente comunica qué subsistemas ya terminaron de
prepararse antes de liberar la interfaz principal. Desde 64w el gate también espera la primera muestra real ya renderizada.
"""
from __future__ import annotations

import ctypes
import os
import customtkinter as ctk
from PIL import Image

from core.runtime_paths import resource_path
from core.theme_manager import color as theme_color, role_color

# V124: la pantalla de arranque usa los roles EXACTOS del tema activo,
# igual que la vista previa del selector. Ya no depende de clasificar tonos
# heredados del tema azul original.
BG = role_color('bg')
# V128: el gate es una superficie visual amplia, igual que el panel grande de
# actividad de la previsualización. Usa surface_2 EXACTO; nunca una variante
# oscurecida de surface.
CARD = role_color('surface_2')
BORDER = role_color('border')
TEXT = role_color('text')
TEXT_2 = role_color('text_2')
MUTED = role_color('muted')
BLUE = role_color('accent')
PROGRESS_TRACK = role_color('border')
TRANSPARENT_KEY = '#010203'


def _active_monitor_work_area(app):
    """Devuelve el área útil del monitor donde está el cursor al iniciar CorePulse."""
    if os.name != 'nt':
        return None
    try:
        from ctypes import wintypes
        user32 = ctypes.windll.user32

        class MONITORINFO(ctypes.Structure):
            _fields_ = [
                ('cbSize', wintypes.DWORD),
                ('rcMonitor', wintypes.RECT),
                ('rcWork', wintypes.RECT),
                ('dwFlags', wintypes.DWORD),
            ]

        user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
        user32.GetCursorPos.restype = wintypes.BOOL
        user32.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
        user32.MonitorFromPoint.restype = ctypes.c_void_p
        user32.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.POINTER(MONITORINFO)]
        user32.GetMonitorInfoW.restype = wintypes.BOOL

        point = wintypes.POINT()
        if not user32.GetCursorPos(ctypes.byref(point)):
            return None
        monitor = user32.MonitorFromPoint(point, 2)  # MONITOR_DEFAULTTONEAREST
        if not monitor:
            return None
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            return None
        rect = info.rcWork
        return (int(rect.left), int(rect.top), int(rect.right), int(rect.bottom))
    except Exception:
        return None


def _startup_geometry(app, preferred_w, preferred_h):
    """Fallback Tk para tamaño/posición inicial antes del centrado Win32 definitivo."""
    bounds = _active_monitor_work_area(app)
    if bounds is None:
        screen_w = max(640, int(app.winfo_screenwidth()))
        screen_h = max(480, int(app.winfo_screenheight()))
        left, top, right, bottom = (0, 0, screen_w, screen_h)
    else:
        left, top, right, bottom = bounds
    monitor_w = max(420, right - left)
    monitor_h = max(240, bottom - top)
    width = min(int(preferred_w), max(420, monitor_w - 32))
    height = min(int(preferred_h), max(240, monitor_h - 48))
    x = left + (monitor_w - width) // 2
    y = top + (monitor_h - height) // 2
    return width, height, x, y


def _center_native_window_on_active_monitor(window):
    """Centra el HWND real dentro del monitor activo.

    Se hace después de materializar el Toplevel para que Windows calcule usando
    las mismas coordenadas/DPI del HWND. Esto evita desplazamientos en equipos
    con escalado distinto o varios monitores.
    """
    if os.name != 'nt':
        return False
    try:
        from ctypes import wintypes
        user32 = ctypes.windll.user32

        class MONITORINFO(ctypes.Structure):
            _fields_ = [
                ('cbSize', wintypes.DWORD),
                ('rcMonitor', wintypes.RECT),
                ('rcWork', wintypes.RECT),
                ('dwFlags', wintypes.DWORD),
            ]

        user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
        user32.GetCursorPos.restype = wintypes.BOOL
        user32.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
        user32.MonitorFromPoint.restype = ctypes.c_void_p
        user32.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.POINTER(MONITORINFO)]
        user32.GetMonitorInfoW.restype = wintypes.BOOL
        user32.GetAncestor.argtypes = [ctypes.c_void_p, wintypes.UINT]
        user32.GetAncestor.restype = ctypes.c_void_p
        user32.GetWindowRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.RECT)]
        user32.GetWindowRect.restype = wintypes.BOOL
        user32.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
        user32.SetWindowPos.restype = wintypes.BOOL

        point = wintypes.POINT()
        if not user32.GetCursorPos(ctypes.byref(point)):
            return False
        monitor = user32.MonitorFromPoint(point, 2)  # MONITOR_DEFAULTTONEAREST
        if not monitor:
            return False

        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            return False

        hwnd = int(window.winfo_id())
        try:
            root_hwnd = int(user32.GetAncestor(hwnd, 2))  # GA_ROOT
            if root_hwnd:
                hwnd = root_hwnd
        except Exception:
            pass

        rect = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return False

        win_w = max(1, int(rect.right - rect.left))
        win_h = max(1, int(rect.bottom - rect.top))
        work = info.rcWork
        work_w = int(work.right - work.left)
        work_h = int(work.bottom - work.top)
        x = int(work.left + (work_w - win_w) // 2)
        y = int(work.top + (work_h - win_h) // 2)

        SWP_NOSIZE = 0x0001
        SWP_NOZORDER = 0x0004
        SWP_NOACTIVATE = 0x0010
        return bool(user32.SetWindowPos(hwnd, 0, x, y, 0, 0, SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE))
    except Exception:
        return False


class StartupGate:
    """Gate visual mínimo: logo, progreso real y porcentaje."""

    WIDTH = 560
    HEIGHT = 250

    def __init__(self, app):
        self.app = app
        self._progress = 0.0
        self.window = ctk.CTkToplevel(app)
        self.window.withdraw()
        self.window.overrideredirect(True)
        self.window.configure(fg_color=TRANSPARENT_KEY)
        try:
            self.window.configure(bg=TRANSPARENT_KEY)
        except Exception:
            pass
        self.window.resizable(False, False)
        try:
            self.window.attributes('-topmost', True)
        except Exception:
            pass
        try:
            self.window.wm_attributes('-transparentcolor', TRANSPARENT_KEY)
        except Exception:
            pass

        width, height, x, y = _startup_geometry(app, self.WIDTH, self.HEIGHT)
        self.window.geometry(f'{width}x{height}{x:+d}{y:+d}')

        shell = ctk.CTkFrame(
            self.window,
            fg_color=CARD,
            border_width=1,
            border_color=BORDER,
            corner_radius=24,
        )
        shell.pack(fill='both', expand=True, padx=10, pady=10)

        content = ctk.CTkFrame(shell, fg_color='transparent')
        content.pack(fill='both', expand=True, padx=42, pady=(28, 28))

        self.brand_image = None
        try:
            icon_path = resource_path('assets', 'CorePulseSymbolWhite.png')
            if not icon_path.exists():
                icon_path = resource_path('assets', 'CorePulseSymbol.png')
            if icon_path.exists():
                pil = Image.open(icon_path).convert('RGBA')
                self.brand_image = ctk.CTkImage(light_image=pil, dark_image=pil, size=(104, 104))
        except Exception:
            self.brand_image = None

        self.brand_label = ctk.CTkLabel(content, image=self.brand_image, text='', width=104, height=104)
        self.brand_label.pack(anchor='center', pady=(0, 22))

        progress_row = ctk.CTkFrame(content, fg_color='transparent')
        progress_row.pack(fill='x')
        progress_row.grid_columnconfigure(0, weight=1)

        self.progress = ctk.CTkProgressBar(
            progress_row,
            height=10,
            corner_radius=999,
            progress_color=BLUE,
            fg_color=PROGRESS_TRACK,
            border_width=0,
        )
        self.progress.grid(row=0, column=0, sticky='ew', padx=(0, 14))
        self.progress.set(0.0)

        self.percent = ctk.CTkLabel(
            progress_row,
            text='0%',
            width=44,
            anchor='e',
            font=('Segoe UI', 11, 'bold'),
            text_color=TEXT,
        )
        self.percent.grid(row=0, column=1, sticky='e')

        self.branding = ctk.CTkLabel(
            shell,
            text='by Cereon Technologies ©',
            anchor='w',
            font=('Segoe UI', 10),
            text_color=MUTED,
        )
        self.branding.place(relx=0.055, rely=0.91, anchor='w')

    def _center_now(self):
        try:
            self.window.update_idletasks()
        except Exception:
            pass
        if _center_native_window_on_active_monitor(self.window):
            return
        try:
            width = max(1, int(self.window.winfo_width()))
            height = max(1, int(self.window.winfo_height()))
            _, _, x, y = _startup_geometry(self.app, width, height)
            self.window.geometry(f'{width}x{height}{x:+d}{y:+d}')
        except Exception:
            pass

    def show(self):
        self.window.deiconify()
        self.window.lift()
        self._center_now()
        try:
            self.window.update()
        except Exception:
            pass

        # Repite una vez cuando Tk/Windows ya publicaron el HWND y resolvieron DPI.
        try:
            self.window.after(80, self._center_now)
        except Exception:
            pass

        def _release_topmost():
            try:
                if self.window.winfo_exists():
                    self.window.attributes('-topmost', False)
            except Exception:
                pass
        try:
            self.window.after(250, _release_topmost)
        except Exception:
            pass

    def update_stage(self, text: str, progress: float, detail: str | None = None):
        """Actualiza sólo progreso real; el texto de etapas no se publica en el gate."""
        try:
            value = max(self._progress, min(1.0, max(0.0, float(progress))))
            self._progress = value
            self.progress.set(value)
            self.percent.configure(text=f'{int(round(value * 100.0))}%')
        except Exception:
            pass

    def mark_ready(self, limited: bool = False):
        self.update_stage('', 1.0, None)

    def close(self):
        try:
            if self.window.winfo_exists():
                self.window.destroy()
        except Exception:
            pass
