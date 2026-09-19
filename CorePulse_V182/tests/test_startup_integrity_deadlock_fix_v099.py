"""V100 — la integridad profunda no puede congelar el gate de arranque."""
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
    main_py = (ROOT / 'main.py').read_text(encoding='utf-8')
    readiness = (ROOT / 'core' / 'startup_readiness.py').read_text(encoding='utf-8')
    check('version', VERSION.isdecimal())
    check('core_gate_requires_real_ui_and_telemetry', "core_keys = ('layout', 'charts', 'services')" in main_py)
    check('integrity_watchdog_12s', 'max_wait = 12.0' in main_py and '_startup_integrity_watchdog' in main_py)
    check('integrity_can_continue_background', 'La comprobación profunda continúa en segundo plano' in main_py)
    check('hardwaremonitor_probe_isolated', "[sys.executable, '-c', code]" in readiness)
    check('hardwaremonitor_probe_timeout', 'timeout=5' in readiness and 'subprocess.TimeoutExpired' in readiness)
    check('optional_sensor_timeout_is_na', 'sensores profundos quedan N/A' in readiness)
    print('RESULTADO: PASS')


if __name__ == '__main__':
    main()
