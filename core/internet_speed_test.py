"""Prueba activa de velocidad de Internet para CorePulse.

Usa los endpoints públicos de medición de Cloudflare Speed Test:
  GET  https://speed.cloudflare.com/__down?bytes=N
  POST https://speed.cloudflare.com/__up

La medición es ACTIVA: transfiere datos reales por Internet. No confundir con
NetworkTrafficSampler, que únicamente observa el tráfico actual del adaptador.

Diseño:
- Latencia/jitter sin carga mediante requests bytes=0 sobre una conexión HTTPS.
- Ramp-up de descarga/subida con 4 flujos paralelos para saturar conexiones
  rápidas de forma más parecida a herramientas de speed test.
- Se detiene una dirección cuando una etapa supera ~1.2 s, evitando transferir
  archivos enormes innecesariamente.
- REAL_OR_NA: si una fase falla, el valor queda None; no se estima.
"""
from __future__ import annotations

import concurrent.futures
import http.client
import json
import math
import statistics
import time
import uuid
from dataclasses import dataclass
from typing import Callable
from urllib.request import Request, urlopen

HOST = 'speed.cloudflare.com'
BASE_URL = f'https://{HOST}'
DOWNLOAD_PATH = '/__down'
UPLOAD_PATH = '/__up'
META_URL = f'{BASE_URL}/meta'
USER_AGENT = 'CorePulse-NetworkTest/0.9'

# 4 flujos. En el peor caso ronda ~315 MB entre ambas direcciones.
DOWNLOAD_STAGES = (250_000, 1_000_000, 5_000_000, 12_500_000, 25_000_000)
UPLOAD_STAGES = (100_000, 500_000, 2_000_000, 5_000_000, 10_000_000, 25_000_000)
DEFAULT_STREAMS = 4
TARGET_STAGE_SECONDS = 1.20


def _num(value):
    try:
        if value is None or isinstance(value, bool):
            return None
        return float(value)
    except Exception:
        return None


def _percentile(values, p=0.90):
    clean = sorted(float(v) for v in values if _num(v) is not None and float(v) >= 0)
    if not clean:
        return None
    if len(clean) == 1:
        return clean[0]
    pos = (len(clean) - 1) * max(0.0, min(1.0, float(p)))
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return clean[lo]
    frac = pos - lo
    return clean[lo] * (1.0 - frac) + clean[hi] * frac


def _safe_progress(callback, **payload):
    if not callable(callback):
        return
    try:
        callback(dict(payload))
    except Exception:
        pass


def _server_timing_seconds(headers):
    """Extrae Server-Timing `dur` de Cloudflare (milisegundos -> segundos)."""
    try:
        raw = str(headers.get('Server-Timing') or headers.get('server-timing') or '')
    except Exception:
        raw = ''
    if not raw:
        return None
    import re
    match = re.search(r'(?:^|[;,\s])dur=([0-9]+(?:\.[0-9]+)?)', raw, re.I)
    if not match:
        # Compatibilidad con cabeceras simples del endpoint de medición.
        match = re.search(r'=([0-9]+(?:\.[0-9]+)?)', raw)
    if not match:
        return None
    try:
        value_ms = float(match.group(1))
        return value_ms / 1000.0 if value_ms >= 0 else None
    except Exception:
        return None


def _metadata(timeout=5):
    try:
        req = Request(META_URL, headers={'User-Agent': USER_AGENT, 'Cache-Control': 'no-cache'})
        with urlopen(req, timeout=timeout) as response:
            raw = response.read(128 * 1024)
        data = json.loads(raw.decode('utf-8', errors='replace'))
        if not isinstance(data, dict):
            return {}
        return {
            'client_ip': data.get('clientIp'),
            'asn': data.get('asn'),
            'isp': data.get('asOrganization'),
            'colo': data.get('colo'),
            'country': data.get('country'),
            'city': data.get('city'),
            'region': data.get('region'),
        }
    except Exception:
        return {}


def _latency_series(count=10, timeout=4):
    """Mide TTFB repetido sobre una conexión TLS persistente."""
    samples = []
    conn = None
    try:
        conn = http.client.HTTPSConnection(HOST, timeout=timeout)
        conn.connect()  # DNS/TCP/TLS fuera de las muestras de RTT.
        for _ in range(max(1, int(count))):
            path = f'{DOWNLOAD_PATH}?bytes=0&r={uuid.uuid4().hex}'
            started = time.perf_counter()
            try:
                conn.request('GET', path, headers={
                    'User-Agent': USER_AGENT,
                    'Cache-Control': 'no-cache, no-store',
                    'Accept': 'application/octet-stream',
                })
                response = conn.getresponse()
                elapsed = (time.perf_counter() - started) * 1000.0
                response.read()
                if 200 <= response.status < 400:
                    samples.append(elapsed)
                else:
                    break
            except Exception:
                break
    except Exception:
        samples = []
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass
    if not samples:
        return {'latency_ms': None, 'jitter_ms': None, 'samples_ms': []}
    latency = statistics.median(samples)
    jitter = None
    if len(samples) >= 2:
        diffs = [abs(samples[i] - samples[i - 1]) for i in range(1, len(samples))]
        jitter = sum(diffs) / len(diffs) if diffs else None
    return {
        'latency_ms': round(latency, 2),
        'jitter_ms': round(jitter, 2) if jitter is not None else None,
        'samples_ms': [round(v, 2) for v in samples],
    }


def _download_one(size, timeout=30):
    url = f'{BASE_URL}{DOWNLOAD_PATH}?bytes={int(size)}&r={uuid.uuid4().hex}'
    req = Request(url, headers={
        'User-Agent': USER_AGENT,
        'Cache-Control': 'no-cache, no-store',
        'Accept': 'application/octet-stream',
        'Connection': 'close',
    })
    started = time.perf_counter()
    total = 0
    try:
        server_seconds = None
        with urlopen(req, timeout=timeout) as response:
            server_seconds = _server_timing_seconds(response.headers)
            while True:
                chunk = response.read(256 * 1024)
                if not chunk:
                    break
                total += len(chunk)
        duration = max(1e-6, time.perf_counter() - started)
        network_seconds = max(1e-6, duration - server_seconds) if server_seconds is not None and server_seconds < duration else duration
        bps = total * 8.0 / network_seconds if total > 0 else None
        return {'ok': total > 0, 'bytes': total, 'seconds': duration, 'server_seconds': server_seconds, 'bps': bps}
    except Exception as exc:
        return {'ok': False, 'bytes': total, 'seconds': max(1e-6, time.perf_counter() - started), 'error': str(exc)[:180]}


def _upload_one(size, timeout=30):
    """POST en streaming y mide el tiempo real de transferencia del cliente.

    ``Server-Timing`` NO es el tiempo de subida. Cloudflare lo expone para que
    el tiempo de procesamiento del edge se reste de la duración de la petición.
    Usarlo directamente como denominador puede producir velocidades físicamente
    imposibles (decenas de Gbps sobre un enlace Wi-Fi de pocos Gbps).
    """
    conn = None
    started = None
    sent = 0
    try:
        conn = http.client.HTTPSConnection(HOST, timeout=timeout)
        # DNS/TCP/TLS quedan fuera del reloj de transferencia, igual que el
        # warm connection utilizado en una prueba de velocidad real.
        conn.connect()
        path = f'{UPLOAD_PATH}?r={uuid.uuid4().hex}'
        conn.putrequest('POST', path)
        conn.putheader('User-Agent', USER_AGENT)
        conn.putheader('Content-Type', 'application/octet-stream')
        conn.putheader('Content-Length', str(int(size)))
        conn.putheader('Cache-Control', 'no-cache, no-store')
        conn.putheader('Connection', 'close')
        conn.endheaders()

        block = b'\0' * (256 * 1024)
        remaining = int(size)
        started = time.perf_counter()
        while remaining > 0:
            piece = block if remaining >= len(block) else block[:remaining]
            conn.send(piece)
            sent += len(piece)
            remaining -= len(piece)

        # __up responde una vez recibido el body. Esperar los headers evita
        # confundir el vaciado del buffer local con datos realmente entregados.
        response = conn.getresponse()
        response_received = time.perf_counter()
        server_seconds = _server_timing_seconds(response.headers)
        response.read()
        duration = max(1e-6, response_received - started)

        # Cloudflare define bandwidth = transferSize / requestDuration, con el
        # procesamiento del servidor excluido. Nunca se divide por Server-Timing.
        network_seconds = duration
        if server_seconds is not None and 0 <= server_seconds < duration:
            network_seconds = max(1e-6, duration - server_seconds)
        bps = sent * 8.0 / network_seconds if sent > 0 else None
        return {
            'ok': 200 <= response.status < 400 and sent > 0,
            'bytes': sent,
            'seconds': duration,
            'network_seconds': network_seconds,
            'server_seconds': server_seconds,
            'bps': bps,
            'status': response.status,
        }
    except Exception as exc:
        return {'ok': False, 'bytes': sent, 'seconds': max(1e-6, time.perf_counter() - started), 'error': str(exc)[:180]}
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass


def _parallel_stage(direction, size, streams=DEFAULT_STREAMS, timeout=35):
    worker = _download_one if direction == 'download' else _upload_one
    started = time.perf_counter()
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, int(streams)), thread_name_prefix='CorePulseSpeed') as pool:
        futures = [pool.submit(worker, int(size), timeout) for _ in range(max(1, int(streams)))]
        for future in concurrent.futures.as_completed(futures):
            try:
                results.append(future.result())
            except Exception as exc:
                results.append({'ok': False, 'bytes': 0, 'error': str(exc)[:180]})
    elapsed = max(1e-6, time.perf_counter() - started)
    good = [r for r in results if isinstance(r, dict) and r.get('ok')]
    total_bytes = sum(max(0, int(r.get('bytes') or 0)) for r in good)
    # La capacidad agregada de una etapa paralela es bytes totales / tiempo de
    # pared de la etapa. Sumar tasas individuales puede inflar el resultado si
    # sus relojes no cubren exactamente la misma ventana (especialmente upload).
    # Este cálculo conserva el beneficio de los streams paralelos sin doble
    # contabilizar tiempo ni depender de Server-Timing por conexión.
    bps = (total_bytes * 8.0 / elapsed) if total_bytes > 0 else None
    mbps = bps / 1_000_000.0 if bps is not None else None
    return {
        'direction': direction,
        'size_per_stream': int(size),
        'streams': int(streams),
        'successful_streams': len(good),
        'bytes': total_bytes,
        'seconds': elapsed,
        'mbps': round(mbps, 3) if mbps is not None else None,
        'ok': bool(good),
        'errors': [r.get('error') for r in results if isinstance(r, dict) and r.get('error')][:4],
    }


def _measure_direction(direction, progress=None, streams=DEFAULT_STREAMS):
    stages = DOWNLOAD_STAGES if direction == 'download' else UPLOAD_STAGES
    points = []
    transferred = 0
    for index, size in enumerate(stages):
        base = 22 if direction == 'download' else 61
        span = 34 if direction == 'download' else 30
        percent = base + int(span * index / max(1, len(stages)))
        _safe_progress(
            progress,
            phase=direction,
            percent=percent,
            message=('Midiendo descarga…' if direction == 'download' else 'Midiendo subida…'),
            current_mbps=points[-1]['mbps'] if points else None,
        )
        stage = _parallel_stage(direction, size, streams=streams)
        transferred += int(stage.get('bytes') or 0)
        if stage.get('ok') and _num(stage.get('mbps')) is not None:
            points.append(stage)
        # Al menos dos etapas para que un handshake/outlier no defina todo.
        if len(points) >= 2 and float(stage.get('seconds') or 0) >= TARGET_STAGE_SECONDS:
            break
    values = [p['mbps'] for p in points if _num(p.get('mbps')) is not None]
    # Cloudflare usa percentil 90 para ancho de banda; conservamos esa semántica.
    value = _percentile(values, 0.90)
    return {
        'mbps': round(value, 2) if value is not None else None,
        'points': points,
        'bytes': transferred,
    }


def _validate_against_link(value_mbps, link_speed_mbps, tolerance=1.05):
    """Descarta throughput que supere el techo físico del enlace negociado.

    El throughput IP/aplicación no puede ser superior a la tasa negociada del
    adaptador. Se deja 5 % de margen sólo para redondeos/reportes del driver.
    Si el enlace no está disponible, no se aplica ningún límite inventado.
    """
    value = _num(value_mbps)
    link = _num(link_speed_mbps)
    if value is None:
        return None, None
    if link is None or link <= 0:
        return value, None
    ceiling = link * max(1.0, float(tolerance))
    if value > ceiling:
        return None, f'Resultado descartado: {value:.1f} Mbps supera el enlace negociado de {link:.1f} Mbps.'
    return value, None


@dataclass
class InternetSpeedTest:
    """Runner síncrono pensado para ejecutarse en un thread de trabajo."""

    streams: int = DEFAULT_STREAMS
    link_speed_mbps: float | None = None

    def run(self, progress: Callable[[dict], None] | None = None):
        started = time.perf_counter()
        _safe_progress(progress, phase='preparing', percent=2, message='Preparando prueba…')
        meta = _metadata()

        _safe_progress(progress, phase='latency', percent=8, message='Midiendo ping y jitter…')
        latency = _latency_series(count=10)

        _safe_progress(progress, phase='download', percent=20, message='Midiendo descarga…')
        down = _measure_direction('download', progress=progress, streams=self.streams)

        _safe_progress(progress, phase='upload', percent=60, message='Midiendo subida…')
        up = _measure_direction('upload', progress=progress, streams=self.streams)

        total_bytes = int(down.get('bytes') or 0) + int(up.get('bytes') or 0)
        down_value, down_note = _validate_against_link(down.get('mbps'), self.link_speed_mbps)
        up_value, up_note = _validate_against_link(up.get('mbps'), self.link_speed_mbps)
        validation_notes = [note for note in (down_note, up_note) if note]
        result = {
            'timestamp': time.time(),
            'download_mbps': round(down_value, 2) if down_value is not None else None,
            'upload_mbps': round(up_value, 2) if up_value is not None else None,
            'latency_ms': latency.get('latency_ms'),
            'jitter_ms': latency.get('jitter_ms'),
            'latency_samples_ms': latency.get('samples_ms') or [],
            'download_points': down.get('points') or [],
            'upload_points': up.get('points') or [],
            'bytes_transferred': total_bytes,
            'data_mb': round(total_bytes / 1_000_000.0, 2),
            'duration_s': round(time.perf_counter() - started, 2),
            'server': meta,
            'provider': 'Cloudflare Speed Test endpoints',
            'source': 'speed.cloudflare.com/__down + /__up',
            'method': 'aggregate transferred bytes / client wall-clock stage duration',
            'link_speed_mbps': self.link_speed_mbps,
            'validation_notes': validation_notes,
            'active_test': True,
            'synthetic': False,
            'estimated': False,
            'ok': down_value is not None or up_value is not None,
        }
        _safe_progress(progress, phase='done', percent=100, message='Prueba completada', result=result)
        return result
