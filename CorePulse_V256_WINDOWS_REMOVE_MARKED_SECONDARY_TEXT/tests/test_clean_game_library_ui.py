"""Regresión V100 — biblioteca limpia: icono + nombre, identidad técnica intacta."""
from __future__ import annotations

from pathlib import Path
import tempfile
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION
from performance.game_detector import GameDetector
from performance.game_presentation import display_game_name, fallback_game_icon, extract_executable_icon


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    return True


def main():
    checks = []
    checks.append(check('version', VERSION == '103'))

    # El nombre visible se limpia sin convertirlo en identidad de proceso.
    checks.append(check(
        'shipping_suffix_removed',
        display_game_name('VALORANT-Win64-Shipping.exe') == 'VALORANT',
    ))
    checks.append(check('exe_suffix_removed', display_game_name('eldenring.exe') == 'Eldenring'))
    checks.append(check('camel_case_readable', display_game_name('ForzaHorizon5.exe') == 'Forza Horizon5'))

    with tempfile.TemporaryDirectory() as td:
        cfg = Path(td) / 'performance_games.json'
        detector = GameDetector(config_path=cfg, process_provider=lambda: [])
        supplied = r'C:\Games\VALORANT-Win64-Shipping.exe'
        checks.append(check('manual_add', detector.add_manual_game(supplied)))
        rows = detector.registered_games([])
        checks.append(check('one_registered_game', len(rows) == 1))
        row = rows[0]
        checks.append(check('technical_identity_kept', row.get('name') == 'valorant-win64-shipping.exe'))
        checks.append(check('clean_display_name', row.get('display_name') == 'VALORANT'))
        checks.append(check('closed_game_has_no_fake_pid', row.get('pid') is None and not row.get('active')))

        # Los metadatos de presentación sobreviven al reinicio sin romper config antigua.
        detector2 = GameDetector(config_path=cfg, process_provider=lambda: [])
        row2 = detector2.registered_games([])[0]
        checks.append(check('display_name_persisted', row2.get('display_name') == 'VALORANT'))
        checks.append(check('technical_identity_persisted', row2.get('name') == 'valorant-win64-shipping.exe'))

    fallback = fallback_game_icon(42)
    checks.append(check('fallback_icon_rgba', fallback.mode == 'RGBA' and fallback.size == (42, 42)))
    missing = extract_executable_icon('', 42)
    checks.append(check('icon_failure_is_safe', missing.mode == 'RGBA' and missing.size == (42, 42)))

    ui = (ROOT / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')
    block = ui.split('    def _render_registered_games', 1)[1].split('    def _remove_manual_game', 1)[0]
    checks.append(check('ui_uses_display_name', "game.get('display_name')" in block))
    checks.append(check('ui_uses_visual_art', '_start_game_artwork_jobs' in ui and '_placeholder_game_image' in ui and 'artwork_jobs.append' in block))
    for forbidden in ('EN EJECUCIÓN · PID', 'LISTO PARA DETECTAR', 'Ruta N/A', '_game_source_label('):
        checks.append(check(f'ui_hides_{forbidden}', forbidden not in block))

    print(f'PASS clean_game_library_ui ({len(checks)} checks)')


if __name__ == '__main__':
    main()
