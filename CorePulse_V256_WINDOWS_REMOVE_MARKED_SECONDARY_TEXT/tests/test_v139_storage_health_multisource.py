"""V139 — salud de almacenamiento multi-fuente sin inventar porcentajes."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION, STAGE
from core.storage_health import calculate_storage_health
import core.storage_summary_health as summary
import core.smartctl_storage as smartctl_storage


def check(name, cond):
    if not cond:
        raise AssertionError(name)
    print('[PASS]', name)


def telemetry(name='NVMe Test'):
    return {'_storage_devices': [{
        'name': name,
        'model': name,
        'life_percent': None,
        'temperature_c': None,
        'os_inventory': {'disk_index': 0, 'model': name},
    }]}


def main():
    check('version', VERSION == '139')
    check('stage', STAGE == 'STORAGE_HEALTH_MULTI_SOURCE_RELIABILITY')

    check('positive_windows_wear_6_to_94', calculate_storage_health({
        'Wear': 6, 'HealthStatus': 'Healthy', 'ReliabilityCounterLive': False,
    }) == 94.0)
    check('isolated_zero_wear_stays_na', calculate_storage_health({
        'Wear': 0, 'HealthStatus': 'Healthy', 'ReliabilityCounterLive': False,
    }) is None)
    check('corroborated_zero_wear_to_100', calculate_storage_health({
        'Wear': 0, 'HealthStatus': 'Healthy', 'ReliabilityCounterLive': True,
    }) == 100.0)
    check('zero_wear_not_100_when_windows_warns', calculate_storage_health({
        'Wear': 0, 'HealthStatus': 'Warning', 'ReliabilityCounterLive': True,
    }) is None)

    old_health = summary.get_storage_health
    old_nvme = summary.query_nvme_health_log
    old_smart = summary.query_smartctl_health
    try:
        summary.get_storage_health = lambda: [{
            'device_id': 0, 'model': 'NVMe Test', 'health_status': 'Healthy',
            'operational_status': 'OK', 'wear': None, 'health': None,
        }]
        summary.query_nvme_health_log = lambda idx: {}
        summary.query_smartctl_health = lambda idx: {
            'percentage_used': 8,
            'temperature_c': 36,
            'source': 'smartctl / smartmontools',
        }
        row = summary.collect_storage_summary_health(telemetry())[0]
        check('smartctl_nvme_wear_to_92', row['health'] == 92.0)
        check('smartctl_source_exposed', 'smartctl' in row['health_source'].lower())
        check('smartctl_temperature_used', row['temperature_c'] == 36.0)

        summary.query_smartctl_health = lambda idx: {}
        summary.get_storage_health = lambda: [{
            'device_id': 0, 'model': 'NVMe Test', 'health_status': 'Healthy',
            'operational_status': 'OK', 'wear': 0, 'health': 100.0,
            'health_source': 'Windows Storage Reliability Wear · vida restante 100 - desgaste',
            'reliability_counter_live': True,
        }]
        row = summary.collect_storage_summary_health(telemetry())[0]
        check('validated_windows_health_reaches_summary', row['health'] == 100.0)
        check('validated_windows_health_is_labeled_percent', '100%' in row['health_label'])
    finally:
        summary.get_storage_health = old_health
        summary.query_nvme_health_log = old_nvme
        summary.query_smartctl_health = old_smart

    # Parser smartctl: se prueba sin ejecutar binarios externos.
    old_find = smartctl_storage.find_smartctl
    old_run = smartctl_storage._run_json
    try:
        smartctl_storage.find_smartctl = lambda: r'C:\\smartctl.exe'
        smartctl_storage._run_json = lambda exe, target: {
            'model_name': 'NVMe Test', 'serial_number': 'ABC',
            'smart_status': {'passed': True},
            'temperature': {'current': 39},
            'nvme_smart_health_information_log': {
                'percentage_used': 11, 'power_on_hours': 1234,
                'available_spare': 100, 'media_errors': 0,
            },
        }
        out = smartctl_storage.query_smartctl_health(0)
        check('smartctl_parser_percentage_used', out.get('percentage_used') == 11.0)
        check('smartctl_parser_power_hours', out.get('power_on_hours') == 1234)
        check('smartctl_parser_temp', out.get('temperature_c') == 39.0)
    finally:
        smartctl_storage.find_smartctl = old_find
        smartctl_storage._run_json = old_run

    print('\nRESULTADO: PASS')


if __name__ == '__main__':
    main()
