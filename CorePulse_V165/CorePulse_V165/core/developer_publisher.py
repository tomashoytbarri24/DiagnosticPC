"""Publicación segura de CorePulse hacia una rama Git de desarrollo.

Conceptos separados:
- repositorio local: checkout Git que el usuario selecciona en cualquier PC;
- remoto: ``origin`` configurado en ese checkout;
- rama destino: rama Git activa y segura;
- carpeta publicada: ``CorePulse_Vxxx`` dentro de la raíz del repositorio.

La operación sólo prepara cambios de CorePulse y nunca incluye FASE 1/2/3.
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
COREPULSE_FOLDER_RE = re.compile(r"(?i)^(?:CorePulse_(?:V)?|V)\d+$")
TARGET_FOLDER = f"CorePulse_V{VERSION}"
PUBLISH_FOLDER = TARGET_FOLDER  # alias semántico; compatibilidad con integraciones anteriores.


def remote_branch_url(remote: str, branch: str) -> str:
    """Devuelve una URL navegable de GitHub cuando el remoto lo permite.

    Para remotos no-GitHub devuelve una representación ``remote · branch`` sin
    asumir proveedor. Nunca se usa esta URL para hacer push; Git sigue usando
    ``origin`` del checkout local.
    """
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

_IGNORE_DIRS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
_IGNORE_SUFFIXES = {".pyc", ".pyo"}


class PublishError(RuntimeError):
    pass


def _run_git(repo: Path, *args: str, check: bool = True, env: dict | None = None) -> subprocess.CompletedProcess:
    git = shutil.which("git")
    if not git:
        raise PublishError("Git no está instalado o no está disponible en PATH.")
    proc = subprocess.run(
        [git, "--literal-pathspecs", "-C", str(repo), *args],
        env={**{k: v for k, v in os.environ.items() if k not in {"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR"}}, "GIT_OPTIONAL_LOCKS": "0", **(env or {})},
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
    el clon real de DiagnosticPC como carpeta hermana en el
    Escritorio. CorePulse revisa sólo la selección, sus padres inmediatos y sus
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
    path = str(path).replace("\\", "/")
    return path.split("/", 1)[0] if path else ""


def _protected_status(repo: Path) -> tuple[str, ...]:
    proc = _run_git(repo, "status", "--porcelain=v1", "--", *PROTECTED_REPO_DIRS)
    return tuple(line.rstrip() for line in proc.stdout.splitlines())


def _path_status_lines(repo: Path, path: str) -> list[str]:
    proc = _run_git(repo, "status", "--porcelain=v1", "--", path, check=False)
    return [line.rstrip() for line in proc.stdout.splitlines() if line.strip()]


def _is_deletion_only_status(lines: list[str]) -> bool:
    """True cuando Git sólo ve eliminaciones de archivos previamente rastreados.

    Esto es seguro para el publicador: reemplazar la carpeta CorePulse anterior
    implica justamente retirar esos archivos del próximo commit. Modificaciones,
    renombres o archivos nuevos siguen bloqueando para evitar pérdida de trabajo.
    """
    if not lines:
        return False
    for line in lines:
        code = (line[:2] if len(line) >= 2 else line).ljust(2)
        if 'D' not in code or any(ch not in {' ', 'D'} for ch in code):
            return False
    return True


def _tracked_corepulse_dirs(repo: Path) -> list[str]:
    names = _run_git(repo, "ls-tree", "-d", "--name-only", "-z", "HEAD", check=False).stdout.split("\0")
    return sorted(name for name in names if COREPULSE_FOLDER_RE.fullmatch(name))


def _paths(repo, *args, env=None):
    args = list(args)
    args.insert(args.index('--') if '--' in args else len(args), '-z')
    return [p for p in _run_git(repo, *args, env=env).stdout.split("\0") if p]


def _index_path(repo):
    path = Path(_run_git(repo, 'rev-parse', '--git-path', 'index').stdout.strip())
    return path.resolve() if path.is_absolute() else (repo / path).resolve()


def _context_key(ctx):
    return tuple(ctx.get(k) for k in ('repo_root', 'branch', 'remote', 'head', 'publish_folder', 'index_sha256'))


def _source_top_in_repo(repo: Path) -> str | None:
    src = source_root().resolve()
    try:
        rel = src.relative_to(repo)
    except ValueError:
        return None
    return rel.parts[0] if rel.parts else None


def inspect_publish_context(repo_hint: str | os.PathLike | None = None) -> dict:
    """Vista previa sólo de lectura, ligada al clon seleccionado y proyecto ejecutado."""
    root = find_git_root(repo_hint)
    if root is None or not (root / '.git').exists():
        selected = Path(repo_hint).expanduser().resolve() if repo_hint else source_root().resolve()
        for candidate in (selected, *selected.parents):
            if (candidate / '.git').exists():
                failure = _run_git(candidate, 'rev-parse', '--show-toplevel', check=False)
                return {'available': False, 'can_publish': False,
                        'blockers': ['Git no puede leer el repositorio seleccionado: ' + (failure.stderr or failure.stdout).strip()]}
        return {'available': False, 'can_publish': False,
                'blockers': ['Selecciona el repositorio local que contiene .git; no se elige otro clon automáticamente.']}
    source = source_root().resolve()
    blockers = []
    branch = _run_git(root, 'branch', '--show-current').stdout.strip()
    if not branch or branch.casefold() in BLOCKED_BRANCHES:
        blockers.append('Selecciona una rama de desarrollo; detached HEAD, main, master y trunk están bloqueados.')
    head = _run_git(root, 'rev-parse', '--verify', 'HEAD', check=False).stdout.strip()
    if not head:
        blockers.append('El repositorio necesita un commit inicial antes de publicar CorePulse.')
    remotes = _run_git(root, 'remote', 'get-url', '--push', '--all', 'origin', check=False).stdout.splitlines()
    remote = remotes[0].strip() if len(remotes) == 1 else ''
    if not remote:
        blockers.append('Configura un único destino de push para el remoto origin.')
    if _run_git(root, 'config', '--bool', 'remote.origin.mirror', check=False).stdout.strip() == 'true':
        blockers.append('origin está configurado como mirror; no se permite publicar con esa configuración.')
    protected = {name: (root / name).is_dir() and not (root / name).is_symlink() for name in PROTECTED_REPO_DIRS}
    if not all(protected.values()):
        blockers.append('Faltan carpetas protegidas válidas: ' + ', '.join(k for k,v in protected.items() if not v))
    try:
        rel = source.relative_to(root)
    except ValueError:
        rel = None
    if rel is not None:
        target_name = rel.parts[0] if rel.parts else ''
        if len(rel.parts) != 1 or not COREPULSE_FOLDER_RE.fullmatch(target_name):
            blockers.append('El proyecto ejecutado debe ser una carpeta CorePulse/Vxxx directa del clon, fuera de FASE 1/2/3.')
    else:
        target_name = source.name if COREPULSE_FOLDER_RE.fullmatch(source.name) else TARGET_FOLDER
    target = root / (target_name or TARGET_FOLDER)
    if not (source / 'main.py').is_file() or not (source / 'core/version.py').is_file():
        blockers.append('La carpeta ejecutada no contiene un proyecto CorePulse completo.')
    if target.is_symlink() or target.resolve().parent != root:
        blockers.append('La carpeta a publicar debe estar físicamente dentro del clon, sin enlaces externos.')
    target_state = 'source' if source == target.resolve() else 'missing'
    if target.exists() and target_state != 'source':
        target_state = 'same' if _same_project_tree(source, target) else 'different'
        if target_state == 'different':
            blockers.append('Ya existe otra copia local de ' + target.name + '. No se sobrescribe: ejecuta la copia deseada dentro del clon o selecciona otro repositorio.')
    tracked = _tracked_corepulse_dirs(root)
    old = [name for name in tracked if name != target_name]
    allowed = set(old) | {target_name}
    staged = _paths(root, 'diff', '--cached', '--name-only', '--no-renames')
    outside = [path for path in staged if _top_level(path) not in allowed]
    if outside:
        blockers.append('Hay archivos staged ajenos a CorePulse. Haz commit o unstage de ellos antes de publicar: ' + ', '.join(outside[:8]))
    if _paths(root, 'ls-files', '--unmerged'):
        blockers.append('Resuelve los conflictos Git antes de publicar.')
    for marker in ('MERGE_HEAD', 'CHERRY_PICK_HEAD', 'REVERT_HEAD', 'rebase-merge', 'rebase-apply'):
        name = Path(_run_git(root, 'rev-parse', '--git-path', marker).stdout.strip())
        if (name if name.is_absolute() else root/name).exists():
            blockers.append('Finaliza la operación Git en curso antes de publicar: ' + marker)
    pending = []
    tracking = 'refs/remotes/origin/' + branch
    if branch and _run_git(root, 'rev-parse', '--verify', tracking, check=False).returncode == 0:
        pending = _git_lines(root, 'rev-list', tracking + '..HEAD')
        for commit in pending:
            paths = _paths(root, 'diff-tree', '--no-commit-id', '--name-only', '--no-renames', '-r', '-m', '--root', commit)
            if any(not COREPULSE_FOLDER_RE.fullmatch(_top_level(path)) for path in paths):
                blockers.append('Hay commits locales pendientes con cambios ajenos a CorePulse; revísalos antes de usar este publicador.')
                break
    index = _index_path(root)
    index_hash = hashlib.sha256(index.read_bytes() if index.exists() else b'').hexdigest()
    changed = _paths(root, 'diff', '--name-only', '--no-renames', 'HEAD', '--', target_name) if target_name else []
    untracked = _paths(root, 'ls-files', '--others', '--exclude-standard', '--', target_name) if target_name else []
    plan = sorted(set(changed + untracked))
    return {'available': True, 'can_publish': not blockers, 'blockers': blockers,
            'repo_root': str(root), 'branch': branch, 'remote': remote, 'head': head,
            'remote_branch_url': remote_branch_url(remote, branch), 'publish_folder': target_name,
            'target_folder': target_name, 'source_root': str(source), 'source_top': target_name if rel is not None else None,
            'target_existing_state': target_state, 'version': VERSION_LABEL, 'protected': protected,
            'protected_dirty': list(_protected_status(root)), 'tracked_corepulse': tracked,
            'old_corepulse': old, 'preserved_local_corepulse': [name for name in old if (root/name).exists()],
            'staged_outside': outside, 'index_sha256': index_hash, 'pending_commits': pending,
            'planned_files': plan, 'planned_count': len(plan), 'auto_detected': False}


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


def _iter_project_files(root: Path):
    """Itera sólo archivos publicables usando las mismas exclusiones del copiado."""
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
    """Comprueba que un destino preexistente sea la misma versión publicable."""
    try:
        if not source.is_dir() or not target.is_dir():
            return False
        src_files = {rel: path for rel, path in _iter_project_files(source)}
        dst_files = {rel: path for rel, path in _iter_project_files(target)}
        if set(src_files) != set(dst_files):
            return False
        for rel, src in src_files.items():
            dst = dst_files[rel]
            if src.stat().st_size != dst.stat().st_size:
                return False
            if src.read_bytes() != dst.read_bytes():
                return False
        return True
    except Exception:
        return False


def _backup_untracked_target(target: Path) -> Path:
    """Mueve una carpeta destino no rastreada a un respaldo persistente fuera del repo."""
    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup_root = data_path("updates", "publication_backups", f"{target.name}-{stamp}")
    # Evita colisiones extremadamente improbables sin borrar respaldos previos.
    candidate = Path(backup_root)
    suffix = 1
    while candidate.exists():
        candidate = Path(f"{backup_root}-{suffix}")
        suffix += 1
    candidate.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(target), str(candidate))
    return candidate


def _copy_current_project(source: Path, target: Path) -> bool:
    """Prepara el destino. Devuelve True sólo cuando creó la carpeta."""
    if target.exists():
        if _same_project_tree(source, target):
            return False
        raise PublishError(
            f"La carpeta destino ya existe y no coincide exactamente con la versión actual: {target.name}. "
            "CorePulse no la sobrescribirá para evitar perder cambios locales."
        )
    shutil.copytree(source, target, ignore=_ignore_copy)
    return True


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


def publish_current_version(repo_hint, commit_message, *, progress=None, expected_context=None):
    """Publica únicamente al pulsar el botón. Índice transaccional, sin borrar trabajo local."""
    message = str(commit_message or '').strip()
    if not message:
        raise PublishError('Escribe un mensaje de commit antes de publicar.')
    ctx = inspect_publish_context(repo_hint)
    if not ctx.get('can_publish'):
        raise PublishError('\n'.join(ctx.get('blockers') or ['Publicación bloqueada']))
    if expected_context is not None and _context_key(ctx) != _context_key(expected_context):
        raise PublishError('El repositorio, rama, destino o índice cambió desde la revisión. Pulsa Revisar antes de publicar.')
    repo = Path(ctx['repo_root'])
    target_name = ctx['publish_folder']
    target = repo / target_name
    old = ctx['old_corepulse']
    allowed = set(old) | {target_name}
    index = _index_path(repo)
    lock = index.with_name(index.name + '.lock')
    temporary = None
    owns_lock = False
    committed = False
    staged_backup = ''
    staged = []
    def note(text):
        if callable(progress):
            progress(text)
    def unchanged_destination():
        if (_run_git(repo, 'branch', '--show-current').stdout.strip() != ctx['branch'] or
            _run_git(repo, 'remote', 'get-url', '--push', '--all', 'origin').stdout.strip() != ctx['remote']):
            raise PublishError('La rama o el remoto cambió durante la publicación. No se hace push.')
    try:
        note(f"Repositorio: {repo}\nDestino: {ctx['remote_branch_url']}\nProyecto: {target_name}")
        # Bloqueo Git estándar: nadie puede modificar el índice real mientras se prepara.
        with lock.open('xb'):
            pass
        owns_lock = True
        initial = index.read_bytes() if index.exists() else b''
        if hashlib.sha256(initial).hexdigest() != ctx['index_sha256']:
            raise PublishError('El índice cambió durante la revisión. Vuelve a revisar.')
        with tempfile.NamedTemporaryFile(dir=index.parent, prefix='corepulse-publish-', suffix='.index', delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(initial)
        env = {'GIT_INDEX_FILE': str(temporary)}
        if not initial:
            temporary.unlink()
            _run_git(repo, 'read-tree', 'HEAD', env=env)
        if Path(ctx['source_root']) != target.resolve() and not target.exists():
            _copy_current_project(Path(ctx['source_root']), target)
        staged_old = [p for p in _paths(repo, 'diff', '--cached', '--name-only', '--no-renames') if _top_level(p) in old]
        if staged_old:
            # Conserva también contenido que existe sólo staged y no en el working tree.
            backup = data_path('updates', 'publication_backups', str(time.time_ns()))
            backup.mkdir(parents=True, exist_ok=False)
            (backup/'index.before').write_bytes(initial)
            patch_text = _run_git(repo, 'diff', '--cached', '--binary', '--no-renames', '--', *old).stdout
            (backup/'old-versions-staged.patch').write_text(patch_text, encoding='utf-8')
            staged_backup = str(backup)
            note('Respaldo del contenido staged anterior: ' + staged_backup)
        for name in old:
            note('Retirando sólo del índice: ' + name + ' (los archivos locales se conservan)')
            _run_git(repo, 'rm', '-r', '-f', '--cached', '--ignore-unmatch', '--', name, env=env)
        _run_git(repo, 'add', '-A', '--', target_name, env=env)
        staged = _paths(repo, 'diff', '--cached', '--name-only', '--no-renames', env=env)
        if any(_top_level(path) not in allowed for path in staged):
            raise PublishError('El índice preparado contiene cambios ajenos; no se hará commit.')
        if not all((repo/name).is_dir() for name in PROTECTED_REPO_DIRS) or list(_protected_status(repo)) != ctx['protected_dirty']:
            raise PublishError('FASE 1/2/3 cambió durante la preparación. Revisa antes de publicar.')
        unchanged_destination()
        if _run_git(repo, 'rev-parse', 'HEAD').stdout.strip() != ctx['head']:
            raise PublishError('HEAD cambió durante la preparación. No se crea otro commit.')
        if staged:
            note('Creando commit sólo de los cambios revisados…')
            with tempfile.NamedTemporaryFile('w', encoding='utf-8', suffix='.txt', delete=False) as message_file:
                message_file.write(message + '\n')
                message_path = Path(message_file.name)
            try:
                _run_git(repo, 'commit', '-F', str(message_path), env=env)
                committed = True
            finally:
                message_path.unlink(missing_ok=True)
            # Publicar el índice resultante sin tocar archivos del working tree.
            lock.write_bytes(temporary.read_bytes())
            os.replace(lock, index)
            owns_lock = False
            paths = _paths(repo, 'diff', '--name-only', '--no-renames', ctx['head'], 'HEAD')
            if any(_top_level(path) not in allowed for path in paths):
                raise PublishError('El commit contiene cambios ajenos (p. ej. de un hook). Quedó local; no se hace push.')
        else:
            note('Sin cambios nuevos; comprobando/publicando el commit local existente, sin duplicarlo.')
            lock.unlink()
            owns_lock = False
        unchanged_destination()
        commit = _run_git(repo, 'rev-parse', 'HEAD').stdout.strip()
        note(f"Push a origin/{ctx['branch']}…")
        try:
            push = _run_git(repo, '-c', 'push.followTags=false', 'push', '--no-follow-tags', '--recurse-submodules=no',
                            'origin', 'refs/heads/' + ctx['branch'] + ':refs/heads/' + ctx['branch'])
        except Exception as exc:
            raise PublishError(f'El commit {commit[:12]} permanece local; el push falló. Puedes reintentar Publicar sin crear otro commit.\n{exc}') from exc
        note('Push completado.')
        return {'ok': True, 'repo_root': str(repo), 'branch': ctx['branch'], 'remote': ctx['remote'],
                'commit': commit[:12], 'target_folder': target_name, 'publish_folder': target_name,
                'remote_branch_url': ctx['remote_branch_url'], 'staged_count': len(staged),
                'release_assets': {}, 'staged_backup': staged_backup, 'source_old_left_local': bool(old),
                'preserved_local_corepulse': [n for n in old if (repo/n).exists()],
                'push_output': (push.stdout or push.stderr).strip()}
    except FileExistsError as exc:
        raise PublishError('Git está ocupado (index.lock). Espera a que termine la otra operación y vuelve a revisar.') from exc
    finally:
        # Sólo artefactos creados por este flujo. El índice del usuario nunca se restaura a HEAD.
        if owns_lock:
            lock.unlink(missing_ok=True)
        if temporary is not None:
            temporary.unlink(missing_ok=True)



def _profile_context_key(ctx):
    """Firma de revisión para el publicador de raíz completa V164."""
    return tuple(ctx.get(k) for k in (
        'profile_id', 'repo_root', 'branch', 'remote_name', 'remote', 'head',
        'index_sha256', 'worktree_sha256',
    ))


def _worktree_status_blob(repo: Path) -> str:
    return _run_git(repo, 'status', '--porcelain=v1', '-z', '--untracked-files=all', check=False).stdout


def inspect_profile_publish_context(profile: dict | None) -> dict:
    """Revisa un perfil V164 sin modificar Git ni copiar carpetas.

    A diferencia del publicador histórico de versiones, el ámbito es la raíz
    completa del clon elegido. Git decide qué cambió y respeta .gitignore.
    """
    profile = dict(profile or {})
    blockers: list[str] = []
    profile_id = str(profile.get('id') or '').strip()
    profile_name = str(profile.get('name') or '').strip() or 'Perfil sin nombre'
    repo_hint = str(profile.get('repo_root') or '').strip()
    remote_name = str(profile.get('remote') or 'origin').strip() or 'origin'
    expected_remote = str(profile.get('remote_url') or '').strip()
    expected_branch = str(profile.get('branch') or '').strip()
    expected_user = str(profile.get('git_user_name') or '').strip()
    expected_email = str(profile.get('git_user_email') or '').strip()
    if not profile_id:
        blockers.append('Guarda el perfil de publicación antes de publicar.')
    if not repo_hint:
        return {'available': False, 'can_publish': False, 'can_push': False,
                'profile_id': profile_id, 'profile_name': profile_name,
                'blockers': ['El perfil no tiene una carpeta raíz configurada.']}
    root = find_git_root(repo_hint)
    if root is None or not (root/'.git').exists():
        return {'available': False, 'can_publish': False, 'can_push': False,
                'profile_id': profile_id, 'profile_name': profile_name,
                'blockers': ['La carpeta del perfil no es un clon Git válido. Selecciona de nuevo la carpeta raíz.']}
    try:
        if Path(repo_hint).expanduser().resolve() != root.resolve():
            blockers.append('La carpeta guardada debe ser la raíz del clon Git, no una subcarpeta.')
    except Exception:
        pass
    branch = _run_git(root, 'branch', '--show-current', check=False).stdout.strip()
    if not expected_branch:
        blockers.append('El perfil no tiene una rama configurada.')
    elif expected_branch.casefold() in BLOCKED_BRANCHES:
        blockers.append('main, master y trunk están bloqueadas para publicación desde CorePulse.')
    elif branch != expected_branch:
        blockers.append(f'La rama activa es {branch or "detached HEAD"}; activa {expected_branch} para usar este perfil.')
    if not branch:
        blockers.append('Git está en detached HEAD. Activa la rama configurada en el perfil.')
    head = _run_git(root, 'rev-parse', '--verify', 'HEAD', check=False).stdout.strip()
    if not head:
        blockers.append('El repositorio necesita un commit inicial antes de publicar.')

    remotes = _run_git(root, 'remote', 'get-url', '--push', '--all', remote_name, check=False).stdout.splitlines()
    remote = remotes[0].strip() if len(remotes) == 1 else ''
    if not remote:
        blockers.append(f'Configura un único destino de push para el remoto {remote_name}.')
    if expected_remote and remote and expected_remote != remote:
        blockers.append('La URL del remoto cambió desde que se guardó el perfil. Guarda el perfil de nuevo antes de publicar.')
    if _run_git(root, 'config', '--bool', f'remote.{remote_name}.mirror', check=False).stdout.strip() == 'true':
        blockers.append(f'{remote_name} está configurado como mirror; CorePulse no publica con esa configuración.')

    current_user = _run_git(root, 'config', '--local', '--get', 'user.name', check=False).stdout.strip()
    current_email = _run_git(root, 'config', '--local', '--get', 'user.email', check=False).stdout.strip()
    if expected_user and current_user != expected_user:
        blockers.append('La identidad Git local no coincide con el usuario guardado en el perfil. Guarda el perfil para aplicarla.')
    if expected_email and current_email != expected_email:
        blockers.append('El correo Git local no coincide con el perfil. Guarda el perfil para aplicarlo.')

    if _paths(root, 'ls-files', '--unmerged'):
        blockers.append('Resuelve los conflictos Git antes de publicar.')
    for marker in ('MERGE_HEAD', 'CHERRY_PICK_HEAD', 'REVERT_HEAD', 'rebase-merge', 'rebase-apply'):
        marker_path = Path(_run_git(root, 'rev-parse', '--git-path', marker).stdout.strip())
        if (marker_path if marker_path.is_absolute() else root/marker_path).exists():
            blockers.append('Finaliza la operación Git en curso antes de publicar: ' + marker)

    tracked = _paths(root, 'diff', '--name-only', '--no-renames', 'HEAD') if head else []
    untracked = _paths(root, 'ls-files', '--others', '--exclude-standard')
    added_tracked = _paths(root, 'diff', '--name-only', '--no-renames', '--diff-filter=A', 'HEAD') if head else []
    deleted = _paths(root, 'diff', '--name-only', '--no-renames', '--diff-filter=D', 'HEAD') if head else []
    plan = sorted(set(tracked + untracked), key=str.casefold)
    new_files = sorted(set(added_tracked + untracked), key=str.casefold)
    modified = sorted(set(tracked) - set(added_tracked) - set(deleted), key=str.casefold)

    pending: list[str] = []
    behind: list[str] = []
    tracking = f'refs/remotes/{remote_name}/{expected_branch}' if expected_branch else ''
    if tracking and _run_git(root, 'rev-parse', '--verify', tracking, check=False).returncode == 0:
        pending = _git_lines(root, 'rev-list', tracking + '..HEAD')
        behind = _git_lines(root, 'rev-list', 'HEAD..' + tracking)

    index = _index_path(root)
    index_hash = hashlib.sha256(index.read_bytes() if index.exists() else b'').hexdigest()
    worktree_blob = _worktree_status_blob(root)
    worktree_hash = hashlib.sha256(worktree_blob.encode('utf-8', 'surrogatepass')).hexdigest()
    can_publish = not blockers
    has_changes = bool(plan)
    has_pending = bool(pending)
    return {
        'available': True, 'can_publish': can_publish,
        'can_push': bool(can_publish and (has_changes or has_pending)),
        'blockers': blockers, 'profile_id': profile_id, 'profile_name': profile_name,
        'repo_root': str(root), 'project_root': str(root), 'branch': branch,
        'configured_branch': expected_branch, 'remote_name': remote_name,
        'remote': remote, 'configured_remote': expected_remote,
        'remote_branch_url': remote_branch_url(remote, expected_branch or branch),
        'head': head, 'index_sha256': index_hash, 'worktree_sha256': worktree_hash,
        'planned_files': plan, 'planned_count': len(plan),
        'new_files': new_files, 'new_count': len(new_files),
        'modified_files': modified, 'modified_count': len(modified),
        'deleted_files': deleted, 'deleted_count': len(deleted),
        'pending_commits': pending, 'behind_commits': behind,
        'git_user_name': current_user, 'git_user_email': current_email,
        'scope': 'repository-root', 'respects_gitignore': True,
    }


def publish_profile_root(profile: dict, commit_message: str, *, progress=None, expected_context=None):
    """Publica el contenido rastreable de la raíz del perfil usando Git.

    No copia versiones ni trata FASE 1/2/3 de forma especial: ``git add -A``
    prepara únicamente altas, cambios y eliminaciones reales, respetando
    ``.gitignore``. Nunca hace force-push ni guarda credenciales.
    """
    message = str(commit_message or '').strip()
    if not message:
        raise PublishError('Escribe un mensaje de commit antes de publicar.')
    ctx = inspect_profile_publish_context(profile)
    if not ctx.get('can_publish'):
        raise PublishError('\n'.join(ctx.get('blockers') or ['Publicación bloqueada']))
    if expected_context is not None and _profile_context_key(ctx) != _profile_context_key(expected_context):
        raise PublishError('El perfil, la rama o los archivos cambiaron desde la revisión. Pulsa Revisar antes de publicar.')

    repo = Path(ctx['repo_root'])
    branch = ctx['configured_branch']
    remote_name = ctx['remote_name']
    index = _index_path(repo)
    lock = index.with_name(index.name + '.lock')
    temporary = None
    owns_lock = False
    staged: list[str] = []

    def note(text):
        if callable(progress):
            progress(text)

    # Consulta el remoto antes de crear un commit. Si la rama ya existe allí,
    # actualiza únicamente su tracking ref y exige fast-forward seguro.
    note(f"Perfil: {ctx['profile_name']}\nRepositorio: {repo}\nDestino: {ctx['remote_branch_url']}")
    ls_remote = _run_git(repo, 'ls-remote', '--heads', remote_name, f'refs/heads/{branch}', check=False)
    if ls_remote.returncode != 0:
        detail = (ls_remote.stderr or ls_remote.stdout or '').strip()
        raise PublishError('No se pudo consultar el repositorio remoto antes de publicar.\n' + (detail or 'Revisa conexión y credenciales Git.'))
    remote_branch_exists = bool(ls_remote.stdout.strip())
    if remote_branch_exists:
        note(f'Actualizando referencia {remote_name}/{branch}…')
        _run_git(repo, 'fetch', '--no-tags', '--prune', remote_name,
                 f'+refs/heads/{branch}:refs/remotes/{remote_name}/{branch}')
        tracking = f'refs/remotes/{remote_name}/{branch}'
        ancestor = _run_git(repo, 'merge-base', '--is-ancestor', tracking, 'HEAD', check=False)
        if ancestor.returncode != 0:
            raise PublishError(f'El remoto {remote_name}/{branch} contiene cambios que tu rama no tiene. Sincroniza/revisa la rama antes de publicar; CorePulse no hará force-push.')

    # El fetch no toca working tree ni índice; después de él volvemos a validar
    # exactamente lo que el usuario revisó.
    current = inspect_profile_publish_context(profile)
    if current.get('blockers'):
        raise PublishError('\n'.join(current.get('blockers') or []))
    if _profile_context_key(current) != _profile_context_key(ctx):
        raise PublishError('Los archivos, HEAD, índice o configuración Git cambiaron durante la publicación. Vuelve a Revisar.')

    try:
        with lock.open('xb'):
            pass
        owns_lock = True
        initial = index.read_bytes() if index.exists() else b''
        if hashlib.sha256(initial).hexdigest() != ctx['index_sha256']:
            raise PublishError('El índice Git cambió desde la revisión. Vuelve a Revisar.')
        with tempfile.NamedTemporaryFile(dir=index.parent, prefix='corepulse-profile-', suffix='.index', delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(initial)
        env = {'GIT_INDEX_FILE': str(temporary)}
        if not initial:
            temporary.unlink(missing_ok=True)
            _run_git(repo, 'read-tree', 'HEAD', env=env)

        note('Preparando únicamente los cambios detectados en la carpeta raíz…')
        _run_git(repo, 'add', '-A', '--', '.', env=env)
        staged = _paths(repo, 'diff', '--cached', '--name-only', '--no-renames', env=env)
        if hashlib.sha256(_worktree_status_blob(repo).encode('utf-8', 'surrogatepass')).hexdigest() != ctx['worktree_sha256']:
            raise PublishError('Los archivos cambiaron mientras se preparaba la publicación. No se creó el commit; vuelve a Revisar.')
        if _run_git(repo, 'branch', '--show-current').stdout.strip() != branch:
            raise PublishError('La rama activa cambió durante la publicación. No se hace commit ni push.')
        if _run_git(repo, 'rev-parse', 'HEAD').stdout.strip() != ctx['head']:
            raise PublishError('HEAD cambió durante la publicación. No se crea otro commit.')

        if staged:
            note(f'Creando commit con {len(staged)} archivo(s) cambiado(s)…')
            with tempfile.NamedTemporaryFile('w', encoding='utf-8', suffix='.txt', delete=False) as message_file:
                message_file.write(message + '\n')
                message_path = Path(message_file.name)
            try:
                _run_git(repo, 'commit', '-F', str(message_path), env=env)
            finally:
                message_path.unlink(missing_ok=True)
            # Publica el índice resultante sin borrar ni reescribir archivos del
            # working tree. Este patrón conserva la seguridad transaccional V163.
            lock.write_bytes(temporary.read_bytes())
            os.replace(lock, index)
            owns_lock = False
        else:
            lock.unlink(missing_ok=True)
            owns_lock = False
            note('No hay archivos nuevos/modificados/eliminados para commitear.')

        commit = _run_git(repo, 'rev-parse', 'HEAD').stdout.strip()
        pending_after = []
        tracking = f'refs/remotes/{remote_name}/{branch}'
        if _run_git(repo, 'rev-parse', '--verify', tracking, check=False).returncode == 0:
            pending_after = _git_lines(repo, 'rev-list', tracking + '..HEAD')
        elif not remote_branch_exists:
            pending_after = [commit]
        if not pending_after:
            note('Todo está actualizado. No hay nada que enviar al remoto.')
            return {
                'ok': True, 'no_changes': True, 'repo_root': str(repo), 'project_root': str(repo),
                'profile_id': ctx['profile_id'], 'profile_name': ctx['profile_name'],
                'branch': branch, 'remote': ctx['remote'], 'remote_name': remote_name,
                'remote_branch_url': ctx['remote_branch_url'], 'commit': commit[:12],
                'staged_count': len(staged), 'push_output': '',
            }

        note(f'Push seguro a {remote_name}/{branch}…')
        try:
            push = _run_git(repo, '-c', 'push.followTags=false', 'push', '--no-follow-tags', '--recurse-submodules=no',
                            remote_name, f'refs/heads/{branch}:refs/heads/{branch}')
        except Exception as exc:
            raise PublishError(f'El commit {commit[:12]} permanece local; el push falló. Puedes reintentar sin perderlo.\n{exc}') from exc
        note('Push completado.')
        return {
            'ok': True, 'no_changes': False, 'repo_root': str(repo), 'project_root': str(repo),
            'profile_id': ctx['profile_id'], 'profile_name': ctx['profile_name'],
            'branch': branch, 'remote': ctx['remote'], 'remote_name': remote_name,
            'remote_branch_url': ctx['remote_branch_url'], 'commit': commit[:12],
            'staged_count': len(staged), 'push_output': (push.stdout or push.stderr).strip(),
        }
    except FileExistsError as exc:
        raise PublishError('Git está ocupado (index.lock). Espera a que termine la otra operación y vuelve a revisar.') from exc
    finally:
        if owns_lock:
            lock.unlink(missing_ok=True)
        if temporary is not None:
            temporary.unlink(missing_ok=True)


__all__ = [
    "PROTECTED_REPO_DIRS", "BLOCKED_BRANCHES", "TARGET_FOLDER", "PUBLISH_FOLDER", "PublishError",
    "remote_branch_url",
    "find_git_root", "discover_nearby_git_roots", "resolve_git_root",
    "inspect_publish_context", "publish_current_version",
    "inspect_profile_publish_context", "publish_profile_root",
]
