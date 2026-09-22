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


def test_v188_keeps_gpu_v16_workload_byte_identical():
    from core.version import VERSION, STAGE
    from core import benchmark_engine as engine
    assert VERSION == '188'
    assert 'V16' in STAGE
    assert engine.GPU_LAST_RESULT_RELATIVE_PATH.name == 'benchmark_gpu_v16_ultimo_resultado.json'
    for rel, digest in EXPECTED_V16.items():
        assert _sha(ROOT / rel) == digest, rel


def test_hud_is_external_real_or_na_and_cursor_is_restored():
    text = (ROOT / 'gui/health_center_panel.py').read_text(encoding='utf-8')
    assert 'class _BenchmarkHudOverlay:' in text
    assert "re.search(r'([0-9]+(?:[\\.,][0-9]+)?)\\s*FPS\\b'" in text
    assert "fps_text = 'FPS N/A'" in text
    assert "fps_text = 'WARM-UP · FPS N/A'" in text
    assert 'self._cursor_restore_calls = calls' in text
    assert 'for _ in range(calls):' in text
    assert 'user32.ShowCursor(True)' in text
    # El renderer V16 no contiene el HUD: permanece byte-identical arriba.
    assert '_BenchmarkHudOverlay' not in (ROOT / 'core/directx_benchmark.py').read_text(encoding='utf-8')


def test_completed_dashboard_hides_setup_and_exposes_compact_actions():
    text = (ROOT / 'gui/health_center_panel.py').read_text(encoding='utf-8')
    region = text[text.index('def _set_benchmark_setup_collapsed'):text.index('def _show_benchmark_setup')]
    assert 'component.pack_forget()' in region
    assert 'action.pack_forget()' in region
    assert "text='Repetir prueba'" in text
    assert "text='Cambiar componentes'" in text
    assert "specs.append(('GPU · Extreme'" in text
    assert "specs.append(('CPU · SHA-256'" in text
    assert "specs.append(('RAM · Copia'" in text
    assert "specs.append(('SSD · Lectura'" in text


def test_sensor_compatibility_is_progressively_disclosed():
    text = (ROOT / 'gui/health_center_panel.py').read_text(encoding='utf-8')
    evidence = text[text.index('def _render_benchmark_evidence_view'):text.index('def _render_visual_benchmark_result_body')]
    assert "text='Ver sensores'" in evidence or "else 'Ver sensores'" in evidence
    assert 'self._benchmark_evidence_sensors_expanded' in evidence
    assert 'if self._benchmark_evidence_sensors_expanded:' in evidence
    assert 'self._render_sensor_compatibility(parent=shell)' in evidence


def test_result_tabs_reset_viewport_and_repeat_reenters_running_state():
    text = (ROOT / 'gui/health_center_panel.py').read_text(encoding='utf-8')
    setter = text[text.index('def _set_benchmark_result_view'):text.index('def _render_benchmark_result_nav')]
    assert 'self.scroll.yview_moveto(0.0)' in setter
    run = text[text.index('def _run_visual_benchmark'):text.index('def _render_sensor_compatibility')]
    assert 'had_previous_result = isinstance(self._visual_bench, dict)' in run
    assert 'self._visual_bench = None' in run
    assert "started = self._async('visual_benchmark', work, done)" in run
    assert 'self._request_render(1)' in run
