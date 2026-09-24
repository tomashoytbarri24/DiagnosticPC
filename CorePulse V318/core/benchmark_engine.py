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
import json
import math
import os
import platform
import tempfile
import threading
import time
import statistics
import random
import zlib
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional

from core.benchmark_telemetry import BenchmarkTelemetry, stats
from core.runtime_paths import executable_root
from core.benchmark_version import BENCHMARK_METHOD, GPU_BENCHMARK_METHOD, GPU_RESULT_FILENAME, GPU_PROVIDER, GPU_POLICY, GPU_BENCHMARK_LABEL

ProgressCallback = Optional[Callable[[float, str, str], None]]
TelemetrySampler = Optional[Callable[[], Dict[str, Any]]]


BENCHMARK_PROFILES = {
    'quick': {
        'label': 'Rápido',
        'duration_label': '~40–55 s',
        'description': 'Comprobación breve de CPU, RAM, SSD y GPU.',
        'cpu_seconds': 6.0,
        'ram_seconds': 4.0,
        'ram_size_cap_mb': 128,
        'ssd_size_mb': 192,
        'gpu_seconds': 20.0,
    },
    'standard': {
        'label': 'Estándar',
        'duration_label': '~95–125 s',
        'description': 'Benchmark V25: CPU/RAM/SSD por áreas y GPU DirectX 11 con reloj de pared determinista, 49 s medidos en las cuatro escenas, timestamps GPU auditados y pulido visual del escenario.',
        'cpu_seconds': 12.0,
        'ram_seconds': 8.0,
        'ram_size_cap_mb': 192,
        'ssd_size_mb': 256,
        'gpu_seconds': 58.0,
    },
    'extended': {
        'label': 'Extendido',
        'duration_label': '~155–210 s',
        'description': 'Carga más prolongada para observar estabilidad y temperatura.',
        'cpu_seconds': 28.0,
        'ram_seconds': 18.0,
        'ram_size_cap_mb': 384,
        'ssd_size_mb': 512,
        'gpu_seconds': 91.0,
    },
}

BENCHMARK_COMPONENTS = ('cpu', 'ram', 'ssd', 'gpu')

# V162: identificadores explícitos de metodología. El historial sólo debe
# comparar sesiones que midieron realmente lo mismo.
BENCHMARK_METHOD_ID = BENCHMARK_METHOD
CPU_METHOD_ID = 'COREPULSE_CPU_AREAS_V4'
RAM_METHOD_ID = 'COREPULSE_RAM_AREAS_V4'
SSD_METHOD_ID = 'COREPULSE_SSD_IO_V4'
GPU_METHOD_ID = GPU_BENCHMARK_METHOD
GPU_LAST_RESULT_RELATIVE_PATH = Path('resultados') / GPU_RESULT_FILENAME


def gpu_last_result_path() -> Path:
    """Ruta portable del último resultado: proyecto en Python o carpeta del EXE."""
    return executable_root() / GPU_LAST_RESULT_RELATIVE_PATH


def _strict_json_value(value):
    """Conserva evidencia JSON real; valores no representables quedan como N/A."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else 'N/A'
    if isinstance(value, dict):
        return {str(key): _strict_json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_strict_json_value(item) for item in value]
    return 'N/A'


def save_last_gpu_v25_result(result: Dict[str, Any]) -> Path:
    """Sobrescribe atómicamente el último resultado GPU V25 completado."""
    target = gpu_last_result_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + '.tmp')
    payload = _strict_json_value(dict(result))
    with temporary.open('w', encoding='utf-8', newline='\n') as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, target)
    return target.resolve()


def save_last_gpu_v24_result(result: Dict[str, Any]) -> Path:
    """Alias de compatibilidad: desde V205 la ruta vigente es V25."""
    return save_last_gpu_v25_result(result)


def save_last_gpu_v23_result(result: Dict[str, Any]) -> Path:
    """Alias de compatibilidad hacia la ruta vigente V25."""
    return save_last_gpu_v25_result(result)


def save_last_gpu_v22_result(result: Dict[str, Any]) -> Path:
    """Alias de compatibilidad hacia la ruta vigente V25."""
    return save_last_gpu_v25_result(result)


def save_last_gpu_v21_result(result: Dict[str, Any]) -> Path:
    """Alias de compatibilidad hacia la ruta vigente V25."""
    return save_last_gpu_v25_result(result)


def save_last_gpu_v20_result(result: Dict[str, Any]) -> Path:
    """Alias de compatibilidad hacia la ruta vigente V22."""
    return save_last_gpu_v25_result(result)


def save_last_gpu_v19_result(result: Dict[str, Any]) -> Path:
    """Alias de compatibilidad hacia la ruta vigente V21."""
    return save_last_gpu_v25_result(result)


def save_last_gpu_v18_result(result: Dict[str, Any]) -> Path:
    """Alias de compatibilidad hacia la ruta vigente V20."""
    return save_last_gpu_v25_result(result)


def save_last_gpu_v17_result(result: Dict[str, Any]) -> Path:
    return save_last_gpu_v25_result(result)


def save_last_gpu_v16_result(result: Dict[str, Any]) -> Path:
    return save_last_gpu_v25_result(result)


def save_last_gpu_v15_result(result: Dict[str, Any]) -> Path:
    return save_last_gpu_v25_result(result)


def save_last_gpu_v14_result(result: Dict[str, Any]) -> Path:
    return save_last_gpu_v25_result(result)


def save_last_gpu_v13_result(result: Dict[str, Any]) -> Path:
    return save_last_gpu_v25_result(result)

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

    def begin(self, active_component=None):
        self.monitor = BenchmarkTelemetry(
            self.telemetry_sampler,
            self.storage_inventory,
            active_component=active_component,
        )
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
            throughput_mbps=single_ops * (len(block) / (1024 * 1024)), status='SAFETY_STOP', benchmark_method=CPU_METHOD_ID,
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
        benchmark_method=CPU_METHOD_ID,
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
        _safe_progress(progress_callback, frac, 'RAM · copia sostenida', f'{copied_mb / 1024.0:.1f} GB copiados')
        if callable(stop_check) and stop_check():
            break
        if target_seconds is None:
            if completed_rounds >= rounds:
                break
        elif elapsed >= target_seconds and completed_rounds >= rounds:
            break
    duration = max(1e-6, time.perf_counter() - start)
    bandwidth = copied_mb / duration
    # Verificación fuera de la ventana cronometrada: el contenido copiado debe
    # coincidir byte por byte. Si no coincide, no se publica una medición válida.
    integrity_ok = bool(dst == src)
    status = 'SAFETY_STOP' if callable(stop_check) and stop_check() else ('OK' if integrity_ok else 'ERROR')
    return _result(
        'RAM', bandwidth if integrity_ok else None, 'MB/s', 'CorePulse sustained memory copy', duration,
        benchmark_method=RAM_METHOD_ID,
        transferred_mb=copied_mb,
        buffer_mb=size_mb,
        rounds=completed_rounds,
        checksum=checksum,
        integrity_ok=integrity_ok,
        status=status,
        reason=None if integrity_ok else 'La verificación post-test de RAM no coincidió',
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


def _benchmark_ssd_windows_uncached(path: Path, actual_mb: int, chunk_bytes: int, progress_callback=None, stop_check=None):
    """E/S secuencial Windows con NO_BUFFERING + WRITE_THROUGH.

    VirtualAlloc garantiza un buffer alineado a página y el tamaño de bloque es
    múltiplo de 4 KiB. Si el dispositivo/controlador rechaza esta ruta, el
    llamador conserva un fallback explícitamente marcado como cacheable.
    """
    if platform.system() != 'Windows':
        raise RuntimeError('Direct I/O sólo disponible en Windows')
    from ctypes import wintypes
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    HANDLE = wintypes.HANDLE
    INVALID = ctypes.c_void_p(-1).value
    GENERIC_READ, GENERIC_WRITE = 0x80000000, 0x40000000
    FILE_SHARE_READ, FILE_SHARE_WRITE, FILE_SHARE_DELETE = 1, 2, 4
    CREATE_ALWAYS, OPEN_EXISTING = 2, 3
    FILE_ATTRIBUTE_TEMPORARY = 0x00000100
    FILE_FLAG_SEQUENTIAL_SCAN = 0x08000000
    FILE_FLAG_NO_BUFFERING = 0x20000000
    FILE_FLAG_WRITE_THROUGH = 0x80000000
    MEM_COMMIT, MEM_RESERVE, MEM_RELEASE, PAGE_READWRITE = 0x1000, 0x2000, 0x8000, 0x04

    kernel32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                                     wintypes.DWORD, wintypes.DWORD, HANDLE]
    kernel32.CreateFileW.restype = HANDLE
    kernel32.WriteFile.argtypes = [HANDLE, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
    kernel32.WriteFile.restype = wintypes.BOOL
    kernel32.ReadFile.argtypes = [HANDLE, wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
    kernel32.ReadFile.restype = wintypes.BOOL
    kernel32.FlushFileBuffers.argtypes = [HANDLE]
    kernel32.FlushFileBuffers.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.VirtualAlloc.argtypes = [wintypes.LPVOID, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD]
    kernel32.VirtualAlloc.restype = wintypes.LPVOID
    kernel32.VirtualFree.argtypes = [wintypes.LPVOID, ctypes.c_size_t, wintypes.DWORD]
    kernel32.VirtualFree.restype = wintypes.BOOL

    flags = FILE_ATTRIBUTE_TEMPORARY | FILE_FLAG_SEQUENTIAL_SCAN | FILE_FLAG_NO_BUFFERING | FILE_FLAG_WRITE_THROUGH
    sharing = FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE

    def invalid_handle(value):
        try:
            raw = value if isinstance(value, int) else ctypes.cast(value, ctypes.c_void_p).value
        except Exception:
            raw = None
        return raw in (None, INVALID)
    buffer = kernel32.VirtualAlloc(None, chunk_bytes, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE)
    if not buffer:
        raise OSError(ctypes.get_last_error(), 'VirtualAlloc falló para buffer alineado')
    handle = None
    total_bytes = int(actual_mb) * 1024 * 1024
    total_chunks = max(1, total_bytes // chunk_bytes)
    written = read = 0
    try:
        seed = os.urandom(min(chunk_bytes, 1024 * 1024))
        for offset in range(0, chunk_bytes, len(seed)):
            ctypes.memmove(int(buffer) + offset, seed, min(len(seed), chunk_bytes - offset))
        handle = kernel32.CreateFileW(str(path), GENERIC_WRITE, sharing, None, CREATE_ALWAYS, flags, None)
        if invalid_handle(handle):
            raise OSError(ctypes.get_last_error(), 'CreateFileW escritura directa falló')
        start_w = time.perf_counter()
        for index in range(total_chunks):
            done = wintypes.DWORD(0)
            if not kernel32.WriteFile(handle, buffer, chunk_bytes, ctypes.byref(done), None) or done.value != chunk_bytes:
                raise OSError(ctypes.get_last_error(), 'WriteFile directo falló')
            written += int(done.value)
            _safe_progress(progress_callback, 0.48 * ((index + 1) / total_chunks), 'SSD · escritura directa', f'{written / (1024*1024):.0f} / {actual_mb} MB')
            if callable(stop_check) and stop_check():
                break
        if not kernel32.FlushFileBuffers(handle):
            raise OSError(ctypes.get_last_error(), 'FlushFileBuffers falló')
        write_duration = max(1e-6, time.perf_counter() - start_w)
        kernel32.CloseHandle(handle); handle = None
        if callable(stop_check) and stop_check():
            return written, 0, write_duration, 0.0

        handle = kernel32.CreateFileW(str(path), GENERIC_READ, sharing, None, OPEN_EXISTING, flags, None)
        if invalid_handle(handle):
            raise OSError(ctypes.get_last_error(), 'CreateFileW lectura directa falló')
        start_r = time.perf_counter()
        for _index in range(total_chunks):
            done = wintypes.DWORD(0)
            if not kernel32.ReadFile(handle, buffer, chunk_bytes, ctypes.byref(done), None):
                raise OSError(ctypes.get_last_error(), 'ReadFile directo falló')
            if not done.value:
                break
            read += int(done.value)
            _safe_progress(progress_callback, 0.48 + 0.52 * min(1.0, read / max(1, total_bytes)), 'SSD · lectura directa', f'{read / (1024*1024):.0f} / {actual_mb} MB')
            if callable(stop_check) and stop_check():
                break
        read_duration = max(1e-6, time.perf_counter() - start_r)
        return written, read, write_duration, read_duration
    finally:
        if handle:
            kernel32.CloseHandle(handle)
        kernel32.VirtualFree(buffer, 0, MEM_RELEASE)


def benchmark_ssd(
    target_dir: str | Path | None = None,
    size_mb: int = 96,
    *,
    progress_callback: ProgressCallback = None,
    stop_check: Optional[Callable[[], bool]] = None,
):
    """E/S secuencial real; en Windows prefiere I/O directo resistente a caché."""
    base = Path(target_dir) if target_dir else Path(tempfile.gettempdir())
    base.mkdir(parents=True, exist_ok=True)
    size_mb = _adaptive_ssd_size(size_mb, base)
    path = base / f'corepulse_bench_{os.getpid()}_{threading.get_ident()}_{time.time_ns()}.bin'
    chunk_mb = 4
    chunk_bytes = chunk_mb * 1024 * 1024
    total_chunks = max(1, size_mb // chunk_mb)
    actual_mb = total_chunks * chunk_mb
    direct_error = None
    try:
        if platform.system() == 'Windows':
            try:
                written, read, write_duration, read_duration = _benchmark_ssd_windows_uncached(
                    path, actual_mb, chunk_bytes, progress_callback, stop_check,
                )
                write_mb = written / (1024 * 1024)
                read_mb = read / (1024 * 1024)
                if callable(stop_check) and stop_check():
                    return _result(
                        'SSD', None, 'MB/s', 'CorePulse Windows unbuffered sequential I/O', write_duration + read_duration,
                        benchmark_method=SSD_METHOD_ID, write_mbps=(write_mb / write_duration) if write_duration else None,
                        read_mbps=(read_mb / read_duration) if read_duration and read_mb else None,
                        size_mb=write_mb, path_root=str(base.anchor or base), status='SAFETY_STOP',
                        io_mode='WINDOWS_NO_BUFFERING_WRITE_THROUGH', cache_resistant=True,
                    )
                return _result(
                    'SSD', write_mb / write_duration, 'MB/s write', 'CorePulse Windows unbuffered sequential I/O',
                    write_duration + read_duration, benchmark_method=SSD_METHOD_ID,
                    write_mbps=write_mb / write_duration, read_mbps=read_mb / read_duration,
                    size_mb=write_mb, path_root=str(base.anchor or base), status='OK',
                    io_mode='WINDOWS_NO_BUFFERING_WRITE_THROUGH', cache_resistant=True,
                )
            except Exception as exc:
                direct_error = f'{type(exc).__name__}: {exc}'

        # Fallback compatible: sigue siendo I/O real, pero se etiqueta como
        # potencialmente cacheable para no confundirlo con la ruta directa.
        chunk = os.urandom(chunk_bytes)
        write_start = time.perf_counter()
        written_bytes = 0
        with open(path, 'wb', buffering=0) as f:
            for index in range(total_chunks):
                written_bytes += f.write(chunk)
                if index % 4 == 0 or index + 1 == total_chunks:
                    _safe_progress(progress_callback, 0.48 * ((index + 1) / total_chunks), 'SSD · escritura secuencial', f'{(index + 1) * chunk_mb} / {actual_mb} MB')
                if callable(stop_check) and stop_check():
                    break
            f.flush(); os.fsync(f.fileno())
        write_duration = max(1e-6, time.perf_counter() - write_start)
        if callable(stop_check) and stop_check():
            return _result(
                'SSD', None, 'MB/s', 'CorePulse sequential file I/O', write_duration,
                benchmark_method=SSD_METHOD_ID, write_mbps=(written_bytes / (1024 * 1024)) / write_duration,
                read_mbps=None, size_mb=written_bytes / (1024 * 1024), path_root=str(base.anchor or base), status='SAFETY_STOP',
                io_mode='BUFFERED_FALLBACK', cache_resistant=False, direct_io_error=direct_error,
            )
        read_start = time.perf_counter(); total = 0
        with open(path, 'rb', buffering=0) as f:
            while True:
                data = f.read(chunk_bytes)
                if not data: break
                total += len(data)
                _safe_progress(progress_callback, 0.48 + 0.52 * min(1.0, total / max(1, actual_mb * 1024 * 1024)), 'SSD · lectura secuencial', f'{total / (1024 * 1024):.0f} / {actual_mb} MB')
                if callable(stop_check) and stop_check(): break
        read_duration = max(1e-6, time.perf_counter() - read_start)
        read_mb = total / (1024 * 1024)
        return _result(
            'SSD', actual_mb / write_duration, 'MB/s write', 'CorePulse sequential file I/O', write_duration + read_duration,
            benchmark_method=SSD_METHOD_ID, write_mbps=actual_mb / write_duration, read_mbps=read_mb / read_duration,
            size_mb=actual_mb, path_root=str(base.anchor or base), status='SAFETY_STOP' if callable(stop_check) and stop_check() else 'OK',
            io_mode='BUFFERED_FALLBACK', cache_resistant=False, direct_io_error=direct_error,
        )
    finally:
        try: path.unlink(missing_ok=True)
        except Exception: pass



def _median(values):
    vals = [float(v) for v in values if v is not None]
    return statistics.median(vals) if vals else None


def _cv_percent(values):
    vals = [float(v) for v in values if v is not None]
    if len(vals) < 2:
        return None
    mean = statistics.fmean(vals)
    if mean == 0:
        return 0.0
    return statistics.pstdev(vals) / abs(mean) * 100.0


def _map_local_progress(callback, start, end, prefix=''):
    span = max(0.0, float(end) - float(start))
    def mapped(frac, stage, detail=''):
        label = f'{prefix}{stage}' if prefix else stage
        _safe_progress(callback, float(start) + span * max(0.0, min(1.0, float(frac))), label, detail)
    return mapped


def _cpu_compression_samples(*, stop_check=None):
    """Tres muestras fijas de zlib. El contenido es determinista y se genera fuera del tiempo medido."""
    rng = random.Random(0xC0DE_2026)
    payload = rng.randbytes(8 * 1024 * 1024)
    comp_rates = []
    decomp_rates = []
    integrity = True
    for _ in range(3):
        if callable(stop_check) and stop_check():
            break
        t0 = time.perf_counter()
        compressed = zlib.compress(payload, 6)
        dt = max(1e-9, time.perf_counter() - t0)
        comp_rates.append((len(payload) / (1024 * 1024)) / dt)

        t0 = time.perf_counter()
        restored = zlib.decompress(compressed)
        dt = max(1e-9, time.perf_counter() - t0)
        decomp_rates.append((len(payload) / (1024 * 1024)) / dt)
        integrity = integrity and (restored == payload)
    return {
        'compression_mbps_samples': comp_rates,
        'compression_mbps': _median(comp_rates),
        'compression_cv_percent': _cv_percent(comp_rates),
        'decompression_mbps_samples': decomp_rates,
        'decompression_mbps': _median(decomp_rates),
        'decompression_cv_percent': _cv_percent(decomp_rates),
        'integrity_ok': bool(integrity and len(comp_rates) == 3 and len(decomp_rates) == 3),
        'payload_mb': 8,
        'algorithm': 'zlib level 6',
    }



def _na_area(reason: str, *, scope: str = ''):
    """Área declarada pero no inferida: REAL_OR_NA estricto."""
    return {
        'status': 'N/A', 'value': None, 'unit': '', 'reason': str(reason),
        'metric_scope': str(scope or 'NOT_MEASURED_NO_SUBSTITUTE'),
    }


def _cpu_image_pipeline_samples(*, stop_check=None):
    """Workload de aplicación real con Pillow.

    No se presenta como ALU/SIMD puro: mide un pipeline fijo de procesamiento de
    imagen (resize + blur + grayscale + autocontrast). El mismo buffer de entrada
    se usa en las 3 muestras y el SHA-256 de salida debe coincidir.
    """
    try:
        from PIL import Image, ImageFilter, ImageOps
    except Exception as exc:
        return {'status': 'UNAVAILABLE', 'reason': f'Pillow no disponible: {exc}'}
    width = height = 1024
    rng = random.Random(0x1A6E_2026)
    payload = rng.randbytes(width * height * 3)
    source = Image.frombytes('RGB', (width, height), payload)
    values = []
    hashes = []
    output_pixels = 1536 * 1536
    for _ in range(3):
        if callable(stop_check) and stop_check():
            break
        t0 = time.perf_counter()
        img = source.resize((1536, 1536), Image.Resampling.BILINEAR)
        img = img.filter(ImageFilter.GaussianBlur(radius=1.25))
        img = ImageOps.grayscale(img)
        img = ImageOps.autocontrast(img)
        out = img.tobytes()
        dt = max(1e-9, time.perf_counter() - t0)
        values.append((output_pixels / 1_000_000.0) / dt)
        hashes.append(hashlib.sha256(out).hexdigest())
    integrity = len(values) == 3 and len(set(hashes)) == 1
    return {
        'status': 'OK' if integrity else 'ERROR',
        'value': _median(values) if integrity else None,
        'unit': 'MPix/s',
        'samples': values,
        'cv_percent': _cv_percent(values),
        'integrity_ok': integrity,
        'pipeline': 'Pillow resize 1536² + GaussianBlur 1.25 + grayscale + autocontrast',
        'input_resolution': [width, height],
        'output_resolution': [1536, 1536],
        'metric_scope': 'APPLICATION_IMAGE_PIPELINE_NOT_PURE_ALU',
    }


def benchmark_cpu_v4(
    seconds: float = 12.0,
    *,
    progress_callback: ProgressCallback = None,
    stop_check: Optional[Callable[[], bool]] = None,
):
    """CPU V4: capacidades medibles reales + N/A explícito para áreas no aislables.

    Se evita llamar "integer", "FP" o "SIMD" a un bucle Python. Esas áreas quedan
    N/A hasta que CorePulse tenga un backend nativo que pueda aislarlas.
    """
    started = time.perf_counter()
    sample_seconds = max(1.0, min(4.0, float(seconds) * 0.18))
    rows = []
    for index in range(3):
        if callable(stop_check) and stop_check():
            break
        cb = _map_local_progress(progress_callback, index * 0.14, (index + 1) * 0.14, f'CPU SHA-256 {index + 1}/3 · ')
        row = benchmark_cpu(sample_seconds, progress_callback=cb, stop_check=stop_check)
        rows.append(row)
        if str(row.get('status') or '').upper() != 'OK':
            break
    valid = [r for r in rows if str(r.get('status') or '').upper() == 'OK']
    single = [r.get('single_thread_ops_s') for r in valid]
    multi = [r.get('multi_thread_ops_s') for r in valid]
    sha_mbps = [r.get('throughput_mbps') for r in valid]

    compression = {'integrity_ok': False}
    image = {'status': 'UNAVAILABLE', 'reason': 'No ejecutado'}
    if len(valid) == 3 and not (callable(stop_check) and stop_check()):
        _safe_progress(progress_callback, 0.45, 'CPU · compresión', 'zlib nivel 6 · 3 muestras · verificación posterior')
        compression = _cpu_compression_samples(stop_check=stop_check)
    if compression.get('integrity_ok') is True and not (callable(stop_check) and stop_check()):
        _safe_progress(progress_callback, 0.70, 'CPU · procesamiento de imagen', 'Pipeline Pillow fijo · 3 muestras')
        image = _cpu_image_pipeline_samples(stop_check=stop_check)
    _safe_progress(progress_callback, 0.98, 'CPU · verificando', 'Validando integridad y variación de cada área')

    stopped = callable(stop_check) and stop_check()
    required_ok = len(valid) == 3 and compression.get('integrity_ok') is True
    image_status = str(image.get('status') or '').upper()
    status = 'SAFETY_STOP' if stopped else ('OK' if required_ok else 'ERROR')
    cvs = [_cv_percent(single), _cv_percent(multi), _cv_percent(sha_mbps),
           compression.get('compression_cv_percent'), compression.get('decompression_cv_percent'),
           image.get('cv_percent')]
    variable = any(v is not None and float(v) > 12.0 for v in cvs)
    low_level_reason = 'No existe todavía un backend nativo universal que aísle esta unidad sin medir el intérprete Python; CorePulse no la estima.'
    subtests = {
        'single_thread_crypto': {'status': 'OK' if len(valid) == 3 else 'N/A', 'value': _median(single), 'unit': 'SHA256 ops/s', 'cv_percent': _cv_percent(single), 'metric_scope': 'SINGLE_THREAD_SHA256_NATIVE_HASHLIB'},
        'multi_thread_crypto': {'status': 'OK' if len(valid) == 3 else 'N/A', 'value': _median(multi), 'unit': 'SHA256 ops/s', 'cv_percent': _cv_percent(multi), 'metric_scope': 'MULTI_THREAD_SHA256_NATIVE_HASHLIB'},
        'sha256_throughput': {'status': 'OK' if len(valid) == 3 else 'N/A', 'value': _median(sha_mbps), 'unit': 'MB/s', 'cv_percent': _cv_percent(sha_mbps)},
        'compression': {'status': 'OK' if compression.get('integrity_ok') else 'N/A', 'value': compression.get('compression_mbps'), 'unit': 'MB/s', 'cv_percent': compression.get('compression_cv_percent'), 'algorithm': 'zlib level 6'},
        'decompression': {'status': 'OK' if compression.get('integrity_ok') else 'N/A', 'value': compression.get('decompression_mbps'), 'unit': 'MB/s', 'cv_percent': compression.get('decompression_cv_percent'), 'algorithm': 'zlib level 6'},
        'image_processing': {'status': image_status if image_status in {'OK','ERROR'} else 'N/A', 'value': image.get('value'), 'unit': image.get('unit') or 'MPix/s', 'cv_percent': image.get('cv_percent'), 'integrity_ok': image.get('integrity_ok'), 'pipeline': image.get('pipeline'), 'metric_scope': image.get('metric_scope')},
        'integer_alu_pure': _na_area(low_level_reason, scope='PURE_INTEGER_ALU_NOT_ISOLATED'),
        'floating_point_pure': _na_area(low_level_reason, scope='PURE_FLOAT_ALU_NOT_ISOLATED'),
        'simd_vector_pure': _na_area(low_level_reason, scope='PURE_SIMD_NOT_ISOLATED'),
        'cache_latency': _na_area('La latencia L1/L2/L3 requiere pointer-chasing nativo y afinidad/control de caché; no se infiere desde RAM ni clocks.', scope='CACHE_LATENCY_NATIVE_BACKEND_REQUIRED'),
    }
    reason = None
    if status == 'ERROR':
        reason = 'CPU V4 no completó las tres muestras requeridas o falló una verificación de integridad'
    result = _result(
        'CPU', _median(multi) if required_ok else None, 'SHA256 ops/s', 'CorePulse CPU Areas Benchmark V4', time.perf_counter()-started,
        benchmark_method=CPU_METHOD_ID, status=status, reason=reason, samples=3,
        single_thread_ops_s=_median(single), multi_thread_ops_s=_median(multi), throughput_mbps=_median(sha_mbps),
        threads=(valid[0].get('threads') if valid else None), compression=compression, image_processing=image,
        subtests=subtests, integrity_ok=bool(required_ok and (image_status in {'OK','UNAVAILABLE'})),
        measurement_quality='VARIABLE' if variable else 'STABLE',
        quality_warning=('Variación alta entre muestras; el resultado es real pero debe repetirse para confirmar estabilidad' if variable else None),
        coverage={'measured': ['single_thread_crypto','multi_thread_crypto','sha256_throughput','compression','decompression'] + (['image_processing'] if image_status=='OK' else []),
                  'not_evaluated': ['integer_alu_pure','floating_point_pure','simd_vector_pure','cache_latency']},
        policy='REAL_OR_NA_AREAS_NO_SYNTHETIC_ALU_LABELS_MEDIAN_3',
    )
    _safe_progress(progress_callback, 1.0, 'CPU V4 completado' if status in {'OK','PARTIAL'} else 'CPU V4 no evaluable', reason or 'Áreas reales medidas; áreas no aislables declaradas N/A')
    return result


def _ram_native_area_samples(size_mb: int, *, stop_check=None):
    """Mide memset y memmove nativos sobre buffers privados con verificación."""
    size_mb = max(32, min(512, int(size_mb)))
    size_bytes = size_mb * 1024 * 1024
    src = ctypes.create_string_buffer(size_bytes)
    dst = ctypes.create_string_buffer(size_bytes)
    src_addr = ctypes.addressof(src); dst_addr = ctypes.addressof(dst)
    ctypes.memset(src_addr, 0xA5, size_bytes)
    # Warm-up fuera del tiempo medido: fuerza commit/touch de páginas y evita
    # publicar la latencia de page-fault inicial como si fuera ancho de banda RAM.
    ctypes.memset(dst_addr, 0x11, size_bytes)
    ctypes.memmove(dst_addr, src_addr, size_bytes)
    writes=[]; copies=[]; integrity=True
    sent_offsets=(0, max(0,size_bytes//2-128), max(0,size_bytes-256))
    expected=b'\xA5'*256
    inner_rounds=max(4, min(32, int(512/max(1,size_mb))))
    for rep in range(3):
        if callable(stop_check) and stop_check():
            break
        t0=time.perf_counter()
        for inner in range(inner_rounds):
            ctypes.memset(dst_addr, (0x31 + rep + inner) & 0xFF, size_bytes)
        dt=max(1e-9,time.perf_counter()-t0)
        writes.append((size_mb*inner_rounds)/dt)
        t0=time.perf_counter()
        for _inner in range(inner_rounds):
            ctypes.memmove(dst_addr, src_addr, size_bytes)
        dt=max(1e-9,time.perf_counter()-t0)
        copies.append((size_mb*inner_rounds)/dt)
        integrity = integrity and all(ctypes.string_at(dst_addr+off,256)==expected for off in sent_offsets)
    return {
        'status':'OK' if integrity and len(writes)==3 and len(copies)==3 else 'ERROR',
        'write_mbps':_median(writes), 'write_samples':writes, 'write_cv_percent':_cv_percent(writes),
        'copy_mbps':_median(copies), 'copy_samples':copies, 'copy_cv_percent':_cv_percent(copies),
        'buffer_mb':size_mb, 'inner_rounds':inner_rounds, 'integrity_ok':bool(integrity and len(writes)==3 and len(copies)==3),
        'metric_scope':'NATIVE_MEMSET_AND_MEMMOVE_PRIVATE_BUFFERS',
    }


def benchmark_ram_v4(
    size_mb: int = 192,
    *,
    min_seconds: float = 8.0,
    progress_callback: ProgressCallback = None,
    stop_check: Optional[Callable[[], bool]] = None,
):
    """RAM V4: escritura nativa + copia nativa, ambas medianas de 3 muestras."""
    started=time.perf_counter()
    _safe_progress(progress_callback,0.05,'RAM · preparando',f'Reservando dos buffers de {size_mb} MB')
    try:
        native=_ram_native_area_samples(size_mb,stop_check=stop_check)
    except (MemoryError,OSError) as exc:
        native={'status':'ERROR','reason':f'{type(exc).__name__}: {exc}','integrity_ok':False}
    _safe_progress(progress_callback,0.92,'RAM · verificando','Comprobando sentinelas fuera de la ventana cronometrada')
    stopped=callable(stop_check) and stop_check()
    ok=str(native.get('status') or '').upper()=='OK' and native.get('integrity_ok') is True
    cvs=(native.get('write_cv_percent'),native.get('copy_cv_percent'))
    variable=any(v is not None and float(v)>10.0 for v in cvs)
    status='SAFETY_STOP' if stopped else ('OK' if ok else 'ERROR')
    subtests={
        'native_write_fill': {'status':'OK' if ok else 'N/A','value':native.get('write_mbps'),'unit':'MB/s','cv_percent':native.get('write_cv_percent'),'metric_scope':'NATIVE_MEMSET_WRITE'},
        'native_copy': {'status':'OK' if ok else 'N/A','value':native.get('copy_mbps'),'unit':'MB/s','cv_percent':native.get('copy_cv_percent'),'metric_scope':'NATIVE_MEMMOVE_READ_PLUS_WRITE'},
        'pure_read_bandwidth': _na_area('Una lectura pura universal sin copia/hash requiere backend nativo específico; no se deriva de memmove.', scope='PURE_READ_NATIVE_BACKEND_REQUIRED'),
        'latency': _na_area('La latencia requiere pointer-chasing nativo con control de optimización/caché; no se estima.', scope='RAM_LATENCY_NATIVE_BACKEND_REQUIRED'),
    }
    result=_result(
        'RAM',native.get('copy_mbps') if ok else None,'MB/s','CorePulse RAM Areas Benchmark V4',time.perf_counter()-started,
        benchmark_method=RAM_METHOD_ID,status=status,
        reason=(native.get('reason') if not ok else None),
        samples=3,bandwidth_mbps=native.get('copy_mbps'),write_mbps=native.get('write_mbps'),
        bandwidth_cv_percent=native.get('copy_cv_percent'),write_cv_percent=native.get('write_cv_percent'),
        buffer_mb=native.get('buffer_mb') or size_mb,integrity_ok=bool(ok),subtests=subtests,
        measurement_quality='VARIABLE' if variable else 'STABLE',
        quality_warning=('Variación alta entre muestras RAM; repetir en condiciones estables para confirmar' if variable else None),
        coverage={'measured':['native_write_fill','native_copy'],'not_evaluated':['pure_read_bandwidth','latency']},
        policy='REAL_OR_NA_NATIVE_MEMORY_AREAS_MEDIAN_3',
    )
    _safe_progress(progress_callback,1.0,'RAM V4 completado' if status in {'OK','PARTIAL'} else 'RAM V4 no evaluable','Escritura/copia nativa medidas; lectura pura y latencia quedan N/A')
    return result

def benchmark_cpu_v3(
    seconds: float = 12.0,
    *,
    progress_callback: ProgressCallback = None,
    stop_check: Optional[Callable[[], bool]] = None,
):
    """CPU Benchmark V3: tres muestras SHA-256 + compresión/descompresión verificadas."""
    started = time.perf_counter()
    sample_seconds = max(1.2, min(5.0, float(seconds) / 3.0))
    rows = []
    for index in range(3):
        if callable(stop_check) and stop_check():
            break
        cb = _map_local_progress(progress_callback, index * 0.20, (index + 1) * 0.20, f'CPU muestra {index + 1}/3 · ')
        row = benchmark_cpu(sample_seconds, progress_callback=cb, stop_check=stop_check)
        rows.append(row)
        if str(row.get('status') or '').upper() not in {'OK'}:
            break

    valid = [row for row in rows if str(row.get('status') or '').upper() == 'OK']
    compression = {'integrity_ok': False}
    if len(valid) == 3 and not (callable(stop_check) and stop_check()):
        _safe_progress(progress_callback, 0.62, 'CPU · compresión', '3 muestras zlib deterministas con verificación de contenido')
        compression = _cpu_compression_samples(stop_check=stop_check)
        _safe_progress(progress_callback, 0.98, 'CPU · compresión completada', 'Verificación post-test realizada')

    single = [row.get('single_thread_ops_s') for row in valid]
    multi = [row.get('multi_thread_ops_s') for row in valid]
    throughput = [row.get('throughput_mbps') for row in valid]
    ok = len(valid) == 3 and compression.get('integrity_ok') is True
    stopped = callable(stop_check) and stop_check()
    status = 'SAFETY_STOP' if stopped else ('OK' if ok else 'ERROR')
    reason = None
    if status == 'ERROR':
        reason = 'CPU V3 no obtuvo tres muestras válidas o falló una verificación de integridad'
    result = _result(
        'CPU', _median(multi) if ok else None, 'SHA256 ops/s', 'CorePulse CPU Diagnostic Benchmark V3',
        time.perf_counter() - started,
        benchmark_method=CPU_METHOD_ID,
        status=status,
        reason=reason,
        samples=3,
        single_thread_ops_s=_median(single),
        multi_thread_ops_s=_median(multi),
        throughput_mbps=_median(throughput),
        single_thread_cv_percent=_cv_percent(single),
        multi_thread_cv_percent=_cv_percent(multi),
        throughput_cv_percent=_cv_percent(throughput),
        threads=(valid[0].get('threads') if valid else None),
        sha256_samples=[{
            'single_thread_ops_s': row.get('single_thread_ops_s'),
            'multi_thread_ops_s': row.get('multi_thread_ops_s'),
            'throughput_mbps': row.get('throughput_mbps'),
            'duration_s': row.get('duration_s'),
        } for row in valid],
        compression=compression,
        integrity_ok=bool(ok),
        subtests={
            'single_thread_sha256': {'value': _median(single), 'unit': 'ops/s', 'cv_percent': _cv_percent(single)},
            'multi_thread_sha256': {'value': _median(multi), 'unit': 'ops/s', 'cv_percent': _cv_percent(multi)},
            'sha256_throughput': {'value': _median(throughput), 'unit': 'MB/s', 'cv_percent': _cv_percent(throughput)},
            'compression': {'value': compression.get('compression_mbps'), 'unit': 'MB/s', 'cv_percent': compression.get('compression_cv_percent')},
            'decompression': {'value': compression.get('decompression_mbps'), 'unit': 'MB/s', 'cv_percent': compression.get('decompression_cv_percent')},
        },
        measurement_quality=('VARIABLE' if any((v is not None and v > 12.0) for v in (_cv_percent(single), _cv_percent(multi), _cv_percent(throughput), compression.get('compression_cv_percent'), compression.get('decompression_cv_percent'))) else 'STABLE'),
        policy='FIXED_WORK_REAL_OR_NA_MEDIAN_3',
    )
    _safe_progress(progress_callback, 1.0, 'CPU V3 completado' if status == 'OK' else 'CPU V3 no evaluable', reason or '3 muestras + integridad verificadas')
    return result


def benchmark_ram_v3(
    size_mb: int = 192,
    *,
    min_seconds: float = 8.0,
    progress_callback: ProgressCallback = None,
    stop_check: Optional[Callable[[], bool]] = None,
):
    """RAM V3: tres ejecuciones reales de copia nativa, cada una con verificación byte a byte."""
    started = time.perf_counter()
    rows = []
    per_seconds = max(1.0, float(min_seconds) / 3.0)
    for index in range(3):
        if callable(stop_check) and stop_check():
            break
        cb = _map_local_progress(progress_callback, index / 3.0, (index + 1) / 3.0, f'RAM muestra {index + 1}/3 · ')
        row = benchmark_ram(size_mb, 3, min_seconds=per_seconds, progress_callback=cb, stop_check=stop_check)
        rows.append(row)
        if str(row.get('status') or '').upper() != 'OK' or row.get('integrity_ok') is not True:
            break
    valid = [row for row in rows if str(row.get('status') or '').upper() == 'OK' and row.get('integrity_ok') is True]
    vals = [row.get('value') for row in valid]
    ok = len(valid) == 3
    stopped = callable(stop_check) and stop_check()
    status = 'SAFETY_STOP' if stopped else ('OK' if ok else 'ERROR')
    result = _result(
        'RAM', _median(vals) if ok else None, 'MB/s', 'CorePulse RAM Native Copy V3', time.perf_counter() - started,
        benchmark_method=RAM_METHOD_ID,
        status=status,
        reason=None if ok else 'RAM V3 no obtuvo tres muestras verificadas',
        samples=3,
        bandwidth_mbps=_median(vals),
        bandwidth_cv_percent=_cv_percent(vals),
        buffer_mb=(valid[0].get('buffer_mb') if valid else size_mb),
        transferred_mb=sum(float(row.get('transferred_mb') or 0.0) for row in valid),
        rounds=sum(int(row.get('rounds') or 0) for row in valid),
        integrity_ok=ok,
        sample_values_mbps=vals,
        subtests={'native_copy': {'value': _median(vals), 'unit': 'MB/s', 'cv_percent': _cv_percent(vals)}},
        measurement_quality=('VARIABLE' if (_cv_percent(vals) is not None and _cv_percent(vals) > 10.0) else 'STABLE'),
        policy='REAL_NATIVE_COPY_MEDIAN_3_INTEGRITY_VERIFIED',
    )
    return result


def _benchmark_random4k_windows(base: Path, size_mb: int = 128, *, stop_check=None):
    """Random 4K QD1 real sobre archivo temporal. NO_BUFFERING + WRITE_THROUGH en Windows."""
    if platform.system() != 'Windows':
        return {'status': 'UNAVAILABLE', 'reason': 'Random 4K directo requiere Windows'}
    from ctypes import wintypes
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    GENERIC_READ, GENERIC_WRITE = 0x80000000, 0x40000000
    FILE_SHARE_READ, FILE_SHARE_WRITE, FILE_SHARE_DELETE = 1, 2, 4
    OPEN_EXISTING = 3
    FILE_FLAG_NO_BUFFERING = 0x20000000
    FILE_FLAG_WRITE_THROUGH = 0x80000000
    FILE_ATTRIBUTE_TEMPORARY = 0x00000100
    MEM_COMMIT, MEM_RESERVE, MEM_RELEASE, PAGE_READWRITE = 0x1000, 0x2000, 0x8000, 0x04
    INVALID = ctypes.c_void_p(-1).value

    kernel32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                                     wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.SetFilePointerEx.argtypes = [wintypes.HANDLE, ctypes.c_longlong, ctypes.POINTER(ctypes.c_longlong), wintypes.DWORD]
    kernel32.SetFilePointerEx.restype = wintypes.BOOL
    kernel32.ReadFile.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
    kernel32.ReadFile.restype = wintypes.BOOL
    kernel32.WriteFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
    kernel32.WriteFile.restype = wintypes.BOOL
    kernel32.FlushFileBuffers.argtypes = [wintypes.HANDLE]
    kernel32.FlushFileBuffers.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.VirtualAlloc.argtypes = [wintypes.LPVOID, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD]
    kernel32.VirtualAlloc.restype = wintypes.LPVOID
    kernel32.VirtualFree.argtypes = [wintypes.LPVOID, ctypes.c_size_t, wintypes.DWORD]
    kernel32.VirtualFree.restype = wintypes.BOOL

    base.mkdir(parents=True, exist_ok=True)
    path = base / f'corepulse_random4k_{os.getpid()}_{time.time_ns()}.bin'
    size_bytes = max(64, int(size_mb)) * 1024 * 1024
    chunk = bytes(random.Random(0x4B2026).randbytes(1024 * 1024))
    with open(path, 'wb', buffering=0) as f:
        remain = size_bytes
        while remain > 0:
            part = chunk[:min(len(chunk), remain)]
            f.write(part)
            remain -= len(part)
        f.flush(); os.fsync(f.fileno())

    buf = kernel32.VirtualAlloc(None, 4096, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE)
    if not buf:
        path.unlink(missing_ok=True)
        return {'status': 'ERROR', 'reason': 'VirtualAlloc 4K falló'}
    pattern = random.Random(0x5A17).randbytes(4096)
    ctypes.memmove(buf, pattern, 4096)
    flags = FILE_ATTRIBUTE_TEMPORARY | FILE_FLAG_NO_BUFFERING | FILE_FLAG_WRITE_THROUGH
    sharing = FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE
    handle = None
    try:
        handle = kernel32.CreateFileW(str(path), GENERIC_READ | GENERIC_WRITE, sharing, None, OPEN_EXISTING, flags, None)
        raw = handle if isinstance(handle, int) else ctypes.cast(handle, ctypes.c_void_p).value
        if raw in (None, INVALID):
            raise OSError(ctypes.get_last_error(), 'CreateFileW random4K falló')
        total_blocks = size_bytes // 4096
        offsets = [((i * 8191 + 127) % total_blocks) * 4096 for i in range(1024)]
        read_samples = []
        write_samples = []
        for rep in range(3):
            if callable(stop_check) and stop_check():
                break
            t0 = time.perf_counter()
            completed = 0
            for off in offsets:
                pos = ctypes.c_longlong(0)
                if not kernel32.SetFilePointerEx(handle, ctypes.c_longlong(off), ctypes.byref(pos), 0):
                    raise OSError(ctypes.get_last_error(), 'SetFilePointerEx lectura falló')
                done = wintypes.DWORD(0)
                if not kernel32.ReadFile(handle, buf, 4096, ctypes.byref(done), None) or done.value != 4096:
                    raise OSError(ctypes.get_last_error(), 'ReadFile 4K falló')
                completed += 1
            dt = max(1e-9, time.perf_counter() - t0)
            read_samples.append(completed / dt)

            ctypes.memmove(buf, pattern, 4096)
            t0 = time.perf_counter()
            completed = 0
            for off in offsets[:512]:
                pos = ctypes.c_longlong(0)
                if not kernel32.SetFilePointerEx(handle, ctypes.c_longlong(off), ctypes.byref(pos), 0):
                    raise OSError(ctypes.get_last_error(), 'SetFilePointerEx escritura falló')
                done = wintypes.DWORD(0)
                if not kernel32.WriteFile(handle, buf, 4096, ctypes.byref(done), None) or done.value != 4096:
                    raise OSError(ctypes.get_last_error(), 'WriteFile 4K falló')
                completed += 1
            if not kernel32.FlushFileBuffers(handle):
                raise OSError(ctypes.get_last_error(), 'FlushFileBuffers random4K falló')
            dt = max(1e-9, time.perf_counter() - t0)
            write_samples.append(completed / dt)
        # Verificación post-test fuera del tiempo medido: el primer bloque escrito
        # debe contener exactamente el patrón 4K usado por la prueba.
        integrity_ok = False
        if offsets:
            pos = ctypes.c_longlong(0)
            if kernel32.SetFilePointerEx(handle, ctypes.c_longlong(offsets[0]), ctypes.byref(pos), 0):
                done = wintypes.DWORD(0)
                if kernel32.ReadFile(handle, buf, 4096, ctypes.byref(done), None) and done.value == 4096:
                    integrity_ok = (ctypes.string_at(buf, 4096) == pattern)
        ok = len(read_samples) == 3 and len(write_samples) == 3 and integrity_ok
        return {
            'status': 'OK' if ok else 'PARTIAL',
            'read_iops': _median(read_samples), 'read_iops_samples': read_samples, 'read_cv_percent': _cv_percent(read_samples),
            'write_iops': _median(write_samples), 'write_iops_samples': write_samples, 'write_cv_percent': _cv_percent(write_samples),
            'block_bytes': 4096, 'queue_depth': 1, 'file_mb': size_bytes / (1024 * 1024),
            'integrity_ok': integrity_ok,
            'io_mode': 'WINDOWS_NO_BUFFERING_WRITE_THROUGH',
        }
    except Exception as exc:
        return {'status': 'ERROR', 'reason': f'{type(exc).__name__}: {exc}'}
    finally:
        try:
            if handle:
                kernel32.CloseHandle(handle)
        except Exception:
            pass
        try:
            kernel32.VirtualFree(buf, 0, MEM_RELEASE)
        except Exception:
            pass
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass


def benchmark_ssd_v3(
    target_dir: str | Path | None = None,
    size_mb: int = 256,
    *,
    progress_callback: ProgressCallback = None,
    stop_check: Optional[Callable[[], bool]] = None,
):
    """SSD V3: 3 muestras secuenciales + random 4K QD1 directo cuando Windows lo permite."""
    started = time.perf_counter()
    seq_rows = []
    # El tamaño por muestra se mantiene acotado para evitar convertir el benchmark en estrés.
    per_sample_mb = max(64, min(256, int(size_mb)))
    for index in range(3):
        if callable(stop_check) and stop_check():
            break
        cb = _map_local_progress(progress_callback, index * 0.22, (index + 1) * 0.22, f'SSD secuencial {index + 1}/3 · ')
        row = benchmark_ssd(target_dir, per_sample_mb, progress_callback=cb, stop_check=stop_check)
        seq_rows.append(row)
        if str(row.get('status') or '').upper() != 'OK':
            break
    valid = [row for row in seq_rows if str(row.get('status') or '').upper() == 'OK']
    writes = [row.get('write_mbps') for row in valid]
    reads = [row.get('read_mbps') for row in valid]

    base = Path(target_dir) if target_dir else Path(tempfile.gettempdir())
    random4k = {'status': 'UNAVAILABLE', 'reason': 'No ejecutado'}
    if len(valid) == 3 and not (callable(stop_check) and stop_check()):
        _safe_progress(progress_callback, 0.70, 'SSD · Random 4K QD1', 'Lectura/escritura 4 KiB directa, 3 muestras')
        random4k = _benchmark_random4k_windows(base, 128, stop_check=stop_check)
        _safe_progress(progress_callback, 0.98, 'SSD · Random 4K completado', f"Estado {random4k.get('status')}")

    seq_ok = len(valid) == 3
    random_ok = str(random4k.get('status') or '').upper() == 'OK'
    stopped = callable(stop_check) and stop_check()
    write_cv = _cv_percent(writes)
    read_cv = _cv_percent(reads)
    random_read_cv = random4k.get('read_cv_percent')
    random_write_cv = random4k.get('write_cv_percent')
    variable = any(v is not None and float(v) > 15.0 for v in (write_cv, read_cv, random_read_cv, random_write_cv))
    status = 'SAFETY_STOP' if stopped else ('PARTIAL' if seq_ok and variable else ('OK' if seq_ok and (random_ok or platform.system() != 'Windows') else 'PARTIAL' if seq_ok else 'ERROR'))
    write_med = _median(writes)
    read_med = _median(reads)
    return _result(
        'SSD', write_med if seq_ok else None, 'MB/s write', 'CorePulse SSD Diagnostic Benchmark V3', time.perf_counter() - started,
        benchmark_method=SSD_METHOD_ID,
        status=status,
        reason=(None if status == 'OK' else ('Variación alta entre muestras SSD; el resultado se conserva como evidencia pero no se considera estable' if variable else (random4k.get('reason') if seq_ok else 'SSD V3 no obtuvo tres muestras secuenciales válidas'))),
        samples=3,
        write_mbps=write_med,
        read_mbps=read_med,
        write_cv_percent=write_cv,
        read_cv_percent=read_cv,
        sequential_samples=[{'write_mbps': r.get('write_mbps'), 'read_mbps': r.get('read_mbps'), 'io_mode': r.get('io_mode'), 'cache_resistant': r.get('cache_resistant')} for r in valid],
        size_mb=per_sample_mb,
        path_root=(valid[0].get('path_root') if valid else str(base.anchor or base)),
        io_mode=(valid[0].get('io_mode') if valid else 'N/A'),
        cache_resistant=all(r.get('cache_resistant') is True for r in valid) if valid else False,
        random_4k=random4k,
        random4k_read_iops=random4k.get('read_iops'),
        random4k_write_iops=random4k.get('write_iops'),
        subtests={
            'sequential_write': {'value': write_med, 'unit': 'MB/s', 'cv_percent': write_cv},
            'sequential_read': {'value': read_med, 'unit': 'MB/s', 'cv_percent': read_cv},
            'random_4k_read_qd1': {'value': random4k.get('read_iops'), 'unit': 'IOPS', 'cv_percent': random4k.get('read_cv_percent')},
            'random_4k_write_qd1': {'value': random4k.get('write_iops'), 'unit': 'IOPS', 'cv_percent': random4k.get('write_cv_percent')},
        },
        measurement_quality=('VARIABLE' if variable else 'STABLE'),
        policy='DIRECT_IO_WHEN_AVAILABLE_MEDIAN_3_REAL_OR_NA',
    )



def benchmark_ssd_v4(
    target_dir: str | Path | None = None,
    size_mb: int = 256,
    *,
    progress_callback: ProgressCallback = None,
    stop_check: Optional[Callable[[], bool]] = None,
):
    """SSD V4: secuencial R/W + Random 4K QD1 R/W con Direct I/O cuando Windows lo permite."""
    row=benchmark_ssd_v3(target_dir,size_mb,progress_callback=progress_callback,stop_check=stop_check)
    row=dict(row or {})
    if str(row.get('status') or '').upper() == 'PARTIAL' and str(row.get('reason') or '').startswith('Variación alta'):
        row['status'] = 'OK'
        row['quality_warning'] = str(row.get('reason') or '')
        row['reason'] = None
    row['benchmark_method']=SSD_METHOD_ID
    row['provider']='CorePulse SSD Areas Benchmark V4'
    sub=dict(row.get('subtests') or {})
    random4k=row.get('random_4k') if isinstance(row.get('random_4k'),dict) else {}
    # Latencia derivada directamente de IOPS cuando la prueba QD1 existe (1/IOPS), no estimada por modelo.
    riops=_float(random4k.get('read_iops')); wiops=_float(random4k.get('write_iops'))
    sub['random_4k_read_latency_qd1']={'status':'OK' if riops else 'N/A','value':(1000.0/riops if riops else None),'unit':'ms/op','metric_scope':'DERIVED_FROM_MEASURED_QD1_IOPS'}
    sub['random_4k_write_latency_qd1']={'status':'OK' if wiops else 'N/A','value':(1000.0/wiops if wiops else None),'unit':'ms/op','metric_scope':'DERIVED_FROM_MEASURED_QD1_IOPS'}
    row['subtests']=sub
    row['coverage']={'measured':['sequential_write','sequential_read'] + (['random_4k_read_qd1','random_4k_write_qd1','random_4k_read_latency_qd1','random_4k_write_latency_qd1'] if riops and wiops else []),
                     'not_evaluated':([] if riops and wiops else ['random_4k_direct_io'])}
    row['policy']='DIRECT_IO_WHEN_AVAILABLE_REAL_OR_NA_MEDIAN_3_V4'
    return row

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


def _visual_gpu_result(profile, *, progress_callback=None, telemetry_sampler=None, cancel_check=None):
    """Benchmark GPU V20: escenas DirectX 11 visibles, reloj de pared determinista y timestamp GPU real.

    No existe fallback silencioso al renderer OpenGL anterior: si DirectX 11 no
    puede inicializarse, GPU queda N/A/ERROR para no mezclar metodologías.
    """
    from core.directx_benchmark import run_directx_benchmark
    raw = run_directx_benchmark(
        profile, width=1920, height=1080, visible=True,
        progress_callback=progress_callback, telemetry_sampler=telemetry_sampler,
        cancel_check=cancel_check,
    )
    raw = raw if isinstance(raw, dict) else {}
    status = str(raw.get('status') or 'ERROR').upper()
    scenes = raw.get('scenes') if isinstance(raw.get('scenes'), list) else []
    scene_results = []
    for scene in scenes:
        row = dict(scene) if isinstance(scene, dict) else {}
        work = row.get('workload') if isinstance(row.get('workload'), dict) else {}
        fps = _float(row.get('frames_per_s'))
        triangles = _float(work.get('approx_triangles_per_frame'))
        if fps is not None and triangles is not None:
            row['throughput_value'] = triangles * fps / 1_000_000.0
            row['throughput_unit'] = 'Mtri/s aprox. escena'
        scene_results.append(row)
    return _result(
        'GPU', _float(raw.get('value')), str(raw.get('unit') or 'FPS'),
        str(raw.get('provider') or GPU_PROVIDER),
        _float(raw.get('duration_s')) or 0.0,
        benchmark_method=GPU_METHOD_ID, status=status, reason=raw.get('reason'),
        benchmark_mode=f'DIRECTX11_REALISTIC_VALLEY_{GPU_BENCHMARK_LABEL}_WALLCLOCK_DETERMINISTIC_GPU_TIMESTAMP',
        renderer=raw.get('renderer'), api=raw.get('api'), feature_level=raw.get('feature_level'),
        dedicated_vram_mb=raw.get('dedicated_vram_mb'), resolution=raw.get('resolution'),
        vsync_disabled=raw.get('vsync_disabled'), primary_scene=raw.get('primary_scene'),
        frames_per_s=_float(raw.get('frames_per_s')), one_percent_low_fps=_float(raw.get('one_percent_low_fps')),
        fps_1pct_low=_float(raw.get('one_percent_low_fps')), frametime_avg_ms=_float(raw.get('frametime_avg_ms')),
        frametime_median_ms=_float(raw.get('frametime_median_ms')), frametime_p95_ms=_float(raw.get('frametime_p95_ms')), frametime_p99_ms=_float(raw.get('frametime_p99_ms')),
        frametime_spike_frames=raw.get('frametime_spike_frames'), frametime_spike_ratio=_float(raw.get('frametime_spike_ratio')),
        gpu_frame_time_avg_ms=_float(raw.get('gpu_frame_time_avg_ms')), gpu_frame_time_p95_ms=_float(raw.get('gpu_frame_time_p95_ms')),
        gpu_frame_time_p99_ms=_float(raw.get('gpu_frame_time_p99_ms')), gpu_timestamp_samples=raw.get('gpu_timestamp_samples'),
        gpu_timestamp_coverage=_float(raw.get('gpu_timestamp_coverage')), gpu_timing_available=raw.get('gpu_timing_available'),
        gpu_timing_reason=raw.get('gpu_timing_reason'),
        scene_results=scene_results, scenes=scene_results, phase_results=scene_results,
        subtests={
            **{str(row.get('key')): {
                'label': row.get('label'), 'status': row.get('status'), 'fps': row.get('frames_per_s'),
                'one_percent_low_fps': row.get('one_percent_low_fps'), 'frametime_avg_ms': row.get('frametime_avg_ms'),
                'frametime_median_ms': row.get('frametime_median_ms'), 'frametime_p95_ms': row.get('frametime_p95_ms'), 'frametime_p99_ms': row.get('frametime_p99_ms'),
                'frametime_spike_frames': row.get('frametime_spike_frames'), 'frametime_spike_ratio': row.get('frametime_spike_ratio'),
                'gpu_frame_time_avg_ms': row.get('gpu_frame_time_avg_ms'), 'gpu_frame_time_p95_ms': row.get('gpu_frame_time_p95_ms'),
                'gpu_frame_time_p99_ms': row.get('gpu_frame_time_p99_ms'), 'gpu_samples': row.get('gpu_samples'),
                'gpu_sample_coverage': row.get('gpu_sample_coverage'), 'workload': row.get('workload'),
                'metric_scope': 'MEASURED_DIRECTX11_SCENE_CPU_AND_GPU_TIMESTAMPS'
            } for row in scene_results if row.get('key')},
            'gpu_buffer_copy': {'label': 'GPU buffer copy', 'status': 'N/A', 'value': None, 'reason': 'V20 no aísla ancho de banda VRAM con un workload independiente validado'},
            'ray_tracing': {'label': 'Ray Tracing', 'status': 'N/A', 'value': None, 'reason': 'DirectX 11 no expone DXR; no se infiere por modelo'},
            'mesh_shaders': {'label': 'Mesh Shaders', 'status': 'N/A', 'value': None, 'reason': 'No medido por el backend D3D11 V20'},
            'ai_matrix': {'label': 'AI / Matrix', 'status': 'N/A', 'value': None, 'reason': 'No existe subprueba nativa validada en V20'},
        },
        telemetry_samples=raw.get('telemetry_samples') if isinstance(raw.get('telemetry_samples'), list) else [],
        startup_stage=raw.get('startup_stage'), startup_checks=raw.get('startup_checks') if isinstance(raw.get('startup_checks'), list) else [],
        failure_stage=raw.get('failure_stage'),
        coverage={'measured': [row.get('key') for row in scene_results if str(row.get('status') or '').upper() == 'OK'],
                  'not_evaluated': ['gpu_buffer_copy', 'ray_tracing', 'mesh_shaders', 'ai_matrix'],
                  'backend': 'DIRECT3D11'},
        policy=GPU_POLICY,
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

        reporter.begin(key)
        if reporter.stop_reason or cancelled():
            results[key] = _not_run(key.upper(), 'Cancelado por el usuario' if cancelled() else reporter.stop_reason)
            results[key]['status'] = 'CANCELLED' if cancelled() else 'SAFETY_STOP'
            reporter.finish(results[key])
            continue
        start_fraction, end_fraction = span_for(key)
        callback = _map_progress(reporter, start_fraction, end_fraction)
        try:
            if key == 'cpu':
                results[key] = benchmark_cpu_v4(
                    profile_data['cpu_seconds'],
                    progress_callback=callback,
                    stop_check=should_stop,
                )
            elif key == 'ram':
                results[key] = benchmark_ram_v4(
                    _adaptive_ram_size(profile_data['ram_size_cap_mb']),
                    min_seconds=profile_data['ram_seconds'],
                    progress_callback=callback,
                    stop_check=should_stop,
                )
            elif key == 'ssd':
                results[key] = benchmark_ssd_v4(
                    ssd_dir, profile_data['ssd_size_mb'],
                    progress_callback=callback,
                    stop_check=should_stop,
                )
            elif key == 'gpu':
                # V181: el renderer GPU debe obedecer también el SAFETY_STOP térmico
                # detectado por el reporter. `cancelled()` por sí solo sólo cubría al
                # usuario y podía dejar la escena terminar aunque la telemetría ya
                # hubiera activado una parada de seguridad.
                results[key] = _visual_gpu_result(
                    profile_data['key'], progress_callback=callback, telemetry_sampler=telemetry_sampler,
                    cancel_check=should_stop,
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

    duration = time.perf_counter() - started
    suite_result = {
        'started_at': started_wall,
        'finished_at': time.time(),
        'duration_s': duration,
        'profile': profile_data['key'].upper(),
        'profile_label': profile_data['label'],
        'benchmark_method': BENCHMARK_METHOD_ID,
        'component_methods': {'cpu': CPU_METHOD_ID, 'ram': RAM_METHOD_ID, 'ssd': SSD_METHOD_ID, 'gpu': GPU_METHOD_ID},
        'selected_components': selected,
        'cpu': results['cpu'],
        'ram': results['ram'],
        'ssd': results['ssd'],
        'gpu': results['gpu'],
        'telemetry_summary': reporter.summary(),
        'safety_stop': reporter.stop_reason,
        'cancelled': cancelled(),
        'status': 'CANCELLED' if cancelled() else ('SAFETY_STOP' if reporter.stop_reason else 'PARTIAL' if any(results[k].get('status') != 'OK' for k in selected) else 'OK'),
        'policy': f'REAL_OR_NA_BENCHMARK_{GPU_BENCHMARK_LABEL}_WALLCLOCK_GPU_TIMESTAMP_NO_REFERENCE_RANKING',
    }
    gpu_result = results.get('gpu') if 'gpu' in selected else None
    if (
        isinstance(gpu_result, dict)
        and str(gpu_result.get('status') or '').upper() == 'OK'
        and not suite_result['cancelled']
        and not suite_result['safety_stop']
    ):
        try:
            saved_path = save_last_gpu_v25_result(gpu_result)
            suite_result['gpu_result_saved'] = True
            suite_result['gpu_result_path'] = str(saved_path)
        except Exception as exc:
            suite_result['gpu_result_saved'] = False
            suite_result['gpu_result_save_error'] = f'{type(exc).__name__}: {exc}'
    final_detail = (
        f"Resultado GPU guardado en: {suite_result['gpu_result_path']}"
        if suite_result.get('gpu_result_saved')
        else 'Resultados medidos durante esta ejecución'
    )
    _safe_progress(progress_callback, 1.0, 'Benchmark cancelado' if cancelled() else 'Benchmark interrumpido por seguridad' if reporter.stop_reason else 'Benchmark finalizado', final_detail)
    return suite_result


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
        'benchmark_method': 'COREPULSE_LEGACY_SHORT_BENCHMARK',
        'policy': 'LOCAL_SHORT_BENCHMARK_NO_REFERENCE_RANKING',
    }
