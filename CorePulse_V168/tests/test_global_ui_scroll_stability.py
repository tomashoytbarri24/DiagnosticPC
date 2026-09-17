"""Cobertura de infraestructura visual/scroll global V100."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION, STAGE


def check(name, condition):
    print(f"[{'PASS' if condition else 'FAIL'}] {name}: {bool(condition)}")
    return bool(condition)


def main():
    scroll = (ROOT/'gui/stable_scroll.py').read_text(encoding='utf-8')
    nav = (ROOT/'gui/internal_navigation.py').read_text(encoding='utf-8')
    tweaks = (ROOT/'gui/windows_tweaks_panel.py').read_text(encoding='utf-8')
    network = (ROOT/'gui/network_detail_panel.py').read_text(encoding='utf-8')
    targets = [
        'cpu_detail_panel.py', 'gpu_detail_panel.py', 'ram_detail_panel.py',
        'network_detail_panel.py', 'windows_tweaks_panel.py',
        'telemetry_detail_panel.py', 'alert_panel.py', 'alert_history_panel.py',
        'session_trends_panel.py',
    ]
    texts = {name:(ROOT/'gui'/name).read_text(encoding='utf-8') for name in targets}
    results = [
        check('version', VERSION == '103'),
        check('stage', STAGE == 'STARTUP_RESPONSIVENESS_SINGLE_LAYOUT_AUTHORITY'),
        check('stable_scroll_uses_native_canvas_viewport', 'self.canvas = tk.Canvas(' in scroll and 'self.canvas.create_window' in scroll),
        check('local_pointer_wheel_routing', '_contains_root_point' in scroll and '_WheelRouter' in scroll),
        check('geometry_is_debounced', '_schedule_geometry' in scroll and 'self.after(max(0, int(delay_ms))' in scroll),
        check('scroll_defers_heavy_repaint', 'defer_until_idle' in scroll and '_idle_callbacks' in scroll),
        check('all_large_internal_panels_migrated', all('StableScrollHost' in t for t in texts.values())),
        check('no_large_internal_ctk_scrollableframe', all('CTkScrollableFrame(' not in t for t in texts.values())),
        check('single_canvas_window_is_intentional', 'self._window_item = self.canvas.create_window' in scroll and 'window=self.content' in scroll),
        check('wheel_is_direct_without_motion_queue', 'self.canvas.yview_scroll(amount' in scroll and '_pending_wheel_px' not in scroll),
        check('scroll_has_no_content_interpolation', 'math.exp(' not in scroll and '_target_offset' not in scroll),
        check('tweaks_defers_66_row_status_repaint', 'host.defer_until_idle(finish)' in tweaks),
        check('network_does_not_repaint_speed_section_while_scroll', 'if not self._is_scrolling()' in network and 'self._apply_speed_test()' in network),
        check('page_transition_is_atomic_without_flash', '_show_navigation_transition' in nav and "text='Preparando vista…'" in nav),
        check('transition_destroyed_on_commit', '_clear_navigation_transition(app)' in nav and 'host.lift()' in nav),
        check('dashboard_tkagg_async_redraw', 'def _redraw_dashboard(app):' in nav and 'canvas.draw_idle()' in nav),
        check('dashboard_no_sync_draw_block', '            canvas.draw()' not in nav.split('def _redraw_dashboard',1)[1].split('def show_dashboard',1)[0]),
    ]
    ok=all(results)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1

if __name__=='__main__':
    raise SystemExit(main())
