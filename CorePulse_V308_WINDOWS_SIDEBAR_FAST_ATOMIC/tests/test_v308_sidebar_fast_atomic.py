from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "main.py").read_text(encoding="utf-8")


def _block(start, end):
    a = MAIN.index(start)
    b = MAIN.index(end, a)
    return MAIN[a:b]


def test_sidebar_toggle_keeps_native_atomic_redraw():
    block = _block("    def set_sidebar_collapsed", "    def toggle_sidebar_collapse")
    assert "_set_sidebar_native_redraw(False)" in block
    assert "_finish_sidebar_native_transition(handles)" in block
    assert "sidebar.place(" not in block


def test_finish_does_not_block_on_matplotlib_draw():
    block = _block("    def _finish_sidebar_native_transition", "    def _show_sidebar_transition_cover")
    assert "canvas.draw()" not in block
    assert "request_chart_reflow(self, redraw=True)" in block
    assert "after_idle(finish_charts)" in block


def test_finish_uses_layout_fast_path():
    block = _block("    def _finish_sidebar_native_transition", "    def _show_sidebar_transition_cover")
    assert "_apply_layout(self, force=False)" in block
    assert "_apply_layout(self, force=True)" not in block
