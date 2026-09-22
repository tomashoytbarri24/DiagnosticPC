from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def test_v225_version_contract():
    from core import version
    assert version.VERSION == '225'
    assert 'SIDEBAR_TYPOGRAPHY_ICON_SCALE' in version.STAGE

def test_v225_dashboard_sidebar_scaling():
    text = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    assert "font=(FONT, 9, 'bold')" in text
    assert "size=(20, 20)" in text
    assert "width=248" in text
    assert "height=38" in text

def test_v225_layout_sidebar_scaling():
    text = (ROOT / 'gui' / 'dashboard_layout.py').read_text(encoding='utf-8')
    assert "_cfg(app.sidebar, width=248, fg_color=SIDEBAR)" in text
    assert "width = 242 if compact else 248 if standard else 254" in text
    assert "font=(FONT, 11 if compact else 12, 'bold')" in text
    assert "height=40 if collapsed else 36 if compact else 38 if standard else 40" in text
