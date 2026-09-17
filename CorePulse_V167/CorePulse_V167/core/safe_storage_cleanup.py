"""Escáner determinista de espacio eliminable para CorePulse.

Política:
- Sólo enumera archivos cuya ubicación y propósito están en una allowlist explícita.
- No clasifica documentos, descargas, juegos, instaladores, logs de diagnóstico o
  carpetas desconocidas como "basura".
- No sigue symlinks, junctions ni otros reparse points.
- La eliminación sólo acepta rutas que fueron escaneadas y vuelve a validar cada
  archivo contra la regla permitida antes de borrarlo.
- REAL_OR_NA: todos los tamaños y conteos provienen del sistema de archivos real.
"""
from __future__ import annotations

from dataclasses import dataclass
import fnmatch
import os
from pathlib import Path
import shutil
import stat
import tempfile
import time
from typing import Iterable

import psutil

POLICY = "ALLOWLIST_RECREATABLE_ONLY"
MIN_TEMP_AGE_SECONDS = 24 * 60 * 60


@dataclass(frozen=True)
class SafeCleanupRule:
    id: str
    label: str
    roots: tuple[Path, ...]
    patterns: tuple[str, ...] = ()
    recursive: bool = True
    min_age_seconds: int = 0


def _norm(path: Path | str) -> str:
    return os.path.normcase(os.path.abspath(os.fspath(path)))


def _is_reparse(path: Path) -> bool:
    """Detecta symlinks/junctions/reparse points sin seguirlos."""
    try:
        if path.is_symlink():
            return True
    except OSError:
        return True
    try:
        isjunction = getattr(os.path, "isjunction", None)
        if isjunction is not None and isjunction(path):
            return True
    except OSError:
        return True
    try:
        attrs = getattr(path.stat(follow_symlinks=False), "st_file_attributes", 0)
        reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        return bool(attrs & reparse_flag)
    except (OSError, TypeError):
        return False


def _unique_existing_dirs(paths: Iterable[Path | str | None]) -> tuple[Path, ...]:
    result: list[Path] = []
    seen: set[str] = set()
    for raw in paths:
        if not raw:
            continue
        try:
            path = Path(raw).expanduser()
            if not path.exists() or not path.is_dir():
                continue
            key = _norm(path)
        except (OSError, ValueError):
            continue
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return tuple(result)


def _windows_directory() -> Path | None:
    if os.name == "nt":
        try:
            import ctypes

            buffer = ctypes.create_unicode_buffer(32768)
            length = ctypes.windll.kernel32.GetWindowsDirectoryW(buffer, len(buffer))
            if 0 < length < len(buffer):
                path = Path(buffer.value)
                if path.exists():
                    return path
        except Exception:
            pass
    raw = os.environ.get("SystemRoot") or os.environ.get("WINDIR")
    if raw:
        try:
            path = Path(raw)
            if path.exists():
                return path
        except OSError:
            pass
    return None


def _local_appdata() -> Path | None:
    raw = os.environ.get("LOCALAPPDATA")
    if raw:
        path = Path(raw)
        try:
            if path.exists():
                return path
        except OSError:
            pass
    fallback = Path.home() / "AppData" / "Local"
    try:
        return fallback if fallback.exists() else None
    except OSError:
        return None




def _is_reasonable_temp_root(path: Path, windows: Path | None, local: Path | None) -> bool:
    """Impide que una variable TEMP mal configurada convierta una ruta amplia en objetivo."""
    try:
        absolute = Path(os.path.abspath(os.fspath(path)))
        drive, tail = os.path.splitdrive(str(absolute))
        if str(absolute) in (absolute.anchor, drive + os.sep if drive else os.sep):
            return False
        if absolute == Path.home():
            return False
        name = absolute.name.lower()
        if name not in {"temp", "tmp"}:
            return False
        if windows is not None and _norm(absolute) == _norm(windows):
            return False
        # AppData\Local\Temp y otras raíces TEMP dedicadas son aceptables; una
        # ruta padre amplia como AppData\Local no lo es por la comprobación del nombre.
        return True
    except (OSError, ValueError):
        return False


def safe_cleanup_rules() -> tuple[SafeCleanupRule, ...]:
    """Allowlist inicial deliberadamente pequeña y conservadora."""
    local = _local_appdata()
    windows = _windows_directory()

    user_temp_candidates: list[Path | str | None] = [
        os.environ.get("TEMP"),
        os.environ.get("TMP"),
        tempfile.gettempdir(),
        (local / "Temp") if local else None,
    ]

    user_temp = tuple(
        p for p in _unique_existing_dirs(user_temp_candidates)
        if _is_reasonable_temp_root(p, windows, local)
    )
    windows_temp = _unique_existing_dirs(((windows / "Temp") if windows else None,))
    thumbnail_root = _unique_existing_dirs(((local / "Microsoft" / "Windows" / "Explorer") if local else None,))

    # Si TEMP apunta exactamente a Windows\Temp, se contabiliza sólo en la regla
    # del sistema para evitar duplicar bytes/candidatos.
    windows_keys = {_norm(p) for p in windows_temp}
    user_temp = tuple(p for p in user_temp if _norm(p) not in windows_keys)

    return (
        SafeCleanupRule(
            id="user_temp",
            label="Temporales del usuario",
            roots=user_temp,
            recursive=True,
            min_age_seconds=MIN_TEMP_AGE_SECONDS,
        ),
        SafeCleanupRule(
            id="windows_temp",
            label="Temporales de Windows",
            roots=windows_temp,
            recursive=True,
            min_age_seconds=MIN_TEMP_AGE_SECONDS,
        ),
        SafeCleanupRule(
            id="thumbnail_cache",
            label="Caché de miniaturas",
            roots=thumbnail_root,
            patterns=("thumbcache_*.db", "thumbcache*.db"),
            recursive=False,
            min_age_seconds=0,
        ),
    )


def _drive_type(mountpoint: str) -> int | None:
    if os.name != "nt":
        return None
    try:
        import ctypes

        return int(ctypes.windll.kernel32.GetDriveTypeW(str(mountpoint)))
    except Exception:
        return None


def list_local_storage_units() -> list[dict]:
    """Devuelve volúmenes locales utilizables sin recorrer su contenido."""
    rows: list[dict] = []
    seen: set[str] = set()
    for part in psutil.disk_partitions(all=False):
        mountpoint = str(part.mountpoint or "")
        if not mountpoint:
            continue
        key = os.path.normcase(os.path.abspath(mountpoint))
        if key in seen:
            continue
        if os.name == "nt":
            dtype = _drive_type(mountpoint)
            # DRIVE_FIXED=3. Se excluyen red, ópticos y removibles de la limpieza
            # automática. Si la API no responde, se conserva sólo una raíz con letra.
            if dtype is not None and dtype != 3:
                continue
            drive, _ = os.path.splitdrive(mountpoint)
            if not drive:
                continue
        try:
            usage = shutil.disk_usage(mountpoint)
        except (PermissionError, OSError):
            continue
        seen.add(key)
        used = int(usage.total - usage.free)
        rows.append(
            {
                "mountpoint": mountpoint,
                "fstype": str(part.fstype or ""),
                "total_bytes": int(usage.total),
                "used_bytes": used,
                "free_bytes": int(usage.free),
                "used_percent": (used / usage.total * 100.0) if usage.total else 0.0,
            }
        )
    rows.sort(key=lambda row: os.path.normcase(row["mountpoint"]))
    return rows


def _unit_for_path(path: Path, units: list[dict]) -> str | None:
    p = _norm(path)
    best: tuple[int, str] | None = None
    for unit in units:
        mount = _norm(unit["mountpoint"])
        try:
            common = os.path.commonpath((p, mount))
        except ValueError:
            continue
        if os.path.normcase(common) != os.path.normcase(mount):
            continue
        candidate = (len(mount), unit["mountpoint"])
        if best is None or candidate[0] > best[0]:
            best = candidate
    return best[1] if best else None


def _is_deletable_now(path: Path) -> bool:
    """Comprueba permiso/compartición de borrado sin modificar el archivo."""
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            DELETE = 0x00010000
            FILE_READ_ATTRIBUTES = 0x00000080
            FILE_SHARE_READ = 0x00000001
            FILE_SHARE_WRITE = 0x00000002
            FILE_SHARE_DELETE = 0x00000004
            OPEN_EXISTING = 3
            FILE_ATTRIBUTE_NORMAL = 0x00000080
            INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value
            kernel32 = ctypes.windll.kernel32
            kernel32.CreateFileW.argtypes = [
                wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
            ]
            kernel32.CreateFileW.restype = wintypes.HANDLE
            handle = kernel32.CreateFileW(
                str(path), DELETE | FILE_READ_ATTRIBUTES,
                FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                None, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, None,
            )
            if handle == INVALID_HANDLE_VALUE or handle in (None, 0):
                return False
            kernel32.CloseHandle(handle)
            return True
        except Exception:
            return False
    try:
        return os.access(path, os.W_OK) and os.access(path.parent, os.W_OK)
    except OSError:
        return False


def _matches_patterns(path: Path, patterns: tuple[str, ...]) -> bool:
    if not patterns:
        return True
    name = path.name.lower()
    return any(fnmatch.fnmatch(name, pattern.lower()) for pattern in patterns)


def _path_inside(path: Path, root: Path) -> bool:
    try:
        p = _norm(path)
        r = _norm(root)
        return os.path.normcase(os.path.commonpath((p, r))) == os.path.normcase(r)
    except (ValueError, OSError):
        return False


def _iter_rule_files(rule: SafeCleanupRule, now: float):
    for root in rule.roots:
        try:
            if _is_reparse(root):
                continue
        except OSError:
            continue

        if not rule.recursive:
            try:
                entries = list(os.scandir(root))
            except (PermissionError, OSError):
                continue
            for entry in entries:
                path = Path(entry.path)
                try:
                    if not entry.is_file(follow_symlinks=False) or _is_reparse(path):
                        continue
                    if not _matches_patterns(path, rule.patterns):
                        continue
                    st = entry.stat(follow_symlinks=False)
                    if getattr(st, "st_nlink", 1) > 1:
                        continue
                    if not _is_deletable_now(path):
                        continue
                    if rule.min_age_seconds and now - float(st.st_mtime) < rule.min_age_seconds:
                        continue
                    if int(st.st_size) <= 0:
                        continue
                    yield path, st
                except (PermissionError, OSError):
                    continue
            continue

        for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
            kept: list[str] = []
            for dirname in dirnames:
                child = Path(dirpath) / dirname
                try:
                    if not _is_reparse(child):
                        kept.append(dirname)
                except OSError:
                    pass
            dirnames[:] = kept
            for filename in filenames:
                path = Path(dirpath) / filename
                try:
                    if _is_reparse(path) or not _matches_patterns(path, rule.patterns):
                        continue
                    st = path.stat(follow_symlinks=False)
                    if not stat.S_ISREG(st.st_mode):
                        continue
                    if getattr(st, "st_nlink", 1) > 1:
                        continue
                    if not _is_deletable_now(path):
                        continue
                    if rule.min_age_seconds and now - float(st.st_mtime) < rule.min_age_seconds:
                        continue
                    if int(st.st_size) <= 0:
                        continue
                    yield path, st
                except (PermissionError, OSError):
                    continue


def scan_safe_storage_cleanup(now: float | None = None) -> dict:
    """Analiza unidades locales y devuelve sólo candidatos eliminables."""
    now = float(time.time() if now is None else now)
    units = list_local_storage_units()
    categories: list[dict] = []
    candidates: list[dict] = []
    seen_files: set[str] = set()
    errors = 0

    for rule in safe_cleanup_rules():
        cat_bytes = 0
        cat_files = 0
        cat_candidates: list[dict] = []
        for path, st in _iter_rule_files(rule, now):
            key = _norm(path)
            if key in seen_files:
                continue
            seen_files.add(key)
            unit = _unit_for_path(path, units)
            # Sólo candidatos ubicados realmente en una unidad local enumerada.
            if units and unit is None:
                continue
            item = {
                "path": str(path),
                "size": int(st.st_size),
                "mtime": float(st.st_mtime),
                "rule_id": rule.id,
                "label": rule.label,
                "root": str(next((r for r in rule.roots if _path_inside(path, r)), rule.roots[0] if rule.roots else "")),
                "unit": unit,
            }
            cat_candidates.append(item)
            candidates.append(item)
            cat_bytes += int(st.st_size)
            cat_files += 1
        if cat_files:
            categories.append(
                {
                    "id": rule.id,
                    "label": rule.label,
                    "bytes": cat_bytes,
                    "files": cat_files,
                }
            )

    by_unit: dict[str, dict] = {}
    for unit in units:
        by_unit[unit["mountpoint"]] = {
            **unit,
            "cleanup_bytes": 0,
            "cleanup_files": 0,
        }
    for item in candidates:
        mount = item.get("unit")
        if mount in by_unit:
            by_unit[mount]["cleanup_bytes"] += int(item["size"])
            by_unit[mount]["cleanup_files"] += 1

    return {
        "policy": POLICY,
        "scanned_at": now,
        "units": list(by_unit.values()),
        "units_scanned": len(units),
        "categories": categories,
        "candidates": candidates,
        "total_bytes": sum(int(row["bytes"]) for row in categories),
        "total_files": sum(int(row["files"]) for row in categories),
        "errors": errors,
    }


def _current_rule_map() -> dict[str, SafeCleanupRule]:
    return {rule.id: rule for rule in safe_cleanup_rules()}


def _candidate_still_allowed(item: dict, rule: SafeCleanupRule, now: float) -> tuple[Path, os.stat_result] | None:
    try:
        path = Path(str(item.get("path") or ""))
        if not path.exists() or _is_reparse(path):
            return None
        if not any(_path_inside(path, root) for root in rule.roots):
            return None
        if not _matches_patterns(path, rule.patterns):
            return None
        st = path.stat(follow_symlinks=False)
        if not stat.S_ISREG(st.st_mode) or getattr(st, "st_nlink", 1) > 1:
            return None
        if not _is_deletable_now(path):
            return None
        if rule.min_age_seconds and now - float(st.st_mtime) < rule.min_age_seconds:
            return None
        # No se borra un archivo que cambió desde el análisis.
        if int(st.st_size) != int(item.get("size") or -1):
            return None
        if abs(float(st.st_mtime) - float(item.get("mtime") or 0.0)) > 1.0:
            return None
        return path, st
    except (OSError, ValueError, TypeError):
        return None


def delete_scanned_candidates(scan: dict) -> dict:
    """Elimina únicamente los candidatos exactos del último análisis."""
    rules = _current_rule_map()
    now = time.time()
    candidates = list(scan.get("candidates") or ())

    touched_units = sorted({str(item.get("unit")) for item in candidates if item.get("unit")})
    free_before: dict[str, int] = {}
    for mount in touched_units:
        try:
            free_before[mount] = int(shutil.disk_usage(mount).free)
        except (PermissionError, OSError):
            pass

    deleted_bytes = 0
    deleted_files = 0
    skipped = 0
    by_category: dict[str, dict] = {}

    for item in candidates:
        rule = rules.get(str(item.get("rule_id") or ""))
        if rule is None:
            skipped += 1
            continue
        allowed = _candidate_still_allowed(item, rule, now)
        if allowed is None:
            skipped += 1
            continue
        path, st = allowed
        try:
            size = int(st.st_size)
            path.unlink()
            deleted_bytes += size
            deleted_files += 1
            row = by_category.setdefault(rule.id, {"label": rule.label, "bytes": 0, "files": 0})
            row["bytes"] += size
            row["files"] += 1
        except (PermissionError, OSError):
            skipped += 1

    measured_delta = 0
    measured_units = 0
    for mount, before in free_before.items():
        try:
            after = int(shutil.disk_usage(mount).free)
        except (PermissionError, OSError):
            continue
        measured_units += 1
        measured_delta += after - before

    after_scan = scan_safe_storage_cleanup()
    return {
        "policy": POLICY,
        "deleted_bytes": deleted_bytes,
        "deleted_files": deleted_files,
        "skipped": skipped,
        "by_category": by_category,
        "free_space_delta_bytes": measured_delta if measured_units else None,
        "measured_units": measured_units,
        "after": after_scan,
    }
