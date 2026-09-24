from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _toggle_block():
    source = (ROOT / 'main.py').read_text(encoding='utf-8')
    start = source.index('    def set_sidebar_collapsed')
    end = source.index('    def toggle_sidebar_collapse', start)
    return source[start:end]


def test_sidebar_toggle_reuses_existing_tree():
    block = _toggle_block()
    assert '_rebuild_sidebar' not in block
    assert 'grid_remove()' in block
    assert "self.sidebar.grid(row=0, column=0" in block
    assert 'self.sidebar.configure(width=target_width)' in block


def test_sidebar_toggle_avoids_progressive_geometry_animation():
    block = _toggle_block()
    assert '_run_sidebar_motion_effect' not in block
    assert '_show_sidebar_transition_cover' not in block
    assert '_finish_sidebar_native_transition(handles)' in block
