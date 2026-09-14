"""Actualizador manual de CorePulse basado en GitHub Releases.

V118 introduce un canal de pruebas internas sin tocar ni sobrescribir el árbol de
fuentes del desarrollador. En modo instalado/PyInstaller puede descargar y abrir
un instalador verificado. En modo fuente descarga y prepara una copia aislada en
AppData para validar el flujo entre los dos desarrolladores.

Seguridad:
- nunca actualiza automáticamente al iniciar;
- ignora releases draft;
- canal estable ignora prereleases;
- verifica SHA-256 publicado por GitHub (`asset.digest`) antes de habilitar la
  instalación/preparación;
- el token, si el repositorio fuese privado, sólo se lee desde entorno y jamás se
  persiste en disco;
- la extracción ZIP protege contra path traversal.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Callable, Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import zipfile

from core.runtime_paths import config_path, data_path, is_frozen
from core.version import VERSION, VERSION_LABEL

DEFAULT_OWNER = "tomashoytbarri24"
DEFAULT_REPO = "DiagnosticPC"
API_VERSION = "2026-03-10"
USER_AGENT = f"CorePulse/{VERSION} updater"
PREFERENCES_FILE = "update_preferences.json"
CHANNEL_INTERNAL = "internal"
CHANNEL_STABLE = "stable"
VALID_CHANNELS = {CHANNEL_INTERNAL, CHANNEL_STABLE}


@dataclass(frozen=True)
class ReleaseAsset:
    name: str
    size: int
    browser_download_url: str
    api_url: str
    digest: str | None
    content_type: str | None = None

    @property
    def sha256(self) -> str | None:
        raw = str(self.digest or "").strip().lower()
        if raw.startswith("sha256:"):
            value = raw.split(":", 1)[1].strip()
            if re.fullmatch(r"[0-9a-f]{64}", value):
                return value
        return None


@dataclass(frozen=True)
class ReleaseInfo:
    tag: str
    name: str
    body: str
    prerelease: bool
    published_at: str | None
    html_url: str | None
    assets: tuple[ReleaseAsset, ...]

    @property
    def version_key(self) -> tuple[int, ...]:
        return parse_version_key(self.tag or self.name)


class UpdateError(RuntimeError):
    pass


def _repo_parts() -> tuple[str, str]:
    override = str(os.environ.get("COREPULSE_UPDATE_REPOSITORY") or "").strip()
    if override and "/" in override:
        owner, repo = override.split("/", 1)
        owner, repo = owner.strip(), repo.strip().removesuffix(".git")
        if owner and repo:
            return owner, repo
    return DEFAULT_OWNER, DEFAULT_REPO


def releases_api_url() -> str:
    owner, repo = _repo_parts()
    return f"https://api.github.com/repos/{owner}/{repo}/releases?per_page=30"


def releases_web_url() -> str:
    owner, repo = _repo_parts()
    return f"https://github.com/{owner}/{repo}/releases"


def parse_version_key(value: str | int | None) -> tuple[int, ...]:
    """Convierte V118/118/CorePulse-V118 a una clave ordenable.

    CorePulse usa actualmente versionado entero. También acepta versiones con
    puntos para no bloquear una futura migración de esquema.
    """
    text = str(value or "").strip()
    m = re.search(r"(?i)(?:^|[^a-z0-9])v(\d+(?:\.\d+){0,3})(?:\D|$)", text)
    if not m:
        m = re.search(r"(?<!\d)(\d+(?:\.\d+){0,3})(?!\d)", text)
    if not m:
        return tuple()
    try:
        return tuple(int(part) for part in m.group(1).split("."))
    except Exception:
        return tuple()


def _request(url: str, *, accept: str = "application/vnd.github+json") -> Request:
    headers = {
        "Accept": accept,
        "User-Agent": USER_AGENT,
        "X-GitHub-Api-Version": API_VERSION,
    }
    token = str(os.environ.get("COREPULSE_GITHUB_TOKEN") or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return Request(url, headers=headers)


def _friendly_network_error(exc: Exception) -> UpdateError:
    if isinstance(exc, HTTPError):
        if exc.code in {401, 403, 404}:
            return UpdateError(
                "GitHub no permitió consultar las releases. Si el repositorio es privado, "
                "define COREPULSE_GITHUB_TOKEN en el entorno de pruebas."
            )
        return UpdateError(f"GitHub respondió HTTP {exc.code}.")
    if isinstance(exc, URLError):
        return UpdateError("No se pudo conectar con GitHub. Comprueba Internet y vuelve a intentar.")
    return UpdateError(f"No se pudo consultar actualizaciones: {type(exc).__name__}: {exc}")


def fetch_releases(*, timeout: float = 8.0, opener=urlopen) -> list[ReleaseInfo]:
    try:
        with opener(_request(releases_api_url()), timeout=timeout) as response:
            raw = response.read()
    except Exception as exc:
        raise _friendly_network_error(exc) from exc
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise UpdateError("GitHub devolvió una respuesta de releases que CorePulse no pudo interpretar.") from exc
    if not isinstance(payload, list):
        raise UpdateError("La respuesta de GitHub no contiene una lista de releases.")

    releases: list[ReleaseInfo] = []
    for item in payload:
        if not isinstance(item, dict) or item.get("draft"):
            continue
        assets: list[ReleaseAsset] = []
        for asset in item.get("assets") or []:
            if not isinstance(asset, dict):
                continue
            name = str(asset.get("name") or "").strip()
            browser = str(asset.get("browser_download_url") or "").strip()
            api = str(asset.get("url") or "").strip()
            if not name or not (browser or api):
                continue
            assets.append(ReleaseAsset(
                name=name,
                size=int(asset.get("size") or 0),
                browser_download_url=browser,
                api_url=api,
                digest=str(asset.get("digest") or "").strip() or None,
                content_type=str(asset.get("content_type") or "").strip() or None,
            ))
        releases.append(ReleaseInfo(
            tag=str(item.get("tag_name") or "").strip(),
            name=str(item.get("name") or item.get("tag_name") or "Release").strip(),
            body=str(item.get("body") or "").strip(),
            prerelease=bool(item.get("prerelease")),
            published_at=str(item.get("published_at") or "").strip() or None,
            html_url=str(item.get("html_url") or "").strip() or None,
            assets=tuple(assets),
        ))
    return releases


def choose_release(releases: Iterable[ReleaseInfo], channel: str = CHANNEL_INTERNAL) -> ReleaseInfo | None:
    channel = channel if channel in VALID_CHANNELS else CHANNEL_INTERNAL
    candidates = []
    for release in releases:
        if channel == CHANNEL_STABLE and release.prerelease:
            continue
        if not release.version_key:
            continue
        candidates.append(release)
    if not candidates:
        return None
    return max(candidates, key=lambda r: r.version_key)


def check_for_update(channel: str = CHANNEL_INTERNAL, *, timeout: float = 8.0, opener=urlopen) -> dict:
    releases = fetch_releases(timeout=timeout, opener=opener)
    latest = choose_release(releases, channel)
    current_key = parse_version_key(VERSION)
    latest_key = latest.version_key if latest else tuple()
    return {
        "channel": channel if channel in VALID_CHANNELS else CHANNEL_INTERNAL,
        "current_version": VERSION,
        "current_label": VERSION_LABEL,
        "latest": latest,
        "available": bool(latest and latest_key and current_key and latest_key > current_key),
        "up_to_date": bool(latest and latest_key and current_key and latest_key <= current_key),
        "checked_at": time.time(),
        "repository": "/".join(_repo_parts()),
    }


def choose_asset(release: ReleaseInfo, *, frozen: bool | None = None) -> ReleaseAsset | None:
    frozen = is_frozen() if frozen is None else bool(frozen)
    assets = list(release.assets)
    if not assets:
        return None

    def score(asset: ReleaseAsset) -> tuple[int, int]:
        name = asset.name.casefold()
        if name.endswith((".sha256", ".sha256.txt", ".sig")):
            return (-1000, 0)
        points = 0
        if "corepulse" in name:
            points += 30
        if frozen:
            if name.endswith(".exe") and ("setup" in name or "installer" in name):
                points += 100
            elif name.endswith(".msi"):
                points += 90
            elif name.endswith(".zip"):
                points += 35
        else:
            if name.endswith(".zip"):
                points += 100
            elif name.endswith(".exe") and ("setup" in name or "installer" in name):
                points += 50
        if asset.sha256:
            points += 25
        return (points, int(asset.size or 0))

    ranked = sorted(assets, key=score, reverse=True)
    return ranked[0] if ranked and score(ranked[0])[0] > 0 else None


def updates_dir() -> Path:
    path = data_path("updates")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _download_url(asset: ReleaseAsset) -> str:
    # La URL API funciona también para repositorios privados cuando existe token.
    token = str(os.environ.get("COREPULSE_GITHUB_TOKEN") or "").strip()
    if token and asset.api_url:
        return asset.api_url
    return asset.browser_download_url or asset.api_url


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while True:
            block = handle.read(chunk_size)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def download_asset(
    asset: ReleaseAsset,
    release: ReleaseInfo,
    *,
    progress: Callable[[int, int], None] | None = None,
    timeout: float = 30.0,
    opener=urlopen,
) -> dict:
    target_dir = updates_dir() / (release.tag or release.name or "release")
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / Path(asset.name).name
    part = target.with_suffix(target.suffix + ".part")
    part.unlink(missing_ok=True)

    try:
        request = _request(
            _download_url(asset),
            accept="application/octet-stream" if asset.api_url and _download_url(asset) == asset.api_url else "*/*",
        )
        with opener(request, timeout=timeout) as response, part.open("wb") as handle:
            total = int(response.headers.get("Content-Length") or asset.size or 0)
            downloaded = 0
            while True:
                chunk = response.read(256 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
                downloaded += len(chunk)
                if progress:
                    progress(downloaded, total)
        os.replace(part, target)
    except Exception as exc:
        part.unlink(missing_ok=True)
        raise _friendly_network_error(exc) from exc

    actual = sha256_file(target)
    expected = asset.sha256
    verified = bool(expected and actual.casefold() == expected.casefold())
    if expected and not verified:
        target.unlink(missing_ok=True)
        raise UpdateError("La descarga no superó la verificación SHA-256 y fue eliminada.")

    metadata = {
        "version": release.tag,
        "release_name": release.name,
        "asset": asset.name,
        "path": str(target),
        "sha256": actual,
        "expected_sha256": expected,
        "verified": verified,
        "downloaded_at": time.time(),
        "source": release.html_url,
    }
    try:
        (target_dir / "download.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
    return metadata


def _safe_extract_zip(source: Path, destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    with zipfile.ZipFile(source, "r") as archive:
        for member in archive.infolist():
            member_path = (destination / member.filename).resolve()
            try:
                member_path.relative_to(root)
            except ValueError as exc:
                raise UpdateError("El ZIP de actualización contiene una ruta no segura.") from exc
        archive.extractall(destination)
    return destination


def stage_source_release(download: dict) -> dict:
    """Prepara una copia aislada para probar una release desde modo fuente."""
    if not download.get("verified"):
        raise UpdateError("La copia de prueba sólo se prepara después de verificar SHA-256.")
    source = Path(str(download.get("path") or ""))
    if source.suffix.casefold() != ".zip" or not source.is_file():
        raise UpdateError("La release de modo fuente necesita un asset ZIP.")
    version = str(download.get("version") or "release").replace("/", "_").replace("\\", "_")
    destination = updates_dir() / "staged" / version
    if destination.exists():
        shutil.rmtree(destination, ignore_errors=True)
    _safe_extract_zip(source, destination)

    candidates = [destination / "main.py", destination / "corepulse_launcher.py"]
    for child in destination.iterdir() if destination.exists() else []:
        if child.is_dir():
            candidates.extend([child / "main.py", child / "corepulse_launcher.py"])
    entry = next((p for p in candidates if p.is_file()), None)
    if entry is None:
        raise UpdateError("El ZIP se verificó, pero no contiene una entrada reconocible de CorePulse.")
    return {"directory": str(destination), "entry": str(entry), "version": download.get("version")}


def launch_staged_source(staged: dict) -> bool:
    entry = Path(str(staged.get("entry") or ""))
    if not entry.is_file():
        raise UpdateError("La copia preparada ya no está disponible.")
    python = Path(sys.executable)
    if not python.is_file():
        raise UpdateError("No se encontró el intérprete actual de Python.")
    subprocess.Popen([str(python), str(entry)], cwd=str(entry.parent))
    return True


def launch_installer(download: dict) -> bool:
    if not download.get("verified"):
        raise UpdateError("CorePulse no abrirá un instalador sin verificación SHA-256.")
    path = Path(str(download.get("path") or ""))
    if not path.is_file() or path.suffix.casefold() not in {".exe", ".msi"}:
        raise UpdateError("No se encontró un instalador compatible en la release.")
    if os.name == "nt":
        os.startfile(str(path))  # type: ignore[attr-defined]
    else:
        subprocess.Popen([str(path)])
    return True


def open_updates_folder() -> bool:
    path = updates_dir()
    try:
        if os.name == "nt":
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
        return True
    except Exception as exc:
        raise UpdateError(f"No se pudo abrir la carpeta de actualizaciones: {exc}") from exc


def load_preferences() -> dict:
    defaults = {"channel": CHANNEL_INTERNAL}
    path = config_path(PREFERENCES_FILE)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            defaults.update(payload)
    except Exception:
        pass
    if defaults.get("channel") not in VALID_CHANNELS:
        defaults["channel"] = CHANNEL_INTERNAL
    return defaults


def save_preferences(**values) -> bool:
    payload = load_preferences()
    payload.update(values)
    payload["channel"] = payload.get("channel") if payload.get("channel") in VALID_CHANNELS else CHANNEL_INTERNAL
    try:
        path = config_path(PREFERENCES_FILE)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return True
    except Exception:
        return False


__all__ = [
    "CHANNEL_INTERNAL", "CHANNEL_STABLE", "DEFAULT_OWNER", "DEFAULT_REPO",
    "ReleaseAsset", "ReleaseInfo", "UpdateError", "check_for_update",
    "choose_asset", "choose_release", "download_asset", "fetch_releases",
    "launch_installer", "launch_staged_source", "load_preferences",
    "open_updates_folder", "parse_version_key", "releases_web_url",
    "save_preferences", "sha256_file", "stage_source_release", "updates_dir",
]
