"""V100 — Gaming vive sólo en Centro de salud > Rendimiento."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION

def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print('[PASS]', name)

def main():
    dashboard = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    layout = (ROOT / 'gui' / 'dashboard_layout.py').read_text(encoding='utf-8')
    sidebar = (ROOT / 'gui' / 'sidebar.py').read_text(encoding='utf-8')
    nav = (ROOT / 'gui' / 'internal_navigation.py').read_text(encoding='utf-8')
    ui = (ROOT / 'gui' / 'ui_consistency.py').read_text(encoding='utf-8')
    health = (ROOT / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')
    main = (ROOT / 'main.py').read_text(encoding='utf-8')

    check('version', VERSION.isdecimal())
    check('gaming_button_not_published', 'app.btn_overlay.pack(' not in dashboard)
    check('gaming_label_removed_from_sidebar', "'btn_overlay': 'Gaming'" not in sidebar)
    check('gaming_icon_removed_from_sidebar_assets', "'btn_overlay': 'overlay.png'" not in dashboard)
    check('sidebar_nav_excludes_gaming', "'btn_overlay': 'Gaming'" not in layout.split('NAV =',1)[1].split('\n',1)[0])
    check('gaming_context_highlights_health_center', "'gaming': 'btn_health_center'" in nav and "'overlay': 'btn_health_center'" in nav)
    check('layout_context_highlights_health_center', "'gaming': 'btn_health_center'" in layout and "'overlay': 'btn_health_center'" in layout)
    check('ui_context_highlights_health_center', "'gaming': 'btn_health_center'" in ui and "'overlay': 'btn_health_center'" in ui)
    check('sidebar_dispatcher_has_no_gaming_route', "'btn_overlay': ('gaming'" not in ui)
    check('health_center_performance_opens_gaming', "getattr(self.app, 'open_gaming'" in health and "('performance')" in health)
    check('gaming_runtime_preserved', 'def open_gaming' in main and 'GamingPanel' in main)
    print('\nRESULTADO: PASS (11 checks)')

if __name__ == '__main__':
    main()
