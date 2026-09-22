from pathlib import Path
import inspect

from core import version
from core import benchmark_engine as engine
from core import directx_scene as scene
from core import directx_benchmark as dx
from core.benchmark_version import GPU_BENCHMARK_LABEL, GPU_BENCHMARK_METHOD, GPU_RESULT_FILENAME

ROOT = Path(__file__).resolve().parents[1]
HISTORY = (ROOT / 'gui' / 'benchmark_history_panel.py').read_text(encoding='utf-8')
PANEL = (ROOT / 'gui' / 'benchmark_panel.py').read_text(encoding='utf-8')
GUI = (ROOT / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')


def test_v196_windows_mainline_identity_is_v19():
    assert version.VERSION == '196'
    assert GPU_BENCHMARK_LABEL == 'V19'
    assert engine.GPU_METHOD_ID == GPU_BENCHMARK_METHOD
    assert engine.GPU_LAST_RESULT_RELATIVE_PATH.name == GPU_RESULT_FILENAME == 'benchmark_gpu_v19_ultimo_resultado.json'


def test_v19_standard_timing_contract_stays_49_seconds():
    levels = scene.profile_levels('standard')
    assert [row.measure_seconds for row in levels] == [10.0, 12.0, 12.0, 15.0]
    assert sum(row.measure_seconds for row in levels) == 49.0
    assert levels[0].warmup_seconds == 5.0


def test_v19_keeps_draw_calls_but_adds_small_jet_geometry_detail():
    assert scene.mesh_triangles(scene.build_jet()[1]) == 368
    assert scene.mesh_triangles(scene.build_tree()[1]) == 328
    assert scene.mesh_triangles(scene.build_water()[1]) == 72962
    assert all(scene.level_workload(row)['draw_calls_per_frame'] == 7 for row in scene.profile_levels('standard'))


def test_v19_shader_has_3d_jet_formation_water_breakup_and_tree_morphology():
    source = inspect.getsource(dx)
    assert 'jets V19: V tridimensional con variación determinista' in source
    assert 'float3 rotateX' in source and 'float3 rotateZ' in source
    assert 'float exhaust=step(1.05,i.uv.y)' in source
    assert 'float shorelineBreak=' in source
    assert 'float crown=hash11(id*19.13+2.1);' in source
    assert 'float a0=dot(xz,float2(0.0067,-0.0041))' in source


def test_v19_result_does_not_overwrite_v18(tmp_path, monkeypatch):
    old = tmp_path / 'resultados' / 'benchmark_gpu_v18_ultimo_resultado.json'
    old.parent.mkdir(parents=True, exist_ok=True)
    old.write_text('{"status":"OLD_V18"}\n', encoding='utf-8')
    monkeypatch.setattr(engine, 'executable_root', lambda: tmp_path)
    out = engine.save_last_gpu_v19_result({'status': 'OK', 'value': 19.0})
    assert out.name == 'benchmark_gpu_v19_ultimo_resultado.json'
    assert old.read_text(encoding='utf-8') == '{"status":"OLD_V18"}\n'
    assert '19.0' in out.read_text(encoding='utf-8')


def test_history_first_paint_is_fast_and_rest_prefetches_in_background():
    assert "latest_benchmark_sessions(limit=20)" in PANEL
    assert "CorePulseBenchmarkHistoryPrefetch" in PANEL
    assert "panel.set_sessions_cache(full, total_count=total)" in PANEL
    assert "def set_sessions_cache" in HISTORY
    assert "if reload_from_store or not self._sessions" in HISTORY


def test_history_cards_use_component_chips_not_one_dense_metric_line():
    start = HISTORY.index('    def _render_session_card')
    end = HISTORY.index('    def _toggle_detail', start)
    card = HISTORY[start:end]
    assert 'self._render_session_metrics(card, session)' in card
    assert 'text=_metric_text(session)' not in card
    assert 'GPU · Extreme' in HISTORY
    assert 'CPU · SHA-256' in HISTORY
    assert 'RAM · Copia' in HISTORY
    assert 'SSD · Lectura' in HISTORY


def test_evidence_has_open_folder_and_copy_path_without_exposing_full_path_as_primary():
    assert "text='Abrir carpeta'" in GUI
    assert 'def _open_benchmark_result_folder' in GUI
    assert 'la ruta completa está disponible en «Copiar ruta»' in GUI
