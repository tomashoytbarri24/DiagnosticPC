"""V113 — retirar branding no debe deformar la navegación ni hundir el agente."""
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
    dashboard = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    layout = (ROOT / 'gui' / 'dashboard_layout.py').read_text(encoding='utf-8')
    check('sidebar_width_unchanged', "width = 210 if compact else 224 if standard else 236" in layout)
    check('branding_stays_removed', "app._sidebar_brand_block = None" in dashboard)
    check('monitor_gets_missing_brand_spacing', "top_gap = 8 if compact else 12 if standard else 14" in layout)
    check('agent_not_forced_to_bottom', "card.pack_configure(side='bottom'" not in layout)
    check('agent_forced_top_after_navigation', "card.pack(side='top', fill='x'" in layout and "current_side != 'top'" in layout)
    print('RESULTADO: PASS')


if __name__ == '__main__':
    main()
