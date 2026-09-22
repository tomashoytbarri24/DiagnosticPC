from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v222_version_contract():
    from core import version
    assert version.VERSION == '222'
    assert 'EDGE_ARROW_GLOBAL_HITZONE_FIX' in version.STAGE


def test_v222_global_click_binding_exists():
    src = (ROOT / 'main.py').read_text(encoding='utf-8')
    assert "self.bind_all('<Button-1>', self._on_sidebar_global_click, add='+')" in src
    assert 'def _on_sidebar_global_click(self, event=None):' in src
    assert '38 <= x <= 122' in src
    assert 'abs(int(y) - int(preview_y)) <= 34' in src


def test_v222_hover_lock_prevents_moving_target():
    src = (ROOT / 'main.py').read_text(encoding='utf-8')
    assert 'if x >= 42 and active_key and active_y is not None:' in src
    assert 'self._show_sidebar_edge_preview(active_key, active_y)' in src
    assert 'self._sidebar_edge_preview_y = y' in src


def test_v222_arrow_visual_area_slightly_larger():
    src = (ROOT / 'main.py').read_text(encoding='utf-8')
    assert "self, text='›', width=42, height=46" in src
    assert "(52, widgets['arrow'], {'x': 54, 'y': y, 'anchor': 'w'})," in src
