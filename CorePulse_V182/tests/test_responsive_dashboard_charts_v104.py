"""V104 — gráficos del Resumen deben conservar geometría responsiva y legible."""
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
    dashboard = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    layout = (ROOT / 'gui' / 'dashboard_layout.py').read_text(encoding='utf-8')

    check('version', VERSION.isdecimal())
    check('stage', bool(STAGE))
    check('charts_canvas_uses_fill_both', "canvas_widget.pack(fill='both', expand=True" in main_py)
    check('dashboard_delegates_chart_geometry', 'from gui.dashboard_layout import request_chart_reflow' in dashboard)
    check('layout_has_dynamic_chart_height', 'def _chart_target_height_for(app, mode):' in layout)
    check('layout_has_reflow_entrypoint', 'def request_chart_reflow(app, redraw=True):' in layout)
    check('frame_charts_reflow_binding', "app.frame_charts.bind('<Configure>', on_frame_configure, add='+')" in layout)
    check('chart_ticks_are_dynamic', 'def _chart_tick_positions(total_points):' in layout)
    check('legacy_fixed_206_removed_from_dashboard', 'canvas_widget.configure(height=206)' not in dashboard)
    print('\nRESULTADO: PASS')


if __name__ == '__main__':
    main()
