from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "main.py").read_text(encoding="utf-8")

def _block(a, b):
    return SRC[SRC.index(a):SRC.index(b)]

def test_sidebar_transition_is_shorter_and_lower_overhead():
    block = _block("    def _run_sidebar_drawer", "    def set_sidebar_collapsed")
    assert "duration_ms=52" in block
    assert "steps = 4" in block
    tick = block[block.index("        def tick"): ]
    assert "self.sidebar.lift()" not in tick

def test_chart_reflow_stays_async_after_commit():
    block = _block("    def _commit_sidebar_drawer_state", "    def _run_sidebar_drawer")
    assert "self.after(4, self._finish_sidebar_chart_reflow)" in block
    assert "draw()" not in block
