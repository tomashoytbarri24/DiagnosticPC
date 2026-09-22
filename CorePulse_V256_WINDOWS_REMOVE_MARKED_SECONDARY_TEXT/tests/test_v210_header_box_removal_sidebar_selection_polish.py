from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v210_version_contract():
    from core import version
    assert version.VERSION == "210"
    assert "HEADER_BOX_REMOVAL_SIDEBAR_SELECTION_POLISH" in version.STAGE


def test_v210_header_is_unboxed_and_compact():
    dashboard = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    assert 'Cabecera superior limpia: sin recuadro exterior pesado.' in dashboard
    assert "fg_color='transparent',\n        border_width=0" in dashboard
    assert "app._header_chip_row = None" in dashboard
    assert "app._header_meta_hint = None" in dashboard


def test_v210_sidebar_selection_indicator_exists():
    dashboard = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    assert 'def _set_nav_selection_indicator(btn, active=False):' in dashboard
    assert "bar.place(x=7, rely=0.5, anchor='w', width=3, relheight=0.52)" in dashboard
    assert "_set_nav_selection_indicator(btn, active)" in dashboard


def test_v210_layout_applies_sidebar_polish():
    layout = (ROOT / 'gui' / 'dashboard_layout.py').read_text(encoding='utf-8')
    assert "_cfg(header, height=80 if compact else 84 if mode == 'standard' else 86)" in layout
    assert "from gui.dashboard import _set_nav_selection_indicator" in layout
    assert "_set_nav_selection_indicator(b, active)" in layout
    assert "fg_color=role_color('accent_soft') if active else 'transparent'" in layout
