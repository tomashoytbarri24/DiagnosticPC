from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def _src():
    return (ROOT / "main.py").read_text(encoding="utf-8")

def test_sidebar_final_commit_still_uses_windows_native_redraw_freeze():
    src = _src()
    assert "WM_SETREDRAW = 0x000B" in src
    assert "SendMessageW(hwnd, WM_SETREDRAW" in src
    assert "RedrawWindow(hwnd, None, None, flags)" in src

def test_sidebar_animation_does_not_reflow_dashboard_each_tick():
    src = _src()
    block = src[src.index("    def _run_sidebar_drawer"):src.index("    def set_sidebar_collapsed")]
    assert "sidebar.place_configure" in block
    assert "grid_columnconfigure" not in block[block.index("        def tick"): ]
    assert "update_idletasks()" not in block[block.index("        def tick"): ]
    assert "_apply_layout" not in block

def test_commit_is_single_and_chart_redraw_is_deferred():
    src = _src()
    block = src[src.index("    def _commit_sidebar_drawer_state"):src.index("    def _run_sidebar_drawer")]
    assert "_set_sidebar_native_redraw(False)" in block
    assert "_set_sidebar_native_redraw(True)" in block
    assert "_flush_sidebar_native_redraw(handles)" in block
    assert "_apply_layout" not in block
    assert "after(4, self._finish_sidebar_chart_reflow)" in block
