from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_driver_attention_cards_have_inline_update_actions():
    text = (ROOT / "gui" / "health_center_panel.py").read_text(encoding="utf-8")
    assert "Buscar actualización" in text
    assert "Disponible {update_item.get('available_version')" in text
    assert "action_text = 'Descargar'" in text
    assert "action_text = 'Instalar'" in text

def test_selected_scan_updates_in_place_without_full_render():
    text = (ROOT / "gui" / "health_center_panel.py").read_text(encoding="utf-8")
    start = text.index("def _start_attention_scan")
    end = text.index("def _toggle_driver_inventory", start)
    block = text[start:end]
    assert "_apply_attention_scan_feedback" in block
    assert "_request_render" not in block
