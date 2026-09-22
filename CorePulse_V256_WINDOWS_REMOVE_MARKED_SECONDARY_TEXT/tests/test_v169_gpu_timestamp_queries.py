from __future__ import annotations

import inspect
from core import directx_benchmark as dx
from core import benchmark_engine
from core.directx_scene import build_jet, build_cloud


def test_v169_d3d11_query_types_and_context_slots_are_canonical():
    assert dx.D3D11_QUERY_TIMESTAMP == 2
    assert dx.D3D11_QUERY_TIMESTAMP_DISJOINT == 3
    assert dx.CTX_BEGIN == 27
    assert dx.CTX_END == 28
    assert dx.CTX_GET_DATA == 29
    assert dx.ctypes.sizeof(dx.D3D11_QUERY_DESC) == 8
    assert dx.ctypes.sizeof(dx.D3D11_QUERY_DATA_TIMESTAMP_DISJOINT) >= 12


def test_v169_gpu_stats_are_computed_only_from_real_samples():
    row=dx._gpu_time_stats([5.0,5.0,10.0],total_frames=4,dropped=1,disjoint=0)
    assert row['gpu_samples'] == 3
    assert abs(row['gpu_sample_coverage']-0.75) < 1e-9
    assert abs(row['gpu_frame_time_avg_ms']-(20.0/3.0)) < 1e-9
    assert row['gpu_query_dropped_frames'] == 1
    assert row['gpu_equivalent_fps'] == 150.0


def test_v169_timestamp_query_uses_end_not_begin_for_timestamp_markers():
    src=inspect.getsource(dx._GpuFrameTimer.begin_frame)
    assert 'CTX_BEGIN' in src
    assert 'slot.disjoint' in src
    assert 'CTX_END' in src
    assert 'slot.start' in src

def test_v169_renderer_returns_gpu_ready_samples_without_changing_present_path():
    src=inspect.getsource(dx.D3D11Renderer.render_frame)
    assert 'gpu_timing' in src
    assert 'begin_frame' in src
    assert 'end_frame' in src
    assert 'self._present()' in src
    assert 'collect_ready' in src

def test_v169_visual_meshes_are_denser_than_v168_defaults():
    _,jet_i=build_jet()
    _,cloud_i=build_cloud()
    assert len(jet_i)//3 > 200
    assert len(cloud_i)//3 >= 300

def test_v169_method_ids_do_not_mix_with_v168_history():
    assert benchmark_engine.GPU_METHOD_ID == 'COREPULSE_GPU_DIRECTX11_SCENES_V7'
    assert benchmark_engine.BENCHMARK_METHOD_ID == 'COREPULSE_BENCHMARK_7_GPU_TIMESTAMP'

def test_v169_gpu_timer_converts_disjoint_frequency_to_milliseconds(monkeypatch):
    next_id={'value':1000}
    query_kind={}
    timestamp_value={}
    timestamp_counter={'value':0}

    def fake_com_method(ptr,index,restype,*argtypes):
        if index == 24:  # ID3D11Device::CreateQuery
            def create(_self, desc_ptr, out_ptr):
                desc=dx.ctypes.cast(desc_ptr, dx.ctypes.POINTER(dx.D3D11_QUERY_DESC)).contents
                qid=next_id['value']; next_id['value'] += 1
                query_kind[qid]=int(desc.Query)
                if int(desc.Query) == dx.D3D11_QUERY_TIMESTAMP:
                    timestamp_counter['value'] += 1
                    timestamp_value[qid]=1000 if timestamp_counter['value'] % 2 else 6000
                dx.ctypes.cast(out_ptr, dx.ctypes.POINTER(dx.ctypes.c_void_p)).contents.value=qid
                return 0
            return create
        if index in (dx.CTX_BEGIN, dx.CTX_END):
            return lambda _self, query: None
        if index == dx.CTX_GET_DATA:
            def get_data(_self, query, data_ptr, size, flags):
                qid=int(query.value if hasattr(query,'value') else query)
                kind=query_kind[qid]
                if kind == dx.D3D11_QUERY_TIMESTAMP_DISJOINT:
                    info=dx.ctypes.cast(data_ptr,dx.ctypes.POINTER(dx.D3D11_QUERY_DATA_TIMESTAMP_DISJOINT)).contents
                    info.Frequency=1_000_000
                    info.Disjoint=0
                else:
                    value=dx.ctypes.cast(data_ptr,dx.ctypes.POINTER(dx.ctypes.c_uint64)).contents
                    value.value=timestamp_value[qid]
                return 0
            return get_data
        raise AssertionError(f'unexpected COM index {index}')

    monkeypatch.setattr(dx,'_com_method',fake_com_method)
    timer=dx._GpuFrameTimer(dx.ctypes.c_void_p(1),dx.ctypes.c_void_p(2),slot_count=8)
    slot=timer.begin_frame(); assert slot is not None
    timer.end_frame(slot)
    vals=timer.drain(timeout_s=0.1)
    assert vals == [5.0]
