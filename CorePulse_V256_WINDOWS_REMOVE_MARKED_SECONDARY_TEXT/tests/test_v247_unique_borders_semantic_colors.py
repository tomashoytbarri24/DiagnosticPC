from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def test_v247_version():
    from core import version
    assert version.VERSION == '247'
    assert 'UNIQUE_BORDERS_SEMANTIC_TELEMETRY_COLORS' in version.STAGE

def test_resource_semantic_colors_preserved():
    text = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    assert "COLORS['cpu_card'], COLORS['primary']" in text
    assert "COLORS['ram_card'], COLORS['green']" in text
    assert "COLORS['gpu_card'], COLORS['purple']" in text
    assert "progress_color=semantic" in text

def test_storage_unique_border_but_cyan_data():
    text = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    assert "storage_accent = _storage_card_accent(idx)" in text
    assert "progress_color=COLORS['primary']" in text
    assert "text_color=COLORS['primary']" in text
