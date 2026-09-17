"""V100 — drag de scrollbar sin ghosting en todas las vistas largas."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION


def check(name, condition):
    print(f"[{'PASS' if condition else 'FAIL'}] {name}: {bool(condition)}")
    return bool(condition)


def main():
    scroll = (ROOT / 'gui' / 'stable_scroll.py').read_text(encoding='utf-8')
    main = (ROOT / 'main.py').read_text(encoding='utf-8')
    panels = [
        'cpu_detail_panel.py', 'gpu_detail_panel.py', 'ram_detail_panel.py',
        'network_detail_panel.py', 'windows_tweaks_panel.py',
        'health_center_panel.py', 'telemetry_detail_panel.py',
        'alert_panel.py', 'alert_history_panel.py', 'session_trends_panel.py',
    ]
    panel_text = [(ROOT / 'gui' / name).read_text(encoding='utf-8') for name in panels]

    checks = [
        check('version', VERSION == '103'),
        check('custom_corepulse_drag_scrollbar', 'class _CorePulseDragScrollbar(tk.Canvas):' in scroll),
        check('ctk_scrollbar_removed_from_shared_host', 'ctk.CTkScrollbar(' not in scroll),
        check('drag_events_owned_directly', "'<Button-1>'" in scroll and "'<B1-Motion>'" in scroll and "'<ButtonRelease-1>'" in scroll),
        check('drag_coalesced_to_refresh_frame', '_pending_fraction' in scroll and '_frame_ms' in scroll and '_flush_drag_frame' in scroll),
        check('content_and_thumb_commit_same_frame', "self._command('moveto', fraction)" in scroll and 'self.scrollbar.set(first_f, last_f)' in scroll),
        check('geometry_frozen_during_drag', 'if self._drag_active:' in scroll and 'self._geometry_dirty = True' in scroll),
        check('scroll_state_stays_active_while_button_held', 'return bool(self._drag_active or time.monotonic() < self._scroll_active_until)' in scroll),
        check('windows_old_frame_is_erased', 'ERASE | ERASENOW' in scroll and 'flags |= 0x0004 | 0x0200' in scroll),
        check('windows_gdi_flush_after_drag_frame', 'GdiFlush' in scroll),
        check('no_reentrant_tk_update_during_drag', '.update()' not in scroll),
        check('all_long_panels_share_fix', all('StableScrollHost' in text for text in panel_text)),
        check('dashboard_storage_scroll_uses_same_engine', 'self.scroll_disks = StableScrollHost(' in main and "disk_parent = getattr(self.scroll_disks, 'content', self.scroll_disks)" in main),
    ]
    ok = all(checks)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
