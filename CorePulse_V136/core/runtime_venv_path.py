"""Ruta corta y estable para el entorno Python de CorePulse.

El runtime fuente debe vivir fuera de la carpeta del proyecto para evitar rutas
Win32 profundas, pero tampoco puede depender de LOCALAPPDATA: el Python 3.12 de
Microsoft Store virtualiza escrituras en AppData y puede crear el venv en una
ruta física distinta de la que CorePulse intenta abrir después.

Por eso Windows usa una ruta corta bajo el perfil real del usuario:
    %USERPROFILE%/.corepulse/runtime/py312_<hash-lock>

Este módulo usa sólo biblioteca estándar porque se importa antes de que el
runtime de terceros esté disponible.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path


def _lock_token(root: Path) -> str:
    lock = Path(root) / "requirements-runtime-lock.txt"
    try:
        data = lock.read_bytes()
    except Exception:
        data = str(Path(root).resolve()).encode("utf-8", "replace")
    return hashlib.sha256(data).hexdigest()[:12]


def _windows_user_root() -> Path:
    """Devuelve una base escribible que no sufra virtualización de AppData."""
    raw = str(os.environ.get("USERPROFILE") or "").strip()
    if raw:
        return Path(os.path.expandvars(os.path.expanduser(raw)))

    try:
        home = Path.home()
        if str(home).strip():
            return home
    except Exception:
        pass

    # Último fallback: TEMP. Sólo se usa si Windows no expone perfil de usuario.
    raw = str(os.environ.get("TEMP") or os.environ.get("TMP") or "").strip()
    if raw:
        return Path(os.path.expandvars(os.path.expanduser(raw)))

    return Path.cwd()


def source_runtime_venv(root: Path) -> Path:
    """Devuelve el venv fuente autoritativo de esta revisión de CorePulse."""
    root = Path(root)
    override = str(os.environ.get("COREPULSE_VENV") or "").strip()
    if override:
        return Path(os.path.expandvars(os.path.expanduser(override)))

    if os.name == "nt":
        return _windows_user_root() / ".corepulse" / "runtime" / f"py312_{_lock_token(root)}"

    return root / ".venv"


def source_runtime_python(root: Path, *, windowed: bool = False) -> Path:
    venv = source_runtime_venv(root)
    name = "pythonw.exe" if windowed else "python.exe"
    return venv / "Scripts" / name


__all__ = ["source_runtime_venv", "source_runtime_python"]
