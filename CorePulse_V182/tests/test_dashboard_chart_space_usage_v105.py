"""V105 — las tendencias deben usar una fracción sustancial del viewport."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from core.version import VERSION

def check(name, cond):
    if not cond: raise AssertionError(name)
    print('[PASS]', name)

def main():
    layout=(ROOT/'gui'/'dashboard_layout.py').read_text(encoding='utf-8')
    main_py=(ROOT/'main.py').read_text(encoding='utf-8')
    check('version', VERSION.isdecimal())
    check('chart_height_uses_viewport_ratio', "ratio = 0.31 if mode == 'compact' else 0.35 if mode == 'standard' else 0.38" in layout)
    check('standard_chart_minimum_300', "minimum = 258 if mode == 'compact' else 300" in layout)
    check('large_chart_can_reach_440', "maximum = 330 if mode == 'compact' else 390 if mode == 'standard' else 440" in layout)
    check('storage_uses_real_content_height', 'content_host.winfo_reqheight()' in layout)
    check('figure_uses_more_vertical_area', 'top=0.90, bottom=0.16' in layout)
    check('line_width_increased', 'linewidth=2.6' in main_py)
    check('percentage_scale_preserved', 'ax.set_ylim(0, 100)' in layout)
    print('RESULTADO: PASS')

if __name__=='__main__': main()
