from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parents[1]


def _sha(rel):
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


def test_v200_version_and_gpu_v20_contract():
    from core import version, benchmark_engine
    from core.benchmark_version import GPU_BENCHMARK_VERSION, GPU_BENCHMARK_LABEL
    assert version.VERSION == "200"
    assert "BENCHMARK_V20_RESULT_CLARITY_AIRCRAFT_FRAMING" in version.STAGE
    assert GPU_BENCHMARK_VERSION == 20
    assert GPU_BENCHMARK_LABEL == "V20"
    assert benchmark_engine.GPU_LAST_RESULT_RELATIVE_PATH.name == "benchmark_gpu_v20_ultimo_resultado.json"
    assert "V20" in benchmark_engine.GPU_METHOD_ID


def test_v200_keeps_geometry_and_49s_contract():
    from core.directx_scene import profile_levels, level_workload
    # V199 geometry hash: V200 only changes HLSL instance transforms/framing.
    assert _sha("core/directx_scene.py") == "21716b2013cfcee87330f81620a71791952024474af2e734c30d4c7fa6f32e2b"
    levels = profile_levels("standard")
    assert [s.measure_seconds for s in levels] == [10.0, 12.0, 12.0, 15.0]
    assert sum(s.measure_seconds for s in levels) == 49.0
    assert all(level_workload(s)["draw_calls_per_frame"] == 7 for s in levels)


def test_v200_aircraft_are_reframed_closer_without_instance_change():
    src = (ROOT / "core/directx_benchmark.py").read_text(encoding="utf-8")
    assert "jets V20: formación 3D más cercana y mejor encuadrada" in src
    assert "44.0+sin(a*0.73)*3.8" in src
    assert "34.0+cos(a*0.82)*9.0" in src
    assert "p=p*1.74" in src
    from core.directx_scene import SCENE_LEVELS
    assert [s.jet_instances for s in SCENE_LEVELS] == [3, 6, 9, 12]


def test_v200_result_pages_have_independent_stable_scroll():
    src = (ROOT / "gui/health_center_panel.py").read_text(encoding="utf-8")
    assert "self._benchmark_result_page_scrolls = page_scrolls" in src
    assert "page_scroll = StableScrollHost(" in src
    assert "self._render_benchmark_page_content(page_scroll.content, key, result)" in src
    assert "page_scroll.yview_moveto(0.0)" in src
    # Nav stays outside the scrollable page host.
    assert src.index("self._render_benchmark_result_nav(shell)") < src.index("page_scroll = StableScrollHost(")


def test_v200_save_aliases_target_current_v20_file(tmp_path, monkeypatch):
    from core import benchmark_engine as be
    monkeypatch.setattr(be, "executable_root", lambda: tmp_path)
    out = be.save_last_gpu_v20_result({"status": "OK", "fps": 1.0})
    assert out.name == "benchmark_gpu_v20_ultimo_resultado.json"
    assert out.exists()
    out2 = be.save_last_gpu_v19_result({"status": "OK", "fps": 2.0})
    assert out2 == out


def test_v200_keeps_knowledge_layer_language():
    src = (ROOT / "gui/health_center_panel.py").read_text(encoding="utf-8")
    assert "Conclusión CorePulse" in src
    assert "benchmark_run_conclusion" in src
    assert "Ver evidencia térmica" in src
