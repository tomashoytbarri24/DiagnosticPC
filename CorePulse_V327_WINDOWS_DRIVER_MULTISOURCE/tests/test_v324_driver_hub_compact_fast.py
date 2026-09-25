from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_driver_hub_uses_loaded_inventory_and_selected_attention():
    ui = (ROOT / "gui" / "health_center_panel.py").read_text(encoding="utf-8")
    core = (ROOT / "core" / "driver_updates.py").read_text(encoding="utf-8")
    assert "Buscar seleccionados" in ui
    assert "local_inventory=self._drivers" in ui
    assert "_candidates_from_health_inventory" in core
    assert "max_devices: int = 5" in core
    assert "CATALOG_HTTP_TIMEOUT = 4" in core

def test_attention_cards_are_explicitly_compact():
    ui = (ROOT / "gui" / "health_center_panel.py").read_text(encoding="utf-8")
    assert "corner_radius=9, height=76" in ui
    assert "row.pack_propagate(False)" in ui
    assert "corner_radius=10, height=82" in ui
