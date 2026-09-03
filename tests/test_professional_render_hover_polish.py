from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
from core.version import VERSION, STAGE


def check(name, cond):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}: {bool(cond)}")
    return bool(cond)


def main():
    nav=(ROOT/'gui'/'internal_navigation.py').read_text(encoding='utf-8')
    polish=(ROOT/'gui'/'render_polish.py').read_text(encoding='utf-8')
    ui=(ROOT/'gui'/'ui_consistency.py').read_text(encoding='utf-8')
    dash=(ROOT/'gui'/'dashboard.py').read_text(encoding='utf-8')
    tweaks=(ROOT/'gui'/'windows_tweaks_panel.py').read_text(encoding='utf-8')
    theme=(ROOT/'core'/'theme_manager.py').read_text(encoding='utf-8')
    checks=[
        check('version', VERSION=='0.10.0.0w'),
        check('stage', STAGE=='HEALTH_INTELLIGENCE_RECOVERY'),
        check('no_fullscreen_transition_loader', "transition = None" in nav and "Cargando vista…" not in nav),
        check('offscreen_atomic_build_preserved', "x=-20000" in nav and "host.place_configure(x=0" in nav),
        check('busy_cursor_feedback', "cursor='watch'" in nav and "cursor=''" in nav),
        check('light_corner_normalizer', 'LIGHT_CARD_RADIUS = 9' in polish and 'polish_widget_tree' in polish),
        check('polish_applied_before_commit', 'polish_widget_tree(host)' in nav),
        check('sidebar_hover_feedback', 'hover_color=ACTIVE_HOVER if active else HOVER' in ui),
        check('hover_contrast_strengthened', "'#0e1d2f': '#d9e3ec'" in theme),
        check('card_hover_pointer_guard', 'inside_root()' in dash and 'root.after(12, finalize_leave)' in dash),
        check('tweak_row_hover', '_bind_row_hover' in tweaks and 'row.configure(fg_color=hover)' in tweaks),
        check('dashboard_single_visible_redraw', 'Un solo draw síncrono' in nav),
    ]
    ok=all(checks)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1

if __name__=='__main__':
    raise SystemExit(main())
