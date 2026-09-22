from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v220_version_contract():
    from core import version
    assert version.VERSION == '220'
    assert 'SUPERVISION_CLIP_ARROW_INTERACTION_FIX' in version.STAGE


def test_v220_sidebar_motion_clear_does_not_reset_hover_state():
    src = (ROOT / 'main.py').read_text(encoding='utf-8')
    block = src.split('def _clear_sidebar_motion_layers(self):', 1)[1].split('def _sidebar_boundary_x(self):', 1)[0]
    assert 'self._sidebar_motion_layers = []' in block
    assert '_sidebar_hover_map' not in block
    assert '_sidebar_edge_widgets' not in block
    assert '_sidebar_edge_tracking_enabled' not in block


def test_v220_arrow_has_stable_interaction_zone():
    src = (ROOT / 'main.py').read_text(encoding='utf-8')
    assert 'if x <= 118:' in src
    assert 'self._schedule_sidebar_edge_hide(150)' in src
    assert "if self._sidebar_hover_active_key == attr:" in src
    assert "width=34, height=42" in src
    assert "fg_color='transparent'" in src


def test_v220_supervision_card_is_more_responsive():
    dash = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    layout = (ROOT / 'gui' / 'dashboard_layout.py').read_text(encoding='utf-8')
    assert "band.grid_columnconfigure(1, weight=4" in dash
    assert "wraplength=185" in dash
    assert "font=(FONT, 11 if compact else 12 if standard else 14, 'bold')" in layout
    assert "wraplength=180 if compact else 205 if standard else 230" in layout
