"""Regresión V100 — Sidebar Navigation Hierarchy Polish."""
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
        check('version', VERSION.isdecimal()),
        check('compact_text_identity', "text='CorePulse'" in dash and "text='CEREON TECHNOLOGIES'" in dash),
        check('monitor_top_spacing', "monitor.pack(fill='x', padx=17, pady=(0, 3))" in dash),
        check('responsive_sidebar_width', "width = 210 if compact else 224 if standard else 236" in layout),
        check('agent_compact', 'target_h = 112 if compact else 122 if standard else 126' in layout),
        check('agent_human_state', "'NINGUNA SOSTENIDA': 'Sin alertas sostenidas'" in layout),
        check('agent_theme_version_bottom', "card.pack_configure(side='bottom'" in layout and "ver.pack_configure(side='bottom'" in layout),
        check('logo_never_returns_sidebar', 'app.frame_logo.pack_forget()' in layout),
    ]
    ok=all(checks)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1

if __name__=='__main__':
    raise SystemExit(main())
