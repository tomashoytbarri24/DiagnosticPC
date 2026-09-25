from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_theme_apply_is_live_and_does_not_restart():
    panel = (ROOT / 'gui' / 'theme_panel.py').read_text(encoding='utf-8')
    manager = (ROOT / 'core' / 'theme_manager.py').read_text(encoding='utf-8')
    assert 'apply_theme_live' in panel
    apply_block = panel.split('def _apply(self):', 1)[1]
    assert 'restart_application()' not in apply_block
    assert 'def apply_theme_live(' in manager


def test_startup_waits_for_settled_real_sample_and_preloads_nvme():
    main = (ROOT / 'main.py').read_text(encoding='utf-8')
    assert '_startup_ui_sample_count' in main
    assert 'if self._startup_ui_sample_count < 2:' in main
    assert 'collect_storage_summary_health(telemetry, include_slow_fallbacks=False)' in main
    assert "'services', 0.96, 'Estabilizando sensores…'" in main


def test_storage_health_is_flush_right_without_reserved_action_slot():
    dash = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    block = dash.split('def _ensure_storage_card_decor', 1)[1].split('def _ensure_chart_accents', 1)[0]
    assert "badge.pack(side='right'" in block
    assert "action_slot = ctk.CTkFrame" not in block
    assert "action_place={'relx': 1.0, 'rely': 0.5, 'anchor': 'e'}" in block


def test_sidebar_border_compacts_to_visible_content():
    dash = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    assert 'def _sync_sidebar_native_border_to_content(app):' in dash
    assert "target = getattr(app, '_sidebar_version', None)" in dash
