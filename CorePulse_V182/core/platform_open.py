"""Apertura de URLs/archivos con integración de escritorio por plataforma."""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import threading
import time
import webbrowser
from pathlib import Path


def _run_detached(argv):
    try:
        subprocess.Popen(
            list(argv),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return True
    except Exception:
        return False


def _default_browser_token() -> str:
    """Obtiene una pista del navegador predeterminado sin asumir una marca."""
    if platform.system() != 'Linux':
        return ''
    try:
        cp = subprocess.run(
            ['xdg-settings', 'get', 'default-web-browser'],
            capture_output=True, text=True, timeout=2, check=False,
        )
        value = (cp.stdout or '').strip().casefold()
    except Exception:
        value = ''
    value = value.removesuffix('.desktop')
    for suffix in ('-stable', '-browser', '.browser'):
        value = value.replace(suffix, '')
    aliases = {
        'com.brave.browser': 'brave', 'brave': 'brave',
        'google-chrome': 'chrome', 'chromium': 'chromium',
        'firefox': 'firefox', 'org.mozilla.firefox': 'firefox',
        'microsoft-edge': 'edge', 'vivaldi': 'vivaldi', 'opera': 'opera',
    }
    for key, token in aliases.items():
        if key in value:
            return token
    return value.split('.')[-1] if value else ''


def _focus_linux_browser(token: str = '') -> bool:
    """Best-effort: activa la ventana del navegador si el compositor lo permite.

    En Wayland puro los compositores pueden impedir que una aplicación robe foco;
    en X11/XWayland wmctrl/xdotool sí pueden activarla. No se instala software ni
    se considera un fallo si la política del escritorio lo bloquea.
    """
    token = (token or _default_browser_token()).casefold()
    patterns = [x for x in (token, 'brave', 'firefox', 'chromium', 'chrome', 'edge', 'vivaldi', 'opera') if x]

    wmctrl = shutil.which('wmctrl')
    if wmctrl:
        try:
            cp = subprocess.run([wmctrl, '-lx'], capture_output=True, text=True, timeout=2, check=False)
            rows = (cp.stdout or '').splitlines()
            for pattern in patterns:
                matches = [line for line in rows if pattern in line.casefold()]
                if matches:
                    window_id = matches[-1].split(None, 1)[0]
                    subprocess.run([wmctrl, '-ia', window_id], timeout=2, check=False,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return True
        except Exception:
            pass

    xdotool = shutil.which('xdotool')
    if xdotool:
        for pattern in patterns:
            try:
                cp = subprocess.run([xdotool, 'search', '--onlyvisible', '--class', pattern],
                                    capture_output=True, text=True, timeout=2, check=False)
                ids = [line.strip() for line in (cp.stdout or '').splitlines() if line.strip().isdigit()]
                if ids:
                    subprocess.run([xdotool, 'windowactivate', '--sync', ids[-1]], timeout=2, check=False,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return True
            except Exception:
                continue
    return False


def open_url_foreground(url: str) -> bool:
    """Abre una URL y solicita foco al navegador cuando el SO lo permite."""
    url = str(url or '').strip()
    if not url:
        return False
    system = platform.system()
    if system == 'Linux':
        token = _default_browser_token()
        desktop = (os.environ.get('XDG_CURRENT_DESKTOP') or '').casefold()
        opened = False
        # En Plasma, kioclient conserva mejor la activación que webbrowser.
        if 'kde' in desktop or 'plasma' in desktop:
            for name in ('kioclient6', 'kioclient5', 'kioclient'):
                tool = shutil.which(name)
                if tool:
                    opened = _run_detached([tool, 'exec', url])
                    if opened:
                        break
        if not opened:
            opener = shutil.which('xdg-open')
            opened = _run_detached([opener, url]) if opener else bool(webbrowser.open(url, new=2))

        def activate():
            # Damos tiempo al navegador para crear/cambiar de pestaña.
            for delay in (0.35, 0.65, 1.0):
                time.sleep(delay)
                if _focus_linux_browser(token):
                    return
        threading.Thread(target=activate, daemon=True, name='CorePulse-BrowserFocus').start()
        return opened
    try:
        return bool(webbrowser.open(url, new=2))
    except Exception:
        return False


def open_path(path: str | os.PathLike) -> bool:
    value = str(Path(path).expanduser())
    system = platform.system()
    if system == 'Windows':
        try:
            os.startfile(value)  # type: ignore[attr-defined]
            return True
        except Exception:
            return False
    if system == 'Darwin':
        return _run_detached(['open', value])
    opener = shutil.which('xdg-open')
    return _run_detached([opener, value]) if opener else False
