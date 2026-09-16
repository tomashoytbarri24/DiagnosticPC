"""Benchmark visual 3D propio de CorePulse.

Benchmark visual reproducible dividido en cargas reales de GPU, CPU y RAM:
geometría, fill/fragmentos, texturas/VRAM, shaders programables, compute/GPGPU,
CPU multinúcleo, copia sostenida de memoria y carga combinada. CorePulse mide
FPS/frametime del bucle visible y cruza cada fase con telemetría real. No estima
FPS ni sensores ausentes.
"""
from __future__ import annotations

import ctypes
import hashlib
import math
import os
import platform
import threading
import time
from typing import Any, Callable, Dict, Optional

from core.diagnostic_evidence import gpu_for_renderer, number

ProgressCallback = Optional[Callable[[float, str, str], None]]
TelemetrySampler = Optional[Callable[[], Dict[str, Any]]]
CancelCheck = Optional[Callable[[], bool]]

VISUAL_PROFILES = {
    # V125: los perfiles visuales dejan de ser una demo ligera. La carga GPU
    # aumenta de forma deliberada y reproducible; el usuario puede elegir un
    # perfil menor en equipos modestos. El benchmark nunca intenta ocultar que
    # Windows puede asignar el contexto OpenGL a otro adaptador en portátiles
    # híbridos: el renderer real siempre se registra y se muestra.
    'quick': {
        'label': 'Rápido',
        'seconds': 12.0,
        'warmup_seconds': 1.0,
        'width': 1280,
        'height': 720,
        'grid': 96,
        'layers': 48,
        'fill_passes': 20,
        'texture_size': 2048,
        'texture_count': 4,
        'texture_passes': 22,
        'combined_texture_passes': 10,
        'shader_passes': 8,
        'combined_shader_passes': 3,
        'compute_buffer_mb': 16,
        'compute_passes': 2,
        'combined_compute_passes': 1,
        'cpu_hash_block_kb': 512,
        'cpu_worker_cap': 8,
        'ram_buffer_mb': 32,
        'ram_workers': 2,
    },
    'standard': {
        'label': 'Estándar',
        'seconds': 24.0,
        'warmup_seconds': 1.5,
        'width': 1440,
        'height': 810,
        'grid': 128,
        'layers': 80,
        'fill_passes': 48,
        'texture_size': 2048,
        'texture_count': 8,
        'texture_passes': 42,
        'combined_texture_passes': 18,
        'shader_passes': 18,
        'combined_shader_passes': 6,
        'compute_buffer_mb': 32,
        'compute_passes': 4,
        'combined_compute_passes': 2,
        'cpu_hash_block_kb': 1024,
        'cpu_worker_cap': 16,
        'ram_buffer_mb': 64,
        'ram_workers': 3,
    },
    'extended': {
        'label': 'Extendido',
        'seconds': 48.0,
        'warmup_seconds': 2.0,
        'width': 1600,
        'height': 900,
        'grid': 160,
        'layers': 112,
        'fill_passes': 72,
        'texture_size': 2048,
        'texture_count': 12,
        'texture_passes': 60,
        'combined_texture_passes': 28,
        'shader_passes': 30,
        'combined_shader_passes': 10,
        'compute_buffer_mb': 64,
        'compute_passes': 6,
        'combined_compute_passes': 3,
        'cpu_hash_block_kb': 1024,
        'cpu_worker_cap': 32,
        'ram_buffer_mb': 128,
        'ram_workers': 4,
    },
}


def visual_profile_info(profile: str = 'standard') -> Dict[str, Any]:
    key = str(profile or 'standard').strip().lower()
    if key not in VISUAL_PROFILES:
        key = 'standard'
    return {'key': key, **VISUAL_PROFILES[key]}


def _safe_progress(callback: ProgressCallback, fraction: float, stage: str, detail: str = ''):
    if not callable(callback):
        return
    try:
        callback(max(0.0, min(1.0, float(fraction))), str(stage), str(detail or ''))
    except Exception:
        pass


def _float(value):
    try:
        return float(value) if value is not None else None
    except Exception:
        return None


def _first_number(*values):
    for value in values:
        parsed = number(value)
        if parsed is not None:
            return parsed
    return None


def _visual_telemetry_metrics(raw, renderer):
    """Reduce un snapshot real al renderer que atiende el contexto OpenGL.

    Si el llamador entrega el formato plano histórico, se conserva. Cuando
    existe inventario ``_gpus``, sólo una coincidencia inequívoca con el
    renderer puede aportar temperatura/uso/frecuencia de GPU.
    """
    if not isinstance(raw, dict):
        return {}
    cpu = raw.get('_cpu') if isinstance(raw.get('_cpu'), dict) else {}
    gpus = raw.get('_gpus') if isinstance(raw.get('_gpus'), list) else []
    matched = gpu_for_renderer(gpus, renderer) if gpus else {}

    def gpu_sensor_limit(kind):
        if not matched:
            return None
        for row in matched.get('sensors') or []:
            if not isinstance(row, dict):
                continue
            name = str(row.get('name') or row.get('sensor_name') or '').casefold()
            sensor_type = str(row.get('type') or row.get('sensor_type') or '').casefold()
            value = _first_number(row.get('value'))
            if value is None or not (20.0 <= value <= 150.0):
                continue
            if 'limit' not in name and 'critical' not in name:
                continue
            if 'temp' not in name and 'thermal' not in name and sensor_type != 'temperature':
                continue
            if kind == 'hotspot' and 'hot' in name:
                return value
            if kind == 'core' and 'hot' not in name:
                return value
        return None

    # El formato plano sigue permitido para tests/llamadores antiguos, pero
    # nunca sustituye una identidad de GPU cuando existe una lista detallada.
    gpu_temp = _first_number(matched.get('temperature_c')) if matched else (None if gpus else _first_number(raw.get('gpu_temp')))
    gpu_hotspot = _first_number(matched.get('hotspot_c')) if matched else (None if gpus else _first_number(raw.get('gpu_hotspot')))
    gpu_usage = _first_number(matched.get('usage_percent')) if matched else (None if gpus else _first_number(raw.get('gpu_usage')))
    gpu_vram_used = _first_number(matched.get('memory_used_mb')) if matched else (None if gpus else _first_number(raw.get('gpu_vram_used_mb')))
    gpu_vram_pct = _first_number(matched.get('memory_usage_percent')) if matched else (None if gpus else _first_number(raw.get('gpu_vram_usage_percent')))

    return {
        'cpu_temp': _first_number(raw.get('cpu_temp'), cpu.get('package_temp_c'), cpu.get('core_max_temp_c'), cpu.get('core_average_temp_c')),
        'cpu_tjmax_distance': _first_number(cpu.get('distance_to_tjmax_min_c'), raw.get('cpu_distance_to_tjmax_min_c'), raw.get('distance_to_tjmax_min_c')),
        'cpu_ghz': _first_number(raw.get('cpu_ghz'), cpu.get('clock_avg_ghz'), cpu.get('clock_max_ghz')),
        'cpu_usage': _first_number(raw.get('cpu_usage'), cpu.get('usage_percent'), cpu.get('total_load_percent')),
        'ram_usage': _first_number(raw.get('ram_usage')),
        'gpu_temp': gpu_temp,
        'gpu_hotspot': gpu_hotspot,
        'gpu_temp_limit': gpu_sensor_limit('core') if matched else (None if gpus else _first_number(raw.get('gpu_temp_limit'))),
        'gpu_hotspot_limit': gpu_sensor_limit('hotspot') if matched else (None if gpus else _first_number(raw.get('gpu_hotspot_limit'))),
        'gpu_usage': gpu_usage,
        'gpu_vram_used_mb': gpu_vram_used,
        'gpu_vram_usage_percent': gpu_vram_pct,
        'gpu_sensor_match': bool(matched),
        'gpu_sensor_name': str(matched.get('name') or '') if matched else None,
    }


def _telemetry_summary(samples):
    out: Dict[str, Any] = {'sample_count': len(samples)}
    for key in ('cpu_temp', 'cpu_ghz', 'cpu_usage', 'ram_usage', 'cpu_tjmax_distance', 'gpu_temp', 'gpu_hotspot', 'gpu_temp_limit', 'gpu_hotspot_limit', 'gpu_usage', 'gpu_vram_used_mb', 'gpu_vram_usage_percent'):
        vals = [_float(row.get(key)) for row in samples]
        vals = [v for v in vals if v is not None and math.isfinite(v)]
        if vals:
            out[key] = {'min': min(vals), 'max': max(vals), 'avg': sum(vals) / len(vals)}
    return out


def _percentile(sorted_values, q: float):
    if not sorted_values:
        return None
    q = max(0.0, min(1.0, float(q)))
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    index = (len(sorted_values) - 1) * q
    lo = int(math.floor(index))
    hi = int(math.ceil(index))
    if lo == hi:
        return float(sorted_values[lo])
    frac = index - lo
    return float(sorted_values[lo]) * (1.0 - frac) + float(sorted_values[hi]) * frac


def _one_percent_low_fps(frame_times_ms):
    """FPS equivalente al promedio del 1 % de frames más lentos."""
    values = [float(v) for v in frame_times_ms or [] if _float(v) is not None and float(v) > 0.0]
    if not values:
        return None
    slow_count = max(1, int(math.ceil(len(values) * 0.01)))
    slowest = sorted(values, reverse=True)[:slow_count]
    avg_slow_ms = sum(slowest) / len(slowest)
    return (1000.0 / avg_slow_ms) if avg_slow_ms > 0 else None


def _phase_result(key: str, label: str, frame_times_ms, telemetry_samples=None, workload=None):
    """Resume una fase usando únicamente frametimes medidos realmente."""
    values = [float(v) for v in frame_times_ms or [] if _float(v) is not None and float(v) > 0.0]
    sorted_ft = sorted(values)
    avg_ms = (sum(values) / len(values)) if values else None
    fps = (1000.0 / avg_ms) if avg_ms and avg_ms > 0 else None
    result = {
        'key': str(key),
        'label': str(label),
        'status': 'OK' if values else 'N/A',
        'frames': len(values),
        'duration_s': (sum(values) / 1000.0) if values else 0.0,
        'frames_per_s': fps,
        'one_percent_low_fps': _one_percent_low_fps(values),
        'frametime_avg_ms': avg_ms,
        'frametime_p95_ms': _percentile(sorted_ft, 0.95),
        'frametime_p99_ms': _percentile(sorted_ft, 0.99),
        'telemetry': _telemetry_summary(telemetry_samples or []),
        'workload': dict(workload or {}),
    }
    return result


def _valid_wgl_proc_address(value) -> bool:
    """Filtra sentinelas inválidos documentados/de facto de wglGetProcAddress."""
    try:
        raw = int(value or 0)
    except Exception:
        return False
    invalid = {0, 1, 2, 3, 0xFFFFFFFF, 0xFFFFFFFFFFFFFFFF}
    return raw not in invalid


def _build_wave_mesh(grid: int):
    grid = max(24, min(int(grid), 160))
    cells = grid - 1
    vertices = []
    colors = []

    def point(ix, iz):
        nx = ix / float(cells)
        nz = iz / float(cells)
        x = (nx - 0.5) * 9.6
        z = (nz - 0.5) * 9.6
        y = (
            math.sin(x * 1.35) * 0.34
            + math.cos(z * 1.10) * 0.28
            + math.sin((x + z) * 0.72) * 0.20
        )
        # Paleta CorePulse: cian -> verde -> violeta según posición/altura.
        r = 0.10 + 0.48 * nz
        g = 0.46 + 0.42 * nx
        b = 0.92 - 0.26 * nx + 0.06 * math.sin((x - z) * 0.4)
        return (x, y, z, max(0.0, min(1.0, r)), max(0.0, min(1.0, g)), max(0.0, min(1.0, b)))

    for iz in range(cells):
        for ix in range(cells):
            p00 = point(ix, iz)
            p10 = point(ix + 1, iz)
            p01 = point(ix, iz + 1)
            p11 = point(ix + 1, iz + 1)
            for p in (p00, p10, p11, p00, p11, p01):
                vertices.extend(p[:3])
                colors.extend(p[3:6])

    vertex_count = len(vertices) // 3
    vertex_array = (ctypes.c_float * len(vertices))(*vertices)
    color_array = (ctypes.c_float * len(colors))(*colors)
    return vertex_array, color_array, vertex_count


def _run_windows_visual(profile_data, progress_callback: ProgressCallback, telemetry_sampler: TelemetrySampler, components=None, cancel_check: CancelCheck = None):
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    kernel32 = ctypes.windll.kernel32
    opengl32 = ctypes.windll.opengl32

    HWND_T = getattr(wintypes, 'HWND', wintypes.HANDLE)
    HINSTANCE_T = getattr(wintypes, 'HINSTANCE', wintypes.HANDLE)
    HMODULE_T = getattr(wintypes, 'HMODULE', HINSTANCE_T)
    HICON_T = getattr(wintypes, 'HICON', wintypes.HANDLE)
    HCURSOR_T = getattr(wintypes, 'HCURSOR', wintypes.HANDLE)
    HBRUSH_T = getattr(wintypes, 'HBRUSH', wintypes.HANDLE)
    HDC_T = getattr(wintypes, 'HDC', wintypes.HANDLE)
    HMENU_T = getattr(wintypes, 'HMENU', wintypes.HANDLE)
    HGLRC_T = wintypes.HANDLE
    LRESULT_T = ctypes.c_ssize_t

    WNDPROC = ctypes.WINFUNCTYPE(LRESULT_T, HWND_T, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

    class WNDCLASSW(ctypes.Structure):
        _fields_ = [
            ('style', wintypes.UINT), ('lpfnWndProc', WNDPROC), ('cbClsExtra', ctypes.c_int),
            ('cbWndExtra', ctypes.c_int), ('hInstance', HINSTANCE_T), ('hIcon', HICON_T),
            ('hCursor', HCURSOR_T), ('hbrBackground', HBRUSH_T), ('lpszMenuName', wintypes.LPCWSTR),
            ('lpszClassName', wintypes.LPCWSTR),
        ]

    class PIXELFORMATDESCRIPTOR(ctypes.Structure):
        _fields_ = [
            ('nSize', ctypes.c_ushort), ('nVersion', ctypes.c_ushort), ('dwFlags', ctypes.c_uint),
            ('iPixelType', ctypes.c_ubyte), ('cColorBits', ctypes.c_ubyte), ('cRedBits', ctypes.c_ubyte),
            ('cRedShift', ctypes.c_ubyte), ('cGreenBits', ctypes.c_ubyte), ('cGreenShift', ctypes.c_ubyte),
            ('cBlueBits', ctypes.c_ubyte), ('cBlueShift', ctypes.c_ubyte), ('cAlphaBits', ctypes.c_ubyte),
            ('cAlphaShift', ctypes.c_ubyte), ('cAccumBits', ctypes.c_ubyte), ('cAccumRedBits', ctypes.c_ubyte),
            ('cAccumGreenBits', ctypes.c_ubyte), ('cAccumBlueBits', ctypes.c_ubyte), ('cAccumAlphaBits', ctypes.c_ubyte),
            ('cDepthBits', ctypes.c_ubyte), ('cStencilBits', ctypes.c_ubyte), ('cAuxBuffers', ctypes.c_ubyte),
            ('iLayerType', ctypes.c_ubyte), ('bReserved', ctypes.c_ubyte), ('dwLayerMask', ctypes.c_uint),
            ('dwVisibleMask', ctypes.c_uint), ('dwDamageMask', ctypes.c_uint),
        ]

    class RECT(ctypes.Structure):
        _fields_ = [('left', ctypes.c_long), ('top', ctypes.c_long), ('right', ctypes.c_long), ('bottom', ctypes.c_long)]

    class MSG(ctypes.Structure):
        # Layout completo de Win32 MSG; lPrivate evita escritura fuera del buffer
        # en versiones modernas de Windows.
        _fields_ = [
            ('hwnd', HWND_T), ('message', wintypes.UINT), ('wParam', wintypes.WPARAM),
            ('lParam', wintypes.LPARAM), ('time', wintypes.DWORD),
            ('pt_x', ctypes.c_long), ('pt_y', ctypes.c_long), ('lPrivate', wintypes.DWORD),
        ]

    cancel_requested = {'value': False}
    WM_CLOSE = 0x0010
    WM_DESTROY = 0x0002

    @WNDPROC
    def wndproc(hwnd, msg, wparam, lparam):
        if msg in (WM_CLOSE, WM_DESTROY):
            cancel_requested['value'] = True
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    # Firmas pointer-safe Win64.
    kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
    kernel32.GetModuleHandleW.restype = HMODULE_T
    user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
    user32.RegisterClassW.restype = wintypes.ATOM
    user32.CreateWindowExW.argtypes = [
        wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        HWND_T, HMENU_T, HINSTANCE_T, wintypes.LPVOID,
    ]
    user32.CreateWindowExW.restype = HWND_T
    user32.DefWindowProcW.argtypes = [HWND_T, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.DefWindowProcW.restype = LRESULT_T
    user32.GetDC.argtypes = [HWND_T]
    user32.GetDC.restype = HDC_T
    user32.ReleaseDC.argtypes = [HWND_T, HDC_T]
    user32.ReleaseDC.restype = ctypes.c_int
    user32.DestroyWindow.argtypes = [HWND_T]
    user32.DestroyWindow.restype = wintypes.BOOL
    user32.UnregisterClassW.argtypes = [wintypes.LPCWSTR, HINSTANCE_T]
    user32.UnregisterClassW.restype = wintypes.BOOL
    user32.ShowWindow.argtypes = [HWND_T, ctypes.c_int]
    user32.ShowWindow.restype = wintypes.BOOL
    user32.UpdateWindow.argtypes = [HWND_T]
    user32.UpdateWindow.restype = wintypes.BOOL
    user32.SetWindowTextW.argtypes = [HWND_T, wintypes.LPCWSTR]
    user32.SetWindowTextW.restype = wintypes.BOOL
    user32.PeekMessageW.argtypes = [ctypes.POINTER(MSG), HWND_T, wintypes.UINT, wintypes.UINT, wintypes.UINT]
    user32.PeekMessageW.restype = wintypes.BOOL
    user32.TranslateMessage.argtypes = [ctypes.POINTER(MSG)]
    user32.DispatchMessageW.argtypes = [ctypes.POINTER(MSG)]
    user32.GetSystemMetrics.argtypes = [ctypes.c_int]
    user32.GetSystemMetrics.restype = ctypes.c_int
    user32.AdjustWindowRectEx.argtypes = [ctypes.POINTER(RECT), wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    user32.AdjustWindowRectEx.restype = wintypes.BOOL
    user32.GetClientRect.argtypes = [HWND_T, ctypes.POINTER(RECT)]
    user32.GetClientRect.restype = wintypes.BOOL
    user32.LoadCursorW.argtypes = [HINSTANCE_T, ctypes.c_void_p]
    user32.LoadCursorW.restype = HCURSOR_T

    gdi32.ChoosePixelFormat.argtypes = [HDC_T, ctypes.POINTER(PIXELFORMATDESCRIPTOR)]
    gdi32.ChoosePixelFormat.restype = ctypes.c_int
    gdi32.SetPixelFormat.argtypes = [HDC_T, ctypes.c_int, ctypes.POINTER(PIXELFORMATDESCRIPTOR)]
    gdi32.SetPixelFormat.restype = wintypes.BOOL
    gdi32.SwapBuffers.argtypes = [HDC_T]
    gdi32.SwapBuffers.restype = wintypes.BOOL

    opengl32.wglCreateContext.argtypes = [HDC_T]
    opengl32.wglCreateContext.restype = HGLRC_T
    opengl32.wglMakeCurrent.argtypes = [HDC_T, HGLRC_T]
    opengl32.wglMakeCurrent.restype = wintypes.BOOL
    opengl32.wglDeleteContext.argtypes = [HGLRC_T]
    opengl32.wglDeleteContext.restype = wintypes.BOOL
    opengl32.wglGetProcAddress.argtypes = [ctypes.c_char_p]
    opengl32.wglGetProcAddress.restype = ctypes.c_void_p

    selected_components = {
        str(item or '').strip().lower()
        for item in (components if components is not None else ('gpu', 'cpu', 'ram'))
        if str(item or '').strip().lower() in {'gpu', 'cpu', 'ram'}
    }
    if not selected_components:
        selected_components = {'gpu'}

    width = int(profile_data['width'])
    height = int(profile_data['height'])
    duration_target = float(profile_data['seconds'])
    warmup_seconds = max(0.0, float(profile_data.get('warmup_seconds') or 0.0))
    layers = int(profile_data['layers'])
    profile_label = str(profile_data['label'])

    hinstance = kernel32.GetModuleHandleW(None)
    if not hinstance:
        raise RuntimeError('Windows no entregó el módulo para crear el benchmark visual')
    class_name = f'CorePulseVisualBench_{os.getpid()}_{threading.get_ident()}'
    wc = WNDCLASSW()
    wc.style = 0x0020  # CS_OWNDC
    wc.lpfnWndProc = wndproc
    wc.hInstance = hinstance
    try:
        wc.hCursor = user32.LoadCursorW(None, ctypes.c_void_p(32512))
    except Exception:
        wc.hCursor = None
    wc.lpszClassName = class_name
    if not user32.RegisterClassW(ctypes.byref(wc)):
        raise RuntimeError('No se pudo registrar la ventana del benchmark visual')

    hwnd = hdc = hrc = None
    texture_ids = None
    texture_count_actual = 0
    shader_program = None
    shader_functions = {}
    shader_unavailable_reason = None
    compute_program = None
    compute_functions = {}
    compute_unavailable_reason = None
    compute_buffer = ctypes.c_uint(0)
    compute_buffer_bytes = 0
    compute_groups_x = 0

    # Cargas host reales. CPU usa SHA-256 nativo (hashlib/OpenSSL) en varios
    # hilos; RAM usa memcpy del CRT sobre regiones mayores que la caché típica.
    # Ambas se miden por throughput observado, no por FPS estimado.
    cpu_load_state = {'threads': [], 'stop': None, 'counts': [], 'payload': None, 'start': None}
    ram_load_state = {'threads': [], 'stop': None, 'counts': [], 'src': None, 'dst': None, 'start': None, 'bytes': 0, 'workers': 0}
    cpu_phase_metrics = {}
    ram_phase_metrics = {}
    cpu_unavailable_reason = None
    ram_unavailable_reason = None
    hud_list_base = 0
    samples = []
    stop_reason = None
    render_error = None
    frame_times_ms = []
    frames = 0
    cpu_safety_hits = 0
    gpu_safety_hits = 0
    triangle_count_per_mesh = (int(profile_data['grid']) - 1) ** 2 * 2

    try:
        screen_w = max(1, user32.GetSystemMetrics(0))
        screen_h = max(1, user32.GetSystemMetrics(1))
        # Tamaño fijo: la resolución del perfil corresponde al área de render
        # real, no al rectángulo exterior con bordes/título de Windows.
        WS_CAPTION = 0x00C00000
        WS_SYSMENU = 0x00080000
        WS_MINIMIZEBOX = 0x00020000
        WS_VISIBLE = 0x10000000
        window_style = WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX
        outer = RECT(0, 0, width, height)
        if not user32.AdjustWindowRectEx(ctypes.byref(outer), window_style, False, 0):
            raise RuntimeError('Windows no pudo calcular el tamaño exacto del área 3D')
        outer_w = int(outer.right - outer.left)
        outer_h = int(outer.bottom - outer.top)
        pos_x = max(0, (screen_w - outer_w) // 2)
        pos_y = max(0, (screen_h - outer_h) // 2)
        hwnd = user32.CreateWindowExW(
            0, class_name, f'CorePulse Visual Benchmark 3D — {profile_label}',
            window_style | WS_VISIBLE,
            pos_x, pos_y, outer_w, outer_h, None, None, hinstance, None,
        )
        if not hwnd:
            raise RuntimeError('No se pudo crear la ventana 3D del benchmark')
        user32.ShowWindow(hwnd, 5)  # SW_SHOW
        user32.UpdateWindow(hwnd)
        hdc = user32.GetDC(hwnd)
        if not hdc:
            raise RuntimeError('No se pudo obtener el contexto gráfico de Windows')

        pfd = PIXELFORMATDESCRIPTOR()
        pfd.nSize = ctypes.sizeof(PIXELFORMATDESCRIPTOR)
        pfd.nVersion = 1
        pfd.dwFlags = 0x00000004 | 0x00000020 | 0x00000001
        pfd.iPixelType = 0
        pfd.cColorBits = 32
        pfd.cDepthBits = 24
        pfd.iLayerType = 0
        pf = gdi32.ChoosePixelFormat(hdc, ctypes.byref(pfd))
        if not pf or not gdi32.SetPixelFormat(hdc, pf, ctypes.byref(pfd)):
            raise RuntimeError('Windows no pudo configurar el formato OpenGL')

        hrc = opengl32.wglCreateContext(hdc)
        if not hrc or not opengl32.wglMakeCurrent(hdc, hrc):
            raise RuntimeError('No se pudo activar el contexto OpenGL 3D')

        GL_RENDERER, GL_VENDOR, GL_VERSION = 0x1F01, 0x1F00, 0x1F02
        opengl32.glGetString.restype = ctypes.c_char_p
        renderer = (opengl32.glGetString(GL_RENDERER) or b'').decode('utf-8', 'replace')
        vendor = (opengl32.glGetString(GL_VENDOR) or b'').decode('utf-8', 'replace')
        gl_version = (opengl32.glGetString(GL_VERSION) or b'').decode('utf-8', 'replace')
        if not renderer or 'GDI Generic' in renderer:
            return {
                'kind': 'HARDWARE_VISUAL', 'value': None, 'unit': 'FPS', 'provider': 'CorePulse OpenGL 3D',
                'duration_s': 0.0, 'timestamp': time.time(), 'status': 'UNAVAILABLE',
                'reason': 'No hay aceleración OpenGL de hardware disponible',
                'renderer': renderer or 'N/A', 'vendor': vendor or 'N/A', 'gl_version': gl_version or 'N/A',
            }

        # Intentar desactivar VSync para medir capacidad del render y registrar
        # explícitamente si el driver confirmó el cambio.
        vsync_disabled = None
        try:
            swap_addr = opengl32.wglGetProcAddress(b'wglSwapIntervalEXT')
            if _valid_wgl_proc_address(swap_addr):
                swap_interval = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_int)(swap_addr)
                vsync_disabled = bool(swap_interval(0))
        except Exception:
            vsync_disabled = None

        # Firmas OpenGL usadas por las cuatro fases reales.
        opengl32.glViewport.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]
        opengl32.glClearColor.argtypes = [ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float]
        opengl32.glClear.argtypes = [ctypes.c_uint]
        opengl32.glEnable.argtypes = [ctypes.c_uint]
        opengl32.glDisable.argtypes = [ctypes.c_uint]
        opengl32.glEnableClientState.argtypes = [ctypes.c_uint]
        opengl32.glDisableClientState.argtypes = [ctypes.c_uint]
        opengl32.glVertexPointer.argtypes = [ctypes.c_int, ctypes.c_uint, ctypes.c_int, ctypes.c_void_p]
        opengl32.glColorPointer.argtypes = [ctypes.c_int, ctypes.c_uint, ctypes.c_int, ctypes.c_void_p]
        opengl32.glTexCoordPointer.argtypes = [ctypes.c_int, ctypes.c_uint, ctypes.c_int, ctypes.c_void_p]
        opengl32.glDrawArrays.argtypes = [ctypes.c_uint, ctypes.c_int, ctypes.c_int]
        opengl32.glMatrixMode.argtypes = [ctypes.c_uint]
        opengl32.glLoadIdentity.argtypes = []
        opengl32.glFrustum.argtypes = [ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double]
        opengl32.glOrtho.argtypes = [ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double]
        opengl32.glTranslatef.argtypes = [ctypes.c_float, ctypes.c_float, ctypes.c_float]
        opengl32.glRotatef.argtypes = [ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float]
        opengl32.glScalef.argtypes = [ctypes.c_float, ctypes.c_float, ctypes.c_float]
        opengl32.glPushMatrix.argtypes = []
        opengl32.glPopMatrix.argtypes = []
        opengl32.glColor4f.argtypes = [ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float]
        opengl32.glBlendFunc.argtypes = [ctypes.c_uint, ctypes.c_uint]
        opengl32.glGenTextures.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_uint)]
        opengl32.glDeleteTextures.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_uint)]
        opengl32.glBindTexture.argtypes = [ctypes.c_uint, ctypes.c_uint]
        opengl32.glTexParameteri.argtypes = [ctypes.c_uint, ctypes.c_uint, ctypes.c_int]
        opengl32.glTexImage2D.argtypes = [ctypes.c_uint, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p]
        opengl32.glGetIntegerv.argtypes = [ctypes.c_uint, ctypes.POINTER(ctypes.c_int)]
        opengl32.glGetError.restype = ctypes.c_uint
        opengl32.glFinish.argtypes = []

        GL_COLOR_BUFFER_BIT = 0x00004000
        GL_DEPTH_BUFFER_BIT = 0x00000100
        GL_DEPTH_TEST = 0x0B71
        GL_CULL_FACE = 0x0B44
        GL_BLEND = 0x0BE2
        GL_SRC_ALPHA = 0x0302
        GL_ONE_MINUS_SRC_ALPHA = 0x0303
        GL_VERTEX_ARRAY = 0x8074
        GL_COLOR_ARRAY = 0x8076
        GL_TEXTURE_COORD_ARRAY = 0x8078
        GL_FLOAT = 0x1406
        GL_UNSIGNED_BYTE = 0x1401
        GL_TRIANGLES = 0x0004
        GL_PROJECTION = 0x1701
        GL_MODELVIEW = 0x1700
        GL_TEXTURE_2D = 0x0DE1
        GL_RGBA = 0x1908
        GL_LINEAR = 0x2601
        GL_TEXTURE_MIN_FILTER = 0x2801
        GL_TEXTURE_MAG_FILTER = 0x2800
        GL_TEXTURE_WRAP_S = 0x2802
        GL_TEXTURE_WRAP_T = 0x2803
        GL_REPEAT = 0x2901
        GL_MAX_TEXTURE_SIZE = 0x0D33
        GL_NO_ERROR = 0
        GL_QUADS = 0x0007
        GL_VERTEX_SHADER = 0x8B31
        GL_FRAGMENT_SHADER = 0x8B30
        GL_COMPUTE_SHADER = 0x91B9
        GL_COMPILE_STATUS = 0x8B81
        GL_SHADER_STORAGE_BUFFER = 0x90D2
        GL_DYNAMIC_COPY = 0x88EA
        GL_SHADER_STORAGE_BARRIER_BIT = 0x2000
        GL_LINK_STATUS = 0x8B82

        # OpenGL 2.x+ no exporta las funciones GLSL desde opengl32.dll en Windows;
        # se cargan desde el contexto activo mediante wglGetProcAddress. Si no
        # existen, la fase Shaders queda N/A sin inventar una carga sustituta.
        def load_wgl(name, restype, *argtypes):
            try:
                addr = opengl32.wglGetProcAddress(name.encode('ascii'))
            except Exception:
                return None
            if not _valid_wgl_proc_address(addr):
                return None
            try:
                return ctypes.WINFUNCTYPE(restype, *argtypes)(addr)
            except Exception:
                return None

        shader_functions = {
            'create_shader': load_wgl('glCreateShader', ctypes.c_uint, ctypes.c_uint),
            'shader_source': load_wgl('glShaderSource', None, ctypes.c_uint, ctypes.c_int, ctypes.POINTER(ctypes.c_char_p), ctypes.POINTER(ctypes.c_int)),
            'compile_shader': load_wgl('glCompileShader', None, ctypes.c_uint),
            'get_shader_iv': load_wgl('glGetShaderiv', None, ctypes.c_uint, ctypes.c_uint, ctypes.POINTER(ctypes.c_int)),
            'get_shader_log': load_wgl('glGetShaderInfoLog', None, ctypes.c_uint, ctypes.c_int, ctypes.POINTER(ctypes.c_int), ctypes.c_void_p),
            'create_program': load_wgl('glCreateProgram', ctypes.c_uint),
            'attach_shader': load_wgl('glAttachShader', None, ctypes.c_uint, ctypes.c_uint),
            'link_program': load_wgl('glLinkProgram', None, ctypes.c_uint),
            'get_program_iv': load_wgl('glGetProgramiv', None, ctypes.c_uint, ctypes.c_uint, ctypes.POINTER(ctypes.c_int)),
            'get_program_log': load_wgl('glGetProgramInfoLog', None, ctypes.c_uint, ctypes.c_int, ctypes.POINTER(ctypes.c_int), ctypes.c_void_p),
            'use_program': load_wgl('glUseProgram', None, ctypes.c_uint),
            'delete_shader': load_wgl('glDeleteShader', None, ctypes.c_uint),
            'delete_program': load_wgl('glDeleteProgram', None, ctypes.c_uint),
            'get_uniform_location': load_wgl('glGetUniformLocation', ctypes.c_int, ctypes.c_uint, ctypes.c_char_p),
            'uniform1f': load_wgl('glUniform1f', None, ctypes.c_int, ctypes.c_float),
            'uniform2f': load_wgl('glUniform2f', None, ctypes.c_int, ctypes.c_float, ctypes.c_float),
        }

        required_shader_functions = (
            'create_shader', 'shader_source', 'compile_shader', 'get_shader_iv',
            'create_program', 'attach_shader', 'link_program', 'get_program_iv',
            'use_program', 'delete_shader', 'delete_program', 'get_uniform_location',
            'uniform1f', 'uniform2f',
        )

        def shader_log(shader, program=False):
            getter = shader_functions.get('get_program_log' if program else 'get_shader_log')
            if getter is None:
                return ''
            buf = ctypes.create_string_buffer(2048)
            length = ctypes.c_int(0)
            try:
                getter(int(shader), len(buf), ctypes.byref(length), ctypes.cast(buf, ctypes.c_void_p))
                return buf.value.decode('utf-8', 'replace').strip()
            except Exception:
                return ''

        def compile_shader_program():
            if not all(shader_functions.get(name) is not None for name in required_shader_functions):
                return None, 'El driver no expone las funciones GLSL requeridas'
            vertex_source = b'''#version 120
varying vec2 v_uv;
void main() {
    gl_Position = gl_Vertex;
    v_uv = gl_Vertex.xy * 0.5 + 0.5;
}
'''
            fragment_source = b'''#version 120
uniform float u_time;
uniform float u_alpha;
uniform vec2 u_resolution;
varying vec2 v_uv;
void main() {
    vec2 p = v_uv * 2.0 - 1.0;
    p.x *= u_resolution.x / max(1.0, u_resolution.y);
    vec2 q = p;
    float acc = 0.0;
    for (int i = 0; i < 40; ++i) {
        float fi = float(i) + 1.0;
        q = vec2(q.y, -q.x) * 0.987 + p * (0.018 + fi * 0.00035);
        acc += sin(q.x * (2.1 + fi * 0.075) + u_time * 0.95 + fi * 0.37)
             * cos(q.y * (2.4 + fi * 0.055) - u_time * 0.72) / (1.0 + fi * 0.045);
    }
    float n = 0.5 + 0.5 * sin(acc * 2.25 + u_time * 0.8);
    vec3 c = vec3(0.05 + 0.20 * n, 0.28 + 0.70 * n, 0.82 - 0.38 * n);
    gl_FragColor = vec4(c, u_alpha);
}
'''

            created = []
            try:
                for shader_type, source in ((GL_VERTEX_SHADER, vertex_source), (GL_FRAGMENT_SHADER, fragment_source)):
                    shader = int(shader_functions['create_shader'](shader_type) or 0)
                    if not shader:
                        raise RuntimeError('glCreateShader devolvió 0')
                    created.append(shader)
                    source_ptr = ctypes.c_char_p(source)
                    source_len = ctypes.c_int(len(source))
                    shader_functions['shader_source'](shader, 1, ctypes.byref(source_ptr), ctypes.byref(source_len))
                    shader_functions['compile_shader'](shader)
                    ok = ctypes.c_int(0)
                    shader_functions['get_shader_iv'](shader, GL_COMPILE_STATUS, ctypes.byref(ok))
                    if not ok.value:
                        raise RuntimeError(shader_log(shader) or 'falló la compilación GLSL')
                program = int(shader_functions['create_program']() or 0)
                if not program:
                    raise RuntimeError('glCreateProgram devolvió 0')
                for shader in created:
                    shader_functions['attach_shader'](program, shader)
                shader_functions['link_program'](program)
                linked = ctypes.c_int(0)
                shader_functions['get_program_iv'](program, GL_LINK_STATUS, ctypes.byref(linked))
                if not linked.value:
                    detail = shader_log(program, program=True) or 'falló el enlace GLSL'
                    shader_functions['delete_program'](program)
                    raise RuntimeError(detail)
                return program, None
            except Exception as exc:
                return None, str(exc)
            finally:
                for shader in created:
                    try:
                        shader_functions['delete_shader'](shader)
                    except Exception:
                        pass

        shader_program, shader_unavailable_reason = compile_shader_program()

        # Compute shader real (OpenGL 4.3+). Si el contexto/driver no expone
        # estas funciones, la fase queda N/A; no se reemplaza por una simulación.
        compute_functions = {
            'gen_buffers': load_wgl('glGenBuffers', None, ctypes.c_int, ctypes.POINTER(ctypes.c_uint)),
            'bind_buffer': load_wgl('glBindBuffer', None, ctypes.c_uint, ctypes.c_uint),
            'buffer_data': load_wgl('glBufferData', None, ctypes.c_uint, ctypes.c_ssize_t, ctypes.c_void_p, ctypes.c_uint),
            'bind_buffer_base': load_wgl('glBindBufferBase', None, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint),
            'dispatch_compute': load_wgl('glDispatchCompute', None, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint),
            'memory_barrier': load_wgl('glMemoryBarrier', None, ctypes.c_uint),
            'delete_buffers': load_wgl('glDeleteBuffers', None, ctypes.c_int, ctypes.POINTER(ctypes.c_uint)),
        }

        def compile_compute_program():
            required = (
                'create_shader', 'shader_source', 'compile_shader', 'get_shader_iv',
                'create_program', 'attach_shader', 'link_program', 'get_program_iv',
                'use_program', 'delete_shader', 'delete_program',
            )
            required_compute = (
                'gen_buffers', 'bind_buffer', 'buffer_data', 'bind_buffer_base',
                'dispatch_compute', 'memory_barrier', 'delete_buffers',
            )
            if not all(shader_functions.get(name) is not None for name in required):
                return None, 'El driver no expone las funciones GLSL necesarias para compute'
            if not all(compute_functions.get(name) is not None for name in required_compute):
                return None, 'OpenGL Compute Shader / SSBO no está disponible en el contexto activo'
            source = b'''#version 430
layout(local_size_x = 256) in;
layout(std430, binding = 0) buffer Data { float values[]; };
void main() {
    uint id = gl_GlobalInvocationID.x;
    if (id >= values.length()) return;
    float x = float(id) * 0.000013 + 0.137;
    float y = x * 1.6180339 + 0.37;
    for (int i = 0; i < 64; ++i) {
        float fi = float(i) + 1.0;
        x = sin(x * 1.0017 + fi * 0.013) + cos(y * 0.9971 - fi * 0.009);
        y = sqrt(abs(x * y) + 1.0001) * 0.731 + x * 0.193;
    }
    values[id] = x + y;
}
'''
            shader = 0
            program = 0
            try:
                shader = int(shader_functions['create_shader'](GL_COMPUTE_SHADER) or 0)
                if not shader:
                    raise RuntimeError('glCreateShader(GL_COMPUTE_SHADER) devolvió 0')
                source_ptr = ctypes.c_char_p(source)
                source_len = ctypes.c_int(len(source))
                shader_functions['shader_source'](shader, 1, ctypes.byref(source_ptr), ctypes.byref(source_len))
                shader_functions['compile_shader'](shader)
                ok = ctypes.c_int(0)
                shader_functions['get_shader_iv'](shader, GL_COMPILE_STATUS, ctypes.byref(ok))
                if not ok.value:
                    raise RuntimeError(shader_log(shader) or 'falló la compilación del compute shader')
                program = int(shader_functions['create_program']() or 0)
                if not program:
                    raise RuntimeError('glCreateProgram devolvió 0 para compute')
                shader_functions['attach_shader'](program, shader)
                shader_functions['link_program'](program)
                linked = ctypes.c_int(0)
                shader_functions['get_program_iv'](program, GL_LINK_STATUS, ctypes.byref(linked))
                if not linked.value:
                    detail = shader_log(program, program=True) or 'falló el enlace del compute shader'
                    shader_functions['delete_program'](program)
                    program = 0
                    raise RuntimeError(detail)
                return program, None
            except Exception as exc:
                return None, str(exc)
            finally:
                if shader:
                    try:
                        shader_functions['delete_shader'](shader)
                    except Exception:
                        pass

        compute_program, compute_unavailable_reason = compile_compute_program()
        if compute_program:
            try:
                compute_buffer_mb = max(1, int(profile_data.get('compute_buffer_mb') or 1))
                compute_buffer_bytes = int(compute_buffer_mb * 1024 * 1024)
                compute_functions['gen_buffers'](1, ctypes.byref(compute_buffer))
                if not int(compute_buffer.value):
                    raise RuntimeError('glGenBuffers no creó el SSBO de compute')
                compute_functions['bind_buffer'](GL_SHADER_STORAGE_BUFFER, int(compute_buffer.value))
                compute_functions['buffer_data'](GL_SHADER_STORAGE_BUFFER, compute_buffer_bytes, None, GL_DYNAMIC_COPY)
                compute_functions['bind_buffer_base'](GL_SHADER_STORAGE_BUFFER, 0, int(compute_buffer.value))
                compute_functions['bind_buffer'](GL_SHADER_STORAGE_BUFFER, 0)
                element_count = max(1, compute_buffer_bytes // 4)
                compute_groups_x = max(1, int(math.ceil(element_count / 256.0)))
            except Exception as exc:
                compute_unavailable_reason = str(exc)
                if int(compute_buffer.value) and compute_functions.get('delete_buffers') is not None:
                    try:
                        compute_functions['delete_buffers'](1, ctypes.byref(compute_buffer))
                    except Exception:
                        pass
                compute_buffer = ctypes.c_uint(0)
                if compute_program and shader_functions.get('delete_program') is not None:
                    try:
                        shader_functions['delete_program'](int(compute_program))
                    except Exception:
                        pass
                compute_program = None

        # Funciones OpenGL 1.1 para el HUD vectorial. El HUD forma parte del
        # mismo frame presentado y muestra FPS derivados sólo de frametimes reales.
        opengl32.glBegin.argtypes = [ctypes.c_uint]
        opengl32.glEnd.argtypes = []
        opengl32.glVertex2f.argtypes = [ctypes.c_float, ctypes.c_float]
        opengl32.glGenLists.argtypes = [ctypes.c_int]
        opengl32.glGenLists.restype = ctypes.c_uint
        opengl32.glNewList.argtypes = [ctypes.c_uint, ctypes.c_uint]
        opengl32.glEndList.argtypes = []
        opengl32.glListBase.argtypes = [ctypes.c_uint]
        opengl32.glCallLists.argtypes = [ctypes.c_int, ctypes.c_uint, ctypes.c_void_p]
        opengl32.glDeleteLists.argtypes = [ctypes.c_uint, ctypes.c_int]

        vertices, colors, vertex_count = _build_wave_mesh(int(profile_data['grid']))
        vptr = ctypes.cast(vertices, ctypes.c_void_p)
        cptr = ctypes.cast(colors, ctypes.c_void_p)

        # Quad de pantalla para fill-rate y muestreo de texturas. Son dos
        # triángulos reales y se dibujan repetidamente para generar overdraw.
        quad_vertices = (ctypes.c_float * 18)(
            -1.18, -1.18, 0.0,  1.18, -1.18, 0.0,  1.18, 1.18, 0.0,
            -1.18, -1.18, 0.0,  1.18,  1.18, 0.0, -1.18, 1.18, 0.0,
        )
        quad_texcoords = (ctypes.c_float * 12)(
            0.0, 0.0, 4.0, 0.0, 4.0, 4.0,
            0.0, 0.0, 4.0, 4.0, 0.0, 4.0,
        )
        qvptr = ctypes.cast(quad_vertices, ctypes.c_void_p)
        qtptr = ctypes.cast(quad_texcoords, ctypes.c_void_p)

        client = RECT()
        if not user32.GetClientRect(hwnd, ctypes.byref(client)):
            raise RuntimeError('Windows no pudo confirmar el área de render del benchmark')
        client_width = max(1, int(client.right - client.left))
        client_height = max(1, int(client.bottom - client.top))
        opengl32.glViewport(0, 0, client_width, client_height)
        opengl32.glClearColor(ctypes.c_float(0.018), ctypes.c_float(0.035), ctypes.c_float(0.070), ctypes.c_float(1.0))
        # Publica inmediatamente un frame oscuro antes de reservar texturas/recursos.
        # Así Windows no muestra un rectángulo blanco mientras se prepara la GPU.
        opengl32.glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        gdi32.SwapBuffers(hdc)

        # Texturas procedurales: reservan y muestrean memoria gráfica real. No
        # se interpreta esta reserva como capacidad total de VRAM; sólo describe
        # la carga solicitada por esta fase.
        max_texture_size = ctypes.c_int(0)
        opengl32.glGetIntegerv(GL_MAX_TEXTURE_SIZE, ctypes.byref(max_texture_size))
        requested_texture_size = int(profile_data.get('texture_size') or 1024)
        texture_size = max(256, min(requested_texture_size, int(max_texture_size.value or requested_texture_size)))
        requested_texture_count = max(1, int(profile_data.get('texture_count') or 1))
        texture_ids = (ctypes.c_uint * requested_texture_count)()
        opengl32.glGenTextures(requested_texture_count, texture_ids)
        texture_bytes_count = texture_size * texture_size * 4
        pattern = bytes(range(256))
        texture_bytes = (pattern * ((texture_bytes_count + len(pattern) - 1) // len(pattern)))[:texture_bytes_count]
        texture_buffer = ctypes.create_string_buffer(texture_bytes)
        for index in range(requested_texture_count):
            # Limpia errores anteriores para atribuir correctamente cualquier
            # fallo a la carga de esta textura concreta.
            for _ in range(8):
                if opengl32.glGetError() == GL_NO_ERROR:
                    break
            opengl32.glBindTexture(GL_TEXTURE_2D, texture_ids[index])
            opengl32.glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
            opengl32.glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
            opengl32.glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
            opengl32.glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
            opengl32.glTexImage2D(
                GL_TEXTURE_2D, 0, GL_RGBA, texture_size, texture_size, 0,
                GL_RGBA, GL_UNSIGNED_BYTE, ctypes.cast(texture_buffer, ctypes.c_void_p),
            )
            if opengl32.glGetError() != GL_NO_ERROR:
                break
            texture_count_actual += 1
        opengl32.glBindTexture(GL_TEXTURE_2D, 0)
        if texture_count_actual <= 0:
            raise RuntimeError('La GPU no pudo crear las texturas necesarias para la fase Texturas / VRAM')

        texture_requested_mb = (texture_size * texture_size * 4 * texture_count_actual) / (1024.0 * 1024.0)
        fill_passes = max(1, int(profile_data.get('fill_passes') or 1))
        texture_passes = max(1, int(profile_data.get('texture_passes') or 1))
        combined_texture_passes = max(1, int(profile_data.get('combined_texture_passes') or 1))
        shader_passes = max(1, int(profile_data.get('shader_passes') or 1))
        combined_shader_passes = max(1, int(profile_data.get('combined_shader_passes') or 1))
        compute_passes = max(1, int(profile_data.get('compute_passes') or 1))
        combined_compute_passes = max(1, int(profile_data.get('combined_compute_passes') or 1))

        cpu_hash_block_bytes = max(256 * 1024, int(profile_data.get('cpu_hash_block_kb') or 1024) * 1024)
        cpu_worker_count = max(1, min(int(profile_data.get('cpu_worker_cap') or 32), int(os.cpu_count() or 1)))
        ram_target_mb = max(16, int(profile_data.get('ram_buffer_mb') or 128))
        ram_worker_count = max(1, min(int(profile_data.get('ram_workers') or 4), int(os.cpu_count() or 1)))

        def start_cpu_load():
            nonlocal cpu_unavailable_reason
            if cpu_load_state.get('threads'):
                return True
            try:
                pattern = bytes(range(256))
                repeats = (cpu_hash_block_bytes + len(pattern) - 1) // len(pattern)
                payload = (pattern * repeats)[:cpu_hash_block_bytes]
                stop_evt = threading.Event()
                counts = [0] * cpu_worker_count

                def worker(index):
                    local = 0
                    while not stop_evt.is_set():
                        # hashlib ejecuta SHA-256 en código nativo; con bloques >2 KiB
                        # libera el GIL, por lo que los hilos pueden cargar varios cores.
                        hashlib.sha256(payload).digest()
                        local += 1
                        counts[index] = local

                threads = []
                for index in range(cpu_worker_count):
                    thread = threading.Thread(target=worker, args=(index,), name=f'CorePulseCPUPhase-{index}', daemon=True)
                    thread.start()
                    threads.append(thread)
                cpu_load_state.update({'threads': threads, 'stop': stop_evt, 'counts': counts, 'payload': payload, 'start': time.perf_counter()})
                cpu_unavailable_reason = None
                return True
            except Exception as exc:
                cpu_unavailable_reason = f'No se pudo iniciar la carga CPU multinúcleo: {exc}'
                return False

        def stop_cpu_load():
            nonlocal cpu_phase_metrics
            threads = list(cpu_load_state.get('threads') or [])
            if not threads:
                return cpu_phase_metrics
            stop_evt = cpu_load_state.get('stop')
            started = cpu_load_state.get('start')
            if stop_evt is not None:
                stop_evt.set()
            for thread in threads:
                try:
                    thread.join(timeout=2.0)
                except Exception:
                    pass
            ended = time.perf_counter()
            elapsed = max(1e-6, ended - float(started or ended))
            counts = list(cpu_load_state.get('counts') or [])
            operations = int(sum(int(v or 0) for v in counts))
            payload = cpu_load_state.get('payload') or b''
            bytes_processed = operations * len(payload)
            cpu_phase_metrics = {
                'valid': bool(operations > 0 and bytes_processed > 0),
                'workers': len(threads),
                'logical_processors': int(os.cpu_count() or 1),
                'block_kb': len(payload) / 1024.0 if payload else 0.0,
                'hashes_per_s': operations / elapsed if operations > 0 else None,
                'sha256_mb_s': bytes_processed / (1024.0 * 1024.0) / elapsed if bytes_processed > 0 else None,
                'duration_s': elapsed,
                'operations': operations,
            }
            cpu_load_state.update({'threads': [], 'stop': None, 'counts': [], 'payload': None, 'start': None})
            return cpu_phase_metrics

        def start_ram_load():
            nonlocal ram_unavailable_reason
            if ram_load_state.get('threads'):
                return True
            try:
                # Se degrada sólo la cantidad de memoria reservada si el equipo no
                # puede asignar el objetivo; nunca se inventa throughput.
                candidates = []
                for candidate in (ram_target_mb, 96, 64, 48, 32, 16):
                    candidate = int(candidate)
                    if candidate > 0 and candidate not in candidates and candidate <= ram_target_mb:
                        candidates.append(candidate)
                src = dst = None
                actual_mb = 0
                for candidate in candidates:
                    try:
                        size = candidate * 1024 * 1024
                        src = ctypes.create_string_buffer(size)
                        dst = ctypes.create_string_buffer(size)
                        actual_mb = candidate
                        break
                    except (MemoryError, OSError):
                        src = dst = None
                if src is None or dst is None or actual_mb <= 0:
                    raise MemoryError('no fue posible reservar un bloque de RAM seguro para la prueba')

                total_bytes = actual_mb * 1024 * 1024
                src_addr = ctypes.addressof(src)
                dst_addr = ctypes.addressof(dst)
                ctypes.memset(src_addr, 0xA5, total_bytes)
                ctypes.memset(dst_addr, 0x00, total_bytes)

                msvcrt = ctypes.CDLL('msvcrt')
                memcpy = msvcrt.memcpy
                memcpy.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
                memcpy.restype = ctypes.c_void_p
                workers = max(1, min(ram_worker_count, total_bytes // (4 * 1024 * 1024) or 1))
                stop_evt = threading.Event()
                counters = [0] * workers
                chunk = total_bytes // workers

                def worker(index):
                    start = index * chunk
                    length = chunk if index < workers - 1 else total_bytes - start
                    local = 0
                    src_ptr = src_addr + start
                    dst_ptr = dst_addr + start
                    while not stop_evt.is_set():
                        memcpy(dst_ptr, src_ptr, length)
                        local += length
                        counters[index] = local

                threads = []
                for index in range(workers):
                    thread = threading.Thread(target=worker, args=(index,), name=f'CorePulseRAMPhase-{index}', daemon=True)
                    thread.start()
                    threads.append(thread)
                ram_load_state.update({
                    'threads': threads, 'stop': stop_evt, 'counts': counters,
                    'src': src, 'dst': dst, 'start': time.perf_counter(),
                    'bytes': total_bytes, 'workers': workers,
                })
                ram_unavailable_reason = None
                return True
            except Exception as exc:
                ram_unavailable_reason = f'No se pudo iniciar la carga de ancho de banda RAM: {exc}'
                return False

        def stop_ram_load():
            nonlocal ram_phase_metrics
            threads = list(ram_load_state.get('threads') or [])
            if not threads:
                return ram_phase_metrics
            stop_evt = ram_load_state.get('stop')
            started = ram_load_state.get('start')
            if stop_evt is not None:
                stop_evt.set()
            for thread in threads:
                try:
                    thread.join(timeout=2.0)
                except Exception:
                    pass
            ended = time.perf_counter()
            elapsed = max(1e-6, ended - float(started or ended))
            copied = int(sum(int(v or 0) for v in (ram_load_state.get('counts') or [])))
            bytes_per_buffer = int(ram_load_state.get('bytes') or 0)
            ram_phase_metrics = {
                'valid': bool(copied > 0),
                'workers': int(ram_load_state.get('workers') or len(threads)),
                'buffer_mb_each': bytes_per_buffer / (1024.0 * 1024.0) if bytes_per_buffer else 0.0,
                'working_set_mb': (bytes_per_buffer * 2) / (1024.0 * 1024.0) if bytes_per_buffer else 0.0,
                'copy_gb_s': copied / (1024.0 ** 3) / elapsed if copied > 0 else None,
                'bytes_copied': copied,
                'duration_s': elapsed,
                'metric_definition': 'bytes copied / second',
            }
            ram_load_state.update({'threads': [], 'stop': None, 'counts': [], 'src': None, 'dst': None, 'start': None, 'bytes': 0, 'workers': 0})
            return ram_phase_metrics

        opengl32.glEnableClientState(GL_VERTEX_ARRAY)
        opengl32.glEnableClientState(GL_COLOR_ARRAY)

        def set_perspective():
            opengl32.glMatrixMode(GL_PROJECTION)
            opengl32.glLoadIdentity()
            aspect = client_width / max(1.0, float(client_height))
            opengl32.glFrustum(-aspect, aspect, -1.0, 1.0, 1.5, 120.0)
            opengl32.glMatrixMode(GL_MODELVIEW)

        def set_screen_space():
            opengl32.glMatrixMode(GL_PROJECTION)
            opengl32.glLoadIdentity()
            opengl32.glOrtho(-1.0, 1.0, -1.0, 1.0, -1.0, 1.0)
            opengl32.glMatrixMode(GL_MODELVIEW)
            opengl32.glLoadIdentity()

        def draw_geometry(elapsed, layer_count=None):
            layer_count = max(1, int(layer_count if layer_count is not None else layers))
            opengl32.glDisable(GL_BLEND)
            opengl32.glDisable(GL_TEXTURE_2D)
            opengl32.glDisableClientState(GL_TEXTURE_COORD_ARRAY)
            opengl32.glEnable(GL_DEPTH_TEST)
            opengl32.glEnable(GL_CULL_FACE)
            opengl32.glEnableClientState(GL_COLOR_ARRAY)
            opengl32.glVertexPointer(3, GL_FLOAT, 0, vptr)
            opengl32.glColorPointer(3, GL_FLOAT, 0, cptr)
            set_perspective()
            opengl32.glLoadIdentity()
            opengl32.glTranslatef(ctypes.c_float(0.0), ctypes.c_float(-0.45), ctypes.c_float(-16.5))
            opengl32.glRotatef(ctypes.c_float(18.0 + math.sin(elapsed * 0.31) * 6.0), ctypes.c_float(1.0), ctypes.c_float(0.0), ctypes.c_float(0.0))
            opengl32.glRotatef(ctypes.c_float(elapsed * 13.0), ctypes.c_float(0.0), ctypes.c_float(1.0), ctypes.c_float(0.0))
            for layer in range(layer_count):
                angle = (360.0 / max(1, layer_count)) * layer
                depth = -2.5 - (layer % 8) * 0.52
                scale = 0.34 + (layer % 7) * 0.018
                opengl32.glPushMatrix()
                opengl32.glRotatef(ctypes.c_float(angle + elapsed * (3.0 + (layer % 4))), ctypes.c_float(0.0), ctypes.c_float(1.0), ctypes.c_float(0.0))
                opengl32.glTranslatef(ctypes.c_float(0.0), ctypes.c_float(math.sin(elapsed * 0.8 + layer) * 0.45), ctypes.c_float(depth))
                opengl32.glRotatef(ctypes.c_float(52.0 + layer * 2.7), ctypes.c_float(1.0), ctypes.c_float(0.35), ctypes.c_float(0.15))
                opengl32.glScalef(ctypes.c_float(scale), ctypes.c_float(scale), ctypes.c_float(scale))
                opengl32.glDrawArrays(GL_TRIANGLES, 0, vertex_count)
                opengl32.glPopMatrix()

        def draw_fill(elapsed, passes=None):
            passes = max(1, int(passes if passes is not None else fill_passes))
            opengl32.glDisable(GL_DEPTH_TEST)
            opengl32.glDisable(GL_CULL_FACE)
            opengl32.glDisable(GL_TEXTURE_2D)
            opengl32.glDisableClientState(GL_TEXTURE_COORD_ARRAY)
            opengl32.glDisableClientState(GL_COLOR_ARRAY)
            opengl32.glEnable(GL_BLEND)
            opengl32.glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            opengl32.glVertexPointer(3, GL_FLOAT, 0, qvptr)
            set_screen_space()
            for layer in range(passes):
                opengl32.glPushMatrix()
                opengl32.glRotatef(ctypes.c_float((layer * 7.0 + elapsed * 19.0) % 360.0), ctypes.c_float(0.0), ctypes.c_float(0.0), ctypes.c_float(1.0))
                pulse = 0.82 + 0.16 * math.sin(elapsed * 1.3 + layer * 0.31)
                opengl32.glScalef(ctypes.c_float(pulse), ctypes.c_float(pulse), ctypes.c_float(1.0))
                r = 0.08 + (layer % 5) * 0.055
                g = 0.30 + (layer % 7) * 0.045
                b = 0.60 + (layer % 3) * 0.10
                opengl32.glColor4f(ctypes.c_float(r), ctypes.c_float(g), ctypes.c_float(min(1.0, b)), ctypes.c_float(0.16))
                opengl32.glDrawArrays(GL_TRIANGLES, 0, 6)
                opengl32.glPopMatrix()
            opengl32.glEnableClientState(GL_COLOR_ARRAY)

        def draw_textures(elapsed, passes=None, blended=False):
            passes = max(1, int(passes if passes is not None else texture_passes))
            opengl32.glDisable(GL_DEPTH_TEST)
            opengl32.glDisable(GL_CULL_FACE)
            opengl32.glDisableClientState(GL_COLOR_ARRAY)
            opengl32.glEnableClientState(GL_TEXTURE_COORD_ARRAY)
            opengl32.glEnable(GL_TEXTURE_2D)
            if blended:
                opengl32.glEnable(GL_BLEND)
                opengl32.glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
                alpha = 0.18
            else:
                opengl32.glDisable(GL_BLEND)
                alpha = 1.0
            opengl32.glVertexPointer(3, GL_FLOAT, 0, qvptr)
            opengl32.glTexCoordPointer(2, GL_FLOAT, 0, qtptr)
            set_screen_space()
            opengl32.glColor4f(ctypes.c_float(1.0), ctypes.c_float(1.0), ctypes.c_float(1.0), ctypes.c_float(alpha))
            for layer in range(passes):
                tex_id = texture_ids[layer % texture_count_actual]
                opengl32.glBindTexture(GL_TEXTURE_2D, tex_id)
                opengl32.glPushMatrix()
                opengl32.glRotatef(ctypes.c_float((elapsed * (5.0 + (layer % 5)) + layer * 11.0) % 360.0), ctypes.c_float(0.0), ctypes.c_float(0.0), ctypes.c_float(1.0))
                scale = 0.70 + (layer % 6) * 0.07
                opengl32.glScalef(ctypes.c_float(scale), ctypes.c_float(scale), ctypes.c_float(1.0))
                opengl32.glDrawArrays(GL_TRIANGLES, 0, 6)
                opengl32.glPopMatrix()
            opengl32.glBindTexture(GL_TEXTURE_2D, 0)
            opengl32.glDisable(GL_TEXTURE_2D)
            opengl32.glDisableClientState(GL_TEXTURE_COORD_ARRAY)
            opengl32.glEnableClientState(GL_COLOR_ARRAY)

        def draw_shader(elapsed, passes=None, blended=False):
            if not shader_program:
                return
            passes = max(1, int(passes if passes is not None else shader_passes))
            use_program = shader_functions.get('use_program')
            get_uniform = shader_functions.get('get_uniform_location')
            uniform1f = shader_functions.get('uniform1f')
            uniform2f = shader_functions.get('uniform2f')
            if not all((use_program, get_uniform, uniform1f, uniform2f)):
                return
            opengl32.glDisable(GL_DEPTH_TEST)
            opengl32.glDisable(GL_CULL_FACE)
            opengl32.glDisable(GL_TEXTURE_2D)
            opengl32.glDisableClientState(GL_TEXTURE_COORD_ARRAY)
            opengl32.glDisableClientState(GL_COLOR_ARRAY)
            opengl32.glEnableClientState(GL_VERTEX_ARRAY)
            opengl32.glVertexPointer(3, GL_FLOAT, 0, qvptr)
            if blended:
                opengl32.glEnable(GL_BLEND)
                opengl32.glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
                alpha = 0.18
            else:
                opengl32.glDisable(GL_BLEND)
                alpha = 1.0
            use_program(shader_program)
            time_loc = get_uniform(shader_program, b'u_time')
            alpha_loc = get_uniform(shader_program, b'u_alpha')
            res_loc = get_uniform(shader_program, b'u_resolution')
            if res_loc >= 0:
                uniform2f(res_loc, ctypes.c_float(client_width), ctypes.c_float(client_height))
            if alpha_loc >= 0:
                uniform1f(alpha_loc, ctypes.c_float(alpha))
            for layer in range(passes):
                if time_loc >= 0:
                    uniform1f(time_loc, ctypes.c_float(elapsed + layer * 0.137))
                opengl32.glDrawArrays(GL_TRIANGLES, 0, 6)
            use_program(0)
            opengl32.glEnableClientState(GL_COLOR_ARRAY)

        HUD_GLYPHS = {
            '0': ('11111','10001','10011','10101','11001','10001','11111'),
            '1': ('00100','01100','00100','00100','00100','00100','01110'),
            '2': ('11110','00001','00001','11110','10000','10000','11111'),
            '3': ('11110','00001','00001','01110','00001','00001','11110'),
            '4': ('10010','10010','10010','11111','00010','00010','00010'),
            '5': ('11111','10000','10000','11110','00001','00001','11110'),
            '6': ('01111','10000','10000','11110','10001','10001','01110'),
            '7': ('11111','00001','00010','00100','01000','01000','01000'),
            '8': ('01110','10001','10001','01110','10001','10001','01110'),
            '9': ('01110','10001','10001','01111','00001','00001','11110'),
            'F': ('11111','10000','10000','11110','10000','10000','10000'),
            'P': ('11110','10001','10001','11110','10000','10000','10000'),
            'S': ('01111','10000','10000','01110','00001','00001','11110'),
            '.': ('00000','00000','00000','00000','00000','00110','00110'),
            '-': ('00000','00000','00000','11111','00000','00000','00000'),
            '/': ('00001','00010','00010','00100','01000','01000','10000'),
            ' ': ('00000','00000','00000','00000','00000','00000','00000'),
        }

        GL_COMPILE = 0x1300
        hud_list_base = int(opengl32.glGenLists(128) or 0)
        if hud_list_base:
            # Los glVertex2f se ejecutan una sola vez al compilar las listas.
            # Durante el benchmark el texto completo requiere un solo glCallLists,
            # evitando que el HUD distorsione fases de cientos de FPS.
            for code in range(32, 127):
                char = chr(code)
                glyph = HUD_GLYPHS.get(char.upper(), HUD_GLYPHS[' '])
                opengl32.glNewList(hud_list_base + code, GL_COMPILE)
                opengl32.glBegin(GL_QUADS)
                for row, bits in enumerate(glyph):
                    for col, bit in enumerate(bits):
                        if bit != '1':
                            continue
                        x0 = float(col)
                        y0 = float(-row)
                        x1 = x0 + 0.82
                        y1 = y0 - 0.82
                        opengl32.glVertex2f(ctypes.c_float(x0), ctypes.c_float(y0))
                        opengl32.glVertex2f(ctypes.c_float(x1), ctypes.c_float(y0))
                        opengl32.glVertex2f(ctypes.c_float(x1), ctypes.c_float(y1))
                        opengl32.glVertex2f(ctypes.c_float(x0), ctypes.c_float(y1))
                opengl32.glEnd()
                opengl32.glTranslatef(ctypes.c_float(6.0), ctypes.c_float(0.0), ctypes.c_float(0.0))
                opengl32.glEndList()

        def draw_hud_text(text_value, x, y, scale):
            if not hud_list_base:
                return
            raw = str(text_value).encode('ascii', 'replace')
            opengl32.glPushMatrix()
            opengl32.glTranslatef(ctypes.c_float(float(x)), ctypes.c_float(float(y)), ctypes.c_float(0.0))
            opengl32.glScalef(ctypes.c_float(float(scale)), ctypes.c_float(float(scale)), ctypes.c_float(1.0))
            opengl32.glListBase(hud_list_base)
            buf = ctypes.create_string_buffer(raw)
            opengl32.glCallLists(len(raw), GL_UNSIGNED_BYTE, ctypes.cast(buf, ctypes.c_void_p))
            opengl32.glPopMatrix()

        def dispatch_compute(passes=None):
            if not compute_program or not int(compute_buffer.value) or compute_groups_x <= 0:
                return False
            passes = max(1, int(passes if passes is not None else compute_passes))
            use_program = shader_functions.get('use_program')
            if use_program is None:
                return False
            use_program(int(compute_program))
            compute_functions['bind_buffer_base'](GL_SHADER_STORAGE_BUFFER, 0, int(compute_buffer.value))
            for _ in range(passes):
                compute_functions['dispatch_compute'](int(compute_groups_x), 1, 1)
            compute_functions['memory_barrier'](GL_SHADER_STORAGE_BARRIER_BIT)
            use_program(0)
            return True

        def draw_compute_visual(elapsed):
            # Fondo visual mínimo para que la fase siga siendo visible sin
            # convertirla en una segunda prueba de shaders/fill.
            draw_fill(elapsed, 1)

        def draw_cpu_visual(elapsed):
            """Visual ligero: un nodo por hilo mientras la carga real ocurre en CPU."""
            opengl32.glDisable(GL_DEPTH_TEST)
            opengl32.glDisable(GL_CULL_FACE)
            opengl32.glDisable(GL_TEXTURE_2D)
            opengl32.glDisableClientState(GL_TEXTURE_COORD_ARRAY)
            opengl32.glDisableClientState(GL_COLOR_ARRAY)
            opengl32.glEnableClientState(GL_VERTEX_ARRAY)
            opengl32.glDisable(GL_BLEND)
            opengl32.glVertexPointer(3, GL_FLOAT, 0, qvptr)
            set_screen_space()
            visible_workers = max(1, min(cpu_worker_count, 24))
            for index in range(visible_workers):
                angle = (math.tau / visible_workers) * index + elapsed * 0.45
                radius = 0.56 + 0.08 * math.sin(elapsed * 1.4 + index)
                x = math.cos(angle) * radius
                y = math.sin(angle) * radius
                pulse = 0.055 + 0.018 * (1.0 + math.sin(elapsed * 3.0 + index))
                opengl32.glPushMatrix()
                opengl32.glTranslatef(ctypes.c_float(x), ctypes.c_float(y), ctypes.c_float(0.0))
                opengl32.glRotatef(ctypes.c_float((elapsed * 80.0 + index * 11.0) % 360.0), ctypes.c_float(0.0), ctypes.c_float(0.0), ctypes.c_float(1.0))
                opengl32.glScalef(ctypes.c_float(pulse), ctypes.c_float(pulse), ctypes.c_float(1.0))
                opengl32.glColor4f(ctypes.c_float(0.10), ctypes.c_float(0.76), ctypes.c_float(1.0), ctypes.c_float(1.0))
                opengl32.glDrawArrays(GL_TRIANGLES, 0, 6)
                opengl32.glPopMatrix()
            # Núcleo central: el visual no es la carga, sólo representa los workers.
            opengl32.glPushMatrix()
            core_scale = 0.15 + 0.025 * math.sin(elapsed * 2.2)
            opengl32.glScalef(ctypes.c_float(core_scale), ctypes.c_float(core_scale), ctypes.c_float(1.0))
            opengl32.glColor4f(ctypes.c_float(0.66), ctypes.c_float(0.33), ctypes.c_float(0.97), ctypes.c_float(1.0))
            opengl32.glDrawArrays(GL_TRIANGLES, 0, 6)
            opengl32.glPopMatrix()
            opengl32.glEnableClientState(GL_COLOR_ARRAY)

        def draw_ram_visual(elapsed):
            """Visual ligero de carriles; la carga real es memcpy sobre RAM del sistema."""
            opengl32.glDisable(GL_DEPTH_TEST)
            opengl32.glDisable(GL_CULL_FACE)
            opengl32.glDisable(GL_TEXTURE_2D)
            opengl32.glDisableClientState(GL_TEXTURE_COORD_ARRAY)
            opengl32.glDisableClientState(GL_COLOR_ARRAY)
            opengl32.glEnableClientState(GL_VERTEX_ARRAY)
            opengl32.glDisable(GL_BLEND)
            opengl32.glVertexPointer(3, GL_FLOAT, 0, qvptr)
            set_screen_space()
            lanes = 14
            for index in range(lanes):
                y = -0.78 + (1.56 / max(1, lanes - 1)) * index
                direction = -1.0 if index % 2 else 1.0
                x = ((elapsed * (0.38 + index * 0.012) * direction + index * 0.13) % 2.4) - 1.2
                opengl32.glPushMatrix()
                opengl32.glTranslatef(ctypes.c_float(x), ctypes.c_float(y), ctypes.c_float(0.0))
                opengl32.glScalef(ctypes.c_float(0.24), ctypes.c_float(0.027), ctypes.c_float(1.0))
                opengl32.glColor4f(ctypes.c_float(0.12), ctypes.c_float(0.86), ctypes.c_float(0.60), ctypes.c_float(1.0))
                opengl32.glDrawArrays(GL_TRIANGLES, 0, 6)
                opengl32.glPopMatrix()
            opengl32.glEnableClientState(GL_COLOR_ARRAY)

        def draw_fps_overlay(fps_value, phase_index, phase_count):
            # HUD mínimo y constante para todas las fases. Se dibuja dentro del
            # mismo frame; no modifica ni inventa la medición del benchmark.
            if shader_functions.get('use_program') is not None:
                try:
                    shader_functions['use_program'](0)
                except Exception:
                    pass
            opengl32.glDisable(GL_DEPTH_TEST)
            opengl32.glDisable(GL_CULL_FACE)
            opengl32.glDisable(GL_TEXTURE_2D)
            opengl32.glDisableClientState(GL_TEXTURE_COORD_ARRAY)
            opengl32.glDisableClientState(GL_COLOR_ARRAY)
            opengl32.glDisableClientState(GL_VERTEX_ARRAY)
            opengl32.glEnable(GL_BLEND)
            opengl32.glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            opengl32.glMatrixMode(GL_PROJECTION)
            opengl32.glLoadIdentity()
            opengl32.glOrtho(0.0, float(client_width), 0.0, float(client_height), -1.0, 1.0)
            opengl32.glMatrixMode(GL_MODELVIEW)
            opengl32.glLoadIdentity()
            scale = max(2.0, min(4.0, client_width / 480.0))
            fps_text = 'FPS --' if fps_value is None else f'FPS {float(fps_value):.1f}'
            phase_text = f'{max(1, int(phase_index) + 1)}/{max(1, int(phase_count))}'
            fps_width = len(fps_text) * scale * 6.0
            margin = 18.0
            box_h = scale * 9.5
            box_w = fps_width + 24.0
            x0 = client_width - box_w - margin
            y_top = client_height - margin
            opengl32.glColor4f(ctypes.c_float(0.015), ctypes.c_float(0.035), ctypes.c_float(0.060), ctypes.c_float(0.78))
            opengl32.glBegin(GL_QUADS)
            for vx, vy in ((x0, y_top), (x0 + box_w, y_top), (x0 + box_w, y_top - box_h), (x0, y_top - box_h)):
                opengl32.glVertex2f(ctypes.c_float(vx), ctypes.c_float(vy))
            opengl32.glEnd()
            opengl32.glColor4f(ctypes.c_float(0.20), ctypes.c_float(0.82), ctypes.c_float(1.0), ctypes.c_float(1.0))
            draw_hud_text(fps_text, x0 + 12.0, y_top - scale * 1.6, scale)
            # Índice de fase en la esquina superior izquierda.
            left_w = len(phase_text) * scale * 6.0 + 24.0
            lx0 = margin
            opengl32.glColor4f(ctypes.c_float(0.015), ctypes.c_float(0.035), ctypes.c_float(0.060), ctypes.c_float(0.72))
            opengl32.glBegin(GL_QUADS)
            for vx, vy in ((lx0, y_top), (lx0 + left_w, y_top), (lx0 + left_w, y_top - box_h), (lx0, y_top - box_h)):
                opengl32.glVertex2f(ctypes.c_float(vx), ctypes.c_float(vy))
            opengl32.glEnd()
            opengl32.glColor4f(ctypes.c_float(0.66), ctypes.c_float(0.33), ctypes.c_float(0.97), ctypes.c_float(1.0))
            draw_hud_text(phase_text, lx0 + 12.0, y_top - scale * 1.6, scale)
            opengl32.glEnableClientState(GL_VERTEX_ARRAY)
            opengl32.glEnableClientState(GL_COLOR_ARRAY)

        canonical_phase_specs = (
            ('geometry', 'Geometría'),
            ('fill', 'Fill / fragmentos'),
            ('textures', 'Texturas / VRAM'),
            ('shaders', 'Shaders / ALU'),
            ('compute', 'Compute / GPGPU'),
            ('cpu', 'CPU / Multinúcleo'),
            ('ram', 'RAM / Ancho de banda'),
            ('combined', 'Carga combinada'),
        )
        gpu_phase_keys = {'geometry', 'fill', 'textures', 'shaders', 'compute', 'combined'}
        phase_specs = tuple(
            item for item in canonical_phase_specs
            if (
                (item[0] in gpu_phase_keys and 'gpu' in selected_components)
                or (item[0] == 'cpu' and 'cpu' in selected_components)
                or (item[0] == 'ram' and 'ram' in selected_components)
            )
            and (item[0] != 'shaders' or shader_program is not None)
            and (item[0] != 'compute' or (compute_program is not None and int(compute_buffer.value)))
        )
        if not phase_specs:
            raise RuntimeError('No hay áreas visuales seleccionadas para ejecutar')
        phase_count = len(phase_specs)
        phase_times = {key: [] for key, _ in canonical_phase_specs}
        phase_samples = {key: [] for key, _ in canonical_phase_specs}
        phase_duration_target = duration_target / float(max(1, phase_count))
        active_phase_key = None
        active_phase_index = -1

        _safe_progress(
            progress_callback, 0.0, 'Preparando benchmark 3D',
            f'{renderer} · {client_width}×{client_height} · {phase_count} fases reales'
        )
        run_start = time.perf_counter()
        measurement_start = None
        next_progress = run_start
        next_sample = run_start
        msg = MSG()
        recent_frames = []

        while True:
            now = time.perf_counter()
            if measurement_start is None and now - run_start >= warmup_seconds:
                measurement_start = now
                recent_frames.clear()
                first_label = phase_specs[0][1] if phase_specs else 'Geometría'
                _safe_progress(
                    progress_callback, 0.0,
                    f'Fase 1/{phase_count} · {first_label}',
                    'Warm-up completado · comenzando medición válida',
                )
            if measurement_start is not None and now - measurement_start >= duration_target:
                break
            if callable(cancel_check):
                try:
                    if cancel_check():
                        cancel_requested['value'] = True
                except Exception:
                    pass
            if cancel_requested['value'] or stop_reason:
                break

            while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0x0001):
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
                if cancel_requested['value']:
                    break
            if cancel_requested['value']:
                break

            frame_start = time.perf_counter()
            elapsed = frame_start - run_start
            measurement_elapsed = 0.0 if measurement_start is None else max(0.0, frame_start - measurement_start)
            if measurement_start is None:
                render_phase_key = 'warmup'
                render_phase_index = -1
            else:
                render_phase_index = min(phase_count - 1, int(measurement_elapsed / max(0.001, phase_duration_target)))
                render_phase_key = phase_specs[render_phase_index][0]
                if render_phase_key != active_phase_key:
                    # Los workers host se inician/detienen fuera del frame medido,
                    # evitando contaminar el primer frametime de la fase siguiente.
                    if active_phase_key == 'cpu':
                        stop_cpu_load()
                    elif active_phase_key == 'ram':
                        stop_ram_load()
                    if render_phase_key == 'cpu':
                        start_cpu_load()
                    elif render_phase_key == 'ram':
                        start_ram_load()
                    active_phase_key = render_phase_key
                    active_phase_index = render_phase_index
                    # El HUD de la nueva fase nunca hereda FPS de la anterior.
                    recent_frames.clear()
                    label = phase_specs[render_phase_index][1]
                    try:
                        user32.SetWindowTextW(hwnd, f'CorePulse Benchmark — Fase {render_phase_index + 1}/{phase_count} · {label}')
                    except Exception:
                        pass
                    _safe_progress(
                        progress_callback,
                        min(1.0, measurement_elapsed / max(0.001, duration_target)),
                        f'Fase {render_phase_index + 1}/{phase_count} · {label}',
                        'Midiendo carga gráfica real',
                    )

            opengl32.glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
            if render_phase_key == 'warmup':
                # Warm-up visual neutro: prepara geometría y shader sin mostrar
                # el patrón agresivo de texturas que se veía en la grabación.
                draw_geometry(elapsed, max(8, min(layers, 18)))
                if shader_program:
                    draw_shader(elapsed, 1, blended=True)
            elif render_phase_key == 'geometry':
                draw_geometry(elapsed, layers)
            elif render_phase_key == 'fill':
                draw_fill(elapsed, fill_passes)
            elif render_phase_key == 'textures':
                draw_textures(elapsed, texture_passes, blended=False)
            elif render_phase_key == 'shaders':
                draw_shader(elapsed, shader_passes, blended=False)
            elif render_phase_key == 'compute':
                draw_compute_visual(elapsed)
                dispatch_compute(compute_passes)
            elif render_phase_key == 'cpu':
                draw_cpu_visual(elapsed)
            elif render_phase_key == 'ram':
                draw_ram_visual(elapsed)
            else:
                draw_geometry(elapsed, layers)
                draw_textures(elapsed, combined_texture_passes, blended=True)
                if shader_program:
                    draw_shader(elapsed, combined_shader_passes, blended=True)
                if compute_program and int(compute_buffer.value):
                    dispatch_compute(combined_compute_passes)

            overlay_fps = None
            if measurement_start is not None and recent_frames:
                avg_recent_ms = sum(recent_frames) / len(recent_frames)
                overlay_fps = 1000.0 / avg_recent_ms if avg_recent_ms > 0 else None
            draw_fps_overlay(
                overlay_fps,
                active_phase_index if active_phase_index >= 0 else 0,
                phase_count,
            )

            if not gdi32.SwapBuffers(hdc):
                render_error = 'Windows informó un fallo al presentar el frame OpenGL'
                break
            opengl32.glFinish()
            frame_end = time.perf_counter()
            frame_ms = max(0.001, (frame_end - frame_start) * 1000.0)
            if measurement_start is not None:
                frame_times_ms.append(frame_ms)
                phase_times[render_phase_key].append(frame_ms)
                recent_frames.append(frame_ms)
                # Ventana corta real para el HUD; no altera los frametimes crudos.
                if len(recent_frames) > 45:
                    del recent_frames[:-45]
                frames += 1

            if frame_end >= next_sample and callable(telemetry_sampler):
                next_sample = frame_end + 0.45
                try:
                    raw_sample = telemetry_sampler() or {}
                    sample = _visual_telemetry_metrics(raw_sample, renderer)
                except Exception:
                    sample = {}
                if isinstance(sample, dict):
                    row = {
                        'ts': time.time(), 'phase': render_phase_key if measurement_start is not None else 'warmup',
                        'cpu_temp': sample.get('cpu_temp'), 'cpu_ghz': sample.get('cpu_ghz'),
                        'cpu_usage': sample.get('cpu_usage'), 'ram_usage': sample.get('ram_usage'),
                        'cpu_tjmax_distance': sample.get('cpu_tjmax_distance'),
                        'gpu_temp': sample.get('gpu_temp'), 'gpu_hotspot': sample.get('gpu_hotspot'),
                        'gpu_temp_limit': sample.get('gpu_temp_limit'),
                        'gpu_hotspot_limit': sample.get('gpu_hotspot_limit'),
                        'gpu_usage': sample.get('gpu_usage'),
                        'gpu_vram_used_mb': sample.get('gpu_vram_used_mb'),
                        'gpu_vram_usage_percent': sample.get('gpu_vram_usage_percent'),
                        'gpu_sensor_match': sample.get('gpu_sensor_match'),
                        'gpu_sensor_name': sample.get('gpu_sensor_name'),
                    }
                    samples.append(row)
                    if measurement_start is not None and render_phase_key in phase_samples:
                        phase_samples[render_phase_key].append(row)

                    # Seguridad universal basada en límites reales cuando existen.
                    # La antigua regla CPU >= 96 °C abortaba equipos cuyo TjMax real
                    # era superior (tal como ocurrió en la grabación enviada).
                    cpu_distance = _float(row.get('cpu_tjmax_distance'))
                    cpu_temp = _float(row.get('cpu_temp'))
                    if cpu_distance is not None:
                        cpu_safety_hits = cpu_safety_hits + 1 if cpu_distance <= 1.0 else 0
                        if cpu_safety_hits >= 2:
                            stop_reason = f'Seguridad térmica: CPU quedó a {cpu_distance:.1f} °C de su TjMax real'
                    elif cpu_temp is not None:
                        # Respaldo conservador sólo cuando el proveedor no expone TjMax.
                        cpu_safety_hits = cpu_safety_hits + 1 if cpu_temp >= 96.0 else 0
                        if cpu_safety_hits >= 2:
                            stop_reason = f'Seguridad térmica: CPU alcanzó {cpu_temp:.1f} °C sin TjMax disponible'
                    else:
                        cpu_safety_hits = 0

                    gpu_temp = _float(row.get('gpu_temp'))
                    gpu_hotspot = _float(row.get('gpu_hotspot'))
                    gpu_temp_limit = _float(row.get('gpu_temp_limit'))
                    gpu_hotspot_limit = _float(row.get('gpu_hotspot_limit'))
                    has_gpu_limit = gpu_temp_limit is not None or gpu_hotspot_limit is not None
                    gpu_at_limit = (
                        (gpu_temp is not None and gpu_temp_limit is not None and gpu_temp >= gpu_temp_limit)
                        or (gpu_hotspot is not None and gpu_hotspot_limit is not None and gpu_hotspot >= gpu_hotspot_limit)
                    )
                    if not has_gpu_limit and gpu_temp is not None:
                        gpu_at_limit = gpu_temp >= 92.0
                    gpu_safety_hits = gpu_safety_hits + 1 if gpu_at_limit else 0
                    if gpu_safety_hits >= 2 and not stop_reason:
                        if gpu_hotspot is not None and gpu_hotspot_limit is not None and gpu_hotspot >= gpu_hotspot_limit:
                            stop_reason = f'Seguridad térmica: GPU hotspot alcanzó su límite reportado ({gpu_hotspot:.1f}/{gpu_hotspot_limit:.1f} °C)'
                        elif gpu_temp is not None and gpu_temp_limit is not None:
                            stop_reason = f'Seguridad térmica: GPU alcanzó su límite reportado ({gpu_temp:.1f}/{gpu_temp_limit:.1f} °C)'
                        elif gpu_temp is not None:
                            stop_reason = f'Seguridad térmica: GPU alcanzó {gpu_temp:.1f} °C sin límite del proveedor disponible'

            if frame_end >= next_progress:
                next_progress = frame_end + 0.30
                if measurement_start is None:
                    warmup_fraction = 1.0 if warmup_seconds <= 0 else min(1.0, (frame_end - run_start) / warmup_seconds)
                    _safe_progress(
                        progress_callback, 0.0, 'Calentando pipeline 3D',
                        f'{profile_label} · warm-up {warmup_fraction * 100:.0f}% · no se contabiliza en el resultado',
                    )
                else:
                    current_fps = None
                    if recent_frames:
                        avg_recent_ms = sum(recent_frames) / len(recent_frames)
                        current_fps = 1000.0 / avg_recent_ms if avg_recent_ms > 0 else None
                    fraction = min(1.0, (frame_end - measurement_start) / max(0.001, duration_target))
                    label = phase_specs[active_phase_index][1] if active_phase_index >= 0 else phase_specs[0][1]
                    fps_text = f'{current_fps:.1f} FPS reales' if current_fps is not None else 'FPS preparando muestra'
                    _safe_progress(
                        progress_callback, fraction, f'Fase {active_phase_index + 1}/{phase_count} · {label}',
                        f'{profile_label} · {client_width}×{client_height} · {fps_text}',
                    )

        if active_phase_key == 'cpu':
            stop_cpu_load()
        elif active_phase_key == 'ram':
            stop_ram_load()
        measurement_end = time.perf_counter()
        duration = max(1e-6, (measurement_end - measurement_start) if measurement_start is not None else 0.0)
        phase_workloads = {
            'geometry': {
                'triangles_per_frame': triangle_count_per_mesh * layers,
                'mesh_triangles': triangle_count_per_mesh,
                'draw_calls_per_frame': layers,
            },
            'fill': {
                'fullscreen_passes_per_frame': fill_passes,
                'approx_fragment_samples_per_frame': client_width * client_height * fill_passes,
                'blending': True,
            },
            'textures': {
                'texture_size': f'{texture_size}x{texture_size}',
                'texture_count': texture_count_actual,
                'texture_allocation_requested_mb': texture_requested_mb,
                'texture_passes_per_frame': texture_passes,
            },
            'shaders': {
                'fullscreen_shader_passes_per_frame': shader_passes,
                'fragment_alu_iterations_per_pass': 40,
                'glsl_programmable': True,
            },
            'compute': {
                'ssbo_mb': compute_buffer_bytes / (1024.0 * 1024.0) if compute_buffer_bytes else 0,
                'work_groups_x_per_dispatch': compute_groups_x,
                'local_size_x': 256,
                'dispatches_per_frame': compute_passes,
                'alu_iterations_per_invocation': 64,
                'compute_shader_glsl': True,
            },
            'cpu': dict(cpu_phase_metrics),
            'ram': dict(ram_phase_metrics),
            'combined': {
                'triangles_per_frame': triangle_count_per_mesh * layers,
                'texture_passes_per_frame': combined_texture_passes,
                'shader_passes_per_frame': combined_shader_passes if shader_program else 0,
                'compute_dispatches_per_frame': combined_compute_passes if compute_program and int(compute_buffer.value) else 0,
                'texture_allocation_requested_mb': texture_requested_mb,
            },
        }
        phase_results = []
        # Sólo devolvemos fases que realmente pertenecieron a esta ejecución.
        # Antes se recorría el catálogo canónico completo y una ejecución sólo-GPU
        # terminaba arrastrando placeholders CPU/RAM N/A en la presentación.
        for key, label in phase_specs:
            row = _phase_result(key, label, phase_times[key], phase_samples[key], phase_workloads.get(key))
            if key == 'shaders' and shader_program is None:
                row['status'] = 'N/A'
                row['reason'] = shader_unavailable_reason or 'GLSL no disponible en el contexto OpenGL activo'
            if key == 'compute' and (compute_program is None or not int(compute_buffer.value)):
                row['status'] = 'N/A'
                row['reason'] = compute_unavailable_reason or 'Compute Shader / SSBO no disponible en el contexto OpenGL activo'
            if key == 'cpu' and not cpu_phase_metrics.get('valid'):
                row['status'] = 'N/A'
                row['reason'] = cpu_unavailable_reason or 'La carga CPU multinúcleo no produjo una medición válida'
            if key == 'ram' and not ram_phase_metrics.get('valid'):
                row['status'] = 'N/A'
                row['reason'] = ram_unavailable_reason or 'La carga de ancho de banda RAM no produjo una medición válida'
            phase_results.append(row)
        phase_by_key = {row['key']: row for row in phase_results}
        primary = phase_by_key.get('combined') or {}
        fps = primary.get('frames_per_s')
        one_low = primary.get('one_percent_low_fps')
        avg_ms = primary.get('frametime_avg_ms')
        p95_ms = primary.get('frametime_p95_ms')
        p99_ms = primary.get('frametime_p99_ms')
        triangles_per_frame = triangle_count_per_mesh * layers
        triangles_per_s = triangles_per_frame * fps if fps is not None else None

        status = 'OK'
        reason = None
        measured_phase_count = sum(1 for row in phase_results if row.get('status') == 'OK')
        if cancel_requested['value']:
            status = 'CANCELLED'
            reason = 'El usuario cerró la ventana del benchmark visual'
        elif render_error:
            status = 'ERROR'
            reason = render_error
        elif stop_reason:
            status = 'SAFETY_STOP'
            reason = stop_reason
        elif fps is None:
            status = 'ERROR'
            reason = 'La fase de carga combinada no obtuvo frametimes suficientes para un resultado principal válido'
        else:
            required_failures = [
                row for row in phase_results
                if row.get('key') in ('geometry', 'fill', 'textures', 'combined') and row.get('status') != 'OK'
            ]
            optional_failures = [
                row for row in phase_results
                if row.get('key') in ('shaders', 'compute', 'cpu', 'ram') and row.get('status') != 'OK'
            ]
            if required_failures:
                status = 'ERROR'
                reason = 'Una o más fases obligatorias no obtuvieron frametimes suficientes'
            elif optional_failures:
                status = 'PARTIAL'
                reason = ' · '.join(
                    f"{row.get('label') or row.get('key')} N/A: {row.get('reason') or 'no disponible'}"
                    for row in optional_failures
                )

        if status in ('CANCELLED', 'ERROR', 'SAFETY_STOP') and reason:
            final_detail = reason
        elif fps is not None:
            final_detail = f'Carga combinada: {fps:.1f} FPS promedio · {measured_phase_count}/{len(phase_specs)} fases medidas'
            if status == 'PARTIAL' and reason:
                final_detail += f' · {reason}'
        else:
            final_detail = 'Sin FPS evaluable'
        _safe_progress(progress_callback, 1.0, 'Benchmark por áreas finalizado', final_detail)
        return {
            'kind': 'HARDWARE_VISUAL_MULTI_PHASE',
            'benchmark_method': 'COREPULSE_GPU_VISUAL_MULTIPHASE_V2',
            'value': fps,
            'unit': 'FPS',
            'provider': 'CorePulse Visual Hardware Benchmark · Multi-phase',
            'duration_s': duration,
            'timestamp': time.time(),
            'status': status,
            'reason': reason,
            'renderer': renderer,
            'vendor': vendor,
            'gl_version': gl_version,
            'profile': profile_data['key'],
            'profile_label': profile_label,
            'selected_components': sorted(selected_components),
            'resolution': f'{client_width}x{client_height}',
            'requested_resolution': f'{width}x{height}',
            'warmup_s': warmup_seconds,
            'vsync_disabled': vsync_disabled,
            'measurement_quality': ('VALID_PARTIAL' if status == 'PARTIAL' else ('VALID' if vsync_disabled is True else 'VALID_VSYNC_UNCONFIRMED')),
            'phase_count': len(phase_results),
            'measured_phase_count': measured_phase_count,
            'shader_supported': shader_program is not None,
            'shader_unavailable_reason': shader_unavailable_reason,
            'compute_supported': compute_program is not None and bool(int(compute_buffer.value)),
            'compute_unavailable_reason': compute_unavailable_reason,
            'compute_buffer_mb': compute_buffer_bytes / (1024.0 * 1024.0) if compute_buffer_bytes else 0,
            'cpu_benchmark': dict(cpu_phase_metrics),
            'ram_benchmark': dict(ram_phase_metrics),
            'fps_hud': 'REAL_FRAME_TIMES_WINDOW_45',
            'thermal_safety_policy': 'REAL_LIMITS_ONLY',
            'phases': phase_results,
            'primary_phase': 'combined',
            'frames': frames,
            'frames_per_s': fps,
            'one_percent_low_fps': one_low,
            'frametime_avg_ms': avg_ms,
            'frametime_p95_ms': p95_ms,
            'frametime_p99_ms': p99_ms,
            'triangles_per_frame': triangles_per_frame,
            'triangles_per_s': triangles_per_s,
            'texture_allocation_requested_mb': texture_requested_mb,
            'telemetry': {
                **_telemetry_summary([row for row in samples if row.get('phase') != 'warmup']),
                'gpu_sensor_match': any(bool(row.get('gpu_sensor_match')) for row in samples if row.get('phase') != 'warmup'),
                'gpu_sensor_name': next((row.get('gpu_sensor_name') for row in samples if row.get('gpu_sensor_name')), None),
            },
        }
    finally:
        try:
            stop_cpu_load()
        except Exception:
            pass
        try:
            stop_ram_load()
        except Exception:
            pass
        try:
            if hud_list_base and hrc:
                opengl32.glDeleteLists(int(hud_list_base), 128)
        except Exception:
            pass
        try:
            if compute_program and hrc and shader_functions.get('delete_program') is not None:
                try:
                    if shader_functions.get('use_program') is not None:
                        shader_functions['use_program'](0)
                except Exception:
                    pass
                shader_functions['delete_program'](int(compute_program))
        except Exception:
            pass
        try:
            if int(compute_buffer.value) and hrc and compute_functions.get('delete_buffers') is not None:
                compute_functions['delete_buffers'](1, ctypes.byref(compute_buffer))
        except Exception:
            pass
        try:
            if shader_program and hrc and shader_functions.get('delete_program') is not None:
                try:
                    if shader_functions.get('use_program') is not None:
                        shader_functions['use_program'](0)
                except Exception:
                    pass
                shader_functions['delete_program'](int(shader_program))
        except Exception:
            pass
        try:
            if texture_ids is not None and texture_count_actual > 0 and hrc:
                opengl32.glDeleteTextures(texture_count_actual, texture_ids)
        except Exception:
            pass
        try:
            if hrc:
                opengl32.wglMakeCurrent(None, None)
                opengl32.wglDeleteContext(hrc)
        except Exception:
            pass
        try:
            if hwnd and hdc:
                user32.ReleaseDC(hwnd, hdc)
        except Exception:
            pass
        try:
            if hwnd:
                user32.DestroyWindow(hwnd)
        except Exception:
            pass
        try:
            user32.UnregisterClassW(class_name, hinstance)
        except Exception:
            pass


def run_visual_benchmark(
    profile: str = 'standard',
    *,
    components=None,
    progress_callback: ProgressCallback = None,
    telemetry_sampler: TelemetrySampler = None,
    cancel_check: CancelCheck = None,
) -> Dict[str, Any]:
    """Ejecuta el benchmark visual 3D visible.

    Devuelve únicamente mediciones observadas. En plataformas no compatibles,
    retorna UNAVAILABLE en vez de simular un resultado.
    """
    profile_data = visual_profile_info(profile)
    if platform.system() != 'Windows':
        return {
            'kind': 'HARDWARE_VISUAL', 'value': None, 'unit': 'FPS', 'provider': 'N/A',
            'duration_s': 0.0, 'timestamp': time.time(), 'status': 'UNAVAILABLE',
            'reason': 'El benchmark visual 3D de CorePulse requiere Windows',
            'profile': profile_data['key'], 'profile_label': profile_data['label'],
        }
    try:
        return _run_windows_visual(profile_data, progress_callback, telemetry_sampler, components=components, cancel_check=cancel_check)
    except Exception as exc:
        return {
            'kind': 'HARDWARE_VISUAL', 'value': None, 'unit': 'FPS', 'provider': 'CorePulse Visual Hardware Benchmark',
            'duration_s': 0.0, 'timestamp': time.time(), 'status': 'ERROR', 'reason': str(exc),
            'profile': profile_data['key'], 'profile_label': profile_data['label'],
        }
