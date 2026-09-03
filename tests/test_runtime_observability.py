"""Pruebas de observabilidad y trazabilidad introducidas en V0.9.19.0w."""
from __future__ import annotations

import ast
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.runtime_logging import redact_sensitive_text
from core.version import VERSION, STAGE


def check(name, condition):
    print(f"[{'PASS' if condition else 'FAIL'}] {name}: {bool(condition)}")
    return bool(condition)


def main():
    main_text = (ROOT / 'main.py').read_text(encoding='utf-8')
    dashboard_text = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    nav_text = (ROOT / 'gui' / 'internal_navigation.py').read_text(encoding='utf-8')
    panel_text = (ROOT / 'gui' / 'telemetry_detail_panel.py').read_text(encoding='utf-8')
    logging_text = (ROOT / 'core' / 'runtime_logging.py').read_text(encoding='utf-8')

    results = [
        check('version_bumped', VERSION == '0.10.0.0w'),
        check('stage_matches_reliability', STAGE == 'HEALTH_INTELLIGENCE_RECOVERY'),
        check('telemetry_internal_page_registered', "'telemetry_details': None" in nav_text and "'telemetry_details': 'telemetry_detail_panel'" in nav_text),
        check('dashboard_coverage_is_clickable', 'open_telemetry_details' in dashboard_text and 'clic para inspeccionar' in dashboard_text),
        check('panel_reads_certified_metadata', "telemetry.get('_metrics')" in panel_text and "telemetry.get('_sensor_summary')" in panel_text),
        check('panel_does_not_collect_hardware_directly', 'get_system_telemetry' not in panel_text and '_collect_snapshot' not in panel_text),
        check('runtime_logging_is_rotating', 'RotatingFileHandler' in logging_text),
        check('uncaught_hooks_installed', 'install_exception_hooks()' in main_text),
        check('telemetry_errors_are_not_silent', "Fallo durante un ciclo de adquisición de telemetría" in main_text),
        check('secret_redaction', 'abc123' not in redact_sensitive_text('GROQ_API_KEY=abc123')),
    ]

    for path in [ROOT / 'core' / 'runtime_logging.py', ROOT / 'gui' / 'telemetry_detail_panel.py']:
        ast.parse(path.read_text(encoding='utf-8'))

    ok = all(results)
    print(f'\nRESULTADO: {"PASS" if ok else "FAIL"}')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
