"""V113 — gráficos del Resumen deben verse encuadrados y con eje Y visible por gráfico."""
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
    dashboard = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    layout = (ROOT / 'gui' / 'dashboard_layout.py').read_text(encoding='utf-8')
    check('subplots_spacing_increased', 'left=0.048, right=0.985, top=0.84, bottom=0.24, wspace=0.24' in main_py and 'left=0.048, right=0.985, top=0.84, bottom=0.24, wspace=0.24' in layout)
    check('individual_y_axes_enabled', "labelleft=True" in dashboard and "labelleft=True" in layout)
    check('zero_y_tick_removed', "set_yticks([25, 50, 75, 100])" in main_py and "set_yticks([25, 50, 75, 100])" in dashboard and "set_yticks([25, 50, 75, 100])" in layout)
    check('chart_frames_enabled', "for side, spine in ax.spines.items():" in main_py and "for side, spine in ax.spines.items():" in dashboard and "for side, spine in ax.spines.items():" in layout)
    check('axis_padding_improved', "pad=10" in main_py and "pad=10, labelleft=True" in dashboard and "pad=10, labelleft=True" in layout)
    print('RESULTADO: PASS')


if __name__ == '__main__':
    main()
