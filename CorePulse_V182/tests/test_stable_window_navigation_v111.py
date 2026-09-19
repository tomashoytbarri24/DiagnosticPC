"""V111 — estabilidad visual durante resize, move y navegación interna."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION, STAGE


def check(name, cond):
    if not cond:
        raise AssertionError(name)
    print('[PASS]', name)


def main():
    layout = (ROOT/'gui'/'dashboard_layout.py').read_text(encoding='utf-8')
    nav = (ROOT/'gui'/'internal_navigation.py').read_text(encoding='utf-8')
    overlay = (ROOT/'gui'/'overlay_config_panel.py').read_text(encoding='utf-8')
    main_src = (ROOT/'main.py').read_text(encoding='utf-8')
    health = (ROOT/'gui'/'health_center_panel.py').read_text(encoding='utf-8')
    alerts = (ROOT/'gui'/'alert_panel.py').read_text(encoding='utf-8')

    check('version', VERSION.isdecimal())
    check('stage', bool(STAGE))
    check('resize_debounce_fast', 'RESIZE_DEBOUNCE_MS = 85' in layout)
    check('same_breakpoint_fast_path', "if (not force) and (not mode_changed):" in layout)
    check('hidden_dashboard_skips_resize_restyle', "if getattr(app, '_active_internal_page', None):" in layout and '_dashboard_layout_sync_pending' in layout)
    check('move_does_not_reflow', 'if previous_size == size:' in layout and 'return' in layout.split('if previous_size == size:',1)[1][:100])
    check('charts_do_not_fight_live_resize', "if getattr(app, 'is_resizing', False)" in layout and '_chart_reflow_pending' in layout)
    check('first_page_keeps_previous_visible', '_show_navigation_transition(app, page_key)' not in nav.split('def request_navigation',1)[1].split('def _pending',1)[0])
    check('new_page_still_builds_offscreen', "host.place(x=-20000" in nav)
    check('cached_page_uses_place_forget', 'host.place_forget()' in nav)
    check('dashboard_return_deferred_sync', 'request_stable_layout_sync' in nav and 'after_idle' in nav.split('def show_dashboard',1)[1])
    check('overlay_resize_coalesced', '_responsive_after_id' in overlay and 'self.root.after(70, self._apply_responsive_layout)' in overlay)
    check('active_page_gets_single_settled_resize', 'notify_active_page_geometry' in nav and 'on_viewport_settled' in overlay and 'notify_active_page_geometry(app)' in layout)
    check('navigation_import_prewarm', 'def _prewarm_navigation_modules(self):' in main_src and 'CorePulse-NavigationPrewarm' in main_src)
    check('health_cached_return_does_not_force_rebuild', 'if battery_changed:' in health and 'Los jobs asíncronos ya solicitan render' in health)
    check('alerts_skip_identical_rebuild', '_last_render_signature' in alerts and 'signature == self._last_render_signature' in alerts)
    print('\nRESULTADO: PASS')


if __name__ == '__main__':
    main()
