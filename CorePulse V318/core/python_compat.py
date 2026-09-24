"""Compatibilidad y bootstrap automático del runtime de CorePulse.

CorePulse no fija un minor máximo artificial. Cualquier CPython 3.12+ x64
instalado en Windows es candidato. Si el intérprete usado para abrir ``main.py`` o
``corepulse_launcher.py`` no tiene las dependencias, este módulo crea de forma
automática un venv aislado para ESE mismo minor, instala el stack y lo valida
antes de reejecutar CorePulse.

La compatibilidad funcional no se declara por número de versión: se declara
sólo si el stack completo de Windows pasa validación real.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import sys
import tempfile
from dataclasses import dataclass

from core.version import MIN_PYTHON, VERSION

RUNTIME_POINTER_NAME = '.corepulse_runtime_python.txt'
RUNTIME_REPORT_NAME = '.corepulse_runtime_validation.json'
ESSENTIAL_SOURCE_IMPORTS = ('customtkinter', 'psutil', 'PIL', 'matplotlib')
_AUTO_BOOTSTRAP_ENV = 'COREPULSE_AUTO_RUNTIME_BOOTSTRAP'
_BOOTSTRAPPED_ENV = 'COREPULSE_RUNTIME_BOOTSTRAPPED'


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


def is_x64() -> bool:
    return struct.calcsize('P') * 8 == 64


def is_cpython() -> bool:
    return platform.python_implementation().casefold() == 'cpython'


def enforce_minimum_python() -> None:
    if os.name != 'nt':
        raise RuntimeError('CorePulse es una aplicación exclusiva para Windows.')
    if is_supported_python() and is_x64() and is_cpython():
        return
    required = '.'.join(str(x) for x in MIN_PYTHON)
    actual = platform.python_version()
    bits = struct.calcsize('P') * 8
    implementation = platform.python_implementation()
    raise RuntimeError(
        f'CorePulse requiere Windows con CPython {required}+ x64. '
        f'Intérprete detectado: {implementation} {actual} {bits}-bit ({sys.executable}).'
    )


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


def missing_source_imports() -> list[str]:
    return [name for name in ESSENTIAL_SOURCE_IMPORTS if not _module_available(name)]


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def runtime_pointer_path() -> Path:
    return project_root() / RUNTIME_POINTER_NAME


def runtime_report_path() -> Path:
    return project_root() / RUNTIME_REPORT_NAME


def validated_runtime_python() -> Path | None:
    try:
        pointer = runtime_pointer_path()
        if not pointer.is_file():
            return None
        value = pointer.read_text(encoding='utf-8').strip().strip('"')
        candidate = Path(value).expanduser()
        return candidate.resolve() if candidate.is_file() else None
    except Exception:
        return None




def _runtime_minor(python_exe: Path) -> tuple[int, int] | None:
    try:
        proc = subprocess.run(
            [str(python_exe), '-c', 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")'],
            capture_output=True, text=True, timeout=15, check=False,
        )
        if proc.returncode != 0:
            return None
        major, minor = proc.stdout.strip().split('.', 1)
        return int(major), int(minor)
    except Exception:
        return None


def _runtime_matches_current_minor(python_exe: Path) -> bool:
    return _runtime_minor(python_exe) == (sys.version_info.major, sys.version_info.minor)

def _runtime_root_for_current_python() -> Path:
    tag = f'py{sys.version_info.major}{sys.version_info.minor}'
    base = os.environ.get('LOCALAPPDATA')
    if base:
        return Path(base) / 'CorePulse' / 'runtime' / tag / f'v{VERSION}'
    return Path(tempfile.gettempdir()) / 'CorePulseRuntime' / tag / f'v{VERSION}'


def _venv_python(venv: Path) -> Path:
    return venv / 'Scripts' / 'python.exe'


def _print_bootstrap(message: str) -> None:
    try:
        print(f'[CorePulse] {message}', flush=True)
    except Exception:
        pass


def _run(cmd: list[str], *, cwd: Path | None = None) -> int:
    _print_bootstrap('> ' + ' '.join(f'"{x}"' if ' ' in str(x) else str(x) for x in cmd))
    try:
        return subprocess.call(cmd, cwd=str(cwd) if cwd else None)
    except OSError as exc:
        _print_bootstrap(f'No se pudo ejecutar el comando: {exc}')
        return 1


def _validate_runtime(python_exe: Path) -> tuple[bool, str]:
    root = project_root()
    validator = root / 'tools' / 'validate_python_runtime.py'
    report = runtime_report_path()
    if not validator.is_file():
        return False, f'Falta {validator}'
    code = _run([str(python_exe), str(validator), '--output', str(report)], cwd=root)
    if code == 0:
        return True, ''
    detail = ''
    try:
        payload = json.loads(report.read_text(encoding='utf-8'))
        errors = payload.get('errors') or []
        detail = '\n'.join(f'- {x}' for x in errors)
    except Exception:
        pass
    return False, detail or f'La validación terminó con código {code}.'


def _install_requirements(python_exe: Path) -> tuple[bool, str]:
    root = project_root()
    lock = root / 'requirements-runtime-lock.txt'
    flex = root / 'requirements-runtime-flex.txt'
    if not lock.is_file() or not flex.is_file():
        return False, 'Faltan requirements-runtime-lock.txt o requirements-runtime-flex.txt.'

    _print_bootstrap('Preparando pip / setuptools / wheel…')
    if _run([str(python_exe), '-m', 'pip', 'install', '--upgrade', 'pip', 'setuptools', 'wheel'], cwd=root) != 0:
        return False, 'No se pudo preparar pip/setuptools/wheel.'

    _print_bootstrap('Instalando el lock reproducible…')
    code = _run([str(python_exe), '-m', 'pip', 'install', '--prefer-binary', '-r', str(lock)], cwd=root)
    if code == 0:
        return True, 'LOCK'

    _print_bootstrap('El lock exacto no está disponible para este minor. Probando resolución adaptable…')
    code = _run([str(python_exe), '-m', 'pip', 'install', '--upgrade', '--prefer-binary', '-r', str(flex)], cwd=root)
    if code != 0:
        return False, (
            'No existe una combinación instalable del stack completo de CorePulse '
            f'para Python {platform.python_version()}.'
        )
    return True, 'FLEX'


def provision_runtime_for_current_python() -> Path:
    """Crea y valida un runtime aislado usando el mismo CPython que abrió CorePulse."""
    enforce_minimum_python()
    root = project_root()
    venv = _runtime_root_for_current_python()
    target = _venv_python(venv)

    _print_bootstrap(
        f'Python {platform.python_version()} x64 detectado sin dependencias completas. '
        'Creando runtime automático…'
    )

    # Si ya existe un venv de esta versión de CorePulse, se reutiliza sólo si valida.
    if target.is_file():
        ok, _ = _validate_runtime(target)
        if ok:
            runtime_pointer_path().write_text(str(target.resolve()), encoding='utf-8')
            _print_bootstrap(f'Runtime existente validado: {target}')
            return target.resolve()
        _print_bootstrap('El runtime existente no pasó validación; se reconstruirá.')
        try:
            shutil.rmtree(venv)
        except Exception as exc:
            raise RuntimeError(f'No se pudo reconstruir el runtime {venv}: {exc}') from exc

    venv.parent.mkdir(parents=True, exist_ok=True)
    _print_bootstrap(f'Creando entorno aislado en {venv}')
    code = _run([sys.executable, '-m', 'venv', str(venv)], cwd=root)
    if code != 0 or not target.is_file():
        raise RuntimeError(
            'No se pudo crear el entorno virtual automático. '
            f'Python usado: {sys.executable}'
        )

    ok, resolution = _install_requirements(target)
    if not ok:
        raise RuntimeError(resolution)

    _print_bootstrap('Validando el stack completo de CorePulse…')
    valid, detail = _validate_runtime(target)
    if not valid:
        raise RuntimeError(
            'Python fue detectado, pero el stack completo de CorePulse no pasó validación.\n'
            f'{detail}\n\n'
            f'Reporte: {runtime_report_path()}'
        )

    runtime_pointer_path().write_text(str(target.resolve()), encoding='utf-8')
    _print_bootstrap(
        f'Runtime validado correctamente ({resolution}) para Python '
        f'{sys.version_info.major}.{sys.version_info.minor}. Reabriendo CorePulse…'
    )
    return target.resolve()


def bootstrap_validated_runtime(entry_script: str | os.PathLike | None = None) -> bool:
    """Garantiza dependencias antes de que el resto de CorePulse sea importado.

    Flujo:
    1. Si el Python actual ya tiene los imports esenciales, continúa sin tocar nada.
    2. Si falta alguno, intenta un runtime validado previamente.
    3. Si no existe, crea uno automáticamente para el mismo minor de Python,
       instala dependencias, valida TODO el stack y reejecuta CorePulse allí.
    """
    if getattr(sys, 'frozen', False) or os.environ.get(_BOOTSTRAPPED_ENV) == '1':
        return False

    missing = missing_source_imports()
    if not missing:
        return False

    enforce_minimum_python()
    target = validated_runtime_python()
    # Cada minor usa su propio runtime. Si el proyecto fue abierto antes con
    # otro Python, no reciclamos ese intérprete: se prepara el minor actual.
    if target is not None and not _runtime_matches_current_minor(target):
        target = None

    if target is None:
        disabled = os.environ.get(_AUTO_BOOTSTRAP_ENV, '1').strip().lower() in {'0', 'false', 'no', 'off'}
        if disabled:
            raise RuntimeError(
                'Faltan dependencias de CorePulse: ' + ', '.join(missing) + '. '
                'El bootstrap automático está desactivado.'
            )
        target = provision_runtime_for_current_python()

    try:
        if Path(sys.executable).resolve() == target.resolve():
            # Evita caer después en un ModuleNotFoundError poco claro.
            raise RuntimeError(
                'El runtime registrado sigue incompleto. Faltan: ' + ', '.join(missing)
            )
    except OSError:
        pass

    script = Path(entry_script or sys.argv[0]).resolve()
    env = os.environ.copy()
    env[_BOOTSTRAPPED_ENV] = '1'
    env['COREPULSE_REQUESTED_PYTHON'] = sys.executable
    os.execve(str(target), [str(target), str(script), *sys.argv[1:]], env)
    return True


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
        'python_policy': f'{MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ x64',
        'minimum_supported': state.minimum_supported,
        'pythonnet_available': state.sensor_bridge_importable,
        'hardwaremonitor_available': state.hardwaremonitor_importable,
        'deep_sensors_available': state.full_sensor_stack_importable,
        'no_artificial_upper_bound': True,
        'automatic_runtime_bootstrap': True,
        'runtime_pointer': str(validated_runtime_python() or ''),
    }
