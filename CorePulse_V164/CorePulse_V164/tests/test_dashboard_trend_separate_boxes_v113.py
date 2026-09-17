"""V113 — tendencias deben verse como 3 gráficos encuadrados sin usar más alto superior."""
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
    layout = (ROOT / 'gui' / 'dashboard_layout.py').read_text(encoding='utf-8')
    dashboard = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    check('individual_chart_frames_helper', 'def _refresh_trend_chart_frames(self):' in main_py)
    check('chart_frame_patch_added', 'FancyBboxPatch' in main_py and 'fig.add_artist(patch)' in main_py)
    check('tick_positions_shifted_from_origin', 'positions = [1, round(last * 0.28), round(last * 0.56), round(last * 0.80), last]' in layout and 'ticks = [1, round(last * 0.28), round(last * 0.56), round(last * 0.80), last]' in main_py)
    check('frame_refresh_called_on_style', "app._refresh_trend_chart_frames()" in layout and "app._refresh_trend_chart_frames()" in dashboard)
    check('no_extra_top_space_used', 'top=0.84, bottom=0.24' in main_py and 'top=0.84, bottom=0.24' in layout)
    print('RESULTADO: PASS')


if __name__ == '__main__':
    main()
