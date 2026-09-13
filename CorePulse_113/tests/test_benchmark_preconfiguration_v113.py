"""V113 — benchmark debe configurarse antes de ejecutar."""
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
    panel = (ROOT / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')
    start = panel.index('    def _render_gaming_benchmark_section(self):')
    end = panel.index('    def _render_gaming_library_section(self):', start)
    bench_view = panel[start:end]
    check('version', VERSION == '113')
    check('stage', STAGE == 'BENCHMARK_PRECONFIGURATION_FLOW')
    check('stability_opens_config', "benchmark, 'Configurar'" in panel and "lambda: self._select_performance_section('benchmark')" in panel)
    check('no_direct_execute_from_stability', "benchmark, 'Ejecutar',\n                self._run_benchmark" not in panel)
    check('profile_before_execute', bench_view.index("text='1'") < bench_view.index("self.btn_bench = self._button("))
    check('components_before_execute', bench_view.index("text='2'") < bench_view.index("self.btn_bench = self._button("))
    check('action_state_guard', 'def _refresh_benchmark_action_state(self):' in panel and "state='normal' if selected else 'disabled'" in panel)
    check('controls_locked_while_running', "profile_selector.configure(state='disabled' if bench_running else 'normal')" in panel and "switch.configure(state='disabled' if bench_running else 'normal')" in panel)
    print('RESULTADO: PASS')

if __name__ == '__main__':
    main()
