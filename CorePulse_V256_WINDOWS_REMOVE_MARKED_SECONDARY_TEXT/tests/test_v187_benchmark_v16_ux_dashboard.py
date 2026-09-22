from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_V16 = {
    'core/directx_benchmark.py': 'a9106f3157a0a7e8cc54e4924d5afe2c0d99c78823a45c1acdb86b90c3d88437',
    'core/directx_scene.py': '879f7a664d2616fa5485477e9475393bf11bd5b2d082cfaf2bf934ac5c05f5ee',
    'core/benchmark_engine.py': 'c77426c5b56632cda58c13af0a032470656ef3ae55e81ac209a8ea4d5fb40fe5',
}

def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def test_v187_keeps_benchmark_v16_byte_identical():
    from core.version import VERSION, STAGE
    from core import benchmark_engine as engine
    assert VERSION == '187'
    assert 'V16' in STAGE
    assert engine.GPU_LAST_RESULT_RELATIVE_PATH.name == 'benchmark_gpu_v16_ultimo_resultado.json'
    for rel, digest in EXPECTED_V16.items():
        assert _sha(ROOT / rel) == digest, rel

def test_benchmark_first_open_is_progressive_and_history_is_lazy():
    text = (ROOT / 'gui/benchmark_panel.py').read_text(encoding='utf-8')
    assert 'self._benchmark = None' in text
    assert 'self._history = None' in text
    assert 'self._schedule_run_build()' in text
    assert 'def _schedule_history_build(self):' in text
    assert 'Preparando Benchmark' in text
    # Las dos vistas pesadas se importan sólo dentro del constructor diferido.
    before_class = text[:text.index('class BenchmarkPanel:')]
    assert 'from gui.health_center_panel import HealthCenterPanel' not in before_class
    assert 'from gui.benchmark_history_panel import BenchmarkHistoryPanel' not in before_class

def test_result_is_progressively_disclosed_in_four_views():
    text = (ROOT / 'gui/health_center_panel.py').read_text(encoding='utf-8')
    for token in (
        "('summary', 'Resumen')",
        "('gpu', 'GPU')",
        "('system', 'CPU · RAM · SSD')",
        "('evidence', 'Evidencia')",
        'def _render_benchmark_summary_view',
        'def _render_benchmark_gpu_view',
        'def _render_benchmark_system_view',
        'def _render_benchmark_evidence_view',
    ):
        assert token in text
    assert "self._benchmark_result_view = 'summary'" in text

def test_sensor_and_json_details_are_not_in_initial_setup_wall():
    text = (ROOT / 'gui/health_center_panel.py').read_text(encoding='utf-8')
    start = text.index('def _render_gaming_benchmark_section')
    end = text.index('def _format_visual_metric', start)
    region = text[start:end]
    assert 'self._render_sensor_compatibility()' not in region
    assert 'ruta JSON quedan en las pestañas del resultado' in region
    evidence = text[text.index('def _render_benchmark_evidence_view'):text.index('def _render_visual_benchmark_result_body')]
    assert 'self._render_sensor_compatibility(parent=shell)' in evidence
    assert 'Copiar ruta' in evidence

def test_completed_run_collapses_setup_but_can_reopen_it():
    text = (ROOT / 'gui/health_center_panel.py').read_text(encoding='utf-8')
    assert 'def _set_benchmark_setup_collapsed(self, collapsed):' in text
    assert 'def _show_benchmark_setup(self):' in text
    assert "text='Cambiar componentes'" in text
    done_region = text[text.index("self._visual_bench = combined"):text.index("if overall == 'OK'", text.index("self._visual_bench = combined"))]
    assert "self._benchmark_result_view = 'summary'" in done_region
    assert 'self._set_benchmark_setup_collapsed(True)' in done_region

def test_finish_focuses_summary_and_history_keeps_loading_shell_until_built():
    panel = (ROOT / 'gui/benchmark_panel.py').read_text(encoding='utf-8')
    health = (ROOT / 'gui/health_center_panel.py').read_text(encoding='utf-8')
    assert 'panel = BenchmarkHistoryPanel(self.app, self._history_host)' in panel
    assert 'self._history = panel' in panel
    assert 'self.app.after_idle(lambda: self.scroll.yview_moveto(0.0)' in health

