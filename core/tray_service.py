"""Gestiona el icono de bandeja y el ciclo de restauración o cierre de CorePulse."""
from __future__ import annotations
# Código refactorizado: nombres estables y documentación en español.
import threading
from pathlib import Path
try:
    import pystray
    from PIL import Image, ImageDraw
except Exception:
    pystray = Image = ImageDraw = None
def _icon():
    """Gestiona la operación `icon` dentro de CorePulse sin alterar la evidencia real ni las reglas del módulo."""
    if Image is not None:
        try:
            path = Path(__file__).resolve().parents[1] / 'assets' / 'CorePulseSymbol.png'
            if path.exists():
                return Image.open(path).convert('RGBA').resize((64, 64), Image.Resampling.LANCZOS)
        except Exception:
            pass
    if Image is None or ImageDraw is None:
        return None
    img = Image.new('RGB', (64, 64), (8, 13, 23))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((8, 8, 56, 56), radius=12, fill=(14, 165, 233))
    d.rectangle((20, 28, 44, 36), fill=(248, 250, 252))
    return img

class CorePulseTray:

    def __init__(self, app, agent):
        self.app = app
        self.agent = agent
        self.icon = None
        self._minimize_notice_sent = False
        self._last_title = 'CorePulse · Agente activo'

    @property
    def available(self):
        return pystray is not None and Image is not None

    @property
    def running(self):
        return self.icon is not None

    def _dispatch(self, method_name, *args):

        def invoke():
            method = getattr(self.app, method_name, None)
            if callable(method):
                method(*args)
        try:
            self.app.after(0, invoke)
        except Exception:
            pass

    def _restore_then(self, method_name=None):

        def invoke():
            restore = getattr(self.app, 'restore_from_tray', None)
            if callable(restore):
                restore()
            if method_name:
                method = getattr(self.app, method_name, None)
                if callable(method):
                    method()
        try:
            self.app.after(0, invoke)
        except Exception:
            pass

    def start(self):
        if not self.available or self.icon is not None:
            return False
        icon_image = _icon()
        if icon_image is None:
            return False

        def show(*_):
            self._restore_then()

        def overlay(*_):
            self._restore_then('open_overlay_config_window')

        def alerts(*_):
            self._restore_then('open_smart_alert_window')

        def trends(*_):
            self._restore_then('open_session_trends_window')

        def history(*_):
            self._restore_then('open_alert_history_window')

        def quit_app(*_):
            self._dispatch('on_close')
        self.icon = pystray.Icon('CorePulse', icon_image, self._last_title, pystray.Menu(pystray.MenuItem('Abrir CorePulse', show, default=True), pystray.Menu.SEPARATOR, pystray.MenuItem('Configurar Overlay', overlay), pystray.MenuItem('Alertas y diagnóstico', alerts), pystray.MenuItem('Tendencias', trends), pystray.MenuItem('Historial de alertas', history), pystray.Menu.SEPARATOR, pystray.MenuItem('Salir de CorePulse', quit_app)))
        threading.Thread(target=self.icon.run, daemon=True, name='CorePulse-Tray').start()
        return True

    def notify_minimized(self):
        if not self.icon or self._minimize_notice_sent:
            return
        self._minimize_notice_sent = True
        try:
            self.icon.notify('CorePulse continúa monitoreando en segundo plano.', 'CorePulse')
        except Exception:
            pass

    def notify_state(self):
        if not self.icon:
            return
        try:
            state = self.agent.get_state()
        except Exception:
            state = {}
        game = state.get('game') or {}
        name = str(game.get('name') or '').replace('\\', '/').split('/')[-1]
        overall = str(state.get('overall') or 'UNKNOWN').upper()
        mode = str(state.get('mode') or 'UNKNOWN').upper()
        if mode == 'GAME' and name:
            title = f'CorePulse · {overall} · Juego: {name}'
        else:
            title = f'CorePulse · {overall} · Agente activo'
        self._last_title = title
        try:
            self.icon.title = title
        except Exception:
            pass

    def stop(self):
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass
        self.icon = None
