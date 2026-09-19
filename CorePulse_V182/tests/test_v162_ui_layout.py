
import pytest
pytest.importorskip("customtkinter", reason="GUI dependency not installed in this validation environment")

import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from gui.overlay_config_panel import OverlayConfigPanel
from tests.test_v159_resize_ownership import fresh_guard, Widget

ROOT = Path(__file__).resolve().parents[1]


class ScheduledWindow:
    def __init__(self):
        self.jobs = {}
        self.serial = 0
    def after(self, delay, callback):
        self.serial += 1
        self.jobs[self.serial] = callback
        return self.serial
    def after_cancel(self, ident):
        self.jobs.pop(ident, None)
    def frame(self):
        jobs, self.jobs = self.jobs, {}
        for callback in jobs.values():
            callback()


class LayoutTests(unittest.TestCase):
    def panel(self, width, scale=1):
        panel = object.__new__(OverlayConfigPanel)
        panel._alive = panel._visible = True
        panel._responsive_after_id = None
        panel._metrics_columns = panel._layout_mode = panel._controls_columns = None
        panel.app = SimpleNamespace(is_resizing=False)
        panel.root = Mock()
        panel.root.winfo_width.return_value = width
        panel.root._reverse_widget_scaling.side_effect = lambda value: value / scale
        for name in ('metrics_grid', 'overview', 'metrics', 'preview_card', 'visual', 'body', '_controls_grid', 'hotkey_hint'):
            setattr(panel, name, Mock())
        panel._metric_cards = [Mock() for _ in range(7)]
        panel._control_sections = [Mock() for _ in range(4)]
        return panel

    def test_single_column_uses_all_space(self):
        panel = self.panel(480)
        panel._apply_responsive_layout()
        self.assertEqual(panel._metrics_columns, 1)
        panel.metrics_grid.grid_columnconfigure.assert_any_call(1, weight=0, minsize=0, uniform='')
        self.assertEqual(panel._metric_cards[-1].grid.call_args.kwargs['row'], 6)
        self.assertEqual(panel._controls_columns, 1)

    def test_wide_overlay_and_restore_keep_widgets(self):
        panel = self.panel(1400)
        panel._apply_responsive_layout()
        self.assertEqual(panel._layout_mode, 'columns')
        self.assertEqual(panel._metrics_columns, 2)
        self.assertEqual(panel.preview_card.grid.call_args.kwargs['column'], 1)
        panel.root.winfo_width.return_value = 700
        panel._apply_responsive_layout()
        self.assertEqual(panel._layout_mode, 'stacked')
        self.assertEqual(panel.preview_card.grid.call_args.kwargs['column'], 0)
        for card in panel._metric_cards:
            card.grid_forget.assert_not_called()
            card.destroy.assert_not_called()

    def test_breakpoints_respect_dpi_and_skip_identical_layout(self):
        panel = self.panel(1400, 2)
        panel._apply_responsive_layout()
        self.assertEqual(panel._layout_mode, 'stacked')
        calls = panel.metrics.grid.call_count
        panel._apply_responsive_layout()
        self.assertEqual(panel.metrics.grid.call_count, calls)

    def test_resize_defers_layout_then_retries(self):
        panel = self.panel(1400)
        panel.app.is_resizing = True
        panel._apply_responsive_layout()
        panel.metrics.grid.assert_not_called()
        callback = panel.root.after.call_args.args[1]
        panel.app.is_resizing = False
        callback()
        self.assertEqual(panel._layout_mode, 'columns')

    def test_frame_redraw_occurs_before_resize_ends(self):
        guard = fresh_guard()
        from customtkinter.windows.widgets.core_widget_classes.ctk_base_class import CTkBaseClass
        guard._original_update_dimensions_event = getattr(CTkBaseClass, '_corepulse_resize_guard_original', CTkBaseClass._update_dimensions_event)
        owner = ScheduledWindow()
        widget = Widget(owner)
        guard.set_active(True, owner=owner)
        for width in range(100, 200):
            guard._patched_update_dimensions_event(widget, SimpleNamespace(width=width, height=50))
        self.assertEqual(len(owner.jobs), 1)
        self.assertEqual(len(widget.draws), 0)
        owner.frame()
        self.assertTrue(guard.is_active(owner))
        self.assertEqual(widget.draws[-1][:2], (199, 50))
        guard._patched_update_dimensions_event(widget, SimpleNamespace(width=300, height=50))
        guard.release(owner)
        self.assertFalse(owner.jobs)
        self.assertEqual(guard.pending_count(), 0)

    def test_public_benchmark_has_only_standard_mode(self):
        source = (ROOT/'gui/health_center_panel.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        methods = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
        render = ast.get_source_segment(source, methods['_render_gaming_benchmark_section'])
        self.assertNotIn('Intensidad', render)
        self.assertNotIn('CTkSegmentedButton', render)
        run = ast.get_source_segment(source, methods['_run_visual_benchmark'])
        self.assertIn("profile_key = 'standard'", run)
        self.assertNotIn('run_stress', run)


if __name__ == '__main__':
    unittest.main()
