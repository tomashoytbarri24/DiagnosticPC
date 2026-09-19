"""V113 — benchmark principal usa una única configuración extendida."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
from core.version import VERSION


def check(name, cond):
    if not cond:
        raise AssertionError(name)
    print('[PASS]', name)


def main():
    panel=(ROOT/'gui'/'health_center_panel.py').read_text(encoding='utf-8')
    start=panel.index('    def _render_gaming_benchmark_section(self):')
    end=panel.index('    def _format_visual_metric', start)
    bench_view=panel[start:end]
    check('version', VERSION.isdecimal())
    check('extended_only_mode', "text='Modo de ejecución'" in bench_view and 'No se ofrecen perfiles reducidos' in bench_view)
    check('visual_benchmark_rendered_after_mode_info', bench_view.index('profile_shell =') < bench_view.index('self._render_visual_benchmark_card(bench)'))
    check('only_visual_benchmark_exposed', 'self.btn_bench' not in bench_view and 'Selecciona qué componentes' not in bench_view)
    check('main_action_locks_while_running', "self.btn_visual_bench.configure(state='disabled' if 'visual_benchmark' in self._jobs else 'normal')" in panel)
    check('legacy_runner_removed', 'def _run_benchmark(' not in panel)
    print('RESULTADO: PASS')


if __name__=='__main__':
    main()
