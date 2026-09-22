from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v206_version_contract():
    from core import version
    assert version.VERSION == "206"
    assert "MAIN_SCREEN_HERO_VISUAL_POLISH" in version.STAGE


def test_v206_dashboard_hero_visual_contracts():
    dashboard = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    assert "def _section_header(parent, title, subtitle):" in dashboard
    assert "RESUMEN EJECUTIVO DEL EQUIPO" in dashboard
    assert "Monitoreo continuo · datos reales / N/A · lectura rápida del estado general" in dashboard
    assert "DATOS REALES / N/A" in dashboard
    assert "VISIÓN RÁPIDA" in dashboard
    assert "app._resources_section = _section_header" in dashboard
    assert "app._storage_section_header = _section_header" in dashboard
    assert "app._trends_section_header = _section_header" in dashboard


def test_v206_layout_polish_contracts():
    layout = (ROOT / 'gui' / 'dashboard_layout.py').read_text(encoding='utf-8')
    assert "_cfg(header, height=76 if compact else 88 if mode == 'standard' else 96)" in layout
    assert "getattr(app, '_header_eyebrow', None)" in layout
    assert "getattr(app, '_header_subtitle', None)" in layout
    assert "for attr in ('_header_chip_live', '_header_chip_data', '_header_chip_focus'):" in layout
    assert "height = 92 if compact else 108 if standard else 114" in layout
