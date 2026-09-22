from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_updates_has_no_rollback_ui():
    text = (ROOT / 'gui' / 'update_dialog.py').read_text(encoding='utf-8')
    assert 'text="Rollback"' not in text
    assert 'rollback_latest' not in text
    assert 'Versiones anteriores' in text


def test_benchmark_idle_status_card_is_not_packed():
    text = (ROOT / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')
    assert 'if running or result:' in text
    assert 'La superficie aparece recién cuando hay progreso real o un resultado.' in text
    assert "status_shell.pack(fill='x', padx=12, pady=(0, 10))" in text


def test_agent_card_matches_dashboard_signature():
    text = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    assert "agent_accent = ctk.CTkFrame(agent, fg_color=COLORS['primary'], width=4" in text
    assert "fg_color=COLORS['surface']" in text


def test_all_themes_are_dark_and_red_exists():
    from core.theme_manager import get_theme_profiles
    profiles = get_theme_profiles()
    assert profiles
    assert all(profile.get('appearance') == 'dark' for profile in profiles.values())
    assert 'crimson' in profiles
    assert profiles['crimson']['name'] == 'Rojo'
