from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]


def test_v214_version_contract():
    from core import version
    assert version.VERSION == "214"
    assert "SIDEBAR_STABLE_MOTION_FIX" in version.STAGE


def test_v214_startup_helpers_still_exist():
    src = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    tree = ast.parse(src)
    defs = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    for name in ('_style_existing_cards', '_style_charts', '_rebuild_main_layout', '_rebuild_sidebar'):
        assert name in defs


def test_v214_sidebar_geometry_is_immediate_not_frame_by_frame():
    main = (ROOT / 'main.py').read_text(encoding='utf-8')
    assert 'def _run_sidebar_motion_effect(self, boundary_x, duration_ms=120):' in main
    assert 'self.sidebar.configure(width=target_width)' in main
    assert 'request_stable_layout_sync(self, force=True)' in main
    assert 'def _run_sidebar_animation(' not in main
    assert 'Esto evita que CPU/RAM/GPU, textos y gráficos se aplasten cuadro a cuadro.' in main
    assert 'return 64' in main


def test_v214_toggle_is_floating_on_sidebar_boundary():
    dashboard = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    assert 'Botón flotante pegado al divisor entre sidebar y contenido.' in dashboard
    assert 'button = ctk.CTkButton(\n            app,' in dashboard
    assert "text='›' if getattr(app, '_sidebar_collapsed', False) else '‹'" in dashboard
    assert "width=26" in dashboard
    assert "height=46" in dashboard


def test_v214_collapsed_nav_is_compact_and_soft():
    layout = (ROOT / 'gui' / 'dashboard_layout.py').read_text(encoding='utf-8')
    consistency = (ROOT / 'gui' / 'ui_consistency.py').read_text(encoding='utf-8')
    assert 'width = 64' in layout
    assert "width=44 if collapsed else 0" in layout
    assert "height=38 if collapsed" in layout
    assert "_set_nav_selection_indicator(b, active and not collapsed)" in layout
    assert "fg_color=role_color('accent_soft') if active else 'transparent'" in consistency
    assert "extra.update({'text': '', 'height': 38, 'width': 44, 'padx': 0, 'anchor': 'center'})" in consistency
