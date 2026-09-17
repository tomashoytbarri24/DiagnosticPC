"""V100 — Speedtest by Ookla, servidor visible y comparación honesta."""
from __future__ import annotations

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
    engine = (ROOT / 'core' / 'internet_speed_test.py').read_text(encoding='utf-8')
    panel = (ROOT / 'gui' / 'network_detail_panel.py').read_text(encoding='utf-8')
    installer = (ROOT / 'Instalar_Speedtest_Ookla.bat').read_text(encoding='utf-8')

    # El JSON oficial usa bytes/s para formatos machine-readable.
    raw = {
        'type': 'result',
        'ping': {'jitter': 1.23, 'latency': 8.12},
        'download': {
            'bandwidth': 125_000_000, 'bytes': 500_000_000, 'elapsed': 5000,
            'latency': {'iqm': 15.4, 'low': 10.1, 'high': 22.8, 'jitter': 2.1},
        },
        'upload': {
            'bandwidth': 50_000_000, 'bytes': 100_000_000, 'elapsed': 4000,
            'latency': {'iqm': 12.0, 'low': 9.2, 'high': 18.0, 'jitter': 1.6},
        },
        'packetLoss': 0.0,
        'isp': 'ISP de prueba',
        'interface': {'externalIp': '203.0.113.10', 'name': 'Ethernet', 'isVpn': False},
        'server': {
            'id': 12345, 'name': 'Servidor ISP', 'location': 'Santiago', 'country': 'Chile',
            'host': 'speed.example.net', 'port': 8080, 'ip': '198.51.100.4',
        },
        'result': {'id': 'abc', 'url': 'https://www.speedtest.net/result/c/abc'},
    }
    parsed = speed._ookla_result(
        raw, 11.4,
        {'path': 'C:/Speedtest/speedtest.exe', 'version': 'Speedtest by Ookla 1.2.0'},
        selected_server_id=12345,
        link_speed_mbps=2500,
    )

    original_probe = speed._probe_ookla_cli
    original_run = speed.subprocess.run
    try:
        speed._probe_ookla_cli = lambda path, timeout=4: {'path': str(path), 'version': 'Speedtest by Ookla 1.2.0', 'official': True}

        class Completed:
            returncode = 0
            stdout = '''Closest servers:\n\n    ID  Name                           Location             Country\n==============================================================================\n 12345  Servidor ISP                   Santiago             Chile\n 67890  Fibra Test                     Valparaiso           Chile\n'''
            stderr = ''

        speed.subprocess.run = lambda *args, **kwargs: Completed()
        listed = speed.list_ookla_servers('C:/fake/speedtest.exe', limit=12)
    finally:
        speed._probe_ookla_cli = original_probe
        speed.subprocess.run = original_run

    original_find = speed.find_ookla_cli
    try:
        speed.find_ookla_cli = lambda: None
        missing = speed.InternetSpeedTest(provider='ookla').run()
    finally:
        speed.find_ookla_cli = original_find

    checks = [
        check('version', VERSION == '103'),
        check('official_provider_supported', "OOKLA_PROVIDER = 'ookla'" in engine and 'Speedtest by Ookla' in engine),
        check('no_automatic_license_acceptance', '--accept-license' not in engine and '--accept-gdpr' not in engine),
        check('no_silent_cloudflare_fallback_in_ookla_mode', missing.get('error_code') == 'OOKLA_CLI_NOT_FOUND' and missing.get('provider_key') == 'ookla'),
        check('machine_bandwidth_conversion_download', parsed.get('download_mbps') == 1000.0),
        check('machine_bandwidth_conversion_upload', parsed.get('upload_mbps') == 400.0),
        check('server_identity_preserved', parsed.get('server', {}).get('id') == 12345 and parsed.get('server', {}).get('name') == 'Servidor ISP'),
        check('isp_and_external_ip_preserved', parsed.get('isp') == 'ISP de prueba' and parsed.get('external_ip') == '203.0.113.10'),
        check('result_url_preserved', parsed.get('result_url') == 'https://www.speedtest.net/result/c/abc'),
        check('packet_loss_preserved', parsed.get('packet_loss_percent') == 0.0),
        check('server_lock_recorded', parsed.get('server_locked') is True and parsed.get('speedtest_net_comparable') is True),
        check('nearby_server_list_parsed', listed.get('ok') is True and [x.get('id') for x in listed.get('servers', [])] == [12345, 67890]),
        check('ui_defaults_to_ookla', "InternetSpeedTest(provider='ookla')" in panel and "Speedtest.net (Ookla)" in panel),
        check('ui_exposes_server_selector', 'self.speed_server_menu' in panel and 'Actualizar servidores' in panel),
        check('ui_exposes_actual_server', 'Servidor:' in panel and 'ID {server_id}' in panel),
        check('ui_exposes_provider_isp_and_loss', 'Motor usado: Speedtest by Ookla' in panel and 'ISP:' in panel and "('loss', 'PÉRDIDA'" in panel),
        check('ui_result_link', 'Ver resultado' in panel and 'https://www.speedtest.net/' in panel),
        check('cloudflare_marked_non_equivalent', 'no equivale 1:1 a Speedtest.net' in panel or 'no comparable 1:1 con Speedtest.net' in panel),
        check('installer_uses_official_winget_id', 'Ookla.Speedtest.CLI' in installer and 'winget install' in installer),
        check('installer_does_not_auto_accept_terms', '--accept-license' not in installer and '--accept-gdpr' not in installer),
    ]
    ok = all(checks)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
