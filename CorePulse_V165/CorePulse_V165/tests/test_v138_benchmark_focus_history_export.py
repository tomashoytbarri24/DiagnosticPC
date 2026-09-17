"""V138 — benchmark enfocado e historial dedicado/exportable."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION, STAGE


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print('[PASS]', name)


def main():
    check('version', VERSION == '138')
    check('stage', STAGE == 'BENCHMARK_FOCUSED_RUN_AND_HISTORY_EXPORT_POLISH')

    panel = (ROOT / 'gui' / 'benchmark_panel.py').read_text(encoding='utf-8')
    health = (ROOT / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')
    history = (ROOT / 'gui' / 'benchmark_history_panel.py').read_text(encoding='utf-8')

    check('history_dedicated_tab', "text='Historial'" in panel and "_show_section('history')" in panel)
    render_segment = health[health.index('    def _render_gaming_benchmark_section'):health.index('    def _format_visual_metric')]
    check('no_inline_history', 'self._render_benchmark_history()' not in render_segment)
    check('quick_component_controls', "'Todos'" in render_segment and "'Ninguno'" in render_segment and '_set_all_benchmark_components' in health)
    check('benchmark_sensor_scope', "benchmark_keys = {'cpu', 'ram', 'gpu', 'storage'}" in health and 'batería no forma parte' in health.lower())
    check('history_status_filter', 'STATUS_FILTERS' in history and 'status_filter' in history)
    check('history_csv_export', 'Exportar CSV' in history and 'csv.DictWriter' in history and 'renderer_opengl' in history)
    check('real_or_na', 'no existen rankings externos' in history.lower() and 'N/A' in history)

    protected = [
        'core/runtime_venv_path.py', 'bootstrap_corepulse.py',
        'core/source_runtime_bootstrap.py', 'requirements-runtime-lock.txt',
        'core/nvme_smart_windows.py',
    ]
    check('protected_present', all((ROOT / item).exists() for item in protected))


if __name__ == '__main__':
    main()
