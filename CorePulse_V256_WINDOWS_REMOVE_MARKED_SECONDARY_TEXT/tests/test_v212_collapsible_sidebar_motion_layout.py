from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v212_version_contract():
    from core import version
    assert version.VERSION == "212"
    assert "COLLAPSIBLE_SIDEBAR_MOTION_LAYOUT" in version.STAGE


def test_v212_main_sidebar_toggle_methods_exist():
    main = (ROOT / 'main.py').read_text(encoding='utf-8')
    assert 'self._sidebar_collapsed = False' in main
    assert 'def toggle_sidebar_collapse(self):' in main
    assert 'def set_sidebar_collapsed(self, collapsed, *, animated=True):' in main
    assert 'def _run_sidebar_animation(self, start_width, end_width, duration_ms=140):' in main
    assert 'Trail visual simple tipo motion blur durante el colapso/expansión.' in main
    assert 'apply_ui_consistency(self)' in main


def test_v212_dashboard_rebuilds_collapsible_sidebar():
    dashboard = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    assert 'def _build_sidebar_toggle(app):' in dashboard
    assert "text='⟩' if getattr(app, '_sidebar_collapsed', False) else '⟨'" in dashboard
    assert 'collapsed = bool(getattr(app, \"_sidebar_collapsed\", False))' not in dashboard  # exact quote style guard
    assert "collapsed = bool(getattr(app, '_sidebar_collapsed', False))" in dashboard
    assert "_apply_sidebar_icon(app, 'btn_benchmark', collapsed=collapsed)" in dashboard
    assert "if collapsed:" in dashboard and "app._personalization_block = None" in dashboard


def test_v212_layout_supports_collapsed_width_and_icon_mode():
    layout = (ROOT / 'gui' / 'dashboard_layout.py').read_text(encoding='utf-8')
    assert "if getattr(app, '_sidebar_collapsed', False):\n        width = 74" in layout
    assert "collapsed = bool(getattr(app, '_sidebar_collapsed', False))" in layout
    assert "_cfg(toggle_button, text='⟩' if collapsed else '⟨'" in layout
    assert "anchor='center' if collapsed else 'w'" in layout
