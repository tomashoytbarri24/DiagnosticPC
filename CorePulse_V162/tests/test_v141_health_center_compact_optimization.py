from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v141_version_and_stage():
    ns = {}
    exec((ROOT / 'core' / 'version.py').read_text(encoding='utf-8'), ns)
    assert ns['VERSION'] == '141'
    assert ns['STAGE'] == 'HEALTH_CENTER_COMPACT_CLARITY_UI_OPTIMIZATION'


def test_health_summary_is_compact_and_more_readable():
    src = (ROOT / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')
    section = src[src.index('    def _render_health_intelligence_card'):src.index('    def _render_summary')]
    assert "font=(FONT, 20, 'bold')" in section
    assert "font=(FONT, 11)" in section
    assert "Índice actual" not in section
    assert "Conclusión determinista" not in section
    assert "Evidencia: " in section


def test_corepulse_inventory_card_removed_but_backend_preserved_lazy():
    src = (ROOT / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')
    summary = src[src.index('    def _render_summary'):src.index('    def _corepulse_state_style')]
    assert "lambda: self._select_tab('corepulse')" not in summary
    assert "'CorePulse',\n                'Runtime, herramientas opcionales" not in summary
    assert 'def _render_corepulse_diagnostics' in src
    assert 'from core.corepulse_diagnostics import collect_corepulse_diagnostics' in src
    top = src[:src.index('class HealthCenterPanel:')]
    assert 'from core.corepulse_diagnostics import collect_corepulse_diagnostics' not in top


def test_module_cards_drop_decorative_widget_layers():
    src = (ROOT / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')
    section = src[src.index('    def _health_module_card'):src.index('    def _capture_scroll_fraction')]
    assert 'tags_row' not in section
    assert 'status_box' not in section
    assert "font=(FONT, 14, 'bold')" in section
    assert "font=(FONT, 10), text_color=TEXT2" in section


def test_attention_copy_is_clearer():
    src = (ROOT / 'core' / 'health_intelligence.py').read_text(encoding='utf-8')
    assert "'ATTENTION': ('Seguimiento recomendado'" in src
    assert 'conviene seguir su evolución' in src
