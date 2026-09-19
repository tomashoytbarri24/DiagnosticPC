"""Perfiles persistentes para publicación Git de CorePulse.

Los perfiles guardan únicamente configuración no secreta: carpeta del clon,
remoto, rama e identidad Git local. Las credenciales continúan gestionadas por
Git Credential Manager/SSH y nunca se escriben en CorePulse.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import uuid
from urllib.parse import urlsplit

from core.runtime_paths import config_path

STORE_VERSION = 1
STORE_FILE = "publication_profiles.json"
BLOCKED_BRANCHES = {"main", "master", "trunk"}


class PublicationProfileError(RuntimeError):
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _store_path() -> Path:
    return config_path(STORE_FILE)


def _run_git(repo: str | os.PathLike, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    git = shutil.which("git")
    if not git:
        raise PublicationProfileError("Git no está instalado o no está disponible en PATH.")
    proc = subprocess.run(
        [git, "--literal-pathspecs", "-C", str(repo), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
    )
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise PublicationProfileError(detail or f"Git devolvió código {proc.returncode}.")
    return proc


def _git_root(path: str | os.PathLike) -> Path:
    candidate = Path(path).expanduser().resolve()
    if candidate.is_file():
        candidate = candidate.parent
    proc = _run_git(candidate, "rev-parse", "--show-toplevel", check=False)
    if proc.returncode != 0 or not proc.stdout.strip():
        raise PublicationProfileError("La carpeta seleccionada no pertenece a un repositorio Git.")
    root = Path(proc.stdout.strip()).resolve()
    if not (root / ".git").exists():
        raise PublicationProfileError("La carpeta seleccionada no es un clon Git de trabajo válido.")
    return root



def _ensure_remote_has_no_embedded_credentials(remote_url: str) -> None:
    value = str(remote_url or "").strip()
    if value.lower().startswith(("http://", "https://")):
        parsed = urlsplit(value)
        if parsed.username is not None or parsed.password is not None:
            raise PublicationProfileError(
                "La URL remota contiene credenciales incrustadas. Usa una URL limpia y deja la autenticación a Git Credential Manager/SSH."
            )

def _slug(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(value or "").strip()).strip("-").lower()
    return text[:40] or "perfil"


def _empty_store() -> dict:
    return {"version": STORE_VERSION, "active_profile_id": "", "profiles": []}


def load_publication_profiles() -> dict:
    store = _empty_store()
    try:
        raw = json.loads(_store_path().read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            profiles = raw.get("profiles")
            if isinstance(profiles, list):
                store["profiles"] = [p for p in profiles if isinstance(p, dict)]
            store["active_profile_id"] = str(raw.get("active_profile_id") or "")
    except Exception:
        pass
    ids = {str(p.get("id") or "") for p in store["profiles"]}
    if store["active_profile_id"] not in ids:
        store["active_profile_id"] = next(iter(ids), "")
    return store


def _write_store(store: dict) -> None:
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": STORE_VERSION,
        "active_profile_id": str(store.get("active_profile_id") or ""),
        "profiles": list(store.get("profiles") or []),
    }
    fd, temp_name = tempfile.mkstemp(prefix=path.stem + "-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        os.replace(temp_name, path)
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass


def list_publication_profiles() -> list[dict]:
    return [dict(p) for p in load_publication_profiles().get("profiles", [])]


def get_active_publication_profile() -> dict | None:
    store = load_publication_profiles()
    active = str(store.get("active_profile_id") or "")
    for profile in store.get("profiles", []):
        if str(profile.get("id") or "") == active:
            return dict(profile)
    return None


def set_active_publication_profile(profile_id: str) -> None:
    store = load_publication_profiles()
    wanted = str(profile_id or "")
    if wanted and not any(str(p.get("id") or "") == wanted for p in store.get("profiles", [])):
        raise PublicationProfileError("El perfil de publicación seleccionado ya no existe.")
    store["active_profile_id"] = wanted
    _write_store(store)


def save_publication_profile(profile: dict) -> dict:
    name = str(profile.get("name") or "").strip()
    repo_root = str(profile.get("repo_root") or "").strip()
    remote = str(profile.get("remote") or "origin").strip() or "origin"
    remote_url = str(profile.get("remote_url") or "").strip()
    branch = str(profile.get("branch") or "").strip()
    git_user_name = str(profile.get("git_user_name") or "").strip()
    git_user_email = str(profile.get("git_user_email") or "").strip()
    if not name:
        raise PublicationProfileError("Escribe un nombre para el perfil.")
    if not repo_root:
        raise PublicationProfileError("Selecciona la carpeta raíz del repositorio local.")
    root = _git_root(repo_root)
    if not branch:
        raise PublicationProfileError("Selecciona una rama de publicación.")
    if branch.casefold() in BLOCKED_BRANCHES:
        raise PublicationProfileError("main, master y trunk están bloqueadas para publicación desde CorePulse.")
    if not remote_url:
        detected = _run_git(root, "remote", "get-url", remote, check=False).stdout.strip()
        remote_url = detected
    if not remote_url:
        raise PublicationProfileError("El perfil necesita un repositorio remoto configurado.")
    _ensure_remote_has_no_embedded_credentials(remote_url)
    if not git_user_name:
        raise PublicationProfileError("Configura el nombre de usuario Git del perfil.")
    if not git_user_email:
        raise PublicationProfileError("Configura el correo Git del perfil.")

    store = load_publication_profiles()
    profile_id = str(profile.get("id") or "").strip()
    if not profile_id:
        profile_id = f"{_slug(name)}-{uuid.uuid4().hex[:8]}"
    previous = next((p for p in store.get("profiles", []) if str(p.get("id") or "") == profile_id), None)
    for existing in store.get("profiles", []):
        if str(existing.get("id") or "") != profile_id and str(existing.get("name") or "").strip().casefold() == name.casefold():
            raise PublicationProfileError("Ya existe otro perfil con ese nombre.")
    now = _now_iso()
    normalized = {
        "id": profile_id,
        "name": name,
        "repo_root": str(root),
        "remote": remote,
        "remote_url": remote_url,
        "branch": branch,
        "git_user_name": git_user_name,
        "git_user_email": git_user_email,
        "created_at": str((previous or {}).get("created_at") or now),
        "updated_at": now,
    }
    profiles = [p for p in store.get("profiles", []) if str(p.get("id") or "") != profile_id]
    profiles.append(normalized)
    profiles.sort(key=lambda item: str(item.get("name") or "").casefold())
    store["profiles"] = profiles
    store["active_profile_id"] = profile_id
    _write_store(store)
    return dict(normalized)


def delete_publication_profile(profile_id: str) -> None:
    store = load_publication_profiles()
    wanted = str(profile_id or "")
    store["profiles"] = [p for p in store.get("profiles", []) if str(p.get("id") or "") != wanted]
    if store.get("active_profile_id") == wanted:
        store["active_profile_id"] = str((store["profiles"][0] if store["profiles"] else {}).get("id") or "")
    _write_store(store)


def inspect_git_repository(repo: str | os.PathLike) -> dict:
    root = _git_root(repo)
    remote = "origin"
    remote_url = _run_git(root, "remote", "get-url", remote, check=False).stdout.strip()
    branch = _run_git(root, "branch", "--show-current", check=False).stdout.strip()
    git_user_name = _run_git(root, "config", "--local", "--get", "user.name", check=False).stdout.strip()
    if not git_user_name:
        git_user_name = _run_git(root, "config", "--get", "user.name", check=False).stdout.strip()
    git_user_email = _run_git(root, "config", "--local", "--get", "user.email", check=False).stdout.strip()
    if not git_user_email:
        git_user_email = _run_git(root, "config", "--get", "user.email", check=False).stdout.strip()
    return {
        "repo_root": str(root),
        "remote": remote,
        "remote_url": remote_url,
        "branch": branch,
        "branches": list_git_branches(root, remote=remote),
        "git_user_name": git_user_name,
        "git_user_email": git_user_email,
    }


def list_git_branches(repo: str | os.PathLike, *, remote: str = "origin") -> list[str]:
    root = _git_root(repo)
    local = _run_git(root, "for-each-ref", "--format=%(refname:short)", "refs/heads", check=False).stdout.splitlines()
    remote_lines = _run_git(root, "for-each-ref", "--format=%(refname:short)", f"refs/remotes/{remote}", check=False).stdout.splitlines()
    values: list[str] = []
    seen: set[str] = set()
    for raw in [*local, *remote_lines]:
        item = raw.strip()
        if not item or item.endswith("/HEAD"):
            continue
        if item.startswith(remote + "/"):
            item = item[len(remote) + 1:]
        key = item.casefold()
        if key not in seen:
            seen.add(key)
            values.append(item)
    return sorted(values, key=str.casefold)



def refresh_git_remote(repo: str | os.PathLike, *, remote: str = "origin") -> dict:
    """Actualiza referencias remotas sin tocar la rama ni el working tree."""
    root = _git_root(repo)
    remote = str(remote or "origin").strip() or "origin"
    proc = _run_git(root, "fetch", "--prune", "--no-tags", remote, check=False)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise PublicationProfileError(detail or f"No se pudo actualizar {remote}.")
    return inspect_git_repository(root)

def configure_git_repository(repo: str | os.PathLike, *, remote: str = "origin", remote_url: str,
                             git_user_name: str, git_user_email: str) -> dict:
    root = _git_root(repo)
    remote = str(remote or "origin").strip() or "origin"
    remote_url = str(remote_url or "").strip()
    git_user_name = str(git_user_name or "").strip()
    git_user_email = str(git_user_email or "").strip()
    if not remote_url:
        raise PublicationProfileError("Indica la URL del repositorio remoto.")
    _ensure_remote_has_no_embedded_credentials(remote_url)
    if not git_user_name or not git_user_email:
        raise PublicationProfileError("Nombre y correo Git son obligatorios para guardar el perfil.")
    remotes = {line.strip() for line in _run_git(root, "remote", check=False).stdout.splitlines() if line.strip()}
    if remote in remotes:
        _run_git(root, "remote", "set-url", remote, remote_url)
    else:
        _run_git(root, "remote", "add", remote, remote_url)
    _run_git(root, "config", "--local", "user.name", git_user_name)
    _run_git(root, "config", "--local", "user.email", git_user_email)
    return inspect_git_repository(root)


def activate_profile_branch(repo: str | os.PathLike, branch: str, *, remote: str = "origin") -> str:
    root = _git_root(repo)
    branch = str(branch or "").strip()
    if not branch:
        raise PublicationProfileError("Selecciona una rama.")
    if branch.casefold() in BLOCKED_BRANCHES:
        raise PublicationProfileError("main, master y trunk están bloqueadas para publicación desde CorePulse.")
    local_exists = _run_git(root, "show-ref", "--verify", "--quiet", f"refs/heads/{branch}", check=False).returncode == 0
    remote_exists = _run_git(root, "show-ref", "--verify", "--quiet", f"refs/remotes/{remote}/{branch}", check=False).returncode == 0
    if local_exists:
        _run_git(root, "switch", branch)
    elif remote_exists:
        _run_git(root, "switch", "--track", "-c", branch, f"{remote}/{branch}")
    else:
        _run_git(root, "switch", "-c", branch)
    return _run_git(root, "branch", "--show-current").stdout.strip()


__all__ = [
    "STORE_VERSION", "STORE_FILE", "BLOCKED_BRANCHES", "PublicationProfileError",
    "load_publication_profiles", "list_publication_profiles", "get_active_publication_profile",
    "set_active_publication_profile", "save_publication_profile", "delete_publication_profile",
    "inspect_git_repository", "list_git_branches", "refresh_git_remote", "configure_git_repository", "activate_profile_branch",
]
