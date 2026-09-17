"""V122 — autoridad SMART NVMe y rechazo de sentinels 0 ambiguos."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION, STAGE
import core.storage_summary_health as storage_summary
from core.storage_details import build_storage_detail_snapshot
from core.health_intelligence import build_health_intelligence


def check(name, cond):
    if not cond:
        raise AssertionError(name)
    print('[PASS]', name)


def _telemetry(name='NVMe Test', *, life=0.0, temp=0.0, disk_index=0):
    return {'_storage_devices': [{
        'name': name,
        'model': name,
        'life_percent': life,
        'temperature_c': temp,
        'os_inventory': {'disk_index': disk_index, 'model': name},
        '_metrics': {'life_percent': {'source': 'LibreHardwareMonitorLib'}},
    }]}


def main():
    check('version', VERSION == '122')
    check('stage', STAGE == 'STORAGE_NVME_AUTHORITY_AND_ZERO_SENTINEL_FIX')

    old_health = storage_summary.get_storage_health
    old_nvme = storage_summary.query_nvme_health_log
    try:
        # Reproduce el Acer del caso real: LHM entrega 0/0, Windows Reliability
        # devuelve Wear 0 y 60 °C, pero SMART NVMe directo entrega 6% usado y 35 °C.
        storage_summary.get_storage_health = lambda: [{
            'device_id': 0,
            'model': 'SAMSUNG MZVLQ512HBLU-00B00',
            'friendly_name': 'SAMSUNG MZVLQ512HBLU-00B00',
            'health_status': 'Healthy',
            'operational_status': 'OK',
            'wear': 0,
            'temperature': 60,
        }]
        storage_summary.query_nvme_health_log = lambda idx: {
            'percentage_used': 6,
            'temperature_c': 35,
            'source': 'Windows NVMe SMART/Health Log (device)',
            'query_scope': 'device',
        }
        row = storage_summary.collect_storage_summary_health(
            _telemetry('SAMSUNG MZVLQ512HBLU-00B00')
        )[0]
        check('nvme_health_wins_over_lhm_zero', row['health'] == 94.0)
        check('nvme_temperature_wins_over_lhm_zero', row['temperature_c'] == 35.0)
        check('nvme_temperature_wins_over_windows_60', row['temperature_c'] != 60.0)
        check('nvme_source_exposed', 'NVMe SMART' in row['health_source'])

        # Percentage Used = 0 sí es válido cuando procede del SMART NVMe directo.
        storage_summary.query_nvme_health_log = lambda idx: {
            'percentage_used': 0,
            'temperature_c': 37,
            'source': 'Windows NVMe SMART/Health Log (device)',
            'query_scope': 'device',
        }
        storage_summary.get_storage_health = lambda: [{
            'device_id': 0,
            'model': 'MSI M450 1TB',
            'friendly_name': 'MSI M450 1TB',
            'health_status': 'Healthy',
            'operational_status': 'OK',
            'wear': 0,
            'temperature': 60,
        }]
        row = storage_summary.collect_storage_summary_health(_telemetry('MSI M450 1TB'))[0]
        check('nvme_zero_used_means_100_remaining', row['health'] == 100.0)
        check('nvme_real_temp_37', row['temperature_c'] == 37.0)

        # Sin SMART directo, Wear=0 + Healthy no puede convertirse en 100% ni 0%.
        storage_summary.query_nvme_health_log = lambda idx: {}
        storage_summary.get_storage_health = lambda: [{
            'device_id': 0,
            'model': 'NVMe Ambiguous',
            'friendly_name': 'NVMe Ambiguous',
            'health_status': 'Healthy',
            'operational_status': 'OK',
            'wear': 0,
            'temperature': 0,
        }]
        row = storage_summary.collect_storage_summary_health(_telemetry('NVMe Ambiguous'))[0]
        check('ambiguous_zero_health_is_na', row['health'] is None)
        check('healthy_status_preserved', row['health_label'] == 'Estado  Saludable')
        check('zero_temperature_is_na', row['temperature_c'] is None)

        intel = build_health_intelligence({}, [row], preliminary_score=None)
        texts = ' '.join(x.get('text','') for x in intel.get('factors', []))
        check('na_storage_does_not_create_zero_percent_alert', '0%' not in texts)
    finally:
        storage_summary.get_storage_health = old_health
        storage_summary.query_nvme_health_log = old_nvme

    # Detalle: el SMART directo también debe ganar a LHM 0 y Windows 60.
    detail = build_storage_detail_snapshot(
        0,
        _telemetry('SAMSUNG MZVLQ512HBLU-00B00'),
        [{'index': 0, 'model': 'SAMSUNG MZVLQ512HBLU-00B00', 'health': None}],
        reliability_records=[{
            'device_id': 0,
            'model': 'SAMSUNG MZVLQ512HBLU-00B00',
            'health_status': 'Healthy',
            'wear': 0,
            'temperature': 60,
            'temperature_max': 0,
        }],
        nvme_smart={'percentage_used': 6, 'temperature_c': 35, 'source': 'Windows NVMe SMART/Health Log'},
    )
    check('detail_remaining_life_94', detail['remaining_life_percent'] == 94.0)
    check('detail_temp_35', detail['temperature_c'] == 35.0)
    check('detail_tempmax_zero_is_na', detail['temperature_max_c'] is None)

    print('\nRESULTADO: PASS')


if __name__ == '__main__':
    main()
