"""Regresión de V0.10.0.0w — prueba activa real de velocidad de Internet."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION, STAGE
import core.internet_speed_test as speed


def check(name, condition):
    print(f"[{'PASS' if condition else 'FAIL'}] {name}: {bool(condition)}")
    return bool(condition)


def main():
    engine = (ROOT / 'core' / 'internet_speed_test.py').read_text(encoding='utf-8')
    panel = (ROOT / 'gui' / 'network_detail_panel.py').read_text(encoding='utf-8')

    old_meta = speed._metadata
    old_latency = speed._latency_series
    old_measure = speed._measure_direction
    try:
        speed._metadata = lambda timeout=5: {'colo': 'SCL', 'city': 'Santiago', 'country': 'CL'}
        speed._latency_series = lambda count=10, timeout=4: {'latency_ms': 8.2, 'jitter_ms': 1.1, 'samples_ms': [8.0, 8.4]}
        def fake_measure(direction, progress=None, streams=4):
            return {
                'mbps': 612.4 if direction == 'download' else 318.7,
                'points': [{'mbps': 612.4 if direction == 'download' else 318.7, 'seconds': 1.3}],
                'bytes': 50_000_000 if direction == 'download' else 25_000_000,
            }
        speed._measure_direction = fake_measure
        result = speed.InternetSpeedTest().run()
    finally:
        speed._metadata = old_meta
        speed._latency_series = old_latency
        speed._measure_direction = old_measure

    checks = [
        check('version', VERSION == '0.10.0.0w'),
        check('stage', STAGE == 'HEALTH_INTELLIGENCE_RECOVERY'),
        check('official_cloudflare_endpoints', "HOST = 'speed.cloudflare.com'" in engine and "DOWNLOAD_PATH = '/__down'" in engine and "UPLOAD_PATH = '/__up'" in engine),
        check('active_download_reads_real_bytes', 'response.read(256 * 1024)' in engine and 'total += len(chunk)' in engine),
        check('active_upload_streams_real_bytes', "conn.putheader('Content-Length'" in engine and 'conn.send(piece)' in engine),
        check('parallel_multistream', 'ThreadPoolExecutor' in engine and 'DEFAULT_STREAMS = 4' in engine),
        check('adaptive_ramp', 'DOWNLOAD_STAGES' in engine and 'UPLOAD_STAGES' in engine and 'TARGET_STAGE_SECONDS' in engine),
        check('cloudflare_90th_percentile_semantics', '_percentile(values, 0.90)' in engine),
        check('latency_persistent_https', 'HTTPSConnection(HOST' in engine and 'DNS/TCP/TLS fuera de las muestras' in engine),
        check('jitter_real_samples', 'abs(samples[i] - samples[i - 1])' in engine),
        check('ui_separates_traffic_from_capacity', "'TRÁFICO ↓'" in panel and "'TRÁFICO ↑'" in panel and 'PRUEBA DE VELOCIDAD DE INTERNET' in panel),
        check('ui_speed_metrics', "('download', 'DESCARGA'" in panel and "('upload', 'SUBIDA'" in panel and "('ping', 'PING'" in panel and "('jitter', 'JITTER'" in panel),
        check('speed_test_user_initiated', "command=self._start_speed_test" in panel and "text='Iniciar prueba'" in panel),
        check('speed_test_off_ui_thread', "threading.Thread(target=worker, name='CorePulseInternetSpeedTest'" in panel),
        check('worker_does_not_touch_tk', 'Sólo memoria compartida; nunca toca Tk desde el worker.' in panel),
        check('mock_download_value', result.get('download_mbps') == 612.4),
        check('mock_upload_value', result.get('upload_mbps') == 318.7),
        check('mock_latency_value', result.get('latency_ms') == 8.2 and result.get('jitter_ms') == 1.1),
        check('mock_data_usage', result.get('data_mb') == 75.0),
        check('real_or_na_flags', result.get('active_test') is True and result.get('synthetic') is False and result.get('estimated') is False),
    ]
    ok = all(checks)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
