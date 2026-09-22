from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v216_version_contract():
    from core import version
    assert version.VERSION == "216"
    assert "WINDOWED_STARTUP_GEOMETRY_FIX" in version.STAGE


def test_v216_preferred_geometry_can_be_forced_after_gate():
    src = (ROOT / 'gui' / 'adaptive_window.py').read_text(encoding='utf-8')
    assert 'def apply_preferred_launch_geometry(app, *, force=False):' in src
    assert "if getattr(app, '_launch_geometry_applied', False) and not force:" in src
    assert 'force=True' in src


def test_v216_reveal_forces_normal_window_before_deiconify():
    src = (ROOT / 'main.py').read_text(encoding='utf-8')
    reveal = src[src.index('def _reveal_main_window(self):'):]
    assert "self.attributes('-fullscreen', False)" in reveal
    assert "self.state('normal')" in reveal
    assert "apply_preferred_launch_geometry(self, force=True)" in reveal
    assert reveal.index("self.state('normal')") < reveal.index("self.deiconify()")
    assert reveal.index("apply_preferred_launch_geometry(self, force=True)") < reveal.index("self.deiconify()")


def test_v216_sidebar_full_hide_behavior_is_preserved():
    src = (ROOT / 'main.py').read_text(encoding='utf-8')
    assert 'self.sidebar.grid_remove()' in src
    assert "self.sidebar.grid(row=0, column=0, sticky='nsew')" in src
    assert 'return 0' in src[src.index('def _sidebar_target_width'):src.index('def _clear_sidebar_motion_layers')]
