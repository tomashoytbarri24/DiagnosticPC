"""V130 — Temas estable desde arranque + Actualizaciones embebida."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_version_130():
    text = (ROOT / "core" / "version.py").read_text(encoding="utf-8")
    assert 'VERSION = "130"' in text
    assert 'EMBEDDED_UPDATE_CENTER_THEME_BUTTON_STABILITY' in text


def test_updates_are_internal_navigation_page():
    nav = (ROOT / "gui" / "internal_navigation.py").read_text(encoding="utf-8")
    main = (ROOT / "main.py").read_text(encoding="utf-8")
    update = (ROOT / "gui" / "update_dialog.py").read_text(encoding="utf-8")
    assert "'updates': '_update_button'" in nav
    assert "'updates': 'update_panel'" in nav
    assert "activate_internal_page(self, 'updates')" in main
    assert "commit_internal_page(self, 'updates', host, panel)" in main
    assert "class UpdatePanel" in update
    assert "CTkToplevel" not in update
    assert "Todo ocurre dentro de esta misma ventana" in update


def test_update_page_has_guided_flow_and_auto_check():
    update = (ROOT / "gui" / "update_dialog.py").read_text(encoding="utf-8")
    assert "1 · Buscar  →  2 · Descargar y verificar SHA-256" in update
    assert "self.frame.after(260, self._auto_check)" in update
    assert "No hay versiones publicadas en el canal" in update
    assert "Esto no es un fallo de CorePulse" in update


def test_theme_button_never_falls_into_transparent_nav_style():
    layout = (ROOT / "gui" / "dashboard_layout.py").read_text(encoding="utf-8")
    consistency = (ROOT / "gui" / "ui_consistency.py").read_text(encoding="utf-8")
    assert "if attr == '_theme_toggle_button':" in layout
    assert "Era la segunda autoridad que borraba su fondo" in layout
    assert "fg_color=role_color('accent_2') if active else role_color('accent')" in layout
    assert "reafirmar SIEMPRE el CTA de Temas" in layout
    assert "if attr == '_theme_toggle_button':" in consistency
    assert "fg_color=role_color('accent_2') if active else role_color('accent')" in consistency
