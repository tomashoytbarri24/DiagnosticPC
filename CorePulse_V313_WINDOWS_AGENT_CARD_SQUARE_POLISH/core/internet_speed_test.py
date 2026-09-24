"""Prueba activa de velocidad de Internet para CorePulse.

CorePulse soporta dos motores reales y nunca mezcla sus resultados:

1. ``ookla``: usa la CLI oficial *Speedtest by Ookla* si está instalada por el
   usuario. Es el modo pensado para comparar CorePulse con Speedtest.net porque
   utiliza la Speedtest Server Network y expone el servidor real seleccionado.
2. ``cloudflare``: conserva el motor propio basado en los endpoints públicos de
   Cloudflare Speed Test como alternativa independiente.

No se descarga, incluye ni acepta automáticamente software/licencias de Ookla.
Si la CLI oficial no está disponible, ``provider='ookla'`` devuelve N/A con una
explicación; no finge equivalencia usando Cloudflare.

REAL_OR_NA: si una fase falla, el valor queda None; no se estima.
"""
from __future__ import annotations

import concurrent.futures
import http.client
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import shutil
import socket
import statistics
import subprocess
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


def _ip_family_of(value):
    text = str(value or '').strip()
    if not text:
        return None
    # IPv6 de Windows puede incluir zone-id (fe80::1%12).
    text = text.split('%', 1)[0]
    try:
        parsed = ipaddress.ip_address(text)
    except Exception:
        return None
    return 'ipv4' if parsed.version == 4 else 'ipv6'


def _discover_source_ip(family):
    """Obtiene la IP local que Windows enrutaría para esa familia sin enviar datos."""
    family = str(family or '').strip().lower()
    if family not in ('ipv4', 'ipv6'):
        return None
    af = socket.AF_INET if family == 'ipv4' else socket.AF_INET6
    target = ('1.1.1.1', 443) if af == socket.AF_INET else ('2606:4700:4700::1111', 443, 0, 0)
    sock = None
    try:
        sock = socket.socket(af, socket.SOCK_DGRAM)
        sock.connect(target)
        candidate = sock.getsockname()[0]
        return candidate if _ip_family_of(candidate) == family else None
    except Exception:
        return None
    finally:
        try:
            if sock is not None:
                sock.close()
        except Exception:
            pass


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


OOKLA_PROVIDER = 'ookla'
CLOUDFLARE_PROVIDER = 'cloudflare'


def _subprocess_kwargs():
    kwargs = {
        'stdin': subprocess.DEVNULL,
        'stdout': subprocess.PIPE,
        'stderr': subprocess.PIPE,
        'text': True,
        'encoding': 'utf-8',
        'errors': 'replace',
    }
    if os.name == 'nt':
        kwargs['creationflags'] = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    return kwargs


def _candidate_ookla_paths():
    """Rutas plausibles de la CLI oficial, sin descargar ni instalar nada."""
    seen = set()

    def emit(value):
        if not value:
            return
        try:
            path = Path(value).expanduser()
        except Exception:
            return
        key = str(path).lower()
        if key in seen:
            return
        seen.add(key)
        yield path

    configured = os.environ.get('COREPULSE_SPEEDTEST_CLI')
    yield from emit(configured)
    yield from emit(shutil.which('speedtest'))
    yield from emit(shutil.which('speedtest.exe'))

    for env_name in ('LOCALAPPDATA', 'ProgramFiles', 'ProgramFiles(x86)'):
        base = os.environ.get(env_name)
        if not base:
            continue
        base_path = Path(base)
        for relative in (
            Path('Ookla Speedtest CLI') / 'speedtest.exe',
            Path('Speedtest') / 'speedtest.exe',
            Path('Ookla') / 'Speedtest CLI' / 'speedtest.exe',
        ):
            yield from emit(base_path / relative)

    local = os.environ.get('LOCALAPPDATA')
    if local:
        # winget crea un alias/enlace aquí. El proceso actual puede usarlo
        # inmediatamente aunque su PATH todavía no se haya refrescado.
        yield from emit(Path(local) / 'Microsoft' / 'WinGet' / 'Links' / 'speedtest.exe')

        packages = Path(local) / 'Microsoft' / 'WinGet' / 'Packages'
        if packages.is_dir():
            try:
                for folder in packages.glob('Ookla.Speedtest.CLI_*'):
                    direct = folder / 'speedtest.exe'
                    yield from emit(direct)
                    # Algunas revisiones de winget dejan el binario en un
                    # subdirectorio de versión. El patrón queda deliberadamente
                    # limitado a este paquete para no recorrer todo LOCALAPPDATA.
                    try:
                        for candidate in folder.glob('**/speedtest.exe'):
                            yield from emit(candidate)
                    except Exception:
                        pass
            except Exception:
                pass


def _probe_ookla_cli(path, timeout=4):
    try:
        p = Path(path)
        if not p.is_file():
            return None
        completed = subprocess.run(
            [str(p), '--version'], timeout=timeout, **_subprocess_kwargs()
        )
        output = f"{completed.stdout or ''}\n{completed.stderr or ''}".strip()
        lowered = output.lower()
        if completed.returncode == 0 and 'speedtest' in lowered and 'ookla' in lowered and 'speedtest-cli' not in lowered:
            version_line = next((line.strip() for line in output.splitlines() if line.strip()), 'Speedtest by Ookla')
            return {'path': str(p), 'version': version_line, 'official': True}
    except Exception:
        pass
    return None


def find_ookla_cli():
    """Devuelve sólo una CLI verificada como Speedtest by Ookla oficial."""
    for candidate in _candidate_ookla_paths():
        status = _probe_ookla_cli(candidate)
        if status:
            return status
    return None


def ookla_cli_status():
    status = find_ookla_cli()
    if status:
        return {
            'available': True,
            'path': status.get('path'),
            'version': status.get('version'),
            'provider': 'Speedtest by Ookla',
            'official_engine': True,
        }
    return {
        'available': False,
        'path': None,
        'version': None,
        'provider': 'Speedtest by Ookla',
        'official_engine': False,
        'message': 'CLI oficial de Ookla no instalada o no detectada.',
    }


def _license_error(text):
    lowered = str(text or '').lower()
    markers = ('license', 'eula', 'gdpr', 'privacy policy', 'terms of use', 'accept-license', 'accept-gdpr')
    return any(marker in lowered for marker in markers)


def _extract_json_object(text):
    raw = str(text or '').strip()
    if not raw:
        return None
    # La CLI oficial con --progress=no normalmente entrega un único JSON. Este
    # fallback tolera avisos previos sin interpretar texto como mediciones.
    for line in reversed(raw.splitlines()):
        candidate = line.strip()
        if candidate.startswith('{') and candidate.endswith('}'):
            try:
                data = json.loads(candidate)
                if isinstance(data, dict):
                    return data
            except Exception:
                pass
    start = raw.find('{')
    end = raw.rfind('}')
    if 0 <= start < end:
        try:
            data = json.loads(raw[start:end + 1])
            return data if isinstance(data, dict) else None
        except Exception:
            pass
    return None


def list_ookla_servers(cli_path=None, limit=12, timeout=18):
    """Lista servidores cercanos que la CLI oficial permite seleccionar."""
    status = _probe_ookla_cli(cli_path) if cli_path else find_ookla_cli()
    if not status:
        return {'ok': False, 'servers': [], 'error_code': 'OOKLA_CLI_NOT_FOUND', 'message': 'CLI oficial de Ookla no detectada.'}
    try:
        completed = subprocess.run(
            [status['path'], '--servers'], timeout=timeout, **_subprocess_kwargs()
        )
    except subprocess.TimeoutExpired:
        return {'ok': False, 'servers': [], 'error_code': 'OOKLA_TIMEOUT', 'message': 'La lista de servidores de Ookla tardó demasiado.'}
    except Exception as exc:
        return {'ok': False, 'servers': [], 'error_code': 'OOKLA_ERROR', 'message': str(exc)[:180]}

    output = f"{completed.stdout or ''}\n{completed.stderr or ''}".strip()
    if completed.returncode != 0:
        code = 'OOKLA_LICENSE_REQUIRED' if _license_error(output) else 'OOKLA_SERVER_LIST_FAILED'
        message = (
            'La CLI oficial necesita que aceptes sus términos una vez.'
            if code == 'OOKLA_LICENSE_REQUIRED'
            else (output.splitlines()[-1].strip() if output.splitlines() else 'No se pudo listar servidores.')
        )
        return {'ok': False, 'servers': [], 'error_code': code, 'message': message}

    servers = []
    for line in output.splitlines():
        line = line.strip()
        if not re.match(r'^\d+\s+', line):
            continue
        parts = re.split(r'\s{2,}', line, maxsplit=3)
        if len(parts) < 3:
            continue
        try:
            server_id = int(parts[0])
        except Exception:
            continue
        name = parts[1].strip() if len(parts) > 1 else ''
        location = parts[2].strip() if len(parts) > 2 else ''
        country = parts[3].strip() if len(parts) > 3 else ''
        servers.append({
            'id': server_id,
            'name': name or None,
            'location': location or None,
            'country': country or None,
        })
        if len(servers) >= max(1, int(limit)):
            break
    return {
        'ok': bool(servers),
        'servers': servers,
        'error_code': None if servers else 'OOKLA_NO_SERVERS',
        'message': None if servers else 'La CLI no devolvió servidores cercanos.',
        'cli': status,
    }


def _ookla_bandwidth_mbps(section):
    if not isinstance(section, dict):
        return None
    bandwidth = _num(section.get('bandwidth'))
    if bandwidth is None:
        return None
    # El JSON oficial usa bytes/s en formatos machine-readable.
    return bandwidth * 8.0 / 1_000_000.0


def _ookla_latency_detail(section):
    if not isinstance(section, dict):
        return None
    latency = section.get('latency')
    if not isinstance(latency, dict):
        return None
    result = {}
    for source, target in (('iqm', 'latency_ms'), ('low', 'low_ms'), ('high', 'high_ms'), ('jitter', 'jitter_ms')):
        value = _num(latency.get(source))
        result[target] = round(value, 2) if value is not None else None
    return result if any(value is not None for value in result.values()) else None


def _ookla_result(data, duration_s, cli_status, selected_server_id=None, link_speed_mbps=None, ip_family='auto', bind_ip=None):
    if not isinstance(data, dict):
        return None
    down = data.get('download') if isinstance(data.get('download'), dict) else {}
    up = data.get('upload') if isinstance(data.get('upload'), dict) else {}
    ping = data.get('ping') if isinstance(data.get('ping'), dict) else {}
    server = data.get('server') if isinstance(data.get('server'), dict) else {}
    interface = data.get('interface') if isinstance(data.get('interface'), dict) else {}
    result_info = data.get('result') if isinstance(data.get('result'), dict) else {}
    internal_ip = interface.get('internalIp')
    external_ip = interface.get('externalIp')
    requested_family = str(ip_family or 'auto').strip().lower()
    network_family = _ip_family_of(external_ip) or _ip_family_of(internal_ip) or _ip_family_of(bind_ip)
    route_bound = requested_family in ('ipv4', 'ipv6') and _ip_family_of(bind_ip) == requested_family

    down_mbps = _ookla_bandwidth_mbps(down)
    up_mbps = _ookla_bandwidth_mbps(up)
    latency = _num(ping.get('latency'))
    jitter = _num(ping.get('jitter'))
    packet_loss = _num(data.get('packetLoss'))
    down_bytes = int(_num(down.get('bytes')) or 0)
    up_bytes = int(_num(up.get('bytes')) or 0)
    total_bytes = max(0, down_bytes) + max(0, up_bytes)

    notes = []
    link = _num(link_speed_mbps)
    for label, value in (('descarga', down_mbps), ('subida', up_mbps)):
        if link and value is not None and value > link * 1.05:
            notes.append(
                f'La {label} oficial ({value:.1f} Mbps) supera el enlace reportado por Windows ({link:.1f} Mbps); se conserva sin modificar por provenir de Ookla.'
            )

    server_id = server.get('id')
    try:
        server_id = int(server_id) if server_id is not None else None
    except Exception:
        pass
    locked = selected_server_id is not None
    return {
        'timestamp': time.time(),
        'download_mbps': round(down_mbps, 2) if down_mbps is not None else None,
        'upload_mbps': round(up_mbps, 2) if up_mbps is not None else None,
        'latency_ms': round(latency, 2) if latency is not None else None,
        'jitter_ms': round(jitter, 2) if jitter is not None else None,
        'packet_loss_percent': round(packet_loss, 2) if packet_loss is not None else None,
        'download_latency': _ookla_latency_detail(down),
        'upload_latency': _ookla_latency_detail(up),
        'latency_samples_ms': [],
        'download_points': [],
        'upload_points': [],
        'bytes_transferred': total_bytes,
        'data_mb': round(total_bytes / 1_000_000.0, 2),
        'duration_s': round(float(duration_s), 2),
        'server': {
            'id': server_id,
            'name': server.get('name'),
            'location': server.get('location'),
            'country': server.get('country'),
            'host': server.get('host'),
            'port': server.get('port'),
            'ip': server.get('ip'),
        },
        'isp': data.get('isp'),
        'external_ip': external_ip,
        'internal_ip': internal_ip,
        'interface_name': interface.get('name'),
        'network_family': network_family,
        'requested_ip_family': requested_family,
        'route_bound': route_bound,
        'bind_ip': bind_ip,
        'is_vpn': interface.get('isVpn'),
        'result_id': result_info.get('id'),
        'result_url': result_info.get('url'),
        'provider': 'Speedtest by Ookla',
        'provider_key': OOKLA_PROVIDER,
        'source': 'Official Speedtest CLI / Speedtest Server Network',
        'method': 'official Ookla Speedtest CLI result; machine-readable bandwidth converted from B/s to Mbps',
        'official_engine': True,
        'speedtest_net_comparable': True,
        'server_locked': locked,
        'comparability': (
            f'Motor oficial + servidor fijado + ruta {requested_family.upper()} fijada. Verifica que Speedtest.net use la misma familia/IP pública.'
            if locked and route_bound else
            'Motor y servidor fijados, pero la familia IP no está fijada; IPv4/IPv6 pueden tomar rutas distintas.'
            if locked else
            'Motor oficial de Ookla; servidor y/o ruta pueden diferir de otra ejecución de Speedtest.net.'
        ),
        'cli_path': cli_status.get('path') if isinstance(cli_status, dict) else None,
        'cli_version': cli_status.get('version') if isinstance(cli_status, dict) else None,
        'link_speed_mbps': link_speed_mbps,
        'validation_notes': notes,
        'active_test': True,
        'synthetic': False,
        'estimated': False,
        'ok': down_mbps is not None or up_mbps is not None,
    }


def run_ookla_speedtest(cli_path=None, server_id=None, progress=None, link_speed_mbps=None, timeout=150, ip_family='auto', bind_ip=None):
    status = _probe_ookla_cli(cli_path) if cli_path else find_ookla_cli()
    if not status:
        return {
            'timestamp': time.time(), 'ok': False,
            'download_mbps': None, 'upload_mbps': None, 'latency_ms': None, 'jitter_ms': None,
            'provider': 'Speedtest by Ookla', 'provider_key': OOKLA_PROVIDER,
            'official_engine': False, 'speedtest_net_comparable': False,
            'error_code': 'OOKLA_CLI_NOT_FOUND',
            'error': 'No se detectó la CLI oficial de Speedtest by Ookla.',
            'action': 'Instala/configura la CLI oficial de Ookla y vuelve a intentar.',
            'active_test': False, 'synthetic': False, 'estimated': False,
            'server': {}, 'validation_notes': [],
        }

    requested_family = str(ip_family or 'auto').strip().lower()
    if requested_family not in ('auto', 'ipv4', 'ipv6'):
        requested_family = 'auto'
    source_ip = str(bind_ip or '').strip() or None
    if requested_family == 'auto':
        source_ip = None
    if requested_family in ('ipv4', 'ipv6'):
        if _ip_family_of(source_ip) != requested_family:
            source_ip = _discover_source_ip(requested_family)
        if _ip_family_of(source_ip) != requested_family:
            return {
                'timestamp': time.time(), 'ok': False,
                'download_mbps': None, 'upload_mbps': None, 'latency_ms': None, 'jitter_ms': None,
                'provider': 'Speedtest by Ookla', 'provider_key': OOKLA_PROVIDER,
                'official_engine': True, 'speedtest_net_comparable': False,
                'error_code': 'OOKLA_ROUTE_UNAVAILABLE',
                'error': f'No se encontró una ruta {requested_family.upper()} utilizable para ejecutar Speedtest.',
                'action': 'Elige Ruta automática o revisa la configuración IP del adaptador.',
                'active_test': False, 'synthetic': False, 'estimated': False,
                'server': {}, 'validation_notes': [],
                'requested_ip_family': requested_family, 'route_bound': False,
            }

    args = [status['path'], '--format=json', '--progress=no']
    if source_ip is not None:
        # La CLI oficial permite fijar la IP de origen con --ip; esto evita que
        # Windows elija IPv6 mientras el navegador está usando IPv4 (o viceversa).
        args.append(f'--ip={source_ip}')
    if server_id is not None:
        try:
            args.append(f'--server-id={int(server_id)}')
        except Exception:
            pass
    _safe_progress(progress, phase='preparing', percent=8, message='Conectando con Speedtest by Ookla…')
    started = time.perf_counter()
    try:
        completed = subprocess.run(args, timeout=timeout, **_subprocess_kwargs())
    except subprocess.TimeoutExpired:
        return {
            'timestamp': time.time(), 'ok': False,
            'download_mbps': None, 'upload_mbps': None, 'latency_ms': None, 'jitter_ms': None,
            'provider': 'Speedtest by Ookla', 'provider_key': OOKLA_PROVIDER,
            'official_engine': True, 'speedtest_net_comparable': True,
            'error_code': 'OOKLA_TIMEOUT', 'error': 'La prueba oficial agotó el tiempo de espera.',
            'active_test': True, 'synthetic': False, 'estimated': False,
            'server': {}, 'validation_notes': [],
        }
    except Exception as exc:
        return {
            'timestamp': time.time(), 'ok': False,
            'download_mbps': None, 'upload_mbps': None, 'latency_ms': None, 'jitter_ms': None,
            'provider': 'Speedtest by Ookla', 'provider_key': OOKLA_PROVIDER,
            'official_engine': True, 'speedtest_net_comparable': True,
            'error_code': 'OOKLA_ERROR', 'error': str(exc)[:180],
            'active_test': False, 'synthetic': False, 'estimated': False,
            'server': {}, 'validation_notes': [],
        }

    elapsed = time.perf_counter() - started
    output = f"{completed.stdout or ''}\n{completed.stderr or ''}".strip()
    if completed.returncode != 0:
        license_required = _license_error(output)
        return {
            'timestamp': time.time(), 'ok': False,
            'download_mbps': None, 'upload_mbps': None, 'latency_ms': None, 'jitter_ms': None,
            'provider': 'Speedtest by Ookla', 'provider_key': OOKLA_PROVIDER,
            'official_engine': True, 'speedtest_net_comparable': True,
            'error_code': 'OOKLA_LICENSE_REQUIRED' if license_required else 'OOKLA_TEST_FAILED',
            'error': (
                'La CLI oficial necesita que aceptes sus términos una vez.'
                if license_required else
                (output.splitlines()[-1].strip() if output.splitlines() else 'Speedtest by Ookla no pudo completar la prueba.')
            ),
            'action': 'Ejecuta speedtest una vez en una consola para revisar y aceptar los términos de Ookla.' if license_required else None,
            'active_test': False, 'synthetic': False, 'estimated': False,
            'server': {}, 'validation_notes': [],
        }

    data = _extract_json_object(completed.stdout)
    result = _ookla_result(
        data, elapsed, status,
        selected_server_id=server_id,
        link_speed_mbps=link_speed_mbps,
        ip_family=requested_family,
        bind_ip=source_ip,
    )
    if result is None:
        return {
            'timestamp': time.time(), 'ok': False,
            'download_mbps': None, 'upload_mbps': None, 'latency_ms': None, 'jitter_ms': None,
            'provider': 'Speedtest by Ookla', 'provider_key': OOKLA_PROVIDER,
            'official_engine': True, 'speedtest_net_comparable': True,
            'error_code': 'OOKLA_INVALID_OUTPUT', 'error': 'La CLI oficial no devolvió un resultado JSON válido.',
            'active_test': True, 'synthetic': False, 'estimated': False,
            'server': {}, 'validation_notes': [],
        }
    _safe_progress(progress, phase='done', percent=100, message='Speedtest by Ookla completado', result=result)
    return result


@dataclass
class InternetSpeedTest:
    """Runner síncrono pensado para ejecutarse en un thread de trabajo."""

    streams: int = DEFAULT_STREAMS
    link_speed_mbps: float | None = None
    provider: str = CLOUDFLARE_PROVIDER
    server_id: int | None = None
    ookla_cli_path: str | None = None
    ip_family: str = 'auto'
    bind_ip: str | None = None

    def cli_status(self):
        if not self.ookla_cli_path:
            return ookla_cli_status()
        status = _probe_ookla_cli(self.ookla_cli_path)
        if status:
            return {
                'available': True, 'path': status.get('path'), 'version': status.get('version'),
                'provider': 'Speedtest by Ookla', 'official_engine': True,
            }
        return {
            'available': False, 'path': None, 'version': None,
            'provider': 'Speedtest by Ookla', 'official_engine': False,
            'message': 'CLI oficial de Ookla no instalada o no detectada.',
        }

    def list_servers(self, limit=12):
        return list_ookla_servers(self.ookla_cli_path, limit=limit)

    def run(self, progress: Callable[[dict], None] | None = None):
        provider = str(self.provider or CLOUDFLARE_PROVIDER).strip().lower()
        if provider == OOKLA_PROVIDER:
            return run_ookla_speedtest(
                cli_path=self.ookla_cli_path,
                server_id=self.server_id,
                progress=progress,
                link_speed_mbps=self.link_speed_mbps,
                ip_family=self.ip_family,
                bind_ip=self.bind_ip,
            )
        if provider == 'auto':
            status = _probe_ookla_cli(self.ookla_cli_path) if self.ookla_cli_path else find_ookla_cli()
            if status:
                return run_ookla_speedtest(
                    cli_path=status.get('path'),
                    server_id=self.server_id,
                    progress=progress,
                    link_speed_mbps=self.link_speed_mbps,
                    ip_family=self.ip_family,
                    bind_ip=self.bind_ip,
                )
        return self._run_cloudflare(progress=progress)

    def _run_cloudflare(self, progress: Callable[[dict], None] | None = None):
        started = time.perf_counter()
        _safe_progress(progress, phase='preparing', percent=2, message='Preparando prueba alternativa Cloudflare…')
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
            'packet_loss_percent': None,
            'latency_samples_ms': latency.get('samples_ms') or [],
            'download_points': down.get('points') or [],
            'upload_points': up.get('points') or [],
            'bytes_transferred': total_bytes,
            'data_mb': round(total_bytes / 1_000_000.0, 2),
            'duration_s': round(time.perf_counter() - started, 2),
            'server': meta,
            'isp': meta.get('isp') if isinstance(meta, dict) else None,
            'external_ip': meta.get('client_ip') if isinstance(meta, dict) else None,
            'provider': 'Cloudflare Speed Test endpoints',
            'provider_key': CLOUDFLARE_PROVIDER,
            'source': 'speed.cloudflare.com/__down + /__up',
            'method': 'aggregate transferred bytes / client wall-clock stage duration',
            'official_engine': False,
            'speedtest_net_comparable': False,
            'server_locked': False,
            'comparability': 'Motor alternativo: sus resultados no deben presentarse como equivalentes 1:1 a Speedtest.net.',
            'link_speed_mbps': self.link_speed_mbps,
            'validation_notes': validation_notes,
            'active_test': True,
            'synthetic': False,
            'estimated': False,
            'ok': down_value is not None or up_value is not None,
        }
        _safe_progress(progress, phase='done', percent=100, message='Prueba alternativa completada', result=result)
        return result
