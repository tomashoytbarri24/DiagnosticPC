from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def test_version_245():
    from core import version
    assert version.VERSION == '245'
    assert 'ALIGNMENT_UNIQUE_CARD_ACCENTS' in version.STAGE

def test_storage_alignment_has_no_inner_horizontal_inset():
    main = (ROOT / 'main.py').read_text(encoding='utf-8')
    layout = (ROOT / 'gui' / 'dashboard_layout.py').read_text(encoding='utf-8')
    storage = (ROOT / 'gui' / 'hardware_storage_view.py').read_text(encoding='utf-8')
    assert "card.pack(fill='x', pady=3, padx=0)" in main
    assert "card.pack_configure(fill='x', expand=False, padx=0, pady=2)" in layout
    assert "card.pack_configure(fill='x', expand=False, padx=0, pady=2)" in storage

def test_resource_cards_have_distinct_accents():
    dash = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    for key in ('cpu_card', 'ram_card', 'gpu_card', 'trends_card'):
        assert f"'{key}'" in dash
    assert 'STORAGE_CARD_ACCENTS = (' in dash
    assert "_storage_card_accent(idx)" in dash

def test_smart_authority_not_replaced():
    dash = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    storage = (ROOT / 'gui' / 'hardware_storage_view.py').read_text(encoding='utf-8')
    assert "health_percent" in dash
    assert "health_label" in storage
    assert "windows_health_status" in storage
