"""Regresión V0.10.0.0w — Sidebar Alignment & Agent Polish."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
from core.version import VERSION

def check(name, value):
    print(f"[{'PASS' if value else 'FAIL'}] {name}: {bool(value)}")
    return bool(value)

def main():
    dash=(ROOT/'gui'/'dashboard.py').read_text(encoding='utf-8')
    layout=(ROOT/'gui'/'dashboard_layout.py').read_text(encoding='utf-8')
    checks=[
        check('version', VERSION=='0.10.0.0w'),
        check('monitor_top_spacing', "pady=(4, 4)" in dash),
        check('header_identity_reference', 'app._header_identity = identity' in dash),
        check('header_shifted_right', "identity.pack(side='left', fill='both', expand=True, padx=(34, 18))" in dash),
        check('responsive_header_offset', "left_pad = 18 if compact else 28 if mode == 'standard' else 36" in layout),
        check('agent_taller', 'target_h = 138 if compact else 154 if standard else 160' in layout),
        check('agent_multiline_detail', "height=24 if compact else 28" in layout and "anchor='nw'" in layout),
        check('agent_theme_version_bottom', "card.pack_configure(side='bottom'" in layout and "ver.pack_configure(side='bottom'" in layout),
        check('logo_never_returns_sidebar', 'app.frame_logo.pack_forget()' in layout),
    ]
    ok=all(checks)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1

if __name__=='__main__':
    raise SystemExit(main())
