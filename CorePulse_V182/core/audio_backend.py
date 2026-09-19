"""Selecciona el backend de audio real apropiado para la plataforma."""
from __future__ import annotations

import platform

from core.audio_common import AudioError

if platform.system() == 'Linux':
    from core.linux_audio import LinuxAudio as AudioBackend
else:
    from core.windows_audio import WindowsAudio as AudioBackend

__all__ = ['AudioBackend', 'AudioError']
