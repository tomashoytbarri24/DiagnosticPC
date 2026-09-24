"""Presentación segura del catálogo de juegos de CorePulse.

La detección continúa usando el nombre real del ejecutable. Este módulo sólo
transforma metadatos para UI: nombre amigable e icono del EXE cuando Windows
permite leerlo. Si no hay evidencia suficiente, devuelve un fallback visual y
nunca inventa rutas ni títulos de una tienda.
"""
from __future__ import annotations

import logging
import os
import json
import io
import hashlib
from pathlib import Path
import re
import urllib.parse
import urllib.request
from typing import Optional

from PIL import Image, ImageDraw, ImageOps

logger = logging.getLogger('CorePulse.GamePresentation')

_COMMON_EXEC_SUFFIXES = (
    r'(?i)[\s._-]*win(?:32|64)[\s._-]*shipping$',
    r'(?i)[\s._-]*shipping$',
    r'(?i)[\s._-]*x64$',
    r'(?i)[\s._-]*x86$',
)


def _strip_exe(value: str | os.PathLike | None) -> str:
    raw = str(value or '').replace('\\', '/').strip()
    name = raw.rsplit('/', 1)[-1]
    return name[:-4] if name.lower().endswith('.exe') else name


def _clean_candidate(value: str | os.PathLike | None) -> str:
    name = _strip_exe(value)
    name = re.sub(r'[_\-.]+', ' ', name).strip()
    for pattern in _COMMON_EXEC_SUFFIXES:
        name = re.sub(pattern, '', name).strip()
    # Separa CamelCase sin destruir siglas como GTA, CS2 o DX12.
    name = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip()
    if not name:
        return 'N/A'
    # Un ejecutable enteramente minúsculo obtiene una capitalización mínima;
    # no intentamos adivinar un título comercial que no esté presente.
    if name == name.lower():
        name = name[:1].upper() + name[1:]
    return name


def _windows_version_title(exe_path: str | os.PathLike | None) -> Optional[str]:
    if os.name != 'nt':
        return None
    path = str(exe_path or '').strip()
    if not path or not Path(path).is_file():
        return None
    try:
        import win32api  # type: ignore
        info = win32api.GetFileVersionInfo(path, '\\')
        translations = win32api.GetFileVersionInfo(path, r'\VarFileInfo\Translation') or []
        for lang, codepage in translations:
            prefix = rf'\StringFileInfo\{lang:04x}{codepage:04x}'
            for key in ('ProductName', 'FileDescription'):
                try:
                    value = win32api.GetFileVersionInfo(path, prefix + '\\' + key)
                except Exception:
                    value = None
                cleaned = _clean_candidate(value)
                if value and cleaned not in {'N/A', 'Application'}:
                    return cleaned
        # Algunos binarios carecen de tabla de traducción pero sí exponen metadatos fijos.
        _ = info
    except Exception:
        logger.debug('[GAME_UI] Metadatos de versión no disponibles para %s', path, exc_info=True)
    return None


def display_game_name(
    exe_name: str | os.PathLike | None,
    exe_path: str | os.PathLike | None = None,
    name_hint: str | os.PathLike | None = None,
) -> str:
    """Nombre visible sin ``.exe``.

    Prioriza metadatos reales del binario en Windows. Si no existen, conserva el
    nombre observado originalmente por CorePulse (incluido CamelCase) y sólo al
    final cae al identificador normalizado del ejecutable.
    """
    metadata_title = _windows_version_title(exe_path)
    if metadata_title:
        return metadata_title
    if name_hint:
        return _clean_candidate(name_hint)
    return _clean_candidate(exe_name)


def fallback_game_icon(size: int = 48) -> Image.Image:
    """Icono genérico dibujado localmente cuando no hay icono real disponible."""
    size = max(24, int(size or 48))
    image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    margin = max(3, size // 10)
    body = (margin, size // 3, size - margin, size - margin)
    draw.rounded_rectangle(body, radius=max(5, size // 7), fill=(20, 184, 255, 235))
    # D-pad.
    cx, cy = size * 0.34, size * 0.57
    arm = max(2, size // 14)
    reach = max(5, size // 9)
    draw.rectangle((cx - arm, cy - reach, cx + arm, cy + reach), fill=(6, 17, 31, 230))
    draw.rectangle((cx - reach, cy - arm, cx + reach, cy + arm), fill=(6, 17, 31, 230))
    # Botones.
    r = max(2, size // 18)
    for x, y in ((size * 0.68, size * 0.52), (size * 0.76, size * 0.62)):
        draw.ellipse((x-r, y-r, x+r, y+r), fill=(6, 17, 31, 230))
    return image


def extract_executable_icon(exe_path: str | os.PathLike | None, size: int = 48) -> Image.Image:
    """Extrae el icono asociado al EXE en Windows y devuelve PIL RGBA.

    Usa pywin32, ya requerido por CorePulse en Windows. Ante cualquier fallo,
    devuelve un icono genérico: la UI nunca depende de que la extracción funcione.
    """
    size = max(24, int(size or 48))
    path = str(exe_path or '').strip()
    if os.name != 'nt' or not path or not Path(path).is_file():
        return fallback_game_icon(size)

    large = []
    small = []
    hicon = None
    screen_dc_handle = None
    mem_dc = None
    bitmap = None
    try:
        import win32api  # type: ignore
        import win32con  # type: ignore
        import win32gui  # type: ignore
        import win32ui  # type: ignore

        large, small = win32gui.ExtractIconEx(path, 0)
        if large:
            hicon = large[0]
        elif small:
            hicon = small[0]
        if not hicon:
            return fallback_game_icon(size)

        screen_dc_handle = win32gui.GetDC(0)
        screen_dc = win32ui.CreateDCFromHandle(screen_dc_handle)
        mem_dc = screen_dc.CreateCompatibleDC()
        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(screen_dc, size, size)
        mem_dc.SelectObject(bitmap)

        # Fondo transparente/negro; el icono se compone encima. Muchos iconos modernos
        # conservan alpha en DrawIconEx; en iconos antiguos aplicamos un alpha por luminancia.
        win32gui.DrawIconEx(mem_dc.GetSafeHdc(), 0, 0, hicon, size, size, 0, None, win32con.DI_NORMAL)
        info = bitmap.GetInfo()
        bits = bitmap.GetBitmapBits(True)
        image = Image.frombuffer(
            'RGBA', (info['bmWidth'], info['bmHeight']), bits,
            'raw', 'BGRA', 0, 1,
        ).copy()
        alpha = image.getchannel('A')
        if not alpha.getbbox():
            rgb = image.convert('RGB')
            mask = Image.new('L', image.size, 0)
            mask_data = []
            for r, g, b in rgb.getdata():
                mask_data.append(0 if (r < 4 and g < 4 and b < 4) else 255)
            mask.putdata(mask_data)
            image.putalpha(mask)
        if not image.getbbox():
            return fallback_game_icon(size)
        return image.resize((size, size), Image.Resampling.LANCZOS)
    except Exception:
        logger.debug('[GAME_UI] No se pudo extraer icono de %s', path, exc_info=True)
        return fallback_game_icon(size)
    finally:
        try:
            if mem_dc is not None:
                mem_dc.DeleteDC()
        except Exception:
            pass
        try:
            if bitmap is not None:
                import win32gui  # type: ignore
                win32gui.DeleteObject(bitmap.GetHandle())
        except Exception:
            pass
        try:
            if screen_dc_handle is not None:
                import win32gui  # type: ignore
                win32gui.ReleaseDC(0, screen_dc_handle)
        except Exception:
            pass
        try:
            import win32gui  # type: ignore
            for handle in set(large + small):
                if handle:
                    win32gui.DestroyIcon(handle)
        except Exception:
            pass


_ARTWORK_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}
_NVIDIA_ARTWORK_CACHE = {
    'storage_mtime': None,
    'storage_path': None,
    'applications': [],
    'images': [],
}


def _normalized_path_text(value) -> str:
    try:
        return os.path.normcase(os.path.normpath(os.path.expandvars(str(value or '').strip().strip('\"'))))
    except Exception:
        return str(value or '').strip().casefold()


def _iter_record_strings(value, *, depth=0, limit=400):
    """Extrae strings de un registro NVIDIA sin depender de un schema fijo."""
    if depth > 6 or limit <= 0:
        return []
    out = []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        for item in value.values():
            if len(out) >= limit:
                break
            out.extend(_iter_record_strings(item, depth=depth + 1, limit=limit - len(out)))
    elif isinstance(value, (list, tuple)):
        for item in value:
            if len(out) >= limit:
                break
            out.extend(_iter_record_strings(item, depth=depth + 1, limit=limit - len(out)))
    return out


def _nvidia_backend_paths():
    """Rutas de NVIDIA App resueltas por variables de Windows, nunca por usuario fijo."""
    if os.name != 'nt':
        return None, None
    local = os.environ.get('LOCALAPPDATA')
    if not local:
        return None, None
    app_root = Path(local) / 'NVIDIA Corporation' / 'NVIDIA app'
    backend = app_root / 'NvBackend'
    storage = backend / 'ApplicationStorage.json'
    return app_root, storage


def _nvidia_image_inventory(app_root: Path, limit: int = 2600):
    """Indexa sólo imágenes locales de NVIDIA App y evita recorrer el PC completo."""
    roots = [
        app_root / 'NvBackend',
        app_root / 'NvBackend' / 'ApplicationOntology',
        app_root / 'CefCache',
        app_root / 'Cache',
    ]
    found = []
    seen = set()
    for root in roots:
        if len(found) >= limit or not root.is_dir():
            continue
        try:
            base_depth = len(root.parts)
            for folder, dirs, files in os.walk(root):
                depth = len(Path(folder).parts) - base_depth
                if depth >= 6:
                    dirs[:] = []
                # Carpetas gigantes que no aportan artwork.
                dirs[:] = [d for d in dirs if d.lower() not in {'logs', 'temp', 'crashdumps', 'gpucrashdumps'}]
                for name in files:
                    if len(found) >= limit:
                        break
                    path = Path(folder) / name
                    if path.suffix.lower() not in _ARTWORK_EXTENSIONS:
                        continue
                    try:
                        key = str(path.resolve()).casefold()
                    except Exception:
                        key = str(path).casefold()
                    if key in seen:
                        continue
                    seen.add(key)
                    found.append(path)
        except OSError:
            continue
    return found


def _load_nvidia_application_index():
    """Carga ApplicationStorage y el inventario de imágenes con caché por mtime."""
    app_root, storage = _nvidia_backend_paths()
    if app_root is None or storage is None or not storage.is_file():
        return app_root, [], []
    try:
        mtime = storage.stat().st_mtime_ns
    except OSError:
        mtime = None
    cache = _NVIDIA_ARTWORK_CACHE
    if cache.get('storage_path') == str(storage) and cache.get('storage_mtime') == mtime:
        return app_root, list(cache.get('applications') or []), list(cache.get('images') or [])
    applications = []
    try:
        # ApplicationStorage puede ser grande; se lee una sola vez por modificación.
        raw = json.loads(storage.read_text(encoding='utf-8', errors='ignore'))
        if isinstance(raw, dict):
            candidates = raw.get('Applications')
            if isinstance(candidates, list):
                applications = [x for x in candidates if isinstance(x, dict)]
            else:
                # Compatibilidad con variantes de schema: busca la primera lista
                # de registros que contenga objetos Application/DetectedFiles.
                for value in raw.values():
                    if isinstance(value, list) and value and isinstance(value[0], dict):
                        if any(('Application' in x or 'DetectedFiles' in x) for x in value[:8] if isinstance(x, dict)):
                            applications = [x for x in value if isinstance(x, dict)]
                            break
    except Exception:
        logger.debug('[GAME_UI] NVIDIA ApplicationStorage no pudo analizarse', exc_info=True)
    images = _nvidia_image_inventory(app_root) if app_root.is_dir() else []
    cache.update({
        'storage_mtime': mtime,
        'storage_path': str(storage),
        'applications': applications,
        'images': images,
    })
    return app_root, applications, images


def _nvidia_record_match_score(record, exe: Path, title_hint: str | None = None) -> float:
    strings = _iter_record_strings(record)
    if not strings:
        return -1.0
    exe_norm = _normalized_path_text(exe)
    exe_name = exe.name.casefold()
    exe_stem = exe.stem.casefold()
    parent_norm = _normalized_path_text(exe.parent)
    score = 0.0
    title_tokens = _artwork_tokens(title_hint) if title_hint else set()
    for raw in strings:
        text = str(raw or '').strip()
        low = text.casefold()
        norm = _normalized_path_text(text)
        if norm == exe_norm:
            score = max(score, 220.0)
        elif low.endswith('\\' + exe_name) or low.endswith('/' + exe_name) or low == exe_name:
            score = max(score, 155.0)
        elif parent_norm and norm == parent_norm:
            score = max(score, 120.0)
        elif exe_stem and len(exe_stem) >= 5 and exe_stem in low:
            score = max(score, 62.0)
        compact = re.sub(r'[^a-z0-9]+', '', low)
        if title_tokens and any(token in compact for token in title_tokens if len(token) >= 4):
            score = max(score, 105.0)
    return score


def _nvidia_artwork_tokens(record, exe: Path):
    tokens = set()
    tokens.add(exe.stem.casefold())
    for key in ('LocalId', 'CmsId', 'Id', 'ShortName', 'DisplayName', 'Name'):
        value = record.get(key) if isinstance(record, dict) else None
        if value not in (None, ''):
            tokens.add(str(value).strip().casefold())
        app = record.get('Application') if isinstance(record, dict) and isinstance(record.get('Application'), dict) else {}
        value = app.get(key)
        if value not in (None, ''):
            tokens.add(str(value).strip().casefold())
    # URLs/rutas del registro pueden contener el identificador exacto del artwork.
    for raw in _iter_record_strings(record):
        text = str(raw or '').strip()
        if not text:
            continue
        try:
            name = Path(text.replace('\\', '/')).name
            stem = Path(name).stem.casefold()
            if len(stem) >= 6:
                tokens.add(stem)
        except Exception:
            pass
    clean = set()
    for token in tokens:
        normalized = re.sub(r'[^a-z0-9]+', '', token.casefold())
        if len(normalized) >= 4:
            clean.add(normalized)
    return clean


def discover_nvidia_app_artwork(exe_path: str | os.PathLike | None, *, title_hint: str | None = None) -> Optional[Path]:
    """Obtiene artwork local que NVIDIA App ya asoció al ejecutable.

    No contiene rutas de usuario ni nombres de juegos codificados. La asociación
    se demuestra con ``ApplicationStorage.json`` del propio equipo y después se
    puntúan sólo imágenes dentro de la instalación/cache local de NVIDIA App.
    """
    raw = str(exe_path or '').strip()
    if os.name != 'nt' or not raw:
        return None
    try:
        exe = Path(raw)
    except Exception:
        return None
    _root, applications, images = _load_nvidia_application_index()
    if not applications or not images:
        return None
    ranked = []
    for record in applications:
        score = _nvidia_record_match_score(record, exe, title_hint=title_hint)
        if score >= 60:
            ranked.append((score, record))
    if not ranked:
        return None
    ranked.sort(key=lambda item: item[0], reverse=True)
    record = ranked[0][1]
    tokens = _nvidia_artwork_tokens(record, exe)
    tokens.update(_artwork_tokens(title_hint))

    # Primera opción: si el registro contiene una ruta local de imagen, úsala.
    for raw_value in _iter_record_strings(record):
        try:
            candidate = Path(os.path.expandvars(str(raw_value))).expanduser()
        except Exception:
            continue
        if candidate.is_file() and candidate.suffix.lower() in _ARTWORK_EXTENSIONS and is_supported_artwork_file(candidate):
            return candidate

    best = None
    best_score = -10000.0
    for candidate in images:
        compact = re.sub(r'[^a-z0-9]+', '', str(candidate).casefold())
        hits = [token for token in tokens if token and token in compact]
        if not hits:
            continue
        token_bonus = max(35.0, min(180.0, 28.0 * len(hits)))
        score = _artwork_score(candidate) + token_bonus
        if score > best_score:
            best, best_score = candidate, score
    return best

_ARTWORK_KEYWORDS = (
    ('library_hero', 80), ('hero', 70), ('header', 68), ('banner', 62),
    ('capsule', 58), ('cover', 54), ('keyart', 52), ('key_art', 52),
    ('splash', 50), ('background', 44), ('library', 36), ('promo', 32),
)


def is_supported_artwork_file(value: str | os.PathLike | None) -> bool:
    """True sólo para una imagen local existente que Pillow puede abrir."""
    try:
        path = Path(os.fspath(value)).expanduser()
    except Exception:
        return False
    if not path.is_file() or path.suffix.lower() not in _ARTWORK_EXTENSIONS:
        return False
    try:
        with Image.open(path) as image:
            image.verify()
        return True
    except Exception:
        return False


def _steam_context(exe_path: str | os.PathLike | None):
    """Resuelve (appid, raíz del juego, raíz Steam) usando manifests locales.

    No consulta Internet ni adivina AppIDs. Si la ruta no demuestra que pertenece
    a ``steamapps/common`` devuelve valores vacíos.
    """
    raw = str(exe_path or '').strip()
    if not raw:
        return None, None, None
    try:
        path = Path(raw)
        common = next(
            (parent for parent in path.parents
             if parent.name.lower() == 'common' and parent.parent.name.lower() == 'steamapps'),
            None,
        )
        if common is None:
            return None, None, None
        rel = path.relative_to(common)
        if not rel.parts:
            return None, None, None
        game_root = common / rel.parts[0]
        steamapps = common.parent
        appid = None
        target_dir = game_root.name.casefold()
        for manifest in steamapps.glob('appmanifest_*.acf'):
            try:
                text = manifest.read_text(encoding='utf-8', errors='ignore')[:262144]
            except OSError:
                continue
            install = re.search(r'"installdir"\s+"([^"]+)"', text, flags=re.I)
            if not install or install.group(1).strip().casefold() != target_dir:
                continue
            match = re.search(r'"appid"\s+"(\d+)"', text, flags=re.I)
            if match:
                appid = match.group(1)
                break
            stem_match = re.search(r'(\d+)$', manifest.stem)
            if stem_match:
                appid = stem_match.group(1)
                break
        return appid, game_root, steamapps.parent
    except Exception:
        logger.debug('[GAME_UI] No se pudo resolver contexto Steam para %s', raw, exc_info=True)
        return None, None, None


def _candidate_images(directory: Path, *, recursive=False, limit=64):
    if not directory or not directory.is_dir():
        return []
    try:
        iterator = directory.rglob('*') if recursive else directory.glob('*')
        result = []
        for path in iterator:
            if len(result) >= limit:
                break
            try:
                if path.is_file() and path.suffix.lower() in _ARTWORK_EXTENSIONS:
                    result.append(path)
            except OSError:
                continue
        return result
    except OSError:
        return []


def _artwork_score(path: Path) -> float:
    """Puntúa evidencia visual local; favorece arte panorámico y nombres de portada."""
    name = path.stem.lower()
    score = 0.0
    for keyword, points in _ARTWORK_KEYWORDS:
        if keyword in name:
            score += points
            break
    try:
        with Image.open(path) as image:
            width, height = image.size
        if width < 240 or height < 90:
            return -1000.0
        aspect = width / max(1, height)
        # La biblioteca NVIDIA-style usa una tarjeta panorámica; 16:9 es ideal,
        # pero aceptamos headers 460x215 y arte 2:1 sin distorsionar.
        score += max(0.0, 45.0 - abs(aspect - (16 / 9)) * 28.0)
        score += min(25.0, (width * height) / 180000.0)
    except Exception:
        return -1000.0
    return score


def _best_artwork(candidates):
    best = None
    best_score = -10000.0
    seen = set()
    for candidate in candidates:
        try:
            key = str(candidate.resolve()).casefold()
        except Exception:
            key = str(candidate).casefold()
        if key in seen:
            continue
        seen.add(key)
        score = _artwork_score(candidate)
        if score > best_score:
            best, best_score = candidate, score
    return best if best_score > -500 else None




def _artwork_tokens(*values) -> set[str]:
    """Tokens conservadores para asociar una imagen a un juego/launcher sin adivinar."""
    stop = {
        'game', 'games', 'launcher', 'client', 'shipping', 'win64', 'win32',
        'x64', 'live', 'release', 'retail', 'program', 'files', 'epic', 'riot',
        'steam', 'content', 'engine', 'binaries', 'windows',
    }
    tokens = set()
    for value in values:
        raw = str(value or '').casefold()
        if not raw:
            continue
        for part in re.split(r'[^a-z0-9]+', raw):
            if len(part) >= 4 and part not in stop:
                tokens.add(part)
        compact = re.sub(r'[^a-z0-9]+', '', raw)
        if 5 <= len(compact) <= 80 and compact not in stop:
            tokens.add(compact)
    return tokens


def _path_contains(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except Exception:
        p = _normalized_path_text(path)
        r = _normalized_path_text(root)
        return bool(r and (p == r or p.startswith(r.rstrip('\\/') + os.sep)))


def _bounded_images(root: Path, *, max_depth=5, limit=320):
    """Inventario acotado: nunca recorre una biblioteca completa sin límite."""
    if not root or not root.is_dir():
        return []
    found = []
    try:
        base_depth = len(root.parts)
        for folder, dirs, files in os.walk(root):
            depth = len(Path(folder).parts) - base_depth
            if depth >= max_depth:
                dirs[:] = []
            for name in files:
                if len(found) >= limit:
                    return found
                path = Path(folder) / name
                if path.suffix.lower() in _ARTWORK_EXTENSIONS:
                    found.append(path)
    except OSError:
        pass
    return found


def _best_token_matched_artwork(candidates, tokens: set[str], *, allow_keyword_only=False):
    """Elige arte sólo con evidencia de identidad o semántica fuerte de portada."""
    best = None
    best_score = -10000.0
    for candidate in candidates:
        try:
            compact = re.sub(r'[^a-z0-9]+', '', str(candidate).casefold())
            low = str(candidate).casefold()
        except Exception:
            continue
        token_hits = [t for t in tokens if len(t) >= 4 and t in compact]
        keyword_hit = any(keyword in low for keyword, _ in _ARTWORK_KEYWORDS)
        if not token_hits and not (allow_keyword_only and keyword_hit):
            continue
        score = _artwork_score(candidate)
        score += min(180.0, 42.0 * len(token_hits))
        if keyword_hit:
            score += 28.0
        if score > best_score:
            best, best_score = candidate, score
    return best if best_score > -500 else None



def _materialize_cached_artwork(blob: bytes, tokens: set[str], namespace: str) -> Optional[Path]:
    """Extrae una imagen real de un entry Chromium/Electron sólo si su key/url prueba identidad.

    Epic/Riot usan caches web con nombres hash/extensionless. El nombre del archivo no
    sirve para asociarlo al juego, por lo que exigimos que el propio entry contenga un
    token del título/catalog id antes de extraer JPEG/PNG/WebP embebido.
    """
    if not blob or not tokens:
        return None
    low = blob.lower()
    matched = False
    for token in tokens:
        try:
            raw = token.encode('utf-8', errors='ignore').lower()
        except Exception:
            continue
        if len(raw) >= 4 and raw in low:
            matched = True
            break
    if not matched:
        return None

    offsets = []
    for magic in (b'\xff\xd8\xff', b'\x89PNG\r\n\x1a\n'):
        start = 0
        while len(offsets) < 8:
            idx = blob.find(magic, start)
            if idx < 0:
                break
            offsets.append(idx)
            start = idx + 1
    # WebP: RIFF....WEBP
    start = 0
    while len(offsets) < 12:
        idx = blob.find(b'RIFF', start)
        if idx < 0:
            break
        if idx + 12 <= len(blob) and blob[idx + 8:idx + 12] == b'WEBP':
            offsets.append(idx)
        start = idx + 4

    best_image = None
    best_area = 0
    for offset in sorted(set(offsets)):
        try:
            with Image.open(io.BytesIO(blob[offset:])) as image:
                image.load()
                width, height = image.size
                if width < 240 or height < 90:
                    continue
                area = width * height
                if area > best_area:
                    best_image = image.convert('RGB').copy()
                    best_area = area
        except Exception:
            continue
    if best_image is None:
        return None

    local = os.environ.get('LOCALAPPDATA')
    if not local:
        return None
    digest = hashlib.sha256(blob[:65536] + str(best_image.size).encode('ascii')).hexdigest()[:24]
    target = Path(local) / 'CorePulse' / 'cache' / 'game_artwork' / f'{namespace}_{digest}.jpg'
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.is_file():
            best_image.save(target, 'JPEG', quality=92, optimize=True)
        return target if is_supported_artwork_file(target) else None
    except Exception:
        logger.debug('[GAME_UI] No se pudo materializar artwork de cache %s', namespace, exc_info=True)
        return None


_OFFICIAL_ARTWORK_HOSTS = {
    'epic': ('epicgames.com', 'epicgamesusercontent.com', 'unrealengine.com', 'akamaized.net'),
    'riot': ('riotgames.com', 'riotcdn.net', 'pvp.net', 'playvalorant.com', 'leagueoflegends.com'),
}


def _blob_matches_artwork_tokens(blob: bytes, tokens: set[str]) -> bool:
    if not blob or not tokens:
        return False
    low = blob.lower()
    for token in tokens:
        try:
            raw = token.encode('utf-8', errors='ignore').lower()
        except Exception:
            continue
        if len(raw) >= 4 and raw in low:
            return True
    return False


def _artwork_urls_from_blob(blob: bytes, tokens: set[str], namespace: str, *, identity_proven=False):
    """Extrae URLs de imagen sólo de entries que ya prueban la identidad del juego.

    Los launchers Chromium suelen guardar el JSON/HTML con la URL de portada en
    un archivo y la imagen en otro. La versión anterior exigía token+bytes de la
    imagen dentro del mismo entry, por lo que Epic/Riot fallaban en caches reales.
    """
    if not identity_proven and not _blob_matches_artwork_tokens(blob, tokens):
        return []
    try:
        text = blob.decode('utf-8', errors='ignore').replace('\\/', '/')
    except Exception:
        return []
    hosts = _OFFICIAL_ARTWORK_HOSTS.get(str(namespace or '').lower(), ())
    urls = []
    seen = set()
    pattern = re.compile(r'https?://[^\s"\'<>]+', re.I)
    for match in pattern.findall(text):
        url = match.rstrip('),]}\\')
        low = url.casefold()
        try:
            parsed = urllib.parse.urlparse(url)
            host = (parsed.hostname or '').casefold()
        except Exception:
            continue
        if not host or hosts and not any(host == h or host.endswith('.' + h) for h in hosts):
            continue
        path_low = (parsed.path or '').casefold()
        looks_image = any(ext in path_low for ext in ('.jpg', '.jpeg', '.png', '.webp'))
        looks_art = any(key in low for key, _ in _ARTWORK_KEYWORDS) or any(word in low for word in ('image', 'landscape', 'offerimage', 'productimage'))
        if not (looks_image or looks_art):
            continue
        if url in seen:
            continue
        seen.add(url)
        score = 0
        for keyword, points in _ARTWORK_KEYWORDS:
            if keyword in low:
                score += points
                break
        if looks_image:
            score += 25
        if 'landscape' in low:
            score += 30
        urls.append((score, url))
    urls.sort(key=lambda item: item[0], reverse=True)
    return [url for _score, url in urls[:12]]


def _download_official_artwork(url: str, namespace: str) -> Optional[Path]:
    """Descarga una portada desde una URL oficial ya demostrada por el cache local."""
    try:
        parsed = urllib.parse.urlparse(str(url or ''))
        host = (parsed.hostname or '').casefold()
        hosts = _OFFICIAL_ARTWORK_HOSTS.get(str(namespace or '').lower(), ())
        if parsed.scheme != 'https' or not host or not any(host == h or host.endswith('.' + h) for h in hosts):
            return None
        local = os.environ.get('LOCALAPPDATA')
        if not local:
            return None
        digest = hashlib.sha256(url.encode('utf-8', errors='ignore')).hexdigest()[:24]
        target = Path(local) / 'CorePulse' / 'cache' / 'game_artwork' / f'{namespace}_remote_{digest}.jpg'
        if is_supported_artwork_file(target):
            return target
        req = urllib.request.Request(url, headers={'User-Agent': 'CorePulse/113 GameArtwork'})
        with urllib.request.urlopen(req, timeout=4.0) as response:
            content_type = str(response.headers.get('Content-Type') or '').casefold()
            if content_type and 'image/' not in content_type:
                return None
            data = response.read(12 * 1024 * 1024 + 1)
        if not data or len(data) > 12 * 1024 * 1024:
            return None
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            width, height = image.size
            if width < 240 or height < 90:
                return None
            rendered = image.convert('RGB')
        target.parent.mkdir(parents=True, exist_ok=True)
        rendered.save(target, 'JPEG', quality=92, optimize=True)
        return target if is_supported_artwork_file(target) else None
    except Exception:
        logger.debug('[GAME_UI] Artwork remoto oficial no disponible: %s', url, exc_info=True)
        return None


def _discover_metadata_url_artwork(roots, tokens: set[str], namespace: str, *, limit=120) -> Optional[Path]:
    """Resuelve URLs oficiales guardadas en metadata ya asociada al producto.

    Riot y otros launchers suelen guardar logo/banner como URL en JSON/YAML y no
    como archivo de imagen. Si la carpeta/manifest ya fue asociado al ejecutable,
    no exigimos que el mismo texto repita el título del juego.
    """
    urls = []
    checked = 0
    allowed_suffixes = {'.json', '.yaml', '.yml', '.txt', '.ini', '.cfg', '.manifest', '.item'}
    for root in roots:
        root = Path(root)
        if not root.exists():
            continue
        iterator = [root] if root.is_file() else root.rglob('*')
        try:
            for path in iterator:
                if checked >= limit:
                    break
                try:
                    if not path.is_file() or path.suffix.casefold() not in allowed_suffixes:
                        continue
                    size = path.stat().st_size
                except OSError:
                    continue
                if size <= 0 or size > 3 * 1024 * 1024:
                    continue
                checked += 1
                try:
                    blob = path.read_bytes()
                except OSError:
                    continue
                for url in _artwork_urls_from_blob(blob, tokens, namespace, identity_proven=True):
                    if url not in urls:
                        urls.append(url)
        except OSError:
            continue
    for url in urls[:8]:
        resolved = _download_official_artwork(url, namespace)
        if resolved is not None:
            return resolved
    return None


def _discover_browser_cache_artwork(roots, tokens: set[str], namespace: str, *, limit=520) -> Optional[Path]:
    """Inspecciona caches Chromium/Electron y resuelve bytes o URLs oficiales."""
    checked = 0
    remote_urls = []
    for root in roots:
        if not root or not Path(root).is_dir():
            continue
        try:
            base = Path(root)
            base_depth = len(base.parts)
            for folder, dirs, files in os.walk(base):
                depth = len(Path(folder).parts) - base_depth
                if depth >= 7:
                    dirs[:] = []
                for name in files:
                    if checked >= limit:
                        break
                    checked += 1
                    path = Path(folder) / name
                    try:
                        size = path.stat().st_size
                    except OSError:
                        continue
                    if size < 256 or size > 12 * 1024 * 1024:
                        continue
                    if path.suffix.lower() in _ARTWORK_EXTENSIONS:
                        continue
                    try:
                        blob = path.read_bytes()
                    except OSError:
                        continue
                    resolved = _materialize_cached_artwork(blob, tokens, namespace)
                    if resolved is not None:
                        return resolved
                    if len(remote_urls) < 24:
                        for url in _artwork_urls_from_blob(blob, tokens, namespace):
                            if url not in remote_urls:
                                remote_urls.append(url)
                if checked >= limit:
                    break
        except OSError:
            continue
    # Las descargas se prueban al final para no bloquear el scan local. Máximo 6.
    for url in remote_urls[:6]:
        resolved = _download_official_artwork(url, namespace)
        if resolved is not None:
            return resolved
    return None


def _epic_manifest_for_exe(exe: Path):
    program_data = Path(os.environ.get('PROGRAMDATA', r'C:\ProgramData'))
    manifest_dir = program_data / 'Epic' / 'EpicGamesLauncher' / 'Data' / 'Manifests'
    if not manifest_dir.is_dir():
        return None, None
    exe_norm = _normalized_path_text(exe)
    best = None
    best_root = None
    for file in manifest_dir.glob('*.item'):
        try:
            data = json.loads(file.read_text(encoding='utf-8', errors='ignore'))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        raw_root = str(data.get('InstallLocation') or '').strip()
        if not raw_root:
            continue
        root = Path(os.path.expandvars(raw_root))
        root_norm = _normalized_path_text(root)
        if root_norm and (exe_norm == root_norm or exe_norm.startswith(root_norm.rstrip('\\/') + os.sep)):
            best, best_root = data, root
            break
        launch = str(data.get('LaunchExecutable') or '').replace('\\', '/').strip().casefold()
        if launch and exe.name.casefold() == Path(launch).name.casefold():
            best, best_root = data, root
    return best, best_root


def discover_epic_artwork(exe_path, *, title_hint=None) -> Optional[Path]:
    """Arte Epic local asociado mediante el manifest real de esa instalación."""
    raw = str(exe_path or '').strip()
    if not raw:
        return None
    exe = Path(raw)
    manifest, root = _epic_manifest_for_exe(exe)
    if not manifest or not root:
        return None
    tokens = _artwork_tokens(
        title_hint, exe.stem, root.name,
        manifest.get('DisplayName'), manifest.get('AppName'),
        manifest.get('CatalogItemId'), manifest.get('MainGameAppName'),
    )
    # Algunos .item incluyen URLs de splash/key art. El manifest ya quedó
    # asociado al EXE por InstallLocation/LaunchExecutable, por lo que es seguro
    # usar únicamente URLs oficiales presentes en ese registro.
    try:
        manifest_blob = json.dumps(manifest, ensure_ascii=False).encode('utf-8')
    except Exception:
        manifest_blob = b''
    for url in _artwork_urls_from_blob(manifest_blob, tokens, 'epic', identity_proven=True):
        remote = _download_official_artwork(url, 'epic')
        if remote is not None:
            return remote
    candidates = []
    # Primero la instalación: splashes/key art suelen vivir aquí en juegos UE/Epic.
    candidates.extend(_candidate_images(root, recursive=False, limit=48))
    likely_dirs = [
        root / '.egstore', root / 'Splash', root / 'splash', root / 'Assets', root / 'assets',
        root / 'Art', root / 'Artwork', root / 'Images', root / 'Media',
        root / 'Engine' / 'Splash', root / 'Engine' / 'Content' / 'Splash',
        root / 'Content' / 'Splash',
    ]
    try:
        for child in list(root.iterdir())[:64]:
            if child.is_dir():
                likely_dirs.extend([
                    child / 'Content' / 'Splash', child / 'Splash', child / 'Assets',
                    child / 'Artwork', child / 'Images',
                ])
    except OSError:
        pass
    for folder in likely_dirs:
        candidates.extend(_bounded_images(folder, max_depth=4, limit=100))
    best = _best_token_matched_artwork(candidates, tokens, allow_keyword_only=True)
    if best:
        return best

    # Epic Launcher puede conservar jpg/png con identificadores del catálogo.
    local = os.environ.get('LOCALAPPDATA')
    if local:
        saved = Path(local) / 'EpicGamesLauncher' / 'Saved'
        cache_candidates = _bounded_images(saved, max_depth=7, limit=900)
        best = _best_token_matched_artwork(cache_candidates, tokens, allow_keyword_only=False)
        if best:
            return best
        webcache_roots = []
        try:
            webcache_roots.extend(p for p in saved.glob('webcache*') if p.is_dir())
        except OSError:
            pass
        cached = _discover_browser_cache_artwork(webcache_roots, tokens, 'epic')
        if cached is not None:
            return cached
    return None


def _riot_install_root(exe: Path) -> Optional[Path]:
    """Resuelve raíz Riot desde ruta real o RiotClientInstalls.json."""
    raw = _normalized_path_text(exe)
    for parent in [exe.parent, *exe.parents]:
        if parent.name.casefold() in {'valorant', 'league of legends', 'riot games'}:
            if parent.name.casefold() == 'riot games':
                # El hijo directo identifica el producto cuando existe.
                try:
                    rel = exe.relative_to(parent)
                    return parent / rel.parts[0] if rel.parts else parent
                except Exception:
                    return parent
            return parent
    program_data = Path(os.environ.get('PROGRAMDATA', r'C:\ProgramData'))
    installs = program_data / 'Riot Games' / 'RiotClientInstalls.json'
    try:
        data = json.loads(installs.read_text(encoding='utf-8', errors='ignore'))
    except Exception:
        data = {}
    strings = _iter_record_strings(data, limit=1000)
    for value in strings:
        candidate = Path(os.path.expandvars(str(value)))
        if candidate.suffix.casefold() == '.exe' and _normalized_path_text(candidate) == raw:
            return candidate.parent
    return None


def discover_riot_artwork(exe_path, *, title_hint=None, trusted_source=False) -> Optional[Path]:
    """Busca branding/splash Riot local sin asumir un título concreto."""
    raw = str(exe_path or '').strip()
    if not raw:
        return None
    exe = Path(raw)
    normalized = _normalized_path_text(exe)
    if (not trusted_source) and 'riot games' not in normalized.casefold() and 'valorant' not in normalized.casefold() and 'league of legends' not in normalized.casefold():
        return None
    root = _riot_install_root(exe) or exe.parent
    tokens = _artwork_tokens(title_hint, exe.stem, root.name)
    candidates = []
    candidates.extend(_candidate_images(root, recursive=False, limit=40))
    likely_dirs = [
        root / 'Splash', root / 'splash', root / 'Assets', root / 'assets',
        root / 'Images', root / 'images', root / 'Resources', root / 'resources',
        root / 'Content' / 'Splash', root / 'ShooterGame' / 'Content' / 'Splash',
    ]
    for folder in likely_dirs:
        candidates.extend(_bounded_images(folder, max_depth=5, limit=140))

    program_data = Path(os.environ.get('PROGRAMDATA', r'C:\ProgramData'))
    metadata_root = program_data / 'Riot Games' / 'Metadata'
    matched_metadata = []
    if metadata_root.is_dir():
        # Los nombres de las carpetas de Metadata son ids reales de producto.
        for child in list(metadata_root.iterdir())[:96]:
            if not child.is_dir():
                continue
            compact = re.sub(r'[^a-z0-9]+', '', child.name.casefold())
            if any(t in compact or compact in t for t in tokens if len(t) >= 4):
                matched_metadata.append(child)
                candidates.extend(_bounded_images(child, max_depth=5, limit=160))
                tokens.update(_artwork_tokens(child.name))
    best = _best_token_matched_artwork(candidates, tokens, allow_keyword_only=True)
    if best is not None:
        return best
    if matched_metadata:
        remote = _discover_metadata_url_artwork(matched_metadata, tokens, 'riot')
        if remote is not None:
            return remote
    local = os.environ.get('LOCALAPPDATA')
    if local:
        riot_local = Path(local) / 'Riot Games'
        cache_roots = [riot_local / 'Riot Client', riot_local]
        cached = _discover_browser_cache_artwork(cache_roots, tokens, 'riot')
        if cached is not None:
            return cached
    return None


def discover_other_launcher_artwork(exe_path, *, title_hint=None, source_hint=None) -> Optional[Path]:
    """Caches locales adicionales (GOG/Ubisoft/EA/Battle.net), sólo por match de tokens."""
    raw = str(exe_path or '').strip()
    if not raw:
        return None
    exe = Path(raw)
    tokens = _artwork_tokens(title_hint, exe.stem, exe.parent.name)
    local = os.environ.get('LOCALAPPDATA')
    program_data = os.environ.get('PROGRAMDATA')
    roots = []
    if local:
        base = Path(local)
        roots.extend([
            base / 'GOG.com' / 'Galaxy',
            base / 'Ubisoft Game Launcher' / 'cache',
            base / 'Electronic Arts' / 'EA Desktop',
            base / 'Battle.net',
        ])
    if program_data:
        base = Path(program_data)
        roots.extend([base / 'GOG.com' / 'Galaxy', base / 'Battle.net'])
    candidates = []
    for cache_root in roots:
        candidates.extend(_bounded_images(cache_root, max_depth=7, limit=420))
    return _best_token_matched_artwork(candidates, tokens, allow_keyword_only=False)

def discover_local_game_artwork(
    exe_path: str | os.PathLike | None,
    *,
    title_hint: str | None = None,
    source_hint: str | None = None,
) -> Optional[Path]:
    """Busca arte *real* ya presente en el PC, sin llamadas de red.

    Prioridad: cache local de Steam asociada por AppID demostrado, después assets
    de portada cercanos al directorio instalado. Nunca usa una imagen de otro juego.
    """
    raw = str(exe_path or '').strip()
    if not raw:
        return None
    try:
        exe = Path(raw)
    except Exception:
        return None

    source = str(source_hint or '').upper().strip()
    # Fuentes no-Steam primero cuando existe evidencia del launcher.
    if source == 'EPIC' or _epic_manifest_for_exe(exe)[0] is not None:
        epic = discover_epic_artwork(raw, title_hint=title_hint)
        if epic is not None:
            return epic
    if source == 'RIOT' or any(x in _normalized_path_text(exe).casefold() for x in ('riot games', 'valorant', 'league of legends')):
        riot = discover_riot_artwork(raw, title_hint=title_hint, trusted_source=(source == 'RIOT'))
        if riot is not None:
            return riot

    appid, game_root, steam_root = _steam_context(raw)
    candidates = []
    if appid and steam_root:
        cache = steam_root / 'appcache' / 'librarycache'
        # Formatos usados por distintas generaciones del cliente Steam.
        for suffix in (
            'library_hero.jpg', 'library_hero.png', 'header.jpg', 'header.png',
            'library_600x900.jpg', 'library_600x900.png', 'capsule_616x353.jpg',
        ):
            direct = cache / f'{appid}_{suffix}'
            if direct.is_file():
                candidates.append(direct)
        app_cache = cache / appid
        candidates.extend(_candidate_images(app_cache, recursive=True, limit=48))
        if cache.is_dir():
            try:
                candidates.extend(
                    p for p in list(cache.glob(f'{appid}_*'))[:48]
                    if p.is_file() and p.suffix.lower() in _ARTWORK_EXTENSIONS
                )
            except OSError:
                pass
        # Clientes Steam recientes también conservan arte en config/librarycache.
        config_cache = steam_root / 'config' / 'librarycache'
        if config_cache.is_dir():
            candidates.extend(_candidate_images(config_cache / appid, recursive=True, limit=64))
            try:
                candidates.extend(
                    p for p in list(config_cache.glob(f'{appid}_*'))[:64]
                    if p.is_file() and p.suffix.lower() in _ARTWORK_EXTENSIONS
                )
            except OSError:
                pass
        best = _best_artwork(candidates)
        if best:
            return best

    # Fallback local conservador. Sólo nombres/directorios que sugieren assets de
    # portada; no recorremos todo el juego para no seleccionar screenshots al azar.
    root = game_root
    if root is None:
        try:
            root = exe.parent
        except Exception:
            root = None
    candidates = []
    if root and root.is_dir():
        candidates.extend(_candidate_images(root, recursive=False, limit=48))
        for folder_name in ('assets', 'art', 'artwork', 'images', 'media', 'resources', 'splash', 'branding'):
            folder = root / folder_name
            candidates.extend(_candidate_images(folder, recursive=True, limit=48))
        # Sin una palabra que denote portada/banner no aceptamos una imagen local
        # arbitraria: evita presentar una captura o logo ajeno como carátula real.
        candidates = [
            p for p in candidates
            if any(keyword in p.stem.lower() for keyword, _ in _ARTWORK_KEYWORDS)
        ]
        best = _best_artwork(candidates)
        if best:
            return best

    other = discover_other_launcher_artwork(raw, title_hint=title_hint, source_hint=source_hint)
    if other is not None:
        return other
    return None


def _rounded_rgba(image: Image.Image, size: tuple[int, int], radius: int = 12) -> Image.Image:
    fitted = ImageOps.fit(
        image.convert('RGB'), size, method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.5),
    ).convert('RGBA')
    radius = max(0, min(int(radius), min(size) // 3))
    if radius:
        mask = Image.new('L', size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0]-1, size[1]-1), radius=radius, fill=255)
        fitted.putalpha(mask)
    return fitted


def fallback_game_artwork(
    exe_path: str | os.PathLike | None = None,
    size: tuple[int, int] = (320, 180),
) -> Image.Image:
    """Tarjeta segura cuando no existe portada real: fondo + icono real/genérico.

    V0.10.2.53w:
    - Las diagonales se dibujan hasta el borde útil completo.
    - Se elimina el marco interior para que el patrón no quede "corridο" dentro
      de la portada.
    - El recorte redondeado final lo decide una sola vez _rounded_rgba().
    """
    width = max(160, int(size[0])); height = max(90, int(size[1]))
    image = Image.new('RGBA', (width, height), (8, 20, 34, 255))
    draw = ImageDraw.Draw(image)

    # Base y capas discretas: fallback reconocible, limpio y sin inventar portada.
    draw.rectangle((0, 0, width, height), fill=(8, 20, 34, 255))
    footer_y = int(height * 0.72)
    draw.rectangle((0, footer_y, width, height), fill=(9, 24, 40, 255))

    # Las líneas recorren toda el área para quedar alineadas al borde de la
    # imagen; el clipping redondeado final se aplica una sola vez al final.
    stride = max(24, width // 8)
    for offset in range(-height, width + height, stride):
        draw.line((offset, height, offset + height, 0), fill=(20, 73, 112, 145), width=2)

    # Sutil línea superior para definir la tarjeta sin crear un doble marco.
    draw.line((0, 0, width, 0), fill=(31, 83, 126, 220), width=2)

    icon_size = max(52, min(92, int(height * 0.50)))
    icon = extract_executable_icon(exe_path, icon_size)
    x = (width - icon_size) // 2
    y = (height - icon_size) // 2
    image.alpha_composite(icon, (x, y))
    return _rounded_rgba(image, (width, height), radius=10)


def load_game_artwork(
    exe_path: str | os.PathLike | None,
    size: tuple[int, int] = (320, 180),
    override_path: str | os.PathLike | None = None,
    *,
    title_hint: str | None = None,
    source_hint: str | None = None,
) -> tuple[Image.Image, str, str]:
    """Devuelve ``(imagen, fuente, ruta)`` para la tarjeta del juego.

    ``fuente`` identifica el origen local (CUSTOM/STEAM_LOCAL/EPIC_LOCAL/RIOT_LOCAL/NVIDIA_APP/LOCAL). La ruta queda vacía en
    fallback, respetando REAL_OR_NA y evitando afirmar una portada inexistente.
    """
    chosen = None
    source = 'FALLBACK'
    if override_path and is_supported_artwork_file(override_path):
        chosen = Path(os.fspath(override_path)).expanduser()
        source = 'CUSTOM'
    if chosen is None:
        # Primero el launcher/instalación real del juego. Esto evita que Steam sea
        # la única tienda con carátulas fiables y permite Epic/Riot sin hardcodes.
        chosen = discover_local_game_artwork(
            exe_path, title_hint=title_hint, source_hint=source_hint,
        )
        if chosen is not None:
            source_key = str(source_hint or '').upper().strip()
            if source_key == 'EPIC' or _epic_manifest_for_exe(Path(str(exe_path or '')))[0] is not None:
                source = 'EPIC_LOCAL'
            elif source_key == 'RIOT' or any(x in _normalized_path_text(exe_path).casefold() for x in ('riot games', 'valorant', 'league of legends')):
                source = 'RIOT_LOCAL'
            elif _steam_context(exe_path)[0]:
                source = 'STEAM_LOCAL'
            else:
                source = 'LOCAL'
    if chosen is None:
        chosen = discover_nvidia_app_artwork(exe_path, title_hint=title_hint)
        if chosen is not None:
            source = 'NVIDIA_APP'
    if chosen is not None:
        try:
            with Image.open(chosen) as image:
                rendered = _rounded_rgba(image, (max(160, int(size[0])), max(90, int(size[1]))), radius=12)
            return rendered, source, str(chosen)
        except Exception:
            logger.debug('[GAME_UI] Arte local no pudo abrirse: %s', chosen, exc_info=True)
    return fallback_game_artwork(exe_path, size=size), 'FALLBACK', ''
