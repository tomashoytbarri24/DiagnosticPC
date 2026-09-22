import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from core import benchmark_engine as engine
from core import directx_benchmark as dx
from core import directx_scene as scene
from tests import test_v175_benchmark_v12_wallclock_deterministic as timing


class V13Tests(unittest.TestCase):
    def test_temporal_contract_unchanged(self):
        timing.test_v12_standard_keeps_exact_target_wall_times()
        timing.test_v12_camera_and_phase_end_use_wall_clock_not_render_accumulation()
        timing.test_v12_render_present_timing_still_excludes_queries_ui_and_pump()
        timing.test_v12_progress_callback_is_throttled_to_10hz_outside_frametime()
        timing.test_v174_depth_state_hotfix_is_preserved()

    def test_geometry_deterministic_finite_and_indexed(self):
        for builder in (scene.build_jet, scene.build_tree):
            vertices, indices = builder()
            self.assertEqual((vertices, indices), builder())
            self.assertEqual(len(indices) % 3, 0)
            self.assertTrue(all(0 <= index < len(vertices) for index in indices))
            self.assertTrue(all(math.isfinite(value) for row in vertices for value in row))
        vertices, _ = scene.build_jet()
        # Cabina delante y quilla detrás, con nariz +X.
        self.assertTrue(all(v[0] > 0 for v in vertices if v[7] >= 2))
        self.assertTrue(all(v[0] < 0 for v in vertices if v[1] > 2))

    def test_method_and_file_are_separate_from_v12(self):
        self.assertIn('V13_', engine.GPU_METHOD_ID)
        self.assertIn('BENCHMARK_13_', engine.BENCHMARK_METHOD_ID)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            old = root / 'resultados' / 'benchmark_gpu_v12_ultimo_resultado.json'
            old.parent.mkdir()
            old.write_text('previous V12 file', encoding='utf-8')
            with patch.object(engine, 'executable_root', return_value=root):
                # Entrada de prueba de serialización, sin atribuir FPS ficticios al hardware.
                out = engine.save_last_gpu_v13_result({'status': 'OK', 'value': None})
            self.assertEqual(out.name, 'benchmark_gpu_v13_ultimo_resultado.json')
            self.assertIsNone(json.loads(out.read_text(encoding='utf-8'))['value'])
            self.assertEqual(old.read_text(encoding='utf-8'), 'previous V12 file')


if __name__ == '__main__':
    unittest.main()
