from __future__ import annotations

import inspect
import math

from core import benchmark_engine, version
from core import directx_benchmark as dx
from core.directx_scene import build_tree, build_water, level_workload, profile_levels


def _valid_mesh(v, i):
    return bool(v) and bool(i) and len(i) % 3 == 0 and min(i) >= 0 and max(i) < len(v)


def test_v172_version_and_method_ids_are_new():
    assert version.VERSION == '172'
    assert benchmark_engine.BENCHMARK_METHOD_ID == 'COREPULSE_BENCHMARK_10_REALISTIC_ISOLATED_GPU_TIMESTAMP'
    assert benchmark_engine.GPU_METHOD_ID == 'COREPULSE_GPU_DIRECTX11_SCENES_V10_REALISTIC_ISOLATED'


def test_v10_standard_profile_has_49_seconds_of_actual_render_measurement():
    levels = profile_levels('standard')
    assert [x.key for x in levels] == ['valley', 'forest', 'lake', 'extreme']
    assert math.isclose(sum(x.measure_seconds for x in levels), 49.0, abs_tol=1e-9)
    assert math.isclose(sum(x.warmup_seconds + x.settle_seconds + x.measure_seconds for x in levels), 58.0, abs_tol=1e-9)
    assert all(x.settle_seconds > 0 for x in levels)
    assert math.isclose(dx.gpu_profile_info('standard')['seconds'], 58.0, abs_tol=1e-9)


def test_tree_v10_uses_leaf_cards_not_green_rock_lobes():
    v, i = build_tree()
    assert _valid_mesh(v, i)
    assert len(i) // 3 >= 200
    # Bark marker and foliage UV marker + actual 0..1 local V both exist.
    assert any(row[7] < 1.5 for row in v)
    foliage = [row for row in v if row[7] > 1.5]
    assert foliage
    assert len({round(row[7] % 1.0, 2) for row in foliage}) >= 2
    assert 'leafAlpha' in dx.HLSL and 'clip(leafAlpha-0.18)' in dx.HLSL


def test_water_v10_has_directional_waves_reflection_and_foam():
    v, i = build_water()
    assert _valid_mesh(v, i)
    assert len(i) // 3 >= 40000
    for token in ('cuatro ondas direccionales', 'reflectedSky', 'micro=', 'foamNoise', 'wfres'):
        assert token in dx.HLSL


def test_material_shader_uses_multiscale_terrain_and_bark():
    for token in ('mezcla multiescala arena/pasto/roca', 'rockMask', 'buv*2.7', 'grooves'):
        assert token in dx.HLSL


def test_gpu_query_readback_is_outside_render_present_timing():
    timer_src = inspect.getsource(dx._GpuFrameTimer.begin_frame)
    assert 'collect_ready' not in timer_src
    render_src = inspect.getsource(dx.D3D11Renderer.render_frame)
    # render_frame itself no longer reads queries after Present.
    after_present = render_src.split('self._present()', 1)[1]
    assert 'collect_ready' not in after_present
    assert 'pump_messages' in render_src

    loop_src = inspect.getsource(dx.run_directx_benchmark)
    assert 'renderer.prepare_timed_frame()' in loop_src
    assert 'frame_start_ns=time.perf_counter_ns()' in loop_src
    assert 'pump_messages=False' in loop_src
    assert 'frame_end_ns=time.perf_counter_ns()' in loop_src
    assert loop_src.index('renderer.prepare_timed_frame()') < loop_src.index('frame_start_ns=time.perf_counter_ns()')
    assert loop_src.index('frame_end_ns=time.perf_counter_ns()') < loop_src.index('renderer.poll_gpu_timing()')


def test_measure_duration_accumulates_real_render_present_time():
    src = inspect.getsource(dx.run_directx_benchmark)
    assert 'while measured_render_s<level.measure_seconds' in src
    assert 'measured_render_s += frame_ms/1000.0' in src
    assert "'measurement_wall_seconds':measure_wall_s" in src


def test_frametime_stats_publish_median_and_spike_audit_without_hiding_frames():
    vals = [10.0] * 990 + [30.0] * 10
    row = dx._fps_stats(vals)
    assert row['frames'] == 1000
    assert row['frametime_median_ms'] == 10.0
    assert row['frametime_spike_frames'] == 10
    assert math.isclose(row['frametime_spike_ratio'], 0.01, abs_tol=1e-12)
    # 1% Low remains derived from the real worst 1%; spikes are reported, not removed.
    assert math.isclose(row['one_percent_low_fps'], 1000.0 / 30.0, rel_tol=1e-9)



def test_camera_and_wave_time_are_driven_by_deterministic_phase_clock():
    src = inspect.getsource(dx.run_directx_benchmark)
    assert 'path_base=0.0' in src
    assert 'path_base+level.warmup_seconds+level.settle_seconds+measured_render_s' in src
    assert 'path_base += level.warmup_seconds + level.settle_seconds + level.measure_seconds' in src
    # Measured animation time must not be taken from wall-clock elapsed since launch.
    measured_call = 'renderer.render_frame(level,path_base+level.warmup_seconds+level.settle_seconds+measured_render_s'
    assert measured_call in src

def test_timestamp_coverage_remains_hard_capped_to_100_percent():
    row = dx._gpu_time_stats([2.0] * 150, total_frames=100)
    assert row['gpu_samples'] == 100
    assert row['gpu_sample_coverage'] == 1.0
    assert row['gpu_sample_overflow_discarded'] == 50


def test_workload_is_progressive_and_gpu_heavy():
    rows = [level_workload(s) for s in profile_levels('standard')]
    tris = [r['approx_triangles_per_frame'] for r in rows]
    assert tris == sorted(tris)
    assert tris[-1] > 1_500_000
    assert rows[-1]['shader_iterations'] > rows[0]['shader_iterations']
    assert rows[-1]['texture_samples'] > rows[0]['texture_samples']
    assert all(r['draw_calls_per_frame'] == 7 for r in rows)
