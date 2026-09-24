"""Rutas autoritativas de CorePulse en modo fuente y PyInstaller ONEDIR.

Recursos de sólo lectura (assets, tools, scripts auxiliares de distribución) se
resuelven desde el bundle. Estado mutable, historiales, preferencias, snapshots,
logs y configuración viven fuera de la instalación, en AppData del usuario.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys

try:
    from platformdirs import user_cache_dir, user_config_dir, user_data_dir, user_log_dir
except Exception:  # fallback sólo para un entorno incompleto
    user_cache_dir = user_config_dir = user_data_dir = user_log_dir = None

APP_NAME = "CorePulse"
APP_AUTHOR = False  # evita AppData\CorePulse\CorePulse en Windows


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def source_root() -> Path:
    return Path(__file__).resolve().parents[1]


def executable_root() -> Path:
    """Carpeta de CorePulse.exe o raíz del proyecto en modo fuente."""
    return Path(sys.executable).resolve().parent if is_frozen() else source_root()


def resource_root() -> Path:
    """Raíz de recursos PyInstaller (`_internal`) o raíz del proyecto fuente."""
    if is_frozen():
        bundled = getattr(sys, "_MEIPASS", None)
        if bundled:
            return Path(bundled).resolve()
    return source_root()


def resource_path(*parts: str | os.PathLike) -> Path:
    return resource_root().joinpath(*(os.fspath(p) for p in parts))


def _fallback_local() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    return Path(base) if base else (Path.home() / ".corepulse")


def _platform_path(func, fallback: Path) -> Path:
    if func is not None:
        try:
            return Path(func(APP_NAME, APP_AUTHOR))
        except TypeError:
            try:
                return Path(func(APP_NAME))
            except Exception:
                pass
        except Exception:
            pass
    return fallback


def data_dir() -> Path:
    override = str(os.environ.get("COREPULSE_DATA_DIR") or "").strip()
    path = Path(override).expanduser() if override else _platform_path(
        user_data_dir, _fallback_local() / APP_NAME
    )
    path.mkdir(parents=True, exist_ok=True)
    return path


def state_dir() -> Path:
    path = data_dir() / "state"
    path.mkdir(parents=True, exist_ok=True)
    return path


def diagnostics_dir() -> Path:
    path = data_dir() / "diagnostics"
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_dir() -> Path:
    override = str(os.environ.get("COREPULSE_CONFIG_DIR") or "").strip()
    path = Path(override).expanduser() if override else _platform_path(
        user_config_dir, _fallback_local() / APP_NAME / "config"
    )
    path.mkdir(parents=True, exist_ok=True)
    return path


def cache_dir() -> Path:
    override = str(os.environ.get("COREPULSE_CACHE_DIR") or "").strip()
    path = Path(override).expanduser() if override else _platform_path(
        user_cache_dir, _fallback_local() / APP_NAME / "cache"
    )
    path.mkdir(parents=True, exist_ok=True)
    return path


def log_dir() -> Path:
    override = str(os.environ.get("COREPULSE_LOG_DIR") or "").strip()
    path = Path(override).expanduser() if override else _platform_path(
        user_log_dir, _fallback_local() / APP_NAME / "logs"
    )
    path.mkdir(parents=True, exist_ok=True)
    return path


def data_path(*parts: str | os.PathLike) -> Path:
    return data_dir().joinpath(*(os.fspath(p) for p in parts))


def state_path(*parts: str | os.PathLike) -> Path:
    return state_dir().joinpath(*(os.fspath(p) for p in parts))


def diagnostics_path(*parts: str | os.PathLike) -> Path:
    return diagnostics_dir().joinpath(*(os.fspath(p) for p in parts))


def config_path(*parts: str | os.PathLike) -> Path:
    return config_dir().joinpath(*(os.fspath(p) for p in parts))


def cache_path(*parts: str | os.PathLike) -> Path:
    return cache_dir().joinpath(*(os.fspath(p) for p in parts))


def log_path(*parts: str | os.PathLike) -> Path:
    return log_dir().joinpath(*(os.fspath(p) for p in parts))


def env_candidates() -> list[Path]:
    """Orden: configuración de usuario, override portable junto al EXE, cwd."""
    values = [config_path(".env")]
    values.append((executable_root() if is_frozen() else source_root()) / ".env")
    try:
        values.append(Path.cwd() / ".env")
    except Exception:
        pass
    out: list[Path] = []
    seen: set[str] = set()
    for path in values:
        key = str(path).casefold()
        if key not in seen:
            seen.add(key)
            out.append(path)
    return out


def ensure_runtime_dirs() -> dict[str, str]:
    return {
        "data": str(data_dir()),
        "state": str(state_dir()),
        "diagnostics": str(diagnostics_dir()),
        "config": str(config_dir()),
        "cache": str(cache_dir()),
        "logs": str(log_dir()),
        "resources": str(resource_root()),
        "executable": str(executable_root()),
    }


__all__ = [
    "APP_NAME", "APP_AUTHOR", "is_frozen", "source_root", "executable_root",
    "resource_root", "resource_path", "data_dir", "state_dir", "diagnostics_dir",
    "config_dir", "cache_dir", "log_dir", "data_path", "state_path",
    "diagnostics_path", "config_path", "cache_path", "log_path", "env_candidates",
    "ensure_runtime_dirs",
]
