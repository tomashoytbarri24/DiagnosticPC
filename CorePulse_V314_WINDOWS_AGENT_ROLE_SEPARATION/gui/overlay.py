"""Adapta el ciclo de vida de la interfaz al overlay real renderizado por RTSS."""
# Código refactorizado: nombres estables y documentación en español.
import tkinter as tk
from core.rtss_overlay_service import RTSSOverlayService

class GameOverlay(tk.Toplevel):

    def __init__(self, master=None):
        super().__init__(master)
        self.withdraw()
        self.title('CorePulse RTSS Overlay Controller')
        self.service = RTSSOverlayService()
        self._destroyed = False

    def show(self):
        return

    def hide(self):
        try:
            self.service.rtss.update_osd('')
        except Exception:
            pass

    def get_status(self):
        return self.service.status()

    def destroy(self):
        if self._destroyed:
            return
        self._destroyed = True
        try:
            self.service.stop()
        except Exception:
            pass
        try:
            super().destroy()
        except Exception:
            pass
