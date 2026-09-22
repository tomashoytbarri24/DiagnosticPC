from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v207_version_contract():
    from core import version
    assert version.VERSION == "207"
    assert "MAIN_SCREEN_REFINEMENT_FIXES" in version.STAGE


def test_v207_header_and_status_refinements_exist():
    dashboard = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    assert "height=116" in dashboard
    assert "height=40" in dashboard  # header meta block now tall enough for 2 lines
    assert "text='telemetría viva'" in dashboard
    assert "side_accent = ctk.CTkFrame(shell, fg_color=accent, width=4" in dashboard
    assert "band.grid_columnconfigure(0, weight=4, uniform='dashboard_status_primary')" in dashboard
    assert "badge_text = f'SMART {smart_val:.0f}%'" in dashboard


def test_v207_layout_refinements_exist():
    layout = (ROOT / 'gui' / 'dashboard_layout.py').read_text(encoding='utf-8')
    assert "_cfg(header, height=92 if compact else 108 if mode == 'standard' else 116)" in layout
    assert "ratio = 0.31 if mode == 'compact' else 0.39 if mode == 'standard' else 0.41" in layout
    assert "minimum = 236 if mode == 'compact' else 338 if mode == 'standard' else 360" in layout
