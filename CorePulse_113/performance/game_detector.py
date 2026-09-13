"""Detección conservadora de juegos: proceso principal + Steam + Epic + manual + RTSS.

V0.10.2.6w corrige una limitación importante de la detección anterior: una
instalación de juego puede ejecutar launchers, anticheat, crash handlers,
overlays y otros helpers desde la misma carpeta. CorePulse agrupa esos procesos
por instalación y selecciona un único proceso principal canónico.
"""
from __future__ import annotations

import ctypes
import json
import logging
import math
import os
from pathlib import Path
from core.runtime_paths import data_path
import re
import time
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple

import psutil

from performance.game_presentation import display_game_name, is_supported_artwork_file

logger = logging.getLogger('CorePulse.Game')
CONFIG_PATH = data_path('performance_games.json')

DEFAULT_EXCLUDED = {
    'steam.exe','steamwebhelper.exe','epicgameslauncher.exe','epicwebhelper.exe','unrealenginelauncher.exe',
    'discord.exe','explorer.exe','dwm.exe','searchhost.exe','startmenuexperiencehost.exe','shellexperiencehost.exe',
    'applicationframehost.exe','textinputhost.exe','taskmgr.exe','code.exe','python.exe','pythonw.exe','powershell.exe',
    'pwsh.exe','cmd.exe','conhost.exe','rtss.exe','rtsshooksloader64.exe','rtsshooksloader.exe','msedge.exe','chrome.exe',
}

# Procesos que acompañan a un juego pero no representan su workload principal.
# Sólo se usan para detección automática: un EXE agregado manualmente por el
# usuario conserva prioridad explícita aunque su nombre coincida con un patrón.
AUTO_DEPENDENCY_EXACT = {
    'unitycrashhandler32.exe', 'unitycrashhandler64.exe',
    'crashreportclient.exe', 'crashreporter.exe', 'crashpad_handler.exe',
    'easyanticheat.exe', 'easyanticheat_eos.exe', 'easyanticheat_launcher.exe',
    'eac_launcher.exe', 'eosbootstrapper.exe', 'start_protected_game.exe', 'start_protected_game64.exe',
    'startprotectedgame.exe', 'startprotectedgame64.exe', 'beservice.exe', 'beservice_x64.exe', 'belauncher.exe',
    'cefsubprocess.exe', 'webviewhost.exe', 'dxsetup.exe', 'ue4prereqsetup_x64.exe',
    'vc_redist.x64.exe', 'vc_redist.x86.exe', 'vcredist_x64.exe', 'vcredist_x86.exe',
    'unins000.exe', 'uninstall.exe',
}
AUTO_DEPENDENCY_TOKENS = (
    'crashhandler', 'crashreport', 'crashpad', 'anticheat', 'anti-cheat',
    'easyanticheat', 'battleye', 'beservice', 'belauncher', 'cefsubprocess',
    'webhelper', 'webview', 'overlayrenderer', 'overlay', 'telemetry',
    'updater', 'updatehelper', 'bootstrapper', 'redistributable', 'prereq',
    'installer', 'uninstaller', 'diagnostic', 'bugreport', 'reportclient',
    'helper', 'worker', 'subprocess', 'watchdog', 'launcher', 'service',
)
AUTO_DEPENDENCY_SUFFIXES = (
    'helper.exe', 'service.exe', 'launcher.exe', 'updater.exe', 'server.exe',
)


def _norm_path(value: str | os.PathLike | None) -> str:
    try:
        return os.path.normcase(os.path.abspath(os.fspath(value))).rstrip('\\/')
    except Exception:
        return ''


def _norm_exe(value: str | None) -> str:
    # Acepta rutas Windows incluso durante pruebas ejecutadas desde otro SO.
    raw = str(value or '').replace('\\', '/').strip()
    return Path(raw).name.lower().strip()


def _match_path(value: str | os.PathLike | None) -> str:
    """Representación estable para comparar rutas aun en tests no-Windows."""
    return str(value or '').replace('\\', '/').rstrip('/').casefold()


def _compact_name(value: str | None) -> str:
    stem = Path(_norm_exe(value)).stem.casefold()
    stem = re.sub(r'(?i)(?:[-_. ]?(?:win32|win64|x64|x86))?[-_. ]?shipping$', '', stem)
    return re.sub(r'[^a-z0-9]+', '', stem)


def _looks_like_dependency(
    exe_name: str | None,
    exe_path: str | os.PathLike | None = None,
    display_title: str | None = None,
) -> bool:
    """Clasifica auxiliares automáticos usando EXE, ruta y metadatos visibles.

    El nombre de archivo por sí solo no alcanza: Easy Anti-Cheat, por ejemplo,
    puede arrancar como ``start_protected_game.exe`` y revelar su identidad sólo
    en FileDescription/ProductName. Las altas manuales siguen siendo explícitas y
    no pasan por este filtro.
    """
    exe = _norm_exe(exe_name)
    if not exe:
        return True
    if exe in AUTO_DEPENDENCY_EXACT:
        return True
    low = exe.casefold()
    compact = re.sub(r'[^a-z0-9]+', '', low)
    if any(token.replace('-', '') in compact for token in AUTO_DEPENDENCY_TOKENS):
        return True
    if any(low.endswith(suffix) for suffix in AUTO_DEPENDENCY_SUFFIXES):
        return True
    if re.match(r'^(?:vc_?redist|vcredist|dotnet|directx|dxsetup|unins\d*|start_?protected_?game)', low):
        return True

    title = str(display_title or '').casefold().strip()
    title_compact = re.sub(r'[^a-z0-9]+', '', title)
    strong_title_tokens = (
        'easyanticheat', 'easy anti cheat', 'anti-cheat', 'anti cheat',
        'battleye', 'crashreport', 'crash report', 'crashpad',
        'bootstrapper', 'prerequisite', 'redistributable',
    )
    if title and any(token.replace(' ', '').replace('-', '') in title_compact for token in strong_title_tokens):
        return True

    path = _match_path(exe_path)
    if path:
        strong_path_tokens = (
            '/easyanticheat/', '/easy anti cheat/', '/battleye/', '/anticheat/',
            '/anti-cheat/', '/crashreport/', '/crashreporter/', '/crashpad/',
            '/redist/', '/redistributables/', '/prerequisites/', '/prereq/',
        )
        if any(token in path for token in strong_path_tokens):
            return True
    return False



class GameDetector:
    def __init__(self, config_path: Path = CONFIG_PATH, process_provider=None, rtss_hint_provider: Optional[Callable[[], Any]] = None):
        self.config_path = Path(config_path)
        self.process_provider = process_provider or self._iter_processes
        self.rtss_hint_provider = rtss_hint_provider
        self._last_library_scan = 0.0
        self._steam_roots: Set[str] = set()
        self._epic_roots: Set[str] = set()
        self._epic_launch_exes: Set[str] = set()
        self._dependency_identity_cache: Dict[Tuple[str, str], Tuple[bool, str]] = {}
        self._config = self._load_config()
        self._sanitize_learned_dependencies(persist=True)

    def _load_config(self) -> Dict[str, Any]:
        base = {
            'manual_exes': [], 'excluded_exes': sorted(DEFAULT_EXCLUDED), 'learned_exes': [],
            # Metadatos opcionales para que los juegos registrados puedan verse aun cerrados.
            # Las listas antiguas siguen siendo la autoridad de compatibilidad.
            'manual_paths': {}, 'learned_paths': {}, 'learned_sources': {},
            'manual_titles': {}, 'learned_titles': {}, 'artwork_overrides': {},
            # V0.10.2.6w: identidad canónica por instalación para no aprender helpers.
            'learned_game_ids': {}, 'canonical_by_game_id': {},
        }
        try:
            if self.config_path.is_file():
                raw = json.loads(self.config_path.read_text(encoding='utf-8'))
                if isinstance(raw, dict):
                    for key in ('manual_exes','excluded_exes','learned_exes'):
                        if isinstance(raw.get(key), list):
                            base[key] = sorted({_norm_exe(x) for x in raw[key] if _norm_exe(x)})
                    for key in ('manual_paths', 'learned_paths'):
                        if isinstance(raw.get(key), dict):
                            cleaned = {}
                            for exe_name, path_value in raw[key].items():
                                exe = _norm_exe(exe_name)
                                path = _norm_path(path_value)
                                if exe and path:
                                    cleaned[exe] = path
                            base[key] = cleaned
                    if isinstance(raw.get('learned_sources'), dict):
                        base['learned_sources'] = {
                            _norm_exe(exe_name): str(source or '').upper().strip()
                            for exe_name, source in raw['learned_sources'].items()
                            if _norm_exe(exe_name) and str(source or '').strip()
                        }
                    for key in ('manual_titles', 'learned_titles'):
                        if isinstance(raw.get(key), dict):
                            base[key] = {
                                _norm_exe(exe_name): str(title or '').strip()
                                for exe_name, title in raw[key].items()
                                if _norm_exe(exe_name) and str(title or '').strip()
                            }
                    if isinstance(raw.get('artwork_overrides'), dict):
                        base['artwork_overrides'] = {
                            _norm_exe(exe_name): str(path_value or '').strip()
                            for exe_name, path_value in raw['artwork_overrides'].items()
                            if _norm_exe(exe_name) and str(path_value or '').strip()
                        }
                    if isinstance(raw.get('learned_game_ids'), dict):
                        base['learned_game_ids'] = {
                            _norm_exe(exe_name): str(game_id or '').strip()
                            for exe_name, game_id in raw['learned_game_ids'].items()
                            if _norm_exe(exe_name) and str(game_id or '').strip()
                        }
                    if isinstance(raw.get('canonical_by_game_id'), dict):
                        base['canonical_by_game_id'] = {
                            str(game_id or '').strip(): _norm_exe(exe_name)
                            for game_id, exe_name in raw['canonical_by_game_id'].items()
                            if str(game_id or '').strip() and _norm_exe(exe_name)
                        }
        except Exception:
            logger.exception('[GAME] No se pudo leer configuración de detección')
        base['excluded_exes'] = sorted(set(base['excluded_exes']) | DEFAULT_EXCLUDED)
        return base

    def _sanitize_learned_dependencies(self, persist=False) -> bool:
        """Elimina dependencias aprendidas por builds antiguas, nunca altas manuales."""
        manual = set(self._config.get('manual_exes') or [])
        learned = set(self._config.get('learned_exes') or [])
        paths = dict(self._config.get('learned_paths') or {})
        titles = dict(self._config.get('learned_titles') or {})
        remove = {
            exe for exe in learned
            if exe not in manual and _looks_like_dependency(exe, paths.get(exe), titles.get(exe))
        }
        changed = bool(remove)
        if remove:
            self._config['learned_exes'] = sorted(learned - remove)
            for key in ('learned_paths', 'learned_sources', 'learned_titles', 'learned_game_ids', 'artwork_overrides'):
                mapping = dict(self._config.get(key) or {})
                for exe in remove:
                    mapping.pop(exe, None)
                self._config[key] = mapping

        canonical = dict(self._config.get('canonical_by_game_id') or {})
        for game_id, exe_name in list(canonical.items()):
            exe = _norm_exe(exe_name)
            path = str(paths.get(exe) or '')
            title = str(titles.get(exe) or '')
            if exe in remove or (exe and exe not in manual and _looks_like_dependency(exe, path, title)):
                canonical.pop(game_id, None)
                changed = True
        self._config['canonical_by_game_id'] = canonical
        if changed:
            logger.info('[GAME] Limpieza automática de dependencias aprendidas: %s', sorted(remove))
            if persist:
                self._save_config()
        return changed

    def _save_config(self) -> None:
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.config_path.with_suffix('.tmp')
            tmp.write_text(json.dumps(self._config, ensure_ascii=False, indent=2), encoding='utf-8')
            os.replace(tmp, self.config_path)
        except Exception:
            logger.exception('[GAME] No se pudo guardar configuración de detección')

    @staticmethod
    def _path_if_supplied(value: str | os.PathLike | None) -> str:
        raw = os.fspath(value) if value is not None else ''
        raw = str(raw or '').strip()
        if not raw:
            return ''
        # No convertir un simple 'juego.exe' en una ruta falsa relativa al cwd.
        if not (os.path.isabs(raw) or '/' in raw or '\\' in raw):
            return ''
        return _norm_path(raw)

    def add_manual_game(self, exe_name: str) -> bool:
        exe = _norm_exe(exe_name)
        if not exe or exe in DEFAULT_EXCLUDED:
            return False
        values = set(self._config.get('manual_exes') or [])
        values.add(exe)
        self._config['manual_exes'] = sorted(values)
        supplied_path = self._path_if_supplied(exe_name)
        if supplied_path:
            paths = dict(self._config.get('manual_paths') or {})
            paths[exe] = supplied_path
            self._config['manual_paths'] = paths
        titles = dict(self._config.get('manual_titles') or {})
        titles[exe] = display_game_name(exe, supplied_path, exe_name)
        self._config['manual_titles'] = titles
        # Una exclusión explícita previa no debe bloquear un alta manual posterior del usuario.
        excluded = set(self._config.get('excluded_exes') or [])
        if exe in excluded and exe not in DEFAULT_EXCLUDED:
            excluded.discard(exe)
            self._config['excluded_exes'] = sorted(excluded | DEFAULT_EXCLUDED)
        self._save_config()
        return True

    def remove_manual_game(self, exe_name: str) -> bool:
        exe = _norm_exe(exe_name)
        if not exe:
            return False
        values = set(self._config.get('manual_exes') or [])
        if exe not in values:
            return False
        values.discard(exe)
        self._config['manual_exes'] = sorted(values)
        paths = dict(self._config.get('manual_paths') or {})
        paths.pop(exe, None)
        self._config['manual_paths'] = paths
        titles = dict(self._config.get('manual_titles') or {})
        titles.pop(exe, None)
        self._config['manual_titles'] = titles
        if exe not in set(self._config.get('learned_exes') or []):
            artwork = dict(self._config.get('artwork_overrides') or {})
            artwork.pop(exe, None)
            self._config['artwork_overrides'] = artwork
        self._save_config()
        return True

    def exclude(self, exe_name: str) -> bool:
        exe = _norm_exe(exe_name)
        if not exe:
            return False
        values = set(self._config.get('excluded_exes') or [])
        values.add(exe)
        self._config['excluded_exes'] = sorted(values)
        self._save_config()
        return True

    def set_game_artwork(self, exe_name: str, image_path: str | os.PathLike | None) -> bool:
        """Guarda una portada elegida por el usuario sin alterar la identidad del juego."""
        exe = _norm_exe(exe_name)
        if not exe or exe not in (set(self._config.get('manual_exes') or []) | set(self._config.get('learned_exes') or [])):
            return False
        if not is_supported_artwork_file(image_path):
            return False
        overrides = dict(self._config.get('artwork_overrides') or {})
        overrides[exe] = str(Path(os.fspath(image_path)).expanduser())
        self._config['artwork_overrides'] = overrides
        self._save_config()
        return True

    def clear_game_artwork(self, exe_name: str) -> bool:
        exe = _norm_exe(exe_name)
        overrides = dict(self._config.get('artwork_overrides') or {})
        if not exe or exe not in overrides:
            return False
        overrides.pop(exe, None)
        self._config['artwork_overrides'] = overrides
        self._save_config()
        return True

    def _infer_game_id_from_path(self, exe_path: str | os.PathLike | None, source: str | None = None) -> Tuple[str, str]:
        """Devuelve (game_id, install_root) con evidencia de biblioteca real."""
        path = _norm_path(exe_path)
        match = _match_path(path)
        if not path or not match:
            return '', ''

        # Steam conocido por roots descubiertos.
        for root in sorted(self._steam_roots, key=len, reverse=True):
            root_match = _match_path(root)
            if match == root_match or match.startswith(root_match + '/'):
                rest = match[len(root_match):].lstrip('/')
                folder = rest.split('/', 1)[0] if rest else ''
                if folder:
                    native_root = _norm_path(os.path.join(root, folder))
                    return f'STEAM|{_match_path(native_root)}', native_root

        # Compatibilidad/migración: reconocer la estructura Steam aun antes del scan.
        marker = '/steamapps/common/'
        if marker in match:
            prefix, rest = match.split(marker, 1)
            folder = rest.split('/', 1)[0]
            if folder:
                inferred = f'{prefix}{marker}{folder}'
                return f'STEAM|{inferred}', inferred

        # En Epic, cada root descubierto corresponde a una instalación concreta.
        for root in sorted(self._epic_roots, key=len, reverse=True):
            root_match = _match_path(root)
            if match == root_match or match.startswith(root_match + '/'):
                return f'EPIC|{root_match}', root

        return '', ''

    def _learn(self, exe_name: str, exe_path: str | os.PathLike | None = None, source: str | None = None, game_id: str | None = None) -> None:
        exe = _norm_exe(exe_name)
        if not exe or exe in set(self._config.get('excluded_exes') or []):
            return
        learned_path = self._path_if_supplied(exe_path)
        candidate_title = display_game_name(exe, learned_path, exe_name)
        if _looks_like_dependency(exe, learned_path, candidate_title):
            logger.debug('[GAME] dependencia automática descartada antes de aprender: %s · %s', exe, candidate_title)
            self._sanitize_learned_dependencies(persist=True)
            return
        changed = False
        values = set(self._config.get('learned_exes') or [])
        if exe not in values:
            values.add(exe)
            self._config['learned_exes'] = sorted(values)
            changed = True
        if learned_path:
            paths = dict(self._config.get('learned_paths') or {})
            if paths.get(exe) != learned_path:
                paths[exe] = learned_path
                self._config['learned_paths'] = paths
                changed = True
        source_value = str(source or '').upper().strip()
        if source_value:
            sources = dict(self._config.get('learned_sources') or {})
            if sources.get(exe) != source_value:
                sources[exe] = source_value
                self._config['learned_sources'] = sources
                changed = True
        resolved_game_id = str(game_id or '').strip()
        if not resolved_game_id and learned_path:
            resolved_game_id, _ = self._infer_game_id_from_path(learned_path, source_value)
        if resolved_game_id:
            game_ids = dict(self._config.get('learned_game_ids') or {})
            if game_ids.get(exe) != resolved_game_id:
                game_ids[exe] = resolved_game_id
                self._config['learned_game_ids'] = game_ids
                changed = True
            canonical = dict(self._config.get('canonical_by_game_id') or {})
            if canonical.get(resolved_game_id) != exe:
                canonical[resolved_game_id] = exe
                self._config['canonical_by_game_id'] = canonical
                changed = True
        title = candidate_title
        if title and title != 'N/A':
            titles = dict(self._config.get('learned_titles') or {})
            if titles.get(exe) != title:
                titles[exe] = title
                self._config['learned_titles'] = titles
                changed = True

        # Si versiones anteriores aprendieron helpers del mismo juego, una detección
        # canónica real los retira del catálogo aprendido. Nunca se toca un alta manual.
        if resolved_game_id:
            changed = self._prune_learned_group(resolved_game_id, keep_exe=exe) or changed
        if changed:
            self._save_config()

    def _saved_game_id(self, exe: str) -> str:
        exe = _norm_exe(exe)
        if not exe:
            return ''
        explicit = str((self._config.get('learned_game_ids') or {}).get(exe) or '').strip()
        if explicit:
            return explicit
        path = str((self._config.get('learned_paths') or {}).get(exe) or '')
        source = str((self._config.get('learned_sources') or {}).get(exe) or '')
        inferred, _ = self._infer_game_id_from_path(path, source)
        return inferred

    def _prune_learned_group(self, game_id: str, keep_exe: str) -> bool:
        game_id = str(game_id or '').strip()
        keep = _norm_exe(keep_exe)
        if not game_id or not keep:
            return False
        manual = set(self._config.get('manual_exes') or [])
        learned = set(self._config.get('learned_exes') or [])
        remove = {
            exe for exe in learned
            if exe != keep and exe not in manual and self._saved_game_id(exe) == game_id
        }
        if not remove:
            return False
        self._config['learned_exes'] = sorted(learned - remove)
        for key in ('learned_paths', 'learned_sources', 'learned_titles', 'learned_game_ids'):
            mapping = dict(self._config.get(key) or {})
            for exe in remove:
                mapping.pop(exe, None)
            self._config[key] = mapping
        logger.info('[GAME] Catálogo canónico %s: descartados helpers aprendidos %s', keep, sorted(remove))
        return True

    def _static_catalog_score(self, exe: str, path: str, source: str, game_id: str) -> float:
        score = 0.0
        if _looks_like_dependency(exe):
            score -= 2000.0
        low = exe.casefold()
        if 'shipping' in low:
            score += 180.0
        if exe in self._epic_launch_exes:
            score += 700.0
        canonical = str((self._config.get('canonical_by_game_id') or {}).get(game_id) or '')
        if canonical == exe:
            score += 900.0
        install_name = ''
        if '|' in game_id:
            install_name = game_id.rsplit('/', 1)[-1]
        if install_name and _compact_name(exe) == re.sub(r'[^a-z0-9]+', '', install_name.casefold()):
            score += 160.0
        return score

    def _canonical_learned_exes(self, learned: Set[str]) -> Set[str]:
        """Colapsa catálogos antiguos contaminados a una entrada por instalación."""
        grouped: Dict[str, List[str]] = {}
        for exe in learned:
            game_id = self._saved_game_id(exe) or f'LEARNED|{exe}'
            grouped.setdefault(game_id, []).append(exe)
        selected: Set[str] = set()
        paths = dict(self._config.get('learned_paths') or {})
        sources = dict(self._config.get('learned_sources') or {})
        titles = dict(self._config.get('learned_titles') or {})
        excluded = set(self._config.get('excluded_exes') or []) | DEFAULT_EXCLUDED
        canonical = dict(self._config.get('canonical_by_game_id') or {})
        for game_id, members in grouped.items():
            preferred = _norm_exe(canonical.get(game_id))
            if preferred and preferred in excluded:
                continue
            viable = [exe for exe in members if exe not in excluded and not _looks_like_dependency(exe, paths.get(exe), titles.get(exe))]
            if preferred in viable:
                selected.add(preferred)
                continue
            if not viable:
                # No convertir un helper antiguo aislado en juego visible.
                continue
            winner = max(
                viable,
                key=lambda exe: (
                    self._static_catalog_score(exe, str(paths.get(exe) or ''), str(sources.get(exe) or ''), game_id),
                    exe,
                ),
            )
            selected.add(winner)
        return selected

    def registered_games(self, active_games: Optional[Iterable[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        """Devuelve un catálogo visible con una sola identidad automática por juego."""
        self._sanitize_learned_dependencies(persist=True)
        try:
            self.refresh_libraries()
        except Exception:
            logger.debug('[GAME] Catálogo sin refresh de bibliotecas', exc_info=True)
        manual = set(self._config.get('manual_exes') or [])
        learned = set(self._config.get('learned_exes') or []) - manual
        learned = self._canonical_learned_exes(learned)
        excluded = set(self._config.get('excluded_exes') or []) | DEFAULT_EXCLUDED
        manual_paths = dict(self._config.get('manual_paths') or {})
        learned_paths = dict(self._config.get('learned_paths') or {})
        learned_sources = dict(self._config.get('learned_sources') or {})
        manual_titles = dict(self._config.get('manual_titles') or {})
        learned_titles = dict(self._config.get('learned_titles') or {})
        artwork_overrides = dict(self._config.get('artwork_overrides') or {})

        active_by_name: Dict[str, Dict[str, Any]] = {}
        for game in active_games or []:
            exe = _norm_exe(game.get('name') or game.get('exe'))
            if exe and exe not in active_by_name:
                active_by_name[exe] = dict(game)

        rows: List[Dict[str, Any]] = []
        for exe in sorted(manual | learned):
            active = active_by_name.get(exe) or {}
            is_manual = exe in manual
            source = 'MANUAL' if is_manual else str(learned_sources.get(exe) or 'LEARNED').upper()
            stored_path = manual_paths.get(exe) if is_manual else learned_paths.get(exe)
            stored_title = manual_titles.get(exe) if is_manual else learned_titles.get(exe)
            path = str(active.get('exe') or stored_path or '')
            rows.append({
                # ``name`` sigue siendo la identidad técnica usada por detección/rollback.
                'name': exe,
                'display_name': display_game_name(exe, path, stored_title),
                'exe': path,
                'source': source,
                'manual': is_manual,
                'active': bool(active),
                'pid': int(active.get('pid') or 0) if active else None,
                'excluded': exe in excluded,
                'artwork_override': str(artwork_overrides.get(exe) or ''),
            })
        return rows

    @staticmethod
    def _iter_processes():
        attrs = ['pid', 'ppid', 'name', 'exe', 'memory_info', 'create_time']
        for p in psutil.process_iter(attrs):
            try:
                memory = p.info.get('memory_info')
                yield {
                    'pid': int(p.info.get('pid') or p.pid),
                    'ppid': int(p.info.get('ppid') or 0),
                    'name': p.info.get('name'),
                    'exe': p.info.get('exe'),
                    'rss': int(getattr(memory, 'rss', 0) or 0),
                    'create_time': float(p.info.get('create_time') or 0.0),
                }
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

    def _steam_install_roots(self) -> Set[str]:
        roots = set()
        candidates = []
        for env in ('PROGRAMFILES(X86)','PROGRAMFILES'):
            base = os.environ.get(env)
            if base:
                candidates.append(Path(base) / 'Steam')
        try:
            import winreg
            for hive, subkey, value_name in (
                (winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam', 'SteamPath'),
                (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\WOW6432Node\Valve\Steam', 'InstallPath'),
            ):
                try:
                    with winreg.OpenKey(hive, subkey) as key:
                        candidates.append(Path(winreg.QueryValueEx(key, value_name)[0]))
                except OSError:
                    logger.debug('[GAME] Registro Steam no disponible: %s', subkey, exc_info=True)
        except Exception:
            logger.debug('[GAME] winreg no disponible para descubrir Steam', exc_info=True)
        for steam in candidates:
            if not steam:
                continue
            roots.add(_norm_path(steam / 'steamapps' / 'common'))
            vdf = steam / 'steamapps' / 'libraryfolders.vdf'
            try:
                text = vdf.read_text(encoding='utf-8', errors='ignore')
                for raw in re.findall(r'"path"\s+"([^"]+)"', text, flags=re.I):
                    path = raw.replace('\\\\','\\')
                    roots.add(_norm_path(Path(path) / 'steamapps' / 'common'))
            except OSError:
                logger.debug('[GAME] libraryfolders.vdf no disponible: %s', vdf, exc_info=True)
        return {x for x in roots if x}

    def _epic_install_roots(self) -> tuple[Set[str], Set[str]]:
        roots, exes = set(), set()
        program_data = Path(os.environ.get('PROGRAMDATA', r'C:\ProgramData'))
        manifest_dir = program_data / 'Epic' / 'EpicGamesLauncher' / 'Data' / 'Manifests'
        try:
            for file in manifest_dir.glob('*.item'):
                try:
                    data = json.loads(file.read_text(encoding='utf-8', errors='ignore'))
                except Exception:
                    continue
                root = _norm_path(data.get('InstallLocation'))
                if root:
                    roots.add(root)
                launch = _norm_exe(data.get('LaunchExecutable'))
                if launch:
                    exes.add(launch)
        except OSError:
            logger.debug('[GAME] Manifiestos Epic no disponibles: %s', manifest_dir, exc_info=True)
        return roots, exes

    def refresh_libraries(self, force=False) -> None:
        now = time.monotonic()
        if (not force) and now - self._last_library_scan < 60.0:
            return
        self._last_library_scan = now
        self._steam_roots = self._steam_install_roots()
        self._epic_roots, self._epic_launch_exes = self._epic_install_roots()

    @staticmethod
    def _under(path: str, roots: Iterable[str]) -> bool:
        if not path:
            return False
        target = _match_path(path)
        for root in roots:
            base = _match_path(root)
            if base and (target == base or target.startswith(base + '/')):
                return True
        return False

    @staticmethod
    def _visible_window_pids() -> Set[int]:
        """Obtiene PIDs con ventana top-level visible; falla cerrado fuera de Windows."""
        if os.name != 'nt':
            return set()
        pids: Set[int] = set()
        try:
            user32 = ctypes.windll.user32
            callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

            @callback_type
            def enum_proc(hwnd, _lparam):
                try:
                    if not user32.IsWindowVisible(hwnd):
                        return True
                    if int(user32.GetWindowTextLengthW(hwnd) or 0) <= 0:
                        return True
                    pid = ctypes.c_ulong(0)
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    if pid.value:
                        pids.add(int(pid.value))
                except Exception:
                    pass
                return True

            user32.EnumWindows(enum_proc, 0)
        except Exception:
            logger.debug('[GAME] No se pudo consultar ventanas visibles', exc_info=True)
        return pids

    def _runtime_dependency_identity(self, exe_name: str, exe_path: str, raw_name: str = '') -> Tuple[bool, str]:
        """Clasifica un proceso automático incluyendo ProductName/FileDescription con cache."""
        key = (_norm_exe(exe_name), _match_path(exe_path))
        cached = self._dependency_identity_cache.get(key)
        if cached is not None:
            return cached
        title = display_game_name(exe_name, exe_path, raw_name or exe_name)
        result = (_looks_like_dependency(exe_name, exe_path, title), title)
        if len(self._dependency_identity_cache) >= 512:
            self._dependency_identity_cache.clear()
        self._dependency_identity_cache[key] = result
        return result

    def _process_score(self, candidate: Dict[str, Any], visible_pids: Set[int]) -> float:
        """Puntúa evidencia de proceso principal sin inventar identidad."""
        score = 0.0
        source = str(candidate.get('source') or '').upper()
        name = _norm_exe(candidate.get('name'))
        pid = int(candidate.get('pid') or 0)
        game_id = str(candidate.get('game_id') or '')
        if source == 'MANUAL':
            score += 5000.0
        if candidate.get('rtss_match'):
            score += 2600.0
        if source == 'EPIC' and name in self._epic_launch_exes:
            score += 1900.0
        if pid in visible_pids:
            score += 1500.0
        canonical = _norm_exe((self._config.get('canonical_by_game_id') or {}).get(game_id))
        if canonical and canonical == name:
            score += 1100.0
        if _looks_like_dependency(name, candidate.get('exe'), candidate.get('display_title')) and source != 'MANUAL':
            score -= 5000.0
        if 'shipping' in name.casefold():
            score += 220.0

        # El proceso principal suele concentrar mucha más memoria que helpers.
        rss = max(0, int(candidate.get('rss') or 0))
        if rss:
            score += min(260.0, max(0.0, math.log2(max(1, rss / (16 * 1024 * 1024)))) * 40.0)

        install_root = str(candidate.get('install_root') or '')
        if install_root:
            install_name = Path(install_root.replace('\\', '/')).name
            if _compact_name(name) and _compact_name(name) == re.sub(r'[^a-z0-9]+', '', install_name.casefold()):
                score += 240.0
        return score

    def _has_main_process_evidence(self, candidate: Dict[str, Any], visible_pids: Set[int]) -> bool:
        """Exige evidencia positiva antes de convertir un EXE de biblioteca en juego.

        Estar dentro de la carpeta del juego ya no basta. Esto evita activar AUTO
        mientras sólo quedó vivo un worker/SDK auxiliar de nombre desconocido.
        """
        source = str(candidate.get('source') or '').upper()
        name = _norm_exe(candidate.get('name'))
        pid = int(candidate.get('pid') or 0)
        game_id = str(candidate.get('game_id') or '')
        if source == 'MANUAL' or candidate.get('rtss_match'):
            return True
        if source == 'EPIC' and name in self._epic_launch_exes:
            return True
        canonical = _norm_exe((self._config.get('canonical_by_game_id') or {}).get(game_id))
        if canonical and canonical == name:
            return True
        if pid in visible_pids:
            return True
        low = name.casefold()
        if 'shipping' in low:
            return True
        install_root = str(candidate.get('install_root') or '')
        if install_root:
            install_name = Path(install_root.replace('\\', '/')).name
            if _compact_name(name) and _compact_name(name) == re.sub(r'[^a-z0-9]+', '', install_name.casefold()):
                return True
        return False

    def _select_primary_candidate(self, group: List[Dict[str, Any]], visible_pids: Set[int], excluded: Set[str]) -> Optional[Dict[str, Any]]:
        if not group:
            return None
        game_id = str(group[0].get('game_id') or '')
        canonical = _norm_exe((self._config.get('canonical_by_game_id') or {}).get(game_id))
        # Si el usuario excluyó explícitamente el canónico, no sustituirlo por un helper.
        if canonical and canonical in excluded:
            return None

        viable = []
        for candidate in group:
            name = _norm_exe(candidate.get('name'))
            explicit = candidate.get('source') == 'MANUAL'
            if name in excluded:
                continue
            if _looks_like_dependency(name, candidate.get('exe'), candidate.get('display_title')) and not explicit:
                continue
            if not self._has_main_process_evidence(candidate, visible_pids):
                continue
            viable.append(candidate)
        if not viable:
            return None
        return max(
            viable,
            key=lambda item: (self._process_score(item, visible_pids), int(item.get('rss') or 0), -int(item.get('pid') or 0)),
        )

    def detect_active_games(self) -> List[Dict[str, Any]]:
        self.refresh_libraries()
        logger.debug('[GAME] Buscando procesos principales de juegos activos')
        excluded = set(self._config.get('excluded_exes') or []) | DEFAULT_EXCLUDED
        manual = set(self._config.get('manual_exes') or [])
        learned = set(self._config.get('learned_exes') or [])
        learned_game_ids = dict(self._config.get('learned_game_ids') or {})
        visible_pids = self._visible_window_pids()

        rtss_pid = None
        rtss_name = None
        if callable(self.rtss_hint_provider):
            try:
                hint = self.rtss_hint_provider() or {}
                if isinstance(hint, dict):
                    rtss_pid = int(hint.get('pid') or 0) or None
                    rtss_name = _norm_exe(hint.get('name'))
            except Exception:
                logger.debug('[GAME] RTSS hint no disponible', exc_info=True)

        groups: Dict[str, List[Dict[str, Any]]] = {}
        for proc in self.process_provider():
            try:
                pid = int(proc.get('pid') or 0)
                name = _norm_exe(proc.get('name') or proc.get('exe'))
                exe_path = _norm_path(proc.get('exe'))
            except Exception:
                continue
            if not pid or not name or name in excluded:
                continue

            rtss_match = bool(rtss_pid == pid or (rtss_name and name == rtss_name))
            source = None
            game_id = ''
            install_root = ''

            # Alta manual siempre manda y conserva identidad exacta.
            if name in manual:
                source = 'MANUAL'
                game_id = f'MANUAL|{name}'
            else:
                inferred_id, inferred_root = self._infer_game_id_from_path(exe_path)
                if inferred_id.startswith('STEAM|'):
                    source, game_id, install_root = 'STEAM', inferred_id, inferred_root
                elif inferred_id.startswith('EPIC|'):
                    source, game_id, install_root = 'EPIC', inferred_id, inferred_root
                elif name in self._epic_launch_exes:
                    source = 'EPIC'
                    game_id = inferred_id or f'EPIC_EXE|{name}'
                    install_root = inferred_root
                elif rtss_match:
                    source = 'RTSS'
                    # RTSS identifica el proceso renderizado; si no hay biblioteca, la
                    # identidad queda ligada al EXE para no agrupar juegos distintos.
                    game_id = str(learned_game_ids.get(name) or f'RTSS|{_match_path(exe_path) or name}')
                elif name in learned:
                    source = 'LEARNED'
                    game_id = str(learned_game_ids.get(name) or inferred_id or f'LEARNED|{name}')
                    install_root = inferred_root

            if not source or not game_id:
                continue
            display_title = ''
            if source != 'MANUAL':
                is_dependency, display_title = self._runtime_dependency_identity(name, exe_path, str(proc.get('name') or name))
                if is_dependency:
                    logger.debug('[GAME] dependencia automática omitida por identidad runtime: %s · %s', name, display_title)
                    continue
            candidate = {
                'pid': pid,
                'name': name,
                'raw_name': str(proc.get('name') or name),
                'exe': proc.get('exe') or '',
                'source': source,
                'game_id': game_id,
                'install_root': install_root,
                'rtss_match': rtss_match,
                'ppid': int(proc.get('ppid') or 0),
                'rss': int(proc.get('rss') or 0),
                'create_time': float(proc.get('create_time') or 0.0),
                'display_title': display_title,
            }
            groups.setdefault(game_id, []).append(candidate)

        selected: List[Dict[str, Any]] = []
        for game_id, group in groups.items():
            winner = self._select_primary_candidate(group, visible_pids, excluded)
            if winner is None:
                if group:
                    logger.debug('[GAME] grupo %s omitido: sólo helpers/dependencias', game_id)
                continue
            public = {
                'pid': int(winner['pid']),
                'name': _norm_exe(winner['name']),
                'exe': winner.get('exe') or '',
                'source': winner.get('source') or 'LEARNED',
            }
            selected.append(public)
            if public['source'] in {'STEAM', 'EPIC', 'RTSS', 'LEARNED'}:
                # LEARNED también actualiza identidad para migrar catálogos antiguos.
                self._learn(winner.get('raw_name') or public['name'], public['exe'], public['source'], game_id=game_id)
            dropped = [x['name'] for x in group if int(x.get('pid') or 0) != public['pid']]
            if dropped:
                logger.debug('[GAME] %s elegido como principal; auxiliares ignorados=%s', public['name'], dropped)

        games = sorted(selected, key=lambda x: (x['name'], x['pid']))
        for game in games:
            logger.debug('[GAME] principal activo %s (%s, pid=%s)', game['name'], game['source'], game['pid'])
        return games
