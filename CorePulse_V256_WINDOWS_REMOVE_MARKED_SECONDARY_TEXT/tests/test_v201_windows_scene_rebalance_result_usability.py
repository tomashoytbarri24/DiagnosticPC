from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v201_version_and_gpu_v21_contract():
    from core import version, benchmark_engine
    from core.benchmark_version import GPU_BENCHMARK_VERSION, GPU_BENCHMARK_LABEL
    assert version.VERSION == "201"
    assert "BENCHMARK_V21_SCENE_REBALANCE_RESULT_USABILITY" in version.STAGE
    assert GPU_BENCHMARK_VERSION == 21
    assert GPU_BENCHMARK_LABEL == "V21"
    assert benchmark_engine.GPU_LAST_RESULT_RELATIVE_PATH.name == "benchmark_gpu_v21_ultimo_resultado.json"
    assert "V21" in benchmark_engine.GPU_METHOD_ID


def test_v201_scene_rebalances_aircraft_and_adds_boat_smoke():
    from core.directx_scene import SCENE_LEVELS, level_workload, build_boat
    assert [s.jet_instances for s in SCENE_LEVELS] == [1, 1, 1, 1]
    assert [getattr(s, 'boat_instances', 0) for s in SCENE_LEVELS] == [1, 1, 1, 1]
    assert [getattr(s, 'smoke_instances', 0) for s in SCENE_LEVELS] == [0, 0, 0, 1]
    workloads = [level_workload(s) for s in SCENE_LEVELS]
    assert [row['draw_calls_per_frame'] for row in workloads] == [8, 8, 8, 9]
    verts, idx = build_boat()
    assert len(verts) > 0 and len(idx) > 0


def test_v201_hlsl_mentions_boat_smoke_and_single_aircraft():
    src = (ROOT / 'core/directx_benchmark.py').read_text(encoding='utf-8')
    assert 'jets V21: un único avión protagonista' in src
    assert 'boat V21: bote navegando con cabeceo suave' in src
    assert 'smoke V21: fogata en isla del modo máximo' in src
    assert "self._draw(self.meshes['boat']" in src
    assert "self._draw(self.meshes['smoke']" in src


def test_v201_summary_ui_exposes_quick_glance_strip():
    src = (ROOT / 'gui/health_center_panel.py').read_text(encoding='utf-8')
    assert "('summary', 'Resumen rápido')" in src
    assert 'def _render_benchmark_glance_strip' in src
    assert 'Lo esencial antes de abrir detalle' in src
    assert 'self._render_benchmark_glance_strip(shell, glance_entries)' in src


def test_v201_save_aliases_target_current_v21_file(tmp_path, monkeypatch):
    from core import benchmark_engine as be
    monkeypatch.setattr(be, 'executable_root', lambda: tmp_path)
    out = be.save_last_gpu_v21_result({'status': 'OK', 'fps': 1.0})
    assert out.name == 'benchmark_gpu_v21_ultimo_resultado.json'
    assert out.exists()
    out2 = be.save_last_gpu_v20_result({'status': 'OK', 'fps': 2.0})
    assert out2 == out
