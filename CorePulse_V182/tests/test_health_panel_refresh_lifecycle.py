"""Refresco real de paneles con scheduler controlado, sin abrir Tk ni sensores."""

import pytest
pytest.importorskip("customtkinter", reason="GUI dependency not installed in this validation environment")

import threading
import types
import unittest
from unittest.mock import Mock

from gui.health_center_panel import HealthCenterPanel
from tests.test_ui_update_efficiency import Widget


class Scheduler:
    def __init__(self):
        self.pending = {}
        self.counter = 0
        self.ready = threading.Event()

    def after(self, delay, callback):
        self.counter += 1
        token = str(self.counter)
        self.pending[token] = callback
        self.ready.set()
        return token

    def after_cancel(self, token):
        self.pending.pop(token, None)

    def flush(self):
        callbacks = list(self.pending.values())
        self.pending.clear()
        for callback in callbacks:
            callback()


def panel():
    obj = HealthCenterPanel.__new__(HealthCenterPanel)
    obj.app = Scheduler()
    obj._alive = obj._visible = True
    obj._tab = 'performance'
    obj._performance_section = 'home'
    obj._performance_only = True
    obj._benchmark_only = False
    obj._performance_after_id = None
    obj._render_after_id = None
    obj._rendering = obj._render_pending = False
    obj._render_pending_direct = obj._reset_scroll_on_render = False
    obj._dirty_tabs = set()
    obj._jobs = set()
    obj._last_performance_generation = 3
    obj._gaming_metric_labels = {k: Widget() for k in ('FPS', 'CPU', 'GPU', 'RAM')}
    obj._gaming_live_snapshot = Mock(return_value={'cpu_usage': 24., 'fps': 60.})
    obj.scroll = types.SimpleNamespace(is_scrolling=lambda: False)
    obj.frame = types.SimpleNamespace(winfo_exists=lambda: True)
    obj._schedule_performance_status_tick = Mock()
    obj._render = Mock(side_effect=lambda: obj._dirty_tabs.discard(obj._tab))
    return obj


class PanelRefreshTests(unittest.TestCase):
    def actual_renderer(self):
        obj = panel()
        obj._render = types.MethodType(HealthCenterPanel._render, obj)
        obj._finalize_render = types.MethodType(HealthCenterPanel._finalize_render, obj)
        obj._capture_scroll_fraction = lambda: .75
        obj._clear = Mock()
        obj.body = types.SimpleNamespace(update_idletasks=Mock())
        obj.scroll._refresh_geometry = Mock()
        obj.scroll._flush_repaint = Mock()
        obj.scroll.canvas = types.SimpleNamespace(yview_moveto=Mock())
        obj.app.after_idle = lambda cb: obj.app.after(0, cb)
        for name in ('summary', 'audio', 'battery', 'performance', 'windows', 'repair', 'history', 'recovery', 'corepulse_diagnostics'):
            setattr(obj, '_render_' + name, Mock())
        return obj

    def test_explicit_audio_navigation_during_render_is_not_lost(self):
        obj = self.actual_renderer()
        obj._render()
        obj._tab = 'audio'
        obj._reset_scroll_on_render = True
        obj._render()
        obj._render_audio.assert_not_called()
        obj.app.flush()
        obj._render_audio.assert_called_once()
        obj.app.flush()
        self.assertFalse(obj._rendering)
        self.assertEqual(obj.scroll.canvas.yview_moveto.call_args.args, (0.,))

    def test_dynamic_refresh_preserves_scroll_navigation_resets_it(self):
        obj = self.actual_renderer()
        obj._render()
        obj.app.flush()
        self.assertEqual(obj.scroll.canvas.yview_moveto.call_args.args, (.75,))
        obj._select_performance_section('library')
        obj.app.flush()
        self.assertEqual(obj.scroll.canvas.yview_moveto.call_args.args, (0.,))

    def test_scroll_deferred_refresh_cannot_rebuild_another_tab(self):
        obj = panel()
        deferred = []
        obj.scroll.is_scrolling = lambda: True
        obj.scroll.defer_until_idle = lambda cb, **_: deferred.append(cb)
        obj._request_render()
        obj._tab = 'battery'
        obj.scroll.is_scrolling = lambda: False
        deferred[0]()
        self.assertFalse(obj.app.pending)
        self.assertNotIn('battery', obj._dirty_tabs)

    def test_metrics_advance_without_generation_change_or_page_rebuild(self):
        obj = panel()
        obj.app.performance_manager = types.SimpleNamespace(status=lambda: {'generation': 3})
        for _ in range(100):
            obj._performance_status_tick()
        self.assertEqual(sum(w.writes for w in obj._gaming_metric_labels.values()), 4)
        obj._gaming_live_snapshot.return_value['cpu_usage'] = 75.
        obj._performance_status_tick()
        self.assertIn('75%', obj._gaming_metric_labels['CPU'].values['text'])
        self.assertEqual(sum(w.writes for w in obj._gaming_metric_labels.values()), 5)
        obj._render.assert_not_called()
        self.assertFalse(obj.app.pending)

    def test_unavailable_metrics_remain_na(self):
        obj = panel()
        values = obj._gaming_metric_values({})
        self.assertTrue(all(text == 'N/A' for _, text, _ in values))
        obj._gaming_live_snapshot.return_value = {'ram_usage': 0.}
        obj._refresh_gaming_home_metrics()
        self.assertEqual(obj._gaming_metric_labels['RAM'].values['text'], '0%')

    def test_hidden_updates_coalesce_until_page_is_visible(self):
        obj = panel()
        obj.set_active(False)
        for _ in range(100):
            obj._request_render(1)
        self.assertFalse(obj.app.pending)
        obj.set_active(True)
        self.assertEqual(len(obj.app.pending), 1)
        obj.app.flush()
        obj._render.assert_called_once()
        self.assertFalse(obj._dirty_tabs)

    def test_pending_render_cancelled_on_hide_and_reissued_on_return(self):
        obj = panel()
        obj._request_render(1)
        obj.set_active(False)
        obj.app.flush()
        obj._render.assert_not_called()
        obj.set_active(True)
        obj.app.flush()
        obj._render.assert_called_once()

    def test_old_render_cannot_destroy_audio_after_navigation(self):
        obj = panel()
        obj._request_render(1)
        obj._tab = 'audio'
        obj.app.flush()
        obj._render.assert_not_called()
        self.assertIn('performance', obj._dirty_tabs)

    def test_actual_async_completion_while_hidden_is_applied_on_return(self):
        obj = panel()
        obj.set_active(False)
        received = []
        obj._async('inventory', lambda: {'ready': True}, lambda result, error: received.append(result))
        self.assertTrue(obj.app.ready.wait(1))
        obj.app.flush()
        self.assertEqual(received, [{'ready': True}])
        self.assertNotIn('inventory', obj._jobs)
        obj._render.assert_not_called()
        obj.set_active(True)
        obj.app.flush()
        obj._render.assert_called_once()

    def test_completion_for_another_tab_does_not_rebuild_current_tab(self):
        obj = panel()
        obj._async('inventory', lambda: {}, lambda *_: None)
        self.assertTrue(obj.app.ready.wait(1))
        obj._tab = 'battery'
        obj.app.flush()
        obj._render.assert_not_called()
        self.assertIn('performance', obj._dirty_tabs)

    def test_new_tab_update_not_lost_behind_old_callback(self):
        obj = panel()
        obj._request_render(1)
        obj._tab = 'battery'
        obj._request_render(1)
        obj.app.flush()
        obj.app.flush()
        obj._render.assert_called_once()
        self.assertNotIn('battery', obj._dirty_tabs)

    def test_same_section_keeps_widgets_changed_section_renders(self):
        obj = panel()
        obj._select_performance_section('home')
        obj._render.assert_not_called()
        obj._select_performance_section('library')
        obj._render.assert_called_once()
        self.assertEqual(obj._performance_section, 'library')

    def test_hidden_or_other_section_never_updates_home_widgets(self):
        obj = panel()
        obj._visible = False
        obj._refresh_gaming_home_metrics()
        obj._visible = True
        obj._performance_section = 'library'
        obj._refresh_gaming_home_metrics()
        obj._gaming_live_snapshot.assert_not_called()

    def test_profile_change_signals_busy_before_worker_finishes(self):
        obj = panel()
        obj.app.performance_manager = types.SimpleNamespace(set_mode=Mock())
        def start(name, fn, done, on_started=None):
            obj._jobs.add(name)
            on_started()
        obj._async = start
        obj._apply_performance_mode('BALANCED')
        self.assertIn('profile_change', obj._jobs)
        self.assertEqual(len(obj.app.pending), 1)
        obj.app.flush()
        obj._render.assert_called_once()


if __name__ == '__main__':
    unittest.main()
