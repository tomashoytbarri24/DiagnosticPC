"""V100: dependencias como EAC Bootstrapper no pueden quedar como juegos automáticos."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION
import performance.game_detector as game_detector_module
from performance.game_detector import GameDetector, _looks_like_dependency, _norm_path


def check(name, condition):
    ok = bool(condition)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {ok}")
    return ok


def main():
    results = [
        check('version', VERSION == '103'),
        check('eac_metadata_detected', _looks_like_dependency('unknown.exe', '', 'Easy Anti Cheat Bootstrapper (EOS)')),
        check('protected_bootstrap_exe_detected', _looks_like_dependency('start_protected_game.exe')),
    ]
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        steam_common = base / 'Steam' / 'steamapps' / 'common'
        root = steam_common / 'RealGame'
        main_exe = root / 'Binaries' / 'Win64' / 'RealGame-Win64-Shipping.exe'
        eac_exe = root / 'start_protected_game.exe'
        main_exe.parent.mkdir(parents=True)
        main_exe.write_bytes(b'MZ')
        eac_exe.write_bytes(b'MZ')
        cfg = base / 'games.json'
        cfg.write_text(json.dumps({
            'manual_exes': [],
            'excluded_exes': [],
            'learned_exes': ['start_protected_game.exe', 'RealGame-Win64-Shipping.exe'],
            'learned_paths': {
                'start_protected_game.exe': str(eac_exe),
                'RealGame-Win64-Shipping.exe': str(main_exe),
            },
            'learned_sources': {
                'start_protected_game.exe': 'STEAM',
                'RealGame-Win64-Shipping.exe': 'STEAM',
            },
            'learned_titles': {
                'start_protected_game.exe': 'Easy Anti Cheat Bootstrapper (EOS)',
                'RealGame-Win64-Shipping.exe': 'Real Game',
            },
        }), encoding='utf-8')
        detector = GameDetector(config_path=cfg, process_provider=lambda: iter(()))
        detector.refresh_libraries = lambda force=False: None
        detector._steam_roots = {_norm_path(steam_common)}
        rows = detector.registered_games([])
        results.append(check('polluted_eac_removed_from_visible_library', [r['name'] for r in rows] == ['realgame-win64-shipping.exe']))
        persisted = json.loads(cfg.read_text(encoding='utf-8'))
        results.append(check('polluted_eac_removed_from_config', 'start_protected_game.exe' not in persisted.get('learned_exes', [])))
        results.append(check('polluted_eac_metadata_removed', 'start_protected_game.exe' not in (persisted.get('learned_titles') or {})))

        # Incluso con una ventana visible, el bootstrapper solo no puede activar AUTO.
        detector.process_provider = lambda: iter([
            {'pid': 55, 'name': 'start_protected_game.exe', 'exe': str(eac_exe), 'rss': 120_000_000},
        ])
        detector._visible_window_pids = lambda: {55}
        results.append(check('visible_bootstrapper_never_game', detector.detect_active_games() == []))

        # Caso más difícil: nombre de EXE neutro y EAC identificado sólo por metadatos de versión.
        wrapper = root / 'ProtectedRuntime.exe'
        wrapper.write_bytes(b'MZ')
        original_display = game_detector_module.display_game_name
        try:
            game_detector_module.display_game_name = lambda exe_name, exe_path=None, name_hint=None: (
                'Easy Anti Cheat Bootstrapper (EOS)' if str(exe_name).lower() == 'protectedruntime.exe' else original_display(exe_name, exe_path, name_hint)
            )
            runtime_detector = GameDetector(config_path=base/'runtime_meta.json', process_provider=lambda: iter([
                {'pid': 56, 'name': 'ProtectedRuntime.exe', 'exe': str(wrapper), 'rss': 180_000_000},
            ]))
            runtime_detector.refresh_libraries = lambda force=False: None
            runtime_detector._steam_roots = {_norm_path(steam_common)}
            runtime_detector._visible_window_pids = lambda: {56}
            results.append(check('metadata_only_anticheat_never_game', runtime_detector.detect_active_games() == []))
        finally:
            game_detector_module.display_game_name = original_display

    ok = all(results)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
