from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "main.py").read_text(encoding="utf-8")

def section(a, b):
    return SRC[SRC.index(a):SRC.index(b, SRC.index(a))]

def test_v309_drawer_keeps_content_width_fixed_while_sliding():
    block = section("    def _run_sidebar_drawer", "    def set_sidebar_collapsed")
    assert "duration_ms=72" in block
    assert "steps = 6" in block
    assert "sidebar.place(" in block
    assert "sidebar.place_configure" in block
    assert "_commit_sidebar_drawer_state" in block

def test_v309_no_full_layout_or_sync_matplotlib_in_click_path():
    block = section("    def set_sidebar_collapsed", "    def toggle_sidebar_collapse")
    assert "_apply_layout" not in block
    assert "canvas.draw()" not in block
    assert "update_idletasks()" not in block

def test_v309_queues_rapid_second_toggle():
    block = section("    def set_sidebar_collapsed", "    def toggle_sidebar_collapse")
    assert "_sidebar_pending_collapsed" in block
