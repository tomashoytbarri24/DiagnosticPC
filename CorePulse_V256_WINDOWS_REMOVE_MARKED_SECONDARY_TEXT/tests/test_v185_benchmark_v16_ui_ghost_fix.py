from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_V184 = {
    'core/directx_benchmark.py': 'a9106f3157a0a7e8cc54e4924d5afe2c0d99c78823a45c1acdb86b90c3d88437',
    'core/directx_scene.py': '879f7a664d2616fa5485477e9475393bf11bd5b2d082cfaf2bf934ac5c05f5ee',
    'core/benchmark_engine.py': 'c77426c5b56632cda58c13af0a032470656ef3ae55e81ac209a8ea4d5fb40fe5',
}

def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def test_v185_version_keeps_benchmark_v16():
    from core.version import VERSION, STAGE
    from core import benchmark_engine as engine
    assert VERSION == '185'
    assert 'V16' in STAGE
    assert engine.GPU_LAST_RESULT_RELATIVE_PATH.name == 'benchmark_gpu_v16_ultimo_resultado.json'
    assert 'SCENES_V16_' in engine.GPU_METHOD_ID

def test_v16_workload_files_are_byte_identical_to_v184():
    for rel, digest in EXPECTED_V184.items():
        assert _sha(ROOT / rel) == digest, rel

def test_windows_wheel_uses_frame_limited_strong_repaint():
    text=(ROOT/'gui/stable_scroll.py').read_text(encoding='utf-8')
    assert 'self._schedule_repaint(strong=(sys.platform == \'win32\'))' in text
    assert 'self._repaint_strong_pending = bool(self._repaint_strong_pending or strong)' in text
    assert 'strong = bool(strong or self._repaint_strong_pending)' in text
    assert 'flags |= 0x0004 | 0x0200' in text
    assert 'self.after(delay, self._flush_repaint)' in text

def test_scroll_patch_does_not_add_reentrant_update():
    text=(ROOT/'gui/stable_scroll.py').read_text(encoding='utf-8')
    start=text.index('def _after_direct_scroll')
    end=text.index('def _on_canvas_yview')
    region=text[start:end]
    assert '.update()' not in region
    assert 'update_idletasks()' in region
