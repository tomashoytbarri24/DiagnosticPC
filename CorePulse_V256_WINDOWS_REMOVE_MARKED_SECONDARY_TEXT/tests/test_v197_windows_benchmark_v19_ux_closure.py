from pathlib import Path
import hashlib

from core import version
from core import benchmark_engine as engine
from core.benchmark_version import GPU_BENCHMARK_LABEL, GPU_RESULT_FILENAME

ROOT = Path(__file__).resolve().parents[1]
HISTORY = (ROOT / 'gui' / 'benchmark_history_panel.py').read_text(encoding='utf-8')
PANEL = (ROOT / 'gui' / 'benchmark_panel.py').read_text(encoding='utf-8')
GUI = (ROOT / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')


def _sha(rel):
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


def test_v197_identity_keeps_gpu_v19():
    assert version.VERSION == '197'
    assert GPU_BENCHMARK_LABEL == 'V19'
    assert engine.GPU_LAST_RESULT_RELATIVE_PATH.name == GPU_RESULT_FILENAME == 'benchmark_gpu_v19_ultimo_resultado.json'


def test_v197_keeps_v19_measured_workload_byte_identical():
    assert _sha('core/directx_scene.py') == '21716b2013cfcee87330f81620a71791952024474af2e734c30d4c7fa6f32e2b'
    assert _sha('core/directx_benchmark.py') == '754b46a53e379db6bb4cec1b109a4231b86f391395067a0efa28ac6495f68cd7'
    assert _sha('core/benchmark_engine.py') == '255be8fc4267944472a060e8fd793bc5cbb2471cd3d692911a5bb3d9d0e56891'


def test_history_first_paint_is_smaller_and_background_prefetch_remains():
    assert 'HISTORY_INITIAL_VISIBLE = 3' in HISTORY
    assert 'HISTORY_PAGE_SIZE = 3' in HISTORY
    assert 'HISTORY_FAST_PRELOAD = 5' in HISTORY
    assert 'latest_benchmark_sessions(limit=5)' in PANEL
    assert 'CorePulseBenchmarkHistoryPrefetch' in PANEL
    assert 'panel.set_sessions_cache(full, total_count=total)' in PANEL


def test_technical_labels_are_human_readable_but_keep_real_values():
    assert 'Frame presentado' in GUI
    assert 'Variación' in GUI
    assert 'Frames lentos' in GUI
    assert 'Compresión zlib' in GUI
    assert 'Descompresión zlib' in GUI
    assert 'Variación (CV)' in GUI
    assert 'Muestras sobre' in GUI


def test_thermal_summary_has_direct_evidence_action():
    assert "text='Ver evidencia térmica'" in GUI
    assert "command=lambda: self._set_benchmark_result_view('evidence')" in GUI


def test_v19_result_path_contract_unchanged():
    assert engine.GPU_LAST_RESULT_RELATIVE_PATH.as_posix() == 'resultados/benchmark_gpu_v19_ultimo_resultado.json'
