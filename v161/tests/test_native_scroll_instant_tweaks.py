"""V100 — regresión del ghosting observado al arrastrar Tweaks."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
from core.version import VERSION

def check(name, cond):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}: {bool(cond)}")
    return bool(cond)

def main():
    scroll=(ROOT/'gui/stable_scroll.py').read_text(encoding='utf-8')
    panel=(ROOT/'gui/windows_tweaks_panel.py').read_text(encoding='utf-8')
    nav=(ROOT/'gui/internal_navigation.py').read_text(encoding='utf-8')
    checks=[
        check('version', VERSION == '103'),
        check('canvas_owns_scroll', 'self.canvas = tk.Canvas(' in scroll and 'yscrollincrement=1' in scroll),
        check('no_negative_place_tree_motion', 'place_configure(y=' not in scroll and '_offset' not in scroll),
        check('scrollbar_is_1_to_1', "if op == 'moveto'" in scroll and 'self.canvas.yview_moveto' in scroll),
        check('wheel_is_direct', 'self.canvas.yview_scroll(amount' in scroll),
        check('windows_repaint_invalidates_children', 'RedrawWindow' in scroll and '0x0080' in scroll),
        check('tweaks_no_progressive_category_after_loop', 'self.frame.after(1, self._build_catalog_step)' not in panel),
        check('tweaks_catalog_finishes_in_one_idle_turn', 'self.frame.after_idle(self._build_catalog_step)' in panel and 'for category, rows in self._catalog_groups:' in panel),
        check('tweak_rows_have_no_ctk_frame_per_row', "row = tk.Frame(" in panel and "row = ctk.CTkFrame(" not in panel),
        check('tweak_checkbox_has_no_ctk_canvas', "text='☐'" in panel and 'self.check_labels' in panel),
        check('tweaks_page_remains_cached', "'tweaks'" in nav.split('CACHEABLE_PAGES',1)[1].split('\n',1)[0]),
    ]
    ok=all(checks)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1

if __name__=='__main__':
    raise SystemExit(main())
