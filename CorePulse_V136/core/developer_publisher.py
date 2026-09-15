"""Publicación segura de CorePulse desde una rama Git de desarrollo.

V135 inició el flujo de publicación segura; V136 mejora la detección del repositorio sin tocar las
carpetas académicas/protegidas del repositorio. La operación sólo puede afectar
carpetas CorePulse_Vxxx de primer nivel y bloquea ramas principales.

No guarda credenciales: usa la autenticación Git ya configurada en Windows.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
from typing import Callable
import zipfile

from core.runtime_paths import data_path, source_root
from core.version import VERSION, VERSION_LABEL

PROTECTED_REPO_DIRS = ("FASE 1", "FASE 2", "FASE 3")
BLOCKED_BRANCHES = {"main", "master", "trunk"}
COREPULSE_FOLDER_RE = re.compile(r"(?i)^CorePulse_(?:V)?\d+$")
TARGET_FOLDER = f"CorePulse_V{VERSION}"

_IGNORE_DIRS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
_IGNORE_SUFFIXES = {".pyc", ".pyo"}


class PublishError(RuntimeError):
    pass


def _run_git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    git = shutil.which("git")
    if not git:
        raise PublishError("Git no está instalado o no está disponible en PATH.")
    proc = subprocess.run(
        [git, "-C", str(repo), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
    )
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise PublishError(detail or f"Git devolvió código {proc.returncode}.")
    return proc


def find_git_root(start: str | os.PathLike | None = None) -> Path | None:
    """Devuelve la raíz Git que contiene *start*, si existe.

    La selección puede ser la raíz o cualquier subcarpeta del checkout. No
    intenta adivinar otros repositorios: esa búsqueda se hace por separado para
    poder explicarle al usuario qué se detectó.
    """
    start_path = Path(start).expanduser().resolve() if start else source_root().resolve()
    if start_path.is_file():
        start_path = start_path.parent
    try:
        proc = _run_git(start_path, "rev-parse", "--show-toplevel")
        root = Path(proc.stdout.strip()).resolve()
        return root if root.is_dir() else None
    except Exception:
        return None


def _looks_like_git_checkout(path: Path) -> bool:
    try:
        return path.is_dir() and (path / ".git").exists()
    except Exception:
        return False


def discover_nearby_git_roots(start: str | os.PathLike | None) -> list[Path]:
    """Busca clones Git cercanos sin recorrer el disco completo.

    Es común abrir CorePulse desde una copia ZIP ``DiagnosticPC-main`` y tener
    el clon real (por ejemplo ``DiagnosticPC-Maxi``) como carpeta hermana en el
    Escritorio. V136 revisa sólo la selección, sus padres inmediatos y sus
    carpetas hermanas; nunca hace una búsqueda recursiva costosa.
    """
    if not start:
        return []
    try:
        selected = Path(start).expanduser().resolve()
    except Exception:
        return []
    if selected.is_file():
        selected = selected.parent

    anchors: list[Path] = []
    current = selected
    for _ in range(4):
        if current not in anchors:
            anchors.append(current)
        parent = current.parent
        if parent == current:
            break
        current = parent

    roots: dict[str, Path] = {}
    for anchor in anchors:
        direct = find_git_root(anchor)
        if direct is not None:
            roots[str(direct).casefold()] = direct
        # Sólo inspecciona hijos directos del padre/ancestro. Esto encuentra un
        # clon hermano sin entrar recursivamente en proyectos grandes.
        try:
            children = list(anchor.iterdir())[:200]
        except Exception:
            children = []
        for child in children:
            if not _looks_like_git_checkout(child):
                continue
            root = find_git_root(child)
            if root is not None:
                roots[str(root).casefold()] = root

    return sorted(roots.values(), key=lambda item: str(item).casefold())


def _repo_candidate_score(repo: Path) -> int:
    score = 0
    name = repo.name.casefold()
    if "diagnosticpc" in name:
        score += 30
    if all((repo / part).is_dir() for part in PROTECTED_REPO_DIRS):
        score += 60
    try:
        remote = _run_git(repo, "remote", "get-url", "origin", check=False).stdout.strip().casefold()
    except Exception:
        remote = ""
    if "diagnosticpc" in remote:
        score += 100
    try:
        branch = _run_git(repo, "branch", "--show-current", check=False).stdout.strip().casefold()
    except Exception:
        branch = ""
    if branch and branch not in BLOCKED_BRANCHES:
        score += 20
    return score


def resolve_git_root(start: str | os.PathLike | None = None) -> tuple[Path | None, dict]:
    """Resuelve una selección a un checkout Git y devuelve evidencia.

    Primero acepta la carpeta o cualquier subcarpeta del repo. Si no pertenece a
    Git, busca clones cercanos. Sólo selecciona automáticamente un candidato
    cuando existe un mejor candidato inequívoco.
    """
    exact = find_git_root(start)
    if exact is not None:
        return exact, {"auto_detected": False, "candidates": [str(exact)], "selected": str(start or "")}

    candidates = discover_nearby_git_roots(start)
    if not candidates:
        return None, {"auto_detected": False, "candidates": [], "selected": str(start or "")}

    ranked = sorted((( _repo_candidate_score(repo), repo) for repo in candidates), key=lambda item: (-item[0], str(item[1]).casefold()))
    best_score, best = ranked[0]
    second_score = ranked[1][0] if len(ranked) > 1 else -1
    if len(ranked) == 1 or best_score > second_score:
        return best, {
            "auto_detected": True,
            "candidates": [str(repo) for _, repo in ranked],
            "selected": str(start or ""),
            "note": f"La carpeta seleccionada no era un checkout Git. Se detectó automáticamente el clon: {best}",
        }
    return None, {
        "auto_detected": False,
        "candidates": [str(repo) for _, repo in ranked],
        "selected": str(start or ""),
        "note": "Se encontraron varios repositorios Git cercanos. Selecciona explícitamente el clon que quieres publicar.",
    }


def _git_lines(repo: Path, *args: str) -> list[str]:
    text = _run_git(repo, *args).stdout
    return [line.strip() for line in text.splitlines() if line.strip()]


def _top_level(path: str) -> str:
    path = str(path).replace("\\", "/").lstrip("./")
    return path.split("/", 1)[0] if path else ""


def _protected_status(repo: Path) -> tuple[str, ...]:
    proc = _run_git(repo, "status", "--porcelain=v1", "--", *PROTECTED_REPO_DIRS)
    return tuple(line.rstrip() for line in proc.stdout.splitlines())


def _tracked_corepulse_dirs(repo: Path) -> list[str]:
    try:
        names = _git_lines(repo, "ls-tree", "-d", "--name-only", "HEAD")
    except PublishError:
        names = []
    return sorted(name for name in names if COREPULSE_FOLDER_RE.fullmatch(name))


def _source_top_in_repo(repo: Path) -> str | None:
    src = source_root().resolve()
    try:
        rel = src.relative_to(repo)
    except ValueError:
        return None
    return rel.parts[0] if rel.parts else None


def inspect_publish_context(repo_hint: str | os.PathLike | None = None) -> dict:
    """Inspecciona el repositorio sin modificarlo."""
    root, resolution = resolve_git_root(repo_hint)
    if root is None:
        selected = str(repo_hint or "").strip()
        candidates = list(resolution.get("candidates") or [])
        if candidates:
            blocker = (
                "La carpeta seleccionada no pertenece a un repositorio Git y hay varios clones cercanos. "
                "Selecciona la raíz del clon correcto (la carpeta que contiene .git)."
            )
        elif selected:
            blocker = (
                "La carpeta seleccionada no contiene metadatos Git (.git). "
                "Selecciona el clon creado con 'git clone' (por ejemplo DiagnosticPC-Maxi), "
                "no una carpeta descargada o extraída como ZIP."
            )
        else:
            blocker = "No se detectó un repositorio Git. Selecciona la raíz del clon DiagnosticPC."
        return {
            "available": False,
            "can_publish": False,
            "blockers": [blocker],
            "target_folder": TARGET_FOLDER,
            "version": VERSION_LABEL,
            "selected_hint": selected,
            "nearby_candidates": candidates,
            "resolution_note": resolution.get("note") or "",
        }

    blockers: list[str] = []
    branch = _run_git(root, "branch", "--show-current", check=False).stdout.strip()
    if not branch:
        blockers.append("Git está en detached HEAD. Selecciona una rama de desarrollo.")
    elif branch.casefold() in BLOCKED_BRANCHES:
        blockers.append(f"La rama '{branch}' está protegida. CorePulse nunca publica directamente sobre main/master/trunk.")

    protected = {name: (root / name).is_dir() for name in PROTECTED_REPO_DIRS}
    missing = [name for name, exists in protected.items() if not exists]
    if missing:
        blockers.append("Faltan carpetas protegidas: " + ", ".join(missing))

    remote_proc = _run_git(root, "remote", "get-url", "origin", check=False)
    remote = remote_proc.stdout.strip() if remote_proc.returncode == 0 else ""
    if not remote:
        blockers.append("El repositorio no tiene un remoto 'origin' configurado.")

    tracked = _tracked_corepulse_dirs(root)
    src_top = _source_top_in_repo(root)
    allowed_tops = set(tracked) | {TARGET_FOLDER}
    if src_top and COREPULSE_FOLDER_RE.fullmatch(src_top):
        allowed_tops.add(src_top)

    cached = _git_lines(root, "diff", "--cached", "--name-only")
    staged_outside = [p for p in cached if _top_level(p) not in allowed_tops]
    if staged_outside:
        blockers.append(
            "Hay cambios ya preparados fuera de CorePulse. Haz commit/unstage antes de publicar: "
            + ", ".join(staged_outside[:4])
            + ("…" if len(staged_outside) > 4 else "")
        )

    # Si el CorePulse anterior no es el código que está ejecutándose, exigimos
    # que esté limpio antes de eliminarlo. Así nunca borramos cambios locales.
    dirty_old: list[str] = []
    for name in tracked:
        if name == TARGET_FOLDER or name == src_top:
            continue
        status = _run_git(root, "status", "--porcelain=v1", "--", name).stdout.strip()
        if status:
            dirty_old.append(name)
    if dirty_old:
        blockers.append("Hay cambios locales sin publicar en: " + ", ".join(dirty_old))

    return {
        "available": True,
        "can_publish": not blockers,
        "blockers": blockers,
        "repo_root": str(root),
        "repo_name": root.name,
        "branch": branch or "N/A",
        "remote": remote or "N/A",
        "protected": protected,
        "tracked_corepulse": tracked,
        "source_root": str(source_root().resolve()),
        "source_top": src_top,
        "target_folder": TARGET_FOLDER,
        "version": VERSION_LABEL,
        "protected_dirty": list(_protected_status(root)),
        "staged_outside": staged_outside,
        "selected_hint": str(repo_hint or ""),
        "auto_detected": bool(resolution.get("auto_detected")),
        "nearby_candidates": list(resolution.get("candidates") or []),
        "resolution_note": resolution.get("note") or "",
    }


def _ignore_copy(directory: str, names: list[str]) -> set[str]:
    ignored: set[str] = set()
    for name in names:
        if name in _IGNORE_DIRS:
            ignored.add(name)
        elif Path(name).suffix.casefold() in _IGNORE_SUFFIXES:
            ignored.add(name)
        elif name.endswith(".log"):
            ignored.add(name)
    return ignored


def _copy_current_project(source: Path, target: Path) -> None:
    if target.exists():
        raise PublishError(f"La carpeta destino ya existe: {target.name}. Revísala antes de publicar.")
    shutil.copytree(source, target, ignore=_ignore_copy)


def _staged_paths(repo: Path) -> list[str]:
    return _git_lines(repo, "diff", "--cached", "--name-only")


def _validate_staged_scope(repo: Path, allowed_tops: set[str]) -> list[str]:
    staged = _staged_paths(repo)
    invalid = [p for p in staged if _top_level(p) not in allowed_tops]
    if invalid:
        raise PublishError(
            "Seguridad: Git intentó incluir archivos fuera de CorePulse: "
            + ", ".join(invalid[:8])
            + ("…" if len(invalid) > 8 else "")
        )
    if not staged:
        raise PublishError("No hay cambios de CorePulse para publicar.")
    return staged


def _write_release_assets(project_dir: Path) -> dict:
    out = data_path("updates", "publications", VERSION_LABEL)
    out.mkdir(parents=True, exist_ok=True)
    zip_path = out / f"{TARGET_FOLDER}.zip"
    temp = zip_path.with_suffix(".zip.part")
    temp.unlink(missing_ok=True)
    with zipfile.ZipFile(temp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in project_dir.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(project_dir.parent)
            if any(part in _IGNORE_DIRS for part in rel.parts):
                continue
            if path.suffix.casefold() in _IGNORE_SUFFIXES or path.name.endswith(".log"):
                continue
            archive.write(path, rel.as_posix())
    os.replace(temp, zip_path)
    digest = hashlib.sha256()
    with zip_path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    sha = digest.hexdigest()
    sha_path = out / f"{zip_path.name}.sha256"
    sha_path.write_text(f"{sha}  {zip_path.name}\n", encoding="utf-8")
    return {"zip": str(zip_path), "sha256_file": str(sha_path), "sha256": sha}


def publish_current_version(
    repo_hint: str | os.PathLike,
    commit_message: str,
    *,
    progress: Callable[[str], None] | None = None,
) -> dict:
    """Copia la versión actual, hace commit y push sólo en una rama segura.

    FASE 1/2/3 se validan antes y después; nunca se incluyen en el staging. Si
    falla antes de crear el commit, revierte únicamente la preparación CorePulse.
    """
    message = str(commit_message or "").strip()
    if not message:
        raise PublishError("Escribe un mensaje de commit antes de publicar.")

    ctx = inspect_publish_context(repo_hint)
    if not ctx.get("can_publish"):
        raise PublishError("\n".join(ctx.get("blockers") or ["El repositorio no está listo para publicar."]))

    repo = Path(ctx["repo_root"]).resolve()
    source = source_root().resolve()
    target_name = TARGET_FOLDER
    target = repo / target_name
    tracked = list(ctx.get("tracked_corepulse") or [])
    source_top = ctx.get("source_top")
    allowed = set(tracked) | {target_name}
    if source_top and COREPULSE_FOLDER_RE.fullmatch(str(source_top)):
        allowed.add(str(source_top))

    protected_before = _protected_status(repo)
    created_target = False
    physically_removed: list[str] = []
    index_only_removed: list[str] = []
    committed = False

    def note(text: str) -> None:
        if progress:
            progress(text)

    try:
        note(f"Repositorio: {repo}")
        note(f"Rama segura: {ctx['branch']}")
        note("FASE 1, FASE 2 y FASE 3 verificadas.")

        source_is_target = source == target.resolve() if target.exists() else False
        if not source_is_target:
            note(f"Preparando {target_name}…")
            _copy_current_project(source, target)
            created_target = True

        # Elimina del índice/árbol remoto las versiones CorePulse anteriores. Si una
        # de ellas contiene el proceso actual, sólo se quita del índice para no borrar
        # archivos mientras Python está ejecutándose.
        for old in tracked:
            if old == target_name:
                continue
            if source_top == old:
                note(f"Retirando {old} del próximo commit sin borrar la sesión actual…")
                _run_git(repo, "rm", "-r", "--cached", "--ignore-unmatch", "--", old)
                index_only_removed.append(old)
            else:
                note(f"Retirando versión anterior {old}…")
                _run_git(repo, "rm", "-r", "--ignore-unmatch", "--", old)
                physically_removed.append(old)

        note(f"Preparando cambios de {target_name}…")
        _run_git(repo, "add", "-A", "--", target_name)
        staged = _validate_staged_scope(repo, allowed)

        protected_after_stage = _protected_status(repo)
        if protected_after_stage != protected_before:
            raise PublishError("Seguridad: el estado de FASE 1/2/3 cambió durante la preparación. Publicación cancelada.")

        note(f"Commit: {message.splitlines()[0][:80]}")
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", delete=False) as handle:
            handle.write(message + "\n")
            msg_path = handle.name
        try:
            _run_git(repo, "commit", "-F", msg_path)
            committed = True
        finally:
            try:
                Path(msg_path).unlink()
            except Exception:
                pass

        commit = _run_git(repo, "rev-parse", "--short", "HEAD").stdout.strip()
        note(f"Commit creado: {commit}")
        note(f"Subiendo origin/{ctx['branch']}…")
        try:
            push = _run_git(repo, "push", "-u", "origin", str(ctx["branch"]))
        except Exception as exc:
            raise PublishError(
                f"El commit {commit} quedó creado localmente, pero el push falló. "
                f"Puedes reintentar 'git push' sin perder el commit.\n{exc}"
            ) from exc
        note("Push completado.")

        if _protected_status(repo) != protected_before:
            raise PublishError("La publicación terminó, pero el estado local de FASE 1/2/3 cambió inesperadamente. Revísalo antes de continuar.")

        project_dir = target if target.is_dir() else source
        note("Creando ZIP y SHA-256 para GitHub Release…")
        assets = _write_release_assets(project_dir)
        note("Paquete de Release listo.")

        return {
            "ok": True,
            "repo_root": str(repo),
            "branch": ctx["branch"],
            "remote": ctx["remote"],
            "commit": commit,
            "commit_message": message,
            "staged_count": len(staged),
            "target_folder": target_name,
            "protected": list(PROTECTED_REPO_DIRS),
            "release_assets": assets,
            "push_output": (push.stdout or push.stderr or "").strip(),
            "source_old_left_local": bool(source_top and source_top in tracked and source_top != target_name),
            "finished_at": time.time(),
        }
    except Exception:
        if not committed:
            # Revierte exclusivamente los paths CorePulse tocados por este flujo.
            try:
                for old in physically_removed:
                    _run_git(repo, "restore", "--source=HEAD", "--staged", "--worktree", "--", old, check=False)
                for old in index_only_removed:
                    _run_git(repo, "restore", "--staged", "--", old, check=False)
                _run_git(repo, "restore", "--staged", "--", target_name, check=False)
                if created_target and target.is_dir():
                    shutil.rmtree(target, ignore_errors=True)
            except Exception:
                pass
        raise


__all__ = [
    "PROTECTED_REPO_DIRS", "BLOCKED_BRANCHES", "TARGET_FOLDER", "PublishError",
    "find_git_root", "discover_nearby_git_roots", "resolve_git_root",
    "inspect_publish_context", "publish_current_version",
]
