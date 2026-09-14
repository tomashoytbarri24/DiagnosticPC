"""V113 — sidebar sin branding superior y con tarjeta del agente reposicionada."""
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
    dash = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    layout = (ROOT / 'gui' / 'dashboard_layout.py').read_text(encoding='utf-8')
    check('brand_removed_from_sidebar_rebuild', "app._sidebar_brand_title = None" in dash and "app._sidebar_brand_company = None" in dash and "app._sidebar_brand_rule = None" in dash)
    check('monitor_moves_up_after_header_removal', "monitor.pack(fill='x', padx=17, pady=(12, 3))" in dash)
    check('style_does_not_restore_branding', "_cfg(getattr(app, '_sidebar_brand_title', None), text='')" in layout and "_cfg(getattr(app, '_sidebar_brand_company', None), text='')" in layout and "_cfg(getattr(app, '_sidebar_brand_rule', None), height=0)" in layout)
    check('agent_card_not_bottom_anchored', "card.pack(side='top', fill='x', padx=11, pady=(12, 8))" in layout)
    print('RESULTADO: PASS')


if __name__ == '__main__':
    main()
