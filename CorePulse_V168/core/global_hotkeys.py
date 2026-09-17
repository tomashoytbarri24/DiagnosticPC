"""Atajos globales exactos de CorePulse.

El módulo registra únicamente los modificadores que el usuario eligió. La captura
visual no depende de ``event.state`` porque en Tk/Windows ese bitmask puede conservar
flags Mod1 residuales y producir un Alt "fantasma".
"""
from __future__ import annotations

from dataclasses import dataclass
import os
import re
import threading
from typing import Any, Callable, Iterable, Optional

IS_WINDOWS = os.name == 'nt'
CAPTURE_VERSION = 2
MODIFIER_ORDER = ('CTRL', 'ALT', 'SHIFT', 'WIN')
MODIFIER_LABELS = {'CTRL': 'Ctrl', 'ALT': 'Alt', 'SHIFT': 'Shift', 'WIN': 'Win'}
_MOD_ALIASES = {
    'CONTROL': 'CTRL', 'CTRL': 'CTRL', 'CONTROL_L': 'CTRL', 'CONTROL_R': 'CTRL',
    'ALT': 'ALT', 'ALT_L': 'ALT', 'ALT_R': 'ALT', 'OPTION': 'ALT',
    'SHIFT': 'SHIFT', 'SHIFT_L': 'SHIFT', 'SHIFT_R': 'SHIFT',
    'WIN': 'WIN', 'WIN_L': 'WIN', 'WIN_R': 'WIN', 'WINDOWS': 'WIN',
    'SUPER': 'WIN', 'SUPER_L': 'WIN', 'SUPER_R': 'WIN', 'META': 'WIN',
}
_KEY_ALIASES = {
    'RETURN': 'ENTER', 'ESCAPE': 'ESC', 'ESC': 'ESC', 'PRIOR': 'PAGEUP', 'NEXT': 'PAGEDOWN',
    'SPACE': 'SPACE', 'TAB': 'TAB', 'BACKSPACE': 'BACKSPACE', 'DELETE': 'DELETE', 'DEL': 'DELETE',
    'INSERT': 'INSERT', 'INS': 'INSERT', 'HOME': 'HOME', 'END': 'END',
    'LEFT': 'LEFT', 'RIGHT': 'RIGHT', 'UP': 'UP', 'DOWN': 'DOWN',
    'PRINTSCREEN': 'PRINTSCREEN', 'PRTSC': 'PRINTSCREEN', 'PAUSE': 'PAUSE',
    'CAPSLOCK': 'CAPSLOCK', 'NUMLOCK': 'NUMLOCK', 'SCROLLLOCK': 'SCROLLLOCK',
    'PAGEUP': 'PAGEUP', 'PAGEDOWN': 'PAGEDOWN',
}

if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    WM_HOTKEY = 0x0312
    WM_QUIT = 0x0012
    MOD_ALT = 0x0001
    MOD_CONTROL = 0x0002
    MOD_SHIFT = 0x0004
    MOD_WIN = 0x0008
    MOD_NOREPEAT = 0x4000
    MODIFIER_FLAGS = {'ALT': MOD_ALT, 'CTRL': MOD_CONTROL, 'SHIFT': MOD_SHIFT, 'WIN': MOD_WIN}

    class MSG(ctypes.Structure):
        _fields_ = [
            ('hwnd', wintypes.HWND), ('message', wintypes.UINT),
            ('wParam', wintypes.WPARAM), ('lParam', wintypes.LPARAM),
            ('time', wintypes.DWORD), ('pt', wintypes.POINT), ('lPrivate', wintypes.DWORD),
        ]
else:
    ctypes = None
    wintypes = None
    user32 = None
    kernel32 = None
    WM_HOTKEY = 0
    WM_QUIT = 0
    MOD_NOREPEAT = 0
    MODIFIER_FLAGS = {'ALT': 0, 'CTRL': 0, 'SHIFT': 0, 'WIN': 0}


@dataclass(frozen=True)
class HotkeySpec:
    modifiers: tuple[str, ...]
    key: str
    enabled: bool = True
    capture_version: int = CAPTURE_VERSION

    def as_dict(self):
        return {
            'modifiers': list(self.modifiers), 'key': self.key,
            'enabled': bool(self.enabled), 'capture_version': int(self.capture_version),
        }


DEFAULT_TOGGLE_HOTKEY = HotkeySpec(modifiers=('CTRL',), key='9', enabled=True)


def normalize_modifier(value: Any) -> str:
    return _MOD_ALIASES.get(str(value or '').strip().upper(), '')


def ordered_modifiers(values: Iterable[str]) -> tuple[str, ...]:
    normalized = {normalize_modifier(v) for v in (values or ())}
    normalized.discard('')
    return tuple(name for name in MODIFIER_ORDER if name in normalized)


def normalize_key_name(value: Any) -> str:
    raw = str(value or '').strip().upper().replace(' ', '')
    raw = raw.replace('KP_', 'NUMPAD')
    if raw in _MOD_ALIASES:
        return ''
    if raw in _KEY_ALIASES:
        return _KEY_ALIASES[raw]
    if len(raw) == 1 and raw.isalnum():
        return raw
    if re.fullmatch(r'F([1-9]|1[0-9]|2[0-4])', raw):
        return raw
    if re.fullmatch(r'NUMPAD[0-9]', raw):
        return raw
    if raw in {'NUMPADADD', 'NUMPADSUBTRACT', 'NUMPADMULTIPLY', 'NUMPADDIVIDE', 'NUMPADDECIMAL'}:
        return raw
    return raw if raw in {
        'ENTER', 'TAB', 'SPACE', 'BACKSPACE', 'DELETE', 'INSERT', 'HOME', 'END',
        'PAGEUP', 'PAGEDOWN', 'LEFT', 'RIGHT', 'UP', 'DOWN', 'PRINTSCREEN',
        'PAUSE', 'CAPSLOCK', 'NUMLOCK', 'SCROLLLOCK',
    } else ''


def normalize_key_from_tk_event(keysym: Any) -> str:
    raw = str(keysym or '').strip().upper()
    modifier = normalize_modifier(raw)
    return modifier or normalize_key_name(raw)


def normalize_hotkey_config(data: Any, fallback: HotkeySpec | None = DEFAULT_TOGGLE_HOTKEY):
    if isinstance(data, HotkeySpec):
        return data.as_dict()
    fallback = fallback if isinstance(fallback, HotkeySpec) else DEFAULT_TOGGLE_HOTKEY
    src = data if isinstance(data, dict) else {}
    if isinstance(data, str):
        src = parse_hotkey_label(data)
    raw_modifiers = src['modifiers'] if 'modifiers' in src else fallback.modifiers
    raw_key = src['key'] if 'key' in src else fallback.key
    modifiers = ordered_modifiers(raw_modifiers or ())
    key = normalize_key_name(raw_key)
    enabled = bool(src.get('enabled', fallback.enabled)) and bool(key)
    try:
        capture_version = int(src.get('capture_version', 1 if src else fallback.capture_version))
    except Exception:
        capture_version = 1
    return {
        'modifiers': list(modifiers), 'key': key, 'enabled': enabled,
        'capture_version': capture_version,
    }


def parse_hotkey_label(label: str):
    text = str(label or '').strip()
    if not text or text.casefold() in {'sin atajo', 'none', 'desactivado'}:
        return {'modifiers': [], 'key': '', 'enabled': False, 'capture_version': CAPTURE_VERSION}
    parts = [part.strip() for part in text.replace('＋', '+').split('+') if part.strip()]
    if not parts:
        return {'modifiers': [], 'key': '', 'enabled': False, 'capture_version': CAPTURE_VERSION}
    key = normalize_key_name(parts[-1])
    return {
        'modifiers': list(ordered_modifiers(parts[:-1])), 'key': key,
        'enabled': bool(key), 'capture_version': CAPTURE_VERSION,
    }


def hotkey_to_label(data: Any) -> str:
    spec = normalize_hotkey_config(data)
    if not spec.get('enabled') or not spec.get('key'):
        return 'Sin atajo'
    labels = [MODIFIER_LABELS[name] for name in ordered_modifiers(spec.get('modifiers') or ())]
    return '+'.join(labels + [str(spec['key'])])


def virtual_key_code(key: str) -> Optional[int]:
    name = normalize_key_name(key)
    if not name:
        return None
    if len(name) == 1 and (name.isalpha() or name.isdigit()):
        return ord(name.upper())
    if re.fullmatch(r'F([1-9]|1[0-9]|2[0-4])', name):
        return 0x70 + int(name[1:]) - 1
    fixed = {
        'ENTER': 0x0D, 'TAB': 0x09, 'SPACE': 0x20, 'BACKSPACE': 0x08,
        'DELETE': 0x2E, 'INSERT': 0x2D, 'HOME': 0x24, 'END': 0x23,
        'PAGEUP': 0x21, 'PAGEDOWN': 0x22, 'LEFT': 0x25, 'UP': 0x26,
        'RIGHT': 0x27, 'DOWN': 0x28, 'PRINTSCREEN': 0x2C, 'PAUSE': 0x13,
        'CAPSLOCK': 0x14, 'NUMLOCK': 0x90, 'SCROLLLOCK': 0x91,
        'NUMPAD0': 0x60, 'NUMPAD1': 0x61, 'NUMPAD2': 0x62, 'NUMPAD3': 0x63,
        'NUMPAD4': 0x64, 'NUMPAD5': 0x65, 'NUMPAD6': 0x66, 'NUMPAD7': 0x67,
        'NUMPAD8': 0x68, 'NUMPAD9': 0x69, 'NUMPADADD': 0x6B,
        'NUMPADSUBTRACT': 0x6D, 'NUMPADMULTIPLY': 0x6A,
        'NUMPADDIVIDE': 0x6F, 'NUMPADDECIMAL': 0x6E,
    }
    return fixed.get(name)


def hotkey_to_win32(data: Any):
    spec = normalize_hotkey_config(data)
    if not spec.get('enabled'):
        return 0, None
    modifiers = 0
    for name in ordered_modifiers(spec.get('modifiers') or ()):
        modifiers |= MODIFIER_FLAGS.get(name, 0)
    vk = virtual_key_code(str(spec.get('key') or ''))
    if not IS_WINDOWS:
        return modifiers, vk
    return modifiers | MOD_NOREPEAT, vk


class GlobalHotkeyManager:
    """Registra un atajo global mediante RegisterHotKey sin añadir modificadores."""

    HOTKEY_ID = 0xC0DE

    def __init__(self, callback: Callable[[], None] | None = None):
        self.callback = callback
        self.current = normalize_hotkey_config(DEFAULT_TOGGLE_HOTKEY)
        self._thread: Optional[threading.Thread] = None
        self._win_thread_id: Optional[int] = None
        self._running = False
        self.last_error: Optional[str] = None

    def update(self, config: Any):
        self.current = normalize_hotkey_config(config)
        self.restart()

    def restart(self):
        self.stop()
        if not IS_WINDOWS:
            self.last_error = 'Atajos globales disponibles sólo en Windows'
            return
        modifiers, vk = hotkey_to_win32(self.current)
        if vk is None or not self.current.get('enabled'):
            self.last_error = None
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, name='CorePulse-OverlayHotkey', daemon=True)
        self._thread.start()

    def _run(self):
        self.last_error = None
        self._win_thread_id = int(kernel32.GetCurrentThreadId())
        modifiers, vk = hotkey_to_win32(self.current)
        ok = bool(user32.RegisterHotKey(None, self.HOTKEY_ID, modifiers, vk))
        if not ok:
            self.last_error = 'No se pudo registrar el atajo global; puede estar ocupado por otra aplicación.'
            self._running = False
            self._win_thread_id = None
            return
        try:
            msg = MSG()
            while self._running:
                result = int(user32.GetMessageW(ctypes.byref(msg), None, 0, 0))
                if result <= 0:
                    break
                if msg.message == WM_HOTKEY and int(msg.wParam) == self.HOTKEY_ID:
                    try:
                        if callable(self.callback):
                            self.callback()
                    except Exception:
                        pass
        finally:
            try:
                user32.UnregisterHotKey(None, self.HOTKEY_ID)
            except Exception:
                pass
            self._running = False
            self._win_thread_id = None

    def stop(self):
        self._running = False
        thread = self._thread
        self._thread = None
        if IS_WINDOWS and self._win_thread_id is not None:
            try:
                user32.PostThreadMessageW(self._win_thread_id, WM_QUIT, 0, 0)
            except Exception:
                pass
        if thread is not None and thread.is_alive():
            try:
                thread.join(timeout=1.2)
            except Exception:
                pass


__all__ = [
    'CAPTURE_VERSION', 'HotkeySpec', 'DEFAULT_TOGGLE_HOTKEY', 'GlobalHotkeyManager',
    'normalize_modifier', 'ordered_modifiers', 'normalize_key_name',
    'normalize_key_from_tk_event', 'normalize_hotkey_config', 'parse_hotkey_label',
    'hotkey_to_label', 'virtual_key_code', 'hotkey_to_win32',
]
