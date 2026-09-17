"""V113 — artwork local universal por launcher (Steam/Epic/Riot)."""
from pathlib import Path
import os
import sys
import tempfile
import json
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from performance.game_presentation import (
    discover_local_game_artwork,
    load_game_artwork,
)


def check(name, cond):
    if not cond:
        raise AssertionError(name)
    print('[PASS]', name)


def img(path: Path, size=(640, 360)):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new('RGB', size, (30, 80, 120)).save(path)
    return path


def main():
    old_programdata = os.environ.get('PROGRAMDATA')
    old_local = os.environ.get('LOCALAPPDATA')
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        programdata = base / 'ProgramData'
        local = base / 'LocalAppData'
        os.environ['PROGRAMDATA'] = str(programdata)
        os.environ['LOCALAPPDATA'] = str(local)

        # Epic: manifest real -> InstallLocation -> Splash real.
        epic_root = base / 'EpicLibrary' / 'ExampleEpicGame'
        epic_exe = epic_root / 'Binaries' / 'Win64' / 'ExampleEpicGame-Win64-Shipping.exe'
        epic_exe.parent.mkdir(parents=True, exist_ok=True)
        epic_exe.write_bytes(b'MZ')
        epic_art = img(epic_root / 'Content' / 'Splash' / 'exampleepicgame_splash.png')
        manifests = programdata / 'Epic' / 'EpicGamesLauncher' / 'Data' / 'Manifests'
        manifests.mkdir(parents=True, exist_ok=True)
        (manifests / 'example.item').write_text(
            '{"InstallLocation": %r, "LaunchExecutable": "Binaries/Win64/ExampleEpicGame-Win64-Shipping.exe", "DisplayName": "Example Epic Game", "AppName": "ExampleEpicGame", "CatalogItemId": "example-epic-catalog"}' % str(epic_root),
            encoding='utf-8',
        )
        # %r uses single quotes: JSON requires double quotes. Normalize safely.
        raw = (manifests / 'example.item').read_text(encoding='utf-8')
        raw = raw.replace(repr(str(epic_root)), '"' + str(epic_root).replace('\\', '\\\\') + '"')
        (manifests / 'example.item').write_text(raw, encoding='utf-8')

        found = discover_local_game_artwork(epic_exe, title_hint='Example Epic Game', source_hint='EPIC')
        check('epic_manifest_artwork', found is not None and found.resolve() == epic_art.resolve())
        _pil, source, resolved = load_game_artwork(epic_exe, title_hint='Example Epic Game', source_hint='EPIC')
        check('epic_source_traced', source == 'EPIC_LOCAL' and Path(resolved).resolve() == epic_art.resolve())

        # Epic webcache extensionless: URL/token + imagen embebida real.
        cached_game_root = base / 'EpicLibrary' / 'CacheOnlyGame'
        cached_exe = cached_game_root / 'CacheOnlyGame.exe'
        cached_game_root.mkdir(parents=True, exist_ok=True)
        cached_exe.write_bytes(b'MZ')
        (manifests / 'cacheonly.item').write_text(
            json.dumps({
                'InstallLocation': str(cached_game_root),
                'LaunchExecutable': 'CacheOnlyGame.exe',
                'DisplayName': 'Cache Only Game',
                'AppName': 'CacheOnlyGame',
                'CatalogItemId': 'cache-only-catalog',
            }), encoding='utf-8'
        )
        import io
        buf = io.BytesIO()
        Image.new('RGB', (720, 405), (90, 30, 70)).save(buf, 'JPEG')
        webcache = local / 'EpicGamesLauncher' / 'Saved' / 'webcache_999' / 'Cache' / 'Cache_Data'
        webcache.mkdir(parents=True, exist_ok=True)
        (webcache / 'f_000123').write_bytes(b'https://cdn.example/cache-only-catalog/keyart.jpg\x00' + buf.getvalue())
        found = discover_local_game_artwork(cached_exe, title_hint='Cache Only Game', source_hint='EPIC')
        check('epic_extensionless_webcache', found is not None and 'CorePulse' in str(found))

        # Riot: ruta real del producto -> Splash/branding local.
        riot_root = base / 'Riot Games' / 'VALORANT'
        riot_exe = riot_root / 'live' / 'VALORANT.exe'
        riot_exe.parent.mkdir(parents=True, exist_ok=True)
        riot_exe.write_bytes(b'MZ')
        riot_art = img(riot_root / 'ShooterGame' / 'Content' / 'Splash' / 'valorant_splash.png')
        found = discover_local_game_artwork(riot_exe, title_hint='VALORANT', source_hint='RIOT')
        check('riot_local_artwork', found is not None and found.resolve() == riot_art.resolve())
        _pil, source, resolved = load_game_artwork(riot_exe, title_hint='VALORANT', source_hint='RIOT')
        check('riot_source_traced', source == 'RIOT_LOCAL' and Path(resolved).resolve() == riot_art.resolve())

        # Steam moderno: config/librarycache además de appcache/librarycache.
        steam = base / 'Steam'
        steam_root = steam / 'steamapps' / 'common' / 'ExampleSteamGame'
        steam_exe = steam_root / 'ExampleSteamGame.exe'
        steam_root.mkdir(parents=True, exist_ok=True)
        steam_exe.write_bytes(b'MZ')
        steamapps = steam / 'steamapps'
        (steamapps / 'appmanifest_123.acf').write_text(
            '"AppState"\n{\n  "appid" "123"\n  "installdir" "ExampleSteamGame"\n}',
            encoding='utf-8',
        )
        steam_art = img(steam / 'config' / 'librarycache' / '123' / '123_library_hero.jpg')
        found = discover_local_game_artwork(steam_exe, title_hint='Example Steam Game', source_hint='STEAM')
        check('steam_modern_config_cache', found is not None and found.resolve() == steam_art.resolve())

    if old_programdata is None:
        os.environ.pop('PROGRAMDATA', None)
    else:
        os.environ['PROGRAMDATA'] = old_programdata
    if old_local is None:
        os.environ.pop('LOCALAPPDATA', None)
    else:
        os.environ['LOCALAPPDATA'] = old_local

    ui = (Path(__file__).resolve().parents[1] / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')
    check('ui_passes_launcher_source', "source_hint=job.get('source_hint')" in ui)
    check('ui_passes_title_hint', "title_hint=job.get('title_hint')" in ui)
    print('RESULTADO: PASS')


if __name__ == '__main__':
    main()
