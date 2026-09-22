from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]


def test_v229_version_contract():
    from core import version
    assert version.VERSION == '229'
    assert 'SIDEBAR_COLORED_BORDERS_EXPERIMENT' in version.STAGE


def test_v229_dashboard_has_per_option_accents():
    text = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    assert 'SIDEBAR_OPTION_ACCENTS' in text
    assert "'btn_benchmark': COLORS['purple']" in text
    assert "'btn_diagnostic': COLORS['amber']" in text
    assert "'btn_health_center': COLORS['green']" in text
    assert "'btn_smart_alerts': COLORS['red']" in text
    assert "border_width=2 if active else 1" in text
    assert "_style_nav_button(button, active=active, accent=_sidebar_option_accent(attr))" in text


def test_v229_layout_preserves_colored_borders_on_responsive_restyle():
    text = (ROOT / 'gui' / 'dashboard_layout.py').read_text(encoding='utf-8')
    assert 'SIDEBAR_OPTION_ACCENTS' in text
    assert "border_color=_sidebar_option_accent(attr)" in text
    assert "border_width=2 if active else 1" in text
    assert "('_theme_toggle_button', '◉  Temas', 'themes', PURPLE)" in text
    assert "('_update_button', '↻  Actualizaciones', 'updates', CYAN)" in text
