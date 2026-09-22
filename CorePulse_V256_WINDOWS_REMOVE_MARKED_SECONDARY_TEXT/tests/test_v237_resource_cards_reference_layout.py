from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def test_v237_version_contract():
    from core import version
    assert version.VERSION == '237'
    assert 'RESOURCE_CARDS_REFERENCE_LAYOUT' in version.STAGE

def test_v237_resource_cards_have_no_large_icons_and_keep_bars():
    text = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    assert 'def _resource_title_text' in text
    assert 'card._corepulse_resource_accent = accent_bar' in text
    assert "bar = ctk.CTkProgressBar(" in text
    assert "text=f'CPU\\n{cpu_name}'" in text
    assert "text='MEMORIA RAM\\nUso físico del sistema'" in text
    assert "text=f'GPU\\n{gpu_name}'" in text
    # The former icon helper is gone from the V237 resource builder.
    resource_block = text[text.index('def _ensure_resource_card_decor'):text.index('def _apply_resource_card_geometry')]
    assert 'icon_box' not in resource_block
    assert '_resource_icon_symbol' not in text

def test_v237_storage_has_no_large_icon():
    text = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    block = text[text.index('def _ensure_storage_card_decor'):text.index('def _ensure_chart_accents')]
    assert 'icon_box' not in block
    assert "accent = ctk.CTkFrame(shell, fg_color=COLORS['primary'], width=4" in block
    assert "bar = ctk.CTkProgressBar(content, height=6" in block
