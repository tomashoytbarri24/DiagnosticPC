"""Regresión de la vista CPU avanzada introducida en V0.9.20.0w."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import core.device_identity as device_identity
from core.telemetry_full import _cpu_details
from core.version import VERSION, STAGE


def check(name, condition):
    print(f"[{'PASS' if condition else 'FAIL'}] {name}: {bool(condition)}")
    return bool(condition)


def main():
    original_first_row = device_identity._first_row
    try:
        device_identity._first_row = lambda _cls, _props: {
            'Name': 'Example CPU',
            'Manufacturer': 'Example Vendor',
            'SocketDesignation': 'SOCKET 0',
            'MaxClockSpeed': 4200,
            'CurrentClockSpeed': 3900,
            'NumberOfCores': 8,
            'NumberOfLogicalProcessors': 16,
            'Architecture': 9,
            'AddressWidth': 64,
            'DataWidth': 64,
            'L2CacheSize': 4096,
            'L3CacheSize': 16384,
            'VirtualizationFirmwareEnabled': True,
            'SecondLevelAddressTranslationExtensions': True,
            'VMMonitorModeExtensions': True,
        }
        identity = device_identity.collect_cpu_identity()
    finally:
        device_identity._first_row = original_first_row

    sensors = [
        {'hardware_type': 'Cpu', 'hardware_name': 'Example CPU', 'sensor_name': 'CPU Package', 'sensor_type': 'Temperature', 'value': 71.5, 'identifier': '/cpu/0/temp/0', 'timestamp': 1.0},
        {'hardware_type': 'Cpu', 'hardware_name': 'Example CPU', 'sensor_name': 'CPU Total', 'sensor_type': 'Load', 'value': 44.0, 'identifier': '/cpu/0/load/0', 'timestamp': 1.0},
        {'hardware_type': 'Cpu', 'hardware_name': 'Example CPU', 'sensor_name': 'CPU Core #1', 'sensor_type': 'Clock', 'value': 4100.0, 'identifier': '/cpu/0/clock/1', 'timestamp': 1.0},
        {'hardware_type': 'Cpu', 'hardware_name': 'Example CPU', 'sensor_name': 'CPU Core #2', 'sensor_type': 'Clock', 'value': 3900.0, 'identifier': '/cpu/0/clock/2', 'timestamp': 1.0},
        {'hardware_type': 'Cpu', 'hardware_name': 'Example CPU', 'sensor_name': 'CPU Package', 'sensor_type': 'Power', 'value': 42.3, 'identifier': '/cpu/0/power/0', 'timestamp': 1.0},
        {'hardware_type': 'Cpu', 'hardware_name': 'Example CPU', 'sensor_name': 'CPU Core', 'sensor_type': 'Voltage', 'value': 1.125, 'identifier': '/cpu/0/voltage/0', 'timestamp': 1.0},
    ]
    dynamic = _cpu_details(sensors)
    empty = _cpu_details([])

    main_text = (ROOT / 'main.py').read_text(encoding='utf-8')
    dashboard_text = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    nav_text = (ROOT / 'gui' / 'internal_navigation.py').read_text(encoding='utf-8')
    panel_text = (ROOT / 'gui' / 'cpu_detail_panel.py').read_text(encoding='utf-8')

    results = [
        check('version', VERSION == '0.10.0.0w'),
        check('stage', STAGE == 'HEALTH_INTELLIGENCE_RECOVERY'),
        check('cpu_identity_architecture', identity.get('architecture') == 'x64'),
        check('cpu_identity_topology', identity.get('cores') == 8 and identity.get('threads') == 16),
        check('cpu_identity_caches', identity.get('l2_cache_kb') == 4096 and identity.get('l3_cache_kb') == 16384),
        check('cpu_dynamic_temperature', dynamic.get('package_temp_c') == 71.5),
        check('cpu_dynamic_clock_average', dynamic.get('clock_avg_ghz') == 4.0),
        check('cpu_dynamic_power_voltage', dynamic.get('package_power_w') == 42.3 and dynamic.get('core_voltage_v') == 1.125),
        check('cpu_sensor_inventory', dynamic.get('sensor_count') == 6 and len(dynamic.get('sensors') or []) == 6),
        check('real_or_na_empty', empty.get('package_temp_c') is None and empty.get('package_power_w') is None and empty.get('quality') == 'UNAVAILABLE'),
        check('internal_page_registered', "'cpu_details': None" in nav_text and "'cpu_details': 'cpu_detail_panel'" in nav_text),
        check('main_opens_cpu_page', 'def open_cpu_details(self):' in main_text and 'CPUDetailPanel(self, host)' in main_text),
        check('dashboard_cpu_clickable', 'open_cpu_details' in dashboard_text and 'Ver detalles' in dashboard_text),
        check('panel_uses_existing_snapshot', "getattr(self.app, 'latest_telemetry', None)" in panel_text),
        check('panel_does_not_poll_lhm_directly', 'get_lhm_provider' not in panel_text and 'get_system_telemetry' not in panel_text),
        check('identity_loaded_off_ui_thread', "name='CorePulseCPUIdentity'" in panel_text and 'threading.Thread' in panel_text),
    ]

    ok = all(results)
    print(f'\nRESULTADO: {"PASS" if ok else "FAIL"}')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
