from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v208_version_contract():
    from core import version
    assert version.VERSION == "208"
    assert "MAIN_SCREEN_HEADER_INTEGRATION_FIX" in version.STAGE


def test_v208_header_is_single_integrated_right_block():
    dashboard = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    assert 'Cabecera principal compacta e integrada' in dashboard
    assert 'height=104' in dashboard
    assert 'height=76' in dashboard
    assert "app._header_meta = agent" in dashboard
    assert "divider = ctk.CTkFrame(agent, fg_color=COLORS['border'], height=1)" in dashboard
    assert "text='Última actualización: esperando'" in dashboard


def test_v208_layout_header_contracts():
    layout = (ROOT / 'gui' / 'dashboard_layout.py').read_text(encoding='utf-8')
    assert "_cfg(header, height=88 if compact else 96 if mode == 'standard' else 104)" in layout
    assert "_cfg(getattr(app, '_header_agent_text', None), font=(FONT, 8 if compact else 9, 'bold'))" in layout
