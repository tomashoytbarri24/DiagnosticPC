"""V100 — interacción adaptativa para pantallas de alta frecuencia."""
from __future__ import annotations

import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION
from gui.high_refresh import get_ui_refresh_policy, DEFAULT_NAVIGATION_DEBOUNCE_MS


def check(name, condition):
    print(f"[{'PASS' if condition else 'FAIL'}] {name}: {bool(condition)}")
    return bool(condition)


def main():
    scroll = (ROOT/'gui/stable_scroll.py').read_text(encoding='utf-8')
    nav = (ROOT/'gui/internal_navigation.py').read_text(encoding='utf-8')
    gaming = (ROOT/'gui/gaming_panel.py').read_text(encoding='utf-8')
    health = (ROOT/'gui/health_center_panel.py').read_text(encoding='utf-8')
    overlay = (ROOT/'gui/overlay_config_panel.py').read_text(encoding='utf-8')

    old = os.environ.get('COREPULSE_UI_HZ')
    try:
        os.environ['COREPULSE_UI_HZ'] = '240'
        policy_240 = get_ui_refresh_policy()
        os.environ['COREPULSE_UI_HZ'] = '60'
        policy_60 = get_ui_refresh_policy()
    finally:
        if old is None:
            os.environ.pop('COREPULSE_UI_HZ', None)
        else:
            os.environ['COREPULSE_UI_HZ'] = old

    results = [
        check('version', VERSION == '103'),
        check('240hz_display_caps_ctk_at_120hz', policy_240.display_hz == 240 and policy_240.target_hz == 120 and policy_240.frame_ms == 8),
        check('60hz_preserves_low_cost_interval', policy_60.target_hz == 60 and policy_60.frame_ms == 16),
        check('no_busy_loop_when_idle', '_repaint_after' in scroll and 'self.after(delay, self._flush_repaint)' in scroll),
        check('scroll_is_direct_not_interpolated', 'math.exp(' not in scroll and '_target_offset' not in scroll),
        check('scrollbar_and_wheel_move_canvas_immediately', 'self.canvas.yview_moveto' in scroll and 'self.canvas.yview_scroll(amount' in scroll),
        check('navigation_latency_reduced', DEFAULT_NAVIGATION_DEBOUNCE_MS <= 20 and 'DEFAULT_NAVIGATION_DEBOUNCE_MS' in nav),
        check('gaming_tabs_are_cached', '_tab_panels' in gaming and '_ensure_tab' in gaming and 'place_forget()' in gaming),
        check('hidden_performance_polling_paused', 'def set_active(self, active):' in health and 'after_cancel(self._performance_after_id)' in health),
        check('hidden_overlay_polling_paused', 'def set_active(self, active):' in overlay and 'after_cancel(self._status_after_id)' in overlay),
        check('telemetry_frequency_not_tied_to_ui_hz', 'telemetry' not in (ROOT/'gui/high_refresh.py').read_text(encoding='utf-8').lower().replace('telemetría', '')),
    ]
    ok = all(results)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
