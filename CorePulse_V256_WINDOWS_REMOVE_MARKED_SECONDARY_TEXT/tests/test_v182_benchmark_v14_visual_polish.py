from pathlib import Path
import math
import tempfile
from unittest.mock import patch

from core import benchmark_engine as engine
from core import directx_scene as scene


def test_v182_version_and_method_are_v14():
    from core.version import VERSION, STAGE
    assert VERSION == "182"
    assert "V14" in STAGE
    assert "V14_" in engine.GPU_METHOD_ID
    assert "BENCHMARK_14_" in engine.BENCHMARK_METHOD_ID


def test_v14_result_does_not_overwrite_v13():
    with tempfile.TemporaryDirectory() as folder:
        root=Path(folder); r=root/"resultados"; r.mkdir()
        old=r/"benchmark_gpu_v13_ultimo_resultado.json"; old.write_text("v13",encoding="utf-8")
        with patch.object(engine,"executable_root",return_value=root):
            out=engine.save_last_gpu_v14_result({"status":"OK","value":None})
        assert out.name == "benchmark_gpu_v14_ultimo_resultado.json"
        assert old.read_text(encoding="utf-8") == "v13"


def test_standard_timing_contract_is_preserved():
    levels=scene.profile_levels("standard")
    assert [x.measure_seconds for x in levels] == [10.0,12.0,12.0,15.0]
    assert sum(x.measure_seconds for x in levels) == 49.0
    assert levels[0].warmup_seconds == 5.0


def test_water_is_larger_without_more_grid_triangles():
    verts,idx=scene.build_water()
    xs=[v[0] for v in verts]; zs=[v[2] for v in verts]
    assert round(max(xs)-min(xs),1) == 760.0
    assert round(max(zs)-min(zs),1) == 760.0
    assert len(idx)//3 == 2*(scene.WATER_RESOLUTION-1)**2


def test_visual_geometry_is_deterministic_and_finite():
    for builder in (scene.build_tree,scene.build_jet,scene.build_water):
        a=builder(); b=builder(); assert a==b
        verts,idx=a
        assert all(math.isfinite(x) for row in verts for x in row)
        assert len(idx)%3==0 and all(0<=i<len(verts) for i in idx)


def test_shader_contains_v14_antirepetition_and_leaf_aa():
    text=(Path(__file__).resolve().parents[1]/"core/directx_benchmark.py").read_text(encoding="utf-8")
    assert "water V14: ondas no armónicas" in text
    assert "domain=(warp.rg*2.0-1.0)*0.17" in text
    assert "float aa=max(fwidth(leafShape)*1.35,0.012)" in text
    assert text.count("float backlight=pow(saturate(dot(-L,V)),3.0);") == 1
