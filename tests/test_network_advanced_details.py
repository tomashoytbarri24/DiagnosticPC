"""Regresión funcional de Network Advanced Details V0.10.0.0w."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION, STAGE
from core.network_details import _parse_link_speed_mbps


def check(name, condition):
    print(f"[{'PASS' if condition else 'FAIL'}] {name}: {bool(condition)}")
    return bool(condition)


def main():
    engine = (ROOT / 'core' / 'network_details.py').read_text(encoding='utf-8')
    panel = (ROOT / 'gui' / 'network_detail_panel.py').read_text(encoding='utf-8')
    app = (ROOT / 'main.py').read_text(encoding='utf-8')
    sidebar = (ROOT / 'gui' / 'sidebar.py').read_text(encoding='utf-8')
    nav = (ROOT / 'gui' / 'internal_navigation.py').read_text(encoding='utf-8')
    results = [
        check('version', VERSION == '0.10.0.0w'),
        check('stage', STAGE == 'HEALTH_INTELLIGENCE_RECOVERY'),
        check('gbps_parser', _parse_link_speed_mbps('2.5 Gbps') == 2500.0),
        check('mbps_parser', _parse_link_speed_mbps('866.7 Mbps') == 866.7),
        check('psutil_inventory', 'psutil.net_if_stats()' in engine and 'psutil.net_if_addrs()' in engine),
        check('psutil_real_traffic', 'psutil.net_io_counters(pernic=True)' in engine and 'recv_delta / elapsed' in engine),
        check('windows_native_inventory', 'Get-NetAdapter' in engine and 'Get-NetIPConfiguration' in engine),
        check('wifi_is_optional_real_data', "['netsh', 'wlan', 'show', 'interfaces']" in engine and 'signal_percent' in engine),
        check('separate_connectivity_tests', "'gateway': gateway_test" in engine and "'internet': internet_test" in engine and "'dns': dns_test" in engine),
        check('real_ping_loss', '_ping_series' in engine and "'loss_percent'" in engine),
        check('dns_resolution_real', 'socket.getaddrinfo' in engine),
        check('no_speedtest_synthetic', 'speedtest' not in engine.lower()),
        check('real_or_na_contract', 'synthetic' in engine and 'estimated' in engine and 'CorePulse muestra datos reales o N/A' in panel),
        check('sidebar_button', "self.btn_network = ctk.CTkButton" in app and "text='Red avanzada'" in app and "'btn_network': 'Red avanzada'" in sidebar),
        check('internal_navigation_registered', "'network': 'btn_network'" in nav and "'network': 'network_detail_panel'" in nav),
        check('page_open_method', 'def open_network_details(self):' in app and "activate_internal_page(self, 'network')" in app),
        check('identity_off_ui_thread', "threading.Thread(target=worker, name='CorePulseNetworkIdentity'" in panel),
        check('diagnostic_off_ui_thread', "threading.Thread(target=worker, name='CorePulseNetworkDiagnostic'" in panel),
        check('scroll_guard', '_start_scroll_watch' in panel and 'if not self._is_scrolling()' in panel),
        check('gateway_icmp_note', 'bloquear ICMP' in panel and 'pruebas independientes' in panel),
        check('back_button_no_arrow', "text='Volver al resumen'" in panel and '← Volver' not in panel),
    ]
    ok = all(results)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
