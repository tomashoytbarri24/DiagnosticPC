from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v219_version_contract():
    from core import version
    assert version.VERSION == "219"
    assert "EDGE_HOVER_CASCADE_SIDEBAR" in version.STAGE


def test_v219_main_has_edge_hover_tracking_and_preview():
    main = (ROOT / 'main.py').read_text(encoding='utf-8')
    assert "self._sidebar_hover_map = []" in main
    assert "self._sidebar_edge_tracking_enabled = False" in main
    assert "def _install_sidebar_edge_tracking(self):" in main
    assert "def refresh_sidebar_hover_map(self):" in main
    assert "def _show_sidebar_edge_preview(self, attr, center_y):" in main
    assert "def _on_sidebar_global_motion(self, event=None):" in main
    assert "if x <= 72:" in main
    assert "nearest = min(items, key=lambda item: abs(int(item.get('y', 0)) - int(y)))" in main


def test_v219_hover_preview_has_cascade_steps_and_toggle_is_hover_only():
    main = (ROOT / 'main.py').read_text(encoding='utf-8')
    assert "(0, widgets['ghost_a']" in main
    assert "(18, widgets['ghost_b']" in main
    assert "(34, widgets['icon']" in main
    assert "(52, widgets['arrow']" in main
    assert "if collapsed or not visible:" in main
    assert "button.place_forget()" in main


def test_v219_dashboard_toggle_button_is_smaller():
    dashboard = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    assert "width=20" in dashboard
    assert "height=38" in dashboard
    assert "corner_radius=10" in dashboard
