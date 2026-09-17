from pathlib import Path


def test_drivers_table_no_longer_has_12_row_cap_and_is_paginated():
    ui = Path('gui/health_center_panel.py').read_text(encoding='utf-8')
    start = ui.index("elif kind == 'drivers':")
    end = ui.index("    def _repair_state_label", start)
    block = ui[start:end]

    assert "[:12]" not in block
    assert "_drivers_page_size" in block
    assert "Mostrando {start + 1}–{end} de {total}" in block
    assert "_set_drivers_page(page + 1)" in block
    assert "_set_drivers_page(page - 1)" in block
    assert "enumerate(items, start=start + 1)" in block


def test_driver_page_state_is_reset_on_new_scan():
    ui = Path('gui/health_center_panel.py').read_text(encoding='utf-8')
    assert "self._drivers_page = 0" in ui
    assert "elif name == 'drivers':\n                self._drivers_page = 0" in ui
    assert "def _set_drivers_page(self, page):" in ui
