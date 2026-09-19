from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_update_center_rows_do_not_overlap_and_status_is_compact():
    text = (ROOT / "gui" / "update_dialog.py").read_text(encoding="utf-8")
    assert 'safety.grid(row=4, column=0, sticky="ew"' in text
    assert 'actions.grid(row=5, column=0, sticky="ew"' in text
    assert 'outer.grid_rowconfigure(3, weight=0)' in text
    assert 'release.grid(row=3, column=0, sticky="ew"' in text


def test_publish_counter_describes_files_not_manual_edits():
    text = (ROOT / "gui" / "update_dialog.py").read_text(encoding="utf-8")
    assert "Publicar {count} archivo" in text
    assert "El total cuenta rutas de archivo pendientes en Git" in text
    assert "Cantidad alta:" in text
    assert "Publicar {count} cambio" not in text
