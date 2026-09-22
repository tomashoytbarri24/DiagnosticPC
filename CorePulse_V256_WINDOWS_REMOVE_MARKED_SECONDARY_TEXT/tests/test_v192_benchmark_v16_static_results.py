from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parents[1]

SCENE_SHA = "879f7a664d2616fa5485477e9475393bf11bd5b2d082cfaf2bf934ac5c05f5ee"
DIRECTX_SHA = "648c2caec5f6e4b3abf52dc1c3b16c93f67e7127a909be76d46113b6d1aa64a0"
ENGINE_SHA = "c77426c5b56632cda58c13af0a032470656ef3ae55e81ac209a8ea4d5fb40fe5"


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source(path):
    return path.read_text(encoding="utf-8")


def test_v192_version_and_v16_contract():
    from core.version import VERSION, STAGE
    from core import benchmark_engine as engine
    assert VERSION == "192"
    assert "BENCHMARK_V16_STATIC_RESULTS" in STAGE
    assert engine.GPU_LAST_RESULT_RELATIVE_PATH.name == "benchmark_gpu_v16_ultimo_resultado.json"


def test_v192_keeps_v16_workload_byte_identical():
    assert _sha(ROOT / "core/directx_scene.py") == SCENE_SHA
    assert _sha(ROOT / "core/directx_benchmark.py") == DIRECTX_SHA
    assert _sha(ROOT / "core/benchmark_engine.py") == ENGINE_SHA


def test_v192_results_use_static_surface():
    text = _source(ROOT / "gui/health_center_panel.py")
    assert "_benchmark_static_results" in text
    assert "_show_static_benchmark_results" in text
    assert "self.scroll.pack_forget()" in text
    assert "las escenas GPU se muestran sólo en GPU 3D" in text


def test_v192_history_is_staged_and_compact():
    panel = _source(ROOT / "gui/benchmark_panel.py")
    history = _source(ROOT / "gui/benchmark_history_panel.py")
    assert "staging = ctk.CTkFrame(self._history_host" in panel
    assert "staging.update_idletasks()" in panel
    assert "HISTORY_INITIAL_VISIBLE = 5" in history
    assert "HISTORY_PAGE_SIZE = 5" in history
    assert "filtros en una segunda fila estable" in history


def test_v192_removes_dead_duplicate_gpu_view():
    text = _source(ROOT / "gui/health_center_panel.py")
    assert text.count("def _render_benchmark_gpu_view") == 1
