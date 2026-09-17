"""Pruebas offline de la ficha universal de almacenamiento."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.storage_details import (
    build_storage_detail_snapshot,
    match_reliability_record,
    resolve_physical_disk_index,
)
from core.storage_health import calculate_storage_health
from core.telemetry import _merge_storage_inventory


def check(name, condition):
    ok = bool(condition)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {ok}")
    return ok


telemetry = {
    '_storage_devices': [
        {
            'name': 'ExampleDrive Q700',
            'temperature_c': 46.0,
            'temperature_sensors_c': [
                {'name': 'Temperature', 'value': 46.0, 'source': 'LibreHardwareMonitorLib'},
                {'name': 'Temperature 2', 'value': 55.0, 'source': 'LibreHardwareMonitorLib'},
            ],
            'warning_temperature_c': 80.0,
            'critical_temperature_c': 90.0,
            'life_percent': 96.0,
            'power_on_hours': 2234,
            'power_on_count': 8179,
            'data_read': 22696.0,
            'data_written': 2382.0,
            'free_space_gb': 120.0,
            'total_space_gb': 512.0,
            'used_space_percent': 76.6,
            'source': 'LibreHardwareMonitorLib',
            'inventory_sources': ['LibreHardwareMonitorLib', 'Win32_DiskDrive'],
            'os_inventory': {
                'model': 'ExampleDrive Q700',
                'serial_number': 'SERIAL-ABC',
                'firmware_revision': 'FW-1.2',
                'interface_type': 'SCSI',
                'media_type_os': 'Fixed hard disk media',
                'disk_index': 0,
                'os_status': 'OK',
            },
        },
        {
            'name': 'ArchiveDisk Z20',
            'temperature_c': 39.0,
            'life_percent': 100.0,
            'source': 'LibreHardwareMonitorLib',
            'os_inventory': {
                'model': 'ArchiveDisk Z20',
                'serial_number': 'SERIAL-XYZ',
                'disk_index': 1,
            },
        },
    ]
}

fast = [
    {
        'index': 0,
        'model': 'ExampleDrive Q700',
        'mount_points': 'N/A',
        'total_gb': 512.0,
        'health': 96.0,
        'used_percent': 76.6,
        'used_gb': 392.0,
        'temperature_c': 46.0,
    },
    {
        'index': 1,
        'model': 'ArchiveDisk Z20',
        'mount_points': 'D:',
        'total_gb': 1024.0,
        'health': 100.0,
        'used_percent': 50.0,
        'used_gb': 512.0,
        'temperature_c': 39.0,
    },
]

reliability = [
    {
        'device_id': 0,
        'model': 'ExampleDrive Q700',
        'serial': 'SERIAL-ABC',
        'firmware_version': 'FW-1.2',
        'mount_points': 'C:',
        'media_type': 'SSD',
        'bus_type': 'NVMe',
        'health_status': 'Healthy',
        'operational_status': 'OK',
        'wear': 4.0,
        'power_on_hours': 2234,
        'read_errors_total': 0,
        'read_errors_uncorrected': 0,
        'write_errors_total': 0,
        'write_errors_uncorrected': 0,
        'start_stop_cycles': 8179,
    },
    {
        'device_id': 1,
        'model': 'ArchiveDisk Z20',
        'serial': 'SERIAL-XYZ',
        'health_status': 'Healthy',
    },
]

nvme = {
    'source': 'Windows NVMe SMART/Health Log',
    'critical_warning': 0,
    'critical_warning_flags': [],
    'percentage_used': 4,
    'available_spare_percent': 100,
    'available_spare_threshold_percent': 10,
    'power_on_hours': 2234,
    'power_cycles': 8179,
    'unsafe_shutdowns': 34,
    'media_errors': 0,
    'error_log_entries': 8776,
    'data_read_gb': 24259.0,
    'data_written_gb': 31878.0,
}

record = match_reliability_record(telemetry['_storage_devices'][0], reliability)
snapshot = build_storage_detail_snapshot(0, telemetry, fast, reliability, nvme)
other = build_storage_detail_snapshot(1, telemetry, fast, reliability)

# Caso que reproduce el bug: Windows dice Wear=0 pero no existe sensor Life real.
no_life_telemetry = {
    '_storage_devices': [{
        'name': 'NoLife NVMe X1',
        'source': 'Win32_DiskDrive',
        'telemetry_available': False,
        'os_inventory': {
            'model': 'NoLife NVMe X1',
            'serial_number': 'NO-LIFE-1',
            'disk_index': 3,
            'os_status': 'OK',
        },
    }]
}
no_life_fast = [{
    'index': 0,
    'model': 'NoLife NVMe X1',
    'mount_points': 'E:',
    'total_gb': 1024.0,
    'health': None,
}]
no_life_reliability = [{
    'device_id': 3,
    'model': 'NoLife NVMe X1',
    'serial': 'NO-LIFE-1',
    'health_status': 'Healthy',
    'wear': 0.0,
}]
no_life = build_storage_detail_snapshot(
    0,
    no_life_telemetry,
    no_life_fast,
    no_life_reliability,
)


ambiguous_merge = _merge_storage_inventory(
    [
        {'name': 'TwinDisk X1', 'model': 'TwinDisk X1'},
        {'name': 'TwinDisk X1', 'model': 'TwinDisk X1'},
    ],
    [
        {'name': 'TwinDisk X1', 'model': 'TwinDisk X1', 'serial_number': 'TWIN-A', 'disk_index': 4},
        {'name': 'TwinDisk X1', 'model': 'TwinDisk X1', 'serial_number': 'TWIN-B', 'disk_index': 5},
    ],
)
unique_merge = _merge_storage_inventory(
    [{'name': 'UniqueDisk U7', 'model': 'UniqueDisk U7'}],
    [{'name': 'UniqueDisk U7', 'model': 'UniqueDisk U7', 'serial_number': 'UNIQUE-1', 'disk_index': 7}],
)

ui_source = (ROOT / 'gui' / 'storage_detail_panel.py').read_text(encoding='utf-8')
main_source = (ROOT / 'main.py').read_text(encoding='utf-8')
nav_source = (ROOT / 'gui' / 'internal_navigation.py').read_text(encoding='utf-8')

checks = [
    check('reliability_matches_same_serial', record and record.get('serial') == 'SERIAL-ABC'),
    check('physical_drive_index_is_exact', resolve_physical_disk_index(0, telemetry) == 0),
    check('exact_model_preserved', snapshot.get('model') == 'ExampleDrive Q700'),
    check('mount_point_can_be_completed_by_windows', snapshot.get('mount_points') == 'C:'),
    check('firmware_is_real_or_na', snapshot.get('firmware') == 'FW-1.2'),
    check('real_lhm_health_is_preserved', snapshot.get('health_percent') == 96.0),
    check('temperature_preserved', snapshot.get('temperature_c') == 46.0),
    check('direct_nvme_wear_is_not_health', snapshot.get('wear_percent') == 4 and snapshot.get('wear_source') == 'SMART NVMe'),
    check('direct_nvme_power_counters', snapshot.get('power_on_hours') == 2234 and snapshot.get('power_on_count') == 8179),
    check('direct_nvme_error_counters', snapshot.get('media_errors') == 0 and snapshot.get('error_log_entries') == 8776),
    check('direct_nvme_io_counters', snapshot.get('data_read_gb') == 24259.0 and snapshot.get('data_written_gb') == 31878.0),
    check('windows_wear_zero_does_not_become_100_health', no_life.get('health_percent') is None and no_life.get('wear_percent') == 0.0),
    check('storage_health_never_derives_100_minus_wear', calculate_storage_health({'Wear': 0}) is None),
    check('second_disk_does_not_inherit_first', other.get('serial') == 'SERIAL-XYZ' and other.get('model') == 'ArchiveDisk Z20'),
    check('identical_models_are_not_assigned_arbitrarily', len(ambiguous_merge) == 2 and all(row.get('os_inventory') is None and row.get('identity_ambiguous') for row in ambiguous_merge)),
    check('unique_model_can_receive_exact_disk_index', len(unique_merge) == 1 and (unique_merge[0].get('os_inventory') or {}).get('disk_index') == 7),
    check('detail_page_is_internal', "activate_internal_page(app, 'storage_details')" in ui_source and "'storage_details': None" in nav_source),
    check('disk_card_has_details_button', "text='Ver detalles'" in main_source and 'open_storage_details' in main_source),
    check('worker_does_not_touch_tk', "name='CorePulse-Storage-Details'" in ui_source and "job['done'].set()" in ui_source),
    check('na_rows_are_dynamic_not_four_fixed_errors', "self._set_error_rows(data)" in ui_source and "('read_errors_uncorrected', 'Lectura sin corregir')" not in ui_source),
    check('no_derived_life_text', 'Vida derivada' not in ui_source),
    check('real_or_na_policy_visible', 'REAL_OR_NA' in ui_source and snapshot.get('policy') == 'REAL_OR_NA'),
]

print('\nRESULTADO:', 'PASS' if all(checks) else 'FAIL')
raise SystemExit(0 if all(checks) else 1)
