"""Benchmark 3D DirectX 11 de CorePulse V25 (safe boat route + visual scene polish + audited steady-state timing).

Objetivo: una prueba gráfica de alto nivel, visible, determinista y auditable.
El workload aumenta por niveles y la medición se basa únicamente en frames
realmente presentados durante la ventana de medición. El warm-up queda fuera.

En plataformas no Windows o si Direct3D no puede inicializarse se devuelve N/A;
no existe fallback silencioso al benchmark OpenGL anterior porque cambiaría la
metodología.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import asdict
import math
import os
import platform
import statistics
import re
import struct
import threading
import time
from typing import Any, Callable, Optional

from core.benchmark_version import GPU_BENCHMARK_LABEL, GPU_BENCHMARK_METHOD, GPU_PROVIDER, GPU_POLICY
from core.directx_scene import (
    SceneLevel, profile_levels, build_terrain, build_water, build_jet,
    build_tree, build_rock, build_cloud, build_sky, build_boat, build_smoke_plume, build_fire_billboard, level_workload,
)

ProgressCallback = Optional[Callable[[float, str, str], None]]
TelemetrySampler = Optional[Callable[[], dict]]
CancelCheck = Optional[Callable[[], bool]]

WINFUNCTYPE = getattr(ctypes, 'WINFUNCTYPE', ctypes.CFUNCTYPE)

HWND_T = getattr(wintypes, 'HWND', wintypes.HANDLE)
HINSTANCE_T = getattr(wintypes, 'HINSTANCE', wintypes.HANDLE)
HICON_T = getattr(wintypes, 'HICON', wintypes.HANDLE)
HCURSOR_T = getattr(wintypes, 'HCURSOR', wintypes.HANDLE)
HBRUSH_T = getattr(wintypes, 'HBRUSH', wintypes.HANDLE)
HMENU_T = getattr(wintypes, 'HMENU', wintypes.HANDLE)
HRESULT = ctypes.c_long
UINT = ctypes.c_uint
BOOL = ctypes.c_int
FLOAT = ctypes.c_float
SIZE_T = ctypes.c_size_t
LPVOID = ctypes.c_void_p

S_OK = 0
D3D11_SDK_VERSION = 7
D3D_DRIVER_TYPE_HARDWARE = 1
D3D11_CREATE_DEVICE_BGRA_SUPPORT = 0x20
D3D_FEATURE_LEVEL_11_0 = 0xB000
D3D_FEATURE_LEVEL_10_1 = 0xA100
D3D_FEATURE_LEVEL_10_0 = 0xA000

DXGI_FORMAT_R32G32B32_FLOAT = 6
DXGI_FORMAT_R32G32_FLOAT = 16
DXGI_FORMAT_R32_UINT = 42
DXGI_FORMAT_R8G8B8A8_UNORM = 28
DXGI_FORMAT_D24_UNORM_S8_UINT = 45
DXGI_USAGE_RENDER_TARGET_OUTPUT = 0x20
DXGI_SWAP_EFFECT_DISCARD = 0

D3D11_USAGE_DEFAULT = 0
D3D11_USAGE_IMMUTABLE = 1
D3D11_BIND_VERTEX_BUFFER = 0x1
D3D11_BIND_INDEX_BUFFER = 0x2
D3D11_BIND_CONSTANT_BUFFER = 0x4
D3D11_BIND_SHADER_RESOURCE = 0x8
D3D11_BIND_DEPTH_STENCIL = 0x40
D3D11_INPUT_PER_VERTEX_DATA = 0
D3D11_PRIMITIVE_TOPOLOGY_TRIANGLELIST = 4
D3D11_CLEAR_DEPTH = 0x1
D3D11_CLEAR_STENCIL = 0x2
D3D11_FILTER_MIN_MAG_MIP_LINEAR = 0x15
D3D11_TEXTURE_ADDRESS_WRAP = 1
D3D11_COMPARISON_NEVER = 1
D3D11_COMPARISON_LESS = 2
D3D11_DEPTH_WRITE_MASK_ZERO = 0
D3D11_DEPTH_WRITE_MASK_ALL = 1
D3D11_STENCIL_OP_KEEP = 1
D3D11_BLEND_ZERO = 1
D3D11_BLEND_ONE = 2
D3D11_BLEND_SRC_ALPHA = 5
D3D11_BLEND_INV_SRC_ALPHA = 6
D3D11_BLEND_OP_ADD = 1
D3D11_COLOR_WRITE_ENABLE_ALL = 0x0F
D3D11_FILL_SOLID = 3
D3D11_CULL_NONE = 1
D3D11_QUERY_TIMESTAMP = 2
D3D11_QUERY_TIMESTAMP_DISJOINT = 3
D3D11_ASYNC_GETDATA_DONOTFLUSH = 0x1
S_FALSE = 1

# ID3D11DeviceContext hereda 4 métodos de ID3D11DeviceChild además de IUnknown.
# V167 omitió esos 4 slots al invocar la vtable, causando access violations reales
# en Windows. Estos índices corresponden al orden oficial de d3d11.h.
CTX_VS_SET_CONSTANT_BUFFERS = 7
CTX_PS_SET_SHADER_RESOURCES = 8
CTX_PS_SET_SHADER = 9
CTX_PS_SET_SAMPLERS = 10
CTX_VS_SET_SHADER = 11
CTX_DRAW_INDEXED = 12
CTX_PS_SET_CONSTANT_BUFFERS = 16
CTX_IA_SET_INPUT_LAYOUT = 17
CTX_IA_SET_VERTEX_BUFFERS = 18
CTX_IA_SET_INDEX_BUFFER = 19
CTX_DRAW_INDEXED_INSTANCED = 20
CTX_IA_SET_PRIMITIVE_TOPOLOGY = 24
CTX_BEGIN = 27
CTX_END = 28
CTX_GET_DATA = 29
CTX_OM_SET_RENDER_TARGETS = 33
CTX_OM_SET_DEPTH_STENCIL_STATE = 36
CTX_OM_SET_BLEND_STATE = 35
CTX_RS_SET_STATE = 43
CTX_RS_SET_VIEWPORTS = 44
CTX_UPDATE_SUBRESOURCE = 48
CTX_CLEAR_RENDER_TARGET_VIEW = 50
CTX_CLEAR_DEPTH_STENCIL_VIEW = 53

WM_CLOSE = 0x0010
WM_DESTROY = 0x0002
WM_SETCURSOR = 0x0020
HTCLIENT = 1
WM_KEYDOWN = 0x0100
VK_ESCAPE = 0x1B
WS_POPUP = 0x80000000
PM_REMOVE = 0x0001
SW_SHOW = 5
WS_CAPTION = 0x00C00000
WS_SYSMENU = 0x00080000
WS_MINIMIZEBOX = 0x00020000
WS_VISIBLE = 0x10000000


class GUID(ctypes.Structure):
    _fields_ = [('Data1', ctypes.c_uint32), ('Data2', ctypes.c_uint16), ('Data3', ctypes.c_uint16), ('Data4', ctypes.c_ubyte * 8)]

    @classmethod
    def from_parts(cls, d1, d2, d3, *d4):
        return cls(d1, d2, d3, (ctypes.c_ubyte * 8)(*d4))


IID_ID3D11Texture2D = GUID.from_parts(0x6f15aaf2, 0xd208, 0x4e89, 0x9a,0xb4,0x48,0x95,0x35,0xd3,0x4f,0x9c)
IID_IDXGIDevice = GUID.from_parts(0x54ec77fa, 0x1377, 0x44e6, 0x8c,0x32,0x88,0xfd,0x5f,0x44,0xc8,0x4c)


class DXGI_RATIONAL(ctypes.Structure):
    _fields_ = [('Numerator', UINT), ('Denominator', UINT)]


class DXGI_MODE_DESC(ctypes.Structure):
    _fields_ = [('Width', UINT), ('Height', UINT), ('RefreshRate', DXGI_RATIONAL), ('Format', UINT), ('ScanlineOrdering', UINT), ('Scaling', UINT)]


class DXGI_SAMPLE_DESC(ctypes.Structure):
    _fields_ = [('Count', UINT), ('Quality', UINT)]


class DXGI_SWAP_CHAIN_DESC(ctypes.Structure):
    _fields_ = [
        ('BufferDesc', DXGI_MODE_DESC), ('SampleDesc', DXGI_SAMPLE_DESC), ('BufferUsage', UINT),
        ('BufferCount', UINT), ('OutputWindow', HWND_T), ('Windowed', BOOL),
        ('SwapEffect', UINT), ('Flags', UINT),
    ]


class D3D11_BUFFER_DESC(ctypes.Structure):
    _fields_ = [('ByteWidth', UINT), ('Usage', UINT), ('BindFlags', UINT), ('CPUAccessFlags', UINT), ('MiscFlags', UINT), ('StructureByteStride', UINT)]


class D3D11_SUBRESOURCE_DATA(ctypes.Structure):
    _fields_ = [('pSysMem', LPVOID), ('SysMemPitch', UINT), ('SysMemSlicePitch', UINT)]


class D3D11_TEXTURE2D_DESC(ctypes.Structure):
    _fields_ = [
        ('Width', UINT), ('Height', UINT), ('MipLevels', UINT), ('ArraySize', UINT), ('Format', UINT),
        ('SampleDesc', DXGI_SAMPLE_DESC), ('Usage', UINT), ('BindFlags', UINT), ('CPUAccessFlags', UINT), ('MiscFlags', UINT),
    ]


class D3D11_INPUT_ELEMENT_DESC(ctypes.Structure):
    _fields_ = [
        ('SemanticName', ctypes.c_char_p), ('SemanticIndex', UINT), ('Format', UINT), ('InputSlot', UINT),
        ('AlignedByteOffset', UINT), ('InputSlotClass', UINT), ('InstanceDataStepRate', UINT),
    ]


class D3D11_VIEWPORT(ctypes.Structure):
    _fields_ = [('TopLeftX', FLOAT), ('TopLeftY', FLOAT), ('Width', FLOAT), ('Height', FLOAT), ('MinDepth', FLOAT), ('MaxDepth', FLOAT)]


class D3D11_SAMPLER_DESC(ctypes.Structure):
    _fields_ = [
        ('Filter', UINT), ('AddressU', UINT), ('AddressV', UINT), ('AddressW', UINT), ('MipLODBias', FLOAT),
        ('MaxAnisotropy', UINT), ('ComparisonFunc', UINT), ('BorderColor', FLOAT * 4), ('MinLOD', FLOAT), ('MaxLOD', FLOAT),
    ]


class D3D11_RENDER_TARGET_BLEND_DESC(ctypes.Structure):
    _fields_ = [
        ('BlendEnable', BOOL), ('SrcBlend', UINT), ('DestBlend', UINT), ('BlendOp', UINT),
        ('SrcBlendAlpha', UINT), ('DestBlendAlpha', UINT), ('BlendOpAlpha', UINT), ('RenderTargetWriteMask', ctypes.c_ubyte),
        ('_pad', ctypes.c_ubyte * 3),
    ]


class D3D11_BLEND_DESC(ctypes.Structure):
    _fields_ = [('AlphaToCoverageEnable', BOOL), ('IndependentBlendEnable', BOOL), ('RenderTarget', D3D11_RENDER_TARGET_BLEND_DESC * 8)]


class D3D11_DEPTH_STENCILOP_DESC(ctypes.Structure):
    _fields_ = [('StencilFailOp', UINT), ('StencilDepthFailOp', UINT), ('StencilPassOp', UINT), ('StencilFunc', UINT)]


class D3D11_DEPTH_STENCIL_DESC(ctypes.Structure):
    _fields_ = [
        ('DepthEnable', BOOL), ('DepthWriteMask', UINT), ('DepthFunc', UINT), ('StencilEnable', BOOL),
        ('StencilReadMask', ctypes.c_ubyte), ('StencilWriteMask', ctypes.c_ubyte), ('_pad', ctypes.c_ubyte * 2),
        ('FrontFace', D3D11_DEPTH_STENCILOP_DESC), ('BackFace', D3D11_DEPTH_STENCILOP_DESC),
    ]


class D3D11_RASTERIZER_DESC(ctypes.Structure):
    _fields_ = [
        ('FillMode', UINT), ('CullMode', UINT), ('FrontCounterClockwise', BOOL), ('DepthBias', ctypes.c_int),
        ('DepthBiasClamp', FLOAT), ('SlopeScaledDepthBias', FLOAT), ('DepthClipEnable', BOOL), ('ScissorEnable', BOOL),
        ('MultisampleEnable', BOOL), ('AntialiasedLineEnable', BOOL),
    ]


class D3D11_QUERY_DESC(ctypes.Structure):
    _fields_ = [('Query', UINT), ('MiscFlags', UINT)]


class D3D11_QUERY_DATA_TIMESTAMP_DISJOINT(ctypes.Structure):
    _fields_ = [('Frequency', ctypes.c_uint64), ('Disjoint', BOOL)]


class RECT(ctypes.Structure):
    _fields_ = [('left', ctypes.c_long), ('top', ctypes.c_long), ('right', ctypes.c_long), ('bottom', ctypes.c_long)]


class POINT(ctypes.Structure):
    _fields_ = [('x', ctypes.c_long), ('y', ctypes.c_long)]


class MSG(ctypes.Structure):
    _fields_ = [
        ('hwnd', HWND_T), ('message', UINT), ('wParam', wintypes.WPARAM), ('lParam', wintypes.LPARAM),
        ('time', wintypes.DWORD), ('pt', POINT), ('lPrivate', wintypes.DWORD),
    ]


LRESULT = ctypes.c_ssize_t
WNDPROC = WINFUNCTYPE(LRESULT, HWND_T, UINT, wintypes.WPARAM, wintypes.LPARAM)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ('style', UINT), ('lpfnWndProc', WNDPROC), ('cbClsExtra', ctypes.c_int), ('cbWndExtra', ctypes.c_int),
        ('hInstance', HINSTANCE_T), ('hIcon', HICON_T), ('hCursor', HCURSOR_T),
        ('hbrBackground', HBRUSH_T), ('lpszMenuName', wintypes.LPCWSTR), ('lpszClassName', wintypes.LPCWSTR),
    ]


class DXGI_ADAPTER_DESC(ctypes.Structure):
    _fields_ = [
        ('Description', ctypes.c_wchar * 128), ('VendorId', UINT), ('DeviceId', UINT), ('SubSysId', UINT), ('Revision', UINT),
        ('DedicatedVideoMemory', SIZE_T), ('DedicatedSystemMemory', SIZE_T), ('SharedSystemMemory', SIZE_T), ('AdapterLuidLowPart', UINT), ('AdapterLuidHighPart', ctypes.c_long),
    ]


def _hr_ok(hr) -> bool:
    return int(hr) >= 0


def _com_method(ptr, index: int, restype, *argtypes):
    if not ptr:
        raise RuntimeError('COM pointer nulo')
    vtbl = ctypes.cast(ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    address = vtbl[index]
    if not address:
        raise RuntimeError(f'Método COM {index} no disponible')
    return WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)(address)


def _release(ptr):
    if ptr:
        try:
            _com_method(ptr, 2, ctypes.c_ulong)(ptr)
        except Exception:
            pass


def _query_interface(ptr, iid: GUID):
    out = ctypes.c_void_p()
    hr = _com_method(ptr, 0, HRESULT, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p))(ptr, ctypes.byref(iid), ctypes.byref(out))
    return out if _hr_ok(hr) and out.value else None


def _blob_bytes(blob) -> bytes:
    get_ptr = _com_method(blob, 3, ctypes.c_void_p)(blob)
    get_size = _com_method(blob, 4, SIZE_T)(blob)
    return ctypes.string_at(get_ptr, int(get_size))


def _compile_shader(source: str, entry: bytes, target: bytes):
    compiler = None
    last = None
    for name in ('d3dcompiler_47.dll', 'd3dcompiler_46.dll', 'd3dcompiler_43.dll'):
        try:
            compiler = ctypes.WinDLL(name)
            break
        except Exception as exc:
            last = exc
    if compiler is None:
        raise RuntimeError(f'D3DCompiler no disponible: {last}')
    fn = compiler.D3DCompile
    fn.argtypes = [LPVOID, SIZE_T, ctypes.c_char_p, LPVOID, LPVOID, ctypes.c_char_p, ctypes.c_char_p, UINT, UINT, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p)]
    fn.restype = HRESULT
    raw = source.encode('utf-8')
    code = ctypes.c_void_p(); errors = ctypes.c_void_p()
    buf = ctypes.create_string_buffer(raw)
    hr = fn(ctypes.cast(buf, LPVOID), len(raw), f'CorePulse{GPU_BENCHMARK_LABEL}.hlsl'.encode('ascii'), None, None, entry, target, 0x00008000, 0, ctypes.byref(code), ctypes.byref(errors))
    try:
        if not _hr_ok(hr) or not code.value:
            message = _blob_bytes(errors).decode('utf-8', 'replace') if errors.value else f'HRESULT 0x{int(hr)&0xffffffff:08X}'
            raise RuntimeError(f'Error compilando {entry.decode()}/{target.decode()}: {message}')
        return code, _blob_bytes(code)
    finally:
        if errors.value:
            _release(errors)


def _vec_sub(a, b): return (a[0]-b[0], a[1]-b[1], a[2]-b[2])
def _dot(a,b): return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]
def _cross(a,b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def _norm(v):
    l=math.sqrt(_dot(v,v)) or 1.0
    return (v[0]/l,v[1]/l,v[2]/l)


def _mat_mul(a,b):
    return [[sum(a[r][k]*b[k][c] for k in range(4)) for c in range(4)] for r in range(4)]


def _look_at_lh(eye, at, up=(0.0,1.0,0.0)):
    z=_norm(_vec_sub(at,eye)); x=_norm(_cross(up,z)); y=_cross(z,x)
    return [
        [x[0], y[0], z[0], 0.0],
        [x[1], y[1], z[1], 0.0],
        [x[2], y[2], z[2], 0.0],
        [-_dot(x,eye), -_dot(y,eye), -_dot(z,eye), 1.0],
    ]


def _perspective_fov_lh(fov_y, aspect, zn, zf):
    y=1.0/math.tan(fov_y/2.0); x=y/aspect
    return [[x,0,0,0],[0,y,0,0],[0,0,zf/(zf-zn),1.0],[0,0,-zn*zf/(zf-zn),0]]


def _flatten_matrix(m):
    return [float(v) for row in m for v in row]


def _camera_at(t: float, level_index: int):
    # Recorrido suave reproducible. Las escenas posteriores vuelan más cerca del terreno.
    phase=t*0.11 + level_index*0.9
    radius=150.0 - level_index*10.0
    eye=(math.sin(phase)*radius, 48.0 + 8.0*math.sin(phase*0.7), -115.0 + math.cos(phase)*90.0)
    target=(12.0*math.sin(phase*0.35), 12.0, 5.0+20.0*math.cos(phase*0.4))
    return eye,target


def _percentile(values, p):
    if not values:
        return None
    data=sorted(float(x) for x in values)
    pos=(len(data)-1)*float(p)
    lo=int(math.floor(pos)); hi=int(math.ceil(pos))
    if lo==hi: return data[lo]
    return data[lo]*(hi-pos)+data[hi]*(pos-lo)


def _fps_stats(frame_times_ms):
    vals=[float(x) for x in frame_times_ms if x and x>0]
    if not vals:
        return {'frames':0,'fps':None,'one_percent_low_fps':None,'frametime_avg_ms':None,'frametime_median_ms':None,'frametime_p95_ms':None,'frametime_p99_ms':None,'frametime_spike_threshold_ms':None,'frametime_spike_frames':0,'frametime_spike_ratio':None}
    total_s=sum(vals)/1000.0
    fps=len(vals)/total_s if total_s>0 else None
    one_count=max(1,math.ceil(len(vals)*0.01))
    worst=sorted(vals, reverse=True)[:one_count]
    one_low=1000.0/(sum(worst)/len(worst)) if worst else None
    med=statistics.median(vals)
    spike_threshold=max(med*2.0,med+4.0)
    spikes=sum(1 for x in vals if x>spike_threshold)
    return {
        'frames':len(vals),'fps':fps,'one_percent_low_fps':one_low,
        'frametime_avg_ms':sum(vals)/len(vals),'frametime_median_ms':med,
        'frametime_p95_ms':_percentile(vals,0.95),'frametime_p99_ms':_percentile(vals,0.99),
        'frametime_spike_threshold_ms':spike_threshold,'frametime_spike_frames':spikes,
        'frametime_spike_ratio':spikes/len(vals),
    }


def _gpu_time_stats(values_ms, total_frames: int = 0, dropped: int = 0, disjoint: int = 0):
    vals=[float(x) for x in values_ms if x is not None and math.isfinite(float(x)) and float(x) > 0.0]
    if not vals:
        return {
            'gpu_samples': 0, 'gpu_sample_coverage': 0.0 if total_frames else None,
            'gpu_frame_time_avg_ms': None, 'gpu_frame_time_median_ms': None,
            'gpu_frame_time_p95_ms': None, 'gpu_frame_time_p99_ms': None,
            'gpu_frame_time_min_ms': None, 'gpu_frame_time_max_ms': None,
            'gpu_equivalent_fps': None, 'gpu_query_dropped_frames': int(dropped or 0),
            'gpu_query_disjoint_frames': int(disjoint or 0), 'gpu_sample_overflow_discarded': 0,
        }
    # Una consulta válida corresponde como máximo a un frame medido. Cualquier
    # exceso indica un bug de contabilidad y se informa, nunca se presenta >100%.
    overflow=max(0,len(vals)-max(0,int(total_frames))) if total_frames else 0
    if total_frames and len(vals)>int(total_frames):
        vals=vals[-int(total_frames):]
    avg=sum(vals)/len(vals)
    return {
        'gpu_samples': len(vals),
        'gpu_sample_coverage': min(1.0,(len(vals)/max(1,int(total_frames)))) if total_frames else None,
        'gpu_sample_overflow_discarded': overflow,
        'gpu_frame_time_avg_ms': avg,
        'gpu_frame_time_median_ms': statistics.median(vals),
        'gpu_frame_time_p95_ms': _percentile(vals,0.95),
        'gpu_frame_time_p99_ms': _percentile(vals,0.99),
        'gpu_frame_time_min_ms': min(vals),
        'gpu_frame_time_max_ms': max(vals),
        'gpu_equivalent_fps': (1000.0/avg) if avg > 0 else None,
        'gpu_query_dropped_frames': int(dropped or 0),
        'gpu_query_disjoint_frames': int(disjoint or 0),
    }


class _GpuTimerSlot:
    __slots__=('disjoint','start','end','in_use')
    def __init__(self, disjoint=None, start=None, end=None):
        self.disjoint=disjoint or ctypes.c_void_p()
        self.start=start or ctypes.c_void_p()
        self.end=end or ctypes.c_void_p()
        self.in_use=False


class _GpuFrameTimer:
    """Timestamp queries D3D11 sin serializar cada frame.

    Usa un pool pre-creado. Begin/End delimitan una consulta DISJOINT por frame;
    los timestamps se obtienen de forma no bloqueante durante la escena y se
    drenan fuera de la ventana medida. Si el pool se agota se omite sólo la
    muestra GPU de ese frame; nunca se inventa un tiempo.
    """
    def __init__(self, device, context, slot_count: int = 64):
        self.device=device; self.context=context
        self.slots=[]; self.pending=[]; self.completed=[]
        self.dropped_frames=0; self.disjoint_frames=0
        for _ in range(max(8,int(slot_count))):
            slot=_GpuTimerSlot(
                self._create_query(D3D11_QUERY_TIMESTAMP_DISJOINT),
                self._create_query(D3D11_QUERY_TIMESTAMP),
                self._create_query(D3D11_QUERY_TIMESTAMP),
            )
            self.slots.append(slot)

    def _create_query(self, query_type):
        out=ctypes.c_void_p(); desc=D3D11_QUERY_DESC(int(query_type),0)
        hr=_com_method(self.device,24,HRESULT,ctypes.POINTER(D3D11_QUERY_DESC),ctypes.POINTER(ctypes.c_void_p))(self.device,ctypes.byref(desc),ctypes.byref(out))
        if not _hr_ok(hr) or not out.value:
            raise RuntimeError(f'CreateQuery({query_type}) falló 0x{int(hr)&0xffffffff:08X}')
        return out

    def reset_scene(self):
        # Debe llamarse después de drenar la escena anterior.
        self.completed=[]; self.dropped_frames=0; self.disjoint_frames=0

    def begin_frame(self):
        # V14: nunca consulta GetData aquí. El sondeo de queries se hace fuera
        # de la ventana CPU/Present para que la propia auditoría GPU no fabrique
        # spikes ni degrade artificialmente el 1% Low.
        slot=next((x for x in self.slots if not x.in_use),None)
        if slot is None:
            self.dropped_frames += 1
            return None
        slot.in_use=True
        _com_method(self.context,CTX_BEGIN,None,ctypes.c_void_p)(self.context,slot.disjoint)
        # D3D11_QUERY_TIMESTAMP se marca sólo con End; Begin no es válido.
        _com_method(self.context,CTX_END,None,ctypes.c_void_p)(self.context,slot.start)
        return slot

    def end_frame(self, slot):
        if slot is None:
            return
        _com_method(self.context,CTX_END,None,ctypes.c_void_p)(self.context,slot.end)
        _com_method(self.context,CTX_END,None,ctypes.c_void_p)(self.context,slot.disjoint)
        self.pending.append(slot)

    def _read_one(self, slot, flags):
        info=D3D11_QUERY_DATA_TIMESTAMP_DISJOINT()
        hr=_com_method(self.context,CTX_GET_DATA,HRESULT,ctypes.c_void_p,ctypes.c_void_p,UINT,UINT)(
            self.context,slot.disjoint,ctypes.byref(info),ctypes.sizeof(info),flags)
        if int(hr)==S_FALSE:
            return None
        if not _hr_ok(hr):
            return ('invalid',None)
        start=ctypes.c_uint64(); end=ctypes.c_uint64()
        hs=_com_method(self.context,CTX_GET_DATA,HRESULT,ctypes.c_void_p,ctypes.c_void_p,UINT,UINT)(self.context,slot.start,ctypes.byref(start),ctypes.sizeof(start),flags)
        he=_com_method(self.context,CTX_GET_DATA,HRESULT,ctypes.c_void_p,ctypes.c_void_p,UINT,UINT)(self.context,slot.end,ctypes.byref(end),ctypes.sizeof(end),flags)
        if int(hs)==S_FALSE or int(he)==S_FALSE:
            return None
        if not _hr_ok(hs) or not _hr_ok(he) or bool(info.Disjoint) or not info.Frequency or end.value <= start.value:
            return ('disjoint',None)
        ms=(end.value-start.value)*1000.0/float(info.Frequency)
        return ('ok',ms) if math.isfinite(ms) and ms>0.0 else ('invalid',None)

    def collect_ready(self, nonblocking=True):
        flags=D3D11_ASYNC_GETDATA_DONOTFLUSH if nonblocking else 0
        fresh=[]
        # GPU completa las consultas en orden; detenerse en la primera pendiente
        # evita sondear inútilmente todas las posteriores.
        while self.pending:
            slot=self.pending[0]
            got=self._read_one(slot,flags)
            if got is None:
                break
            self.pending.pop(0); slot.in_use=False
            state,value=got
            if state=='ok':
                self.completed.append(value); fresh.append(value)
            elif state=='disjoint':
                self.disjoint_frames += 1
        return fresh

    def drain(self, timeout_s: float = 4.0):
        deadline=time.perf_counter()+max(0.1,float(timeout_s))
        while self.pending and time.perf_counter()<deadline:
            before=len(self.pending)
            self.collect_ready(nonblocking=False)
            if len(self.pending)==before:
                time.sleep(0.001)
        if self.pending:
            self.dropped_frames += len(self.pending)
            for slot in self.pending:
                slot.in_use=False
            self.pending.clear()
        return list(self.completed)

    def close(self):
        for slot in self.slots:
            _release(slot.end); _release(slot.start); _release(slot.disjoint)
            slot.in_use=False
        self.pending.clear(); self.completed.clear(); self.slots.clear()




HLSL = r'''
cbuffer SceneCB : register(b0)
{
    row_major float4x4 ViewProj;
    float4 CameraTime;      // xyz camera, w time
    float4 SceneParams;     // x object type, y complexity level, z shader iterations, w texture samples
    float4 SceneParams2;    // x render width, y render height, z reserved, w reserved
};
Texture2D NoiseTex : register(t0);
SamplerState LinearWrap : register(s0);

struct VSIn { float3 pos:POSITION; float3 normal:NORMAL; float2 uv:TEXCOORD0; uint iid:SV_InstanceID; };
struct VSOut { float4 pos:SV_POSITION; float3 world:TEXCOORD0; float3 normal:TEXCOORD1; float2 uv:TEXCOORD2; float aux:TEXCOORD3; nointerpolation float instance:TEXCOORD4; };

float hash11(float n) { return frac(sin(n*12.9898)*43758.5453); }
float terrainH(float x, float z)
{
    float h=-4.5;
    float4 cx=float4(-105,70,10,145), cz=float4(-25,50,-110,-72), rr=float4(92,80,58,52), aa=float4(37,30,22,18);
    [unroll] for(int i=0;i<4;i++) {
        float2 d=float2((x-cx[i])/rr[i],(z-cz[i])/rr[i]);
        float r2=dot(d,d); float dome=saturate(1.0-r2);
        float detail=sin(x*0.075+cz[i]*0.01)*0.9+cos(z*0.064-cx[i]*0.01)*0.8+sin((x+z)*0.031)*0.7;
        h += dome*dome*aa[i] + dome*detail*2.3;
    }
    return h;
}
float3 rotateX(float3 p,float a){ float s=sin(a),c=cos(a); return float3(p.x,p.y*c-p.z*s,p.y*s+p.z*c); }
float3 rotateY(float3 p,float a){ float s=sin(a),c=cos(a); return float3(p.x*c-p.z*s,p.y,p.x*s+p.z*c); }
float3 rotateZ(float3 p,float a){ float s=sin(a),c=cos(a); return float3(p.x*c-p.y*s,p.x*s+p.y*c,p.z); }

VSOut VSMain(VSIn i)
{
    VSOut o; float3 p=i.pos; float3 n=i.normal; float type=SceneParams.x; float id=(float)i.iid;
    if(type > 1.5 && type < 2.5) { // jets V24: un único avión protagonista, limpio y legible
        float a=CameraTime.w*0.18;
        float j0=hash11(id*7.17+1.3)-0.5;
        float3 center=float3(sin(a)*18.0, 46.0+sin(a*0.63)*3.1, 26.0+cos(a*0.78)*6.4);
        float yaw=-0.18+sin(a*0.59)*0.11+j0*0.020;
        float pitch=sin(a*0.47+0.35)*0.026+j0*0.012;
        float roll=0.09+sin(a*0.91)*0.022;
        p=p*1.92;
        p=rotateZ(rotateX(rotateY(p,yaw),pitch),roll)+center;
        n=normalize(rotateZ(rotateX(rotateY(n,yaw),pitch),roll));
    } else if(type > 6.5 && type < 7.5) { // boat V25: ruta segura por agua abierta, silueta clara y escala reforzada
        float sway=sin(CameraTime.w*0.88)*0.22;
        float bob=sin(CameraTime.w*1.44)*0.16+cos(CameraTime.w*0.54)*0.08;
        float boatPhase=CameraTime.w*0.20;
        // V25: el recorrido se mantiene íntegramente sobre agua abierta y evita
        // la penetración del barco en las islas del archipiélago.
        float3 center=float3(
            0.0+sin(boatPhase)*13.0,
            1.72+bob,
            -5.0+cos(boatPhase*0.82)*18.0
        );
        float yaw=-0.35+sin(boatPhase*0.94)*0.58;
        float pitch=sin(CameraTime.w*0.82)*0.025;
        float roll=sin(CameraTime.w*1.33)*0.060+sway*0.06;
        p=rotateZ(rotateX(rotateY(p*3.15,yaw),pitch),roll)+center;
        n=normalize(rotateZ(rotateX(rotateY(n,yaw),pitch),roll));
    } else if(type > 8.5 && type < 9.5) { // fire V24: fogata más compacta y brillante
        float2 fireOffsets[2]={float2(34.4,5.4),float2(35.3,4.8)};
        int fi=(int)fmod(id,2.0);
        float2 fp=fireOffsets[fi];
        float3 center=float3(fp.x, terrainH(fp.x,fp.y)+0.88, fp.y);
        float flicker=0.92+abs(sin(CameraTime.w*6.6+id*1.7))*0.72;
        float yaw=sin(CameraTime.w*1.9+id*0.9)*0.22;
        float3 local=float3(
            i.pos.x*0.82+sin(CameraTime.w*4.2+id*2.1)*0.05,
            max(0.0, i.pos.y*1.02*flicker),
            i.pos.z*0.72+cos(CameraTime.w*3.5+id*1.5)*0.04
        );
        p=rotateY(local,yaw)+center;
        n=float3(0.0,1.0,0.0);
    } else if(type > 7.5 && type < 8.5) { // smoke V24: pluma multicapa con deriva visible en tiempo real
        float2 smokeOffsets[3]={float2(34.4,5.4),float2(35.1,4.9),float2(35.8,5.2)};
        int si=(int)fmod(id,3.0);
        float2 sp=smokeOffsets[si];
        float3 center=float3(sp.x, terrainH(sp.x,sp.y)+1.55, sp.y);
        float lane=(float)si-1.0;
        float rise=CameraTime.w*0.94 + id*0.75;
        float swirl=sin(rise*0.82+i.uv.y*5.1+i.pos.x*0.45)*0.66 + cos(rise*0.39+i.uv.y*2.4+i.pos.z*0.31)*0.42;
        float driftX=sin(rise*0.26+lane)*1.55 + lane*0.42;
        float driftZ=cos(rise*0.18+lane*0.6)*0.62;
        float3 local=float3(
            i.pos.x*0.98 + swirl*0.34 + driftX,
            i.pos.y*0.96 + frac(rise)*1.8,
            i.pos.z*0.98 + driftZ
        );
        p=local+center;
        n=float3(0.0,1.0,0.0);
    } else if(type > 3.5 && type < 4.5) { // trees, variación determinista + viento leve} else if(type > 3.5 && type < 4.5) { // trees, variación determinista + viento leve
        int isl=(int)fmod(id,4.0); float2 centers[4]={float2(-105,-25),float2(70,50),float2(10,-110),float2(145,-72)};
        float radii[4]={92,80,58,52}; float ang=hash11(id*3.17)*6.2831853; float rr=sqrt(hash11(id*7.91+1.3))*radii[isl]*0.62;
        float x=centers[isl].x+cos(ang)*rr, z=centers[isl].y+sin(ang)*rr, y=terrainH(x,z);
        float sc=0.72+hash11(id*11.2)*1.22;
        float sx=0.70+hash11(id*5.13+2.0)*0.62, sz=0.70+hash11(id*6.31+5.0)*0.62;
        float sy=0.82+hash11(id*8.73+7.0)*0.46;
        float yaw=hash11(id*17.41)*6.2831853;
        if(i.uv.y > 1.5) {
            float crown=hash11(id*19.13+2.1);
            float crownX=lerp(0.82,1.16,crown);
            float crownZ=lerp(1.13,0.86,crown);
            p.xz*=float2(crownX,crownZ);
            p.y*=lerp(0.94,1.08,hash11(id*23.7+0.9));
            p.x += sin(i.pos.y*1.21+id*0.83)*0.085*saturate(i.pos.y/5.7);
        }
        p=rotateY(p*float3(sc*sx,sc*sy,sc*sz),yaw); n=rotateY(normalize(n/float3(sx,sy,sz)),yaw);
        if(i.uv.y > 1.5) { float wind=sin(CameraTime.w*1.15+id*0.37+i.pos.y*0.9)*0.055; p.xz += float2(wind,wind*0.42)*saturate(i.pos.y/5.5); }
        p += float3(x,y,z);
    } else if(type > 4.5 && type < 5.5) { // rocks sobre costa y laderas
        int isl=(int)fmod(id,4.0); float2 centers[4]={float2(-105,-25),float2(70,50),float2(10,-110),float2(145,-72)};
        float radii[4]={92,80,58,52}; float ang=hash11(id*4.71+2.0)*6.2831853; float rr=sqrt(hash11(id*8.23+4.0))*radii[isl]*0.88;
        float x=centers[isl].x+cos(ang)*rr, z=centers[isl].y+sin(ang)*rr, y=terrainH(x,z);
        float sc=0.7+hash11(id*13.7)*2.5; p=rotateY(p*float3(sc,sc*0.65,sc),hash11(id)*6.28)+float3(x,y+0.15,z);
    } else if(type > 2.5 && type < 3.5) { // clouds, por encima de la cámara para evitar intersecciones
        float hx=hash11(id*2.31), hz=hash11(id*5.17+3.0);
        float driftX=sin(CameraTime.w*0.028+id*0.73)*7.0;
        float driftZ=cos(CameraTime.w*0.021+id*0.51)*5.0;
        float x=(hx-0.5)*430.0+driftX, z=(hz-0.5)*430.0+driftZ, y=106.0+hash11(id*9.7)*48.0;
        float sc=3.5+hash11(id*12.1)*6.0; p=p*float3(sc*1.55,sc*0.62,sc)+float3(x,y,z);
    } else if(type > 5.5 && type < 6.5) { // sky sphere: siempre centrada en la cámara
        p = CameraTime.xyz + p * 680.0;
        n = normalize(p - CameraTime.xyz);
    } else if(type > 0.5 && type < 1.5) { // water V14: ondas no armónicas + Gerstner suave
        // Frecuencias y direcciones deliberadamente no múltiplos entre sí para
        // evitar el patrón cuadriculado que se percibía a distancia en V13.
        float2 xz=p.xz;
        float a1=dot(xz,float2(0.031,0.013))+CameraTime.w*0.91;
        float a2=dot(xz,float2(-0.017,0.044))-CameraTime.w*1.13;
        float a3=dot(xz,float2(0.023,-0.029))+CameraTime.w*0.57;
        float a4=dot(xz,float2(0.061,0.019))-CameraTime.w*0.35;
        float a5=dot(xz,float2(-0.039,0.071))+CameraTime.w*1.43;
        float a0=dot(xz,float2(0.0067,-0.0041))+CameraTime.w*0.18;
        float w=sin(a1)*0.49+cos(a2)*0.34+sin(a3)*0.23+cos(a4)*0.095+sin(a5)*0.052+sin(a0)*0.17;
        p.y += w*0.46;
        p.x += (cos(a1)*0.10 + sin(a3)*0.055 + cos(a5)*0.022) * 0.40;
        p.z += (sin(a2)*0.082 + cos(a4)*0.044 - sin(a5)*0.018) * 0.40;
        float dx= cos(a1)*0.031*0.49 + sin(a2)*0.017*0.34 + cos(a3)*0.023*0.23 - sin(a4)*0.061*0.095 - cos(a5)*0.039*0.052 + cos(a0)*0.0067*0.17;
        float dz= cos(a1)*0.013*0.49 - sin(a2)*0.044*0.34 - cos(a3)*0.029*0.23 - sin(a4)*0.019*0.095 + cos(a5)*0.071*0.052 - cos(a0)*0.0041*0.17;
        n=normalize(float3(-dx,1.0,-dz));
    }
    o.world=p; o.normal=normalize(n); o.uv=i.uv; o.aux=(type>3.5 && type<4.5)?i.uv.y:id; o.instance=id;
    o.pos=mul(float4(p,1),ViewProj); return o;
}

float3 tonemap(float3 c){ return c/(1.0+c); }
float4 PSMain(VSOut i):SV_TARGET
{
    float type=SceneParams.x; int iters=(int)SceneParams.z; int texN=(int)SceneParams.w;
    float3 N=normalize(i.normal); float3 L=normalize(float3(-0.35,0.82,-0.44)); float ndl=saturate(dot(N,L));
    float3 V=normalize(CameraTime.xyz-i.world); float fres=pow(1.0-saturate(dot(N,V)),4.0);
    float2 uv=i.uv; float noise=0.0;
    [loop] for(int t=0;t<texN;t++){ float f=1.0+(float)t*0.63; noise += NoiseTex.Sample(LinearWrap,uv*f+float2(CameraTime.w*0.002*t,-CameraTime.w*0.0015*t)).r; }
    noise /= max(1,texN);
    float alu=noise;
    [loop] for(int k=0;k<iters;k++){ alu=frac(sin(alu*7.31+(float)k*0.17+i.world.x*0.002)*437.1); }
    float3 col; float alpha=1.0;
    if(type > 8.5 && type < 9.5) { // visible campfire V24
        float2 q=i.uv*2.0-1.0;
        float radial=saturate(1.0-dot(q*float2(0.78,1.18),q*float2(0.78,1.18)));
        float4 f0=NoiseTex.Sample(LinearWrap,i.uv*3.5+float2(0.11,0.23)+CameraTime.w*float2(0.036,-0.045));
        float4 f1=NoiseTex.Sample(LinearWrap,i.uv*6.0+float2(0.57,0.39)+CameraTime.w*float2(-0.053,0.035));
        float shape=saturate(radial*(0.64+f0.r*0.58+f1.g*0.42));
        shape*=saturate(1.0-i.uv.y*0.05);
        alpha=smoothstep(0.12,0.92,shape)*lerp(0.98,0.10,saturate(i.uv.y));
        if(alpha<0.03) discard;
        float hot=saturate(1.0-i.uv.y*0.85);
        float flame=saturate(shape*(0.78+0.22*sin(CameraTime.w*8.5+i.instance)));
        float3 ember=float3(1.55,0.95,0.30);
        float3 core=float3(2.10,1.82,0.92);
        float3 tip=float3(1.22,0.28,0.05);
        col=lerp(tip,ember,saturate(hot*1.1));
        col=lerp(col,core,saturate(hot*hot + flame*0.30));
        col += flame*0.32;
    } else if(type > 7.5 && type < 8.5) { // campfire smoke V24
        float2 q=i.uv*2.0-1.0;
        float radial=saturate(1.0-dot(q*float2(0.92,1.05),q*float2(0.92,1.05)));
        float4 s0=NoiseTex.Sample(LinearWrap,i.uv*2.2+float2(0.17,0.29)+CameraTime.w*float2(0.011,-0.009));
        float4 s1=NoiseTex.Sample(LinearWrap,i.uv*4.4+float2(0.61,0.13)+CameraTime.w*float2(-0.015,0.013));
        float curl=saturate(s0.r*0.46+s1.g*0.40+s0.b*0.14);
        float density=saturate(radial*(0.55+curl*0.55));
        density*=lerp(1.0,0.22,saturate(i.uv.y));
        alpha=smoothstep(0.07,0.88,density)*lerp(0.70,0.08,saturate(i.uv.y));
        if(alpha<0.012) discard;
        float ember=smoothstep(0.0,0.18,1.0-i.uv.y)*smoothstep(0.18,0.72,density);
        float3 smokeDark=float3(0.09,0.09,0.10);
        float3 smokeLight=float3(0.68,0.68,0.70);
        col=lerp(smokeDark,smokeLight,saturate(curl*0.55+i.uv.y*0.62));
        col=lerp(float3(1.15,0.38,0.10),col,saturate(i.uv.y*2.4));
        col += ember*float3(0.80,0.24,0.05);
    } else if(type > 6.5 && type < 7.5) { // boat V25
        float cabinMask=saturate((i.world.y-2.85)*1.2);
        float stripe=smoothstep(0.34,0.66,frac(i.uv.x*3.0));
        float plank=0.5+0.5*sin(i.world.x*0.38+i.world.z*0.21);
        float3 hull=lerp(float3(0.06,0.13,0.22),float3(0.17,0.36,0.62),plank*0.64);
        hull=lerp(hull,float3(0.86,0.92,0.96),stripe*0.26);
        float3 cabin=lerp(float3(0.82,0.84,0.88),float3(0.97,0.98,0.99),saturate(noise*0.8));
        float windowMask=saturate((1.0-abs(frac(i.uv.x*2.0)-0.5)*3.0))*cabinMask*saturate((i.world.y-2.15)*1.6);
        col=lerp(hull,cabin,cabinMask);
        col=lerp(col,float3(0.05,0.12,0.20),windowMask*0.88);
        float wetSpec=pow(saturate(dot(reflect(-L,N),V)),84.0);
        col*=0.34+ndl*0.90;
        col += wetSpec*float3(0.92,0.94,0.98)*(0.32+fres*0.48);
    } else if(type > 5.5 && type < 6.5) { // atmospheric sky + sun} else if(type > 5.5 && type < 6.5) { // atmospheric sky + sun
        float3 dir=normalize(i.world-CameraTime.xyz); float horizon=saturate(dir.y*0.78+0.34);
        float storm=saturate((SceneParams.z-8.0)/22.0);
        float3 zen=lerp(float3(0.06,0.20,0.43),float3(0.035,0.055,0.10),storm);
        float3 hor=lerp(float3(0.38,0.58,0.76),float3(0.20,0.24,0.30),storm);
        col=lerp(hor,zen,pow(horizon,0.65));
        float sun=pow(saturate(dot(dir,normalize(float3(-0.30,0.55,-0.78)))),380.0);
        col += sun*lerp(float3(3.8,2.2,0.8),float3(1.9,1.2,0.75),storm);
        alpha=1.0;
    } else if(type < 0.5) { // terrain V24: arena/pasto/roca con más contraste y lectura
        float h=i.world.y; float slope=1.0-saturate(N.y);
        float2 tuv=i.world.xz;
        float4 t0=NoiseTex.Sample(LinearWrap,tuv*0.0070);
        float4 t1=NoiseTex.Sample(LinearWrap,tuv*0.024+float2(0.17,0.31));
        float4 t2=NoiseTex.Sample(LinearWrap,tuv*0.105+float2(0.63,0.11));
        float2 nuv=tuv*0.105+float2(0.63,0.11); float ne=0.0032;
        float nhL=NoiseTex.Sample(LinearWrap,nuv-float2(ne,0)).g;
        float nhR=NoiseTex.Sample(LinearWrap,nuv+float2(ne,0)).g;
        float nhD=NoiseTex.Sample(LinearWrap,nuv-float2(0,ne)).g;
        float nhU=NoiseTex.Sample(LinearWrap,nuv+float2(0,ne)).g;
        float3 TN=normalize(N+float3((nhL-nhR)*0.40,0.0,(nhD-nhU)*0.40));
        float tndl=saturate(dot(TN,L));
        float macro=saturate(t0.g*0.58+t1.b*0.42);
        float grain=saturate(t1.r*0.40+t2.g*0.60);
        float mineral=saturate(t0.b*0.26+t1.g*0.34+t2.r*0.40);
        float scrub=saturate(t2.b*0.45+t1.a*0.35+t0.r*0.20);
        float3 grassA=float3(0.032,0.120,0.028), grassB=float3(0.18,0.36,0.09);
        float3 grass=lerp(grassA,grassB,saturate(macro*0.78+grain*0.46));
        grass=lerp(grass,grass*float3(1.12,0.98,0.82),scrub*0.18);
        float3 rockA=float3(0.14,0.14,0.14), rockB=float3(0.44,0.40,0.35);
        float3 rock=lerp(rockA,rockB,saturate(mineral*0.80+grain*0.26));
        float3 sandA=float3(0.31,0.23,0.13), sandB=float3(0.60,0.52,0.32);
        float3 sand=lerp(sandA,sandB,saturate(macro*0.52+grain*0.48));
        float coast=smoothstep(-2.8,5.9,h); col=lerp(sand,grass,coast);
        float rockMask=saturate(slope*2.75 + smoothstep(22.0,34.0,h)*0.40);
        col=lerp(col,rock,rockMask);
        float shoreDark=saturate(1.0-smoothstep(-0.2,2.2,h));
        col=lerp(col,col*0.82,shoreDark*0.28);
        float wet=saturate(1.0-abs(h)*0.30)*saturate(1.0-slope*1.8); col*=lerp(1.0,0.76,wet);
        float strata=0.5+0.5*sin(h*2.4+t1.b*5.0);
        col*=lerp(1.0,0.78+strata*0.25,rockMask);
        col*=0.32+tndl*0.88;
    } else if(type < 1.5) { // water V24: mejor profundidad, espuma y estela del barco
        float2 wxz=i.world.xz;
        float2 w0=float2(wxz.x*0.0123 + wxz.y*0.0067, -wxz.x*0.0051 + wxz.y*0.0137);
        float2 w1=float2(wxz.x*-0.0181 + wxz.y*0.0094, wxz.x*0.0077 + wxz.y*0.0209);
        float2 tA=float2(CameraTime.w*0.020,-CameraTime.w*0.012);
        float2 tB=float2(-CameraTime.w*0.014,CameraTime.w*0.017);
        float4 warp=NoiseTex.Sample(LinearWrap,w0*0.41+float2(0.17,0.53));
        float2 domain=(warp.rg*2.0-1.0)*0.18;
        float4 wa=NoiseTex.Sample(LinearWrap,w0+tA+domain);
        float4 wb=NoiseTex.Sample(LinearWrap,w1*1.61+tB-domain*0.73);
        float4 wc=NoiseTex.Sample(LinearWrap,(w0+w1)*2.87-tA*1.43+float2(0.63,0.19));
        float4 wd=NoiseTex.Sample(LinearWrap,(w0*1.37-w1*0.62)*5.23+tB*2.07+float2(0.31,0.79));
        float2 micro=(wa.rg*2.0-1.0)*0.40+(wb.gb*2.0-1.0)*0.32+(wc.br*2.0-1.0)*0.24+(wd.rg*2.0-1.0)*0.16;
        float3 WN=normalize(N+float3(micro.x*0.33,0.0,micro.y*0.33));
        float wfres=pow(1.0-saturate(dot(WN,V)),5.0);
        float sunSpec=pow(saturate(dot(reflect(-L,WN),V)),148.0);
        float sunGlint=pow(saturate(dot(reflect(-L,normalize(WN+float3(micro.x*0.095,0,micro.y*0.095))),V)),420.0);
        float3 R=reflect(-V,WN);
        float skyMix=saturate(R.y*0.72+0.30);
        float storm=saturate((SceneParams.z-8.0)/22.0);
        float3 skyZen=lerp(float3(0.06,0.20,0.43),float3(0.035,0.055,0.10),storm);
        float3 skyHor=lerp(float3(0.38,0.58,0.76),float3(0.20,0.24,0.30),storm);
        float3 reflectedSky=lerp(skyHor,skyZen,pow(skyMix,0.65));
        float ground=terrainH(i.world.x,i.world.z);
        float depth=saturate((-ground)/6.2);
        float coastWidth=0.25+0.060*(wa.r-0.5)+0.040*(wc.b-0.5);
        float shore=1.0-saturate(abs(ground)*max(0.17,coastWidth));
        float foamNoise=saturate(wa.b*0.28+wb.r*0.26+wc.g*0.24+wd.b*0.12+warp.a*0.10);
        float shoreWave=0.5+0.5*sin(ground*5.1-CameraTime.w*1.72+wa.g*1.9+wb.b*0.8);
        float foamRidge=smoothstep(0.18,0.84,abs(micro.x)+abs(micro.y));
        float shorelineBreak=smoothstep(0.31,0.76,foamNoise+0.16*sin(wxz.x*0.071+wxz.y*0.043));
        float foam=smoothstep(0.46,0.94,shore)*shorelineBreak*lerp(shoreWave,1.0,foamRidge*0.48);
        float3 shallow=float3(0.020,0.280,0.390), deep=float3(0.003,0.024,0.078);
        col=lerp(shallow,deep,depth);
        float broadTint=0.5+0.5*sin(dot(wxz,float2(0.0127,-0.0083))+CameraTime.w*0.11);
        col*=lerp(0.92,1.08,broadTint);
        float rippleBands=0.5+0.5*sin(dot(wxz,float2(0.094,0.063))-CameraTime.w*1.25+wa.g*3.0);
        col*=lerp(0.94,1.05,rippleBands*0.16);
        float caustic=pow(saturate(sin(dot(wxz,float2(0.73,0.39))+wa.g*3.7+CameraTime.w*0.66)
                       *sin(dot(wxz,float2(-0.31,0.84))+wb.r*3.9-CameraTime.w*0.57)),7.0);
        col+=float3(0.05,0.13,0.10)*caustic*(1.0-depth);
        // Estela del barco: usa la misma trayectoria determinista del VS del barco.
        float boatPhase=CameraTime.w*0.20;
        float2 boatPos=float2(0.0+sin(boatPhase)*13.0, -5.0+cos(boatPhase*0.82)*18.0);
        float2 boatVel=float2(cos(boatPhase)*13.0*0.20, -sin(boatPhase*0.82)*18.0*0.82*0.20);
        float2 dir=normalize(boatVel+float2(1e-4,1e-4));
        float2 rel=wxz-boatPos;
        float along=dot(rel,-dir);
        float across=abs(rel.x*dir.y-rel.y*dir.x);
        float wakeCore=smoothstep(0.0,18.0,along)*(1.0-smoothstep(18.0,76.0,along));
        float wakeWidth=saturate(1.0-across/(1.9+along*0.10));
        float wake=max(0.0,wakeCore*wakeWidth);
        float wakeRipples=0.5+0.5*sin(along*0.46-CameraTime.w*7.2);
        foam=max(foam,wake*(0.54+0.48*wakeRipples));
        col=lerp(col,reflectedSky,saturate(0.13+wfres*0.72));
        col += sunSpec*float3(2.2,1.9,1.2) + sunGlint*float3(4.1,3.5,2.2);
        col=lerp(col,float3(0.82,0.88,0.86),foam*0.78);
        float horizonBlend=smoothstep(260.0,410.0,length(i.world.xz));
        col=lerp(col,reflectedSky,horizonBlend*0.70);
    } else if(type < 2.5) { // jets V24
        float canopy=step(1.5,i.uv.y);
        float exhaust=step(1.05,i.uv.y)*(1.0-step(1.5,i.uv.y));
        float stripe=smoothstep(0.28,0.42,frac(i.uv.x*2.0))*(1.0-smoothstep(0.58,0.72,frac(i.uv.x*2.0)));
        float panel=0.5+0.5*sin(i.world.x*3.7+i.world.z*2.1);
        float3 metal=lerp(float3(0.28,0.33,0.39),float3(0.72,0.31,0.060),stripe*0.76);
        metal*=lerp(0.92,1.10,panel*0.35+noise*0.65);
        float noseGlow=smoothstep(0.78,1.0,i.uv.x);
        float wingFlash=saturate(1.0-abs(i.uv.y-0.5)*2.0);
        metal=lerp(metal,float3(0.82,0.84,0.87),noseGlow*0.22+wingFlash*0.08);
        col=lerp(metal,float3(0.010,0.055,0.095),canopy); col*=0.32+ndl*0.82;
        float exhaustCore=pow(saturate(1.0-abs(i.uv.x-0.5)*2.0),4.0);
        float3 exhaustCol=float3(0.028,0.032,0.043)+float3(0.95,0.24,0.025)*exhaustCore*0.72;
        col=lerp(col,exhaustCol,exhaust);
        float spec=pow(saturate(dot(reflect(-L,N),V)),lerp(52.0,230.0,canopy));
        col+=spec*lerp(float3(0.54,0.58,0.64),float3(1.5,1.78,2.0),canopy)*(1.0-exhaust);
        col += fres*lerp(0.11,0.34,canopy)*(1.0-exhaust*0.7);
    } else if(type < 3.5) { // clouds V14: soft cards con borde radial y ruido multicapa
        float2 cq=i.uv*2.0-1.0;
        float radial=saturate(1.0-dot(cq*float2(0.92,1.08),cq*float2(0.92,1.08)));
        float4 cn0=NoiseTex.Sample(LinearWrap,i.uv*1.7+i.world.xz*0.0018);
        float4 cn1=NoiseTex.Sample(LinearWrap,i.uv*4.1+float2(0.23,0.61)+CameraTime.w*float2(0.0007,-0.0004));
        float billow=saturate(cn0.r*0.58+cn1.g*0.42);
        float density=smoothstep(0.02,0.78,radial*(0.64+billow*0.68));
        alpha=density*0.56; if(alpha<0.018) discard;
        float storm=saturate((SceneParams.z-8.0)/22.0);
        float silver=pow(saturate(dot(normalize(float3(-0.35,0.82,-0.44)),V)),5.0);
        float3 shadow=lerp(float3(0.50,0.56,0.64),float3(0.29,0.32,0.37),storm);
        float3 light=lerp(float3(0.94,0.955,0.97),float3(0.70,0.72,0.75),storm);
        col=lerp(shadow,light,saturate(billow*0.50+radial*0.30+ndl*0.24));
        col += silver*float3(0.10,0.12,0.14)*(1.0-storm*0.4);
    } else if(type < 4.5) { // trees V24: corteza y follaje con más volumen perceptual
        if(i.aux < 1.5) {
            float2 buv=float2(i.uv.x*3.2+i.world.y*0.038,i.world.y*0.16);
            float4 b0=NoiseTex.Sample(LinearWrap,buv);
            float4 b1=NoiseTex.Sample(LinearWrap,buv*2.7+float2(0.21,0.61));
            float bark=saturate(b0.r*0.58+b1.b*0.42);
            float grooves=smoothstep(0.35,0.75,abs(sin((i.world.y+b0.g)*8.5)));
            float moss=saturate((1.0-N.y)*0.18 + b1.g*0.28);
            col=lerp(float3(0.065,0.030,0.012),float3(0.28,0.14,0.05),bark);
            col=lerp(col,col*float3(0.72,1.12,0.72),moss*0.18);
            col*=lerp(0.70,1.10,grooves)*(0.42+ndl*0.66);
        } else {
            float2 luv=float2(frac(i.uv.x),frac(i.uv.y));
            float2 q=luv*2.0-1.0;
            float4 leafTex=NoiseTex.Sample(LinearWrap,luv*3.25+i.world.xz*0.015);
            float angle=atan2(q.y,q.x);
            float r=length(q*float2(0.82,1.12));
            float lobes=0.105*sin(angle*5.0+leafTex.r*1.6)+0.038*sin(angle*9.0+leafTex.g*2.1);
            float leafShape=0.88-r+lobes+(leafTex.b-0.5)*0.095;
            float aa=max(fwidth(leafShape)*1.25,0.012);
            float coverage=smoothstep(-aa,aa,leafShape);
            float breakup=0.52*leafTex.r+0.30*leafTex.g+0.18*leafTex.b;
            float veins=0.5+0.5*sin(q.x*8.7+q.y*5.3+leafTex.a*4.1);
            float interior=smoothstep(0.26,0.49,breakup*0.82+veins*0.18);
            float solidCore=smoothstep(0.18,0.62,coverage);
            float cutout=max(interior,solidCore*0.62);
            float dither=frac(sin(dot(floor(i.pos.xy),float2(12.9898,78.233)))*43758.5453);
            clip(min(coverage,cutout)-dither*0.58-0.20);
            float variation=saturate(leafTex.r*0.62+leafTex.g*0.38);
            float3 dark=float3(0.018,0.090,0.020), mid=float3(0.085,0.26,0.060), light=float3(0.28,0.48,0.12);
            col=lerp(dark,mid,saturate(variation*0.92+leafTex.g*0.18));
            float species=hash11(i.instance*2.71+0.4);
            float species2=hash11(i.instance*5.19+1.7);
            col*=lerp(float3(0.72,0.92,1.00),float3(1.24,1.04,0.62),species);
            col=lerp(col,col*float3(0.82,1.10,0.86),species2*0.25);
            float topLight=saturate(N.y*0.5+0.5);
            col=lerp(col,light,saturate((ndl-0.35)*1.6)*0.52 + topLight*0.10);
            col*=0.56+ndl*0.56;
            col += fres*float3(0.032,0.056,0.022);
            float backlight=pow(saturate(dot(-L,V)),3.0);
            col+=float3(0.14,0.22,0.040)*backlight*leafTex.g;
        }
    } else { // rocks V24
        float2 ruv=i.world.xz*0.11+float2(i.world.y*0.07, i.world.y*0.05);
        float4 r0=NoiseTex.Sample(LinearWrap,ruv);
        float4 r1=NoiseTex.Sample(LinearWrap,ruv*2.2+float2(0.31,0.17));
        float rough=saturate(r0.r*0.58+r1.g*0.42);
        float pits=smoothstep(0.30,0.78,abs(sin(i.world.y*6.0+r1.b*4.0)));
        float moss=saturate((1.0-saturate(N.y))*0.16 + r0.g*0.24);
        float lichen=saturate(r1.r*0.45+r0.b*0.30);
        float3 base=lerp(float3(0.18,0.19,0.20),float3(0.47,0.45,0.42),rough);
        base=lerp(base,base*float3(0.78,0.92,0.76),moss*0.24);
        base=lerp(base,float3(0.62,0.62,0.58),lichen*0.12);
        col=base*(0.34+ndl*0.78);
        col*=lerp(0.86,1.12,pits);
        float spec=pow(saturate(dot(reflect(-L,N),V)),24.0);
        col += spec*float3(0.14,0.15,0.16)*0.15;
    }
    col *= 0.94 + (alu-0.5)*0.06;
    float dist=length(CameraTime.xyz-i.world);
    float distanceFog=saturate((dist-175.0)/380.0);
    float heightFog=saturate((18.0-i.world.y)/96.0)*saturate((dist-115.0)/390.0);
    float fog=saturate(distanceFog*0.60+heightFog*0.18);
    float3 sky=float3(0.16,0.34,0.55);
    float fogStrength=(type > 1.5 && type < 2.5) ? 0.36 : 0.52;
    col=lerp(col,sky,fog*fogStrength);
    return float4(pow(tonemap(max(col,0)),1.0/2.2),alpha);
}
'''


class _Mesh:
    def __init__(self, vb=None, ib=None, index_count=0): self.vb=vb; self.ib=ib; self.index_count=index_count


class D3D11Renderer:
    """Renderer D3D11 dedicado al benchmark V24 con pulido visual de barco/humo/agua/árboles/rocas y timing auditado."""

    def __init__(self, width: int, height: int, visible: bool = True):
        self.width=max(640,int(width)); self.height=max(360,int(height)); self.visible=bool(visible)
        self.user32=None; self.hinstance=None; self.hwnd=None; self.class_name=None; self._wndproc=None
        self.device=ctypes.c_void_p(); self.context=ctypes.c_void_p(); self.swap=ctypes.c_void_p(); self.rtv=ctypes.c_void_p(); self.depth_tex=ctypes.c_void_p(); self.dsv=ctypes.c_void_p()
        self.vs=ctypes.c_void_p(); self.ps=ctypes.c_void_p(); self.layout=ctypes.c_void_p(); self.cbuffer=ctypes.c_void_p(); self.sampler=ctypes.c_void_p(); self.noise_tex=ctypes.c_void_p(); self.noise_srv=ctypes.c_void_p(); self.blend=ctypes.c_void_p(); self.raster=ctypes.c_void_p(); self.depth_readonly=ctypes.c_void_p()
        self.meshes={}; self.terrain_meshes={}
        self.gpu_timer=None; self.gpu_timing_available=False; self.gpu_timing_reason=None
        self.cancelled=False; self.feature_level=None; self.adapter_name='Direct3D 11 hardware adapter'; self.vram_mb=None
        self.startup_stage='created'
        self.startup_checks=[]
        self._shown=False
        try:
            self._run_startup_stage('window', self._init_window)
            self._run_startup_stage('device_swapchain', self._init_device)
            self._run_startup_stage('clear_present_smoke', self._smoke_clear_present)
            self._init_gpu_timing_optional()
            self._run_startup_stage('shader_pipeline', self._init_pipeline)
            self._run_startup_stage('scene_resources', self._init_resources)
            # Renderiza un frame real completo ANTES de mostrar la ventana. De esta
            # forma una inicialización fallida no deja al usuario mirando una ventana negra.
            self._run_startup_stage('first_scene_frame', self._validate_first_scene_frame)
            self.startup_stage='ready'
        except Exception:
            try:
                self.close()
            except Exception:
                pass
            raise

    def _run_startup_stage(self, name, fn):
        self.startup_stage=str(name)
        started=time.perf_counter()
        try:
            fn()
        except Exception as exc:
            raise RuntimeError(f'DirectX startup [{name}] falló: {type(exc).__name__}: {exc}') from exc
        self.startup_checks.append({'stage': str(name), 'status': 'OK', 'duration_ms': round((time.perf_counter()-started)*1000.0, 3)})

    def _init_window(self):
        self.user32=ctypes.WinDLL('user32.dll'); kernel32=ctypes.WinDLL('kernel32.dll')
        self.user32.DefWindowProcW.argtypes=[HWND_T,UINT,wintypes.WPARAM,wintypes.LPARAM]; self.user32.DefWindowProcW.restype=LRESULT
        self.user32.RegisterClassW.argtypes=[ctypes.POINTER(WNDCLASSW)]; self.user32.RegisterClassW.restype=wintypes.ATOM
        self.user32.CreateWindowExW.argtypes=[wintypes.DWORD,wintypes.LPCWSTR,wintypes.LPCWSTR,wintypes.DWORD,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,HWND_T,HMENU_T,HINSTANCE_T,LPVOID]; self.user32.CreateWindowExW.restype=HWND_T
        self.user32.ShowWindow.argtypes=[HWND_T,ctypes.c_int]; self.user32.UpdateWindow.argtypes=[HWND_T]
        self.user32.DestroyWindow.argtypes=[HWND_T]; self.user32.UnregisterClassW.argtypes=[wintypes.LPCWSTR,HINSTANCE_T]
        self.user32.PeekMessageW.argtypes=[ctypes.POINTER(MSG),HWND_T,UINT,UINT,UINT]; self.user32.PeekMessageW.restype=BOOL
        self.user32.TranslateMessage.argtypes=[ctypes.POINTER(MSG)]; self.user32.DispatchMessageW.argtypes=[ctypes.POINTER(MSG)]
        self.user32.SetWindowTextW.argtypes=[HWND_T,wintypes.LPCWSTR]
        self.user32.SetCursor.argtypes=[HCURSOR_T]; self.user32.SetCursor.restype=HCURSOR_T
        self.user32.GetSystemMetrics.argtypes=[ctypes.c_int]; self.user32.GetSystemMetrics.restype=ctypes.c_int
        self.user32.AdjustWindowRectEx.argtypes=[ctypes.POINTER(RECT),wintypes.DWORD,BOOL,wintypes.DWORD]; self.user32.AdjustWindowRectEx.restype=BOOL
        kernel32.GetModuleHandleW.argtypes=[wintypes.LPCWSTR]; kernel32.GetModuleHandleW.restype=HINSTANCE_T
        self.hinstance=kernel32.GetModuleHandleW(None)
        cancelled_ref=self
        @WNDPROC
        def wndproc(hwnd,msg,wparam,lparam):
            # V190: la propia ventana DirectX es la autoridad del cursor.
            # WM_SETCURSOR se procesa fuera de la región cronometrada (pump),
            # por lo que ocultarlo no altera FPS ni el workload V16. Evita que
            # Windows conserve el cursor 'watch' heredado de la navegación.
            if msg == WM_SETCURSOR:
                # Sólo el área cliente 3D queda sin cursor. En la barra de título
                # Windows conserva el puntero normal para cerrar/minimizar.
                hit_test = int(lparam) & 0xFFFF
                if hit_test == HTCLIENT:
                    try:
                        self.user32.SetCursor(None)
                    except Exception:
                        pass
                    return 1
            if msg in (WM_CLOSE,WM_DESTROY) or (msg == WM_KEYDOWN and int(wparam) == VK_ESCAPE):
                cancelled_ref.cancelled=True
                return 0
            return self.user32.DefWindowProcW(hwnd,msg,wparam,lparam)
        self._wndproc=wndproc
        self.class_name=f'CorePulseDX11Bench_{os.getpid()}_{threading.get_ident()}'
        wc=WNDCLASSW(); wc.lpfnWndProc=wndproc; wc.hInstance=self.hinstance; wc.lpszClassName=self.class_name
        if not self.user32.RegisterClassW(ctypes.byref(wc)):
            raise RuntimeError('No se pudo registrar la ventana DirectX del benchmark')
        sw,sh=max(640,self.user32.GetSystemMetrics(0)),max(360,self.user32.GetSystemMetrics(1))
        self.width=min(self.width,sw); self.height=min(self.height,sh)
        fullscreen = self.width >= sw and self.height >= sh
        style = WS_POPUP if fullscreen else (WS_CAPTION|WS_SYSMENU|WS_MINIMIZEBOX)
        if fullscreen:
            ow,oh=self.width,self.height; x=y=0
        else:
            rect=RECT(0,0,self.width,self.height); self.user32.AdjustWindowRectEx(ctypes.byref(rect),style,False,0)
            ow,oh=rect.right-rect.left,rect.bottom-rect.top
            x=max(0,(sw-ow)//2); y=max(0,(sh-oh)//2)
        # Siempre se crea oculta. Sólo se muestra después de que un frame 3D real
        # haya sido renderizado y Present haya terminado correctamente.
        self.hwnd=self.user32.CreateWindowExW(0,self.class_name,f'CorePulse Benchmark {GPU_BENCHMARK_LABEL} — DirectX 11',style,x,y,ow,oh,None,None,self.hinstance,None)
        if not self.hwnd: raise RuntimeError('No se pudo crear la ventana DirectX 11')

    def _init_device(self):
        d3d11=ctypes.WinDLL('d3d11.dll')
        create=d3d11.D3D11CreateDeviceAndSwapChain
        create.argtypes=[ctypes.c_void_p,UINT,ctypes.c_void_p,UINT,ctypes.POINTER(UINT),UINT,UINT,ctypes.POINTER(DXGI_SWAP_CHAIN_DESC),ctypes.POINTER(ctypes.c_void_p),ctypes.POINTER(ctypes.c_void_p),ctypes.POINTER(UINT),ctypes.POINTER(ctypes.c_void_p)]
        create.restype=HRESULT
        desc=DXGI_SWAP_CHAIN_DESC(); desc.BufferDesc.Width=self.width; desc.BufferDesc.Height=self.height; desc.BufferDesc.RefreshRate=DXGI_RATIONAL(0,1); desc.BufferDesc.Format=DXGI_FORMAT_R8G8B8A8_UNORM; desc.SampleDesc=DXGI_SAMPLE_DESC(1,0); desc.BufferUsage=DXGI_USAGE_RENDER_TARGET_OUTPUT; desc.BufferCount=2; desc.OutputWindow=self.hwnd; desc.Windowed=1; desc.SwapEffect=DXGI_SWAP_EFFECT_DISCARD
        levels=(UINT*3)(D3D_FEATURE_LEVEL_11_0,D3D_FEATURE_LEVEL_10_1,D3D_FEATURE_LEVEL_10_0); fl=UINT()
        hr=create(None,D3D_DRIVER_TYPE_HARDWARE,None,D3D11_CREATE_DEVICE_BGRA_SUPPORT,levels,3,D3D11_SDK_VERSION,ctypes.byref(desc),ctypes.byref(self.swap),ctypes.byref(self.device),ctypes.byref(fl),ctypes.byref(self.context))
        if not _hr_ok(hr): raise RuntimeError(f'D3D11CreateDeviceAndSwapChain falló (0x{int(hr)&0xffffffff:08X})')
        self.feature_level=int(fl.value)
        # Backbuffer -> RTV.
        back=ctypes.c_void_p(); hr=_com_method(self.swap,9,HRESULT,UINT,ctypes.POINTER(GUID),ctypes.POINTER(ctypes.c_void_p))(self.swap,0,ctypes.byref(IID_ID3D11Texture2D),ctypes.byref(back))
        if not _hr_ok(hr): raise RuntimeError('IDXGISwapChain::GetBuffer falló')
        try:
            hr=_com_method(self.device,9,HRESULT,ctypes.c_void_p,ctypes.c_void_p,ctypes.POINTER(ctypes.c_void_p))(self.device,back,None,ctypes.byref(self.rtv))
            if not _hr_ok(hr): raise RuntimeError('CreateRenderTargetView falló')
        finally: _release(back)
        # Depth buffer.
        td=D3D11_TEXTURE2D_DESC(self.width,self.height,1,1,DXGI_FORMAT_D24_UNORM_S8_UINT,DXGI_SAMPLE_DESC(1,0),D3D11_USAGE_DEFAULT,D3D11_BIND_DEPTH_STENCIL,0,0)
        hr=_com_method(self.device,5,HRESULT,ctypes.POINTER(D3D11_TEXTURE2D_DESC),ctypes.c_void_p,ctypes.POINTER(ctypes.c_void_p))(self.device,ctypes.byref(td),None,ctypes.byref(self.depth_tex))
        if not _hr_ok(hr): raise RuntimeError('CreateTexture2D(depth) falló')
        hr=_com_method(self.device,10,HRESULT,ctypes.c_void_p,ctypes.c_void_p,ctypes.POINTER(ctypes.c_void_p))(self.device,self.depth_tex,None,ctypes.byref(self.dsv))
        if not _hr_ok(hr): raise RuntimeError('CreateDepthStencilView falló')
        # Adaptador real que creó el device.
        try:
            dxgi_dev=_query_interface(self.device,IID_IDXGIDevice)
            if dxgi_dev:
                adapter=ctypes.c_void_p(); hr=_com_method(dxgi_dev,7,HRESULT,ctypes.POINTER(ctypes.c_void_p))(dxgi_dev,ctypes.byref(adapter))
                if _hr_ok(hr) and adapter.value:
                    ad=DXGI_ADAPTER_DESC(); hr2=_com_method(adapter,8,HRESULT,ctypes.POINTER(DXGI_ADAPTER_DESC))(adapter,ctypes.byref(ad))
                    if _hr_ok(hr2):
                        self.adapter_name=str(ad.Description).strip() or self.adapter_name; self.vram_mb=int(ad.DedicatedVideoMemory/(1024*1024))
                    _release(adapter)
                _release(dxgi_dev)
        except Exception:
            pass

    def _init_gpu_timing_optional(self):
        self.startup_stage='gpu_timestamp_queries'
        started=time.perf_counter()
        try:
            self.gpu_timer=_GpuFrameTimer(self.device,self.context,slot_count=192)
            self.gpu_timing_available=True
            self.gpu_timing_reason=None
            status='OK'
        except Exception as exc:
            self.gpu_timer=None; self.gpu_timing_available=False
            self.gpu_timing_reason=f'{type(exc).__name__}: {exc}'
            status='N/A'
        self.startup_checks.append({'stage':'gpu_timestamp_queries','status':status,'duration_ms':round((time.perf_counter()-started)*1000.0,3),'reason':self.gpu_timing_reason})

    def begin_scene_gpu_timing(self):
        if self.gpu_timer is None:
            return
        self.gpu_timer.drain(timeout_s=2.0)
        self.gpu_timer.reset_scene()

    def finish_scene_gpu_timing(self, timeout_s: float = 4.0):
        if self.gpu_timer is None:
            return [], {'dropped':0,'disjoint':0}
        vals=self.gpu_timer.drain(timeout_s=timeout_s)
        return vals, {'dropped':self.gpu_timer.dropped_frames,'disjoint':self.gpu_timer.disjoint_frames}

    def poll_gpu_timing(self):
        """Recoge queries listas fuera del frametime medido."""
        if self.gpu_timer is None:
            return []
        return self.gpu_timer.collect_ready(nonblocking=True)

    def prepare_timed_frame(self):
        """Trabajo de ventana/auditoría deliberadamente fuera del cronómetro."""
        self.pump()
        self.poll_gpu_timing()
        self._show_if_ready()

    def _show_if_ready(self):
        if self.visible and not self._shown and self.hwnd:
            self.user32.ShowWindow(self.hwnd,SW_SHOW)
            self.user32.UpdateWindow(self.hwnd)
            try:
                self.user32.SetCursor(None)
            except Exception:
                pass
            self._shown=True

    def _present(self):
        hr=_com_method(self.swap,8,HRESULT,UINT,UINT)(self.swap,0,0)
        if not _hr_ok(hr):
            raise RuntimeError(f'IDXGISwapChain::Present falló 0x{int(hr)&0xffffffff:08X}')

    def _smoke_clear_present(self):
        # Smoke test mínimo: valida DeviceContext + RTV + SwapChain sin depender
        # todavía de shaders ni geometría. Se ejecuta con la ventana oculta.
        clear=(FLOAT*4)(0.035,0.07,0.12,1.0)
        _com_method(self.context,CTX_CLEAR_RENDER_TARGET_VIEW,None,ctypes.c_void_p,ctypes.POINTER(FLOAT))(self.context,self.rtv,clear)
        self._present()

    def _validate_first_scene_frame(self):
        level=profile_levels('standard')[0]
        # Un frame completo real: input assembler, shaders, constant buffer,
        # texturas, depth, instancing y Present.
        self.render_frame(level,0.0,0,show_after_present=False)
        self._show_if_ready()

    def _create_buffer(self, raw: bytes, bind_flags: int, usage: int=D3D11_USAGE_IMMUTABLE):
        out=ctypes.c_void_p(); desc=D3D11_BUFFER_DESC(len(raw),usage,bind_flags,0,0,0)
        buf=ctypes.create_string_buffer(raw); sub=D3D11_SUBRESOURCE_DATA(ctypes.cast(buf,LPVOID),0,0)
        hr=_com_method(self.device,3,HRESULT,ctypes.POINTER(D3D11_BUFFER_DESC),ctypes.POINTER(D3D11_SUBRESOURCE_DATA),ctypes.POINTER(ctypes.c_void_p))(self.device,ctypes.byref(desc),ctypes.byref(sub),ctypes.byref(out))
        if not _hr_ok(hr): raise RuntimeError(f'CreateBuffer falló: 0x{int(hr)&0xffffffff:08X}')
        return out

    def _make_mesh(self, vertices, indices):
        vb_raw=b''.join(struct.pack('<8f',*map(float,v)) for v in vertices); ib_raw=struct.pack('<%dI'%len(indices),*indices)
        return _Mesh(self._create_buffer(vb_raw,D3D11_BIND_VERTEX_BUFFER),self._create_buffer(ib_raw,D3D11_BIND_INDEX_BUFFER),len(indices))

    def _init_pipeline(self):
        vs_blob,vs_bytes=_compile_shader(HLSL,b'VSMain',b'vs_5_0' if self.feature_level>=D3D_FEATURE_LEVEL_11_0 else b'vs_4_0')
        ps_blob,ps_bytes=_compile_shader(HLSL,b'PSMain',b'ps_5_0' if self.feature_level>=D3D_FEATURE_LEVEL_11_0 else b'ps_4_0')
        try:
            vs_buf=ctypes.create_string_buffer(vs_bytes); hr=_com_method(self.device,12,HRESULT,LPVOID,SIZE_T,ctypes.c_void_p,ctypes.POINTER(ctypes.c_void_p))(self.device,ctypes.cast(vs_buf,LPVOID),len(vs_bytes),None,ctypes.byref(self.vs));
            if not _hr_ok(hr): raise RuntimeError('CreateVertexShader falló')
            ps_buf=ctypes.create_string_buffer(ps_bytes); hr=_com_method(self.device,15,HRESULT,LPVOID,SIZE_T,ctypes.c_void_p,ctypes.POINTER(ctypes.c_void_p))(self.device,ctypes.cast(ps_buf,LPVOID),len(ps_bytes),None,ctypes.byref(self.ps));
            if not _hr_ok(hr): raise RuntimeError('CreatePixelShader falló')
            elems=(D3D11_INPUT_ELEMENT_DESC*3)(
                D3D11_INPUT_ELEMENT_DESC(b'POSITION',0,DXGI_FORMAT_R32G32B32_FLOAT,0,0,D3D11_INPUT_PER_VERTEX_DATA,0),
                D3D11_INPUT_ELEMENT_DESC(b'NORMAL',0,DXGI_FORMAT_R32G32B32_FLOAT,0,12,D3D11_INPUT_PER_VERTEX_DATA,0),
                D3D11_INPUT_ELEMENT_DESC(b'TEXCOORD',0,DXGI_FORMAT_R32G32_FLOAT,0,24,D3D11_INPUT_PER_VERTEX_DATA,0),
            )
            hr=_com_method(self.device,11,HRESULT,ctypes.POINTER(D3D11_INPUT_ELEMENT_DESC),UINT,LPVOID,SIZE_T,ctypes.POINTER(ctypes.c_void_p))(self.device,elems,3,ctypes.cast(vs_buf,LPVOID),len(vs_bytes),ctypes.byref(self.layout))
            if not _hr_ok(hr): raise RuntimeError('CreateInputLayout falló')
        finally:
            _release(vs_blob); _release(ps_blob)
        # Constant buffer 112 B -> 16-byte aligned.
        cb_desc=D3D11_BUFFER_DESC(112,D3D11_USAGE_DEFAULT,D3D11_BIND_CONSTANT_BUFFER,0,0,0); hr=_com_method(self.device,3,HRESULT,ctypes.POINTER(D3D11_BUFFER_DESC),ctypes.c_void_p,ctypes.POINTER(ctypes.c_void_p))(self.device,ctypes.byref(cb_desc),None,ctypes.byref(self.cbuffer))
        if not _hr_ok(hr): raise RuntimeError('CreateBuffer(constant) falló')
        # Sampler.
        sd=D3D11_SAMPLER_DESC(); sd.Filter=D3D11_FILTER_MIN_MAG_MIP_LINEAR; sd.AddressU=sd.AddressV=sd.AddressW=D3D11_TEXTURE_ADDRESS_WRAP; sd.ComparisonFunc=D3D11_COMPARISON_NEVER; sd.MinLOD=0.0; sd.MaxLOD=1000.0
        hr=_com_method(self.device,23,HRESULT,ctypes.POINTER(D3D11_SAMPLER_DESC),ctypes.POINTER(ctypes.c_void_p))(self.device,ctypes.byref(sd),ctypes.byref(self.sampler));
        if not _hr_ok(hr): raise RuntimeError('CreateSamplerState falló')
        # Alpha blend for clouds.
        bd=D3D11_BLEND_DESC(); rt=bd.RenderTarget[0]; rt.BlendEnable=1; rt.SrcBlend=D3D11_BLEND_SRC_ALPHA; rt.DestBlend=D3D11_BLEND_INV_SRC_ALPHA; rt.BlendOp=D3D11_BLEND_OP_ADD; rt.SrcBlendAlpha=D3D11_BLEND_ONE; rt.DestBlendAlpha=D3D11_BLEND_ZERO; rt.BlendOpAlpha=D3D11_BLEND_OP_ADD; rt.RenderTargetWriteMask=D3D11_COLOR_WRITE_ENABLE_ALL
        hr=_com_method(self.device,20,HRESULT,ctypes.POINTER(D3D11_BLEND_DESC),ctypes.POINTER(ctypes.c_void_p))(self.device,ctypes.byref(bd),ctypes.byref(self.blend));
        if not _hr_ok(hr): self.blend=ctypes.c_void_p()
        # V14: transparencias (nubes) y sky prueban profundidad, pero NO escriben
        # en el depth buffer. Evita halos/planos que oculten puffs posteriores y
        # permite dibujar el cielo antes de la capa transparente correctamente.
        keep=D3D11_DEPTH_STENCILOP_DESC(D3D11_STENCIL_OP_KEEP,D3D11_STENCIL_OP_KEEP,D3D11_STENCIL_OP_KEEP,D3D11_COMPARISON_NEVER)
        dsd=D3D11_DEPTH_STENCIL_DESC(1,D3D11_DEPTH_WRITE_MASK_ZERO,D3D11_COMPARISON_LESS,0,0xff,0xff,(ctypes.c_ubyte*2)(0,0),keep,keep)
        hr=_com_method(self.device,21,HRESULT,ctypes.POINTER(D3D11_DEPTH_STENCIL_DESC),ctypes.POINTER(ctypes.c_void_p))(self.device,ctypes.byref(dsd),ctypes.byref(self.depth_readonly))
        if not _hr_ok(hr): self.depth_readonly=ctypes.c_void_p()
        rd=D3D11_RASTERIZER_DESC(D3D11_FILL_SOLID,D3D11_CULL_NONE,0,0,0.0,0.0,1,0,0,0); hr=_com_method(self.device,22,HRESULT,ctypes.POINTER(D3D11_RASTERIZER_DESC),ctypes.POINTER(ctypes.c_void_p))(self.device,ctypes.byref(rd),ctypes.byref(self.raster));
        if not _hr_ok(hr): self.raster=ctypes.c_void_p()
        self._create_noise_texture()

    def _create_noise_texture(self):
        """Textura procedural determinista multicanal para materiales V13.

        Los tres canales no son el mismo ruido: combinan ondas amplias con una
        componente fina determinista. Esto permite que terreno, corteza, follaje
        y agua tengan detalle sin depender de assets externos ni datos aleatorios
        diferentes entre ejecuciones.
        """
        w=h=512; data=bytearray(w*h*4); seed=0x2468ACE1
        for y in range(h):
            fy=y/float(h)
            for x in range(w):
                fx=x/float(w)
                seed=(1664525*seed+1013904223)&0xffffffff
                rnd=((seed>>8)&0xffff)/65535.0
                a=0.50+0.24*math.sin(fx*math.tau*3.0+fy*1.7)+0.18*math.cos(fy*math.tau*5.0-fx*2.1)
                b=0.50+0.22*math.sin((fx+fy)*math.tau*7.0)+0.15*math.cos((fx-fy)*math.tau*11.0)
                c=0.50+0.20*math.sin(fx*math.tau*17.0)*math.cos(fy*math.tau*13.0)
                r=int(max(0,min(255,(a*0.72+rnd*0.28)*255.0)))
                g=int(max(0,min(255,(b*0.78+rnd*0.22)*255.0)))
                bl=int(max(0,min(255,(c*0.68+rnd*0.32)*255.0)))
                i=(y*w+x)*4; data[i:i+4]=bytes((r,g,bl,255))
        raw=ctypes.create_string_buffer(bytes(data)); td=D3D11_TEXTURE2D_DESC(w,h,1,1,DXGI_FORMAT_R8G8B8A8_UNORM,DXGI_SAMPLE_DESC(1,0),D3D11_USAGE_IMMUTABLE,D3D11_BIND_SHADER_RESOURCE,0,0); sub=D3D11_SUBRESOURCE_DATA(ctypes.cast(raw,LPVOID),w*4,0)
        hr=_com_method(self.device,5,HRESULT,ctypes.POINTER(D3D11_TEXTURE2D_DESC),ctypes.POINTER(D3D11_SUBRESOURCE_DATA),ctypes.POINTER(ctypes.c_void_p))(self.device,ctypes.byref(td),ctypes.byref(sub),ctypes.byref(self.noise_tex));
        if not _hr_ok(hr): raise RuntimeError('CreateTexture2D(surface procedural) falló')
        hr=_com_method(self.device,7,HRESULT,ctypes.c_void_p,ctypes.c_void_p,ctypes.POINTER(ctypes.c_void_p))(self.device,self.noise_tex,None,ctypes.byref(self.noise_srv));
        if not _hr_ok(hr): raise RuntimeError('CreateShaderResourceView falló')

    def _init_resources(self):
        self.meshes['water']=self._make_mesh(*build_water())
        self.meshes['jet']=self._make_mesh(*build_jet())
        self.meshes['tree']=self._make_mesh(*build_tree())
        self.meshes['rock']=self._make_mesh(*build_rock())
        self.meshes['cloud']=self._make_mesh(*build_cloud())
        self.meshes['smoke']=self._make_mesh(*build_smoke_plume())
        self.meshes['fire']=self._make_mesh(*build_fire_billboard())
        self.meshes['boat']=self._make_mesh(*build_boat())
        self.meshes['sky']=self._make_mesh(*build_sky())
        for level in profile_levels('standard'):
            self.terrain_meshes[level.terrain_resolution]=self._make_mesh(*build_terrain(level.terrain_resolution))
        # Perfil extended/quick usan las mismas resoluciones base.

    def pump(self):
        msg=MSG()
        while self.user32.PeekMessageW(ctypes.byref(msg),None,0,0,PM_REMOVE):
            self.user32.TranslateMessage(ctypes.byref(msg)); self.user32.DispatchMessageW(ctypes.byref(msg))

    def _set_mesh(self, mesh: _Mesh):
        stride=UINT(32); offset=UINT(0); vb=ctypes.c_void_p(mesh.vb.value); vbs=(ctypes.c_void_p*1)(vb)
        _com_method(self.context,CTX_IA_SET_VERTEX_BUFFERS,None,UINT,UINT,ctypes.POINTER(ctypes.c_void_p),ctypes.POINTER(UINT),ctypes.POINTER(UINT))(self.context,0,1,vbs,ctypes.byref(stride),ctypes.byref(offset))
        _com_method(self.context,CTX_IA_SET_INDEX_BUFFER,None,ctypes.c_void_p,UINT,UINT)(self.context,mesh.ib,DXGI_FORMAT_R32_UINT,0)

    def _update_cb(self, viewproj, camera, elapsed, object_type, level: SceneLevel):
        vals=_flatten_matrix(viewproj)+[camera[0],camera[1],camera[2],elapsed,float(object_type),0.0,float(level.shader_iterations),float(level.texture_samples),float(self.width),float(self.height),0.0,0.0]
        raw=struct.pack('<28f',*vals); buf=ctypes.create_string_buffer(raw)
        _com_method(self.context,CTX_UPDATE_SUBRESOURCE,None,ctypes.c_void_p,UINT,ctypes.c_void_p,ctypes.c_void_p,UINT,UINT)(self.context,self.cbuffer,0,None,ctypes.cast(buf,LPVOID),0,0)

    def _draw(self, mesh: _Mesh, instances: int, viewproj, camera, elapsed, object_type, level, blend=False, depth_readonly=False):
        if instances<=0:return
        self._set_mesh(mesh); self._update_cb(viewproj,camera,elapsed,object_type,level)
        blend_factor=(FLOAT*4)(0,0,0,0)
        _com_method(self.context,CTX_OM_SET_BLEND_STATE,None,ctypes.c_void_p,ctypes.POINTER(FLOAT),UINT)(self.context,self.blend if blend and self.blend.value else None,blend_factor,0xffffffff)
        if depth_readonly:
            depth_state=getattr(self,'depth_readonly',None)
            if depth_state is not None and getattr(depth_state,'value',None):
                try:
                    _com_method(self.context,CTX_OM_SET_DEPTH_STENCIL_STATE,None,ctypes.c_void_p,UINT)(self.context,depth_state,0)
                except RuntimeError:
                    # Compatibilidad defensiva con contextos de prueba/feature reducido.
                    # En D3D11 hardware normal el slot forma parte obligatoria de la interfaz.
                    pass
        if instances==1:
            _com_method(self.context,CTX_DRAW_INDEXED,None,UINT,UINT,ctypes.c_int)(self.context,mesh.index_count,0,0)
        else:
            _com_method(self.context,CTX_DRAW_INDEXED_INSTANCED,None,UINT,UINT,UINT,ctypes.c_int,UINT)(self.context,mesh.index_count,instances,0,0,0)

    def render_frame(self, level: SceneLevel, elapsed: float, level_index: int, *, show_after_present: bool = True, gpu_timing: bool = False, pump_messages: bool = True):
        if pump_messages:
            self.pump()
        gpu_timer=getattr(self,'gpu_timer',None)
        timer_slot=gpu_timer.begin_frame() if gpu_timing and gpu_timer is not None else None
        storm=max(0.0,min(1.0,(float(level.shader_iterations)-8.0)/20.0))
        clear=(FLOAT*4)(0.075-0.035*storm,0.20-0.095*storm,0.34-0.16*storm,1.0)
        _com_method(self.context,CTX_CLEAR_RENDER_TARGET_VIEW,None,ctypes.c_void_p,ctypes.POINTER(FLOAT))(self.context,self.rtv,clear)
        _com_method(self.context,CTX_CLEAR_DEPTH_STENCIL_VIEW,None,ctypes.c_void_p,UINT,FLOAT,ctypes.c_ubyte)(self.context,self.dsv,D3D11_CLEAR_DEPTH|D3D11_CLEAR_STENCIL,1.0,0)
        rtvs=(ctypes.c_void_p*1)(self.rtv.value); _com_method(self.context,CTX_OM_SET_RENDER_TARGETS,None,UINT,ctypes.POINTER(ctypes.c_void_p),ctypes.c_void_p)(self.context,1,rtvs,self.dsv)
        vp=D3D11_VIEWPORT(0.0,0.0,float(self.width),float(self.height),0.0,1.0); _com_method(self.context,CTX_RS_SET_VIEWPORTS,None,UINT,ctypes.POINTER(D3D11_VIEWPORT))(self.context,1,ctypes.byref(vp))
        if self.raster.value: _com_method(self.context,CTX_RS_SET_STATE,None,ctypes.c_void_p)(self.context,self.raster)
        _com_method(self.context,CTX_IA_SET_INPUT_LAYOUT,None,ctypes.c_void_p)(self.context,self.layout); _com_method(self.context,CTX_IA_SET_PRIMITIVE_TOPOLOGY,None,UINT)(self.context,D3D11_PRIMITIVE_TOPOLOGY_TRIANGLELIST)
        _com_method(self.context,CTX_VS_SET_SHADER,None,ctypes.c_void_p,ctypes.c_void_p,UINT)(self.context,self.vs,None,0); _com_method(self.context,CTX_PS_SET_SHADER,None,ctypes.c_void_p,ctypes.c_void_p,UINT)(self.context,self.ps,None,0)
        cbs=(ctypes.c_void_p*1)(self.cbuffer.value); _com_method(self.context,CTX_VS_SET_CONSTANT_BUFFERS,None,UINT,UINT,ctypes.POINTER(ctypes.c_void_p))(self.context,0,1,cbs); _com_method(self.context,CTX_PS_SET_CONSTANT_BUFFERS,None,UINT,UINT,ctypes.POINTER(ctypes.c_void_p))(self.context,0,1,cbs)
        srvs=(ctypes.c_void_p*1)(self.noise_srv.value); samps=(ctypes.c_void_p*1)(self.sampler.value); _com_method(self.context,CTX_PS_SET_SHADER_RESOURCES,None,UINT,UINT,ctypes.POINTER(ctypes.c_void_p))(self.context,0,1,srvs); _com_method(self.context,CTX_PS_SET_SAMPLERS,None,UINT,UINT,ctypes.POINTER(ctypes.c_void_p))(self.context,0,1,samps)
        eye,target=_camera_at(elapsed,level_index); view=_look_at_lh(eye,target); proj=_perspective_fov_lh(math.radians(58.0),self.width/self.height,0.5,900.0); vp_mat=_mat_mul(view,proj)
        terrain=self.terrain_meshes.get(level.terrain_resolution) or next(iter(self.terrain_meshes.values()))
        # V14: opacos -> cielo sin escritura de profundidad -> nubes transparentes.
        # Así el cielo sólo llena fondo y las tarjetas de nube pueden solaparse sin
        # convertirse en placas opacas ni ser sobrescritas por el sky dome.
        self._draw(terrain,1,vp_mat,eye,elapsed,0,level)
        self._draw(self.meshes['water'],1,vp_mat,eye,elapsed,1,level)
        self._draw(self.meshes['rock'],level.rock_instances,vp_mat,eye,elapsed,5,level)
        self._draw(self.meshes['tree'],level.tree_instances,vp_mat,eye,elapsed,4,level)
        self._draw(self.meshes['boat'],int(getattr(level,'boat_instances',0) or 0),vp_mat,eye,elapsed,7,level)
        self._draw(self.meshes['jet'],level.jet_instances,vp_mat,eye,elapsed,2,level)
        self._draw(self.meshes['sky'],1,vp_mat,eye,elapsed,6,level,depth_readonly=True)
        self._draw(self.meshes['cloud'],level.cloud_instances,vp_mat,eye,elapsed,3,level,blend=True,depth_readonly=True)
        self._draw(self.meshes['fire'],int(getattr(level,'fire_instances',0) or 0),vp_mat,eye,elapsed,9,level,blend=True,depth_readonly=True)
        self._draw(self.meshes['smoke'],int(getattr(level,'smoke_instances',0) or 0),vp_mat,eye,elapsed,8,level,blend=True,depth_readonly=True)
        # Restaura estados por claridad antes de Present.
        blend_factor=(FLOAT*4)(0,0,0,0)
        _com_method(self.context,CTX_OM_SET_BLEND_STATE,None,ctypes.c_void_p,ctypes.POINTER(FLOAT),UINT)(self.context,None,blend_factor,0xffffffff)
        try:
            _com_method(self.context,CTX_OM_SET_DEPTH_STENCIL_STATE,None,ctypes.c_void_p,UINT)(self.context,None,0)
        except RuntimeError:
            pass
        if timer_slot is not None:
            gpu_timer.end_frame(timer_slot)
        # VSync OFF (sync interval 0). CPU frametime mide el bucle presentado;
        # GPU frametime V14 usa timestamp queries dentro del command stream.
        self._present()
        # V14: GetData y ShowWindow quedan fuera de la región cronometrada cuando
        # el caller usa prepare_timed_frame(). El return se conserva por compatibilidad.
        if show_after_present:
            self._show_if_ready()
        return []

    def set_title(self,text):
        try:self.user32.SetWindowTextW(self.hwnd,str(text))
        except Exception:pass

    def close(self):
        if self.gpu_timer is not None:
            try:self.gpu_timer.close()
            except Exception:pass
            self.gpu_timer=None
        for m in list(self.terrain_meshes.values())+list(self.meshes.values()):
            _release(getattr(m,'ib',None)); _release(getattr(m,'vb',None))
        for name in ('depth_readonly','raster','blend','noise_srv','noise_tex','sampler','cbuffer','layout','ps','vs','dsv','depth_tex','rtv','context','device','swap'):
            _release(getattr(self,name,None)); setattr(self,name,ctypes.c_void_p())
        try:
            if self.hwnd:self.user32.DestroyWindow(self.hwnd)
        except Exception:pass
        try:
            if self.class_name and self.hinstance:self.user32.UnregisterClassW(self.class_name,self.hinstance)
        except Exception:pass
        self.hwnd=None


def _telemetry_brief(sampler):
    if not callable(sampler): return {}
    try:
        row=sampler() or {}
        out={}
        for key in ('gpu_temp','gpu_usage','gpu_clock_mhz','gpu_vram_used_mb','cpu_temp'):
            value=row.get(key)
            try: out[key]=float(value) if value is not None else None
            except Exception: out[key]=None
        return out
    except Exception:
        return {}


def run_directx_benchmark(profile: str='standard', *, width: int=1920, height: int=1080, visible: bool=True, progress_callback: ProgressCallback=None, telemetry_sampler: TelemetrySampler=None, cancel_check: CancelCheck=None) -> dict:
    """Ejecuta Benchmark V25: 49 s de render/Present medidos + warm-up/settle.

    Cada fase medida dura un número fijo de segundos de reloj de pared y la cámara/
    animación usa ese mismo reloj. El frametime, en cambio, cronometra sólo
    ``render_frame + Present``. Pump de mensajes, queries, telemetría y callbacks
    no contaminan FPS/1% Low, pero tampoco pueden ralentizar la cámara.
    """
    method=GPU_BENCHMARK_METHOD
    if platform.system()!='Windows':
        return {'kind':'GPU','status':'UNAVAILABLE','value':None,'unit':'FPS','provider':GPU_PROVIDER,'reason':'DirectX 11 sólo está disponible en Windows','benchmark_method':method}
    levels=profile_levels(profile)
    total=sum(s.warmup_seconds+s.settle_seconds+s.measure_seconds for s in levels) or 1.0
    renderer=None; started=time.perf_counter(); scene_rows=[]; elapsed_base=0.0; path_base=0.0; telemetry=[]
    try:
        renderer=D3D11Renderer(width,height,visible=visible)
        for idx,level in enumerate(levels):
            if callable(cancel_check) and cancel_check(): break
            if level.warmup_seconds > 0:
                renderer.set_title(f'CorePulse Benchmark {GPU_BENCHMARK_LABEL} — {level.label} — calentamiento')
                warm_start=time.perf_counter(); next_sample=warm_start; next_progress_warm=warm_start
                while time.perf_counter()-warm_start<level.warmup_seconds:
                    if renderer.cancelled or (callable(cancel_check) and cancel_check()): break
                    frame_t=time.perf_counter(); renderer.render_frame(level,path_base+(frame_t-warm_start),idx)
                    now=time.perf_counter()
                    if now>=next_sample:
                        telemetry.append({'scene':level.key,'phase':'warmup','timestamp':time.time(),**_telemetry_brief(telemetry_sampler)}); next_sample=now+0.5
                    frac=(elapsed_base+(now-warm_start))/total
                    if callable(progress_callback) and now >= next_progress_warm:
                        progress_callback(frac,f'GPU · {level.label}',f'Warm-up {now-warm_start:.1f}/{level.warmup_seconds:.1f} s · fuera de la medición')
                        next_progress_warm=now+0.10
                if renderer.cancelled or (callable(cancel_check) and cancel_check()): break
                elapsed_base += level.warmup_seconds

            # Settle temporal por escena: se ejecuta el workload definitivo antes de
            # abrir estadísticas. Esto vacía transiciones de caché/cola y evita que
            # el primer frame de una fase destruya artificialmente el 1% Low.
            renderer.set_title(f'CorePulse Benchmark {GPU_BENCHMARK_LABEL} — {level.label} — estabilizando')
            settle_start=time.perf_counter(); settle_frames=0
            while time.perf_counter()-settle_start<level.settle_seconds:
                if renderer.cancelled or (callable(cancel_check) and cancel_check()): break
                renderer.render_frame(level,path_base+level.warmup_seconds+(time.perf_counter()-settle_start),idx)
                settle_frames += 1
            if renderer.cancelled or (callable(cancel_check) and cancel_check()): break
            elapsed_base += level.settle_seconds

            # V14: prime fijo del camino de Present y del pipeline antes de abrir
            # queries/estadísticas. Se reporta, no se mezcla con los 49 s medidos.
            prime_frames=8
            prime_time=path_base+level.warmup_seconds+level.settle_seconds
            for prime_idx in range(prime_frames):
                if renderer.cancelled or (callable(cancel_check) and cancel_check()): break
                renderer.render_frame(level,prime_time,idx,show_after_present=False)
                renderer.prepare_timed_frame()
            if renderer.cancelled or (callable(cancel_check) and cancel_check()): break

            renderer.set_title(f'CorePulse Benchmark {GPU_BENCHMARK_LABEL} — {level.label} — midiendo')
            frame_times=[]; renderer.begin_scene_gpu_timing(); next_sample=time.perf_counter()
            measured_render_s=0.0; measure_wall_start=time.perf_counter(); next_progress=measure_wall_start
            # V14: la cámara, shaders y fin de fase usan reloj de pared.
            # El frametime sigue midiendo EXCLUSIVAMENTE render_frame + Present.
            # Así una caída de FPS no ralentiza la animación ni alarga la escena.
            while True:
                wall_elapsed=time.perf_counter()-measure_wall_start
                if wall_elapsed>=level.measure_seconds:
                    break
                if renderer.cancelled or (callable(cancel_check) and cancel_check()): break

                renderer.prepare_timed_frame()
                frame_start_ns=time.perf_counter_ns()
                scene_elapsed=min(wall_elapsed, level.measure_seconds)
                renderer.render_frame(
                    level,
                    path_base+level.warmup_seconds+level.settle_seconds+scene_elapsed,
                    idx,
                    gpu_timing=True,
                    show_after_present=False,
                    pump_messages=False,
                )
                frame_end_ns=time.perf_counter_ns()
                frame_ms=(frame_end_ns-frame_start_ns)/1_000_000.0
                if frame_ms>0.0 and math.isfinite(frame_ms):
                    frame_times.append(frame_ms)
                    measured_render_s += frame_ms/1000.0

                # Query readback, telemetría y UI quedan fuera del frametime,
                # pero SÍ forman parte del reloj real de la escena.
                renderer.poll_gpu_timing()
                now=time.perf_counter()
                if now>=next_sample:
                    telemetry.append({'scene':level.key,'phase':'measure','timestamp':time.time(),**_telemetry_brief(telemetry_sampler)}); next_sample=now+0.45
                wall_elapsed=min(now-measure_wall_start, level.measure_seconds)
                frac=(elapsed_base+wall_elapsed)/total
                # La UI no debe bloquear un callback por frame. Se actualiza a 10 Hz
                # fuera del cronómetro para mantener movimiento visual fluido sin
                # alterar las estadísticas de render+Present.
                if callable(progress_callback) and now >= next_progress:
                    st_live=_fps_stats(frame_times[-240:]); fps=st_live.get('fps')
                    progress_callback(frac,f'GPU · {level.label}',f'{fps:.1f} FPS · DirectX 11 · {renderer.adapter_name}' if fps else 'Midiendo frames reales…')
                    next_progress=now+0.10

            measure_wall_s=time.perf_counter()-measure_wall_start
            elapsed_base += level.measure_seconds
            gpu_times,gpu_meta=renderer.finish_scene_gpu_timing(timeout_s=4.0)
            st=_fps_stats(frame_times); gst=_gpu_time_stats(gpu_times,st['frames'],gpu_meta.get('dropped',0),gpu_meta.get('disjoint',0)); workload=level_workload(level)
            cv=(statistics.pstdev(frame_times)/st['frametime_avg_ms']) if len(frame_times)>1 and st.get('frametime_avg_ms') else 0.0
            max_to_median=(max(frame_times)/st['frametime_median_ms']) if frame_times and st.get('frametime_median_ms') else None
            scene_rows.append({
                'key':level.key,'label':level.label,'status':'CANCELLED' if renderer.cancelled or (callable(cancel_check) and cancel_check()) else 'OK',
                'api':'DirectX 11','feature_level':renderer.feature_level,'resolution':f'{renderer.width}x{renderer.height}','vsync':False,
                'warmup_seconds':level.warmup_seconds,'settle_seconds':level.settle_seconds,'settle_frames_discarded':settle_frames,'measurement_prime_frames_discarded':prime_frames,
                'measure_target_seconds':level.measure_seconds,'measured_seconds':min(measure_wall_s,level.measure_seconds),'measurement_wall_seconds':measure_wall_s,'render_present_accumulated_seconds':measured_render_s,'wall_clock_deterministic':True,
                'frames':st['frames'],'valid_frames':st['frames'],'frames_per_s':st['fps'],'one_percent_low_fps':st['one_percent_low_fps'],
                'frametime_avg_ms':st['frametime_avg_ms'],'frametime_median_ms':st.get('frametime_median_ms'),
                'frametime_p95_ms':st['frametime_p95_ms'],'frametime_p99_ms':st['frametime_p99_ms'],
                'frametime_spike_threshold_ms':st.get('frametime_spike_threshold_ms'),'frametime_spike_frames':st.get('frametime_spike_frames'),
                'frametime_spike_ratio':st.get('frametime_spike_ratio'),'frametime_cv':cv,'frametime_max_to_median_ratio':max_to_median,
                **gst,
                'gpu_frame_time_ms':gst.get('gpu_frame_time_avg_ms'),
                'gpu_frame_time_status':('MEASURED_D3D11_TIMESTAMP' if gst.get('gpu_samples') else ('N/A: '+str(renderer.gpu_timing_reason or 'sin muestras timestamp válidas'))),
                'workload':workload,
            })
            path_base += level.warmup_seconds + level.settle_seconds + level.measure_seconds
            if scene_rows[-1]['status']!='OK': break
        status='CANCELLED' if renderer.cancelled or (callable(cancel_check) and cancel_check()) else ('OK' if scene_rows and all(r['status']=='OK' for r in scene_rows) else 'PARTIAL')
        primary=next((r for r in scene_rows if r['key']=='extreme'),None) or (scene_rows[-1] if scene_rows else None)
        if callable(progress_callback): progress_callback(1.0,'GPU completado' if status=='OK' else 'GPU cancelado',f'{renderer.adapter_name} · DirectX 11')
        return {
            'kind':'GPU','status':status,'value':(primary or {}).get('frames_per_s'),'unit':'FPS','provider':GPU_PROVIDER,
            'benchmark_method':method,'benchmark_mode':f'VISIBLE_REALISTIC_VALLEY_{GPU_BENCHMARK_LABEL}_WALLCLOCK_DETERMINISTIC',
            'duration_s':time.perf_counter()-started,'api':'DirectX 11','feature_level':renderer.feature_level,'renderer':renderer.adapter_name,'dedicated_vram_mb':renderer.vram_mb,
            'resolution':f'{renderer.width}x{renderer.height}','vsync_disabled':True,'scenes':scene_rows,'scene_count':len(scene_rows),'telemetry_samples':telemetry,
            'startup_stage':renderer.startup_stage,'startup_checks':list(renderer.startup_checks),
            'primary_scene':(primary or {}).get('key'),'frames_per_s':(primary or {}).get('frames_per_s'),'one_percent_low_fps':(primary or {}).get('one_percent_low_fps'),
            'frametime_avg_ms':(primary or {}).get('frametime_avg_ms'),'frametime_median_ms':(primary or {}).get('frametime_median_ms'),
            'frametime_p95_ms':(primary or {}).get('frametime_p95_ms'),'frametime_p99_ms':(primary or {}).get('frametime_p99_ms'),
            'frametime_spike_frames':(primary or {}).get('frametime_spike_frames'),'frametime_spike_ratio':(primary or {}).get('frametime_spike_ratio'),'frametime_cv':(primary or {}).get('frametime_cv'),'frametime_max_to_median_ratio':(primary or {}).get('frametime_max_to_median_ratio'),
            'gpu_frame_time_avg_ms':(primary or {}).get('gpu_frame_time_avg_ms'),'gpu_frame_time_p95_ms':(primary or {}).get('gpu_frame_time_p95_ms'),'gpu_frame_time_p99_ms':(primary or {}).get('gpu_frame_time_p99_ms'),
            'gpu_timestamp_samples':(primary or {}).get('gpu_samples'),'gpu_timestamp_coverage':(primary or {}).get('gpu_sample_coverage'),
            'gpu_timing_available':renderer.gpu_timing_available,'gpu_timing_reason':renderer.gpu_timing_reason,
            'policy':GPU_POLICY,
        }
    except Exception as exc:
        message=f'{type(exc).__name__}: {exc}'
        stage=getattr(renderer,'startup_stage',None) if renderer is not None else None
        if not stage:
            match=re.search(r'DirectX startup \[([^\]]+)\]', str(exc)); stage=match.group(1) if match else 'renderer_constructor'
        checks=list(getattr(renderer,'startup_checks',[]) or []) if renderer is not None else []
        return {'kind':'GPU','status':'ERROR','value':None,'unit':'FPS','provider':GPU_PROVIDER,'benchmark_method':method,'reason':message,'failure_stage':stage,'startup_checks':checks,'duration_s':time.perf_counter()-started,'policy':GPU_POLICY}
    finally:
        if renderer is not None:
            try: renderer.close()
            except Exception: pass

def gpu_profile_info(profile: str='standard') -> dict:
    levels=profile_levels(profile); seconds=sum(s.warmup_seconds+s.settle_seconds+s.measure_seconds for s in levels)
    return {
        'key':str(profile or 'standard').lower(),'label':f'DirectX 11 · Valle realista {GPU_BENCHMARK_LABEL} · safe boat route','seconds':seconds,
        'resolution':'1920x1080','scene_count':len(levels),'prime_frames':8*len(levels),
        'warmup_policy':'5 s de warm-up global + settle temporal por escena + 8 prime frames por escena; todo excluido de estadísticas',
        'description':'Valle/Bosque/Lago/Extreme con 1 avión principal, barco visible en el canal central y fogata con humo visible en Extreme; VSync OFF, 49 s de render/Present y timestamps GPU D3D11 auditados.',
    }
