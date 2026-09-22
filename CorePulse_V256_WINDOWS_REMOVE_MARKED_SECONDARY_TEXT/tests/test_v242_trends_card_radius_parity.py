from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def test_v242_version():
    from core import version
    assert version.VERSION == '242'
    assert 'TRENDS_CARD_RADIUS_PARITY' in version.STAGE

def test_chart_radius_matches_top_cards():
    dash = (ROOT/'gui'/'dashboard.py').read_text(encoding='utf-8')
    layout = (ROOT/'gui'/'dashboard_layout.py').read_text(encoding='utf-8')
    assert "app.frame_charts,\n        fg_color=COLORS['surface'],\n        border_color=COLORS['border'],\n        border_width=1,\n        corner_radius=12" in dash
    assert "_cfg(app.frame_charts, fg_color=SURFACE, border_color=BORDER, border_width=1, corner_radius=12)" in layout

def test_v241_header_not_present():
    dash = (ROOT/'gui'/'dashboard.py').read_text(encoding='utf-8')
    assert 'Tendencias recientes de CPU, RAM y GPU' not in dash
    assert "text='Últimos 60 s'" not in dash
