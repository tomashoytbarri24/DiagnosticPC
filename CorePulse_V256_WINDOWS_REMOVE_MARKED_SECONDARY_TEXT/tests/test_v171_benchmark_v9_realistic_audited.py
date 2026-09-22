from __future__ import annotations

import inspect
import math

from core import version, benchmark_engine
from core.directx_benchmark import HLSL, _gpu_time_stats, gpu_profile_info, D3D11Renderer
from core.directx_scene import build_tree, build_water, level_workload, profile_levels


def _indices_valid(vertices, indices):
    return bool(vertices) and bool(indices) and min(indices) >= 0 and max(indices) < len(vertices) and len(indices) % 3 == 0


def test_version_and_method_v171_v9():
    assert version.VERSION == '171'
    assert version.VERSION_LABEL == 'V171'
    assert benchmark_engine.BENCHMARK_METHOD_ID == 'COREPULSE_BENCHMARK_9_REALISTIC_AUDITED_GPU_TIMESTAMP'
    assert benchmark_engine.GPU_METHOD_ID == 'COREPULSE_GPU_DIRECTX11_SCENES_V9_REALISTIC'


def test_standard_profile_is_54_seconds_with_49_measured():
    levels = profile_levels('standard')
    assert [s.key for s in levels] == ['valley', 'forest', 'lake', 'extreme']
    assert math.isclose(sum(s.warmup_seconds + s.measure_seconds for s in levels), 54.0, abs_tol=1e-9)
    assert math.isclose(sum(s.measure_seconds for s in levels), 49.0, abs_tol=1e-9)
    assert [s.measure_seconds for s in levels] == [10.0, 12.0, 12.0, 15.0]
    assert [s.warmup_seconds for s in levels] == [5.0, 0.0, 0.0, 0.0]
    assert math.isclose(gpu_profile_info('standard')['seconds'], 54.0, abs_tol=1e-9)


def test_tree_is_real_3d_cluster_not_old_cones():
    v, i = build_tree()
    assert _indices_valid(v, i)
    assert len(i) // 3 >= 900
    assert any(x[7] > 1.5 for x in v)  # foliage marker
    assert any(x[7] < 0.5 for x in v)  # bark marker


def test_water_mesh_has_more_surface_detail():
    v, i = build_water()
    assert _indices_valid(v, i)
    assert len(i) // 3 >= 40000
    assert 'micro-normal' in HLSL
    assert 'foam' in HLSL
    assert 'wfres' in HLSL


def test_workload_progression_is_gpu_heavy_without_draw_call_explosion():
    rows = [level_workload(s) for s in profile_levels('standard')]
    tris = [x['approx_triangles_per_frame'] for x in rows]
    assert tris == sorted(tris)
    assert tris[-1] > 4_000_000
    assert all(x['draw_calls_per_frame'] == 7 for x in rows)
    assert rows[-1]['shader_iterations'] > rows[0]['shader_iterations']
    assert rows[-1]['texture_samples'] > rows[0]['texture_samples']


def test_gpu_coverage_can_never_exceed_100_percent():
    stats = _gpu_time_stats([1.0] * 141, total_frames=100)
    assert stats['gpu_samples'] == 100
    assert stats['gpu_sample_coverage'] == 1.0
    assert stats['gpu_sample_overflow_discarded'] == 41


def test_sky_is_drawn_after_scene_to_avoid_depth_occlusion_artifact():
    src = inspect.getsource(D3D11Renderer.render_frame)
    pos_sky = src.index("self._draw(self.meshes['sky']")
    pos_cloud = src.index("self._draw(self.meshes['cloud']")
    pos_terrain = src.index("self._draw(terrain")
    assert pos_sky > pos_cloud > pos_terrain


def test_hlsl_distinguishes_bark_and_foliage():
    assert 'i.aux < 1.5' in HLSL
    assert 'corteza(0) / follaje(2)' in HLSL


def test_measurement_loop_does_not_duplicate_timestamp_samples_or_include_callbacks():
    import core.directx_benchmark as dx
    src = inspect.getsource(dx.run_directx_benchmark)
    assert 'gpu_times.extend(renderer.render_frame' not in src
    assert 'gpu_times,gpu_meta=renderer.finish_scene_gpu_timing' in src
    assert 'frame_start=time.perf_counter()' in src
    assert 'frame_end=time.perf_counter()' in src
    assert 'frame_times.append((frame_end-frame_start)*1000.0)' in src


def test_procedural_texture_is_multichannel_and_deterministic_source():
    src = inspect.getsource(D3D11Renderer._create_noise_texture)
    assert 'w=h=512' in src
    assert 'seed=0x13579BDF' in src
    assert 'r=int(' in src and 'g=int(' in src and 'bl=int(' in src
