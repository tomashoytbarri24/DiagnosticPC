from pathlib import Path
import inspect

from core import version
from core import benchmark_engine as engine
from core import directx_scene as scene
from core import directx_benchmark as dx
from core.benchmark_version import GPU_BENCHMARK_LABEL, GPU_BENCHMARK_METHOD, GPU_RESULT_FILENAME

ROOT = Path(__file__).resolve().parents[1]
GUI = (ROOT / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')
PANEL = (ROOT / 'gui' / 'benchmark_panel.py').read_text(encoding='utf-8')
PRESENT = (ROOT / 'core' / 'benchmark_presentation.py').read_text(encoding='utf-8')


def test_v195_identity_is_centralized_v18():
    assert version.VERSION == '195'
    assert GPU_BENCHMARK_LABEL == 'V18'
    assert engine.GPU_METHOD_ID == GPU_BENCHMARK_METHOD
    assert engine.GPU_LAST_RESULT_RELATIVE_PATH.name == GPU_RESULT_FILENAME == 'benchmark_gpu_v18_ultimo_resultado.json'
    assert "DX_WINDOW_TITLE = f'CorePulse Benchmark {GPU_BENCHMARK_LABEL} — DirectX 11'" in GUI


def test_v18_standard_timing_contract_is_preserved():
    levels = scene.profile_levels('standard')
    assert [row.measure_seconds for row in levels] == [10.0, 12.0, 12.0, 15.0]
    assert sum(row.measure_seconds for row in levels) == 49.0
    assert levels[0].warmup_seconds == 5.0


def test_v18_jet_formation_is_not_a_single_horizontal_row():
    source = inspect.getsource(dx)
    assert 'jets V18: dos formaciones en V' in source
    assert 'float pair=floor((local+1.0)/2.0);' in source
    assert 'float side=' in source
    assert 'fogStrength=(type > 1.5 && type < 2.5) ? 0.43 : 0.72' in source


def test_static_result_tabs_are_prebuilt_and_raised_not_full_rebuilt():
    assert 'def _build_static_benchmark_result_pages' in GUI
    assert "for key in ('summary', 'gpu', 'system', 'evidence')" in GUI
    assert 'page.tkraise()' in GUI
    set_view = GUI[GUI.index('    def _set_benchmark_result_view'):GUI.index('    def _render_benchmark_result_nav')]
    assert '_show_static_benchmark_result_page(view)' in set_view


def test_summary_has_no_legacy_duplicate_gpu_grid_block():
    start = GUI.index('    def _render_benchmark_summary_view')
    end = GUI.index('    def _toggle_benchmark_detail', start)
    summary = GUI[start:end]
    assert 'phase_results' not in summary
    assert 'gpu_frame_time_avg_ms' not in summary


def test_current_ui_does_not_expose_v16_label():
    assert "text='COREPULSE  ·  BENCHMARK GPU V16'" not in GUI
    assert 'CorePulse Benchmark V16 · DirectX 11' not in GUI
    assert 'Benchmark V16 · DirectX 11 · tiempo determinista' not in PRESENT


def test_history_is_loaded_off_tk_thread():
    assert 'threading.Thread(target=read_worker' in PANEL
    assert 'preloaded_sessions=sessions' in PANEL


def test_v18_result_path_does_not_overwrite_v17(tmp_path, monkeypatch):
    old = tmp_path / 'resultados' / 'benchmark_gpu_v17_ultimo_resultado.json'
    old.parent.mkdir(parents=True, exist_ok=True)
    old.write_text('{"status":"OLD_V17"}\n', encoding='utf-8')
    monkeypatch.setattr(engine, 'executable_root', lambda: tmp_path)
    out = engine.save_last_gpu_v18_result({'status': 'OK', 'value': 12.3})
    assert out.name == 'benchmark_gpu_v18_ultimo_resultado.json'
    assert old.read_text(encoding='utf-8') == '{"status":"OLD_V17"}\n'
    assert '12.3' in out.read_text(encoding='utf-8')
