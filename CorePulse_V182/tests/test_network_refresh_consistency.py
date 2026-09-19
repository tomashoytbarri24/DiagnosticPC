
import pytest
pytest.importorskip("customtkinter", reason="GUI dependency not installed in this validation environment")

import types
import unittest
from unittest.mock import Mock, patch

from core.network_details import NetworkTrafficSampler
from gui.network_detail_panel import NetworkDetailPanel
from tests.test_ui_update_efficiency import Widget


def counters(recv, sent):
    return types.SimpleNamespace(bytes_recv=recv, bytes_sent=sent)


class TrafficTests(unittest.TestCase):
    def test_wall_clock_adjustment_does_not_change_rate(self):
        sampler = NetworkTrafficSampler()
        with patch('core.network_details.time.time', side_effect=[1000., 50.]), \
             patch('core.network_details.time.monotonic', side_effect=[10., 12.]), \
             patch('core.network_details.psutil.net_io_counters', side_effect=[
                 {'eth': counters(100, 200)}, {'eth': counters(1100, 600)}]):
            first = sampler.sample('eth')
            second = sampler.sample('eth')
        self.assertIsNone(first['download_bps'])
        self.assertEqual(second['timestamp'], 50.)
        self.assertEqual(second['download_bps'], 500.)
        self.assertEqual(second['upload_bps'], 200.)

    def test_reset_counter_is_na_then_recovers_from_new_base(self):
        sampler = NetworkTrafficSampler()
        with patch('core.network_details.time.monotonic', side_effect=[1., 2., 3.]), \
             patch('core.network_details.psutil.net_io_counters', side_effect=[
                 {'eth': counters(1000, 1000)}, {'eth': counters(10, 1200)}, {'eth': counters(110, 1300)}]):
            sampler.sample('eth')
            reset = sampler.sample('eth')
            recovered = sampler.sample('eth')
        self.assertIsNone(reset['download_bps'])
        self.assertEqual(reset['upload_bps'], 200.)
        self.assertEqual(recovered['download_bps'], 100.)

    def test_return_from_hidden_page_restarts_baseline(self):
        sampler = NetworkTrafficSampler()
        with patch('core.network_details.time.monotonic', side_effect=[1., 3601., 3602.]), \
             patch('core.network_details.psutil.net_io_counters', side_effect=[
                 {'eth': counters(100, 100)}, {'eth': counters(10000, 10000)}, {'eth': counters(10100, 10200)}]):
            sampler.sample('eth')
            panel = types.SimpleNamespace(_traffic=sampler, _after_id=None)
            NetworkDetailPanel.set_active(panel, False)
            returned = sampler.sample('eth')
            next_sample = sampler.sample('eth')
        self.assertIsNone(returned['download_bps'])
        self.assertEqual(next_sample['download_bps'], 100.)

    def test_unknown_interface_does_not_invent_primary(self):
        with patch('core.network_details.psutil.net_io_counters', return_value={'eth': counters(10, 20)}):
            result = NetworkTrafficSampler().sample(None)
        self.assertIsNone(result['download_bps'])
        self.assertIsNone(result['bytes_recv_total'])


class SpeedResultTests(unittest.TestCase):
    def test_finished_speed_result_avoids_repainting_installation_status(self):
        obj = NetworkDetailPanel.__new__(NetworkDetailPanel)
        obj._apply_ookla_status = Mock()
        obj._apply_speed_servers = Mock()
        obj._speed_progress = {}
        obj._speed_running = False
        obj._speed = {'ok': True, 'provider_key': 'ookla', 'official_engine': True,
                      'download_mbps': 250., 'upload_mbps': 100., 'latency_ms': 10.}
        names = ('speed_progress btn_speed lbl_speed_status lbl_speed_loaded_latency '
                 'lbl_speed_engine lbl_speed_server lbl_speed_isp lbl_speed_compare btn_speed_result').split()
        for name in names:
            setattr(obj, name, Widget())
        obj._speed_labels = {k: (Widget(), Widget()) for k in ('download', 'upload', 'ping', 'jitter', 'loss')}
        obj._speed_server_text = obj._speed_isp_text = obj._speed_compare_text = lambda _: 'Real'
        def writes():
            return sum(getattr(obj, n).writes for n in names) + sum(v[0].writes for v in obj._speed_labels.values())
        obj._apply_speed_test()
        count = writes()
        for _ in range(100):
            obj._apply_speed_test()
        self.assertEqual(writes(), count)
        obj._apply_ookla_status.assert_not_called()
        obj._speed['download_mbps'] = 300.
        obj._apply_speed_test()
        self.assertEqual(obj._speed_labels['download'][0].values['text'], '300.0')
        obj._speed = None
        obj._apply_speed_test()
        obj._apply_ookla_status.assert_called_once()


if __name__ == '__main__':
    unittest.main()
