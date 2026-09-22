"""Compatibilidad V165: los wrappers V3 siguen disponibles para historial/pruebas.

V166 cambia los identificadores activos a Benchmark V4 por áreas, por lo que este
archivo ya no debe fijar los METHOD_ID globales a V3.
"""
import inspect
import core.benchmark_engine as be
import core.visual_benchmark as vb


def test_v3_wrappers_remain_available_for_compatibility():
    assert callable(be.benchmark_cpu_v3)
    assert callable(be.benchmark_ram_v3)
    assert callable(be.benchmark_ssd_v3)


def test_gpu_can_run_hidden():
    sig = inspect.signature(vb.run_visual_benchmark)
    assert 'visible' in sig.parameters
    src = inspect.getsource(be._visual_gpu_result)
    assert 'visible=False' in src
    assert 'Texture Sampling' in src
    assert 'Pixel Fill / Blending' in src


def test_cpu_v3_real_samples_and_integrity():
    result = be.benchmark_cpu_v3(3.6)
    assert result['status'] == 'OK'
    assert result['integrity_ok'] is True
    assert len(result['sha256_samples']) == 3
    assert result['subtests']['compression']['value'] is not None
    assert result['subtests']['decompression']['value'] is not None


def test_ram_v3_real_samples_and_integrity():
    result = be.benchmark_ram_v3(64, min_seconds=3.0)
    assert result['status'] == 'OK'
    assert result['integrity_ok'] is True
    assert len(result['sample_values_mbps']) == 3
    assert result['value'] is not None
