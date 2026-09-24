from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _src():
    return (ROOT / "main.py").read_text(encoding="utf-8")


def test_sidebar_transition_uses_windows_native_redraw_freeze():
    src = _src()
    assert "WM_SETREDRAW = 0x000B" in src
    assert "SendMessageW(hwnd, WM_SETREDRAW" in src
    assert "RedrawWindow(hwnd, None, None, flags)" in src


def test_sidebar_toggle_does_not_capture_or_overlay_the_window():
    src = _src()
    block = src[src.index("    def set_sidebar_collapsed"):src.index("    def toggle_sidebar_collapse")]
    assert "ImageGrab" not in block
    assert "_capture_sidebar_transition_snapshot" not in block
    assert "_show_sidebar_transition_cover" not in block
    assert "_run_sidebar_motion_effect" not in block
    assert "_set_sidebar_native_redraw(False)" in block
    assert "_finish_sidebar_native_transition(handles)" in block


def test_final_state_is_published_atomically_and_chart_redraw_is_deferred():
    src = _src()
    block = src[src.index("    def _finish_sidebar_native_transition"):src.index("    def _show_sidebar_transition_cover")]
    assert "_apply_layout(self, force=False)" in block
    assert "request_chart_reflow(self, redraw=True)" in block
    assert "after_idle(finish_charts)" in block
    assert "_set_sidebar_native_redraw(True)" in block
    assert "_flush_sidebar_native_redraw(handles)" in block
