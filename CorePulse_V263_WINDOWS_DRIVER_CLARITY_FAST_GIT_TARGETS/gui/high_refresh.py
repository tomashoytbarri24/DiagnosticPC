"""Política de interacción fluida para pantallas de alta frecuencia.

CorePulse no intenta convertir la telemetría en un bucle de 120/240 Hz. La
frecuencia alta sólo se usa mientras hay movimiento visual (scroll/transición),
y se detiene completamente al quedar la interfaz en reposo.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
import sys


@dataclass(frozen=True)
class UIRefreshPolicy:
    display_hz: int
    target_hz: int
    frame_ms: int
    source: str


def _windows_primary_refresh_hz() -> int | None:
    """Lee la frecuencia actual del display primario sin dependencias externas."""
    if sys.platform != 'win32':
        return None
    try:
        import ctypes
        from ctypes import wintypes

        CCHDEVICENAME = 32
        CCHFORMNAME = 32
        ENUM_CURRENT_SETTINGS = -1

        class POINTL(ctypes.Structure):
            _fields_ = [('x', wintypes.LONG), ('y', wintypes.LONG)]

        class _PrinterFields(ctypes.Structure):
            _fields_ = [
                ('dmOrientation', ctypes.c_short),
                ('dmPaperSize', ctypes.c_short),
                ('dmPaperLength', ctypes.c_short),
                ('dmPaperWidth', ctypes.c_short),
                ('dmScale', ctypes.c_short),
                ('dmCopies', ctypes.c_short),
                ('dmDefaultSource', ctypes.c_short),
                ('dmPrintQuality', ctypes.c_short),
            ]

        class _DisplayFields(ctypes.Structure):
            _fields_ = [
                ('dmPosition', POINTL),
                ('dmDisplayOrientation', wintypes.DWORD),
                ('dmDisplayFixedOutput', wintypes.DWORD),
            ]

        class _ModeUnion(ctypes.Union):
            _fields_ = [('printer', _PrinterFields), ('display', _DisplayFields)]

        class DEVMODEW(ctypes.Structure):
            _anonymous_ = ('mode',)
            _fields_ = [
                ('dmDeviceName', wintypes.WCHAR * CCHDEVICENAME),
                ('dmSpecVersion', wintypes.WORD),
                ('dmDriverVersion', wintypes.WORD),
                ('dmSize', wintypes.WORD),
                ('dmDriverExtra', wintypes.WORD),
                ('dmFields', wintypes.DWORD),
                ('mode', _ModeUnion),
                ('dmColor', ctypes.c_short),
                ('dmDuplex', ctypes.c_short),
                ('dmYResolution', ctypes.c_short),
                ('dmTTOption', ctypes.c_short),
                ('dmCollate', ctypes.c_short),
                ('dmFormName', wintypes.WCHAR * CCHFORMNAME),
                ('dmLogPixels', wintypes.WORD),
                ('dmBitsPerPel', wintypes.DWORD),
                ('dmPelsWidth', wintypes.DWORD),
                ('dmPelsHeight', wintypes.DWORD),
                ('dmDisplayFlags', wintypes.DWORD),
                ('dmDisplayFrequency', wintypes.DWORD),
                ('dmICMMethod', wintypes.DWORD),
                ('dmICMIntent', wintypes.DWORD),
                ('dmMediaType', wintypes.DWORD),
                ('dmDitherType', wintypes.DWORD),
                ('dmReserved1', wintypes.DWORD),
                ('dmReserved2', wintypes.DWORD),
                ('dmPanningWidth', wintypes.DWORD),
                ('dmPanningHeight', wintypes.DWORD),
            ]

        mode = DEVMODEW()
        mode.dmSize = ctypes.sizeof(DEVMODEW)
        ok = ctypes.windll.user32.EnumDisplaySettingsW(None, ENUM_CURRENT_SETTINGS, ctypes.byref(mode))
        if not ok:
            return None
        hz = int(mode.dmDisplayFrequency or 0)
        return hz if 30 <= hz <= 1000 else None
    except Exception:
        return None


def get_ui_refresh_policy() -> UIRefreshPolicy:
    """Devuelve una política conservadora con tope de 120 Hz para Tk/CTk.

    ``COREPULSE_UI_HZ`` permite diagnóstico manual, pero siempre se limita a
    60..120 Hz para evitar que la interfaz compita con los juegos por CPU.
    """
    override = str(os.environ.get('COREPULSE_UI_HZ', '') or '').strip()
    if override:
        try:
            display_hz = max(30, min(1000, int(float(override))))
            source = 'env'
        except Exception:
            display_hz = _windows_primary_refresh_hz() or 60
            source = 'windows' if display_hz != 60 else 'fallback'
    else:
        detected = _windows_primary_refresh_hz()
        display_hz = detected or 60
        source = 'windows' if detected else 'fallback'

    # 60 Hz conserva el coste histórico; 75/90/120/144/165/240 ganan pasos
    # adicionales, con techo de 120 Hz para CustomTkinter.
    target_hz = max(60, min(120, int(display_hz)))
    frame_ms = max(8, int(1000.0 / float(target_hz)))
    return UIRefreshPolicy(display_hz=display_hz, target_hz=target_hz, frame_ms=frame_ms, source=source)


DEFAULT_NAVIGATION_DEBOUNCE_MS = 4
