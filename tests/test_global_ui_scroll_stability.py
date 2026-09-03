"""Cobertura de infraestructura visual/scroll global V0.10.0.0w."""
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
        check('version', VERSION == '0.10.0.0w'),
        check('stage', STAGE == 'HEALTH_INTELLIGENCE_RECOVERY'),
        check('stable_scroll_uses_native_clipped_viewport', "tk.Frame(self, bg=self._bg" in scroll and "content.place(x=0, y=0, relwidth=1.0)" in scroll),
        check('local_pointer_wheel_routing', '_contains_root_point' in scroll and '_WheelRouter' in scroll),
        check('geometry_is_debounced', '_schedule_geometry' in scroll and 'after(int(delay_ms)' in scroll),
        check('scroll_defers_heavy_repaint', 'defer_until_idle' in scroll and '_idle_callbacks' in scroll),
        check('all_large_internal_panels_migrated', all('StableScrollHost' in t for t in texts.values())),
        check('no_large_internal_ctk_scrollableframe', all('CTkScrollableFrame(' not in t for t in texts.values())),
        check('no_canvas_create_window', 'self.canvas = tk.Canvas' not in scroll and 'self.canvas.create_window' not in scroll),
        check('wheel_is_frame_limited', 'self.after(16, self._flush_motion)' in scroll),
        check('tweaks_defers_66_row_status_repaint', 'host.defer_until_idle(finish)' in tweaks),
        check('network_does_not_repaint_speed_section_while_scroll', 'if not self._is_scrolling()' in network and 'self._apply_speed_test()' in network),
        check('page_transition_is_atomic_without_flash', 'transition = None' in nav and "text='Cargando vista…'" not in nav),
        check('transition_destroyed_on_commit', "transition = pending.get('transition')" in nav and 'transition.destroy()' in nav),
        check('dashboard_tkagg_forced_redraw', 'def _redraw_dashboard(app):' in nav and 'canvas.draw()' in nav),
        check('dashboard_single_visible_repaint', 'Un solo draw síncrono' in nav and 'draw_idle' in nav),
    ]
    ok=all(results)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1

if __name__=='__main__':
    raise SystemExit(main())
