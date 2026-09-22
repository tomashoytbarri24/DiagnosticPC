"""Publicación Git segura y acotada para CorePulse.

V262 permite elegir explícitamente la rama remota de destino (desarrollo, main
estable u otra rama existente) sin cambiar de rama local. Cada publicación se
construye sobre el HEAD remoto elegido y contiene únicamente la carpeta de la
versión ejecutada. FASE 1/2/3, .github, versiones anteriores, HEAD, staging y
commits locales permanecen intactos.

No almacena credenciales: el push usa la autenticación Git ya configurada en
Windows. GitHub Actions/Releases siguen siendo responsabilidad del repositorio;
CorePulse sólo envía el código a la rama seleccionada.
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

from core.runtime_paths import data_path, source_root
from core.version import VERSION, VERSION_LABEL

PROTECTED_REPO_DIRS = ("FASE 1", "FASE 2", "FASE 3")
PROTECTED_REPO_ITEMS = (*PROTECTED_REPO_DIRS, ".github")
STABLE_BRANCHES = {"main", "master", "trunk"}
# Compatibilidad con imports antiguos: desde V262 main/master/trunk ya no se
# bloquean; se consideran destinos estables y exigen confirmación en la UI.
BLOCKED_BRANCHES: set[str] = set()
# Acepta nombres reales del proyecto, p. ej. CorePulse_V224_WINDOWS_... y las
# nomenclaturas antiguas CorePulse_V0.10.2.99w_.... La estructura del proyecto
# (main.py + core/version.py) termina de validar que sea una versión publicable.
COREPULSE_FOLDER_RE = re.compile(r"(?i)^(?:CorePulse[_ .-]*)?V[0-9][A-Za-z0-9._ -]*$")
TARGET_FOLDER = f"CorePulse_V{VERSION}"
PUBLISH_FOLDER = TARGET_FOLDER

_IGNORE_DIRS = {
    ".git", ".github", ".venv", "venv", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache",
}
_IGNORE_SUFFIXES = {".pyc", ".pyo"}


class PublishError(RuntimeError):
    pass


def _run_git(repo: Path, *args: str, check: bool = True, env: dict | None = None) -> subprocess.CompletedProcess:
    git = shutil.which("git")
    if not git:
        raise PublishError("Git no está instalado o no está disponible en PATH.")
    proc = subprocess.run(
        [git, "--literal-pathspecs", "-C", str(repo), *args],
        env={
            **{k: v for k, v in os.environ.items() if k not in {"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR"}},
            "GIT_OPTIONAL_LOCKS": "0",
            **(env or {}),
        },
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


def remote_branch_url(remote: str, branch: str) -> str:
    remote = str(remote or "").strip()
    branch = str(branch or "").strip()
    if not remote:
        return ""
    normalized = remote
    if remote.startswith("git@github.com:"):
        normalized = "https://github.com/" + remote.split(":", 1)[1]
    elif remote.startswith("ssh://git@github.com/"):
        normalized = "https://github.com/" + remote.split("ssh://git@github.com/", 1)[1]
    if normalized.startswith("https://github.com/") or normalized.startswith("http://github.com/"):
        normalized = normalized.replace("http://github.com/", "https://github.com/", 1)
        if normalized.endswith(".git"):
            normalized = normalized[:-4]
        return f"{normalized}/tree/{branch}" if branch else normalized
    return f"{remote} · {branch}" if branch else remote


def find_git_root(start: str | os.PathLike | None = None) -> Path | None:
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
    """Busca clones cercanos sin escanear el disco completo."""
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
    for _ in range(5):
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
        try:
            children = list(anchor.iterdir())[:250]
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
    if "diagnosticpc" in name or "corepulse" in name:
        score += 30
    if (repo / ".github").is_dir():
        score += 15
    score += 10 * sum((repo / part).is_dir() for part in PROTECTED_REPO_DIRS)
    try:
        remote = _run_git(repo, "remote", "get-url", "origin", check=False).stdout.strip().casefold()
    except Exception:
        remote = ""
    if "diagnosticpc" in remote or "corepulse" in remote:
        score += 100
    try:
        branch = _run_git(repo, "branch", "--show-current", check=False).stdout.strip().casefold()
    except Exception:
        branch = ""
    if branch:
        score += 20
    return score


def discover_publish_repositories(start: str | os.PathLike | None = None, preferred: str | os.PathLike | None = None) -> list[Path]:
    """Devuelve candidatos Git ordenados por relevancia para el usuario."""
    roots: dict[str, Path] = {}
    for seed in (preferred, start, source_root()):
        if not seed:
            continue
        exact = find_git_root(seed)
        if exact is not None:
            roots[str(exact).casefold()] = exact
        for root in discover_nearby_git_roots(seed):
            roots[str(root).casefold()] = root
    return [repo for _score, repo in sorted(
        ((_repo_candidate_score(repo), repo) for repo in roots.values()),
        key=lambda item: (-item[0], str(item[1]).casefold()),
    )]


def resolve_git_root(start: str | os.PathLike | None = None) -> tuple[Path | None, dict]:
    """Detecta automáticamente el clon cuando existe un candidato inequívoco."""
    exact = find_git_root(start)
    if exact is not None:
        return exact, {"auto_detected": False, "candidates": [str(exact)], "selected": str(start or "")}

    candidates = discover_publish_repositories(start=start)
    if not candidates:
        return None, {"auto_detected": False, "candidates": [], "selected": str(start or "")}

    ranked = [(_repo_candidate_score(repo), repo) for repo in candidates]
    best_score, best = ranked[0]
    second_score = ranked[1][0] if len(ranked) > 1 else -1
    if len(ranked) == 1 or best_score > second_score:
        return best, {
            "auto_detected": True,
            "candidates": [str(repo) for _, repo in ranked],
            "selected": str(start or ""),
            "note": f"Clon detectado automáticamente: {best}",
        }
    return None, {
        "auto_detected": False,
        "candidates": [str(repo) for _, repo in ranked],
        "selected": str(start or ""),
        "note": "Hay más de un repositorio posible. Elige uno en la lista.",
    }


def _git_lines(repo: Path, *args: str) -> list[str]:
    text = _run_git(repo, *args).stdout
    return [line.strip() for line in text.splitlines() if line.strip()]


def _paths(repo: Path, *args: str, env=None) -> list[str]:
    args = list(args)
    args.insert(args.index("--") if "--" in args else len(args), "-z")
    return [p for p in _run_git(repo, *args, env=env).stdout.split("\0") if p]


def _top_level(path: str) -> str:
    path = str(path).replace("\\", "/")
    return path.split("/", 1)[0] if path else ""


def _path_parts(path: str) -> tuple[str, ...]:
    return tuple(part.casefold() for part in str(path).replace("\\", "/").split("/") if part)


def _index_path(repo: Path) -> Path:
    path = Path(_run_git(repo, "rev-parse", "--git-path", "index").stdout.strip())
    return path.resolve() if path.is_absolute() else (repo / path).resolve()


def _context_key(ctx: dict) -> tuple:
    # V258: la publicación usa un índice temporal y el HEAD remoto actual. El
    # staging/HEAD local puede cambiar sin contaminar el commit de CorePulse.
    return tuple(ctx.get(k) for k in ("repo_root", "branch", "remote", "publish_folder", "source_root"))


def _is_corepulse_project(path: Path) -> bool:
    try:
        return (
            path.is_dir()
            and not path.is_symlink()
            and (path / "main.py").is_file()
            and (path / "core" / "version.py").is_file()
        )
    except Exception:
        return False


def is_publishable_version_folder(path: Path) -> bool:
    try:
        if path.name in PROTECTED_REPO_ITEMS or path.name.startswith("."):
            return False
        return bool(COREPULSE_FOLDER_RE.fullmatch(path.name)) and _is_corepulse_project(path)
    except Exception:
        return False


def discover_version_folders(repo: str | os.PathLike) -> list[str]:
    root = Path(repo).expanduser().resolve()
    try:
        children = list(root.iterdir())
    except Exception:
        return []
    items = [p.name for p in children if is_publishable_version_folder(p)]
    return sorted(items, key=lambda value: value.casefold())


def _tracked_corepulse_dirs(repo: Path) -> list[str]:
    names = _run_git(repo, "ls-tree", "-d", "--name-only", "-z", "HEAD", check=False).stdout.split("\0")
    return sorted(name for name in names if name and COREPULSE_FOLDER_RE.fullmatch(name))


def _iter_project_files(root: Path):
    root = Path(root)
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in _IGNORE_DIRS for part in rel.parts):
            continue
        if path.suffix.casefold() in _IGNORE_SUFFIXES or path.name.endswith(".log"):
            continue
        yield rel, path


def _same_project_tree(source: Path, target: Path) -> bool:
    try:
        if not source.is_dir() or not target.is_dir():
            return False
        src_files = {rel: path for rel, path in _iter_project_files(source)}
        dst_files = {rel: path for rel, path in _iter_project_files(target)}
        if set(src_files) != set(dst_files):
            return False
        for rel, src in src_files.items():
            dst = dst_files[rel]
            if src.stat().st_size != dst.stat().st_size or src.read_bytes() != dst.read_bytes():
                return False
        return True
    except Exception:
        return False


def _backup_untracked_target(target: Path) -> Path:
    """Compatibilidad: mueve un destino conflictivo a AppData sin borrarlo."""
    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup_root = data_path("updates", "publication_backups", f"{target.name}-{stamp}")
    candidate = Path(backup_root)
    suffix = 1
    while candidate.exists():
        candidate = Path(f"{backup_root}-{suffix}")
        suffix += 1
    candidate.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(target), str(candidate))
    return candidate


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


def _copy_current_project(source: Path, target: Path) -> bool:
    if target.exists():
        if _same_project_tree(source, target):
            return False
        raise PublishError(
            f"Ya existe {target.name} dentro del clon y no coincide con la versión que estás ejecutando. "
            "CorePulse no la sobrescribe automáticamente para no perder cambios locales."
        )
    shutil.copytree(source, target, ignore=_ignore_copy)
    return True


def _planned_source_files(source: Path, target_name: str) -> list[str]:
    return [f"{target_name}/{rel.as_posix()}" for rel, _path in _iter_project_files(source)]


def discover_remote_branches(repo: str | os.PathLike) -> list[str]:
    """Lista ramas de ``origin`` sin cambiar la rama local.

    Primero usa refs ya conocidas y después ``ls-remote`` para que el selector
    pueda mostrar ramas creadas por otro integrante sin exigir un checkout.
    Un fallo de red no invalida las refs locales ya disponibles.
    """
    root = Path(repo).expanduser().resolve()
    branches: set[str] = set()
    proc = _run_git(
        root, "for-each-ref", "--format=%(refname:strip=3)",
        "refs/remotes/origin", check=False,
    )
    for raw in proc.stdout.splitlines():
        name = raw.strip()
        if name and name.casefold() != "head":
            branches.add(name)

    live = _run_git(root, "ls-remote", "--heads", "origin", check=False)
    if live.returncode == 0:
        for line in live.stdout.splitlines():
            parts = line.strip().split(None, 1)
            if len(parts) != 2 or not parts[1].startswith("refs/heads/"):
                continue
            branches.add(parts[1][len("refs/heads/"):])

    def key(name: str):
        folded = name.casefold()
        if folded in STABLE_BRANCHES:
            return (0, folded)
        if folded.endswith("corepulse-dev"):
            return (1, folded)
        return (2, folded)

    return sorted(branches, key=key)


def classify_destination_branch(branch: str) -> dict:
    branch = str(branch or "").strip()
    folded = branch.casefold()
    if folded in STABLE_BRANCHES:
        return {
            "kind": "stable",
            "label": "Estable",
            "release_label": VERSION_LABEL,
            "release_kind": "Release estable",
        }
    if folded.endswith("corepulse-dev"):
        return {
            "kind": "development",
            "label": "Desarrollo",
            "release_label": f"{VERSION_LABEL}-dev",
            "release_kind": "Prerelease de desarrollo",
        }
    return {
        "kind": "custom",
        "label": "Otra rama",
        "release_label": VERSION_LABEL,
        "release_kind": "Release según workflow",
    }


def _workflow_support(repo: Path, branch: str) -> dict:
    """Diagnóstico conservador de Actions locales; nunca modifica .github."""
    folder = repo / ".github" / "workflows"
    try:
        files = sorted([*folder.glob("*.yml"), *folder.glob("*.yaml")]) if folder.is_dir() else []
    except Exception:
        files = []
    profile = classify_destination_branch(branch)
    if not files:
        return {
            "workflow_detected": False,
            "workflow_files": [],
            "workflow_note": "No se detectaron workflows locales en .github/workflows. El push puede funcionar, pero no se creará una Release automática desde este clon.",
        }

    texts = []
    for path in files:
        try:
            texts.append((path.name, path.read_text(encoding="utf-8", errors="ignore").casefold()))
        except Exception:
            continue

    needle = branch.casefold()
    matched = [name for name, body in texts if needle and needle in body]
    if not matched and profile["kind"] == "development":
        matched = [name for name, body in texts if "corepulse-dev" in body]
    if not matched and profile["kind"] == "stable":
        # No asumimos que cualquier Action sea un release estable: buscamos una
        # mención explícita a la rama para no prometer automatización inexistente.
        matched = [name for name, body in texts if re.search(r"(?m)^\s*-\s*['\"]?" + re.escape(needle) + r"['\"]?\s*$", body)]

    if matched:
        return {
            "workflow_detected": True,
            "workflow_files": matched,
            "workflow_note": f"Action compatible detectada: {', '.join(matched[:3])}",
        }
    return {
        "workflow_detected": False,
        "workflow_files": [path.name for path in files],
        "workflow_note": (
            f"No se detectó una mención clara a '{branch}' en los workflows locales. "
            "CorePulse puede subir el código, pero la Release automática depende de la configuración de GitHub Actions."
        ),
    }


def inspect_publish_context(
    repo_hint: str | os.PathLike | None = None,
    target_branch: str | None = None,
) -> dict:
    """Analiza repositorio, versión y rama remota sin cambiar el checkout local."""
    source = source_root().resolve()
    selected_hint = str(repo_hint or "").strip()

    if selected_hint:
        root = find_git_root(selected_hint)
        discovery = {
            "auto_detected": False,
            "candidates": [str(p) for p in discover_publish_repositories(source, preferred=selected_hint)],
            "selected": selected_hint,
        }
        if root is None:
            root, auto = resolve_git_root(selected_hint)
            discovery.update(auto)
    else:
        root, discovery = resolve_git_root(source)

    if root is None:
        return {
            "available": False,
            "can_publish": False,
            "blockers": [discovery.get("note") or "No se encontró un clon Git cercano."],
            "repo_candidates": discovery.get("candidates", []),
            "remote_branches": [],
            "auto_detected": False,
            "source_root": str(source),
            "publish_folder": source.name if COREPULSE_FOLDER_RE.fullmatch(source.name) else TARGET_FOLDER,
        }

    root = root.resolve()
    candidates = [str(p) for p in discover_publish_repositories(source, preferred=root)]
    if str(root) not in candidates:
        candidates.insert(0, str(root))

    blockers: list[str] = []
    local_branch = _run_git(root, "branch", "--show-current", check=False).stdout.strip()
    remote_branches = discover_remote_branches(root)
    requested_branch = str(target_branch or "").strip()

    preference_note = ""
    if requested_branch and requested_branch in remote_branches:
        branch = requested_branch
    else:
        if requested_branch and requested_branch not in remote_branches:
            preference_note = f"La rama guardada '{requested_branch}' no existe en este origin; se eligió un destino disponible."
        if local_branch and local_branch in remote_branches:
            branch = local_branch
        elif "main" in remote_branches:
            branch = "main"
        elif remote_branches:
            branch = remote_branches[0]
        else:
            branch = local_branch
            blockers.append("No se encontraron ramas remotas en origin.")

    if not branch:
        blockers.append("Selecciona una rama remota de destino.")

    head = _run_git(root, "rev-parse", "--verify", "HEAD", check=False).stdout.strip()
    if not head:
        blockers.append("El repositorio necesita un commit inicial antes de subir una versión.")

    remotes = _run_git(root, "remote", "get-url", "--push", "--all", "origin", check=False).stdout.splitlines()
    remote = remotes[0].strip() if len(remotes) == 1 else ""
    if not remote:
        blockers.append("Configura un único destino de push para origin.")
    if _run_git(root, "config", "--bool", "remote.origin.mirror", check=False).stdout.strip() == "true":
        blockers.append("origin está configurado como mirror; este flujo no publica en mirrors.")

    if not _is_corepulse_project(source):
        blockers.append("La versión ejecutada no contiene main.py y core/version.py; no se puede identificar como CorePulse.")

    try:
        rel = source.relative_to(root)
    except ValueError:
        rel = None

    if rel is not None:
        if len(rel.parts) != 1:
            blockers.append("La versión ejecutada está dentro del clon pero no en la raíz. Las versiones deben ser carpetas directas del repositorio.")
            target_name = rel.parts[0] if rel.parts else TARGET_FOLDER
        else:
            target_name = rel.parts[0]
            if not COREPULSE_FOLDER_RE.fullmatch(target_name):
                blockers.append("La carpeta ejecutada no tiene un nombre de versión CorePulse válido.")
    else:
        target_name = source.name if COREPULSE_FOLDER_RE.fullmatch(source.name) else TARGET_FOLDER

    target = root / target_name
    if target.is_symlink() or target.resolve().parent != root:
        blockers.append("La carpeta de versión debe ser un hijo directo real del repositorio, no un enlace.")

    if source == target.resolve():
        target_state = "running_inside_repo"
    elif target.exists():
        if _same_project_tree(source, target):
            target_state = "same_copy"
        else:
            target_state = "different"
            blockers.append(
                f"Ya existe {target_name} en el repositorio y su contenido es distinto. "
                "Abre esa copia o usa un nombre de versión nuevo para evitar sobrescribir trabajo."
            )
    else:
        target_state = "will_copy"

    staged = _paths(root, "diff", "--cached", "--name-only", "--no-renames")
    outside = [path for path in staged if _top_level(path) != target_name]

    if _paths(root, "ls-files", "--unmerged"):
        blockers.append("Resuelve los conflictos Git antes de subir la versión.")
    for marker in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge", "rebase-apply"):
        name = Path(_run_git(root, "rev-parse", "--git-path", marker).stdout.strip())
        marker_path = name if name.is_absolute() else root / name
        if marker_path.exists():
            blockers.append("Finaliza la operación Git en curso antes de continuar: " + marker)

    pending: list[str] = []
    if local_branch and branch and local_branch == branch:
        tracking = "refs/remotes/origin/" + branch
        if _run_git(root, "rev-parse", "--verify", tracking, check=False).returncode == 0:
            pending = _git_lines(root, "rev-list", tracking + "..HEAD")

    index = _index_path(root)
    index_hash = hashlib.sha256(index.read_bytes() if index.exists() else b"").hexdigest()
    plan = sorted(_planned_source_files(source if source != target.resolve() else target, target_name)) if _is_corepulse_project(source) else []

    version_folders = discover_version_folders(root)
    protected = {name: (root / name).exists() for name in PROTECTED_REPO_ITEMS}
    profile = classify_destination_branch(branch)
    workflow = _workflow_support(root, branch)
    return {
        "available": True,
        "can_publish": not blockers,
        "blockers": blockers,
        "repo_root": str(root),
        "repo_candidates": candidates,
        "branch": branch,
        "local_branch": local_branch,
        "remote_branches": remote_branches,
        "destination_kind": profile["kind"],
        "destination_label": profile["label"],
        "release_label": profile["release_label"],
        "release_kind": profile["release_kind"],
        "remote": remote,
        "head": head,
        "remote_branch_url": remote_branch_url(remote, branch),
        "publish_folder": target_name,
        "target_folder": target_name,
        "source_root": str(source),
        "target_existing_state": target_state,
        "version": VERSION_LABEL,
        "protected": protected,
        "protected_items": list(PROTECTED_REPO_ITEMS),
        "version_folders": version_folders,
        "tracked_corepulse": _tracked_corepulse_dirs(root),
        "staged_outside": outside,
        "index_sha256": index_hash,
        "pending_commits": pending,
        "planned_files": plan,
        "planned_count": len(plan),
        "auto_detected": bool(discovery.get("auto_detected")),
        "detection_note": " · ".join(part for part in (discovery.get("note") or "", preference_note) if part),
        **workflow,
    }


def publish_current_version(
    repo_hint,
    commit_message,
    *,
    target_branch: str | None = None,
    progress: Callable | None = None,
    expected_context=None,
):
    """Publica sólo la versión ejecutada sobre la rama remota seleccionada.

    Puede publicar a main desde un checkout local de desarrollo sin hacer
    checkout, merge, pull ni force-push. El commit se crea sobre origin/<rama>
    mediante un índice temporal y se reintenta una vez ante non-fast-forward.
    """
    message = str(commit_message or "").strip()
    if not message:
        raise PublishError("Escribe un mensaje de commit antes de subir la versión.")

    branch_hint = str(target_branch or (expected_context or {}).get("branch") or "").strip() or None
    ctx = inspect_publish_context(repo_hint, target_branch=branch_hint)
    if not ctx.get("can_publish"):
        raise PublishError("\n".join(ctx.get("blockers") or ["Publicación bloqueada"]))
    if expected_context is not None and _context_key(ctx) != _context_key(expected_context):
        raise PublishError("El repositorio, destino remoto o versión cambió desde el análisis. Pulsa Analizar otra vez.")

    repo = Path(ctx["repo_root"])
    branch = str(ctx["branch"])
    target_name = str(ctx["publish_folder"])
    target = repo / target_name
    source = Path(ctx["source_root"])

    def note(text: str):
        if callable(progress):
            progress(text)

    def unchanged_destination():
        current_remote_lines = _run_git(repo, "remote", "get-url", "--push", "--all", "origin").stdout.splitlines()
        current_remote = current_remote_lines[0].strip() if len(current_remote_lines) == 1 else ""
        if current_remote != ctx["remote"]:
            raise PublishError("El remoto origin cambió durante la operación. No se hace push.")

    def fetch_remote_head() -> str:
        unchanged_destination()
        note(f"Sincronizando origin/{branch}…")
        refspec = f"+refs/heads/{branch}:refs/remotes/origin/{branch}"
        proc = _run_git(repo, "fetch", "--no-tags", "origin", refspec, check=False)
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()
            raise PublishError(detail or f"No se pudo consultar origin/{branch}.")
        remote_ref = f"refs/remotes/origin/{branch}"
        verify = _run_git(repo, "rev-parse", "--verify", remote_ref, check=False)
        if verify.returncode != 0 or not verify.stdout.strip():
            raise PublishError(f"La rama remota origin/{branch} ya no existe. Analiza los destinos otra vez.")
        return verify.stdout.strip()

    def prepare_snapshot(base_commit: str) -> tuple[str | None, list[str]]:
        if source != target.resolve() and not target.exists():
            note("Copiando la versión ejecutada a la raíz del clon…")
            _copy_current_project(source, target)

        fd, tmp_name = tempfile.mkstemp(prefix="corepulse-publish-", suffix=".index")
        os.close(fd)
        temp_index = Path(tmp_name)
        temp_index.unlink(missing_ok=True)
        env = {"GIT_INDEX_FILE": str(temp_index)}
        try:
            _run_git(repo, "read-tree", base_commit, env=env)
            _run_git(repo, "add", "-A", "--", target_name, env=env)
            nested_github = f"{target_name}/.github"
            _run_git(repo, "reset", "-q", base_commit, "--", nested_github, env=env, check=False)

            staged = _paths(repo, "diff", "--cached", "--name-only", "--no-renames", base_commit, env=env)
            if any(_top_level(path) != target_name for path in staged):
                raise PublishError("Seguridad: la instantánea contiene rutas fuera de la versión seleccionada.")
            if any(".github" in _path_parts(path) for path in staged):
                raise PublishError("Seguridad: .github apareció en la instantánea y fue bloqueado.")
            if not staged:
                return None, []

            tree = _run_git(repo, "write-tree", env=env).stdout.strip()
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", delete=False) as msg_file:
                msg_file.write(message + "\n")
                msg_path = Path(msg_file.name)
            try:
                commit = _run_git(repo, "commit-tree", tree, "-p", base_commit, "-F", str(msg_path)).stdout.strip()
            finally:
                msg_path.unlink(missing_ok=True)
            if not commit:
                raise PublishError("Git no devolvió el commit preparado.")

            commit_paths = _paths(repo, "diff-tree", "--no-commit-id", "--name-only", "--no-renames", "-r", base_commit, commit)
            if any(_top_level(path) != target_name for path in commit_paths):
                raise PublishError("Seguridad: el commit preparado contiene cambios fuera de la versión.")
            if any(".github" in _path_parts(path) for path in commit_paths):
                raise PublishError("Seguridad: el commit preparado contiene .github.")
            return commit, commit_paths
        finally:
            temp_index.unlink(missing_ok=True)
            Path(str(temp_index) + ".lock").unlink(missing_ok=True)

    profile = classify_destination_branch(branch)
    note(f"Repositorio: {repo}")
    note(f"Destino: {profile['label']} · origin/{branch}")
    note(f"Versión: {target_name}")
    note("Publicación aislada: no modifica HEAD, rama local, staging ni commits locales.")
    note("Excluidos: FASE 1, FASE 2, FASE 3, .github y cualquier otra carpeta del repositorio.")

    last_error = None
    for attempt in range(2):
        base = fetch_remote_head()
        commit, paths = prepare_snapshot(base)
        if commit is None:
            note("La versión remota ya coincide con la carpeta ejecutada; no hay cambios nuevos que subir.")
            return {
                "ok": True,
                "repo_root": str(repo),
                "branch": branch,
                "destination_kind": profile["kind"],
                "release_label": profile["release_label"],
                "workflow_detected": ctx.get("workflow_detected", False),
                "remote": ctx["remote"],
                "commit": base[:12],
                "target_folder": target_name,
                "publish_folder": target_name,
                "remote_branch_url": ctx["remote_branch_url"],
                "staged_count": 0,
                "release_assets": {},
                "source_old_left_local": False,
                "preserved_local_corepulse": ctx.get("version_folders", []),
                "push_output": "Sin cambios: el remoto ya contiene esta versión.",
                "remote_based_publish": True,
            }

        note(f"Preparando commit {commit[:12]} con {len(paths)} archivo(s)…")
        note(f"Subiendo a origin/{branch}…")
        push = _run_git(
            repo, "-c", "push.followTags=false", "push", "--no-follow-tags", "--recurse-submodules=no",
            "origin", f"{commit}:refs/heads/{branch}", check=False,
        )
        if push.returncode == 0:
            _run_git(repo, "fetch", "--no-tags", "origin", f"+refs/heads/{branch}:refs/remotes/origin/{branch}", check=False)
            note("Versión subida correctamente.")
            return {
                "ok": True,
                "repo_root": str(repo),
                "branch": branch,
                "destination_kind": profile["kind"],
                "release_label": profile["release_label"],
                "workflow_detected": ctx.get("workflow_detected", False),
                "remote": ctx["remote"],
                "commit": commit[:12],
                "target_folder": target_name,
                "publish_folder": target_name,
                "remote_branch_url": ctx["remote_branch_url"],
                "staged_count": len(paths),
                "release_assets": {},
                "source_old_left_local": False,
                "preserved_local_corepulse": ctx.get("version_folders", []),
                "push_output": (push.stdout or push.stderr).strip(),
                "remote_based_publish": True,
            }

        last_error = (push.stderr or push.stdout or "").strip()
        if attempt == 0 and any(token in last_error.casefold() for token in ("fetch first", "non-fast-forward", "rejected")):
            # Reintentar sólo si parece una carrera de actualización. Los rechazos
            # explícitos de branch protection no se benefician de reconstruir.
            lowered = last_error.casefold()
            if "protected branch" not in lowered and "protected branch hook" not in lowered:
                note("La rama cambió mientras se publicaba. Reintentando sobre la versión remota más reciente…")
                continue
        break

    lowered = (last_error or "").casefold()
    if branch.casefold() in STABLE_BRANCHES and any(token in lowered for token in ("protected branch", "protected branch hook", "permission denied", "not permitted")):
        raise PublishError(
            f"GitHub rechazó el push directo a {branch}, probablemente por protección de rama. "
            "No se usó force-push ni se modificó tu rama local. Publica primero en tu rama de desarrollo o habilita el flujo de PR para main.\n" +
            (last_error or "")
        )

    raise PublishError(
        "No se pudo subir la versión. CorePulse no creó commits locales ni modificó tu staging.\n" +
        (last_error or "Git rechazó el push sin entregar un detalle adicional.")
    )


__all__ = [
    "PROTECTED_REPO_DIRS", "PROTECTED_REPO_ITEMS", "STABLE_BRANCHES", "BLOCKED_BRANCHES", "TARGET_FOLDER", "PUBLISH_FOLDER",
    "COREPULSE_FOLDER_RE", "PublishError", "remote_branch_url", "find_git_root",
    "discover_nearby_git_roots", "discover_publish_repositories", "resolve_git_root",
    "discover_remote_branches", "classify_destination_branch",
    "discover_version_folders", "is_publishable_version_folder", "inspect_publish_context",
    "publish_current_version",
]
