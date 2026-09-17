"""V113 — Benchmark es una página principal independiente, fuera de Gaming/Diagnóstico."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def check(name, cond):
    if not cond:
        raise AssertionError(name)
    print('[PASS]', name)


def main():
    main_py=(ROOT/'main.py').read_text(encoding='utf-8')
    dash=(ROOT/'gui'/'dashboard.py').read_text(encoding='utf-8')
    nav=(ROOT/'gui'/'internal_navigation.py').read_text(encoding='utf-8')
    ui=(ROOT/'gui'/'ui_consistency.py').read_text(encoding='utf-8')
    health=(ROOT/'gui'/'health_center_panel.py').read_text(encoding='utf-8')
    gaming=(ROOT/'gui'/'gaming_panel.py').read_text(encoding='utf-8')
    page=(ROOT/'gui'/'benchmark_panel.py').read_text(encoding='utf-8')

    check('main_button_exists', "self.btn_benchmark = ctk.CTkButton" in main_py and "text='Benchmark'" in main_py)
    check('button_published_before_diagnostic_section', dash.index("app.btn_benchmark.pack") < dash.index("diagnosis = _section_label(app.sidebar, 'DIAGNÓSTICO')"))
    check('dedicated_route', "'benchmark': 'btn_benchmark'" in nav and "'benchmark': 'benchmark_panel'" in nav)
    check('sidebar_dispatcher', "'btn_benchmark': ('benchmark', lambda: app.open_benchmark())" in ui)
    check('dedicated_open_method', 'def open_benchmark(self):' in main_py and 'from gui.benchmark_panel import BenchmarkPanel' in main_py)
    check('page_is_benchmark_only', 'benchmark_only=True' in page and "title='Benchmark'" in page)
    check('gaming_nav_has_no_benchmark_card', "('benchmark', 'Benchmark 3D'" not in health)
    check('gaming_home_has_no_benchmark_shortcut', "('Benchmark 3D', 'Ejecuta la escena gráfica" not in health)
    check('gaming_stability_has_no_benchmark_launcher', "lambda: self._select_performance_section('benchmark')" not in health)
    check('gaming_router_has_no_benchmark_branch', "elif section == 'benchmark':" not in health)
    check('gaming_copy_no_longer_claims_benchmark', 'throttling y benchmark con evidencia real' not in gaming)
    print('RESULTADO: PASS')


if __name__=='__main__':
    main()
