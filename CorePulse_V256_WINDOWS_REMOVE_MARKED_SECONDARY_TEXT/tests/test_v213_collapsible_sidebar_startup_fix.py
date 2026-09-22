import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v213_version_contract():
    from core import version
    assert version.VERSION == "213"
    assert "COLLAPSIBLE_SIDEBAR_STARTUP_FIX" in version.STAGE


def test_v213_dashboard_required_helpers_exist():
    src = (ROOT / "gui" / "dashboard.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    defs = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    for name in (
        "_style_existing_cards",
        "_series_stats",
        "_update_trend_titles",
        "_apply_chart_geometry_alignment",
        "_style_charts",
    ):
        assert name in defs, name


def test_v213_rebuild_main_layout_references_defined_helpers():
    src = (ROOT / "gui" / "dashboard.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    defs = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    assert "_rebuild_main_layout" in defs
    assert "_style_existing_cards" in defs
    assert "_style_charts" in defs


def test_v213_sidebar_motion_features_preserved():
    main = (ROOT / "main.py").read_text(encoding="utf-8")
    dashboard = (ROOT / "gui" / "dashboard.py").read_text(encoding="utf-8")
    assert "def toggle_sidebar_collapse(self):" in main
    assert "def _run_sidebar_animation(self, start_width, end_width, duration_ms=140):" in main
    assert "def _build_sidebar_toggle(app):" in dashboard
