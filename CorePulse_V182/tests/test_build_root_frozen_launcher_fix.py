"""Regresión de root de build y separación recurso/ejecutable."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from core.version import VERSION, STAGE

def check(name,cond):
    if not cond: raise AssertionError(name)
    print('[PASS]',name)

def main():
    spec=(ROOT/'build/CorePulse.spec').read_text(encoding='utf-8')
    launcher=(ROOT/'corepulse_launcher.py').read_text(encoding='utf-8')
    paths=(ROOT/'core/runtime_paths.py').read_text(encoding='utf-8')
    check('version',VERSION.isdecimal())
    check('stage',bool(STAGE))
    check('spec_root_one_level','ROOT = SPEC_DIR.parent' in spec and 'parent.parent' not in spec)
    check('launcher_analysis_visible','from main import App' in launcher and 'runpy.run_path' not in launcher)
    check('frozen_runtime_authority','getattr(sys, "frozen", False)' in paths and '_MEIPASS' in paths)
    check('executable_root_separate','Path(sys.executable).resolve().parent' in paths)
    check('icon_exists',(ROOT/'assets/app_icon.ico').is_file())
    print('RESULTADO: PASS')
if __name__=='__main__': main()
