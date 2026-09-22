"""Inventario y diagnóstico de red para CorePulse.

Política REAL_OR_NA:
- psutil entrega contadores, direcciones y estado del adaptador.
- Windows PowerShell completa gateway, DNS, descripción y velocidad de enlace.
- netsh wlan se usa sólo para datos Wi-Fi que Windows expone realmente.
- No se estiman SSID, señal, gateway, DNS, latencia ni pérdida de paquetes.
"""
from __future__ import annotations

import json
import os
import platform
import re
import socket
import subprocess
import time
from dataclasses import dataclass

import psutil

WINDOWS = platform.system().lower() == 'windows'


def _num(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except Exception:
        return None


def _safe_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _run(cmd, timeout=6):
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0) if WINDOWS else 0,
            errors='replace',
        )
        return completed.returncode, completed.stdout or '', completed.stderr or ''
    except Exception as exc:
        return -1, '', str(exc)


def _powershell_json(script, timeout=7):
    if not WINDOWS:
        return None
    code, stdout, _stderr = _run(
        ['powershell.exe', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-Command', script],
        timeout=timeout,
    )
    if code != 0 or not stdout.strip():
        return None
    try:
        return json.loads(stdout.strip())
    except Exception:
        return None


def _windows_network_inventory():
    """Obtiene metadatos nativos de Windows fuera del hilo UI."""
    script = r"""
$ErrorActionPreference='SilentlyContinue'
$adapters = @(Get-NetAdapter | ForEach-Object {
  [pscustomobject]@{
    Name=$_.Name
    InterfaceDescription=$_.InterfaceDescription
    InterfaceIndex=$_.ifIndex
    Status=$_.Status
    LinkSpeed=$_.LinkSpeed
    MacAddress=$_.MacAddress
    MediaConnectionState=$_.MediaConnectionState
    PhysicalMediaType=$_.PhysicalMediaType
    HardwareInterface=$_.HardwareInterface
  }
})
$configs = @(Get-NetIPConfiguration | ForEach-Object {
  [pscustomobject]@{
    InterfaceAlias=$_.InterfaceAlias
    InterfaceIndex=$_.InterfaceIndex
    IPv4Address=@($_.IPv4Address | ForEach-Object {$_.IPAddress})
    IPv6Address=@($_.IPv6Address | ForEach-Object {$_.IPAddress})
    IPv4DefaultGateway=@($_.IPv4DefaultGateway | ForEach-Object {$_.NextHop})
    IPv6DefaultGateway=@($_.IPv6DefaultGateway | ForEach-Object {$_.NextHop})
    DnsServers=@($_.DNSServer.ServerAddresses)
  }
})
[pscustomobject]@{Adapters=$adapters; Configs=$configs} | ConvertTo-Json -Depth 6 -Compress
"""
    data = _powershell_json(script)
    return data if isinstance(data, dict) else {}


def _parse_link_speed_mbps(text):
    raw = str(text or '').strip().replace(',', '.')
    if not raw:
        return None
    match = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*(Gbps|Mbps|Kbps|bps)', raw, re.I)
    if not match:
        return None
    value = float(match.group(1))
    unit = match.group(2).lower()
    if unit == 'gbps':
        return value * 1000.0
    if unit == 'mbps':
        return value
    if unit == 'kbps':
        return value / 1000.0
    return value / 1_000_000.0


def _wifi_inventory():
    """Extrae datos Wi-Fi de netsh. Los nombres de campo contemplan EN/ES."""
    if not WINDOWS:
        return []
    code, stdout, _stderr = _run(['netsh', 'wlan', 'show', 'interfaces'], timeout=5)
    if code != 0 or not stdout.strip():
        return []
    aliases = {
        'name': ('name', 'nombre'),
        'description': ('description', 'descripción', 'descripcion'),
        'ssid': ('ssid',),
        'bssid': ('bssid',),
        'signal': ('signal', 'señal', 'senal'),
        'radio_type': ('radio type', 'tipo de radio'),
        'channel': ('channel', 'canal'),
        'receive_rate': ('receive rate (mbps)', 'velocidad de recepción (mbps)', 'velocidad de recepcion (mbps)'),
        'transmit_rate': ('transmit rate (mbps)', 'velocidad de transmisión (mbps)', 'velocidad de transmision (mbps)'),
        'state': ('state', 'estado'),
    }
    records = []
    current = {}
    for line in stdout.splitlines():
        if ':' not in line:
            continue
        key, value = line.split(':', 1)
        key_n = key.strip().lower()
        value = value.strip()
        canonical = None
        for name, options in aliases.items():
            if key_n in options:
                canonical = name
                break
        if canonical is None:
            continue
        if canonical == 'name' and current.get('name'):
            records.append(current)
            current = {}
        current[canonical] = value
    if current:
        records.append(current)
    for rec in records:
        sig = str(rec.get('signal') or '').replace('%', '').strip()
        rec['signal_percent'] = _num(sig)
        rec['receive_mbps'] = _num(rec.get('receive_rate'))
        rec['transmit_mbps'] = _num(rec.get('transmit_rate'))
    return records


def _addr_parts(addrs):
    ipv4, ipv6, macs = [], [], []
    af_link = getattr(psutil, 'AF_LINK', object())
    for addr in addrs or []:
        if addr.family == socket.AF_INET and addr.address:
            ipv4.append(addr.address)
        elif addr.family == socket.AF_INET6 and addr.address:
            ipv6.append(str(addr.address).split('%')[0])
        elif addr.family == af_link and addr.address:
            macs.append(addr.address)
    return ipv4, ipv6, macs


def collect_network_identity():
    """Devuelve adaptadores reales y selecciona la conexión primaria sin inferir por marca."""
    try:
        stats = psutil.net_if_stats()
    except Exception:
        stats = {}
    try:
        addrs = psutil.net_if_addrs()
    except Exception:
        addrs = {}
    try:
        counters = psutil.net_io_counters(pernic=True)
    except Exception:
        counters = {}

    win = _windows_network_inventory() if WINDOWS else {}
    win_adapters = _safe_list(win.get('Adapters')) if isinstance(win, dict) else []
    win_configs = _safe_list(win.get('Configs')) if isinstance(win, dict) else []
    by_name = {str(x.get('Name') or '').casefold(): x for x in win_adapters if isinstance(x, dict)}
    cfg_by_name = {str(x.get('InterfaceAlias') or '').casefold(): x for x in win_configs if isinstance(x, dict)}
    wifi = _wifi_inventory() if WINDOWS else []
    wifi_by_name = {str(x.get('name') or '').casefold(): x for x in wifi if isinstance(x, dict)}

    names = set(stats) | set(addrs) | set(counters)
    for item in win_adapters:
        if isinstance(item, dict) and item.get('Name'):
            names.add(str(item['Name']))

    adapters = []
    for name in sorted(names, key=lambda s: str(s).casefold()):
        stat = stats.get(name)
        nic_addrs = addrs.get(name) or []
        cnt = counters.get(name)
        ipv4, ipv6, macs = _addr_parts(nic_addrs)
        native = by_name.get(str(name).casefold(), {})
        cfg = cfg_by_name.get(str(name).casefold(), {})
        wlan = wifi_by_name.get(str(name).casefold(), {})
        native_speed = _parse_link_speed_mbps(native.get('LinkSpeed'))
        psutil_speed = _num(getattr(stat, 'speed', None))
        speed = native_speed if native_speed is not None and native_speed > 0 else psutil_speed if psutil_speed and psutil_speed > 0 else None
        mac = native.get('MacAddress') or (macs[0] if macs else None)
        gateways = [x for x in _safe_list(cfg.get('IPv4DefaultGateway')) + _safe_list(cfg.get('IPv6DefaultGateway')) if x]
        dns_servers = [x for x in _safe_list(cfg.get('DnsServers')) if x]
        actual_ipv4 = [x for x in _safe_list(cfg.get('IPv4Address')) if x] or ipv4
        actual_ipv6 = [x for x in _safe_list(cfg.get('IPv6Address')) if x] or ipv6
        is_up = bool(getattr(stat, 'isup', False))
        status_text = str(native.get('Status') or ('Up' if is_up else 'Down'))
        active = bool(is_up and (gateways or actual_ipv4))
        adapters.append({
            'name': str(name),
            'description': native.get('InterfaceDescription') or wlan.get('description') or None,
            'interface_index': native.get('InterfaceIndex') or cfg.get('InterfaceIndex'),
            'status': status_text,
            'is_up': is_up,
            'active_candidate': active,
            'link_speed_mbps': round(speed, 3) if speed is not None else None,
            'mac': mac,
            'ipv4': actual_ipv4,
            'ipv6': actual_ipv6,
            'gateways': gateways,
            'dns_servers': dns_servers,
            'physical_media_type': native.get('PhysicalMediaType') or None,
            'media_state': native.get('MediaConnectionState') or None,
            'hardware_interface': native.get('HardwareInterface'),
            'ssid': wlan.get('ssid') or None,
            'bssid': wlan.get('bssid') or None,
            'wifi_signal_percent': wlan.get('signal_percent'),
            'wifi_radio_type': wlan.get('radio_type') or None,
            'wifi_channel': wlan.get('channel') or None,
            'wifi_receive_mbps': wlan.get('receive_mbps'),
            'wifi_transmit_mbps': wlan.get('transmit_mbps'),
            'bytes_sent_total': getattr(cnt, 'bytes_sent', None) if cnt else None,
            'bytes_recv_total': getattr(cnt, 'bytes_recv', None) if cnt else None,
            'packets_sent_total': getattr(cnt, 'packets_sent', None) if cnt else None,
            'packets_recv_total': getattr(cnt, 'packets_recv', None) if cnt else None,
            'errors_in_total': getattr(cnt, 'errin', None) if cnt else None,
            'errors_out_total': getattr(cnt, 'errout', None) if cnt else None,
            'drops_in_total': getattr(cnt, 'dropin', None) if cnt else None,
            'drops_out_total': getattr(cnt, 'dropout', None) if cnt else None,
            'sources': ['psutil.net_if_stats', 'psutil.net_if_addrs', 'psutil.net_io_counters'] + (['Windows Get-NetAdapter / Get-NetIPConfiguration'] if WINDOWS else []) + (['netsh wlan'] if wlan else []),
        })

    primary_index = None
    ranked = []
    for index, adapter in enumerate(adapters):
        score = 0
        if adapter.get('is_up'):
            score += 10
        if adapter.get('gateways'):
            score += 30
        if adapter.get('ipv4'):
            score += 10
        if adapter.get('ssid'):
            score += 2
        if str(adapter.get('name') or '').lower().startswith(('loopback', 'lo')):
            score -= 50
        ranked.append((score, index))
    if ranked:
        best_score, primary_index = max(ranked)
        if best_score <= 0:
            primary_index = None

    return {
        'timestamp': time.time(),
        'platform': platform.system(),
        'hostname': socket.gethostname() or None,
        'adapters': adapters,
        'primary_index': primary_index,
        'primary_name': adapters[primary_index]['name'] if primary_index is not None else None,
        'source': 'psutil + Windows networking APIs' if WINDOWS else 'psutil',
        'synthetic': False,
        'estimated': False,
    }


@dataclass
class NetworkTrafficSampler:
    """Calcula tasas sólo desde deltas de contadores reales de psutil."""
    previous: dict | None = None
    previous_ts: float | None = None

    def sample(self, interface_name=None):
        now = time.time()
        try:
            counters = psutil.net_io_counters(pernic=True)
        except Exception:
            counters = {}
        selected = counters.get(interface_name) if interface_name else None
        if selected is None and counters:
            # Sin interfaz primaria conocida no inventamos cuál es la conexión principal.
            current = None
        else:
            current = selected
        out = {
            'timestamp': now,
            'interface': interface_name,
            'download_bps': None,
            'upload_bps': None,
            'bytes_recv_total': getattr(current, 'bytes_recv', None) if current else None,
            'bytes_sent_total': getattr(current, 'bytes_sent', None) if current else None,
            'packets_recv_total': getattr(current, 'packets_recv', None) if current else None,
            'packets_sent_total': getattr(current, 'packets_sent', None) if current else None,
            'errors_in_total': getattr(current, 'errin', None) if current else None,
            'errors_out_total': getattr(current, 'errout', None) if current else None,
            'drops_in_total': getattr(current, 'dropin', None) if current else None,
            'drops_out_total': getattr(current, 'dropout', None) if current else None,
            'source': 'psutil.net_io_counters',
            'synthetic': False,
        }
        if current is not None and self.previous is not None and self.previous_ts is not None:
            old = self.previous.get(interface_name)
            elapsed = now - self.previous_ts
            if old is not None and elapsed > 0.05:
                recv_delta = max(0, int(current.bytes_recv) - int(old.bytes_recv))
                sent_delta = max(0, int(current.bytes_sent) - int(old.bytes_sent))
                out['download_bps'] = recv_delta / elapsed
                out['upload_bps'] = sent_delta / elapsed
        self.previous = counters
        self.previous_ts = now
        return out


def _ping_once(host, timeout_ms=900):
    if not host:
        return {'ok': False, 'latency_ms': None, 'error': 'Sin destino'}
    if WINDOWS:
        cmd = ['ping', '-n', '1', '-w', str(int(timeout_ms)), str(host)]
    else:
        timeout_s = max(1, int(round(timeout_ms / 1000.0)))
        cmd = ['ping', '-c', '1', '-W', str(timeout_s), str(host)]
    started = time.perf_counter()
    code, stdout, stderr = _run(cmd, timeout=max(2, timeout_ms / 1000.0 + 1.5))
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    if code != 0:
        return {'ok': False, 'latency_ms': None, 'error': (stderr or stdout or 'Sin respuesta').strip()[:180]}
    match = re.search(r'(?:time|tiempo)[=<]\s*([0-9]+(?:[\.,][0-9]+)?)\s*ms', stdout, re.I)
    latency = float(match.group(1).replace(',', '.')) if match else elapsed_ms
    return {'ok': True, 'latency_ms': round(latency, 2), 'error': None}


def _ping_series(host, count=4):
    samples = []
    for _ in range(max(1, int(count))):
        samples.append(_ping_once(host))
    success = [x for x in samples if x.get('ok')]
    latencies = [float(x['latency_ms']) for x in success if _num(x.get('latency_ms')) is not None]
    sent = len(samples)
    received = len(success)
    loss = ((sent - received) / sent * 100.0) if sent else None
    return {
        'target': host,
        'sent': sent,
        'received': received,
        'loss_percent': round(loss, 1) if loss is not None else None,
        'latency_avg_ms': round(sum(latencies) / len(latencies), 2) if latencies else None,
        'latency_min_ms': round(min(latencies), 2) if latencies else None,
        'latency_max_ms': round(max(latencies), 2) if latencies else None,
        'reachable': bool(received),
        'source': 'ping.exe' if WINDOWS else 'ping',
    }


def _dns_test(host='www.microsoft.com'):
    started = time.perf_counter()
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        ips = []
        for item in addresses:
            try:
                ip = item[4][0]
            except Exception:
                continue
            if ip not in ips:
                ips.append(ip)
        return {
            'ok': bool(ips),
            'host': host,
            'addresses': ips[:5],
            'latency_ms': round((time.perf_counter() - started) * 1000.0, 2),
            'error': None if ips else 'Sin respuestas DNS',
            'source': 'socket.getaddrinfo',
        }
    except Exception as exc:
        return {
            'ok': False,
            'host': host,
            'addresses': [],
            'latency_ms': None,
            'error': str(exc)[:180],
            'source': 'socket.getaddrinfo',
        }


def diagnose_network(identity=None, count=4):
    """Diagnóstico conservador: gateway, Internet (1.1.1.1) y resolución DNS."""
    identity = identity if isinstance(identity, dict) else collect_network_identity()
    adapters = identity.get('adapters') if isinstance(identity.get('adapters'), list) else []
    index = identity.get('primary_index')
    primary = adapters[index] if isinstance(index, int) and 0 <= index < len(adapters) else {}
    gateway = None
    gateways = primary.get('gateways') if isinstance(primary, dict) else None
    if isinstance(gateways, list) and gateways:
        gateway = gateways[0]
    gateway_test = _ping_series(gateway, count=count) if gateway else {
        'target': None, 'sent': 0, 'received': 0, 'loss_percent': None,
        'latency_avg_ms': None, 'latency_min_ms': None, 'latency_max_ms': None,
        'reachable': False, 'source': 'N/A', 'reason': 'Gateway no expuesto por Windows',
    }
    internet_test = _ping_series('1.1.1.1', count=count)
    dns_test = _dns_test()
    if not primary:
        status = 'SIN_ADAPTADOR_ACTIVO'
    elif not internet_test.get('reachable'):
        status = 'SIN_INTERNET'
    elif not dns_test.get('ok'):
        status = 'DNS_CON_PROBLEMAS'
    elif gateway and not gateway_test.get('reachable'):
        status = 'GATEWAY_NO_RESPONDE_ICMP'
    else:
        status = 'CONECTIVIDAD_OK'
    return {
        'timestamp': time.time(),
        'status': status,
        'interface': primary.get('name') if isinstance(primary, dict) else None,
        'gateway': gateway_test,
        'internet': internet_test,
        'dns': dns_test,
        'synthetic': False,
        'estimated': False,
        'notes': 'Una respuesta ICMP bloqueada no demuestra por sí sola una caída del servicio.',
    }
