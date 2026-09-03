"""Benchmarks cortos, explícitos y locales de CorePulse.

CPU/RAM/SSD son pruebas propias. GPU usa WinSAT D3D en Windows cuando existe;
si no hay proveedor real, devuelve N/A en lugar de fabricar un score.
"""
from __future__ import annotations

import hashlib
import os
import platform
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Dict


def _result(kind, value=None, unit='', provider='', duration_s=None, **extra):
    return {'kind': kind, 'value': value, 'unit': unit, 'provider': provider, 'duration_s': duration_s, 'timestamp': time.time(), **extra}


def benchmark_cpu(seconds: float = 2.0):
    seconds = max(0.5, min(8.0, float(seconds)))
    block = b'CorePulse benchmark' * 4096
    count = 0
    start = time.perf_counter()
    end = start + seconds
    digest = b''
    while time.perf_counter() < end:
        digest = hashlib.sha256(block + digest).digest()
        count += 1
    duration = time.perf_counter() - start
    return _result('CPU', count / duration, 'SHA256 ops/s', 'CorePulse SHA-256 workload', duration, iterations=count)


def benchmark_ram(size_mb: int = 128, rounds: int = 4):
    size_mb = max(32, min(512, int(size_mb)))
    rounds = max(1, min(10, int(rounds)))
    src = bytearray(os.urandom(size_mb * 1024 * 1024))
    start = time.perf_counter()
    checksum = 0
    for _ in range(rounds):
        dst = bytearray(src)
        checksum ^= dst[0] if dst else 0
    duration = time.perf_counter() - start
    total_mb = size_mb * rounds
    return _result('RAM', total_mb / duration, 'MB/s', 'CorePulse memory copy', duration, transferred_mb=total_mb, checksum=checksum)


def benchmark_ssd(target_dir: str | Path | None = None, size_mb: int = 96):
    size_mb = max(32, min(512, int(size_mb)))
    base = Path(target_dir) if target_dir else Path(tempfile.gettempdir())
    base.mkdir(parents=True, exist_ok=True)
    path = base / f'corepulse_bench_{os.getpid()}_{int(time.time())}.bin'
    chunk = os.urandom(1024 * 1024)
    write_start = time.perf_counter()
    try:
        with open(path, 'wb', buffering=0) as f:
            for _ in range(size_mb):
                f.write(chunk)
            f.flush()
            os.fsync(f.fileno())
        write_duration = time.perf_counter() - write_start
        read_start = time.perf_counter()
        total = 0
        with open(path, 'rb', buffering=0) as f:
            while True:
                data = f.read(4 * 1024 * 1024)
                if not data:
                    break
                total += len(data)
        read_duration = time.perf_counter() - read_start
        return _result('SSD', size_mb / write_duration, 'MB/s write', 'CorePulse sequential file I/O', write_duration + read_duration,
                       write_mbps=size_mb / write_duration, read_mbps=(total / (1024*1024)) / read_duration, size_mb=size_mb, path_root=str(base.anchor or base))
    finally:
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass


def benchmark_gpu(timeout: int = 30):
    if platform.system() != 'Windows':
        return _result('GPU', None, 'score', 'N/A', 0, status='UNAVAILABLE', reason='WinSAT sólo está disponible en Windows')
    exe = Path(os.environ.get('WINDIR', r'C:\Windows')) / 'System32' / 'winsat.exe'
    if not exe.exists():
        return _result('GPU', None, 'score', 'N/A', 0, status='UNAVAILABLE', reason='WinSAT no disponible')
    start = time.perf_counter()
    try:
        cp = subprocess.run([str(exe), 'd3d', '-time', '3'], capture_output=True, text=True, timeout=max(10, int(timeout)), creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        text = (cp.stdout or '') + '\n' + (cp.stderr or '')
        duration = time.perf_counter() - start
        # WinSAT cambia formato según idioma. Conservamos todas las métricas numéricas detectables.
        metrics = []
        for line in text.splitlines():
            if any(k in line.lower() for k in ('fps', 'frames', 'score', 'rendimiento', 'performance')):
                nums = re.findall(r'(?<![A-Za-z])\d+(?:[\.,]\d+)?', line)
                if nums:
                    metrics.append({'line': line.strip()[:180], 'value': nums[-1]})
        value = None
        if metrics:
            try:
                value = float(str(metrics[-1]['value']).replace(',', '.'))
            except Exception:
                value = None
        return _result('GPU', value, 'WinSAT metric', 'Windows WinSAT D3D', duration, status='OK' if cp.returncode == 0 else 'ERROR', returncode=cp.returncode, metrics=metrics[:20])
    except Exception as exc:
        return _result('GPU', None, 'score', 'Windows WinSAT D3D', time.perf_counter()-start, status='ERROR', reason=str(exc))


def run_quick_suite(ssd_dir=None):
    return {
        'started_at': time.time(),
        'cpu': benchmark_cpu(),
        'ram': benchmark_ram(),
        'ssd': benchmark_ssd(ssd_dir),
        'gpu': benchmark_gpu(),
        'policy': 'LOCAL_SHORT_BENCHMARK_NO_REFERENCE_RANKING',
    }
