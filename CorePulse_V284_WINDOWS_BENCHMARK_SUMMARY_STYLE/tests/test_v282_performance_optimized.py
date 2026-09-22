from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_chart_redraw_is_generation_gated_and_hidden_page_aware():
    text = (ROOT / 'main.py').read_text(encoding='utf-8')
    assert '_telemetry_history_generation' in text
    assert '_chart_last_history_generation' in text
    assert "dashboard_visible = getattr(self, '_active_internal_page', None)" in text
    assert 'generation != last_generation' in text


def test_hidden_alert_history_does_not_hit_store():
    text = (ROOT / 'main.py').read_text(encoding='utf-8')
    block = text[text.index('    def _refresh_alert_history_ui(self):'):text.index('    def _close_session_trends_window', text.index('    def _refresh_alert_history_ui(self):'))]
    assert block.index("panel = getattr(self, 'alert_history_panel', None)") < block.index('rows = self.alert_history_store.refresh()')
    assert "if panel is None:" in block


def test_tray_title_updates_only_when_changed():
    text = (ROOT / 'core' / 'tray_service.py').read_text(encoding='utf-8')
    assert 'if title == self._last_title:' in text


def test_detail_panels_skip_duplicate_snapshot_repaint():
    for rel in ('gui/cpu_detail_panel.py', 'gui/gpu_detail_panel.py', 'gui/ram_detail_panel.py'):
        text = (ROOT / rel).read_text(encoding='utf-8')
        assert "getattr(self, '_last_snapshot_stamp', None)" in text
