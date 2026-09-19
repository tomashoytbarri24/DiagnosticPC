"""V0.10.2.60w — Summary Trend Charts Cleanup geometry regression."""
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
    dashboard = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    main_py = (ROOT / 'main.py').read_text(encoding='utf-8')
    check('version', VERSION.isdecimal())
    check('exe_runtime_stage_preserved', bool(STAGE))
    check('geometry_helper_exists', 'def _apply_chart_geometry_alignment(app):' in dashboard)
    check('equal_centers', "centers = (1.0 / 6.0, 0.5, 5.0 / 6.0)" in dashboard)
    check('equal_axis_width', 'width = 0.272' in dashboard)
    check('taller_plot_area', 'height = 0.72' in dashboard)
    check('explicit_axis_position', 'ax.set_position([left, bottom, width, height])' in dashboard)
    check('canvas_taller', 'canvas_widget.configure(height=206)' in dashboard)
    check('initial_geometry_symmetric', "(1.0/6.0, 0.5, 5.0/6.0)" in main_py)
    check('chart_blitting_preserved', 'self.canvas.blit(self.fig.bbox)' in main_py)
    print('\nRESULTADO: PASS (10 checks)')


if __name__ == '__main__':
    main()
