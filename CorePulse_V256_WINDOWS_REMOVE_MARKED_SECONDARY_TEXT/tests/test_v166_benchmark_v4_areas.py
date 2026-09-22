import inspect
import core.benchmark_engine as be


def test_method_ids_v4_areas():
    assert be.BENCHMARK_METHOD_ID == 'COREPULSE_BENCHMARK_4_AREAS'
    assert be.CPU_METHOD_ID == 'COREPULSE_CPU_AREAS_V4'
    assert be.RAM_METHOD_ID == 'COREPULSE_RAM_AREAS_V4'
    assert be.SSD_METHOD_ID == 'COREPULSE_SSD_IO_V4'
    assert be.GPU_METHOD_ID == 'COREPULSE_GPU_AREAS_V4'


def test_cpu_v4_measured_and_na_areas_are_explicit():
    r = be.benchmark_cpu_v4(3.6)
    assert r['status'] in {'OK', 'PARTIAL'}
    assert r['integrity_ok'] is True
    for key in ('single_thread_crypto','multi_thread_crypto','compression','decompression'):
        assert r['subtests'][key]['value'] is not None
    assert r['subtests']['integer_alu_pure']['status'] == 'N/A'
    assert r['subtests']['floating_point_pure']['status'] == 'N/A'
    assert r['subtests']['simd_vector_pure']['status'] == 'N/A'
    assert r['subtests']['cache_latency']['status'] == 'N/A'


def test_ram_v4_native_write_copy_and_na_latency():
    r = be.benchmark_ram_v4(64)
    assert r['status'] in {'OK', 'PARTIAL'}
    assert r['integrity_ok'] is True
    assert r['subtests']['native_write_fill']['value'] is not None
    assert r['subtests']['native_copy']['value'] is not None
    assert r['subtests']['pure_read_bandwidth']['status'] == 'N/A'
    assert r['subtests']['latency']['status'] == 'N/A'


def test_ssd_v4_derives_latency_only_from_measured_iops():
    src = inspect.getsource(be.benchmark_ssd_v4)
    assert '1000.0/riops' in src
    assert '1000.0/wiops' in src
    assert 'DERIVED_FROM_MEASURED_QD1_IOPS' in src


def test_gpu_v4_has_explicit_unmeasured_areas_not_fake_numbers():
    src = inspect.getsource(be._visual_gpu_result)
    for key in ('gpu_buffer_copy','ray_tracing','mesh_shaders','ai_matrix'):
        assert key in src
    assert '_na_area(' in src
    assert 'AREAS_V4_HIDDEN_TECHNICAL_WORKLOAD_NO_DECORATIVE_RENDERER' in src


def test_suite_uses_v4_wrappers():
    src = inspect.getsource(be.run_benchmark_suite)
    assert 'benchmark_cpu_v4(' in src
    assert 'benchmark_ram_v4(' in src
    assert 'benchmark_ssd_v4(' in src
    assert '_visual_gpu_result(' in src
    assert 'REAL_OR_NA_BENCHMARK_V4_AREAS_NO_REFERENCE_RANKING' in src
