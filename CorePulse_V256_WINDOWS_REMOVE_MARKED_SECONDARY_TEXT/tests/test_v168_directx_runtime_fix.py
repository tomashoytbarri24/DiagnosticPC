from __future__ import annotations

import inspect

from core import directx_benchmark as dx
from core.benchmark_telemetry import BenchmarkTelemetry


def test_v168_device_context_vtable_slots_match_d3d11_h_order():
    # ID3D11DeviceContext hereda IUnknown + ID3D11DeviceChild (7 slots antes
    # del primer método propio). Estos índices son los usados por d3d11.h.
    assert dx.CTX_VS_SET_CONSTANT_BUFFERS == 7
    assert dx.CTX_PS_SET_SHADER_RESOURCES == 8
    assert dx.CTX_PS_SET_SHADER == 9
    assert dx.CTX_PS_SET_SAMPLERS == 10
    assert dx.CTX_VS_SET_SHADER == 11
    assert dx.CTX_DRAW_INDEXED == 12
    assert dx.CTX_PS_SET_CONSTANT_BUFFERS == 16
    assert dx.CTX_IA_SET_INPUT_LAYOUT == 17
    assert dx.CTX_IA_SET_VERTEX_BUFFERS == 18
    assert dx.CTX_IA_SET_INDEX_BUFFER == 19
    assert dx.CTX_DRAW_INDEXED_INSTANCED == 20
    assert dx.CTX_IA_SET_PRIMITIVE_TOPOLOGY == 24
    assert dx.CTX_OM_SET_RENDER_TARGETS == 33
    assert dx.CTX_OM_SET_BLEND_STATE == 35
    assert dx.CTX_RS_SET_STATE == 43
    assert dx.CTX_RS_SET_VIEWPORTS == 44
    assert dx.CTX_UPDATE_SUBRESOURCE == 48
    assert dx.CTX_CLEAR_RENDER_TARGET_VIEW == 50
    assert dx.CTX_CLEAR_DEPTH_STENCIL_VIEW == 53


def test_v168_render_path_uses_named_context_slots_not_v167_wrong_magic_indices():
    source = inspect.getsource(dx.D3D11Renderer)
    assert 'CTX_IA_SET_VERTEX_BUFFERS' in source
    assert 'CTX_UPDATE_SUBRESOURCE' in source
    assert 'CTX_CLEAR_RENDER_TARGET_VIEW' in source
    assert 'CTX_CLEAR_DEPTH_STENCIL_VIEW' in source
    assert 'CTX_OM_SET_RENDER_TARGETS' in source
    assert 'CTX_RS_SET_VIEWPORTS' in source


def test_v168_window_is_hidden_until_first_valid_scene_frame():
    init_source = inspect.getsource(dx.D3D11Renderer._init_window)
    ctor_source = inspect.getsource(dx.D3D11Renderer.__init__)
    assert 'style|(WS_VISIBLE' not in init_source
    assert "first_scene_frame" in ctor_source
    assert '_validate_first_scene_frame' in ctor_source


def test_v168_cpu_97c_is_warning_not_immediate_benchmark_abort_without_tjmax():
    samples = iter([
        {'cpu_temp': 97.0, '_cpu': {}, '_gpus': []},
        {'cpu_temp': 97.5, '_cpu': {}, '_gpus': []},
        {'cpu_temp': 97.0, '_cpu': {}, '_gpus': []},
        {'cpu_temp': 97.2, '_cpu': {}, '_gpus': []},
    ])
    mon = BenchmarkTelemetry(lambda: next(samples), active_component='gpu')
    for _ in range(4):
        mon.sample(force=True)
    assert mon.stop_reason is None
    assert mon.safety_warnings


def test_v168_real_tjmax_distance_can_still_stop_sustained_critical_heat():
    sample = {
        'cpu_temp': 99.8,
        '_cpu': {'distance_to_tjmax_min_c': 0.2},
        '_gpus': [],
    }
    mon = BenchmarkTelemetry(lambda: sample, active_component='gpu')
    mon.sample(force=True)
    mon.sample(force=True)
    assert mon.stop_reason is None
    mon.sample(force=True)
    assert mon.stop_reason is not None
    assert 'TjMax' in mon.stop_reason


def test_v168_method_id_is_new_so_history_does_not_mix_broken_v167_runs():
    assert dx.run_directx_benchmark.__doc__
    # The actual method id is also asserted by the adapter suite test.
    from core import benchmark_engine
    assert benchmark_engine.GPU_METHOD_ID == 'COREPULSE_GPU_DIRECTX11_SCENES_V7'
    assert benchmark_engine.BENCHMARK_METHOD_ID == 'COREPULSE_BENCHMARK_7_GPU_TIMESTAMP'
