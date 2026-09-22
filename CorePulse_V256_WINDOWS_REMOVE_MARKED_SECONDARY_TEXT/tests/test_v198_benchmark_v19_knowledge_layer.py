from __future__ import annotations

import hashlib
from pathlib import Path

from core import version
from core.benchmark_presentation import benchmark_component_reading
from core.benchmark_version import GPU_BENCHMARK_VERSION, GPU_RESULT_FILENAME

ROOT = Path(__file__).resolve().parents[1]


def sha(path: str) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def test_v198_keeps_gpu_v19_workload_byte_identical():
    assert version.VERSION == "198"
    assert GPU_BENCHMARK_VERSION == 19
    assert GPU_RESULT_FILENAME == "benchmark_gpu_v19_ultimo_resultado.json"
    assert sha("core/directx_scene.py") == "21716b2013cfcee87330f81620a71791952024474af2e734c30d4c7fa6f32e2b"
    assert sha("core/directx_benchmark.py") == "754b46a53e379db6bb4cec1b109a4231b86f391395067a0efa28ac6495f68cd7"
    assert sha("core/benchmark_engine.py") == "255be8fc4267944472a060e8fd793bc5cbb2471cd3d692911a5bb3d9d0e56891"


def test_cpu_reading_uses_real_quality_and_temperature():
    row = {"status": "OK", "measurement_quality": "VARIABLE", "integrity_ok": True}
    telemetry = {"cpu_temp": {"max": 96.0}}
    reading = benchmark_component_reading("cpu", row, telemetry=telemetry)
    assert reading["tone"] == "amber"
    assert "CALIENTE" in reading["label"]
    assert "VARIABLE" in reading["label"]
    assert "96,0" in reading["summary"]


def test_ram_reading_requires_integrity_before_saying_correct():
    good = benchmark_component_reading(
        "ram",
        {"status": "OK", "measurement_quality": "STABLE", "integrity_ok": True, "bandwidth_cv_percent": 1.2},
    )
    bad = benchmark_component_reading(
        "ram",
        {"status": "OK", "measurement_quality": "STABLE", "integrity_ok": False},
    )
    assert good["tone"] == "green"
    assert "CORRECTAMENTE" in good["label"]
    assert "byte a byte" in good["summary"]
    assert bad["tone"] == "red"
    assert "INTEGRIDAD" in bad["label"]


def test_ssd_reading_separates_performance_from_smart_health():
    reading = benchmark_component_reading(
        "ssd",
        {
            "status": "OK",
            "measurement_quality": "STABLE",
            "read_mbps": 1200.0,
            "write_mbps": 300.0,
            "random_4k": {"status": "OK"},
        },
    )
    assert reading["tone"] == "green"
    assert "E/S" in reading["label"]
    assert "SMART" in reading["summary"]
    assert "desgaste" in reading["scope"]


def test_gpu_reading_explains_completion_consistency_and_heat_without_external_ranking():
    row = {
        "status": "OK",
        "frames_per_s": 47.4,
        "one_percent_low_fps": 29.5,
        "scenes": [{"status": "OK"} for _ in range(4)],
    }
    reading = benchmark_component_reading("gpu", row, telemetry={"gpu_temp": {"max": 89.0}})
    assert reading["tone"] == "amber"
    assert "TEMPERATURA ALTA" in reading["label"]
    assert "4/4" in reading["summary"]
    assert "1% Low" in reading["summary"]
    assert "otras GPUs" in reading["scope"]


def test_safety_stop_overrides_component_positive_reading():
    reading = benchmark_component_reading(
        "gpu",
        {"status": "OK", "frames_per_s": 50.0, "scenes": [{"status": "OK"} for _ in range(4)]},
        safety_stop="CPU TjMax distance <= 1 C",
    )
    assert reading["tone"] == "red"
    assert reading["label"] == "DETENIDO POR SEGURIDAD"


def test_v198_ui_exposes_knowledge_layer_without_hiding_evidence():
    panel = (ROOT / "gui/health_center_panel.py").read_text(encoding="utf-8")
    assert "Lectura CorePulse" in panel
    assert "benchmark_component_reading" in panel
    assert "% del promedio" in panel
    assert "TEMPERATURA CPU ALTA · SIN PARADA" in panel
    assert "Muestras sobre" in panel
    assert "Ver detalles técnicos" in panel
