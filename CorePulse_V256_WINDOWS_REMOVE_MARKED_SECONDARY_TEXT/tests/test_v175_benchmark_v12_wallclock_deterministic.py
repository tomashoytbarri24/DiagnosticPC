from __future__ import annotations

import inspect
import math

from core import benchmark_engine, version
from core import directx_benchmark as dx
from core.directx_scene import profile_levels


def test_v175_ids_are_new_and_separate_from_v11_history():
    assert version.VERSION == '175'
    assert benchmark_engine.BENCHMARK_METHOD_ID == 'COREPULSE_BENCHMARK_12_WALLCLOCK_DETERMINISTIC_GPU_TIMESTAMP'
    assert benchmark_engine.GPU_METHOD_ID == 'COREPULSE_GPU_DIRECTX11_SCENES_V12_WALLCLOCK_DETERMINISTIC'


def test_v12_standard_keeps_exact_target_wall_times():
    levels=profile_levels('standard')
    assert [x.key for x in levels] == ['valley','forest','lake','extreme']
    assert [x.measure_seconds for x in levels] == [10.0,12.0,12.0,15.0]
    assert math.isclose(sum(x.measure_seconds for x in levels),49.0,abs_tol=1e-9)
    assert math.isclose(sum(x.warmup_seconds+x.settle_seconds+x.measure_seconds for x in levels),58.0,abs_tol=1e-9)


def test_v12_camera_and_phase_end_use_wall_clock_not_render_accumulation():
    src=inspect.getsource(dx.run_directx_benchmark)
    assert 'measure_wall_start=time.perf_counter()' in src
    assert 'wall_elapsed=time.perf_counter()-measure_wall_start' in src
    assert 'if wall_elapsed>=level.measure_seconds' in src
    assert 'scene_elapsed=min(wall_elapsed, level.measure_seconds)' in src
    assert 'path_base+level.warmup_seconds+level.settle_seconds+scene_elapsed' in src
    assert 'while measured_render_s<level.measure_seconds' not in src
    # render accumulation remains audit metadata only, not phase/camera clock
    assert 'measured_render_s += frame_ms/1000.0' in src
    assert "'render_present_accumulated_seconds':measured_render_s" in src


def test_v12_render_present_timing_still_excludes_queries_ui_and_pump():
    src=inspect.getsource(dx.run_directx_benchmark)
    assert src.index('renderer.prepare_timed_frame()') < src.index('frame_start_ns=time.perf_counter_ns()')
    assert src.index('frame_end_ns=time.perf_counter_ns()') < src.index('renderer.poll_gpu_timing()')
    measured_call=src[src.index('frame_start_ns=time.perf_counter_ns()'):src.index('frame_end_ns=time.perf_counter_ns()')]
    assert 'pump_messages=False' in measured_call


def test_v12_progress_callback_is_throttled_to_10hz_outside_frametime():
    src=inspect.getsource(dx.run_directx_benchmark)
    assert 'next_progress=measure_wall_start' in src
    assert 'now >= next_progress' in src
    assert 'next_progress=now+0.10' in src
    measure=src.split('next_progress=measure_wall_start',1)[1]
    assert measure.index('frame_end_ns=time.perf_counter_ns()') < measure.index('now >= next_progress')


def test_v174_depth_state_hotfix_is_preserved():
    assert dx.CTX_OM_SET_DEPTH_STENCIL_STATE == 36
