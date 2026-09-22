from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v215_version_contract():
    from core import version
    assert version.VERSION == '215'
    assert 'FULL_SIDEBAR_HIDE_RESTORE' in version.STAGE


def test_v215_full_hide_uses_grid_remove_and_zero_boundary():
    main = (ROOT / 'main.py').read_text(encoding='utf-8')
    assert "if getattr(self, '_sidebar_collapsed', False):\n            return 0" in main
    assert 'self.sidebar.grid_remove()' in main
    assert "self.sidebar.grid(row=0, column=0, sticky='nsew')" in main
    assert "final_boundary = 0 if collapsed else self._sidebar_target_width()" in main


def test_v215_toggle_remains_available_when_sidebar_hidden():
    main = (ROOT / 'main.py').read_text(encoding='utf-8')
    dashboard = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    assert "button.configure(text='›' if collapsed else '‹')" in main
    assert "button.place(x=10, rely=0.48, anchor='w')" in main
    assert "button = ctk.CTkButton(\n            app," in dashboard


def test_v215_no_icon_rail_is_published_when_collapsed():
    dashboard = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    assert "if collapsed:\n        app._personalization_block = None" in dashboard
    assert "_safe_config(app.sidebar, fg_color=COLORS['sidebar'], width=224)" in dashboard
    assert "width=64 if collapsed else 224" not in dashboard


def test_v215_motion_blur_moves_only_visual_trail():
    main = (ROOT / 'main.py').read_text(encoding='utf-8')
    assert 'def _run_sidebar_motion_effect(self, start_x, end_x, duration_ms=130):' in main
    assert 'boundary = int(round(float(start_x) + delta * ratio))' in main
    assert 'self._paint_sidebar_motion_layers(boundary' in main
    assert 'self.sidebar.configure(width=width_now)' not in main
