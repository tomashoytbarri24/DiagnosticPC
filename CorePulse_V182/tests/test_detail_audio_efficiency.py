"""Presentación con datos controlados: no consulta dispositivos físicos."""

import pytest
pytest.importorskip("customtkinter", reason="GUI dependency not installed in this validation environment")

from collections import defaultdict
import queue
import threading
import types
import unittest
from unittest.mock import Mock, patch

from gui.audio_test_panel import AudioTestPanel
from gui.cpu_detail_panel import CPUDetailPanel
from gui.gpu_detail_panel import GPUDetailPanel
from gui.ram_detail_panel import RAMDetailPanel
from gui.network_detail_panel import NetworkDetailPanel
from gui.health_center_panel import HealthCenterPanel
from tests.test_ui_update_efficiency import Widget


class DetailTests(unittest.TestCase):
    def make(self, cls):
        obj = cls.__new__(cls)
        obj._alive = obj._active = obj._visible = True
        obj._after_id = None
        obj._identity = {}
        obj.frame = types.SimpleNamespace(after=Mock(return_value='timer'), after_cancel=Mock())
        obj.app = types.SimpleNamespace(latest_telemetry={'cpu_usage': 20., 'ram_usage': 35.,
            'ram_used_gb': 7., 'ram_total_gb': 20., 'ram_available_gb': 13.,
            '_cpu': {'hardware': 'CPU real'}})
        obj._is_scrolling = lambda: False
        obj._apply_identity = Mock()
        obj._log_refresh_exception = Mock()
        obj._update_sensor_rows = Mock()
        obj._aggregate_sensor_rows = Mock(return_value=[])
        obj._snapshot_metric_rows = Mock(return_value=[])
        names = ('lbl_title lbl_freshness usage_value usage_detail temp_value temp_detail '
                 'clock_value clock_detail power_value power_detail vram_value vram_detail '
                 'used_value available_value total_value status_value status_detail down_value '
                 'up_value link_value link_detail lbl_source').split()
        for name in names:
            setattr(obj, name, Widget())
        obj._advanced_labels = defaultdict(Widget)
        obj._runtime_labels = defaultdict(Widget)
        obj._traffic_labels = defaultdict(Widget)
        return obj

    def writes(self, obj):
        return sum(w.writes for w in vars(obj).values() if isinstance(w, Widget)) + sum(
            w.writes for name in ('_advanced_labels', '_runtime_labels', '_traffic_labels')
            for w in getattr(obj, name).values())

    def test_cpu_ram_and_gpu_repeat_only_changed_values(self):
        for cls in (CPUDetailPanel, RAMDetailPanel, GPUDetailPanel):
            with self.subTest(panel=cls.__name__):
                obj = self.make(cls)
                gpu = {'name': 'GPU real', 'usage_percent': 42.}
                obj._gpu_list = lambda _: [gpu]
                obj._selected_index = 0
                obj._select_initial_index = Mock()
                obj._update_selector = Mock()
                obj._apply_static_rows = Mock()
                obj.refresh()
                initial = self.writes(obj)
                self.assertGreater(initial, 5)
                for _ in range(100):
                    obj.refresh()
                self.assertEqual(self.writes(obj), initial)
                if cls is GPUDetailPanel:
                    gpu['usage_percent'] = 80.
                else:
                    obj.app.latest_telemetry['cpu_usage' if cls is CPUDetailPanel else 'ram_usage'] = 80.
                obj.refresh()
                self.assertIn('80', obj.usage_value.values['text'])
                self.assertGreater(self.writes(obj), initial)
                obj._log_refresh_exception.assert_not_called()

    def test_gpu_absence_still_schedules_next_sample_and_can_recover(self):
        obj = self.make(GPUDetailPanel)
        obj._gpu_list = Mock(return_value=[])
        obj._selected_index = None
        obj._select_initial_index = Mock()
        obj._update_selector = Mock()
        obj.refresh()
        self.assertEqual(obj.usage_value.values['text'], 'N/A')
        obj.frame.after.assert_called_once()
        obj._gpu_list.return_value = [{'name': 'GPU', 'usage_percent': 0.}]
        obj._selected_index = 0
        obj._apply_static_rows = Mock()
        obj.refresh()
        self.assertEqual(obj.usage_value.values['text'], '0.0%')
        obj._log_refresh_exception.assert_not_called()

    def test_network_preserves_real_sampling_without_rewriting_identical_text(self):
        obj = self.make(NetworkDetailPanel)
        obj._request_identity = Mock()
        obj._primary = lambda: {'name': 'Ethernet', 'is_up': True, 'link_speed_mbps': 1000.}
        obj._traffic = types.SimpleNamespace(sample=Mock(return_value={'download_bps': 1024.}))
        obj._apply_speed_test = obj._apply_diag = Mock()
        obj.refresh()
        initial = self.writes(obj)
        for _ in range(100):
            obj.refresh()
        self.assertEqual(obj._traffic.sample.call_count, 101)
        self.assertEqual(self.writes(obj), initial)
        self.assertGreater(initial, 8)
        obj._traffic.sample.return_value = {'download_bps': 2048.}
        obj.refresh()
        self.assertGreater(self.writes(obj), initial)


class AudioPollingTests(unittest.TestCase):
    def panel(self):
        obj = types.SimpleNamespace(closed=False, busy=False, _poll_id=None,
            events=queue.Queue(), level=Widget(), level_text=Widget(), status=Widget(),
            question=Widget(), actions=[], answers=[], update_state=Mock(),
            after=Mock(return_value='poll'), service=types.SimpleNamespace(cancel=threading.Event(), pending=None))
        obj.poll = types.MethodType(AudioTestPanel.poll, obj)
        obj.run = types.MethodType(AudioTestPanel.run, obj)
        return obj

    def test_idle_does_not_schedule_timer(self):
        obj = self.panel()
        obj.poll()
        obj.after.assert_not_called()

    def test_busy_poll_rearms_and_completion_stops(self):
        obj = self.panel()
        obj.busy = True
        obj.poll()
        obj.after.assert_called_once()
        obj.after.reset_mock()
        obj.events.put(('done', 'record'))
        obj.poll()
        obj.after.assert_not_called()
        self.assertFalse(obj.busy)
        obj.update_state.assert_called_once()

    def test_level_burst_has_bounded_work_and_one_write_per_batch(self):
        obj = self.panel()
        for i in range(300):
            obj.events.put(('level', i / 300.))
        obj.poll()
        self.assertEqual(obj.events.qsize(), 172)
        self.assertEqual(obj.level.writes, 1)
        obj.poll()
        obj.poll()
        self.assertTrue(obj.events.empty())
        self.assertEqual(obj.level.writes, 3)
        self.assertAlmostEqual(obj.level.value, 299 / 300.)

    def test_explicit_action_starts_worker_and_resumes_polling(self):
        obj = self.panel()
        ready = threading.Event()
        obj.run(ready.set, 'refresh')
        self.assertTrue(ready.wait(1))
        obj.after.assert_called_once()
        obj.poll()
        self.assertFalse(obj.busy)
        obj.after.reset_mock()
        obj.run(lambda: None, 'refresh')
        obj.after.assert_called_once()

    def test_closed_panel_does_not_start_worker_or_timer(self):
        obj = self.panel()
        obj.closed = True
        work = Mock()
        obj.run(work, 'refresh')
        obj.poll()
        work.assert_not_called()
        obj.after.assert_not_called()


class InitialGamingViewTests(unittest.TestCase):
    def test_requested_section_is_set_before_first_render(self):
        for section in ('home', 'library', 'stability', 'boost', 'invalid'):
            rendered = []
            def build(obj):
                obj.frame = types.SimpleNamespace(after_idle=Mock())
            with patch.object(HealthCenterPanel, '_seed_preloaded_battery_state'), \
                 patch.object(HealthCenterPanel, '_build', build), \
                 patch.object(HealthCenterPanel, '_render', lambda obj: rendered.append(obj._performance_section)), \
                 patch.object(HealthCenterPanel, '_schedule_performance_status_tick'):
                HealthCenterPanel(types.SimpleNamespace(), None, performance_only=True,
                                  initial_performance_section=section)
            self.assertEqual(rendered, ['home' if section == 'invalid' else section])


if __name__ == '__main__':
    unittest.main()
