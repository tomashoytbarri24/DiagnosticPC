from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_driver_buttons_keep_high_contrast():
    ui = (ROOT / "gui" / "health_center_panel.py").read_text(encoding="utf-8")
    assert "text_color='#ffffff'" in ui
    assert "text_color_disabled='#d8e2ee'" in ui

def test_selected_driver_search_has_per_device_feedback():
    ui = (ROOT / "gui" / "health_center_panel.py").read_text(encoding="utf-8")
    assert "Buscar seleccionados" in ui
    assert "Buscando una versión compatible" in ui
    assert "Sin actualización compatible confirmada" in ui

def test_driver_scan_reports_each_checked_device():
    core = (ROOT / "core" / "driver_updates.py").read_text(encoding="utf-8")
    assert '"device_results": device_results' in core
    assert '"status": "NO_UPDATE"' in core
    assert '"status": "UPDATE_AVAILABLE"' in core

def test_windows_inventory_keeps_hardware_ids():
    source = (ROOT / "core" / "windows_health.py").read_text(encoding="utf-8")
    assert "HardwareID=$_.HardWareID" in source
