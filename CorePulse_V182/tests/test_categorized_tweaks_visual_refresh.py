"""V100 — identidad visual por categoría sin alterar el motor de tweaks."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION
from core.windows_tweaks import CATEGORY_ORDER, catalog


def check(name, cond):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}: {bool(cond)}")
    return bool(cond)


def main():
    panel = (ROOT/'gui'/'windows_tweaks_panel.py').read_text(encoding='utf-8')
    theme = (ROOT/'core'/'theme_manager.py').read_text(encoding='utf-8')
    rows = catalog()
    categories = {row['category'] for row in rows}
    checks = [
        check('version', VERSION.isdecimal()),
        check('catalog_still_78', len(rows) == 78 and len({r['id'] for r in rows}) == 78),
        check('all_categories_still_ordered', categories.issubset(set(CATEGORY_ORDER))),
        check('category_palette_present', 'CATEGORY_VISUALS = {' in panel and 'def category_visual(category):' in panel),
        check('every_category_has_palette_literal', all(repr(c) + ': {' in panel for c in categories)),
        check('colored_category_surface', "bg=visual['surface']" in panel and "highlightbackground=visual['border']" in panel),
        check('accent_bar_present', "bg=visual['accent'], width=5" in panel),
        check('category_counter_present', "AJUSTES" in panel and 'len(rows)' in panel),
        check('rows_inherit_category_tone', "row_bg = visual['row']" in panel and "hover=visual['hover']" in panel),
        check('security_stays_red', "'Seguridad avanzada': {" in panel and "'accent': '#ff5d6c'" in panel),
        check('light_theme_palette_mapped', all(color in theme for color in ('#17182f','#a991ff','#241d0f','#20c997','#20171d'))),
        check('no_tweak_engine_change_in_visual_test', 'apply_tweak(' not in panel and 'undo_tweak(' not in panel),
    ]
    ok = all(checks)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
