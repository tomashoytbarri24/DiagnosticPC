from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v203_version_and_gpu_v23_contract():
    from core import version, benchmark_engine
    from core.benchmark_version import GPU_BENCHMARK_VERSION, GPU_BENCHMARK_LABEL
    assert version.VERSION == "203"
    assert "BENCHMARK_V23_BOAT_FIRE_SMOKE_VISIBILITY" in version.STAGE
    assert GPU_BENCHMARK_VERSION == 23
    assert GPU_BENCHMARK_LABEL == "V23"
    assert benchmark_engine.GPU_LAST_RESULT_RELATIVE_PATH.name == "benchmark_gpu_v23_ultimo_resultado.json"
    assert "V23" in benchmark_engine.GPU_METHOD_ID


def test_v203_boat_fire_smoke_visibility_contract_in_shader():
    src = (ROOT / "core/directx_benchmark.py").read_text(encoding="utf-8")
    assert "boat V23: rediseñado y recorriendo el centro del lago" in src
    assert "8.0+sin(CameraTime.w*0.18)*11.0" in src
    assert "8.0+cos(CameraTime.w*0.16)*13.5" in src
    assert "fire V23: fogata visible con flicker propio" in src
    assert "terrainH(35.0,5.0)+1.05" in src
    assert "smoke V23: humo animado en tiempo real sobre la fogata" in src
    assert "frac(rise)*1.4" in src
    assert "self._draw(self.meshes['fire']" in src
    assert "self._draw(self.meshes['smoke']" in src


def test_v203_scene_workload_preserves_49_seconds_and_adds_fire_instances():
    from core.directx_scene import SCENE_LEVELS, profile_levels, level_workload, build_boat
    assert [s.jet_instances for s in SCENE_LEVELS] == [1, 1, 1, 1]
    assert [s.boat_instances for s in SCENE_LEVELS] == [1, 1, 1, 1]
    assert [s.smoke_instances for s in SCENE_LEVELS] == [0, 0, 0, 3]
    assert [s.fire_instances for s in SCENE_LEVELS] == [0, 0, 0, 2]
    levels = profile_levels("standard")
    assert sum(s.measure_seconds for s in levels) == 49.0
    workloads = [level_workload(s) for s in SCENE_LEVELS]
    assert [row["draw_calls_per_frame"] for row in workloads] == [8, 8, 8, 10]
    verts, idx = build_boat()
    assert len(verts) > 0 and len(idx) > 0


def test_v203_save_aliases_target_v23(tmp_path, monkeypatch):
    from core import benchmark_engine as be
    monkeypatch.setattr(be, "executable_root", lambda: tmp_path)
    out = be.save_last_gpu_v23_result({"status": "OK", "fps": 1.0})
    assert out.name == "benchmark_gpu_v23_ultimo_resultado.json"
    assert out.exists()
    assert be.save_last_gpu_v22_result({"status": "OK", "fps": 2.0}) == out
    assert be.save_last_gpu_v21_result({"status": "OK", "fps": 3.0}) == out
