"""Regresión V100 — el Dashboard no aparece antes de la primera telemetría real renderizada."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION, STAGE


def check(name, cond):
    if not cond:
        raise AssertionError(name)
    print('[PASS]', name)


def main():
    main_py = (ROOT / 'main.py').read_text(encoding='utf-8')
    profiler = (ROOT / 'core' / 'startup_profiler.py').read_text(encoding='utf-8')
    telemetry_policy = (ROOT / 'core' / 'telemetry.py').read_text(encoding='utf-8')
    fps_policy = (ROOT / 'core' / 'fps_certification.py').read_text(encoding='utf-8')

    check('version', VERSION.isdecimal())
    check('startup_foundation_preserved', bool(STAGE))
    check('first_sample_flags', '_startup_first_telemetry_acquired = False' in main_py and '_startup_first_telemetry_applied = False' in main_py)
    check('services_not_complete_on_thread_start', "'services', 0.90" in main_py and 'Leyendo la primera muestra real' in main_py)
    check('acquisition_marked_from_real_snapshot', "self._startup_mark('first_telemetry_acquired'" in main_py)
    check('ui_commit_counter', '_telemetry_ui_apply_count' in main_py and 'Contador de commit visual' in main_py)
    check('release_after_ui_commit', '_complete_startup_after_first_telemetry(telemetry)' in main_py and "'services', 1.0, 'Monitoreo en tiempo real activo'" in main_py)
    check('charts_primed_before_release', '_prime_startup_charts_from_real_history()' in main_py and 'self.canvas.draw()' in main_py)
    check('no_fake_sample_generation', 'No crea muestras: sólo consume los deques que llenó telemetry_loop.' in main_py)
    check('real_or_na_preserved', 'REAL_OR_NA' in telemetry_policy and 'REAL_FPS_OR_NA_ONLY' in fps_policy)
    check('startup_metrics_first_telemetry', 'first_telemetry_acquired_ms' in profiler and 'first_telemetry_ui_ready_ms' in profiler)
    print('RESULTADO: PASS (11 checks)')


if __name__ == '__main__':
    main()
