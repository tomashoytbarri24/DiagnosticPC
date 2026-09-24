from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "main.py").read_text(encoding="utf-8")

def _block(a, b):
    return SRC[SRC.index(a):SRC.index(b)]

def test_sidebar_commit_waits_for_idle_before_unfreezing_root():
    block = _block("    def _commit_sidebar_drawer_state", "    def _run_sidebar_drawer")
    assert "self.after_idle(release_final_frame)" in block
    assert "self.update_idletasks()" in block
    release = block[block.index("        def release_final_frame"):]
    assert "self._set_sidebar_native_redraw(True)" in release
    assert "self._flush_sidebar_native_redraw(handles)" in release

def test_sidebar_drawer_speed_and_async_chart_reflow_are_preserved():
    drawer = _block("    def _run_sidebar_drawer", "    def set_sidebar_collapsed")
    commit = _block("    def _commit_sidebar_drawer_state", "    def _run_sidebar_drawer")
    assert "duration_ms=52" in drawer
    assert "steps = 4" in drawer
    assert "self.after(4, self._finish_sidebar_chart_reflow)" in commit
