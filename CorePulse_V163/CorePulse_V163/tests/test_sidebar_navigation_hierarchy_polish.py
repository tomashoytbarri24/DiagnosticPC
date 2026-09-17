"""V100 — jerarquía visual y densidad del sidebar profesional."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from core.version import VERSION

def check(name, value):
    print(f"[{'PASS' if value else 'FAIL'}] {name}: {bool(value)}")
    return bool(value)

def main():
    dash=(ROOT/'gui'/'dashboard.py').read_text(encoding='utf-8')
    layout=(ROOT/'gui'/'dashboard_layout.py').read_text(encoding='utf-8')
    consistency=(ROOT/'gui'/'ui_consistency.py').read_text(encoding='utf-8')
    checks=[
        check('version', VERSION == '103'),
        check('brand_is_text_only', "text='CorePulse'" in dash and "text='CEREON TECHNOLOGIES'" in dash and '_safe_pack_forget(app.frame_logo)' in dash),
        check('sidebar_is_narrower', 'width=224' in dash and '210 if compact else 224 if standard else 236' in layout),
        check('active_nav_is_subtle', "SIDEBAR_ACTIVE_BG = theme_color('#0c2941')" in dash and 'border_width=1 if active else 0' in dash),
        check('active_nav_uses_accent_text', "text_color=COLORS['primary'] if active else SIDEBAR_INACTIVE_TEXT" in dash),
        check('state_refresh_matches_visual', "ACTIVE_BG = theme_color('#0c2941')" in consistency and 'border_width=1 if active else 0' in consistency),
        check('agent_is_compact', "text='ESTADO DEL AGENTE'" in layout and 'height=122' in layout),
        check('agent_copy_is_human', "'NINGUNA SOSTENIDA': 'Sin alertas sostenidas'" in layout and "'EVALUANDO': 'Evaluando evidencia'" in layout),
        check('internal_compliance_label_removed', 'RF/RNF Compliance' not in dash and "Cereon Technologies" in dash),
        check('theme_toggle_is_quiet', "fg_color='transparent'" in dash and "border_color=COLORS['border']" in dash),
    ]
    ok=all(checks)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1

if __name__=='__main__':
    raise SystemExit(main())
