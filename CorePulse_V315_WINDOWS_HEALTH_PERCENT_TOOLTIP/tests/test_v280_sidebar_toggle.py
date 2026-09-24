from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def _source():
    return (ROOT / "main.py").read_text(encoding="utf-8")

def _toggle_block():
    source = _source()
    start = source.index("    def set_sidebar_collapsed")
    end = source.index("    def toggle_sidebar_collapse", start)
    return source[start:end]

def test_sidebar_toggle_reuses_existing_tree():
    src = _source()
    block = _toggle_block()
    drawer = src[src.index("    def _run_sidebar_drawer"):src.index("    def set_sidebar_collapsed")]
    commit = src[src.index("    def _commit_sidebar_drawer_state"):src.index("    def _run_sidebar_drawer")]
    assert "_rebuild_sidebar" not in block
    assert "self.sidebar.grid_remove()" in drawer or "self.sidebar.grid_remove()" in commit
    assert "self.sidebar.grid(" in commit
    assert "self.sidebar.configure(width=target_width)" in commit

def test_sidebar_toggle_avoids_dashboard_geometry_animation_per_frame():
    src = _source()
    block = _toggle_block()
    drawer = src[src.index("    def _run_sidebar_drawer"):src.index("    def set_sidebar_collapsed")]
    tick = drawer[drawer.index("        def tick"): ]
    assert "_run_sidebar_motion_effect" not in block
    assert "_show_sidebar_transition_cover" not in block
    assert "sidebar.place_configure" in tick
    assert "grid_columnconfigure" not in tick
