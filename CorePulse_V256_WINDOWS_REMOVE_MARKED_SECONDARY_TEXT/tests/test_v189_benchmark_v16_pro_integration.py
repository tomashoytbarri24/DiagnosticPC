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

def test_v189_keeps_gpu_v16_workload_byte_identical():
    from core.version import VERSION, STAGE
    from core import benchmark_engine as engine
    assert VERSION == '189'
    assert 'BENCHMARK_V16_PRO_INTEGRATION' in STAGE
    assert engine.GPU_LAST_RESULT_RELATIVE_PATH.name == 'benchmark_gpu_v16_ultimo_resultado.json'
    for rel, digest in EXPECTED_V16.items():
        assert _sha(ROOT / rel) == digest, rel

def test_v189_hud_is_branded_real_or_na_and_external():
    text = (ROOT / 'gui/health_center_panel.py').read_text(encoding='utf-8')
    assert "COREPULSE  /  BENCHMARK GPU V16" in text
    assert "FPS REAL" in text
    assert "value, state = 'N/A', 'WARM-UP'" in text
    assert "value, state = 'N/A', 'SETTLE'" in text
    assert "re.search(r'([0-9]+(?:[\\.,][0-9]+)?)\\s*FPS\\b'" in text
    assert "_BenchmarkHudOverlay" not in (ROOT / 'core/directx_benchmark.py').read_text(encoding='utf-8')

def test_v189_cursor_guard_targets_directx_hwnd_and_restores_it():
    text = (ROOT / 'gui/health_center_panel.py').read_text(encoding='utf-8')
    assert "DX_WINDOW_TITLE = 'CorePulse Benchmark V16 — DirectX 11'" in text
    assert "FindWindowW(None, self.DX_WINDOW_TITLE)" in text
    assert "_GCLP_HCURSOR = -12" in text
    assert "set_class(hwnd, self._GCLP_HCURSOR, None)" in text
    assert "self._restore_directx_window_cursor()" in text
    assert "user32.ShowCursor(True)" in text

def test_v189_benchmark_uses_corepulse_accent_and_clearer_labels():
    bench = (ROOT / 'gui/benchmark_panel.py').read_text(encoding='utf-8')
    health = (ROOT / 'gui/health_center_panel.py').read_text(encoding='utf-8')
    assert "ACCENT = '#2aa9e9'" in bench
    assert "BENCH_ACCENT = '#2aa9e9'" in health
    assert "('gpu', 'GPU 3D')" in health
    assert "('system', 'Sistema')" in health
    assert "Resultado de esta ejecución" in health
    assert "Configurar benchmark" in health

def test_v189_benchmark_only_skips_irrelevant_battery_probe():
    text = (ROOT / 'gui/health_center_panel.py').read_text(encoding='utf-8')
    init = text[text.index('def __init__(self, app, host'):text.index('def _seed_preloaded_battery_state')]
    assert "if not self._benchmark_only:" in init
    assert "self._seed_preloaded_battery_state()" in init

def test_v189_first_load_has_visible_indeterminate_shell():
    text = (ROOT / 'gui/benchmark_panel.py').read_text(encoding='utf-8')
    assert "mode='indeterminate'" in text
    assert "bar.start()" in text
    assert "self.app.after(80, build)" in text
    assert "todavía no se ejecuta ninguna carga" in text
