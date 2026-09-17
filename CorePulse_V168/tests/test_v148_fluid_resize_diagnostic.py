from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel):
    return (ROOT / rel).read_text(encoding='utf-8')


def test_v148_version_stage():
    src = read('core/version.py')
    assert 'VERSION = "148"' in src
    assert 'FLUID_WINDOW_RESIZE_AND_DIAGNOSTIC_BREAKPOINT_OPTIMIZATION' in src


def test_global_resize_uses_single_trailing_detector():
    src = read('gui/dashboard_layout.py')
    assert 'app._layout_last_resize_event = time.monotonic()' in src
    assert "if getattr(app, '_resize_after_id', None) is None:" in src
    configure_region = src[src.index('    def configure(event):'):src.index("    app.bind('<Configure>'")]
    assert "_cancel(app, '_resize_after_id')" not in configure_region


def test_diagnostic_reflows_by_breakpoint_not_each_pixel():
    src = read('gui/diagnostic_view.py')
    assert 'def _layout_signature_for(width, height):' in src
    assert "columns = 3 if width >= 1320 else 2 if width >= 830 else 1" in src
    assert 'def on_viewport_settled(self):' in src
    assert 'self.after(24, self._apply_responsive_layout)' not in src
    assert 'signature != self._last_layout_signature' in src


def test_diagnostic_gauge_configure_is_debounced():
    src = read('gui/diagnostic_view.py')
    assert "self.bind('<Configure>', self._schedule_configure_redraw, add='+')" in src
    assert 'self._redraw_after = self.after(72, self._flush_configure_redraw)' in src
    assert "self.bind('<Configure>', lambda _e: self.redraw())" not in src


def test_stable_scroll_defers_heavy_geometry_during_resize():
    src = read('gui/stable_scroll.py')
    assert 'def _window_is_resizing(self):' in src
    assert 'self._pending_canvas_width = width' in src
    assert 'self._schedule_post_resize_geometry()' in src
    assert 'if self._window_is_resizing():' in src


def test_three_two_one_column_result_keeps_all_components():
    src = read('gui/diagnostic_view.py')
    assert "('cpu', 'gpu', 'ram', 'storage', 'battery', 'windows')" in src
    assert 'columns = 3 if width >= 1320 else 2 if width >= 830 else 1' in src
    assert 'self.priority_card.grid_configure(columnspan=columns)' in src
