import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import benchmark_engine
from core.benchmark_presentation import benchmark_card_data, benchmark_component_conclusion
from core.diagnostic_evidence import gpu_for_renderer
from core.version import VERSION, STAGE


class MethodologyTests(unittest.TestCase):
    def test_version_and_method_ids(self):
        self.assertEqual(VERSION, '162')
        self.assertEqual(STAGE, 'BENCHMARK_2_0_METHOD_CONSISTENCY')
        self.assertEqual(benchmark_engine.BENCHMARK_METHOD_ID, 'COREPULSE_BENCHMARK_2')
        self.assertEqual(benchmark_engine.GPU_METHOD_ID, 'COREPULSE_GPU_VISUAL_MULTIPHASE_V2')

    def test_renderer_suffix_maps_only_to_unique_gpu(self):
        rows = [
            {'name': 'Intel(R) UHD Graphics', 'temperature_c': 48},
            {'name': 'NVIDIA GeForce RTX 3060 Laptop GPU', 'temperature_c': 71},
        ]
        match = gpu_for_renderer(rows, 'NVIDIA GeForce RTX 3060 Laptop GPU/PCIe/SSE2')
        self.assertEqual(match.get('temperature_c'), 71)
        ambiguous = rows + [{'name': 'NVIDIA GeForce RTX 3060 Laptop GPU', 'temperature_c': 72}]
        self.assertEqual(gpu_for_renderer(ambiguous, 'NVIDIA GeForce RTX 3060 Laptop GPU/PCIe/SSE2'), {})

    def test_suite_gpu_uses_visual_multiphase_contract(self):
        def visual(profile, **kwargs):
            kwargs['progress_callback'](0.5, 'GPU visual', 'medición')
            return {
                'status': 'OK', 'provider': 'CorePulse Visual Hardware Benchmark · Multi-phase',
                'duration_s': 2.0, 'renderer': 'NVIDIA GeForce RTX 3060 Laptop GPU/PCIe/SSE2',
                'vendor': 'NVIDIA', 'gl_version': 'test', 'frames': 120,
                'frames_per_s': 60.0, 'one_percent_low_fps': 48.0,
                'frametime_avg_ms': 16.6, 'phase_count': 6, 'measured_phase_count': 6,
                'phases': [{'key': 'geometry', 'status': 'OK'}], 'resolution': '1440x810',
                'telemetry': {'sample_count': 1},
            }
        snapshot = {
            'cpu_usage': 20, 'ram_usage': 40,
            '_gpus': [
                {'name': 'Intel(R) UHD Graphics', 'temperature_c': 49, 'usage_percent': 5},
                {'name': 'NVIDIA GeForce RTX 3060 Laptop GPU', 'temperature_c': 71, 'usage_percent': 88, 'core_clock_mhz': 1800},
            ],
        }
        with patch('core.visual_benchmark.run_visual_benchmark', side_effect=visual):
            result = benchmark_engine.run_benchmark_suite('quick', ['gpu'], telemetry_sampler=lambda: snapshot)
        self.assertEqual(result['status'], 'OK')
        self.assertEqual(result['benchmark_method'], 'COREPULSE_BENCHMARK_2')
        gpu = result['gpu']
        self.assertEqual(gpu['benchmark_method'], 'COREPULSE_GPU_VISUAL_MULTIPHASE_V2')
        self.assertEqual(gpu['unit'], 'FPS')
        self.assertEqual(gpu['value'], 60.0)
        self.assertEqual(gpu['fps_1pct_low'], 48.0)
        self.assertEqual(gpu['telemetry']['gpu_temp']['max'], 71)
        self.assertTrue(gpu['telemetry']['gpu_sensor_match'])

    def test_ssd_fallback_is_explicitly_cacheable(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(benchmark_engine.platform, 'system', return_value='Linux'), \
             patch.object(benchmark_engine, '_adaptive_ssd_size', return_value=4):
            result = benchmark_engine.benchmark_ssd(tmp, 4)
        self.assertEqual(result['status'], 'OK')
        self.assertEqual(result['benchmark_method'], benchmark_engine.SSD_METHOD_ID)
        self.assertEqual(result['io_mode'], 'BUFFERED_FALLBACK')
        self.assertFalse(result['cache_resistant'])
        self.assertGreater(result['write_mbps'], 0)
        self.assertGreater(result['read_mbps'], 0)

    def test_ram_presentation_is_copy_rate_not_theoretical_bandwidth(self):
        card = benchmark_card_data('ram', {'status': 'OK', 'value': 8000, 'unit': 'MB/s', 'duration_s': 8})
        self.assertIn('copia sostenida', card['subtitle'].lower())
        self.assertIn('no equivale', card['meaning'].lower())
        conclusion, tone = benchmark_component_conclusion('ram', {'ram': {'status': 'OK', 'value': 8000}}, {'available': True, 'deltas': {'ram_usage': {'after': 99}}})
        self.assertIn('Diagnóstico interpreta', conclusion)
        self.assertEqual(tone, 'cyan')

    def test_history_source_requires_method_equivalence(self):
        source = Path('gui/benchmark_history_panel.py').read_text(encoding='utf-8')
        self.assertIn('LEGACY_UNVERSIONED', source)
        self.assertIn('if pa != pb or ca != cb or ma != mb', source)
        self.assertIn("if 'SSD' in ca and (va != vb or ia != ib)", source)

    def test_complete_diagnostic_has_no_automatic_stress(self):
        source = Path('core/complete_diagnostic.py').read_text(encoding='utf-8')
        run_block = source[source.index('def run_complete_diagnostic('):]
        self.assertNotIn('run_stress_suite(', run_block)
        self.assertIn("'automatic_stress': False", run_block)
        self.assertIn("'benchmark_method_versioned': True", run_block)


class CompleteDiagnosticV162Tests(unittest.TestCase):
    def _base(self):
        return {'session_valid': True, 'sample_count': 20, 'duration_seconds': 20,
                'overall_status': 'NORMAL', 'findings': [], 'statistics': {}}

    def _snapshot(self):
        return {'cpu_usage': 25, 'cpu_temp': 65, 'cpu_ghz': 4.0, 'ram_usage': 35,
                '_gpus': [{'name': 'NVIDIA GeForce RTX 3060 Laptop GPU', 'usage_percent': 85,
                           'temperature_c': 70, 'core_clock_mhz': 1750}],
                '_storage_devices': [{'name': 'Drive', 'temperature_c': 42, 'mount_points': ['C:\\']}]}

    def test_complete_diagnostic_uses_visual_gpu_and_finishes(self):
        from core import complete_diagnostic as diag
        def generic(kind):
            def run(*args, **kwargs):
                kwargs['progress_callback'](0.5, kind.upper(), 'medido')
                base = {'kind': kind.upper(), 'status': 'OK', 'value': 1000, 'unit': 'MB/s', 'duration_s': 1,
                        'throughput_mbps': 1000, 'benchmark_method': getattr(benchmark_engine, kind.upper() + '_METHOD_ID')}
                if kind == 'ssd': base.update(read_mbps=1200, write_mbps=800, path_root='C:\\', io_mode='WINDOWS_NO_BUFFERING_WRITE_THROUGH', cache_resistant=True)
                return base
            return run
        def visual(profile, **kwargs):
            kwargs['progress_callback'](0.5, 'GPU', 'visual')
            return {'status': 'OK', 'provider': 'CorePulse Visual Hardware Benchmark · Multi-phase', 'duration_s': 2,
                    'renderer': 'NVIDIA GeForce RTX 3060 Laptop GPU/PCIe/SSE2', 'frames_per_s': 72,
                    'one_percent_low_fps': 55, 'phase_count': 6, 'measured_phase_count': 6, 'phases': [], 'telemetry': {}}
        windows = {'count': 0, 'items': [], 'severity': 'NORMAL', 'device_problems': 0}
        with patch.object(benchmark_engine, 'benchmark_cpu', side_effect=generic('cpu')), \
             patch.object(benchmark_engine, 'benchmark_ram', side_effect=generic('ram')), \
             patch.object(benchmark_engine, 'benchmark_ssd', side_effect=generic('ssd')), \
             patch('core.visual_benchmark.run_visual_benchmark', side_effect=visual), \
             patch.object(diag, 'collect_battery_health', return_value={'present': False}), \
             patch.object(diag, 'analyze_startup', return_value=windows), \
             patch.object(diag, 'analyze_services', return_value=windows), \
             patch.object(diag, 'analyze_crashes', return_value=windows), \
             patch.object(diag, 'analyze_drivers', return_value=windows), \
             patch.object(diag, 'run_stress_suite', side_effect=AssertionError('stress no debe ejecutarse')):
            result = diag.run_complete_diagnostic(self._base(), self._snapshot(), [], telemetry_sampler=self._snapshot)
        block = result['complete_diagnostic']
        self.assertTrue(block['finalized'])
        self.assertEqual(block['version'], '4.1-v162')
        self.assertEqual(block['benchmark']['benchmark_method'], 'COREPULSE_BENCHMARK_2')
        self.assertEqual(block['benchmark']['gpu']['unit'], 'FPS')
        self.assertEqual(block['benchmark']['gpu']['value'], 72)
        self.assertEqual(block['benchmark']['gpu']['telemetry']['gpu_temp']['max'], 70)

    def test_cancel_during_visual_gpu_keeps_result_unfinalized(self):
        from core import complete_diagnostic as diag
        event = __import__('threading').Event()
        def generic(kind):
            def run(*args, **kwargs):
                kwargs['progress_callback'](0.5, kind, 'ok')
                data = {'status': 'OK', 'value': 1, 'unit': 'MB/s', 'duration_s': .1, 'benchmark_method': 'test'}
                if kind == 'ssd': data.update(path_root='C:\\', read_mbps=1, write_mbps=1)
                return data
            return run
        def visual(profile, **kwargs):
            kwargs['progress_callback'](0.2, 'GPU', 'antes de cancelar')
            event.set()
            self.assertTrue(kwargs['cancel_check']())
            return {'status': 'CANCELLED', 'duration_s': .1, 'renderer': 'NVIDIA GeForce RTX 3060 Laptop GPU',
                    'frames_per_s': None, 'one_percent_low_fps': None, 'phase_count': 6, 'measured_phase_count': 1, 'phases': []}
        windows = {'count': 0, 'items': [], 'severity': 'NORMAL', 'device_problems': 0}
        with patch.object(benchmark_engine, 'benchmark_cpu', side_effect=generic('cpu')), \
             patch.object(benchmark_engine, 'benchmark_ram', side_effect=generic('ram')), \
             patch.object(benchmark_engine, 'benchmark_ssd', side_effect=generic('ssd')), \
             patch('core.visual_benchmark.run_visual_benchmark', side_effect=visual), \
             patch.object(diag, 'collect_battery_health', return_value={'present': False}), \
             patch.object(diag, 'analyze_startup', return_value=windows), patch.object(diag, 'analyze_services', return_value=windows), \
             patch.object(diag, 'analyze_crashes', return_value=windows), patch.object(diag, 'analyze_drivers', return_value=windows):
            result = diag.run_complete_diagnostic(self._base(), self._snapshot(), [], telemetry_sampler=self._snapshot, cancel_check=event.is_set)
        self.assertEqual(result['complete_diagnostic']['status'], 'CANCELLED')
        self.assertFalse(result['complete_diagnostic']['finalized'])
        self.assertFalse(result['complete_diagnostic']['pdf_optional'])


class ProtectedHashes(unittest.TestCase):
    EXPECTED = {
        'core/runtime_venv_path.py': '263d725dc8a50ef57d2e0dd8d8827968f58d2b67dcee6b0a276ca6dd8d562e92',
        'bootstrap_corepulse.py': '925d4ef090b28c27ceffbbbba9362a8137f665212ac445e96a096c0ce5e17a0b',
        'core/source_runtime_bootstrap.py': 'bde37780c35ebc280b0b22ac6a71926051ae9fde48b65935b6af64b819f7ccfd',
        'requirements-runtime-lock.txt': '36ee044c5dab3c5c8cfecbe0456923c9f406d83a93ef04d93f9fd27f1566c706',
        'core/nvme_smart_windows.py': 'fe9481d270d5b47299b97fc97d37ee56f65bd904333f634255e4a91e63958283',
    }
    def test_hashes_unchanged(self):
        for name, expected in self.EXPECTED.items():
            with self.subTest(name=name):
                self.assertEqual(hashlib.sha256(Path(name).read_bytes()).hexdigest(), expected)


if __name__ == '__main__':
    unittest.main()
