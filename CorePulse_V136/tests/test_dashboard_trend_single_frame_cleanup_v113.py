"""V113 — cleanup visual de tendencias: sin doble marco raro y sin usar más alto superior."""
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
    check('no_extra_patch_calls', "app._refresh_trend_chart_frames()" not in layout and "app._refresh_trend_chart_frames()" not in dashboard)
    check('helper_is_noop_compat', 'Compatibilidad: ya no dibujamos parches extra' in main_py)
    check('chart_facecolor_soft', "#0f1827" in main_py and "#0f1827" in layout and "#0f1827" in dashboard)
    check('spacing_without_more_top_space', 'left=0.052, right=0.985, top=0.86, bottom=0.22, wspace=0.18' in main_py and 'left=0.052, right=0.985, top=0.86, bottom=0.22, wspace=0.18' in layout)
    check('tick_padding_tightened', 'pad=6' in main_py and 'pad=6' in layout and 'pad=6' in dashboard)
    print('RESULTADO: PASS')


if __name__ == '__main__':
    main()
