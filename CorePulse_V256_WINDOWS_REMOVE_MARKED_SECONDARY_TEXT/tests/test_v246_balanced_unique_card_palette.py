from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def test_version_246():
    from core import version
    assert version.VERSION == '246'
    assert 'BALANCED_UNIQUE_CARD_PALETTE' in version.STAGE

def test_balanced_resource_palette_matches_dashboard_and_layout():
    dash = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    layout = (ROOT / 'gui' / 'dashboard_layout.py').read_text(encoding='utf-8')
    expected = {
        'cpu_card': '#4f7fbd',
        'ram_card': '#2fa58f',
        'gpu_card': '#a866bd',
        'trends_card': '#7086ad',
    }
    for key, color in expected.items():
        assert f"'{key}': '{color}'" in dash
    assert "CPU_CARD = '#4f7fbd'" in layout
    assert "RAM_CARD = '#2fa58f'" in layout
    assert "GPU_CARD = '#a866bd'" in layout
    assert "TRENDS_CARD = '#7086ad'" in layout

def test_storage_palette_is_unique_and_muted():
    dash = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    for color in ('#c4874d', '#b97482', '#839d60', '#5593a6', '#b79b4f', '#7f76ad'):
        assert color in dash

def test_v245_geometry_contract_is_preserved():
    main = (ROOT / 'main.py').read_text(encoding='utf-8')
    layout = (ROOT / 'gui' / 'dashboard_layout.py').read_text(encoding='utf-8')
    storage = (ROOT / 'gui' / 'hardware_storage_view.py').read_text(encoding='utf-8')
    assert "card.pack(fill='x', pady=3, padx=0)" in main
    assert "card.pack_configure(fill='x', expand=False, padx=0, pady=2)" in layout
    assert "card.pack_configure(fill='x', expand=False, padx=0, pady=2)" in storage
