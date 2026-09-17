"""V100 — evita el relaunch loop python.exe/pythonw.exe."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from core.version import VERSION

def check(name, value):
    if not value:
        raise AssertionError(name)
    print('[PASS]', name)

def main():
    src=(ROOT/'core/source_runtime_bootstrap.py').read_text(encoding='utf-8')
    boot=(ROOT/'bootstrap_corepulse.py').read_text(encoding='utf-8')
    check('version', VERSION == '103')
    check('python_exe_accepted', '_same_executable(current, local_python)' in src)
    check('pythonw_exe_accepted', '_same_executable(current, local_pythonw)' in src)
    check('pythonw_declared', 'local_pythonw = _venv_pythonw(root)' in src)
    check('bootstrap_launches_pythonw', 'pyw = VENV_PYW if VENV_PYW.is_file() else VENV_PY' in boot)
    check('only_bootstraps_when_not_local_or_missing_imports', 'if using_local and _imports_ready()' in src)
    print('RESULTADO: PASS')

if __name__ == '__main__':
    main()
