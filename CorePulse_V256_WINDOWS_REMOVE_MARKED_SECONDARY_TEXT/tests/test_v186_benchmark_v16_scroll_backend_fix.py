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

def test_v186_version_keeps_benchmark_v16():
    from core.version import VERSION, STAGE
    from core import benchmark_engine as engine
    assert VERSION == '186'
    assert 'V16' in STAGE
    assert engine.GPU_LAST_RESULT_RELATIVE_PATH.name == 'benchmark_gpu_v16_ultimo_resultado.json'
    assert 'SCENES_V16_' in engine.GPU_METHOD_ID

def test_v16_workload_is_byte_identical_to_v185():
    for rel, digest in EXPECTED_V16.items():
        assert _sha(ROOT / rel) == digest, rel

def test_benchmark_page_uses_place_viewport_only_for_benchmark_only():
    text = (ROOT / 'gui/health_center_panel.py').read_text(encoding='utf-8')
    assert "scroll_backend = 'place' if self._benchmark_only else 'canvas'" in text
    assert "StableScrollHost(self.frame, fg_color=BG, backend=scroll_backend)" in text

def test_place_backend_does_not_use_canvas_create_window():
    text = (ROOT / 'gui/stable_scroll.py').read_text(encoding='utf-8')
    assert "self._backend = 'place' if" in text
    assert "self.content.place(x=0, y=0, relwidth=1.0)" in text
    assert "if self._backend == 'place':" in text
    # create_window remains only in the legacy canvas branch.
    branch = text[text.index("if self._backend == 'place':"):text.index("self.content.bind('<Configure>'")]
    assert "self._window_item = None" in branch
    assert "create_window" in branch  # legacy else branch preserved

def test_place_backend_scroll_is_pixel_clamped_and_reports_fraction():
    text = (ROOT / 'gui/stable_scroll.py').read_text(encoding='utf-8')
    assert 'def _place_metrics(self):' in text
    assert 'max_offset = max(0.0, float(total_h - viewport_h))' in text
    assert 'self._place_offset_y = max(0.0, min(max_offset, float(offset)))' in text
    assert 'self.content.place_configure(y=-int(round(self._place_offset_y)))' in text
    assert 'def _place_moveto(self, fraction):' in text
    assert 'def _place_scroll_pixels(self, pixels):' in text

def test_health_center_restores_scroll_through_host_api_first():
    text = (ROOT / 'gui/health_center_panel.py').read_text(encoding='utf-8')
    start = text.index('fraction = self._restore_scroll_fraction')
    end = text.index('self._rendering = False', start)
    region = text[start:end]
    assert region.index('self.scroll.yview_moveto') < region.index('self.scroll.canvas.yview_moveto')
    assert "getattr(self.scroll, 'backend', 'canvas') == 'canvas'" in region

