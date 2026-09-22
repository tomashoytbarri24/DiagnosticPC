from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def test_v244_version():
    from core import version
    assert version.VERSION == "244"
    assert "SQUARE_TRENDS_CONTAINER" in version.STAGE

def test_chart_container_is_square_everywhere():
    main = (ROOT / "main.py").read_text(encoding="utf-8")
    dash = (ROOT / "gui/dashboard.py").read_text(encoding="utf-8")
    layout = (ROOT / "gui/dashboard_layout.py").read_text(encoding="utf-8")
    assert "self.frame_charts = ctk.CTkFrame(self.main_content, fg_color=role_color('surface_2'), border_width=1, border_color=BORDER_COLOR, corner_radius=0)" in main
    assert "app.frame_charts,\n        fg_color=COLORS['surface'],\n        border_color=COLORS['border'],\n        border_width=1,\n        corner_radius=0," in dash
    assert "_cfg(app.frame_charts, fg_color=SURFACE, border_color=BORDER, border_width=1, corner_radius=0)" in layout
