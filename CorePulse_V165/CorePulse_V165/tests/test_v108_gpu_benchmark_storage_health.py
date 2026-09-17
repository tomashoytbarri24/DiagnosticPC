"""V108 — compatibilidad GPU benchmark, telemetría y salud de almacenamiento."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION, STAGE
from core.before_after import capture_metrics
import core.storage_summary_health as storage_summary


def check(name, cond):
    if not cond:
        raise AssertionError(name)
    print('[PASS]', name)


def test_storage_summary():
    original_health = storage_summary.get_storage_health
    original_nvme = storage_summary.query_nvme_health_log
    try:
        storage_summary.get_storage_health = lambda: [{
            'device_id': 0,
            'model': 'NVMe Example 1TB',
            'friendly_name': 'NVMe Example 1TB',
            'health_status': 'Healthy',
            'operational_status': 'OK',
            'wear': 7,
            'temperature': 43,
            'total_gb': 953.9,
            'mount_points': 'C:',
        }]
        storage_summary.query_nvme_health_log = lambda idx: {
            'source': 'Windows NVMe SMART/Health Log',
            'percentage_used': 4,
            'temperature_c': 41,
        }
        telemetry = {'_storage_devices': [{
            'name': 'NVMe Example 1TB',
            'model': 'NVMe Example 1TB',
            'life_percent': None,
            'temperature_c': None,
            'total_space_gb': 0.0,
            'os_inventory': {
                'disk_index': 0,
                'model': 'NVMe Example 1TB',
                'size_bytes_os': 1_000_204_886_016,
            },
        }]}
        data = storage_summary.collect_storage_summary_health(telemetry)[0]
        check('nvme_remaining_life_derived', data['health'] == 96.0)
        check('nvme_label_is_explicit', data['health_label'] == 'Salud SMART  96%')
        check('nvme_temperature_fallback', data['temperature_c'] == 41.0)
        check('os_capacity_fallback', data['total_gb'] > 900)
    finally:
        storage_summary.get_storage_health = original_health
        storage_summary.query_nvme_health_log = original_nvme


def main():
    bench = (ROOT / 'core' / 'benchmark_engine.py').read_text(encoding='utf-8')
    main_py = (ROOT / 'main.py').read_text(encoding='utf-8')
    panel = (ROOT / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')
    check('version', VERSION == '109')
    check('stage', STAGE == 'GPU_WIN64_SMART_PERCENT_BENCHMARK_TELEMETRY_FIX')
    check('no_direct_hcursor_dependency', 'wintypes.HCURSOR' not in bench)
    check('win32_handle_aliases', "HCURSOR_T = getattr(wintypes, 'HCURSOR', wintypes.HANDLE)" in bench)
    check('benchmark_live_metric_fallback', 'def _benchmark_live_metrics(telemetry):' in panel)
    check('benchmark_observation_fallback', 'def _benchmark_observation_fallback(key, suite):' in panel)
    check('storage_health_background_worker', 'def _schedule_storage_health_refresh(self):' in main_py)

    snap = capture_metrics({
        'cpu_temp': None,
        'cpu_ghz': None,
        'gpu_temp': None,
        '_cpu': {'package_temp_c': 77.0, 'clock_avg_ghz': 3.41},
        '_gpus': [{'temperature_c': 61.0, 'usage_percent': 2.0}],
    })
    check('before_after_cpu_temp_nested_fallback', snap['cpu_temp'] == 77.0)
    check('before_after_cpu_clock_nested_fallback', snap['cpu_ghz'] == 3.41)
    check('before_after_gpu_temp_nested_fallback', snap['gpu_temp'] == 61.0)
    test_storage_summary()
    print('\nRESULTADO: PASS')


if __name__ == '__main__':
    main()
