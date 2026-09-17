"""Regresión: juegos agregados/detectados deben permanecer visibles en CorePulse."""
from __future__ import annotations
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from performance.game_detector import GameDetector, _norm_path
from performance.game_presentation import display_game_name, extract_executable_icon


def check(name, condition):
    ok = bool(condition)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {ok}")
    return ok


def main():
    results = []
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        config = base / 'games.json'
        game_path = base / 'Games' / 'VisibleTitle.exe'
        game_path.parent.mkdir(parents=True)

        detector = GameDetector(config_path=config, process_provider=lambda: iter(()))
        results.append(check('manual_add_ok', detector.add_manual_game(str(game_path))))
        rows = detector.registered_games([])
        results.append(check('manual_visible_while_closed', len(rows) == 1 and rows[0]['name'] == 'visibletitle.exe' and not rows[0]['active']))
        results.append(check('manual_path_persisted', rows[0]['exe'] == _norm_path(game_path)))
        results.append(check('manual_source_visible', rows[0]['source'] == 'MANUAL'))
        results.append(check('manual_display_name_has_no_exe', rows[0]['display_name'] == 'Visible Title' and '.exe' not in rows[0]['display_name'].lower()))

        reloaded = GameDetector(config_path=config, process_provider=lambda: iter(()))
        rows = reloaded.registered_games([])
        results.append(check('catalog_survives_restart', len(rows) == 1 and rows[0]['name'] == 'visibletitle.exe'))

        active = [{'pid': 4242, 'name': 'VisibleTitle.exe', 'exe': str(game_path), 'source': 'MANUAL'}]
        rows = reloaded.registered_games(active)
        results.append(check('active_state_uses_real_pid', rows[0]['active'] and rows[0]['pid'] == 4242))

        results.append(check('manual_remove_ok', reloaded.remove_manual_game('VisibleTitle.exe')))
        results.append(check('manual_removed_from_catalog', reloaded.registered_games([]) == []))

        # Compatibilidad con configuración antigua: sin nuevos campos de metadatos.
        legacy = base / 'legacy.json'
        legacy.write_text(json.dumps({'manual_exes': ['LegacyGame.exe'], 'learned_exes': [], 'excluded_exes': []}), encoding='utf-8')
        legacy_detector = GameDetector(config_path=legacy, process_provider=lambda: iter(()))
        legacy_rows = legacy_detector.registered_games([])
        results.append(check('legacy_config_supported', len(legacy_rows) == 1 and legacy_rows[0]['name'] == 'legacygame.exe'))
        results.append(check('legacy_display_name_clean', legacy_rows[0]['display_name'] == 'Legacygame' and '.exe' not in legacy_rows[0]['display_name'].lower()))

        # Un juego realmente detectado por Steam queda aprendido y visible.
        steam_root = base / 'Steam' / 'steamapps' / 'common'
        detected_path = steam_root / 'ScannedTitle' / 'ScannedTitle.exe'
        detected_path.parent.mkdir(parents=True)
        processes = [{'pid': 73, 'name': 'ScannedTitle.exe', 'exe': str(detected_path)}]
        scan_detector = GameDetector(config_path=base/'scan.json', process_provider=lambda: iter(processes))
        scan_detector.refresh_libraries = lambda force=False: None
        scan_detector._steam_roots = {_norm_path(steam_root)}
        scan_detector._epic_roots = set(); scan_detector._epic_launch_exes = set()
        detected = scan_detector.detect_active_games()
        scan_rows = scan_detector.registered_games(detected)
        results.append(check('scanned_game_detected', len(detected) == 1 and detected[0]['source'] == 'STEAM'))
        results.append(check('scanned_game_added_to_visible_catalog', len(scan_rows) == 1 and scan_rows[0]['name'] == 'scannedtitle.exe'))
        results.append(check('scanned_source_persisted', scan_rows[0]['source'] == 'STEAM'))
        results.append(check('scanned_path_persisted', scan_rows[0]['exe'] == _norm_path(detected_path)))
        results.append(check('scanned_display_name_clean', scan_rows[0]['display_name'] == 'Scanned Title'))

        # Al cerrar el juego sigue apareciendo, pero deja de fingir actividad/PID.
        scan_rows_closed = GameDetector(config_path=base/'scan.json', process_provider=lambda: iter(())).registered_games([])
        results.append(check('scanned_game_visible_after_close', len(scan_rows_closed) == 1 and not scan_rows_closed[0]['active'] and scan_rows_closed[0]['pid'] is None))

        ui_text = (ROOT/'gui'/'health_center_panel.py').read_text(encoding='utf-8')
        render_block = ui_text[ui_text.index('    def _render_registered_games'):ui_text.index('    def _remove_manual_game')]
        results.append(check('ui_has_my_games_section', "text='Biblioteca'" in ui_text and 'juego' in render_block))
        results.append(check('ui_uses_real_or_fallback_icons', '_start_game_artwork_jobs' in ui_text and '_placeholder_game_image' in ui_text and 'CTkImage' in ui_text))
        results.append(check('ui_uses_clean_display_name', "game.get('display_name')" in render_block))
        results.append(check('ui_hides_exe_path_and_source', '_game_source_label' not in render_block and 'path_text' not in render_block and "game.get('pid')" not in render_block))
        results.append(check('ui_has_remove_manual_action', 'def _remove_manual_game' in ui_text))

        # Icono fallback siempre válido, incluso fuera de Windows o sin ruta real.
        icon = extract_executable_icon('', 42)
        results.append(check('fallback_icon_is_rgba', icon.mode == 'RGBA' and icon.size == (42, 42)))
        results.append(check('plain_exe_name_cleaner', display_game_name('valorant.exe') == 'Valorant'))
        results.append(check('shipping_suffix_cleaner', display_game_name('MyGame-Win64-Shipping.exe') == 'My Game'))

    ok = all(results)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
