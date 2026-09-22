from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEALTH = (ROOT / "gui" / "health_center_panel.py").read_text(encoding="utf-8")
VERSION = (ROOT / "core" / "version.py").read_text(encoding="utf-8")

def test_version_250():
    assert 'VERSION = "250"' in VERSION

def test_health_summary_band_present():
    assert "def _health_summary_status_card" in HEALTH
    assert "SALUD DEL SISTEMA" not in HEALTH or "Salud del sistema" in HEALTH
    assert "POLÍTICA DE MEDICIÓN" in HEALTH
    assert "REAL_OR_NA" in HEALTH

def test_three_column_module_grid():
    assert "for col in range(3):" in HEALTH
    assert "uniform='health_module_cards'" in HEALTH

def test_module_cards_keep_commands():
    assert "command, button_text='Abrir'" in HEALTH
    assert "f'{button_text}   →'" in HEALTH
