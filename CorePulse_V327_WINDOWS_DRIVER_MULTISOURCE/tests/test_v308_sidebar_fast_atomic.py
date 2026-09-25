from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "main.py").read_text(encoding="utf-8")

def _block(start, end):
    a = MAIN.index(start)
    b = MAIN.index(end, a)
    return MAIN[a:b]

def test_sidebar_uses_async_drawer_before_atomic_commit():
    block = _block("    def set_sidebar_collapsed", "    def toggle_sidebar_collapse")
    assert "_run_sidebar_drawer" in block
    assert "_commit_sidebar_drawer_state" in block
    assert "_finish_sidebar_native_transition" not in block

def test_drawer_moves_only_sidebar_not_dashboard_grid_per_frame():
    block = _block("    def _run_sidebar_drawer", "    def set_sidebar_collapsed")
    tick = block[block.index("        def tick"):]
    assert "sidebar.place_configure" in tick
    assert "grid_columnconfigure" not in tick
    assert "canvas.draw()" not in tick

def test_native_handle_is_single_root_window():
    block = _block("    def _sidebar_native_hwnds", "    def _set_sidebar_native_redraw")
    assert "GetAncestor" in block
    assert "return [root or client]" in block
