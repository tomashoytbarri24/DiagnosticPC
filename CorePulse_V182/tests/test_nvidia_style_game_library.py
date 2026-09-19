"""Regresión V100 — tarjetas 16:9 con artwork real/local y fallback seguro."""
from __future__ import annotations

from pathlib import Path
import json
import sys
import tempfile

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION
from performance.game_detector import GameDetector
from performance.game_presentation import (
    discover_local_game_artwork,
    fallback_game_artwork,
    is_supported_artwork_file,
    load_game_artwork,
)


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    return True


def main():
    checks = []
    checks.append(check('version', VERSION.isdecimal()))

    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        steam = base / 'Steam'
        steamapps = steam / 'steamapps'
        game_root = steamapps / 'common' / 'ExampleGame'
        exe = game_root / 'bin' / 'ExampleGame.exe'
        exe.parent.mkdir(parents=True)
        exe.write_bytes(b'MZ')
        manifest = steamapps / 'appmanifest_12345.acf'
        manifest.write_text('"AppState"\n{\n"appid" "12345"\n"installdir" "ExampleGame"\n}\n', encoding='utf-8')
        cache = steam / 'appcache' / 'librarycache'
        cache.mkdir(parents=True)
        header = cache / '12345_header.jpg'
        Image.new('RGB', (920, 430), (30, 80, 120)).save(header)

        found = discover_local_game_artwork(exe)
        checks.append(check('steam_art_by_real_appid', found == header))
        rendered, source, resolved = load_game_artwork(exe, size=(304, 171))
        checks.append(check('steam_art_source_local', source == 'LOCAL'))
        checks.append(check('steam_art_path_real', Path(resolved) == header))
        checks.append(check('steam_art_16_9_card', rendered.size == (304, 171) and rendered.mode == 'RGBA'))

        custom = base / 'custom_cover.png'
        Image.new('RGB', (1600, 900), (90, 30, 40)).save(custom)
        checks.append(check('custom_art_valid', is_supported_artwork_file(custom)))
        custom_img, custom_source, custom_resolved = load_game_artwork(exe, size=(304, 171), override_path=custom)
        checks.append(check('custom_has_priority', custom_source == 'CUSTOM' and Path(custom_resolved) == custom))
        checks.append(check('custom_render_size', custom_img.size == (304, 171)))

        cfg = base / 'performance_games.json'
        detector = GameDetector(config_path=cfg, process_provider=lambda: [])
        checks.append(check('add_game', detector.add_manual_game(str(exe))))
        checks.append(check('set_custom_art', detector.set_game_artwork(exe.name, custom)))
        row = detector.registered_games([])[0]
        checks.append(check('override_exposed_only_as_presentation', Path(row['artwork_override']) == custom))
        checks.append(check('technical_identity_unchanged', row['name'] == 'examplegame.exe'))

        detector2 = GameDetector(config_path=cfg, process_provider=lambda: [])
        row2 = detector2.registered_games([])[0]
        checks.append(check('override_persistent', Path(row2['artwork_override']) == custom))
        raw = json.loads(cfg.read_text(encoding='utf-8'))
        checks.append(check('config_backward_maps_preserved', 'manual_exes' in raw and 'artwork_overrides' in raw))
        checks.append(check('clear_custom_art', detector2.clear_game_artwork(exe.name)))
        checks.append(check('override_removed', not detector2.registered_games([])[0]['artwork_override']))

    fallback = fallback_game_artwork('', size=(304, 171))
    checks.append(check('fallback_safe', fallback.mode == 'RGBA' and fallback.size == (304, 171)))

    ui = (ROOT / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')
    block = ui.split('    def _render_registered_games', 1)[1].split('    def _remove_manual_game', 1)[0]
    checks.append(check('ui_uses_artwork_loader', 'load_game_artwork(' in ui and '_start_game_artwork_jobs' in ui and 'artwork_jobs' in block))
    checks.append(check('ui_responsive_panorama_size', '_game_library_geometry()' in block and "'size': art_size" in block and 'art_size[1] + 80' in block))
    checks.append(check('ui_custom_cover_action', "'Cambiar imagen'" in ui and '_choose_game_artwork' in ui and '_show_game_actions' in ui))
    checks.append(check('ui_keeps_clean_name', "game.get('display_name')" in block))
    for forbidden in ('EN EJECUCIÓN · PID', 'LISTO PARA DETECTAR', 'Ruta N/A', '_game_source_label('):
        checks.append(check(f'ui_hides_{forbidden}', forbidden not in block))

    print(f'PASS nvidia_style_game_library ({len(checks)} checks)')


if __name__ == '__main__':
    main()
