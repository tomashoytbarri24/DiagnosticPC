from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v211_version_contract():
    from core import version
    assert version.VERSION == "211"
    assert "HEADER_TEXT_CLEANUP_VISUAL_POLISH" in version.STAGE


def test_v211_header_subtitle_removed_and_header_compacted():
    dashboard = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    assert 'Cabecera superior más limpia: sólo identidad clave + estado del agente.' in dashboard
    assert "app._header_subtitle = None" in dashboard
    assert "header = ctk.CTkFrame(app.main_content, fg_color='transparent', height=78)" in dashboard
    assert "font=(FONT, 17, 'bold')" in dashboard
    assert 'Monitoreo continuo · datos reales / N/A · lectura rápida del estado general' not in dashboard


def test_v211_layout_compact_header_contracts():
    layout = (ROOT / 'gui' / 'dashboard_layout.py').read_text(encoding='utf-8')
    assert "_cfg(header, height=72 if compact else 76 if mode == 'standard' else 78)" in layout
    assert "font=(FONT, 14 if compact else 15 if mode == 'standard' else 17, 'bold')" in layout
    assert "wraplength=450 if compact else 590 if mode == 'standard' else 720" in layout
