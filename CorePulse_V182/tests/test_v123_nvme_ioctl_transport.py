"""V123 — transporte IOCTL NVMe completo y fallback seguro."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION, STAGE
import core.storage_summary_health as storage_summary


def check(name, cond):
    if not cond:
        raise AssertionError(name)
    print('[PASS]', name)


def _telemetry():
    return {'_storage_devices': [{
        'name': 'NVMe Test',
        'model': 'NVMe Test',
        'life_percent': 0.0,
        'temperature_c': 0.0,
        'os_inventory': {'disk_index': 0, 'model': 'NVMe Test'},
    }]}


def main():
    check('version', VERSION.isdecimal())
    check('stage', bool(STAGE))

    source = (ROOT / 'core' / 'nvme_smart_windows.py').read_text(encoding='utf-8')
    check('ioctl_full_input_buffer', 'io_buffer_size = len(payload)' in source)
    check('ioctl_same_in_out_size', source.count('io_buffer_size,') >= 2)

    old_health = storage_summary.get_storage_health
    old_nvme = storage_summary.query_nvme_health_log
    try:
        storage_summary.get_storage_health = lambda: [{
            'device_id': 0,
            'model': 'NVMe Test',
            'friendly_name': 'NVMe Test',
            'health_status': 'Healthy',
            'operational_status': 'OK',
            'wear': 0,
            'temperature': 41,
        }]

        def boom(_idx):
            raise OSError('miniport no expone SMART directo')

        storage_summary.query_nvme_health_log = boom
        row = storage_summary.collect_storage_summary_health(_telemetry())[0]
        check('nvme_exception_does_not_drop_windows_status', row['health_label'] == 'Estado  Saludable')
        check('nvme_exception_does_not_fake_percent', row['health'] is None)
        check('windows_temperature_survives_nvme_failure', row['temperature_c'] == 41.0)
    finally:
        storage_summary.get_storage_health = old_health
        storage_summary.query_nvme_health_log = old_nvme

    print('\nRESULTADO: PASS')


if __name__ == '__main__':
    main()
