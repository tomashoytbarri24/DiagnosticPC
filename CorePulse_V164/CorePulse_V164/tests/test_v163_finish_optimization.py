from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from performance import power_manager as pm
from tests.test_managed_power_plans import Windows
from core.network_details import NetworkTrafficSampler


class FinishOptimizationTests(unittest.TestCase):
    def test_power_plan_reuses_same_guid_across_100_manager_restarts(self):
        with tempfile.TemporaryDirectory() as td:
            registry = Path(td) / 'plans.json'
            windows = Windows()
            first = None
            for _ in range(100):
                manager = pm.PowerManager(windows, registry_path=registry)
                manager.available = lambda: True
                result = manager.ensure_owned_profile('Game')
                self.assertTrue(result['success'], result)
                self.assertTrue(result.get('duplicate_guard'))
                if first is None:
                    first = result['guid']
                    self.assertTrue(result['created'])
                else:
                    self.assertEqual(result['guid'], first)
                    self.assertFalse(result['created'])
                    self.assertTrue(result['reused'])
            self.assertEqual(windows.count('/duplicatescheme'), 1)
            self.assertEqual(list(windows.plans.values()).count('CorePulse Game'), 1)

    def test_existing_exact_corepulse_plan_blocks_new_duplicate_if_not_verifiable(self):
        with tempfile.TemporaryDirectory() as td:
            registry = Path(td) / 'plans.json'
            windows = Windows()
            legacy = '11111111-2222-3333-4444-555555555555'
            windows.plans[legacy] = 'CorePulse Game'
            # Make it intentionally incompatible with both base and legacy profile.
            windows.settings(legacy)[pm.PERF_EPP] = [77, 77]
            windows.settings(pm.HIGH_PERFORMANCE_GUID)[pm.PERF_EPP] = [0, 0]
            manager = pm.PowerManager(windows, registry_path=registry)
            manager.available = lambda: True
            result = manager.ensure_owned_profile('Game')
            self.assertFalse(result['success'])
            self.assertEqual(windows.count('/duplicatescheme'), 0)
            self.assertIn(legacy, windows.plans)

    def test_network_rate_uses_monotonic_clock_not_wall_clock(self):
        class Counters:
            def __init__(self, recv, sent):
                self.bytes_recv = recv; self.bytes_sent = sent
                self.packets_recv = self.packets_sent = 0
                self.errin = self.errout = self.dropin = self.dropout = 0
        sampler = NetworkTrafficSampler()
        snapshots = [
            {'Ethernet': Counters(1000, 2000)},
            {'Ethernet': Counters(3000, 5000)},
        ]
        with patch('core.network_details.psutil.net_io_counters', side_effect=snapshots), \
             patch('core.network_details.time.time', side_effect=[1000.0, 100.0]), \
             patch('core.network_details.time.monotonic', side_effect=[10.0, 12.0]):
            first = sampler.sample('Ethernet')
            second = sampler.sample('Ethernet')
        self.assertIsNone(first['download_bps'])
        self.assertEqual(second['download_bps'], 1000.0)
        self.assertEqual(second['upload_bps'], 1500.0)
        # Timestamp may move backwards; rate remains correct because elapsed is monotonic.
        self.assertEqual(second['timestamp'], 100.0)

    def test_network_panel_lazily_starts_connectivity_tools(self):
        text = Path('gui/network_detail_panel.py').read_text(encoding='utf-8')
        start = text.index('    def _start_runtime(self):')
        end = text.index('    def set_active', start)
        block = text[start:end]
        self.assertNotIn('_request_ookla_status()', block)
        self.assertNotIn('_request_speed_servers()', block)
        self.assertIn("if key == 'connectivity':", text)
        self.assertIn('self._ensure_connectivity_runtime()', text)

    def test_cached_hidden_panels_skip_explicit_refresh(self):
        gaming = Path('gui/gaming_panel.py').read_text(encoding='utf-8')
        health = Path('gui/health_center_panel.py').read_text(encoding='utf-8')
        self.assertIn('if not self._alive or not self._visible:', gaming[gaming.index('    def refresh(self):'):])
        self.assertIn('if not self._alive or not self._visible:', health[health.index('    def refresh(self):'):])


if __name__ == '__main__':
    unittest.main()
