from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parents[1]
SCENE_SHA = "879f7a664d2616fa5485477e9475393bf11bd5b2d082cfaf2bf934ac5c05f5ee"
DIRECTX_SHA = "648c2caec5f6e4b3abf52dc1c3b16c93f67e7127a909be76d46113b6d1aa64a0"
ENGINE_SHA = "c77426c5b56632cda58c13af0a032470656ef3ae55e81ac209a8ea4d5fb40fe5"

def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def _source(rel):
    return (ROOT / rel).read_text(encoding="utf-8")

def test_v193_version_and_v16_contract():
    from core.version import VERSION, STAGE
    from core import benchmark_engine as engine
    assert VERSION == "193"
    assert "BENCHMARK_V16_CLARITY_FINISH" in STAGE
    assert engine.GPU_LAST_RESULT_RELATIVE_PATH.name == "benchmark_gpu_v16_ultimo_resultado.json"

def test_v193_keeps_v16_workload_byte_identical():
    assert _sha(ROOT / "core/directx_scene.py") == SCENE_SHA
    assert _sha(ROOT / "core/directx_benchmark.py") == DIRECTX_SHA
    assert _sha(ROOT / "core/benchmark_engine.py") == ENGINE_SHA

def test_v193_swaps_results_only_after_building_static_dashboard():
    text = _source("gui/health_center_panel.py")
    fn = text[text.index("def _show_static_benchmark_results"):text.index("def _show_benchmark_setup")]
    assert fn.index("self._render_visual_benchmark_result_body") < fn.index("self.scroll.pack_forget()")
    assert "evitando el intervalo vacío" in fn

def test_v193_progressive_details_reduce_first_glance_density():
    text = _source("gui/health_center_panel.py")
    assert "Ver detalles técnicos" in text
    assert "Ocultar detalles técnicos" in text
    assert "Primero FPS y 1% Low" in text
    assert "IOPS, CV y métricas auxiliares son opcionales" in text
    assert "Ver metodología" in text
    assert "BENCH_BORDER" in text

def test_v193_history_keeps_loading_surface_until_staging_is_published():
    text = _source("gui/benchmark_panel.py")
    fn = text[text.index("def _schedule_history_build"):text.index("def _show_section")]
    assert fn.index("staging.pack(fill='both', expand=True)") < fn.index("self._history_loading.destroy()")
    assert "Evita el frame vacío" in fn
