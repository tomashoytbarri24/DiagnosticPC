"""Impide que futuras revisiones reviertan el runtime universal canónico."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION


def check(name, cond):
    if not cond:
        raise AssertionError(name)
    print('[PASS]', name)


def main():
    runtime = (ROOT / 'core' / 'runtime_venv_path.py').read_text(encoding='utf-8')
    bootstrap = (ROOT / 'bootstrap_corepulse.py').read_text(encoding='utf-8')
    source_bootstrap = (ROOT / 'core' / 'source_runtime_bootstrap.py').read_text(encoding='utf-8')
    check('version', VERSION == '103')
    check('userprofile_runtime_root', 'USERPROFILE' in runtime and '".corepulse" / "runtime"' in runtime)
    check('localappdata_not_runtime_authority', 'os.environ.get("LOCALAPPDATA")' not in runtime and "os.environ.get('LOCALAPPDATA')" not in runtime)
    check('project_venv_not_windows_authority', "if os.name == \"nt\"" in runtime and 'return root / ".venv"' in runtime)
    check('bootstrap_uses_runtime_authority', 'source_runtime_venv' in bootstrap)
    check('source_bootstrap_uses_runtime_authority', 'source_runtime_venv' in source_bootstrap)
    print('RESULTADO: PASS')


if __name__ == '__main__':
    main()
