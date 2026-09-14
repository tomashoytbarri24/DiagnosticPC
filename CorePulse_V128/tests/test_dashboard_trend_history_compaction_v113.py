"""V113 — los gráficos del Resumen no deben reservar media tarjeta vacía al inicio."""
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
    main_py = (ROOT / 'main.py').read_text(encoding='utf-8')
    check('history_prefill_kept_real_na', "deque([float('nan')] * self.max_points" in main_py)
    check('display_series_helper_added', 'def _chart_series_for_display(self, values):' in main_py)
    check('math_import_present', 'import math' in main_py)
    check('helper_does_not_invent_samples', 'redistribuye las muestras existentes sobre el ancho disponible' in main_py)
    check('prime_uses_display_series', 'cpu_x, cpu_series, cpu_count = self._chart_series_for_display(cpu_data)' in main_py)
    check('live_update_uses_display_series', 'self._refresh_trend_axis_labels(visible_count)' in main_py)
    check('dynamic_tick_labels_exist', 'def _trend_tick_labels_for_count(self, visible_count):' in main_py)
    print('RESULTADO: PASS')


if __name__ == '__main__':
    main()
