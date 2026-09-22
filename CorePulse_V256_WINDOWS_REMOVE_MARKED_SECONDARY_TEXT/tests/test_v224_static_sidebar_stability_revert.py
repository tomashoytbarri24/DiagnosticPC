from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v224_version_contract():
    from core import version
    assert version.VERSION == '224'
    assert 'STATIC_SIDEBAR_STABILITY_REVERT' in version.STAGE


def test_v224_no_startup_edge_hover_binding():
    main = (ROOT / 'main.py').read_text(encoding='utf-8')
    assert "self.after(220, self._install_sidebar_edge_tracking)" not in main
    assert "def _install_sidebar_edge_tracking(self):" in main
    assert "deshabilitado; no instala bindings globales" in main


def test_v224_sidebar_rebuild_has_no_toggle_or_collapsed_branch():
    dashboard = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    start = dashboard.index('def _rebuild_sidebar(app):')
    end = dashboard.index('\ndef _style_existing_cards', start)
    block = dashboard[start:end]
    assert '_build_sidebar_toggle(app)' not in block
    assert 'if collapsed:' not in block
    assert "app._sidebar_toggle_button = None" in block


def test_v224_layout_and_navigation_are_static():
    layout = (ROOT / 'gui' / 'dashboard_layout.py').read_text(encoding='utf-8')
    ui = (ROOT / 'gui' / 'ui_consistency.py').read_text(encoding='utf-8')
    assert 'collapsed = False' in layout
    assert 'collapsed = False' in ui
    assert "anchor='center' if collapsed else 'w'" not in ui
