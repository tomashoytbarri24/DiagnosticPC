from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_linux_tuning_refresh_is_idempotent_by_parenting_cards_in_body():
    source = (ROOT / 'gui' / 'linux_tuning_panel.py').read_text(encoding='utf-8')
    assert 'self.body, fg_color=SURFACE' in source
    assert 'for child in self.body.winfo_children()' in source
    assert 'child.destroy()' in source


def test_linux_power_profile_feedback_is_optimistic_and_verified():
    source = (ROOT / 'gui' / 'linux_tuning_panel.py').read_text(encoding='utf-8')
    paint = source.index('self._paint_profile(profile)')
    apply_change = source.index('ok, detail = set_power_profile(profile)')
    assert paint < apply_change
    assert '_verify_profile' in source
    assert 'self.app.after(180' in source


def test_theme_catalog_balances_light_options_and_keeps_exact_roles():
    import core.theme_manager as tm

    profiles = tm.get_theme_profiles()
    light = [profile for profile in profiles.values() if profile.get('appearance') == 'light']
    dark = [profile for profile in profiles.values() if profile.get('appearance') == 'dark']
    assert len(profiles) == 15
    assert len(light) == 6
    assert len(dark) == 9
    for key in ('sky', 'mint', 'sand', 'lavender', 'pearl', 'snow'):
        assert profiles[key]['appearance'] == 'light'
        for role in ('bg', 'surface', 'surface_2', 'sidebar', 'border', 'text', 'text_2', 'muted', 'accent', 'accent_2'):
            assert str(profiles[key][role]).startswith('#') and len(profiles[key][role]) == 7


def test_light_filter_never_keeps_a_hidden_dark_preview_selected():
    source = (ROOT / 'gui' / 'theme_panel.py').read_text(encoding='utf-8')
    assert "('Todos', 'Oscuros', 'Claros')" in source
    assert 'selected_visible' in source
    assert "value == 'Claros' and appearance == 'light'" in source
    assert 'self._select(key)' in source
