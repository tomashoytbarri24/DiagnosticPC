from pathlib import Path
import math, tempfile
from unittest.mock import patch
from core import benchmark_engine as engine
from core import directx_scene as scene


def test_version_and_method_v15():
    from core.version import VERSION, STAGE
    assert VERSION == '183'
    assert 'V15' in STAGE
    assert 'BENCHMARK_15_' in engine.BENCHMARK_METHOD_ID
    assert 'SCENES_V15_' in engine.GPU_METHOD_ID


def test_v15_json_is_independent():
    with tempfile.TemporaryDirectory() as folder:
        root=Path(folder); r=root/'resultados'; r.mkdir()
        old14=r/'benchmark_gpu_v14_ultimo_resultado.json'; old14.write_text('v14')
        with patch.object(engine,'executable_root',return_value=root):
            out=engine.save_last_gpu_v15_result({'status':'OK'})
        assert out.name == 'benchmark_gpu_v15_ultimo_resultado.json'
        assert old14.read_text() == 'v14'


def test_standard_measured_time_unchanged():
    levels=scene.profile_levels('standard')
    assert [x.measure_seconds for x in levels] == [10.0,12.0,12.0,15.0]
    assert sum(x.measure_seconds for x in levels) == 49.0
    assert levels[0].warmup_seconds == 5.0


def test_water_v14_preserved():
    verts,idx=scene.build_water(); xs=[v[0] for v in verts]; zs=[v[2] for v in verts]
    assert round(max(xs)-min(xs),1)==760.0 and round(max(zs)-min(zs),1)==760.0
    assert len(idx)//3 == 2*(scene.WATER_RESOLUTION-1)**2


def test_tree_is_deterministic_finite_and_lighter_than_v14():
    a=scene.build_tree(); b=scene.build_tree(); assert a==b
    verts,idx=a
    assert len(idx)//3 == 328
    assert all(math.isfinite(x) for row in verts for x in row)
    assert all(0<=i<len(verts) for i in idx)


def test_v15_shader_reuses_leaf_sample_and_has_three_card_comment():
    root=Path(__file__).resolve().parents[1]
    dx=(root/'core/directx_benchmark.py').read_text()
    sc=(root/'core/directx_scene.py').read_text()
    assert 'V15: silueta lobulada aireada' in dx
    assert 'float variation=saturate(leafTex.r*0.62+leafTex.g*0.38);' in dx
    assert 'for k in range(3):' in sc
    assert 'phase+k*math.pi/3.0' in sc


def test_ui_repaint_has_long_tail_settle():
    text=(Path(__file__).resolve().parents[1]/'gui/health_center_panel.py').read_text()
    assert 'for delay in (24, 90, 180, 420, 900):' in text
    assert 'canvas.update()' in text
