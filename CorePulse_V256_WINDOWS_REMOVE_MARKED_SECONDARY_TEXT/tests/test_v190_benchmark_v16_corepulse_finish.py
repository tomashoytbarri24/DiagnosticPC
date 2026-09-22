from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parents[1]

V189_SCENE_SHA = '879f7a664d2616fa5485477e9475393bf11bd5b2d082cfaf2bf934ac5c05f5ee'
V189_ENGINE_SHA = 'c77426c5b56632cda58c13af0a032470656ef3ae55e81ac209a8ea4d5fb40fe5'
V189_HLSL_SHA = 'c0367450991a682dd9ece98c7a3d1c5b5062fbafb7f37a51c3ce197a632b5b9f'


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source(path):
    return path.read_text(encoding='utf-8')


def _func_block(text, name):
    start = text.index(f'    def {name}(')
    end = text.find('\n    def ', start + 5)
    if end < 0:
        end = len(text)
    return text[start:end]


def test_v190_version_and_v16_result_contract():
    from core.version import VERSION, STAGE
    from core import benchmark_engine as engine
    assert VERSION == '190'
    assert 'BENCHMARK_V16_COREPULSE_FINISH' in STAGE
    assert engine.GPU_LAST_RESULT_RELATIVE_PATH.name == 'benchmark_gpu_v16_ultimo_resultado.json'


def test_v190_keeps_v16_measured_workload_and_shaders_identical():
    assert _sha(ROOT / 'core/directx_scene.py') == V189_SCENE_SHA
    assert _sha(ROOT / 'core/benchmark_engine.py') == V189_ENGINE_SHA
    text = _source(ROOT / 'core/directx_benchmark.py')
    match = re.search(r"HLSL = r'''(.*?)'''", text, re.S)
    assert match
    assert hashlib.sha256(match.group(1).encode()).hexdigest() == V189_HLSL_SHA


def test_v190_directx_window_owns_cursor_without_touching_timed_workload():
    text = _source(ROOT / 'core/directx_benchmark.py')
    init = _func_block(text, '_init_window')
    show = _func_block(text, '_show_if_ready')
    assert 'WM_SETCURSOR = 0x0020' in text
    assert 'if msg == WM_SETCURSOR:' in init
    assert 'hit_test == HTCLIENT' in init
    assert 'self.user32.SetCursor(None)' in init
    assert 'return 1' in init
    assert 'self.user32.SetCursor(None)' in show
    # prepare_timed_frame owns pump/show work outside the caller timed interval.
    prep = _func_block(text, 'prepare_timed_frame')
    assert 'self.pump()' in prep
    assert 'self._show_if_ready()' in prep


def test_v190_benchmark_has_consistent_visual_scale_and_corepulse_identity():
    health = _source(ROOT / 'gui/health_center_panel.py')
    bench = _source(ROOT / 'gui/benchmark_panel.py')
    assert 'BENCH_FONT_TITLE = 16' in health
    assert 'BENCH_FONT_SECTION = 11' in health
    assert 'BENCH_FONT_BODY = 10' in health
    assert 'BENCH_FONT_META = 9' in health
    assert 'BENCH_FONT_MICRO = 8' in health
    assert "COREPULSE  ·  BENCHMARK GPU V16" in health
    assert "text='Prueba actual'" in bench
    assert "('MEDICIÓN REAL', ACCENT)" in bench
    assert "('REAL_OR_NA', '#10b981')" in bench
    assert 'BENCH_TITLE = 24' in bench


def test_v190_benchmark_views_do_not_use_seven_point_text():
    text = _source(ROOT / 'gui/health_center_panel.py')
    for name in (
        '_render_gaming_benchmark_section',
        '_render_benchmark_result_nav',
        '_result_component_card',
        '_render_benchmark_summary_view',
        '_render_benchmark_gpu_view',
        '_system_metric_row',
        '_render_benchmark_system_view',
        '_render_benchmark_evidence_view',
        '_render_visual_benchmark_result_body',
    ):
        block = _func_block(text, name)
        assert 'font=(FONT, 7' not in block, name


def test_v190_instant_critical_is_observed_amber_until_sustained():
    from core.agent_reaction import agent_display_state

    instant = {
        'severity': 'CRITICAL',
        'status': 'CPU muy cerca de TjMax',
        'reasons': ['CPU a 1.0 °C de TjMax'],
    }
    state = agent_display_state({'overall': 'NORMAL', 'alerts': {'active': []}}, instant)
    assert state['status'] == 'OBSERVANDO'
    assert state['tone'] == 'AMBER'
    assert state['border_level'] == 'WARNING'
    assert 'persistencia' in state['detail']

    sustained = agent_display_state(
        {'overall': 'CRITICAL', 'alerts': {'active': [{'level': 'CRITICAL', 'title': 'Temperatura sostenida'}]}},
        instant,
    )
    assert sustained['status'] == 'REACCIONANDO'
    assert sustained['tone'] == 'RED'
    assert sustained['border_level'] == 'CRITICAL'


def test_v190_live_alert_card_uses_amber_for_unsustained_instant_critical():
    raw = (ROOT / 'gui/live_health_binding.py').read_bytes().decode('utf-8')
    assert 'Temperatura alta en observación' in raw
    assert "alert_color = AMBER" in raw
    assert "icon = '◷'" in raw
