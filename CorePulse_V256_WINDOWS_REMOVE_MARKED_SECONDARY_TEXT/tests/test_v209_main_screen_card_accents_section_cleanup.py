from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v209_version_contract():
    from core import version
    assert version.VERSION == "209"
    assert "MAIN_SCREEN_CARD_ACCENTS_SECTION_CLEANUP" in version.STAGE


def test_v209_card_accent_helper_and_usage_exist():
    dashboard = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    assert 'def _ensure_soft_card_accent(card, accent, *, placement=' in dashboard
    assert "_ensure_soft_card_accent(card, accent, placement='left')" in dashboard
    assert "_ensure_soft_card_accent(widgets.get('card'), COLORS['primary'], placement='left')" in dashboard
    assert "_ensure_soft_card_accent(app.frame_charts, COLORS['primary'], placement='left')" in dashboard


def test_v209_section_headers_removed_from_main_layout():
    dashboard = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    assert "app._resources_section.pack(fill='x'" not in dashboard
    assert "app._storage_section_header.pack(fill='x'" not in dashboard
    assert "app._trends_section_header.pack(fill='x'" not in dashboard
    assert "storage_label.pack(anchor='w'" not in dashboard


def test_v209_layout_applies_accents_to_storage_and_charts():
    layout = (ROOT / 'gui' / 'dashboard_layout.py').read_text(encoding='utf-8')
    assert "_ensure_soft_card_accent(card, CYAN, placement='left')" in layout
    assert "_ensure_soft_card_accent(app.frame_charts, CYAN, placement='left')" in layout
