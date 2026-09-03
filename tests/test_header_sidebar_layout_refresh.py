"""Regresión V0.10.0.0w — Header & Sidebar Layout Refresh."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
from core.version import VERSION, STAGE

def check(name, value):
    print(f"[{'PASS' if value else 'FAIL'}] {name}: {bool(value)}")
    return bool(value)

def main():
    dash=(ROOT/'gui'/'dashboard.py').read_text(encoding='utf-8')
    layout=(ROOT/'gui'/'dashboard_layout.py').read_text(encoding='utf-8')
    checks=[
        check('version', VERSION=='0.10.0.0w'),
        check('stage', STAGE=='HEALTH_INTELLIGENCE_RECOVERY'),
        check('sidebar_logo_not_packed', '_safe_pack_forget(app.frame_logo)' in dash),
        check('navigation_starts_near_top', "monitor.pack(fill='x', padx=20, pady=(4, 4))" in dash),
        check('header_has_brand_icon', '_header_brand_icon' in dash and 'size=(46, 46)' in dash),
        check('header_identity_left_aligned', "anchor='w'" in dash and "justify='left'" in dash),
        check('responsive_does_not_remount_logo', 'app.frame_logo.pack_forget()' in layout),
        check('agent_standard_height_154', 'target_h = 138 if compact else 154 if standard else 160' in layout),
        check('agent_detail_always_visible', "app._agent_detail.grid(sticky='nsew')" in layout),
        check('theme_toggle_kept', '_theme_toggle_button' in dash and 'theme_action_label()' in dash),
    ]
    ok=all(checks)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1

if __name__=='__main__':
    raise SystemExit(main())
