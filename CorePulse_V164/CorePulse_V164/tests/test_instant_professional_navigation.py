"""V100 — navegación primaria instantánea, cacheada y sin page-stale flash."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION
from gui.high_refresh import DEFAULT_NAVIGATION_DEBOUNCE_MS


def check(name, condition):
    ok = bool(condition)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {ok}")
    return ok


def main():
    nav = (ROOT / 'gui' / 'internal_navigation.py').read_text(encoding='utf-8')
    main_src = (ROOT / 'main.py').read_text(encoding='utf-8')
    network = (ROOT / 'gui' / 'network_detail_panel.py').read_text(encoding='utf-8')
    health = (ROOT / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')
    diagnostic = (ROOT / 'gui' / 'diagnostic_view.py').read_text(encoding='utf-8')
    cleaning = (ROOT / 'gui' / 'cleaning_center.py').read_text(encoding='utf-8')

    top_level = {'gaming', 'diagnostic', 'health_center', 'cleanup', 'tweaks', 'network', 'alerts', 'trends', 'history'}
    cache_decl = nav.split('CACHEABLE_PAGES = {', 1)[1].split('}', 1)[0]

    commit_pos = main_src.find("commit_internal_page(self, 'history'")
    history_load_pos = main_src.find('rows = self.alert_history_store.refresh()', commit_pos)
    trends_commit_pos = main_src.find("commit_internal_page(self, 'trends'")
    trends_load_pos = main_src.find('sessions = self.session_trend_collector.load_sessions', trends_commit_pos)
    alerts_commit_pos = main_src.find("commit_internal_page(self, 'alerts'")
    alerts_render_pos = main_src.find('panel.render(state, diagnostic)', alerts_commit_pos)

    checks = [
        check('version', VERSION == '103'),
        check('navigation_debounce_near_instant', DEFAULT_NAVIGATION_DEBOUNCE_MS <= 4),
        check('all_primary_pages_cached', all(repr(key) in cache_decl for key in top_level)),
        check('first_load_has_corepulse_transition_surface', '_show_navigation_transition' in nav and "text='Preparando vista…'" in nav),
        check('cached_pages_skip_transition', 'cached = _is_cached(app, page_key)' in nav and '_clear_navigation_transition(app)' in nav),
        check('cached_hosts_are_unmapped_not_dragged_offscreen', 'host.place_forget()' in nav and 'x=-20000' not in nav.split('def _retire_page', 1)[1].split('def clear_internal_page', 1)[0]),
        check('dashboard_does_not_force_sync_matplotlib_draw', '            canvas.draw()' not in nav.split('def _redraw_dashboard', 1)[1].split('def show_dashboard', 1)[0] and 'canvas.draw_idle()' in nav),
        check('cached_refresh_is_deferred', 'self._defer_ui_call(self.health_center_panel.refresh)' in main_src and 'self._defer_ui_call(self.network_detail_panel.refresh)' in main_src and 'self._defer_ui_call(self.windows_tweaks_panel.refresh)' in main_src),
        check('history_shell_commits_before_io', commit_pos >= 0 and history_load_pos > commit_pos),
        check('trends_shell_commits_before_io', trends_commit_pos >= 0 and trends_load_pos > trends_commit_pos),
        check('alerts_shell_commits_before_render', alerts_commit_pos >= 0 and alerts_render_pos > alerts_commit_pos),
        check('network_runtime_starts_after_idle', 'self.frame.after_idle(self._start_runtime)' in network and 'def set_active(self, active):' in network),
        check('health_first_frame_precedes_refresh', 'self._render()' in health and 'self.frame.after_idle(self.refresh)' in health),
        check('diagnostic_back_preserves_cache', "def close(self):\n        \"\"\"Volver al monitoreo conserva la vista" in diagnostic),
        check('cleanup_back_preserves_cache', 'Vuelve al Dashboard conservando el centro para reapertura inmediata' in cleaning),
    ]
    ok = all(checks)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
