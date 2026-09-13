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
from pathlib import Path
import re
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


def _nvidia_record_match_score(record, exe: Path) -> float:
    strings = _iter_record_strings(record)
    if not strings:
        return -1.0
    exe_norm = _normalized_path_text(exe)
    exe_name = exe.name.casefold()
    exe_stem = exe.stem.casefold()
    parent_norm = _normalized_path_text(exe.parent)
    score = 0.0
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


def discover_nvidia_app_artwork(exe_path: str | os.PathLike | None) -> Optional[Path]:
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
        score = _nvidia_record_match_score(record, exe)
        if score >= 100:
            ranked.append((score, record))
    if not ranked:
        return None
    ranked.sort(key=lambda item: item[0], reverse=True)
    record = ranked[0][1]
    tokens = _nvidia_artwork_tokens(record, exe)

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
    ('capsule', 58), ('cover', 54), ('keyart', 50), ('background', 44),
    ('library', 36),
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


def discover_local_game_artwork(exe_path: str | os.PathLike | None) -> Optional[Path]:
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
        for folder_name in ('assets', 'art', 'artwork', 'images', 'media', 'resources'):
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
) -> tuple[Image.Image, str, str]:
    """Devuelve ``(imagen, fuente, ruta)`` para la tarjeta del juego.

    ``fuente`` es ``CUSTOM``, ``NVIDIA_APP``, ``LOCAL`` o ``FALLBACK``. La ruta queda vacía en
    fallback, respetando REAL_OR_NA y evitando afirmar una portada inexistente.
    """
    chosen = None
    source = 'FALLBACK'
    if override_path and is_supported_artwork_file(override_path):
        chosen = Path(os.fspath(override_path)).expanduser()
        source = 'CUSTOM'
    if chosen is None:
        chosen = discover_nvidia_app_artwork(exe_path)
        if chosen is not None:
            source = 'NVIDIA_APP'
    if chosen is None:
        chosen = discover_local_game_artwork(exe_path)
        if chosen is not None:
            source = 'LOCAL'
    if chosen is not None:
        try:
            with Image.open(chosen) as image:
                rendered = _rounded_rgba(image, (max(160, int(size[0])), max(90, int(size[1]))), radius=12)
            return rendered, source, str(chosen)
        except Exception:
            logger.debug('[GAME_UI] Arte local no pudo abrirse: %s', chosen, exc_info=True)
    return fallback_game_artwork(exe_path, size=size), 'FALLBACK', ''
