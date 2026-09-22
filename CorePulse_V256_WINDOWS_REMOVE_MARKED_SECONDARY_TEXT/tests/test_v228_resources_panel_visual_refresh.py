from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def test_v228_version_contract():
    from core import version
    assert version.VERSION == '228'
    assert 'RESOURCES_PANEL_VISUAL_REFRESH' in version.STAGE

def test_v228_dashboard_charts_surface_refresh():
    text = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    assert "corner_radius=16" in text
    assert "app.fig.set_facecolor(COLORS['surface'])" in text
    assert "ax.set_facecolor(COLORS['surface'])" in text

def test_v228_layout_lower_panels_refresh():
    text = (ROOT / 'gui' / 'dashboard_layout.py').read_text(encoding='utf-8')
    assert "_cfg(card, fg_color=SURFACE, border_color=BORDER, border_width=1, corner_radius=16)" in text
    assert "_cfg(card, fg_color=SURFACE, border_color=BORDER, border_width=1, corner_radius=16, height=130)" in text
    assert "_cfg(app.frame_charts, fg_color=SURFACE, border_color=BORDER, border_width=1, corner_radius=16)" in text
