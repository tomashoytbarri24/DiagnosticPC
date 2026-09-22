from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parents[1]

V190_SCENE_SHA = '879f7a664d2616fa5485477e9475393bf11bd5b2d082cfaf2bf934ac5c05f5ee'
V190_ENGINE_SHA = 'c77426c5b56632cda58c13af0a032470656ef3ae55e81ac209a8ea4d5fb40fe5'
V190_DIRECTX_SHA = '648c2caec5f6e4b3abf52dc1c3b16c93f67e7127a909be76d46113b6d1aa64a0'
V190_HLSL_SHA = 'c0367450991a682dd9ece98c7a3d1c5b5062fbafb7f37a51c3ce197a632b5b9f'


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source(path):
    return path.read_text(encoding='utf-8')


def test_v191_version_and_v16_contract():
    from core.version import VERSION, STAGE
    from core import benchmark_engine as engine
    assert VERSION == '191'
    assert 'BENCHMARK_V16_UX_REFINEMENT' in STAGE
    assert engine.GPU_LAST_RESULT_RELATIVE_PATH.name == 'benchmark_gpu_v16_ultimo_resultado.json'


def test_v191_keeps_v16_workload_byte_identical_to_v190():
    assert _sha(ROOT / 'core/directx_scene.py') == V190_SCENE_SHA
    assert _sha(ROOT / 'core/benchmark_engine.py') == V190_ENGINE_SHA
    assert _sha(ROOT / 'core/directx_benchmark.py') == V190_DIRECTX_SHA
    text = _source(ROOT / 'core/directx_benchmark.py')
    match = re.search(r"HLSL = r'''(.*?)'''", text, re.S)
    assert match
    assert hashlib.sha256(match.group(1).encode()).hexdigest() == V190_HLSL_SHA


def test_v191_setup_is_compacted_to_avoid_unnecessary_scroll():
    text = _source(ROOT / 'gui/health_center_panel.py')
    assert "head.pack(fill='x', padx=14, pady=(10, 5))" in text
    assert "grid.pack(fill='x', padx=8, pady=(0, 6))" in text
    assert "action.pack(fill='x', padx=12, pady=(0, 6))" in text
    assert 'scroll innecesario en 1280x800' in text
    assert 'self._benchmark_hint_shell = None' in text


def test_v191_history_uses_progressive_disclosure():
    text = _source(ROOT / 'gui/benchmark_history_panel.py')
    assert 'HISTORY_INITIAL_VISIBLE = 12' in text
    assert 'HISTORY_PAGE_SIZE = 12' in text
    assert 'Ejecuciones recientes' in text
    assert 'Mostrar {step} más' in text
    assert 'for session in sessions[:visible]' in text
    assert 'for session in sessions[:50]' not in text


def test_v191_evidence_path_uses_corepulse_surface_palette():
    text = _source(ROOT / 'gui/health_center_panel.py')
    assert 'fg_color=BENCH_SURFACE_SOFT' in text
    assert 'text_color=TEXT2' in text
    assert "Evidencia térmica · fase GPU" in text
    assert "Protección térmica CPU" in text
    assert "Sin gatillo · racha" in text


def test_v191_history_loading_copy_is_progressive():
    text = _source(ROOT / 'gui/benchmark_panel.py')
    assert 'Preparando las ejecuciones más recientes' in text
    assert 'podrás cargar más sólo si lo necesitas' in text
