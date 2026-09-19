"""V100 — servidor + familia IP fijados para comparar Speedtest.net."""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION
import core.internet_speed_test as speed


def check(name, condition):
    print(f"[{'PASS' if condition else 'FAIL'}] {name}: {bool(condition)}")
    return bool(condition)


def main():
    panel = (ROOT / 'gui' / 'network_detail_panel.py').read_text(encoding='utf-8')
    engine = (ROOT / 'core' / 'internet_speed_test.py').read_text(encoding='utf-8')

    payload = {
        'type': 'result',
        'ping': {'jitter': 1.9, 'latency': 25.0},
        'download': {
            'bandwidth': 131_250_000,
            'bytes': 500_000_000,
            'latency': {'iqm': 43.0, 'low': 20.0, 'high': 70.0, 'jitter': 4.0},
        },
        'upload': {
            'bandwidth': 155_750_000,
            'bytes': 400_000_000,
            'latency': {'iqm': 25.0, 'low': 18.0, 'high': 45.0, 'jitter': 3.0},
        },
        'packetLoss': 0.0,
        'isp': 'Mundo Pacifico',
        'interface': {
            'internalIp': '192.168.1.20',
            'externalIp': '179.60.74.18',
            'name': 'Ethernet',
            'isVpn': False,
        },
        'server': {
            'id': 60496, 'name': 'MundoNET', 'location': 'Santiago', 'country': 'Chile',
            'host': 'speedtest.mundonet.cl', 'ip': '198.51.100.20',
        },
        'result': {'id': '19633225073', 'url': 'https://www.speedtest.net/result/c/example'},
    }

    parsed = speed._ookla_result(
        payload, 20.0,
        {'path': 'C:/speedtest.exe', 'version': 'Speedtest by Ookla 1.2.0'},
        selected_server_id=60496,
        link_speed_mbps=2500,
        ip_family='ipv4',
        bind_ip='192.168.1.20',
    )

    original_probe = speed._probe_ookla_cli
    original_run = speed.subprocess.run
    try:
        speed._probe_ookla_cli = lambda path, timeout=4: {
            'path': str(path), 'version': 'Speedtest by Ookla 1.2.0', 'official': True,
        }
        captured = {}

        class Completed:
            returncode = 0
            stdout = json.dumps(payload)
            stderr = ''

        def fake_run(args, *a, **kw):
            captured['args'] = list(args)
            return Completed()

        speed.subprocess.run = fake_run
        result = speed.run_ookla_speedtest(
            cli_path='C:/speedtest.exe',
            server_id=60496,
            ip_family='ipv4',
            bind_ip='192.168.1.20',
        )
    finally:
        speed._probe_ookla_cli = original_probe
        speed.subprocess.run = original_run

    args = captured.get('args', [])
    checks = [
        check('version', VERSION.isdecimal()),
        check('official_cli_source_ip_binding', '--ip=192.168.1.20' in args),
        check('server_still_locked', '--server-id=60496' in args),
        check('ipv4_detected_from_public_result', result.get('network_family') == 'ipv4'),
        check('route_binding_recorded', parsed.get('route_bound') is True and parsed.get('requested_ip_family') == 'ipv4'),
        check('idle_latency_preserved', parsed.get('latency_ms') == 25.0),
        check('loaded_download_latency_preserved', parsed.get('download_latency', {}).get('latency_ms') == 43.0),
        check('loaded_upload_latency_preserved', parsed.get('upload_latency', {}).get('latency_ms') == 25.0),
        check('ui_has_ip_route_selector', 'IPv4 (comparar con navegador)' in panel and 'Automática (recomendado)' in panel and 'IPv6 (avanzado)' in panel),
        check('ui_exposes_loaded_latency', 'Durante descarga' in panel and 'Durante subida' in panel),
        check('ui_exposes_route_family', 'Ruta {family}' in panel or 'Ruta {family.upper()}' in panel or 'Ruta ' in panel),
        check('no_exact_result_promise', 'idéntic' not in panel.lower() and 'exactamente igual' not in panel.lower()),
        check('engine_documents_source_binding', "args.append(f'--ip={source_ip}')" in engine),
    ]
    ok = all(checks)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
