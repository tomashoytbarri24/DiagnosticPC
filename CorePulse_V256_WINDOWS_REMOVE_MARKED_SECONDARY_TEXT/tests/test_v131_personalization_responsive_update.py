"""V131 — Personalización refinada + Actualizaciones responsive."""
from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256(rel: str) -> str:
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


def test_v131_contract():
    version = (ROOT / "core" / "version.py").read_text(encoding="utf-8")
    dashboard = (ROOT / "gui" / "dashboard.py").read_text(encoding="utf-8")
    layout = (ROOT / "gui" / "dashboard_layout.py").read_text(encoding="utf-8")
    consistency = (ROOT / "gui" / "ui_consistency.py").read_text(encoding="utf-8")
    update = (ROOT / "gui" / "update_dialog.py").read_text(encoding="utf-8")

    assert 'VERSION = "131"' in version
    assert 'RESPONSIVE_PERSONALIZATION_UPDATE_LAYOUT' in version

    # Personalización queda unificada y no usa accent permanente.
    assert "app._personalization_block = personalization_block" in dashboard
    assert "text='Apariencia y versión'" in dashboard
    assert "text='◉  Temas'" in dashboard
    assert "text='↻  Actualizaciones'" in dashboard
    assert "fg_color='transparent'" in dashboard
    assert "personalization_block.pack(side='top'" in dashboard

    # Temas/Actualizaciones usan la misma autoridad contextual.
    assert "('_theme_toggle_button', '◉  Temas', 'themes')" in layout
    assert "('_update_button', '↻  Actualizaciones', 'updates')" in layout
    assert "fg_color=SIDEBAR_ACTIVE_BG if active else 'transparent'" in layout
    assert "width = 224 if compact else 230 if standard else 236" in layout
    assert "font=(FONT, 10, 'bold')" in layout
    assert "app._agent_detail.grid_remove()" in layout
    assert "hint.pack_forget()" in layout and "ver.pack_forget()" in layout
    assert "if attr == '_theme_toggle_button'" in consistency
    assert "extra = {'text': '◉  Temas'" in consistency

    # Actualizaciones usa grid, sólo el estado crece, y el footer queda fuera
    # de esa fila elástica para no desaparecer en ventanas bajas.
    assert "outer.grid_rowconfigure(3, weight=1)" in update
    assert 'release.grid(row=3, column=0, sticky="nsew"' in update
    assert 'actions.grid(row=5, column=0, sticky="ew")' in update
    assert "def on_viewport_settled(self):" in update
    assert "self.notes.configure(height=82 if compact else 110)" in update
    assert "CTkToplevel" not in update


def test_protected_files_unchanged():
    expected = {
        'core/runtime_venv_path.py': '263d725dc8a50ef57d2e0dd8d8827968f58d2b67dcee6b0a276ca6dd8d562e92',
        'bootstrap_corepulse.py': '925d4ef090b28c27ceffbbbba9362a8137f665212ac445e96a096c0ce5e17a0b',
        'core/source_runtime_bootstrap.py': 'bde37780c35ebc280b0b22ac6a71926051ae9fde48b65935b6af64b819f7ccfd',
        'requirements-runtime-lock.txt': '36ee044c5dab3c5c8cfecbe0456923c9f406d83a93ef04d93f9fd27f1566c706',
        'core/nvme_smart_windows.py': 'fe9481d270d5b47299b97fc97d37ee56f65bd904333f634255e4a91e63958283',
    }
    for rel, digest in expected.items():
        assert sha256(rel) == digest, rel
