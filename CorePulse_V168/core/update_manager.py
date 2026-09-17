"""Actualizador manual de CorePulse basado en GitHub Releases.

V118 introdujo un canal de pruebas internas. Desde V168, en modo fuente la
actualización verificada se instala como una nueva carpeta CorePulse_VN junto a
la versión actual, sin sobrescribirla. CorePulse se cierra y la nueva versión se
abre automáticamente. En modo instalado/PyInstaller se mantiene el instalador
verificado.

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
import ast
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
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
import stat
import zipfile

from core.runtime_paths import config_path, data_path, executable_root, is_frozen, source_root
from core.version import VERSION, VERSION_LABEL

class _SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlsplit(newurl).scheme != 'https':
            raise UpdateError('La descarga intentó redirigir a una conexión no segura.')
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected is not None and urlsplit(newurl).hostname != 'api.github.com':
            redirected.remove_header('Authorization')
        return redirected


def urlopen(request, timeout=30):
    return build_opener(_SafeRedirect()).open(request, timeout=timeout)


DEFAULT_OWNER = "tomashoytbarri24"
DEFAULT_REPO = "DiagnosticPC"
API_VERSION = "2026-03-10"
USER_AGENT = f"CorePulse/{VERSION} updater"
PREFERENCES_FILE = "update_preferences.json"
CHANNEL_INTERNAL = "internal"
CHANNEL_DEVELOPMENT = CHANNEL_INTERNAL
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
    return f"https://api.github.com/repos/{owner}/{repo}/releases?per_page=100"


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
    if token and urlsplit(url).hostname == "api.github.com":
        headers["Authorization"] = f"Bearer {token}"
    if urlsplit(url).scheme != "https":
        raise UpdateError("Actualizaciones requiere una conexión HTTPS.")
    return Request(url, headers=headers)


def _friendly_network_error(exc: Exception) -> UpdateError:
    if isinstance(exc, UpdateError):
        return exc
    if isinstance(exc, HTTPError):
        if exc.code == 404:
            return UpdateError("Repositorio de actualizaciones no encontrado o privado sin acceso autorizado.")
        if exc.code == 401:
            return UpdateError("La credencial de GitHub no es válida o ha caducado.")
        if exc.code in {403, 429}:
            return UpdateError("GitHub limitó las consultas o denegó el acceso. Reintenta más tarde y comprueba los permisos si el repositorio es privado.")
        return UpdateError(f"GitHub respondió HTTP {exc.code}.")
    if isinstance(exc, URLError):
        return UpdateError("No se pudo conectar con GitHub. Comprueba Internet y vuelve a intentar.")
    return UpdateError(f"No se pudo consultar actualizaciones: {type(exc).__name__}: {exc}")


def fetch_releases(*, timeout: float = 8.0, opener=urlopen) -> list[ReleaseInfo]:
    payload = []
    for page in range(1, 11):
        url = releases_api_url() + f'&page={page}'
        try:
            with opener(_request(url), timeout=timeout) as response:
                raw = response.read(8 * 1024 * 1024 + 1)
                next_page = 'rel="next"' in str(response.headers.get('Link') or '')
            if len(raw) > 8 * 1024 * 1024:
                raise UpdateError('La respuesta de GitHub excede el tamaño admitido.')
        except Exception as exc:
            raise _friendly_network_error(exc) from exc
        try:
            items = json.loads(raw.decode('utf-8'))
        except Exception as exc:
            raise UpdateError('GitHub devolvió una respuesta de releases no válida.') from exc
        if not isinstance(items, list):
            raise UpdateError('La respuesta de GitHub no contiene una lista de releases.')
        payload.extend(items)
        if not next_page:
            break
    else:
        raise UpdateError('No se pudo completar la consulta de todas las páginas de Releases.')

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


def choose_release(releases: Iterable[ReleaseInfo], channel: str = CHANNEL_STABLE) -> ReleaseInfo | None:
    channel = channel if channel in VALID_CHANNELS else CHANNEL_STABLE
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


def check_for_update(channel: str = CHANNEL_STABLE, *, timeout: float = 8.0, opener=urlopen) -> dict:
    releases = fetch_releases(timeout=timeout, opener=opener)
    latest = choose_release(releases, channel)
    current_key = parse_version_key(VERSION)
    latest_key = latest.version_key if latest else tuple()
    return {
        "channel": channel if channel in VALID_CHANNELS else CHANNEL_STABLE,
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
    def compatible(asset):
        name = asset.name.casefold()
        if not name.startswith('corepulse'):
            return False
        if frozen:
            return name.endswith('.msi') or (name.endswith('.exe') and ('setup' in name or 'installer' in name))
        return name.endswith('.zip')
    assets = [asset for asset in release.assets if compatible(asset)]
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


def _download_target(asset, release):
    name = str(asset.name)
    if (not name or name in {'.', '..'} or name != Path(name).name
            or any(c in name for c in '/\\:') or name.rstrip(' .') != name):
        raise UpdateError('El paquete tiene un nombre de archivo no válido.')
    tag = str(release.tag or release.name or 'release')
    folder = re.sub(r'[^A-Za-z0-9._-]+', '_', tag).strip(' .')[:80] or 'release'
    # Evita que dos tags distintos saneados al mismo texto compartan descarga.
    folder += '-' + hashlib.sha256(tag.encode()).hexdigest()[:10]
    root = updates_dir().resolve()
    target = (root / folder / name).resolve()
    if not target.is_relative_to(root):
        raise UpdateError('La descarga sale de su carpeta autorizada.')
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def _verify_download(download):
    path = Path(str(download.get('path') or ''))
    expected = str(download.get('expected_sha256') or '')
    if (not download.get('verified') or not re.fullmatch(r'[0-9a-fA-F]{64}', expected)
            or not path.is_file() or sha256_file(path).lower() != expected.lower()):
        raise UpdateError('El paquete cambió o no está verificado. Descarga la actualización otra vez.')
    return path


def download_asset(
    asset: ReleaseAsset,
    release: ReleaseInfo,
    *,
    progress: Callable[[int, int], None] | None = None,
    timeout: float = 30.0,
    opener=urlopen,
) -> dict:
    """Compatibilidad pública: todos los consumidores exigen integridad."""
    return download_asset_verified(asset, release, progress=progress, timeout=timeout, opener=opener)


def _safe_extract_zip(source: Path, destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    with zipfile.ZipFile(source, "r") as archive:
        members = archive.infolist()
        if len(members) > 50000 or sum(m.file_size for m in members) > 8 * 1024**3:
            raise UpdateError('El ZIP excede los límites de extracción.')
        seen = set()
        for member in members:
            name = member.filename.replace('\\', '/')
            parts = name.rstrip('/').split('/')
            if (name.startswith('/') or any(p in {'', '.', '..'} or ':' in p or p.rstrip(' .') != p for p in parts)
                    or stat.S_ISLNK(member.external_attr >> 16)):
                raise UpdateError('El ZIP contiene rutas ambiguas o enlaces no admitidos.')
            key = name.rstrip('/').casefold()
            if key in seen:
                raise UpdateError('El ZIP contiene rutas duplicadas.')
            seen.add(key)
            member_path = (destination / member.filename).resolve()
            try:
                member_path.relative_to(root)
            except ValueError as exc:
                raise UpdateError("El ZIP de actualización contiene una ruta no segura.") from exc
        archive.extractall(destination)
    return destination


def _stage_directory(kind, version):
    label = re.sub(r'[^A-Za-z0-9_-]+', '_', str(version or 'release')).strip('_') or 'release'
    root = updates_dir().resolve()
    destination = root / kind / label
    if destination.is_symlink() or destination.is_junction() or not destination.resolve().is_relative_to(root):
        raise UpdateError('La carpeta de preparación no es segura.')
    if destination.exists():
        shutil.rmtree(destination)
    return destination


def stage_source_release(download: dict) -> dict:
    """Prepara una copia aislada para probar una release desde modo fuente."""
    if not download.get("verified"):
        raise UpdateError("La copia de prueba sólo se prepara después de verificar SHA-256.")
    source = _verify_download(download)
    if source.suffix.casefold() != ".zip" or not source.is_file():
        raise UpdateError("La release de modo fuente necesita un asset ZIP.")
    destination = _stage_directory('staged', download.get('version'))
    _safe_extract_zip(source, destination)

    incoming = _package_root_from_extract(destination)
    _validate_package(incoming, download.get('version'))
    entry = next((p for p in (incoming / 'corepulse_launcher.py', incoming / 'main.py') if p.is_file()), None)
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
    path = _verify_download(download)
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
    defaults = {"channel": CHANNEL_STABLE}
    path = config_path(PREFERENCES_FILE)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            defaults.update(payload)
    except Exception:
        pass
    if defaults.get("channel") not in VALID_CHANNELS:
        defaults["channel"] = CHANNEL_STABLE
    return defaults


def save_preferences(**values) -> bool:
    payload = load_preferences()
    payload.update(values)
    payload["channel"] = payload.get("channel") if payload.get("channel") in VALID_CHANNELS else CHANNEL_STABLE
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

# ---------------------------------------------------------------------------
# V129 · Centro de actualizaciones seguro
# ---------------------------------------------------------------------------
BACKUP_KEEP = 3
_MANAGED_DIRS = {
    "assets", "build", "core", "database", "gui", "installer", "performance",
    "tests", "tools",
}
_PRESERVED_NAMES = {".git", ".venv", "venv", ".env", "data", "logs", "__pycache__"}


def installation_mode() -> str:
    """Devuelve installed/source-git/source-portable sin adivinar capacidades."""
    if is_frozen():
        return "installed"
    root = source_root().resolve()
    cursor = root
    for _ in range(5):
        if (cursor / ".git").exists():
            return "source-git"
        if cursor.parent == cursor:
            break
        cursor = cursor.parent
    return "source-portable"


def source_update_supported() -> bool:
    """Nunca pisa un checkout Git: en desarrollo sólo prepara una copia aislada."""
    return installation_mode() == "source-portable"


def _sidecar_candidates(release: ReleaseInfo, asset: ReleaseAsset) -> list[ReleaseAsset]:
    target = asset.name.casefold()
    exact_names = {
        f"{target}.sha256", f"{target}.sha256.txt", f"{target}.sha256sum",
        "sha256sums", "sha256sums.txt", "checksums.txt", "checksums.sha256",
    }
    out = []
    for candidate in release.assets:
        name = candidate.name.casefold()
        if name in exact_names or ("sha256" in name and name != target):
            out.append(candidate)
    return out


def _parse_checksum_text(text: str, asset_name: str, *, allow_bare=False) -> str | None:
    wanted = asset_name.casefold()
    matches = []
    for line in str(text or '').splitlines():
        line = line.strip()
        match = re.fullmatch(r'([0-9a-fA-F]{64})[ \t]+\*?(.+)', line)
        bsd = re.fullmatch(r'SHA256 \((.+)\) = ([0-9a-fA-F]{64})', line, re.I)
        if match and match.group(2).strip().casefold() == wanted:
            matches.append(match.group(1).lower())
        elif bsd and bsd.group(1).casefold() == wanted:
            matches.append(bsd.group(2).lower())
        elif allow_bare and re.fullmatch(r'[0-9a-fA-F]{64}', line):
            matches.append(line.lower())
    return matches[0] if matches and len(set(matches)) == 1 else None


def resolve_release_sha256(
    release: ReleaseInfo,
    asset: ReleaseAsset,
    *,
    timeout: float = 12.0,
    opener=urlopen,
) -> tuple[str | None, str]:
    """Obtiene SHA-256 desde digest de GitHub o asset sidecar publicado."""
    if asset.sha256:
        return asset.sha256, "github-digest"
    for sidecar in _sidecar_candidates(release, asset):
        try:
            request = _request(
                _download_url(sidecar),
                accept="application/octet-stream" if sidecar.api_url and _download_url(sidecar) == sidecar.api_url else "*/*",
            )
            with opener(request, timeout=timeout) as response:
                raw = response.read(256 * 1024)
            expected = _parse_checksum_text(raw.decode("utf-8", errors="replace"), asset.name,
                allow_bare=sidecar.name.casefold() in {asset.name.casefold()+suffix for suffix in ('.sha256', '.sha256.txt', '.sha256sum')})
            if expected:
                return expected, f"sidecar:{sidecar.name}"
        except Exception:
            continue
    return None, "missing"


def download_asset_verified(
    asset: ReleaseAsset,
    release: ReleaseInfo,
    *,
    progress: Callable[[int, int], None] | None = None,
    timeout: float = 30.0,
    opener=urlopen,
    cancel=None,
) -> dict:
    """V129: descarga sólo el asset elegido y exige SHA-256 verificable."""
    def check_cancel():
        if cancel is not None and cancel.is_set():
            raise UpdateError('Descarga cancelada. Puedes volver a intentarlo.')
    check_cancel()
    expected, source = resolve_release_sha256(release, asset, timeout=min(timeout, 12.0), opener=opener)
    if not expected:
        raise UpdateError(
            "La release no publica un SHA-256 verificable para el paquete seleccionado. "
            "CorePulse no instalará una actualización sin integridad comprobada."
        )
    target = _download_target(asset, release)
    target_dir = target.parent
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
                check_cancel()
                chunk = response.read(256 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
                downloaded += len(chunk)
                if progress:
                    progress(downloaded, total)
        check_cancel()
        actual = sha256_file(part)
        if actual.casefold() != expected.casefold():
            raise UpdateError('La descarga no superó la verificación SHA-256 y fue eliminada.')
        check_cancel()
        os.replace(part, target)
    except Exception as exc:
        part.unlink(missing_ok=True)
        raise _friendly_network_error(exc) from exc
    metadata = {
        "version": release.tag,
        "release_name": release.name,
        "asset": asset.name,
        "path": str(target),
        "sha256": actual,
        "expected_sha256": expected,
        "checksum_source": source,
        "verified": True,
        "downloaded_at": time.time(),
        "source": release.html_url,
    }
    try:
        (target_dir / "download.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
    return metadata


def _package_root_from_extract(destination: Path) -> Path:
    if (destination / "main.py").is_file():
        return destination
    candidates = [child for child in destination.iterdir() if child.is_dir() and (child / "main.py").is_file()]
    if len(candidates) == 1:
        return candidates[0]
    raise UpdateError("El ZIP verificado no contiene una raíz reconocible de CorePulse.")


def _validate_package(root, expected_version=None):
    version_file = root / 'core' / 'version.py'
    if not (root / 'main.py').is_file() or not version_file.is_file():
        raise UpdateError('El ZIP no contiene una aplicación CorePulse completa reconocible.')
    try:
        tree = ast.parse(version_file.read_text(encoding='utf-8-sig'))
        versions = [ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == 'VERSION' for t in n.targets)]
        version = versions[0] if len(versions) == 1 else None
    except Exception as exc:
        raise UpdateError('No se pudo verificar la versión del paquete.') from exc
    if not parse_version_key(version) or (expected_version and parse_version_key(version) != parse_version_key(expected_version)):
        raise UpdateError('La versión dentro del paquete no coincide con la Release.')
    return str(version)


def backup_dir() -> Path:
    path = updates_dir() / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _backup_filter(path: Path) -> bool:
    return not any(part in _PRESERVED_NAMES for part in path.parts)


def create_source_backup(*, label: str | None = None) -> dict:
    """Crea un ZIP de rollback del código actual, sin .git/.venv ni estado mutable."""
    root = source_root().resolve()
    stamp = time.strftime("%Y%m%d-%H%M%S")
    safe_label = re.sub(r"[^A-Za-z0-9._-]+", "_", str(label or VERSION_LABEL))
    target = backup_dir() / f"CorePulse_{safe_label}_{stamp}.zip"
    tmp = target.with_suffix(".zip.part")
    tmp.unlink(missing_ok=True)
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in root.rglob("*"):
            rel = path.relative_to(root)
            if any(part in _PRESERVED_NAMES for part in rel.parts):
                continue
            if path.is_file():
                archive.write(path, rel.as_posix())
    os.replace(tmp, target)
    digest = sha256_file(target)
    _prune_backups()
    return {"path": str(target), "sha256": digest, "created_at": time.time(), "version": VERSION_LABEL}


def _prune_backups(keep: int = BACKUP_KEEP) -> None:
    files = sorted(backup_dir().glob("CorePulse_*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in files[max(1, int(keep)):]:
        try:
            old.unlink()
        except Exception:
            pass


def list_source_backups() -> list[dict]:
    out = []
    for path in sorted(backup_dir().glob("CorePulse_*.zip"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            out.append({
                "path": str(path), "name": path.name, "size": path.stat().st_size,
                "mtime": path.stat().st_mtime, "sha256": sha256_file(path),
            })
        except Exception:
            continue
    return out



def _canonical_version_folder(version: str | int | None) -> str:
    key = parse_version_key(version)
    if not key:
        raise UpdateError("La release no contiene una versión válida para crear la carpeta destino.")
    return "CorePulse_V" + ".".join(str(part) for part in key)


def _side_by_side_marker_path(target: Path) -> Path:
    root = updates_dir().resolve() / "installed"
    root.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(str(target.resolve()).casefold().encode("utf-8")).hexdigest()[:24]
    return root / f"{key}.json"


def prepare_side_by_side_source_update(download: dict) -> dict:
    """Instala una release fuente junto a la versión actual y prepara el reinicio.

    La versión en ejecución nunca se modifica. Por ejemplo, si CorePulse se está
    ejecutando desde ``DiagnosticPC-Maxi/CorePulse_V167``, una release V168 se
    materializa en ``DiagnosticPC-Maxi/CorePulse_V168``. Esto funciona tanto en
    un checkout Git como en una copia portable.
    """
    if is_frozen():
        raise UpdateError("El modo instalado usa el instalador publicado, no una actualización fuente paralela.")
    if not download.get("verified"):
        raise UpdateError("La actualización sólo puede prepararse después de verificar SHA-256.")
    package = _verify_download(download)
    if package.suffix.casefold() != ".zip" or not package.is_file():
        raise UpdateError("La actualización en modo fuente necesita un paquete ZIP.")

    current_root = source_root().resolve()
    parent = current_root.parent.resolve()
    if not parent.is_dir():
        raise UpdateError("No se encontró la carpeta que contiene la versión actual de CorePulse.")

    stage = _stage_directory('side-by-side', download.get('version'))
    try:
        _safe_extract_zip(package, stage)
        incoming = _package_root_from_extract(stage)
        package_version = _validate_package(incoming, download.get('version'))
        target = (parent / _canonical_version_folder(package_version)).resolve()
        if target.parent != parent:
            raise UpdateError("La carpeta destino de la actualización no es segura.")
        if target == current_root:
            raise UpdateError("La release coincide con la versión que ya está en ejecución.")

        marker_path = _side_by_side_marker_path(target)
        expected_sha = str(download.get('expected_sha256') or download.get('sha256') or '').lower()
        if target.exists():
            marker = {}
            try:
                marker = json.loads(marker_path.read_text(encoding='utf-8'))
            except Exception:
                marker = {}
            try:
                existing_version = _validate_package(target, package_version)
            except Exception:
                existing_version = None
            if (existing_version == package_version and expected_sha
                    and str(marker.get('package_sha256') or '').lower() == expected_sha):
                entry = next((p for p in (target / 'corepulse_launcher.py', target / 'main.py') if p.is_file()), None)
                if entry is None:
                    raise UpdateError("La carpeta de destino existente no contiene una entrada válida de CorePulse.")
                return _write_update_plan({
                    "mode": "side-by-side",
                    "pid": os.getpid(),
                    "current_root": str(current_root),
                    "target_root": str(target),
                    "python": sys.executable,
                    "relaunch": entry.name,
                    "status": str((updates_dir() / "last_update_status.json").resolve()),
                    "target_version": str(download.get("version") or package_version),
                })
            raise UpdateError(
                f"Ya existe {target.name} junto a la versión actual. CorePulse no la sobrescribirá automáticamente. "
                "Renombra o elimina esa carpeta si quieres volver a instalar esta release."
            )

        temp_target = (parent / f'.{target.name}.corepulse-update-{os.getpid()}-{int(time.time())}').resolve()
        if temp_target.parent != parent or temp_target.exists():
            raise UpdateError("No se pudo reservar una carpeta temporal segura para la actualización.")
        try:
            shutil.copytree(incoming, temp_target)
            _validate_package(temp_target, package_version)
            os.replace(temp_target, target)
            marker_path.write_text(json.dumps({
                "version": package_version,
                "release": str(download.get('version') or ''),
                "package_sha256": expected_sha,
                "installed_at": time.time(),
                "source_root": str(current_root),
                "target_root": str(target),
            }, indent=2, ensure_ascii=False), encoding='utf-8')
        except Exception:
            if temp_target.exists():
                shutil.rmtree(temp_target, ignore_errors=True)
            raise

        entry = next((p for p in (target / 'corepulse_launcher.py', target / 'main.py') if p.is_file()), None)
        if entry is None:
            raise UpdateError("La nueva versión no contiene una entrada reconocible de CorePulse.")
        return _write_update_plan({
            "mode": "side-by-side",
            "pid": os.getpid(),
            "current_root": str(current_root),
            "target_root": str(target),
            "python": sys.executable,
            "relaunch": entry.name,
            "status": str((updates_dir() / "last_update_status.json").resolve()),
            "target_version": str(download.get("version") or package_version),
        })
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def prepare_source_update(download: dict) -> dict:
    """Prepara actualización in-place sólo para copias fuente no gestionadas por Git."""
    if not source_update_supported():
        raise UpdateError(
            "CorePulse detectó un checkout Git. Por seguridad no sobrescribe código versionado; "
            "usa 'Preparar copia de prueba' o actualiza la rama con Git."
        )
    if not download.get("verified"):
        raise UpdateError("La actualización sólo puede prepararse después de verificar SHA-256.")
    package = _verify_download(download)
    if package.suffix.casefold() != ".zip" or not package.is_file():
        raise UpdateError("La actualización portable/fuente necesita un paquete ZIP.")
    stage = _stage_directory('apply', download.get('version'))
    _safe_extract_zip(package, stage)
    incoming = _package_root_from_extract(stage)
    _validate_package(incoming, download.get('version'))
    backup = create_source_backup(label=VERSION_LABEL)
    plan = {
        "mode": "update",
        "pid": os.getpid(),
        "current_root": str(source_root().resolve()),
        "incoming_root": str(incoming.resolve()),
        "backup_zip": backup["path"],
        "backup_sha256": backup["sha256"],
        "incoming_files": {str(p.relative_to(incoming)): sha256_file(p) for p in incoming.rglob('*') if p.is_file()},
        "python": sys.executable,
        "relaunch": "corepulse_launcher.py" if (source_root() / 'corepulse_launcher.py').is_file() else "main.py",
        "status": str((updates_dir() / "last_update_status.json").resolve()),
        "target_version": str(download.get("version") or ""),
    }
    return _write_update_plan(plan)


def prepare_source_rollback(backup_path: str | os.PathLike | None = None) -> dict:
    if not source_update_supported():
        raise UpdateError("Rollback automático no se aplica dentro de un checkout Git.")
    backups = list_source_backups()
    selected = Path(backup_path).resolve() if backup_path else (Path(backups[0]["path"]).resolve() if backups else None)
    if selected is None or not selected.is_file() or selected.parent != backup_dir().resolve():
        raise UpdateError("No hay una copia de seguridad disponible para restaurar.")
    plan = {
        "mode": "rollback",
        "pid": os.getpid(),
        "current_root": str(source_root().resolve()),
        "backup_zip": str(selected),
        "backup_sha256": sha256_file(selected),
        "python": sys.executable,
        "relaunch": "corepulse_launcher.py" if (source_root() / 'corepulse_launcher.py').is_file() else "main.py",
        "status": str((updates_dir() / "last_update_status.json").resolve()),
        "target_version": "rollback",
    }
    return _write_update_plan(plan)


def _write_update_plan(plan: dict) -> dict:
    root = updates_dir() / "helper"
    root.mkdir(parents=True, exist_ok=True)
    plan_path = root / "update_plan.json"
    helper_path = root / "apply_update.py"
    plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    helper_path.write_text(_UPDATE_HELPER_SCRIPT, encoding="utf-8")
    result = dict(plan)
    result.update({"plan": str(plan_path), "helper": str(helper_path)})
    return result


def launch_source_update_helper(plan: dict) -> bool:
    helper = Path(str(plan.get("helper") or ""))
    plan_path = Path(str(plan.get("plan") or ""))
    python = Path(str(plan.get("python") or sys.executable))
    if not helper.is_file() or not plan_path.is_file() or not python.is_file():
        raise UpdateError("No se pudo preparar el proceso auxiliar de actualización.")
    kwargs = {"cwd": str(helper.parent), "close_fds": True}
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
    subprocess.Popen([str(python), str(helper), str(plan_path)], **kwargs)
    return True


def read_last_update_status() -> dict | None:
    path = updates_dir() / "last_update_status.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


_UPDATE_HELPER_SCRIPT = r'''from __future__ import annotations
import hashlib, json, os, shutil, subprocess, sys, time, zipfile
from pathlib import Path

PRESERVE = {".git", ".venv", "venv", ".env", "data", "logs", "__pycache__"}
MANAGED_DIRS = {"assets", "build", "core", "database", "gui", "installer", "performance", "tests", "tools"}

def digest_file(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def write_status(path, **payload):
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass

def wait_pid(pid, timeout=90):
    if os.name != "nt":
        time.sleep(1.0); return
    end = time.time() + timeout
    while time.time() < end:
        try:
            import ctypes
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            SYNCHRONIZE = 0x00100000
            handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, False, int(pid))
            if not handle:
                return
            WAIT_OBJECT_0 = 0
            result = ctypes.windll.kernel32.WaitForSingleObject(handle, 500)
            ctypes.windll.kernel32.CloseHandle(handle)
            if result == WAIT_OBJECT_0:
                return
        except Exception:
            time.sleep(0.5)
    raise RuntimeError("CorePulse no terminó a tiempo para aplicar la actualización")

def clear_managed(root):
    for name in MANAGED_DIRS:
        path = root / name
        if path.is_dir(): shutil.rmtree(path, ignore_errors=False)
        elif path.exists(): path.unlink()

def copy_incoming(incoming, root):
    clear_managed(root)
    for src in incoming.iterdir():
        if src.name in PRESERVE: continue
        dst = root / src.name
        if src.is_dir():
            if dst.exists():
                if dst.is_dir(): shutil.rmtree(dst)
                else: dst.unlink()
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)

def restore_zip(backup, root):
    with zipfile.ZipFile(backup, "r") as zf:
        for item in zf.infolist():
            name = item.filename.replace('\\', '/')
            if not (root / name).resolve().is_relative_to(root) or any(p in PRESERVE for p in Path(name).parts):
                raise RuntimeError('Backup con rutas no permitidas')
        clear_managed(root)
        zf.extractall(root)

def relaunch(plan, root):
    py = plan.get("python") or sys.executable
    entry = root / (plan.get("relaunch") or "main.py")
    if entry.is_file():
        subprocess.Popen([py, str(entry)], cwd=str(root), close_fds=True)

def main():
    plan = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    root = Path(plan["current_root"]).resolve()
    status = plan["status"]
    modified = False
    try:
        if plan.get("mode") == "side-by-side":
            target = Path(plan["target_root"]).resolve()
            if not (target / 'main.py').is_file() or not (target / 'core' / 'version.py').is_file():
                raise RuntimeError('La nueva versión preparada no es reconocible')
            wait_pid(plan.get('pid', 0))
            relaunch(plan, target)
            write_status(status, ok=True, action="side-by-side", target_version=plan.get("target_version"),
                         installed_root=str(target), finished_at=time.time())
            return
        if not (root / 'main.py').is_file() or not (root / 'core' / 'version.py').is_file():
            raise RuntimeError('Destino de actualización no reconocido')
        if any(p.is_symlink() or p.is_junction() for p in root.iterdir()):
            raise RuntimeError('El destino contiene enlaces; actualización automática no admitida')
        if any((parent / '.git').exists() for parent in [root, *list(root.parents)[:4]]):
            raise RuntimeError('El destino pertenece a un checkout Git')
        backup = Path(plan['backup_zip'])
        if digest_file(backup) != plan.get('backup_sha256'):
            raise RuntimeError('La copia de seguridad cambió o no está verificada')
        if plan.get('mode') == 'update':
            incoming = Path(plan['incoming_root']).resolve()
            if incoming == root or incoming.is_relative_to(root) or root.is_relative_to(incoming):
                raise RuntimeError('Origen y destino de actualización se solapan')
            files = plan.get('incoming_files') or {}
            actual_files = {str(p.relative_to(incoming)) for p in incoming.rglob('*') if p.is_file()}
            if not files or actual_files != set(files):
                raise RuntimeError('Cambió el contenido del paquete preparado')
            for relative, digest in files.items():
                path = (incoming / relative).resolve()
                if not path.is_relative_to(incoming) or digest_file(path) != digest:
                    raise RuntimeError('Cambió el paquete preparado')
        elif plan.get('mode') != 'rollback':
            raise RuntimeError('Operación de actualización no válida')
        wait_pid(plan.get('pid', 0))
        modified = True
        if plan.get("mode") == "rollback":
            restore_zip(Path(plan["backup_zip"]), root)
            write_status(status, ok=True, action="rollback", finished_at=time.time(), backup=plan["backup_zip"])
        else:
            incoming = Path(plan["incoming_root"]).resolve()
            copy_incoming(incoming, root)
            write_status(status, ok=True, action="update", target_version=plan.get("target_version"), finished_at=time.time(), backup=plan.get("backup_zip"))
    except Exception as exc:
        try:
            backup = Path(plan.get("backup_zip") or "")
            if modified and backup.is_file(): restore_zip(backup, root)
        except Exception:
            pass
        write_status(status, ok=False, action=plan.get("mode"), error=f"{type(exc).__name__}: {exc}", finished_at=time.time(), backup=plan.get("backup_zip"))
    if modified:
        try:
            relaunch(plan, root)
        except Exception as exc:
            write_status(status, ok=False, action=plan.get('mode'), error='No se pudo reiniciar: ' + str(exc), finished_at=time.time())

if __name__ == "__main__":
    main()
'''

# Extiende exportaciones sin romper imports históricos de V118.
try:
    __all__.extend([
        "CHANNEL_DEVELOPMENT", "installation_mode", "source_update_supported",
        "resolve_release_sha256", "download_asset_verified", "backup_dir",
        "create_source_backup", "list_source_backups", "prepare_source_update",
        "prepare_side_by_side_source_update", "prepare_source_rollback",
        "launch_source_update_helper", "read_last_update_status",
    ])
except Exception:
    pass
