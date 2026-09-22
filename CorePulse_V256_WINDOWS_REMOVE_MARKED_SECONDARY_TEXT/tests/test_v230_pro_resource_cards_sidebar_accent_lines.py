from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]


def test_v230_version_contract():
    from core import version
    assert version.VERSION == '230'
    assert 'PRO_RESOURCE_CARDS_SIDEBAR_ACCENT_LINES' in version.STAGE


def test_v230_sidebar_uses_lines_not_full_colored_borders():
    dash = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    layout = (ROOT / 'gui' / 'dashboard_layout.py').read_text(encoding='utf-8')
    assert 'def _set_sidebar_option_line(btn, color, *, active=False):' in dash
    assert "line.place(x=6, rely=0.5, anchor='w', width=4 if active else 3" in dash
    assert "border_width=0" in dash
    assert "_sidebar_line(b, _sidebar_option_accent(attr), active=active)" in layout
    assert "border_width=2 if active else 1" not in layout


def test_v230_resource_cards_have_professional_decor():
    dash = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    assert 'def _ensure_resource_card_decor(card, accent, short_label):' in dash
    assert "text=short_label" in dash
    assert "width=42" in dash and "height=42" in dash
    assert "title.pack_configure(fill='x', padx=(70, 14)" in dash
    assert "_ensure_storage_card_decor(widgets.get('card'))" in dash
    assert 'def _ensure_chart_accents(app):' in dash


def test_v230_layout_does_not_reintroduce_known_runtime_nameerrors():
    layout = (ROOT / 'gui' / 'dashboard_layout.py').read_text(encoding='utf-8')
    assert 'text_color=PRIMARY' not in layout
    style_sidebar = layout.split('def _style_sidebar(app):', 1)[1].split('def _is_agent_container', 1)[0]
    assert ' if compact else ' not in style_sidebar
