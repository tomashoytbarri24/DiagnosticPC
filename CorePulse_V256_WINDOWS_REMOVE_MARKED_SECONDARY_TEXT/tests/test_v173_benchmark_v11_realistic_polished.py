from __future__ import annotations

import inspect
import math

from core import benchmark_engine, version
from core import directx_benchmark as dx
from core.directx_scene import WATER_RESOLUTION, build_cloud, build_tree, build_water, level_workload, profile_levels


def _valid_mesh(v, i):
    return bool(v) and bool(i) and len(i) % 3 == 0 and min(i) >= 0 and max(i) < len(v)


def test_v173_version_and_method_ids_are_new():
    assert version.VERSION == '173'
    assert benchmark_engine.BENCHMARK_METHOD_ID == 'COREPULSE_BENCHMARK_11_REALISTIC_POLISHED_GPU_TIMESTAMP'
    assert benchmark_engine.GPU_METHOD_ID == 'COREPULSE_GPU_DIRECTX11_SCENES_V11_REALISTIC_POLISHED'


def test_v11_profile_preserves_49_seconds_of_measured_render():
    levels = profile_levels('standard')
    assert [x.key for x in levels] == ['valley', 'forest', 'lake', 'extreme']
    assert math.isclose(sum(x.measure_seconds for x in levels), 49.0, abs_tol=1e-9)
    assert math.isclose(sum(x.warmup_seconds + x.settle_seconds + x.measure_seconds for x in levels), 58.0, abs_tol=1e-9)


def test_v11_tree_water_and_cloud_meshes_are_real_geometry():
    tv, ti = build_tree(); wv, wi = build_water(); cv, ci = build_cloud()
    assert _valid_mesh(tv, ti) and len(ti) // 3 >= 300
    assert _valid_mesh(wv, wi) and WATER_RESOLUTION == 192 and len(wi) // 3 >= 70000
    assert _valid_mesh(cv, ci) and len(ci) // 3 >= 50
    # Cloud V11 is made from cards, not rock spheres: every four vertices make a quad.
    assert len(cv) % 4 == 0


def test_v11_shader_contains_visual_polish_features():
    for token in (
        'micro-normal procedural', 'sunGlint', 'clouds V11: soft cards',
        'heightFog', 'desplazamiento horizontal pequeño tipo Gerstner',
    ):
        assert token in dx.HLSL


def test_v11_transparency_uses_readonly_depth_and_correct_draw_order():
    src = inspect.getsource(dx.D3D11Renderer.render_frame)
    assert "self._draw(self.meshes['sky']" in src
    assert "self._draw(self.meshes['cloud']" in src
    assert src.index("self._draw(self.meshes['sky']") < src.index("self._draw(self.meshes['cloud']")
    assert "depth_readonly=True" in src
    draw_src = inspect.getsource(dx.D3D11Renderer._draw)
    assert 'CTX_OM_SET_DEPTH_STENCIL_STATE' in draw_src


def test_v11_measurement_primes_pipeline_but_keeps_prime_outside_stats():
    src = inspect.getsource(dx.run_directx_benchmark)
    assert 'prime_frames=8' in src
    assert "'measurement_prime_frames_discarded':prime_frames" in src
    assert src.index('for prime_idx in range(prime_frames)') < src.index('frame_times=[]; renderer.begin_scene_gpu_timing()')
    assert 'measured_render_s += frame_ms/1000.0' in src


def test_v11_stability_audit_is_published_without_deleting_spikes():
    src = inspect.getsource(dx.run_directx_benchmark)
    assert "'frametime_cv':cv" in src
    assert "'frametime_max_to_median_ratio':max_to_median" in src
    vals = [10.0] * 990 + [30.0] * 10
    row = dx._fps_stats(vals)
    assert row['frames'] == 1000
    assert math.isclose(row['one_percent_low_fps'], 1000.0 / 30.0, rel_tol=1e-9)


def test_v11_workload_remains_progressive_and_heavy():
    rows = [level_workload(s) for s in profile_levels('standard')]
    tris = [r['approx_triangles_per_frame'] for r in rows]
    assert tris == sorted(tris)
    assert tris[-1] > 1_800_000
    assert all(r['draw_calls_per_frame'] == 7 for r in rows)
    assert rows[-1]['texture_samples'] > rows[0]['texture_samples']
