from __future__ import annotations

import ctypes

from core import directx_benchmark as dx
from core.directx_scene import profile_levels


class FakeCOM(ctypes.Structure):
    _fields_ = [('lpVtbl', ctypes.POINTER(ctypes.c_void_p))]


def _fake_com(size, specs, calls):
    table = (ctypes.c_void_p * size)()
    keepalive = []
    for index, (restype, argtypes, label, retval) in specs.items():
        proto = dx.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)
        if restype is None:
            def make_void(name):
                def fn(_self, *args):
                    calls.append(name)
                return fn
            cb = proto(make_void(label))
        else:
            def make_ret(name, value):
                def fn(_self, *args):
                    calls.append(name)
                    return value
                return fn
            cb = proto(make_ret(label, retval))
        keepalive.append(cb)
        table[index] = ctypes.cast(cb, ctypes.c_void_p).value
    obj = FakeCOM(ctypes.cast(table, ctypes.POINTER(ctypes.c_void_p)))
    keepalive.extend([table, obj])
    return ctypes.cast(ctypes.pointer(obj), ctypes.c_void_p), keepalive


def test_v174_om_set_depth_stencil_state_uses_real_d3d11_slot_36():
    # ID3D11DeviceContext slot 34 is OMSetRenderTargetsAndUnorderedAccessViews;
    # OMSetDepthStencilState is slot 36. Calling slot 34 with the two-argument
    # depth-state signature corrupts the call ABI and can cause access violations.
    assert dx.CTX_OM_SET_RENDER_TARGETS == 33
    assert dx.CTX_OM_SET_BLEND_STATE == 35
    assert dx.CTX_OM_SET_DEPTH_STENCIL_STATE == 36


def test_v174_render_frame_exercises_readonly_depth_state_without_wrong_slot():
    calls=[]
    U=dx.UINT; F=dx.FLOAT; VP=ctypes.c_void_p
    specs={
        dx.CTX_VS_SET_CONSTANT_BUFFERS:(None,(U,U,ctypes.POINTER(VP)),'VSSetConstantBuffers',None),
        dx.CTX_PS_SET_SHADER_RESOURCES:(None,(U,U,ctypes.POINTER(VP)),'PSSetShaderResources',None),
        dx.CTX_PS_SET_SHADER:(None,(VP,VP,U),'PSSetShader',None),
        dx.CTX_PS_SET_SAMPLERS:(None,(U,U,ctypes.POINTER(VP)),'PSSetSamplers',None),
        dx.CTX_VS_SET_SHADER:(None,(VP,VP,U),'VSSetShader',None),
        dx.CTX_DRAW_INDEXED:(None,(U,U,ctypes.c_int),'DrawIndexed',None),
        dx.CTX_PS_SET_CONSTANT_BUFFERS:(None,(U,U,ctypes.POINTER(VP)),'PSSetConstantBuffers',None),
        dx.CTX_IA_SET_INPUT_LAYOUT:(None,(VP,),'IASetInputLayout',None),
        dx.CTX_IA_SET_VERTEX_BUFFERS:(None,(U,U,ctypes.POINTER(VP),ctypes.POINTER(U),ctypes.POINTER(U)),'IASetVertexBuffers',None),
        dx.CTX_IA_SET_INDEX_BUFFER:(None,(VP,U,U),'IASetIndexBuffer',None),
        dx.CTX_DRAW_INDEXED_INSTANCED:(None,(U,U,U,ctypes.c_int,U),'DrawIndexedInstanced',None),
        dx.CTX_IA_SET_PRIMITIVE_TOPOLOGY:(None,(U,),'IASetPrimitiveTopology',None),
        dx.CTX_OM_SET_RENDER_TARGETS:(None,(U,ctypes.POINTER(VP),VP),'OMSetRenderTargets',None),
        dx.CTX_OM_SET_BLEND_STATE:(None,(VP,ctypes.POINTER(F),U),'OMSetBlendState',None),
        dx.CTX_OM_SET_DEPTH_STENCIL_STATE:(None,(VP,U),'OMSetDepthStencilState',None),
        dx.CTX_RS_SET_STATE:(None,(VP,),'RSSetState',None),
        dx.CTX_RS_SET_VIEWPORTS:(None,(U,ctypes.POINTER(dx.D3D11_VIEWPORT)),'RSSetViewports',None),
        dx.CTX_UPDATE_SUBRESOURCE:(None,(VP,U,VP,VP,U,U),'UpdateSubresource',None),
        dx.CTX_CLEAR_RENDER_TARGET_VIEW:(None,(VP,ctypes.POINTER(F)),'ClearRenderTargetView',None),
        dx.CTX_CLEAR_DEPTH_STENCIL_VIEW:(None,(VP,U,F,ctypes.c_ubyte),'ClearDepthStencilView',None),
    }
    context,keep_ctx=_fake_com(64,specs,calls)
    swap,keep_swap=_fake_com(12,{8:(dx.HRESULT,(U,U),'Present',0)},calls)
    r=dx.D3D11Renderer.__new__(dx.D3D11Renderer)
    r.context=context; r.swap=swap; r.rtv=VP(1); r.dsv=VP(2); r.raster=VP(3); r.layout=VP(4)
    r.vs=VP(5); r.ps=VP(6); r.cbuffer=VP(7); r.noise_srv=VP(8); r.sampler=VP(9); r.blend=VP(10); r.depth_readonly=VP(13)
    r.width=1280; r.height=720; r.visible=False; r._shown=False; r.hwnd=None; r.cancelled=False; r.gpu_timer=None
    r.pump=lambda:None; r._show_if_ready=lambda:None
    mesh=dx._Mesh(VP(11),VP(12),6)
    r.meshes={'sky':mesh,'water':mesh,'rock':mesh,'tree':mesh,'jet':mesh,'cloud':mesh}
    level=profile_levels('quick')[0]; r.terrain_meshes={level.terrain_resolution:mesh}
    r._test_keepalive=(keep_ctx,keep_swap)
    r.render_frame(level,0.25,0,show_after_present=False)
    assert calls.count('OMSetDepthStencilState') >= 3
    assert calls[-1] == 'Present'
