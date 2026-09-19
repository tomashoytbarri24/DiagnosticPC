"""Tipos compartidos por los backends de audio de CorePulse."""
from __future__ import annotations


class AudioError(RuntimeError):
    """Error reproducible de la prueba de audio, independiente de plataforma."""


__all__ = ['AudioError']
