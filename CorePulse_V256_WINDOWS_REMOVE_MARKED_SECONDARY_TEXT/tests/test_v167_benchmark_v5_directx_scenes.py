from __future__ import annotations

import platform

from core import benchmark_engine
from core.directx_benchmark import _fps_stats, gpu_profile_info, run_directx_benchmark
from core.directx_scene import profile_levels, level_workload


def test_v5_scene_complexity_strictly_increases():
    levels = profile_levels('standard')
    assert [s.key for s in levels] == ['low', 'medium', 'high', 'extreme']
    workloads = [level_workload(s) for s in levels]
    assert all(a['approx_triangles_per_frame'] < b['approx_triangles_per_frame'] for a, b in zip(workloads, workloads[1:]))
    assert all(a['object_instances'] < b['object_instances'] for a, b in zip(workloads, workloads[1:]))
    assert all(a['shader_iterations'] < b['shader_iterations'] for a, b in zip(workloads, workloads[1:]))
    assert all(a['texture_samples'] < b['texture_samples'] for a, b in zip(workloads, workloads[1:]))


def test_v5_standard_gpu_timing_is_long_enough_for_stable_sampling():
    info = gpu_profile_info('standard')
    levels = profile_levels('standard')
    assert info['scene_count'] == 4
    assert info['seconds'] >= 40.0
    assert all(level.measure_seconds >= 8.0 for level in levels)
    assert all(level.warmup_seconds >= 2.0 for level in levels)


def test_v5_fps_stats_are_derived_from_real_frame_times():
    stats = _fps_stats([10.0] * 100)
    assert stats['frames'] == 100
    assert abs(stats['fps'] - 100.0) < 1e-9
    assert abs(stats['one_percent_low_fps'] - 100.0) < 1e-9
    assert abs(stats['frametime_avg_ms'] - 10.0) < 1e-9
    assert abs(stats['frametime_p95_ms'] - 10.0) < 1e-9


def test_v5_method_ids_are_new_and_not_v4_gpu():
    assert benchmark_engine.BENCHMARK_METHOD_ID == 'COREPULSE_BENCHMARK_7_GPU_TIMESTAMP'
    assert benchmark_engine.GPU_METHOD_ID == 'COREPULSE_GPU_DIRECTX11_SCENES_V7'
    assert benchmark_engine.benchmark_profile_info('standard')['gpu_seconds'] >= 40.0


def test_v5_non_windows_is_explicit_na_not_fake_value():
    if platform.system() == 'Windows':
        return
    result = run_directx_benchmark('quick', visible=False)
    assert result['status'] == 'UNAVAILABLE'
    assert result['value'] is None
    assert result['benchmark_method'] == 'COREPULSE_GPU_DIRECTX11_SCENES_V7'


def test_engine_adapts_directx_scenes_without_inventing_score(monkeypatch):
    import core.directx_benchmark as dx
    fake = {
        'status': 'OK', 'value': 77.5, 'unit': 'FPS', 'duration_s': 41.5,
        'provider': 'CorePulse DirectX 11 Real-World Benchmark V7',
        'renderer': 'Test GPU', 'api': 'DirectX 11', 'feature_level': 0xB000,
        'resolution': '1920x1080', 'vsync_disabled': True, 'primary_scene': 'high',
        'frames_per_s': 77.5, 'one_percent_low_fps': 68.0, 'frametime_avg_ms': 12.9,
        'frametime_p95_ms': 15.0, 'frametime_p99_ms': 17.0,
        'scenes': [
            {'key': 'low', 'label': 'Low', 'status': 'OK', 'frames_per_s': 150.0, 'one_percent_low_fps': 140.0, 'frametime_avg_ms': 6.6, 'workload': {'approx_triangles_per_frame': 50000}},
            {'key': 'medium', 'label': 'Medium', 'status': 'OK', 'frames_per_s': 110.0, 'one_percent_low_fps': 100.0, 'frametime_avg_ms': 9.1, 'workload': {'approx_triangles_per_frame': 100000}},
            {'key': 'high', 'label': 'High', 'status': 'OK', 'frames_per_s': 77.5, 'one_percent_low_fps': 68.0, 'frametime_avg_ms': 12.9, 'workload': {'approx_triangles_per_frame': 200000}},
            {'key': 'extreme', 'label': 'Extreme', 'status': 'OK', 'frames_per_s': 48.0, 'one_percent_low_fps': 41.0, 'frametime_avg_ms': 20.8, 'workload': {'approx_triangles_per_frame': 400000}},
        ],
    }
    monkeypatch.setattr(dx, 'run_directx_benchmark', lambda *a, **k: fake)
    row = benchmark_engine._visual_gpu_result('standard')
    assert row['status'] == 'OK'
    assert row['value'] == 77.5
    assert row['primary_scene'] == 'high'
    assert [s['key'] for s in row['scene_results']] == ['low', 'medium', 'high', 'extreme']
    assert row['scene_results'][2]['throughput_value'] == 15.5
    assert row['policy'].startswith('REAL_OR_NA_DIRECTX11_V7')
