from pathlib import Path
import math, tempfile
from unittest.mock import patch

from core import benchmark_engine as engine
from core import directx_scene as scene


def test_v184_version_and_v16_runtime_ids():
    from core.version import VERSION, STAGE
    assert VERSION == '184'
    assert 'V16' in STAGE
    assert 'BENCHMARK_16_' in engine.BENCHMARK_METHOD_ID
    assert 'SCENES_V16_' in engine.GPU_METHOD_ID
    assert engine.GPU_LAST_RESULT_RELATIVE_PATH.name == 'benchmark_gpu_v16_ultimo_resultado.json'


def test_v16_result_stream_is_independent_from_v15():
    with tempfile.TemporaryDirectory() as folder:
        root=Path(folder); results=root/'resultados'; results.mkdir()
        old=results/'benchmark_gpu_v15_ultimo_resultado.json'; old.write_text('v15', encoding='utf-8')
        with patch.object(engine, 'executable_root', return_value=root):
            out=engine.save_last_gpu_v16_result({'status':'OK'})
        assert out.name == 'benchmark_gpu_v16_ultimo_resultado.json'
        assert old.read_text(encoding='utf-8') == 'v15'


def test_v16_metadata_has_no_v14_or_v15_runtime_leak():
    root=Path(__file__).resolve().parents[1]
    dx=(root/'core/directx_benchmark.py').read_text(encoding='utf-8')
    eng=(root/'core/benchmark_engine.py').read_text(encoding='utf-8')
    ui=(root/'gui/health_center_panel.py').read_text(encoding='utf-8')
    pres=(root/'core/benchmark_presentation.py').read_text(encoding='utf-8')
    forbidden=(
        'COREPULSE_GPU_DIRECTX11_SCENES_V14_WALLCLOCK_DETERMINISTIC',
        'COREPULSE_GPU_DIRECTX11_SCENES_V15_WALLCLOCK_DETERMINISTIC',
        'VISIBLE_REALISTIC_VALLEY_V14_WALLCLOCK_DETERMINISTIC',
        'DIRECTX11_REALISTIC_VALLEY_V14_WALLCLOCK_DETERMINISTIC_GPU_TIMESTAMP',
        'REAL_OR_NA_DIRECTX11_V14_WALLCLOCK_GPU_TIMESTAMP',
        'DirectX 11 · Valle realista V14 · polished',
        'V14 hace 5 s de warm-up global',
    )
    runtime='\n'.join((dx,eng,ui,pres))
    for token in forbidden:
        assert token not in runtime
    assert 'COREPULSE_GPU_DIRECTX11_SCENES_V16_WALLCLOCK_DETERMINISTIC' in runtime
    assert 'VISIBLE_REALISTIC_VALLEY_V16_WALLCLOCK_DETERMINISTIC' in runtime
    assert 'DirectX 11 · Valle realista V16 · visual cleanup' in runtime


def test_timing_and_water_contract_are_preserved():
    levels=scene.profile_levels('standard')
    assert [x.measure_seconds for x in levels] == [10.0,12.0,12.0,15.0]
    assert sum(x.measure_seconds for x in levels) == 49.0
    assert levels[0].warmup_seconds == 5.0
    verts,idx=scene.build_water()
    xs=[v[0] for v in verts]; zs=[v[2] for v in verts]
    assert round(max(xs)-min(xs),1) == 760.0
    assert round(max(zs)-min(zs),1) == 760.0
    assert len(idx)//3 == 2*(scene.WATER_RESOLUTION-1)**2


def test_tree_keeps_geometry_cost_but_changes_card_layout_deterministically():
    a=scene.build_tree(); b=scene.build_tree()
    assert a == b
    verts,idx=a
    assert len(idx)//3 == 328
    assert all(math.isfinite(x) for row in verts for x in row)
    assert all(0 <= i < len(verts) for i in idx)
    src=(Path(__file__).resolve().parents[1]/'core/directx_scene.py').read_text(encoding='utf-8')
    assert 'yaw_offsets = (0.0, 0.93, 2.06)' in src
    assert 'scale_x = (0.79, 0.73, 0.76)' in src
    assert 'for k in range(3):' in src


def test_leaf_shader_uses_single_sample_and_internal_breakup():
    text=(Path(__file__).resolve().parents[1]/'core/directx_benchmark.py').read_text(encoding='utf-8')
    region=text[text.index('float4 leafTex='):text.index('} else { // rocks')]
    assert region.count('NoiseTex.Sample') == 1
    assert 'float breakup=' in region
    assert 'float cutout=' in region
    assert 'clip(min(coverage,cutout)' in region


def test_ui_thermal_scope_and_short_settle():
    text=(Path(__file__).resolve().parents[1]/'gui/health_center_panel.py').read_text(encoding='utf-8')
    assert 'Evidencia térmica durante la prueba GPU' in text
    assert 'sólo a las muestras de la fase GPU DirectX' in text
    assert 'self.scroll.defer_until_idle(self._settle_visual_benchmark_result_paint)' in text
    assert 'for delay in (32, 96):' in text
    assert 'for delay in (24, 90, 180, 420, 900):' not in text
    settle=text[text.index('def _settle_visual_benchmark_result_paint'):text.index('def _refresh_visual_benchmark_result_in_place')]
    assert 'canvas.update()' not in settle
