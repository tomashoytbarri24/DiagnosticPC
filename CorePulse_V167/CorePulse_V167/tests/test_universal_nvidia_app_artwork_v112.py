from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from core.version import VERSION

def check(name, cond):
    if not cond: raise AssertionError(name)
    print('[PASS]', name)

def main():
    src=(ROOT/'performance'/'game_presentation.py').read_text(encoding='utf-8')
    check('version', VERSION=='112')
    check('nvidia_app_context', 'ApplicationStorage.json' in src and "os.environ.get('LOCALAPPDATA')" in src)
    check('no_hardcoded_windows_user', 'C:\\Users\\' not in src and 'tomashoyt' not in src.lower() and 'raami' not in src.lower())
    check('record_to_exe_matching', 'def _nvidia_record_match_score' in src and 'DetectedFiles' in src)
    check('local_cache_only', 'def _nvidia_image_inventory' in src and 'os.walk(root)' in src)
    check('source_exposed', "source = 'NVIDIA_APP'" in src)
    check('custom_still_wins', "source = 'CUSTOM'" in src)
    check('steam_local_fallback_preserved', 'discover_local_game_artwork(exe_path)' in src)
    print('RESULTADO: PASS')
if __name__=='__main__': main()
