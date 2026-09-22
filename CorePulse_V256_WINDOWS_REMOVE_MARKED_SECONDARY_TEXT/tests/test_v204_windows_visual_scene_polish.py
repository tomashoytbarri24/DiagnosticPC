from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v204_version_and_gpu_v24_contract():
    from core import version, benchmark_engine
    from core.benchmark_version import GPU_BENCHMARK_VERSION, GPU_BENCHMARK_LABEL
    assert version.VERSION == "204"
    assert "BENCHMARK_V24_VISUAL_SCENE_POLISH" in version.STAGE
    assert GPU_BENCHMARK_VERSION == 24
    assert GPU_BENCHMARK_LABEL == "V24"
    assert benchmark_engine.GPU_LAST_RESULT_RELATIVE_PATH.name == "benchmark_gpu_v24_ultimo_resultado.json"
    assert "V24" in benchmark_engine.GPU_METHOD_ID


def test_v204_visual_scene_polish_shader_contracts():
    src = (ROOT / "core/directx_benchmark.py").read_text(encoding="utf-8")
    assert "boat V24: ruta cercana, silueta más clara y escala reforzada" in src
    assert "18.0+sin(boatPhase)*17.0" in src
    assert "estela del barco" in src
    assert "smoke V24: pluma multicapa con deriva visible en tiempo real" in src
    assert "fire V24: fogata más compacta y brillante" in src
    assert "trees V24: corteza y follaje con más volumen perceptual" in src
    assert "rocks V24" in src


def test_v204_scene_builders_and_workload_contracts():
    from core.directx_scene import (
        SCENE_LEVELS, profile_levels, level_workload,
        build_boat, build_smoke_plume, build_fire_billboard,
    )
    assert [s.jet_instances for s in SCENE_LEVELS] == [1, 1, 1, 1]
    assert [s.boat_instances for s in SCENE_LEVELS] == [1, 1, 1, 1]
    assert [s.smoke_instances for s in SCENE_LEVELS] == [0, 0, 0, 3]
    assert [s.fire_instances for s in SCENE_LEVELS] == [0, 0, 0, 2]
    levels = profile_levels("standard")
    assert sum(s.measure_seconds for s in levels) == 49.0
    workloads = [level_workload(s) for s in SCENE_LEVELS]
    assert [row["draw_calls_per_frame"] for row in workloads] == [8, 8, 8, 10]
    assert len(build_boat()[0]) > 0 and len(build_boat()[1]) > 0
    assert len(build_smoke_plume()[0]) > 0 and len(build_smoke_plume()[1]) > 0
    assert len(build_fire_billboard()[0]) > 0 and len(build_fire_billboard()[1]) > 0


def test_v204_save_aliases_target_v24(tmp_path, monkeypatch):
    from core import benchmark_engine as be
    monkeypatch.setattr(be, "executable_root", lambda: tmp_path)
    out = be.save_last_gpu_v24_result({"status": "OK", "fps": 1.0})
    assert out.name == "benchmark_gpu_v24_ultimo_resultado.json"
    assert out.exists()
    assert be.save_last_gpu_v23_result({"status": "OK", "fps": 2.0}) == out
    assert be.save_last_gpu_v22_result({"status": "OK", "fps": 3.0}) == out
