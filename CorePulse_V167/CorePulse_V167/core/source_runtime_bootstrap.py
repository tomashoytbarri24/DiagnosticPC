"""Bootstrap mínimo del runtime de desarrollo/fuente de CorePulse.

Este módulo usa únicamente la biblioteca estándar y se ejecuta ANTES de importar
CustomTkinter, Matplotlib, Pillow o cualquier dependencia de terceros. En Windows,
una copia fuente de CorePulse siempre se ejecuta desde su runtime reproducible de ruta corta.
Si el entorno no existe o está incompleto, se delega a bootstrap_corepulse.py.

El EXE PyInstaller nunca pasa por esta ruta.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys

from core.runtime_venv_path import source_runtime_venv

_REQUIRED_IMPORTS = (
    "psutil",
    "customtkinter",
    "PIL",
    "matplotlib",
    "platformdirs",
)


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _venv_python(root: Path) -> Path:
    return source_runtime_venv(root) / "Scripts" / "python.exe"


def _venv_pythonw(root: Path) -> Path:
    return source_runtime_venv(root) / "Scripts" / "pythonw.exe"


def _same_executable(a: Path, b: Path) -> bool:
    try:
        return a.resolve() == b.resolve()
    except Exception:
        return os.path.normcase(os.path.abspath(str(a))) == os.path.normcase(os.path.abspath(str(b)))


def _venv_structurally_valid(root: Path) -> bool:
    """Sólo usa el runtime local como intérprete si es un venv real.

    Un entorno parcial puede conservar Scripts\\python.exe aunque falte
    pyvenv.cfg. Ejecutar el bootstrap con ese binario reproduce el fallo
    "No pyvenv.cfg file" y evita que CorePulse pueda autocurarse.
    """
    venv = source_runtime_venv(root)
    return (venv / "pyvenv.cfg").is_file() and _venv_python(root).is_file()


def _path_inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except Exception:
        return False


def _python312_x64_ok(prefix: list[str]) -> bool:
    """Comprueba un Python anfitrión antes de usarlo para reconstruir el runtime."""
    try:
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        proc = subprocess.run(
            [*prefix, "-c", (
                "import struct,sys; "
                "raise SystemExit(0 if sys.version_info[:2]==(3,12) "
                "and struct.calcsize('P')*8==64 else 9)"
            )],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
        return proc.returncode == 0
    except Exception:
        return False


def _bootstrap_command(root: Path, bootstrap: Path) -> list[str]:
    """Elige un Python seguro para reparar o reconstruir el runtime."""
    venv = source_runtime_venv(root)

    # Un venv completo puede reparar paquetes faltantes con su propio Python.
    # Si ni siquiera supera la sonda 3.12 x64, no se usa como autoridad.
    if _venv_structurally_valid(root):
        candidate = _venv_pythonw(root)
        if not candidate.is_file():
            candidate = _venv_python(root)
        prefix = [str(candidate)]
        if _python312_x64_ok(prefix):
            return [str(candidate), str(bootstrap)]

    # El Python Launcher permite seleccionar exactamente CPython 3.12 aunque
    # VS Code esté usando otra versión como intérprete global.
    py_launcher = shutil.which("py") or shutil.which("py.exe")
    if py_launcher:
        prefix = [str(py_launcher), "-3.12"]
        if _python312_x64_ok(prefix):
            return [*prefix, str(bootstrap)]

    # Si estamos dentro del runtime local, sys._base_executable suele apuntar
    # al CPython real que lo creó. Nunca usamos un ejecutable que viva dentro
    # del runtime que puede necesitar ser eliminado/recreado.
    candidates = (getattr(sys, "_base_executable", None), sys.executable, shutil.which("python"))
    seen: set[str] = set()
    for raw in candidates:
        if not raw:
            continue
        candidate = Path(str(raw))
        key = os.path.normcase(os.path.abspath(str(candidate)))
        if key in seen:
            continue
        seen.add(key)
        if not candidate.is_file() or _path_inside(candidate, venv):
            continue
        prefix = [str(candidate)]
        if _python312_x64_ok(prefix):
            return [str(candidate), str(bootstrap)]

    raise RuntimeError(
        "El runtime local de CorePulse está incompleto y no se encontró Python 3.12 x64 "
        "fuera de ese runtime para reconstruirlo."
    )


def _imports_ready() -> bool:
    for module in _REQUIRED_IMPORTS:
        try:
            if importlib.util.find_spec(module) is None:
                return False
        except Exception:
            return False
    return True


def _spawn_bootstrap_and_exit(entrypoint: str | None = None) -> None:
    root = _root()
    bootstrap = root / "bootstrap_corepulse.py"
    if not bootstrap.is_file():
        raise RuntimeError(f"Falta el bootstrap de CorePulse: {bootstrap}")

    env = os.environ.copy()
    if entrypoint:
        env["COREPULSE_BOOTSTRAP_ENTRYPOINT"] = str(entrypoint)

    # Un runtime parcial no puede ser autoridad para repararse a sí mismo.
    # Si falta pyvenv.cfg se usa el Python base/launcher y se recrea el venv.
    command = _bootstrap_command(root, bootstrap)

    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    subprocess.Popen(
        command,
        cwd=str(root),
        env=env,
        creationflags=creationflags,
    )
    raise SystemExit(0)


def ensure_source_runtime(entrypoint: str | None = None) -> None:
    """Asegura que el modo fuente use el runtime autoritativo de CorePulse.

    - frozen/EXE: no-op
    - no Windows: no-op (permite CI estructural)
    - COREPULSE_SKIP_SOURCE_BOOTSTRAP=1: escape explícito para mantenimiento
    - Windows fuente: si no está en .venv o faltan imports, lanza bootstrap y sale
    """
    if bool(getattr(sys, "frozen", False)):
        return
    if os.name != "nt":
        return
    if str(os.environ.get("COREPULSE_SKIP_SOURCE_BOOTSTRAP") or "").strip() == "1":
        return

    root = _root()
    local_python = _venv_python(root)
    local_pythonw = _venv_pythonw(root)
    current = Path(sys.executable)
    using_local = (
        (local_python.is_file() and _same_executable(current, local_python))
        or (local_pythonw.is_file() and _same_executable(current, local_pythonw))
    )
    if using_local and _imports_ready():
        if _venv_structurally_valid(root):
            return

    # Evita bucles si el bootstrap ya confirmó el entorno, pero vuelve a exigir
    # imports reales; un marcador nunca reemplaza la comprobación de capacidad.
    _spawn_bootstrap_and_exit(entrypoint=entrypoint)


__all__ = ["ensure_source_runtime"]
