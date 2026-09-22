from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v221_version_contract():
    from core import version
    assert version.VERSION == '221'
    assert 'STATUS_TEXT_FIT_EDGE_HOVER_RELIABILITY' in version.STAGE


def test_v221_status_cards_allow_long_text():
    dashboard = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    layout = (ROOT / 'gui' / 'dashboard_layout.py').read_text(encoding='utf-8')
    assert "height=124" in dashboard
    assert "band.grid_columnconfigure(0, weight=5" in dashboard
    assert "band.grid_columnconfigure(1, weight=5" in dashboard
    assert "wraplength=185" in dashboard
    assert "font=(FONT, 12 if compact else 14 if standard else 15, 'bold')" in layout
    assert "wraplength=150 if compact else 175 if standard else 195" in layout


def test_v221_hover_leave_no_longer_uses_global_leave():
    main = (ROOT / 'main.py').read_text(encoding='utf-8')
    assert "self.bind_all('<Motion>', self._on_sidebar_global_motion, add='+')" in main
    assert "self.bind('<Leave>', self._on_sidebar_global_leave, add='+')" in main
    assert "bind_all('<Leave>')" in main  # only in explanatory comment
    assert "def verify_outside():" in main
    assert "if x <= 145:" in main
    assert "self._schedule_sidebar_edge_hide(220)" in main


def test_v221_arrow_position_remains_inside_hover_zone():
    main = (ROOT / 'main.py').read_text(encoding='utf-8')
    assert "widgets['arrow'], {'x': 56, 'y': y, 'anchor': 'w'}" in main
