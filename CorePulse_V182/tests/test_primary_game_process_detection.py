"""V100: AUTO detecta un único proceso principal por instalación de juego."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION
from performance.game_detector import GameDetector, _looks_like_dependency, _norm_path


def check(name, condition):
    ok = bool(condition)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {ok}")
    return ok


def main():
    results = []
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        steam_common = base / 'Steam' / 'steamapps' / 'common'
        game_root = steam_common / 'ExampleGame'
        game_exe = game_root / 'Binaries' / 'Win64' / 'ExampleGame-Win64-Shipping.exe'
        helper = game_root / 'Engine' / 'Binaries' / 'Win64' / 'CrashReportClient.exe'
        anticheat = game_root / 'EasyAntiCheat' / 'EasyAntiCheat_EOS.exe'
        worker = game_root / 'Binaries' / 'Win64' / 'BackgroundWorker.exe'
        for path in (game_exe, helper, anticheat, worker):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'MZ')

        processes = [
            {'pid': 11, 'name': 'CrashReportClient.exe', 'exe': str(helper), 'rss': 40_000_000},
            {'pid': 12, 'name': 'EasyAntiCheat_EOS.exe', 'exe': str(anticheat), 'rss': 55_000_000},
            {'pid': 13, 'name': 'BackgroundWorker.exe', 'exe': str(worker), 'rss': 90_000_000},
            {'pid': 14, 'name': 'ExampleGame-Win64-Shipping.exe', 'exe': str(game_exe), 'rss': 1_400_000_000},
        ]
        detector = GameDetector(config_path=base/'games.json', process_provider=lambda: iter(processes))
        detector.refresh_libraries = lambda force=False: None
        detector._steam_roots = {_norm_path(steam_common)}
        detector._epic_roots = set(); detector._epic_launch_exes = set()
        detector._visible_window_pids = lambda: {14}
        games = detector.detect_active_games()
        results += [
            check('version', VERSION.isdecimal()),
            check('dependency_classifier_crash', _looks_like_dependency('CrashReportClient.exe')),
            check('dependency_classifier_anticheat', _looks_like_dependency('EasyAntiCheat_EOS.exe')),
            check('one_process_per_install', len(games) == 1),
            check('shipping_game_is_primary', games and games[0]['name'] == 'examplegame-win64-shipping.exe' and games[0]['pid'] == 14),
        ]
        raw = json.loads((base/'games.json').read_text(encoding='utf-8'))
        results += [
            check('only_primary_learned', raw.get('learned_exes') == ['examplegame-win64-shipping.exe']),
            check('canonical_identity_persisted', list((raw.get('canonical_by_game_id') or {}).values()) == ['examplegame-win64-shipping.exe']),
        ]

        # Si sólo queda un worker desconocido sin ventana/evidencia positiva, AUTO no debe activarse.
        detector.process_provider = lambda: iter([processes[2]])
        detector._visible_window_pids = lambda: set()
        # El worker nunca fue canónico ni aprendido.
        results.append(check('unknown_worker_alone_not_game', detector.detect_active_games() == []))

        # Un helper con nombre de launcher tampoco puede activar AUTO por sí solo.
        launcher = game_root / 'GameLauncher.exe'
        launcher.write_bytes(b'MZ')
        detector.process_provider = lambda: iter([{'pid': 21, 'name': 'GameLauncher.exe', 'exe': str(launcher), 'rss': 150_000_000}])
        detector._visible_window_pids = lambda: {21}
        results.append(check('launcher_window_not_game', detector.detect_active_games() == []))

        # Dos instalaciones Steam distintas conservan multi-juego real.
        second_root = steam_common / 'SecondGame'
        second = second_root / 'SecondGame.exe'
        second.parent.mkdir(parents=True); second.write_bytes(b'MZ')
        detector.process_provider = lambda: iter([
            {'pid': 31, 'name': 'ExampleGame-Win64-Shipping.exe', 'exe': str(game_exe), 'rss': 1_000_000_000},
            {'pid': 32, 'name': 'SecondGame.exe', 'exe': str(second), 'rss': 800_000_000},
        ])
        detector._visible_window_pids = lambda: {31, 32}
        names = {g['name'] for g in detector.detect_active_games()}
        results.append(check('two_real_games_preserved', names == {'examplegame-win64-shipping.exe', 'secondgame.exe'}))

        # Alta manual explícita gana incluso si su nombre parece launcher/helper.
        manual = base / 'Custom' / 'MyLauncher.exe'
        manual.parent.mkdir(); manual.write_bytes(b'MZ')
        manual_detector = GameDetector(config_path=base/'manual.json', process_provider=lambda: iter([
            {'pid': 41, 'name': 'MyLauncher.exe', 'exe': str(manual), 'rss': 20_000_000},
        ]))
        manual_detector.refresh_libraries = lambda force=False: None
        manual_detector._visible_window_pids = lambda: set()
        manual_detector.add_manual_game(str(manual))
        manual_games = manual_detector.detect_active_games()
        results.append(check('manual_override_respected', len(manual_games) == 1 and manual_games[0]['name'] == 'mylauncher.exe'))

        # Migración visual: configuración antigua contaminada con varios EXE del mismo Steam game.
        legacy = base / 'legacy_polluted.json'
        legacy.write_text(json.dumps({
            'manual_exes': [], 'excluded_exes': [],
            'learned_exes': ['ExampleGame-Win64-Shipping.exe', 'CrashReportClient.exe', 'BackgroundWorker.exe'],
            'learned_paths': {
                'ExampleGame-Win64-Shipping.exe': str(game_exe),
                'CrashReportClient.exe': str(helper),
                'BackgroundWorker.exe': str(worker),
            },
            'learned_sources': {
                'ExampleGame-Win64-Shipping.exe': 'STEAM',
                'CrashReportClient.exe': 'STEAM',
                'BackgroundWorker.exe': 'STEAM',
            },
        }), encoding='utf-8')
        migrated = GameDetector(config_path=legacy, process_provider=lambda: iter(()))
        migrated.refresh_libraries = lambda force=False: None
        migrated._steam_roots = {_norm_path(steam_common)}
        rows = migrated.registered_games([])
        results.append(check('polluted_catalog_collapses_to_one', len(rows) == 1 and rows[0]['name'] == 'examplegame-win64-shipping.exe'))

    ok = all(results)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
