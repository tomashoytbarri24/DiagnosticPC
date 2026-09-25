from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "main.py").read_text(encoding="utf-8")

def _block(a, b):
    return SRC[SRC.index(a):SRC.index(b)]

def test_sidebar_click_path_is_short_and_has_no_legacy_visual_cleanup():
    block = _block("    def set_sidebar_collapsed", "    def toggle_sidebar_collapse")
    assert "duration_ms=52" in block
    assert "_clear_sidebar_transition_cover()" not in block
    assert "_clear_sidebar_motion_layers()" not in block

def test_sidebar_slide_uses_four_frames_and_keeps_atomic_commit():
    drawer = _block("    def _run_sidebar_drawer", "    def set_sidebar_collapsed")
    commit = _block("    def _commit_sidebar_drawer_state", "    def _run_sidebar_drawer")
    assert "duration_ms=52" in drawer
    assert "steps = 4" in drawer
    assert "ease_out_cubic" in drawer
    assert "self.after_idle(release_final_frame)" in commit
    assert "self._set_sidebar_native_redraw(False)" in commit

def test_chart_reflow_remains_outside_click_path():
    commit = _block("    def _commit_sidebar_drawer_state", "    def _run_sidebar_drawer")
    assert "self.after(4, self._finish_sidebar_chart_reflow)" in commit
    assert "canvas.draw()" not in commit
