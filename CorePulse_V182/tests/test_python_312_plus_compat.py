"""Regresión V100: CorePulse acepta Python 3.12+ sin tope artificial."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.python_compat import is_supported_python, compatibility_summary
from core.version import VERSION, MIN_PYTHON, PYTHON_POLICY


def check(name, condition):
    print(f"[{'PASS' if condition else 'FAIL'}] {name}: {bool(condition)}")
    return bool(condition)


def main():
    installer = (ROOT / 'instalar_dependencias.bat').read_text(encoding='utf-8')
    req = (ROOT / 'requirements.txt').read_text(encoding='utf-8')
    req_sensors = (ROOT / 'requirements-sensors.txt').read_text(encoding='utf-8')
    pyproject = (ROOT / 'pyproject.toml').read_text(encoding='utf-8')
    main_text = (ROOT / 'main.py').read_text(encoding='utf-8')
    summary = compatibility_summary()
    results = [
        check('version', VERSION.isdecimal()),
        check('minimum_python', MIN_PYTHON == (3, 12) and PYTHON_POLICY == '3.12+'),
        check('312_supported', is_supported_python((3, 12, 0))),
        check('313_supported', is_supported_python((3, 13, 0))),
        check('future_supported_by_policy', is_supported_python((3, 99, 0))),
        check('311_rejected', not is_supported_python((3, 11, 9))),
        check('no_artificial_upper_bound', summary['no_artificial_upper_bound'] is True),
        check('pyproject_requires_312_plus', 'requires-python = \">=3.12\"' in pyproject),
        check('base_requirements_do_not_force_pythonnet', 'pythonnet' not in req.lower()),
        check('sensor_stack_is_separate', 'pythonnet' in req_sensors.lower() and 'hardwaremonitor' in req_sensors.lower()),
        check('release_builder_pins_python_312', "sys.version_info[:2]==(3,12)" in installer and 'py -3.12' in installer),
        check('installer_uses_virtualenv', '.venv' in installer and '-m venv' in installer),
        check('release_builder_requires_sensor_stack', 'FAIL_SENSORS' in installer and 'No se permite construir un EXE con sensores profundos rotos.' in installer),
        check('main_enforces_minimum_early', 'enforce_minimum_python()' in main_text[:500]),
    ]
    ok = all(results)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
