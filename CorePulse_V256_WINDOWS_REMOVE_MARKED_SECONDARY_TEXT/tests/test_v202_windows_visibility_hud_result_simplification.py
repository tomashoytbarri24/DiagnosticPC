from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v202_version_and_gpu_v22_contract():
    from core import version, benchmark_engine
    from core.benchmark_version import GPU_BENCHMARK_VERSION, GPU_BENCHMARK_LABEL
    assert version.VERSION == "202"
    assert "BENCHMARK_V22_VISIBILITY_HUD_RESULT_SIMPLIFICATION" in version.STAGE
    assert GPU_BENCHMARK_VERSION == 22
    assert GPU_BENCHMARK_LABEL == "V22"
    assert benchmark_engine.GPU_LAST_RESULT_RELATIVE_PATH.name == "benchmark_gpu_v22_ultimo_resultado.json"
    assert "V22" in benchmark_engine.GPU_METHOD_ID


def test_v202_hud_classifies_extreme_before_valley():
    src = (ROOT / "gui/health_center_panel.py").read_text(encoding="utf-8")
    start = src.index("def _scene_text(stage):")
    end = src.index("def update(self, stage", start)
    fn = src[start:end]
    assert fn.index("('extreme', 'EXTREME', 'ESCENA 4/4')") < fn.index("('valle', 'VALLE', 'ESCENA 1/4')")


def test_v202_boat_and_smoke_visibility_contract():
    src = (ROOT / "core/directx_benchmark.py").read_text(encoding="utf-8")
    assert "barco visible en el canal central" in src
    assert "4.0+sin(CameraTime.w*0.12)*8.0" in src
    assert "1.52+bob" in src
    assert "p*1.85" in src
    assert "terrainH(10.0,-110.0)+3.1" in src
    assert "i.pos.x*1.15" in src
    assert "i.pos.y*1.35" in src
    assert "i.pos.z*1.15" in src


def test_v202_single_aircraft_and_extreme_smoke_workload_preserved():
    from core.directx_scene import SCENE_LEVELS, profile_levels
    assert [s.jet_instances for s in SCENE_LEVELS] == [1, 1, 1, 1]
    assert [s.boat_instances for s in SCENE_LEVELS] == [1, 1, 1, 1]
    assert [s.smoke_instances for s in SCENE_LEVELS] == [0, 0, 0, 1]
    levels = profile_levels("standard")
    assert sum(s.measure_seconds for s in levels) == 49.0


def test_v202_summary_removes_duplicate_component_card_grid():
    src = (ROOT / "gui/health_center_panel.py").read_text(encoding="utf-8")
    start = src.index("def _render_benchmark_summary_view")
    end = src.index("def _toggle_benchmark_detail", start)
    fn = src[start:end]
    assert "self._render_benchmark_glance_strip(shell, glance_entries)" in fn
    assert "el Resumen rápido termina aquí" in fn
    assert "cards = ctk.CTkFrame(shell" not in fn
    assert "GPU 3D" in src and "Sistema" in src and "Evidencia" in src


def test_v202_save_aliases_target_v22(tmp_path, monkeypatch):
    from core import benchmark_engine as be
    monkeypatch.setattr(be, "executable_root", lambda: tmp_path)
    out = be.save_last_gpu_v22_result({"status": "OK", "fps": 1.0})
    assert out.name == "benchmark_gpu_v22_ultimo_resultado.json"
    assert out.exists()
    assert be.save_last_gpu_v21_result({"status": "OK", "fps": 2.0}) == out
    assert be.save_last_gpu_v20_result({"status": "OK", "fps": 3.0}) == out
