"""Valida que un intérprete pueda ejecutar CorePulse con funcionalidad completa.

No decide compatibilidad por número de minor. La decide por carga real del stack.
"""
from __future__ import annotations

import argparse
import importlib
import json
import platform
from pathlib import Path
import struct
import sys
import traceback

MIN_PYTHON = (3, 12)
REQUIRED_IMPORTS = (
    'psutil', 'customtkinter', 'PIL', 'matplotlib', 'reportlab', 'platformdirs',
    'send2trash', 'groq', 'dotenv', 'pystray', 'wmi', 'win32api', 'pythoncom',
    'pywintypes', 'clr', 'pythonnet', 'HardwareMonitor',
)


def _check_import(name: str) -> dict:
    try:
        module = importlib.import_module(name)
        return {'name': name, 'ok': True, 'version': str(getattr(module, '__version__', '') or '')}
    except Exception as exc:
        return {'name': name, 'ok': False, 'error': f'{type(exc).__name__}: {exc}'}


def validate() -> dict:
    bits = struct.calcsize('P') * 8
    version = tuple(sys.version_info[:3])
    imports = [_check_import(name) for name in REQUIRED_IMPORTS]
    errors = []
    if version[:2] < MIN_PYTHON:
        errors.append(f'Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ requerido')
    if bits != 64:
        errors.append('Runtime x64 requerido')
    if platform.system() != 'Windows':
        errors.append('Windows requerido para equivalencia funcional completa')
    errors.extend([f"Import {row['name']}: {row.get('error','falló')}" for row in imports if not row['ok']])

    lhm = hid = None
    hm_error = None
    try:
        import HardwareMonitor
        from HardwareMonitor.Hardware import Computer
        base = Path(HardwareMonitor.__file__).resolve().parent / 'lib'
        lhm_rows = list(base.rglob('LibreHardwareMonitorLib.dll'))
        hid_rows = list(base.rglob('HidSharp.dll'))
        if not lhm_rows or not hid_rows:
            raise RuntimeError(f'DLLs requeridas no encontradas en {base}')
        lhm, hid = str(lhm_rows[0]), str(hid_rows[0])
        Computer()
    except Exception as exc:
        hm_error = f'{type(exc).__name__}: {exc}'
        errors.append(f'HardwareMonitor/LibreHardwareMonitor: {hm_error}')

    return {
        'ok': not errors,
        'python': platform.python_version(),
        'python_executable': sys.executable,
        'implementation': platform.python_implementation(),
        'architecture_bits': bits,
        'platform': platform.platform(),
        'minimum_python': f'{MIN_PYTHON[0]}.{MIN_PYTHON[1]}',
        'no_artificial_minor_upper_bound': True,
        'imports': imports,
        'libre_hardware_monitor': lhm,
        'hidsharp': hid,
        'hardwaremonitor_error': hm_error,
        'errors': errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output')
    args = parser.parse_args()
    try:
        report = validate()
    except Exception:
        report = {'ok': False, 'errors': [traceback.format_exc()], 'python_executable': sys.executable}
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    print(payload)
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload, encoding='utf-8')
    return 0 if report.get('ok') else 1


if __name__ == '__main__':
    raise SystemExit(main())
