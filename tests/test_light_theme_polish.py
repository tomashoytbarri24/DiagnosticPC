"""Regresión V0.10.0.0w: modo claro completo y sidebar balanceado."""
from pathlib import Path
import sys, tempfile
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
from core.version import VERSION
import core.theme_manager as tm

def check(name, value):
    print(f"[{'PASS' if value else 'FAIL'}] {name}: {bool(value)}")
    return bool(value)

def main():
    nav=(ROOT/'gui'/'internal_navigation.py').read_text(encoding='utf-8')
    dash=(ROOT/'gui'/'dashboard.py').read_text(encoding='utf-8')
    layout=(ROOT/'gui'/'dashboard_layout.py').read_text(encoding='utf-8')
    trends=(ROOT/'gui'/'session_trends_panel.py').read_text(encoding='utf-8')
    old=tm._THEME_FILE
    try:
        with tempfile.TemporaryDirectory() as td:
            tm._THEME_FILE=Path(td)/'ui_theme.json'
            tm.set_theme(tm.LIGHT)
            light_inner=tm.color('#0a1422')
            light_card2=tm.color('#0a1524')
            light_alt=tm.color('#0e1d2f')
            grid=tm.color('#334155')
    finally:
        tm._THEME_FILE=old
    results=[
        check('version', VERSION=='0.10.0.0w'),
        check('inner_surface_is_light', light_inner.lower() in {'#e9edf2','#e8edf2','#f2f4f7'}),
        check('card2_surface_is_light', light_card2.lower() in {'#e9edf2','#e8edf2','#f2f4f7'}),
        check('secondary_surface_is_light', light_alt.lower() in {'#d9e3ec','#e8edf2','#e9edf2','#f2f4f7'}),
        check('chart_grid_is_light', grid.lower()=='#c5ced8'),
        check('trends_grid_uses_theme', "color=theme_color('#334155')" in trends),
        check('build_host_offscreen', "host.place(x=-20000" in nav),
        check('atomic_host_publish', 'host.place_configure(x=0, y=0' in nav),
        check('header_brand_symbol', 'size=(46, 46)' in dash and '_header_brand_icon' in dash),
        check('sidebar_brand_removed', "_safe_pack_forget(app.frame_logo)" in dash),
        check('agent_card_has_room', 'height=154' in layout and 'target_h = 138 if compact else 154 if standard else 160' in layout),
        check('agent_detail_not_clipped', "height=24 if compact else 28" in layout and "anchor='nw'" in layout),
        check('theme_button_aligned_with_agent', "theme_button.pack(side='bottom', fill='x', padx=12" in layout),
    ]
    ok=all(results)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1

if __name__=='__main__':
    raise SystemExit(main())
