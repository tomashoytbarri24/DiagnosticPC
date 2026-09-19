"""V100 — un fallo al actualizar pip no bloquea el runtime."""
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
    boot=(ROOT/'bootstrap_corepulse.py').read_text(encoding='utf-8')
    check('version', VERSION.isdecimal())
    check('pip_probe', '"pip", "--version"' in boot)
    check('ensurepip_repair', '"ensurepip", "--upgrade"' in boot)
    check('runtime_installer_is_separate', 'def _install_runtime_lock()' in boot)
    check('runtime_retries', '"--retries", "4"' in boot and 'reintentando una vez' in boot)
    prepare=boot.split('def _prepare(progress) -> None:',1)[1].split('def _launch()',1)[0]
    check('pip_upgrade_not_required_in_prepare', '_refresh_packaging_tools_best_effort()' not in prepare)
    check('real_runtime_failure_has_detail', 'Detalle de pip:' in boot)
    check('runtime_lock_still_used', 'requirements-runtime-lock.txt' in boot)
    print('RESULTADO: PASS')

if __name__ == '__main__':
    main()
