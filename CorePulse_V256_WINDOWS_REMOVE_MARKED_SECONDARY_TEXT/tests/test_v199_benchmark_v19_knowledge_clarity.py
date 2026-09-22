from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parents[1]

def _sha(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()

def test_v199_version_and_v19_contract():
    from core import version
    from core import benchmark_engine
    assert version.VERSION == "199"
    assert "BENCHMARK_V19_KNOWLEDGE_CLARITY" in version.STAGE
    assert benchmark_engine.GPU_LAST_RESULT_RELATIVE_PATH.name == "benchmark_gpu_v19_ultimo_resultado.json"
    assert "V19" in benchmark_engine.GPU_METHOD_ID

def test_v199_keeps_v19_workload_byte_identical_to_v198():
    assert _sha("core/directx_scene.py") == "21716b2013cfcee87330f81620a71791952024474af2e734c30d4c7fa6f32e2b"
    assert _sha("core/directx_benchmark.py") == "754b46a53e379db6bb4cec1b109a4231b86f391395067a0efa28ac6495f68cd7"
    assert _sha("core/benchmark_engine.py") == "255be8fc4267944472a060e8fd793bc5cbb2471cd3d692911a5bb3d9d0e56891"

def test_gpu_completed_but_irregular_is_not_called_all_good():
    from core.benchmark_presentation import benchmark_component_reading
    visual = {
        "status":"OK", "frames_per_s":48.5, "one_percent_low_fps":29.6,
        "scenes":[{"status":"OK"} for _ in range(4)],
        "phase_results":[
            {"frames_per_s":398.3,"one_percent_low_fps":78.5},
            {"frames_per_s":210.7,"one_percent_low_fps":46.2},
            {"frames_per_s":131.6,"one_percent_low_fps":41.8},
            {"frames_per_s":48.5,"one_percent_low_fps":29.6},
        ],
    }
    reading = benchmark_component_reading("gpu", visual, telemetry={"gpu_temp":{"max":82.0}})
    assert reading["tone"] == "amber"
    assert "IRREGULAR" in reading["label"]
    assert "4/4" in reading["short"]

def test_run_conclusion_is_short_and_component_scoped():
    from core.benchmark_presentation import benchmark_run_conclusion
    visual = {"status":"OK","frames_per_s":50,"one_percent_low_fps":40,"scenes":[{"status":"OK"} for _ in range(4)]}
    suite = {
        "cpu":{"status":"OK","measurement_quality":"VARIABLE"},
        "ram":{"status":"OK","measurement_quality":"STABLE","integrity_ok":True},
        "ssd":{"status":"OK","measurement_quality":"STABLE","read_mbps":1000,"write_mbps":500},
    }
    c = benchmark_run_conclusion(["gpu","cpu","ram","ssd"], visual, suite, tele_visual={}, tele_suite={})
    assert len(c["items"]) <= 4
    assert {x["component"] for x in c["items"]} == {"GPU","CPU","RAM","SSD"}
    assert len(c["note"]) < 180

def test_gui_uses_single_conclusion_and_progressive_disclosure():
    src = (ROOT / "gui/health_center_panel.py").read_text(encoding="utf-8")
    assert "Conclusión CorePulse" in src
    assert "benchmark_run_conclusion" in src
    assert "show_summary=False" in src
    assert "compact=not advanced" in src
    assert "Protección térmica:" in src
