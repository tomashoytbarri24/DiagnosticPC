"""Detección conservadora de juegos con múltiples fuentes."""
from __future__ import annotations
from pathlib import Path
import tempfile, sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from performance.game_detector import GameDetector, _norm_path


def check(name, condition):
    print(f"[{'PASS' if condition else 'FAIL'}] {name}: {bool(condition)}"); return bool(condition)


def main():
    with tempfile.TemporaryDirectory() as td:
        base=Path(td); steam=base/'Steam'/'steamapps'/'common'; epic=base/'EpicGame'; steam.mkdir(parents=True); epic.mkdir()
        processes=[
            {'pid':1,'name':'steam.exe','exe':str(base/'Steam'/'steam.exe')},
            {'pid':2,'name':'SonsOfTheForest.exe','exe':str(steam/'SonsOfTheForest'/'SonsOfTheForest.exe')},
            {'pid':3,'name':'EpicGame.exe','exe':str(epic/'EpicGame.exe')},
            {'pid':4,'name':'Discord.exe','exe':str(base/'Discord.exe')},
        ]
        d=GameDetector(config_path=base/'games.json', process_provider=lambda: iter(processes))
        d.refresh_libraries=lambda force=False: None
        d._steam_roots={_norm_path(steam)}; d._epic_roots={_norm_path(epic)}; d._epic_launch_exes={'epicgame.exe'}
        games=d.detect_active_games(); names={g['name'] for g in games}
        results=[
            check('steam_game_detected','sonsoftheforest.exe' in names),
            check('epic_game_detected','epicgame.exe' in names),
            check('steam_launcher_excluded','steam.exe' not in names),
            check('discord_excluded','discord.exe' not in names),
            check('multiple_games_preserved',len(games)==2),
        ]
        d.exclude('EpicGame.exe'); games=d.detect_active_games(); names={g['name'] for g in games}
        results.append(check('explicit_exclusion_wins','epicgame.exe' not in names))
        d.add_manual_game('CustomTitle.exe')
        processes.append({'pid':5,'name':'CustomTitle.exe','exe':str(base/'other'/'CustomTitle.exe')})
        games=d.detect_active_games(); names={g['name'] for g in games}
        results.append(check('manual_game_detected','customtitle.exe' in names))
        ok=all(results); print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}"); return 0 if ok else 1
if __name__=='__main__': raise SystemExit(main())
