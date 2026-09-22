from pathlib import Path
import math

ROOT = Path(__file__).resolve().parents[1]


def test_v205_version_and_gpu_v25_contract():
    from core import version, benchmark_engine
    from core.benchmark_version import GPU_BENCHMARK_VERSION, GPU_BENCHMARK_LABEL
    assert version.VERSION == "205"
    assert "BENCHMARK_V25_SAFE_BOAT_ROUTE_VISUAL_POLISH" in version.STAGE
    assert GPU_BENCHMARK_VERSION == 25
    assert GPU_BENCHMARK_LABEL == "V25"
    assert benchmark_engine.GPU_LAST_RESULT_RELATIVE_PATH.name == "benchmark_gpu_v25_ultimo_resultado.json"
    assert "V25" in benchmark_engine.GPU_METHOD_ID


def test_v205_boat_route_remains_on_open_water():
    from core.directx_scene import terrain_height
    highs = []
    for i in range(480):
        t = i / 479 * 65.0
        boat_phase = t * 0.20
        x = 0.0 + math.sin(boat_phase) * 13.0
        z = -5.0 + math.cos(boat_phase * 0.82) * 18.0
        h = terrain_height(x, z)
        highs.append(h)
    assert max(highs) < 0.0


def test_v205_shader_contains_safe_boat_route_and_synced_wake():
    src = (ROOT / "core/directx_benchmark.py").read_text(encoding="utf-8")
    assert "boat V25: ruta segura por agua abierta" in src
    assert "0.0+sin(boatPhase)*13.0" in src
    assert "-5.0+cos(boatPhase*0.82)*18.0" in src
    assert "V25: el recorrido se mantiene íntegramente sobre agua abierta" in src
    assert "float2 boatPos=float2(0.0+sin(boatPhase)*13.0, -5.0+cos(boatPhase*0.82)*18.0);" in src


def test_v205_save_aliases_target_v25(tmp_path, monkeypatch):
    from core import benchmark_engine as be
    monkeypatch.setattr(be, "executable_root", lambda: tmp_path)
    out = be.save_last_gpu_v25_result({"status": "OK", "fps": 1.0})
    assert out.name == "benchmark_gpu_v25_ultimo_resultado.json"
    assert out.exists()
    assert be.save_last_gpu_v24_result({"status": "OK", "fps": 2.0}) == out
    assert be.save_last_gpu_v23_result({"status": "OK", "fps": 3.0}) == out
