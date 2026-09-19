"""V100: Rendimiento y Overlay viven dentro del nuevo hub Gaming."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION


def check(name, condition):
    ok = bool(condition)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {ok}")
    return ok


def main():
    main_src = (ROOT / 'main.py').read_text(encoding='utf-8')
    health = (ROOT / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')
    gaming = (ROOT / 'gui' / 'gaming_panel.py').read_text(encoding='utf-8')
    sidebar = (ROOT / 'gui' / 'sidebar.py').read_text(encoding='utf-8')
    ui = (ROOT / 'gui' / 'ui_consistency.py').read_text(encoding='utf-8')
    nav = (ROOT / 'gui' / 'internal_navigation.py').read_text(encoding='utf-8')

    health_tabs = health.split('    TABS = (', 1)[1].split('    )', 1)[0]
    results = [
        check('version', VERSION.isdecimal()),
        check('gaming_removed_from_sidebar', "'btn_overlay': 'Gaming'" not in sidebar),
        check('health_tabs_no_performance', "('performance', 'Rendimiento')" not in health_tabs),
        check('health_quick_action_routes_to_gaming', "getattr(self.app, 'open_gaming'" in health),
        check('gaming_keeps_route_contract', "TABS = (('performance', 'Rendimiento'), ('overlay', 'Overlay'))" in gaming),
        check('gaming_embeds_performance', 'performance_only=True' in gaming and 'external_scroll=scroll' in gaming),
        check('gaming_embeds_overlay', 'OverlayConfigPanel(overlay_body, self.app)' in gaming),
        check('main_has_gaming_route', "def open_gaming(self, tab='performance')" in main_src and "activate_internal_page(self, 'gaming')" in main_src),
        check('overlay_compat_routes_inside_gaming', "self.open_gaming('overlay')" in main_src),
        check('sidebar_no_longer_dispatches_gaming', "'btn_overlay': ('gaming', lambda: app.open_gaming('performance'))" not in ui),
        check('internal_navigation_keeps_gaming_and_highlights_health_center', "'gaming': 'gaming_panel'" in nav and "'gaming': 'btn_health_center'" in nav and "'overlay': 'btn_health_center'" in nav),
    ]
    ok = all(results)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
