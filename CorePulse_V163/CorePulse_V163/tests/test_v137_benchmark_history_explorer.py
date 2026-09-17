"""V137 — historial de benchmark dedicado y comparación equivalente."""
from __future__ import annotations

from pathlib import Path
import tempfile
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION, STAGE
from core.health_history import HealthHistoryStore


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print('[PASS]', name)


def main():
    check('version', VERSION == '137')
    check('stage', STAGE == 'BENCHMARK_HISTORY_EXPLORER_AND_EQUIVALENT_COMPARISON')

    ui = (ROOT / 'gui' / 'benchmark_panel.py').read_text(encoding='utf-8')
    hist = (ROOT / 'gui' / 'benchmark_history_panel.py').read_text(encoding='utf-8')
    health = (ROOT / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')
    check('benchmark_tabs', "text='Historial'" in ui and 'BenchmarkHistoryPanel' in ui and "_show_section('history')" in ui)
    check('history_real_or_na', 'no existen rankings externos' in hist.lower() and '_equivalent' in hist and 'Renderer OpenGL' in hist)
    check('renderer_persisted', "'renderer': (gpu_result or {}).get('renderer')" in health)

    with tempfile.TemporaryDirectory() as td:
        store = HealthHistoryStore(Path(td) / 'history.sqlite3')
        sample = {
            'finished_at': 1000.0,
            'duration_s': 12.5,
            'profile': 'standard',
            'selected_components': ['gpu', 'cpu'],
            'status': 'OK',
            'visual_gpu': {'renderer': 'GPU Test', 'frames_per_s': 80.0, 'one_percent_low_fps': 60.0},
            'system_suite': {'cpu': {'status': 'OK', 'throughput_mbps': 900.0}},
        }
        store.record_benchmark_session(sample, profile='standard', components=['gpu', 'cpu'], hardware={'cpu_name': 'CPU Test', 'gpu_name': 'GPU Test', 'renderer': 'GPU Test'})
        check('session_count', store.benchmark_session_count() == 1)
        rows = store.latest_benchmark_sessions(limit=5)
        check('session_roundtrip', len(rows) == 1 and rows[0]['hardware'].get('renderer') == 'GPU Test' and rows[0]['suite'].get('duration_s') == 12.5)

    protected = [
        'core/runtime_venv_path.py', 'bootstrap_corepulse.py',
        'core/source_runtime_bootstrap.py', 'requirements-runtime-lock.txt',
        'core/nvme_smart_windows.py',
    ]
    check('protected_present', all((ROOT / item).exists() for item in protected))


if __name__ == '__main__':
    main()
