from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAYOUT = (ROOT / "gui" / "dashboard_layout.py").read_text(encoding="utf-8")


def test_personalization_tight_depends_on_height_not_compact_width():
    assert "personalization_tight = viewport_h < 690" in LAYOUT
    assert "personalization_tight = compact or" not in LAYOUT


def test_personalization_is_never_bottom_anchored():
    marker = "# V300: Personalización forma parte del flujo del sidebar"
    start = LAYOUT.index(marker)
    block = LAYOUT[start:start + 900]
    assert "side='top'" in block
    assert "side='bottom'" not in block
    assert "after=getattr(app, 'btn_alert_history', None)" in block
