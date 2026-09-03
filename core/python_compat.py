"""Política de compatibilidad de intérprete para CorePulse.

CorePulse exige CPython 3.12 o superior y no impone un límite máximo artificial.
Las capacidades que dependen de extensiones de terceros se detectan por importación
real; si una extensión todavía no existe para una futura versión de Python, la app
continúa con esa capacidad marcada como no disponible (REAL_OR_NA).
"""
from __future__ import annotations

import importlib.util
import platform
import struct
import sys
from dataclasses import dataclass

from core.version import MIN_PYTHON


@dataclass(frozen=True)
class PythonCompatibility:
    version: tuple[int, int, int]
    executable: str
    architecture_bits: int
    minimum_supported: bool
    sensor_bridge_importable: bool
    hardwaremonitor_importable: bool

    @property
    def full_sensor_stack_importable(self) -> bool:
        return self.sensor_bridge_importable and self.hardwaremonitor_importable


def current_version_tuple() -> tuple[int, int, int]:
    v = sys.version_info
    return int(v.major), int(v.minor), int(v.micro)


def is_supported_python(version=None) -> bool:
    version = tuple(version or current_version_tuple())
    return version[:2] >= tuple(MIN_PYTHON)


def enforce_minimum_python() -> None:
    """Detiene el arranque únicamente si Python es anterior a 3.12."""
    if is_supported_python():
        return
    required = '.'.join(str(x) for x in MIN_PYTHON)
    actual = platform.python_version()
    raise RuntimeError(
        f'CorePulse requiere Python {required} o superior. '
        f'Intérprete detectado: Python {actual} ({sys.executable}).'
    )


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


def runtime_compatibility() -> PythonCompatibility:
    return PythonCompatibility(
        version=current_version_tuple(),
        executable=sys.executable,
        architecture_bits=struct.calcsize('P') * 8,
        minimum_supported=is_supported_python(),
        sensor_bridge_importable=_module_available('clr'),
        hardwaremonitor_importable=_module_available('HardwareMonitor'),
    )


def compatibility_summary() -> dict:
    state = runtime_compatibility()
    return {
        'python_version': '.'.join(map(str, state.version)),
        'python_executable': state.executable,
        'architecture_bits': state.architecture_bits,
        'python_policy': f'{MIN_PYTHON[0]}.{MIN_PYTHON[1]}+',
        'minimum_supported': state.minimum_supported,
        'pythonnet_available': state.sensor_bridge_importable,
        'hardwaremonitor_available': state.hardwaremonitor_importable,
        'deep_sensors_available': state.full_sensor_stack_importable,
        'no_artificial_upper_bound': True,
    }
