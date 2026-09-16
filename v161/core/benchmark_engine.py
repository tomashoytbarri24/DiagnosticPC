"""Motor de benchmark local de CorePulse.

V106 incorpora una suite ESTÁNDAR sostenida. No pretende sustituir a Cinebench,
3DMark o CrystalDiskMark ni inventa rankings entre equipos: genera trabajo real,
mide cuánto completa este PC y conserva los resultados para comparar ejecuciones.

La API corta histórica sigue disponible para pruebas internas y compatibilidad.
"""
from __future__ import annotations

import concurrent.futures
import ctypes
import hashlib
import math
import os
import platform
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional

from core.benchmark_telemetry import BenchmarkTelemetry, stats

ProgressCallback = Optional[Callable[[float, str, str], None]]
TelemetrySampler = Optional[Callable[[], Dict[str, Any]]]


BENCHMARK_PROFILES = {
    'quick': {
        'label': 'Rápido',
        'duration_label': '~15–25 s',
        'description': 'Comprobación breve de CPU, RAM, SSD y GPU.',
        'cpu_seconds': 6.0,
        'ram_seconds': 4.0,
        'ram_size_cap_mb': 128,
        'ssd_size_mb': 192,
        'gpu_seconds': 6.0,
    },
    'standard': {
        'label': 'Estándar',
        'duration_label': '~35–55 s',
        'description': 'Equilibrio entre duración y carga sostenida.',
        'cpu_seconds': 14.0,
        'ram_seconds': 8.0,
        'ram_size_cap_mb': 256,
        'ssd_size_mb': 512,
        'gpu_seconds': 12.0,
    },
    'extended': {
        'label': 'Extendido',
        'duration_label': '~75–110 s',
        'description': 'Carga más prolongada para observar estabilidad y temperatura.',
        'cpu_seconds': 28.0,
        'ram_seconds': 18.0,
        'ram_size_cap_mb': 384,
        'ssd_size_mb': 1024,
        'gpu_seconds': 28.0,
    },
}

BENCHMARK_COMPONENTS = ('cpu', 'ram', 'ssd', 'gpu')


def benchmark_profile_info(profile: str = 'standard') -> Dict[str, Any]:
    key = str(profile or 'standard').strip().lower()
    if key not in BENCHMARK_PROFILES:
        key = 'standard'
    return {'key': key, **BENCHMARK_PROFILES[key]}


def _result(kind, value=None, unit='', provider='', duration_s=None, **extra):
    return {
        'kind': kind,
        'value': value,
        'unit': unit,
        'provider': provider,
        'duration_s': duration_s,
        'timestamp': time.time(),
        **extra,
    }


def _safe_progress(callback: ProgressCallback, fraction: float, stage: str, detail: str = ''):
    if not callable(callback):
        return
    try:
        callback(max(0.0, min(1.0, float(fraction))), str(stage), str(detail or ''))
    except Exception:
        pass


class _SuiteReporter:
    """Progreso y telemetría del componente que realmente está midiendo la suite."""

    def __init__(self, callback=None, telemetry_sampler=None, storage_inventory=None):
        self.callback = callback
        self.telemetry_sampler = telemetry_sampler
        self.storage_inventory = storage_inventory
        self.monitor = BenchmarkTelemetry(telemetry_sampler, storage_inventory)
        self.monitors = []
        self.gpu_summary = {}
        self.stop_reason = None

    def sample(self, **kwargs):
        self.monitor.sample(**kwargs)
        self.stop_reason = self.stop_reason or self.monitor.stop_reason

    def begin(self):
        self.monitor = BenchmarkTelemetry(self.telemetry_sampler, self.storage_inventory)
        self.monitors.append(self.monitor)
        self.sample(force=True, boundary=True)
        # La primera consulta de la carga debe muestrear incluso en SSD rápidos.
        self.monitor.last_sample = 0.0

    def emit(self, fraction, stage, detail=''):
        self.sample()
        _safe_progress(self.callback, fraction, stage, detail)

    @property
    def should_stop(self):
        self.sample()
        return bool(self.stop_reason)

    def finish(self, result):
        # El último progreso/stop_check ya recogió la evidencia bajo carga.
        result['telemetry'] = self.monitor.summary(result.get('renderer'), result.get('path_root'))
        if result.get('renderer'):
            self.gpu_summary = result['telemetry']
        result['telemetry']['execution_errors'] = ([str(result.get('reason') or result.get('error') or 'ERROR')]
                                                   if result.get('status') == 'ERROR' else [])

    def summary(self):
        rows = [row for monitor in self.monitors for row in monitor.rows if not row['boundary']]
        summary = {'sample_count': len(rows), 'safety_stop': self.stop_reason}
        for key in ('cpu_temp', 'cpu_ghz', 'cpu_usage', 'ram_usage'):
            summary[key] = stats(row.get(key) for row in rows)
        for key in ('gpu_temp', 'gpu_usage', 'gpu_clock_mhz'):
            summary[key] = self.gpu_summary.get(key, stats([]))
        return summary


def _float(value):
    try:
        return float(value) if value is not None else None
    except Exception:
        return None


def _hash_worker(block: bytes, stop_event: threading.Event) -> int:
    count = 0
    digest = b''
    while not stop_event.is_set():
        digest = hashlib.sha256(block + digest).digest()
        count += 1
    return count


def benchmark_cpu(
    seconds: float = 2.0,
    *,
    threads: int | None = None,
    progress_callback: ProgressCallback = None,
    stop_check: Optional[Callable[[], bool]] = None,
):
    """Carga SHA-256 sostenida con tramo single-thread y multi-thread real."""
    seconds = max(0.5, min(30.0, float(seconds)))
    logical = max(1, int(os.cpu_count() or 1))
    worker_count = max(1, min(int(threads or logical), 24))
    # Un bloque grande hace que hashlib ejecute trabajo nativo y permite que los
    # workers concurrentes utilicen varios núcleos sin depender del GIL de Python.
    block = (b'CorePulse sustained CPU benchmark\0' * 8192)[:256 * 1024]

    single_seconds = min(4.0, max(0.5, seconds * 0.30))
    multi_seconds = max(0.1, seconds - single_seconds)
    total_start = time.perf_counter()

    _safe_progress(progress_callback, 0.0, 'CPU · 1 hilo', 'Calentando y midiendo rendimiento por hilo')
    count_single = 0
    digest = b''
    start = time.perf_counter()
    end = start + single_seconds
    next_emit = start
    while time.perf_counter() < end:
        digest = hashlib.sha256(block + digest).digest()
        count_single += 1
        now = time.perf_counter()
        if now >= next_emit:
            frac = min(1.0, (now - start) / max(single_seconds, 0.001))
            _safe_progress(progress_callback, frac * 0.30, 'CPU · 1 hilo', 'Carga SHA-256 sostenida')
            next_emit = now + 0.35
            if callable(stop_check) and stop_check():
                break
    single_duration = max(1e-6, time.perf_counter() - start)
    single_ops = count_single / single_duration

    if callable(stop_check) and stop_check():
        duration = time.perf_counter() - total_start
        return _result(
            'CPU', single_ops, 'SHA256 ops/s', 'CorePulse SHA-256 workload', duration,
            single_thread_ops_s=single_ops, multi_thread_ops_s=None, threads=1,
            throughput_mbps=single_ops * (len(block) / (1024 * 1024)), status='SAFETY_STOP',
        )

    _safe_progress(progress_callback, 0.30, 'CPU · multinúcleo', f'Carga concurrente en {worker_count} hilos')
    stop_event = threading.Event()
    with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix='CorePulse-BenchCPU') as pool:
        futures = [pool.submit(_hash_worker, block, stop_event) for _ in range(worker_count)]
        try:
            start_multi = time.perf_counter()
            deadline = start_multi + multi_seconds
            while time.perf_counter() < deadline:
                now = time.perf_counter()
                frac = min(1.0, (now - start_multi) / max(multi_seconds, 0.001))
                _safe_progress(progress_callback, 0.30 + frac * 0.70, 'CPU · multinúcleo', f'{worker_count} hilos bajo carga real')
                if callable(stop_check) and stop_check():
                    break
                time.sleep(0.25)
        finally:
            stop_event.set()
        counts = []
        for future in futures:
            try:
                counts.append(int(future.result(timeout=3)))
            except Exception:
                counts.append(0)
    multi_duration = max(1e-6, time.perf_counter() - start_multi)
    multi_count = sum(counts)
    multi_ops = multi_count / multi_duration
    duration = time.perf_counter() - total_start
    throughput = multi_ops * (len(block) / (1024 * 1024))
    _safe_progress(progress_callback, 1.0, 'CPU completado', f'{worker_count} hilos · {throughput:.0f} MB/s SHA-256')
    return _result(
        'CPU', multi_ops, 'SHA256 ops/s', 'CorePulse SHA-256 workload', duration,
        single_thread_ops_s=single_ops,
        multi_thread_ops_s=multi_ops,
        threads=worker_count,
        block_kb=len(block) // 1024,
        throughput_mbps=throughput,
        iterations=multi_count,
        status='SAFETY_STOP' if callable(stop_check) and stop_check() else 'OK',
    )


def benchmark_ram(
    size_mb: int = 128,
    rounds: int = 4,
    *,
    min_seconds: float | None = None,
    progress_callback: ProgressCallback = None,
    stop_check: Optional[Callable[[], bool]] = None,
):
    """Copia bloques reales de memoria durante varias rondas sostenidas."""
    size_mb = max(32, min(512, int(size_mb)))
    rounds = max(1, min(1000, int(rounds)))
    target_seconds = None if min_seconds is None else max(1.0, min(20.0, float(min_seconds)))
    size_bytes = size_mb * 1024 * 1024
    seed = bytes((i % 251 for i in range(1024 * 1024)))
    src = bytearray(size_bytes)
    for offset in range(0, size_bytes, len(seed)):
        src[offset:offset + len(seed)] = seed[: min(len(seed), size_bytes - offset)]
    dst = bytearray(size_bytes)

    start = time.perf_counter()
    copied_mb = 0.0
    checksum = 0
    completed_rounds = 0
    while True:
        dst[:] = src
        completed_rounds += 1
        copied_mb += float(size_mb)
        if dst:
            checksum ^= dst[(completed_rounds * 4093) % len(dst)]
        elapsed = time.perf_counter() - start
        if target_seconds is None:
            frac = min(1.0, completed_rounds / rounds)
        else:
            frac = min(1.0, elapsed / target_seconds)
        _safe_progress(progress_callback, frac, 'RAM · ancho de banda', f'{copied_mb / 1024.0:.1f} GB copiados')
        if callable(stop_check) and stop_check():
            break
        if target_seconds is None:
            if completed_rounds >= rounds:
                break
        elif elapsed >= target_seconds and completed_rounds >= rounds:
            break
    duration = max(1e-6, time.perf_counter() - start)
    bandwidth = copied_mb / duration
    return _result(
        'RAM', bandwidth, 'MB/s', 'CorePulse sustained memory copy', duration,
        transferred_mb=copied_mb,
        buffer_mb=size_mb,
        rounds=completed_rounds,
        checksum=checksum,
        status='SAFETY_STOP' if callable(stop_check) and stop_check() else 'OK',
    )


def _adaptive_ssd_size(requested_mb: int, base: Path) -> int:
    requested_mb = max(64, min(1024, int(requested_mb)))
    try:
        import shutil
        free_mb = int(shutil.disk_usage(base).free / (1024 * 1024))
        # Nunca ocupamos más de ~2% del espacio libre ni menos de 64 MB.
        return max(64, min(requested_mb, max(64, int(free_mb * 0.02))))
    except Exception:
        return requested_mb


def benchmark_ssd(
    target_dir: str | Path | None = None,
    size_mb: int = 96,
    *,
    progress_callback: ProgressCallback = None,
    stop_check: Optional[Callable[[], bool]] = None,
):
    """E/S secuencial con archivo temporal, flush y fsync antes de la lectura."""
    base = Path(target_dir) if target_dir else Path(tempfile.gettempdir())
    base.mkdir(parents=True, exist_ok=True)
    size_mb = _adaptive_ssd_size(size_mb, base)
    path = base / f'corepulse_bench_{os.getpid()}_{threading.get_ident()}_{time.time_ns()}.bin'
    chunk_mb = 4
    chunk = os.urandom(chunk_mb * 1024 * 1024)
    total_chunks = max(1, size_mb // chunk_mb)
    actual_mb = total_chunks * chunk_mb
    write_start = time.perf_counter()
    written_bytes = 0
    try:
        with open(path, 'wb', buffering=0) as f:
            for index in range(total_chunks):
                written_bytes += f.write(chunk)
                if index % 4 == 0 or index + 1 == total_chunks:
                    _safe_progress(
                        progress_callback,
                        0.48 * ((index + 1) / total_chunks),
                        'SSD · escritura secuencial',
                        f'{(index + 1) * chunk_mb} / {actual_mb} MB',
                    )
                if callable(stop_check) and stop_check():
                    break
            f.flush()
            os.fsync(f.fileno())
        write_duration = max(1e-6, time.perf_counter() - write_start)

        if callable(stop_check) and stop_check():
            return _result(
                'SSD', None, 'MB/s', 'CorePulse sequential file I/O', write_duration,
                write_mbps=(written_bytes / (1024 * 1024)) / write_duration, read_mbps=None, size_mb=written_bytes / (1024 * 1024),
                path_root=str(base.anchor or base), status='SAFETY_STOP',
            )

        read_start = time.perf_counter()
        total = 0
        with open(path, 'rb', buffering=0) as f:
            while True:
                data = f.read(chunk_mb * 1024 * 1024)
                if not data:
                    break
                total += len(data)
                _safe_progress(
                    progress_callback,
                    0.48 + 0.52 * min(1.0, total / max(1, actual_mb * 1024 * 1024)),
                    'SSD · lectura secuencial',
                    f'{total / (1024 * 1024):.0f} / {actual_mb} MB',
                )
                if callable(stop_check) and stop_check():
                    break
        read_duration = max(1e-6, time.perf_counter() - read_start)
        read_mb = total / (1024 * 1024)
        return _result(
            'SSD', actual_mb / write_duration, 'MB/s write', 'CorePulse sequential file I/O',
            write_duration + read_duration,
            write_mbps=actual_mb / write_duration,
            read_mbps=read_mb / read_duration,
            size_mb=actual_mb,
            path_root=str(base.anchor or base),
            status='SAFETY_STOP' if callable(stop_check) and stop_check() else 'OK',
        )
    finally:
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass


def _benchmark_gpu_opengl(
    seconds: float,
    progress_callback: ProgressCallback = None,
    stop_check: Optional[Callable[[], bool]] = None,
):
    """Carga OpenGL 1.1 real sin dependencias externas y sin requerir elevación."""
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    kernel32 = ctypes.windll.kernel32
    opengl32 = ctypes.windll.opengl32

    # Handles Win32 son punteros. En Windows x64 DEBEN tener firmas explícitas:
    # sin argtypes ctypes intenta convertir argumentos como `int` de 32 bits y
    # CreateWindowExW puede fallar con `argument 11: OverflowError`, porque el
    # hInstance ocupa 64 bits.
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
            ('style', wintypes.UINT),
            ('lpfnWndProc', WNDPROC),
            ('cbClsExtra', ctypes.c_int),
            ('cbWndExtra', ctypes.c_int),
            ('hInstance', HINSTANCE_T),
            ('hIcon', HICON_T),
            ('hCursor', HCURSOR_T),
            ('hbrBackground', HBRUSH_T),
            ('lpszMenuName', wintypes.LPCWSTR),
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

    # ABI Win32 completo y pointer-safe para Python 3.12+ x64.
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
    gdi32.ChoosePixelFormat.argtypes = [HDC_T, ctypes.POINTER(PIXELFORMATDESCRIPTOR)]
    gdi32.ChoosePixelFormat.restype = ctypes.c_int
    gdi32.SetPixelFormat.argtypes = [HDC_T, ctypes.c_int, ctypes.POINTER(PIXELFORMATDESCRIPTOR)]
    gdi32.SetPixelFormat.restype = wintypes.BOOL
    opengl32.wglCreateContext.argtypes = [HDC_T]
    opengl32.wglCreateContext.restype = HGLRC_T
    opengl32.wglMakeCurrent.argtypes = [HDC_T, HGLRC_T]
    opengl32.wglMakeCurrent.restype = wintypes.BOOL
    opengl32.wglDeleteContext.argtypes = [HGLRC_T]
    opengl32.wglDeleteContext.restype = wintypes.BOOL

    @WNDPROC
    def wndproc(hwnd, msg, wparam, lparam):
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    hinstance = kernel32.GetModuleHandleW(None)
    if not hinstance:
        raise RuntimeError('Windows no entregó el módulo para crear el contexto OpenGL')
    class_name = f'CorePulseBenchGL_{os.getpid()}_{threading.get_ident()}'
    wc = WNDCLASSW()
    wc.style = 0x0020  # CS_OWNDC
    wc.lpfnWndProc = wndproc
    wc.hInstance = hinstance
    wc.lpszClassName = class_name
    atom = user32.RegisterClassW(ctypes.byref(wc))
    if not atom:
        raise RuntimeError('No se pudo registrar el contexto gráfico de benchmark')

    hwnd = hdc = hrc = None
    try:
        hwnd = user32.CreateWindowExW(0, class_name, 'CorePulse GPU Benchmark', 0x80000000, 0, 0, 1280, 720, None, None, hinstance, None)
        if not hwnd:
            raise RuntimeError('No se pudo crear la superficie OpenGL')
        hdc = user32.GetDC(hwnd)
        if not hdc:
            raise RuntimeError('No se pudo obtener el contexto de dispositivo')

        pfd = PIXELFORMATDESCRIPTOR()
        pfd.nSize = ctypes.sizeof(PIXELFORMATDESCRIPTOR)
        pfd.nVersion = 1
        pfd.dwFlags = 0x00000004 | 0x00000020 | 0x00000001  # DRAW_TO_WINDOW | SUPPORT_OPENGL | DOUBLEBUFFER
        pfd.iPixelType = 0  # PFD_TYPE_RGBA
        pfd.cColorBits = 32
        pfd.cDepthBits = 24
        pfd.iLayerType = 0
        pixel_format = gdi32.ChoosePixelFormat(hdc, ctypes.byref(pfd))
        if not pixel_format or not gdi32.SetPixelFormat(hdc, pixel_format, ctypes.byref(pfd)):
            raise RuntimeError('Windows no pudo configurar el formato OpenGL')

        hrc = opengl32.wglCreateContext(hdc)
        if not hrc or not opengl32.wglMakeCurrent(hdc, hrc):
            raise RuntimeError('No se pudo activar el contexto OpenGL')

        GL_RENDERER, GL_VENDOR, GL_VERSION = 0x1F01, 0x1F00, 0x1F02
        opengl32.glGetString.restype = ctypes.c_char_p
        renderer = (opengl32.glGetString(GL_RENDERER) or b'').decode('utf-8', 'replace')
        vendor = (opengl32.glGetString(GL_VENDOR) or b'').decode('utf-8', 'replace')
        gl_version = (opengl32.glGetString(GL_VERSION) or b'').decode('utf-8', 'replace')
        if not renderer or 'GDI Generic' in renderer:
            return _result(
                'GPU', None, 'Mtri/s', 'CorePulse OpenGL render workload', 0,
                status='UNAVAILABLE', reason='No hay aceleración OpenGL de hardware disponible', renderer=renderer or 'N/A', vendor=vendor or 'N/A',
            )

        GL_COLOR_BUFFER_BIT = 0x00004000
        GL_VERTEX_ARRAY = 0x8074
        GL_FLOAT = 0x1406
        GL_TRIANGLES = 0x0004
        opengl32.glViewport(0, 0, 1280, 720)
        opengl32.glClearColor(ctypes.c_float(0.02), ctypes.c_float(0.05), ctypes.c_float(0.08), ctypes.c_float(1.0))
        opengl32.glEnableClientState(GL_VERTEX_ARRAY)
        opengl32.glVertexPointer.argtypes = [ctypes.c_int, ctypes.c_uint, ctypes.c_int, ctypes.c_void_p]
        opengl32.glDrawArrays.argtypes = [ctypes.c_uint, ctypes.c_int, ctypes.c_int]

        triangles_per_draw = 12000
        draws_per_frame = 8
        vertex_count = triangles_per_draw * 3
        vertices = (ctypes.c_float * (vertex_count * 2))()
        for tri in range(triangles_per_draw):
            cell_x = tri % 160
            cell_y = (tri // 160) % 75
            x = -0.99 + (cell_x / 160.0) * 1.98
            y = -0.99 + (cell_y / 75.0) * 1.98
            sx = 0.006
            sy = 0.010
            base = tri * 6
            vertices[base:base + 6] = (x, y, x + sx, y, x, y + sy)
        ptr = ctypes.cast(vertices, ctypes.c_void_p)

        seconds = max(2.0, min(30.0, float(seconds)))
        start = time.perf_counter()
        deadline = start + seconds
        frames = 0
        frame_times = []
        last_frame = start
        next_emit = start
        while time.perf_counter() < deadline:
            if callable(stop_check) and stop_check():
                break
            opengl32.glClear(GL_COLOR_BUFFER_BIT)
            opengl32.glVertexPointer(2, GL_FLOAT, 0, ptr)
            for _ in range(draws_per_frame):
                opengl32.glDrawArrays(GL_TRIANGLES, 0, vertex_count)
            opengl32.glFinish()
            frames += 1
            now = time.perf_counter()
            frame_times.append(now - last_frame)
            last_frame = now
            if now >= next_emit:
                frac = min(1.0, (now - start) / seconds)
                _safe_progress(progress_callback, frac, 'GPU · render OpenGL', renderer)
                next_emit = now + 0.35
                if callable(stop_check) and stop_check():
                    break
        duration = max(1e-6, time.perf_counter() - start)
        fps = frames / duration
        triangles = frames * triangles_per_draw * draws_per_frame
        mtri_s = (triangles / duration) / 1_000_000.0
        _safe_progress(progress_callback, 1.0, 'GPU completado', f'{renderer} · {mtri_s:.1f} Mtri/s')
        return _result(
            'GPU', mtri_s, 'Mtri/s', 'CorePulse OpenGL render workload', duration,
            status='SAFETY_STOP' if callable(stop_check) and stop_check() else 'OK',
            renderer=renderer,
            vendor=vendor,
            gl_version=gl_version,
            frames=frames,
            frames_per_s=fps,
            fps_1pct_low=(1.0 / (sum(sorted(frame_times, reverse=True)[:max(1, math.ceil(len(frame_times) * 0.01))])
                         / max(1, math.ceil(len(frame_times) * 0.01)))) if frame_times else None,
            triangles_per_s=triangles / duration,
            triangles_per_frame=triangles_per_draw * draws_per_frame,
            resolution='1280x720 off-screen',
        )
    finally:
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


def benchmark_gpu(
    timeout: int = 30,
    *,
    seconds: float | None = None,
    progress_callback: ProgressCallback = None,
    stop_check: Optional[Callable[[], bool]] = None,
):
    """Benchmark gráfico real. En Windows usa un workload OpenGL propio."""
    if platform.system() != 'Windows':
        return _result('GPU', None, 'Mtri/s', 'N/A', 0, status='UNAVAILABLE', reason='La carga gráfica CorePulse requiere Windows')
    duration = max(2.0, min(float(seconds if seconds is not None else min(timeout, 12)), 30.0))
    start = time.perf_counter()
    try:
        return _benchmark_gpu_opengl(duration, progress_callback=progress_callback, stop_check=stop_check)
    except Exception as exc:
        return _result(
            'GPU', None, 'Mtri/s', 'CorePulse OpenGL render workload', time.perf_counter() - start,
            status='ERROR', reason=str(exc),
        )


def _map_progress(reporter: _SuiteReporter, start: float, end: float):
    span = max(0.0, end - start)

    def callback(local_fraction: float, stage: str, detail: str = ''):
        reporter.emit(start + span * max(0.0, min(1.0, float(local_fraction))), stage, detail)

    return callback


def _not_run(kind: str, reason: str):
    return _result(kind, None, '', 'CorePulse', 0, status='UNAVAILABLE', reason=reason)


def _normalize_components(components=None):
    if components is None:
        return list(BENCHMARK_COMPONENTS)
    selected = []
    for item in components:
        key = str(item or '').strip().lower()
        if key in BENCHMARK_COMPONENTS and key not in selected:
            selected.append(key)
    return selected


def _adaptive_ram_size(cap_mb: int) -> int:
    size_mb = max(64, min(512, int(cap_mb)))
    try:
        import psutil
        available_mb = int(psutil.virtual_memory().available / (1024 * 1024))
        size_mb = max(64, min(size_mb, int(available_mb * 0.08)))
    except Exception:
        pass
    return size_mb


def run_benchmark_suite(
    profile: str = 'standard',
    components=None,
    ssd_dir=None,
    *,
    progress_callback: ProgressCallback = None,
    telemetry_sampler: TelemetrySampler = None,
    cancel_check: Optional[Callable[[], bool]] = None,
    storage_inventory=None,
):
    """Ejecuta un perfil real de benchmark sobre los componentes elegidos.

    Los perfiles sólo cambian duración/tamaño de la carga; nunca inventan una
    puntuación. Los componentes no seleccionados se devuelven como ``SKIPPED``
    para que la presentación pueda explicar claramente qué se midió.
    """
    profile_data = benchmark_profile_info(profile)
    selected = _normalize_components(components)
    if not selected:
        raise ValueError('Selecciona al menos un componente para ejecutar el benchmark')

    started_wall = time.time()
    started = time.perf_counter()
    reporter = _SuiteReporter(progress_callback, telemetry_sampler, storage_inventory)

    def cancelled():
        try:
            return bool(callable(cancel_check) and cancel_check())
        except Exception:
            return False

    def should_stop():
        return bool(cancelled() or reporter.should_stop)

    selected_labels = ', '.join(key.upper() for key in selected)
    _safe_progress(progress_callback, 0.01, f"Preparando benchmark {profile_data['label'].lower()}", selected_labels)

    weights = {
        'cpu': max(1.0, float(profile_data['cpu_seconds'])),
        'ram': max(1.0, float(profile_data['ram_seconds'])),
        'ssd': max(4.0, float(profile_data['ssd_size_mb']) / 64.0),
        'gpu': max(1.0, float(profile_data['gpu_seconds'])),
    }
    total_weight = sum(weights[key] for key in selected) or 1.0
    cursor = 0.03
    usable_span = 0.95

    def span_for(key):
        nonlocal cursor
        span = usable_span * (weights[key] / total_weight)
        start_fraction = cursor
        end_fraction = min(0.98, cursor + span)
        cursor = end_fraction
        return start_fraction, end_fraction

    results = {
        key: _not_run(key.upper(), 'No seleccionado por el usuario')
        for key in BENCHMARK_COMPONENTS
    }
    for result in results.values():
        result['status'] = 'SKIPPED'

    for key in selected:
        if reporter.stop_reason or cancelled():
            reason = 'Cancelado por el usuario' if cancelled() else (reporter.stop_reason or 'Detenido por seguridad')
            results[key] = _not_run(key.upper(), reason)
            results[key]['status'] = 'CANCELLED' if cancelled() else 'SKIPPED'
            continue

        reporter.begin()
        if reporter.stop_reason or cancelled():
            results[key] = _not_run(key.upper(), 'Cancelado por el usuario' if cancelled() else reporter.stop_reason)
            results[key]['status'] = 'CANCELLED' if cancelled() else 'SAFETY_STOP'
            reporter.finish(results[key])
            continue
        start_fraction, end_fraction = span_for(key)
        callback = _map_progress(reporter, start_fraction, end_fraction)
        try:
            if key == 'cpu':
                results[key] = benchmark_cpu(
                    profile_data['cpu_seconds'],
                    progress_callback=callback,
                    stop_check=should_stop,
                )
            elif key == 'ram':
                results[key] = benchmark_ram(
                    _adaptive_ram_size(profile_data['ram_size_cap_mb']), 4,
                    min_seconds=profile_data['ram_seconds'],
                    progress_callback=callback,
                    stop_check=should_stop,
                )
            elif key == 'ssd':
                results[key] = benchmark_ssd(
                    ssd_dir, profile_data['ssd_size_mb'],
                    progress_callback=callback,
                    stop_check=should_stop,
                )
            elif key == 'gpu':
                gpu_seconds = float(profile_data['gpu_seconds'])
                results[key] = benchmark_gpu(
                    max(8, int(gpu_seconds + 4)), seconds=gpu_seconds,
                    progress_callback=callback,
                    stop_check=should_stop,
                )
        except Exception as exc:
            results[key] = _result(key.upper(), status='ERROR', reason=f'{type(exc).__name__}: {exc}')
        if cancelled() or reporter.stop_reason:
            results[key]['status'] = 'CANCELLED' if cancelled() else 'SAFETY_STOP'
            results[key]['reason'] = 'Cancelado por el usuario' if cancelled() else reporter.stop_reason
        reporter.finish(results[key])

    if reporter.stop_reason or cancelled():
        was_cancelled = cancelled()
        reason = 'Cancelado por el usuario' if was_cancelled else (reporter.stop_reason or 'Detenido por seguridad')
        for key in selected:
            item = results.get(key) if isinstance(results.get(key), dict) else {}
            status = str(item.get('status') or '').upper()
            if was_cancelled and status == 'SAFETY_STOP':
                item['status'] = 'CANCELLED'
                item['reason'] = reason

    _safe_progress(progress_callback, 1.0, 'Benchmark cancelado' if cancelled() else 'Benchmark interrumpido por seguridad' if reporter.stop_reason else 'Benchmark finalizado', 'Resultados medidos durante esta ejecución')
    duration = time.perf_counter() - started
    return {
        'started_at': started_wall,
        'finished_at': time.time(),
        'duration_s': duration,
        'profile': profile_data['key'].upper(),
        'profile_label': profile_data['label'],
        'selected_components': selected,
        'cpu': results['cpu'],
        'ram': results['ram'],
        'ssd': results['ssd'],
        'gpu': results['gpu'],
        'telemetry_summary': reporter.summary(),
        'safety_stop': reporter.stop_reason,
        'cancelled': cancelled(),
        'status': 'CANCELLED' if cancelled() else ('SAFETY_STOP' if reporter.stop_reason else 'PARTIAL' if any(results[k].get('status') != 'OK' for k in selected) else 'OK'),
        'policy': 'LOCAL_CONFIGURABLE_BENCHMARK_NO_REFERENCE_RANKING',
    }


def run_standard_suite(
    ssd_dir=None,
    *,
    progress_callback: ProgressCallback = None,
    telemetry_sampler: TelemetrySampler = None,
):
    """Compatibilidad: ejecuta el perfil estándar con los cuatro componentes."""
    return run_benchmark_suite(
        'standard', BENCHMARK_COMPONENTS, ssd_dir,
        progress_callback=progress_callback,
        telemetry_sampler=telemetry_sampler,
    )


def run_quick_suite(ssd_dir=None):
    """Suite corta histórica, conservada para compatibilidad y smoke tests."""
    return {
        'started_at': time.time(),
        'cpu': benchmark_cpu(2.0),
        'ram': benchmark_ram(128, 4),
        'ssd': benchmark_ssd(ssd_dir, 96),
        'gpu': benchmark_gpu(timeout=6, seconds=3.0),
        'policy': 'LOCAL_SHORT_BENCHMARK_NO_REFERENCE_RANKING',
    }
