"""Regresión funcional de RAM Advanced Details V0.10.0.0w."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION, STAGE
import core.device_identity as identity


def check(name, condition):
    print(f"[{'PASS' if condition else 'FAIL'}] {name}: {bool(condition)}")
    return bool(condition)


def _fake_cim(class_name, props):
    if class_name == 'Win32_PhysicalMemory':
        return [
            {
                'DeviceLocator': 'ChannelA-DIMM0', 'BankLabel': 'BANK 0',
                'Manufacturer': 'Vendor A', 'PartNumber': 'ABC123', 'SerialNumber': 'SER1',
                'Capacity': 8 * 1024 ** 3, 'Speed': 3200, 'ConfiguredClockSpeed': 2933,
                'SMBIOSMemoryType': 26, 'MemoryType': 0, 'FormFactor': 12,
                'DataWidth': 64, 'TotalWidth': 64, 'ConfiguredVoltage': 1200,
                'MinVoltage': 1200, 'MaxVoltage': 1200,
                'InterleaveDataDepth': None, 'InterleavePosition': None,
            },
            {
                'DeviceLocator': 'ChannelB-DIMM0', 'BankLabel': 'BANK 2',
                'Manufacturer': 'Vendor A', 'PartNumber': 'ABC123', 'SerialNumber': 'SER2',
                'Capacity': 8 * 1024 ** 3, 'Speed': 3200, 'ConfiguredClockSpeed': 2933,
                'SMBIOSMemoryType': 26, 'MemoryType': 0, 'FormFactor': 12,
                'DataWidth': 64, 'TotalWidth': 64, 'ConfiguredVoltage': 1200,
                'MinVoltage': 1200, 'MaxVoltage': 1200,
                'InterleaveDataDepth': None, 'InterleavePosition': None,
            },
        ]
    if class_name == 'Win32_PhysicalMemoryArray':
        return {'MemoryDevices': 4, 'Location': 3, 'Use': 3}
    return None


def main():
    original = identity._cim
    identity._cim = _fake_cim
    try:
        ram = identity.collect_ram_identity()
    finally:
        identity._cim = original

    panel = (ROOT / 'gui' / 'ram_detail_panel.py').read_text(encoding='utf-8')
    dashboard = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    nav = (ROOT / 'gui' / 'internal_navigation.py').read_text(encoding='utf-8')
    main_text = (ROOT / 'main.py').read_text(encoding='utf-8')

    modules = ram.get('modules') or []
    results = [
        check('version', VERSION == '0.10.0.0w'),
        check('stage', STAGE == 'HEALTH_INTELLIGENCE_RECOVERY'),
        check('ram_inventory_capacity', ram.get('installed_capacity_gb') == 16.0),
        check('ram_inventory_module_count', ram.get('module_count') == 2),
        check('ram_inventory_slots_total', ram.get('slots_total') == 4),
        check('ram_inventory_slots_available', ram.get('slots_available') == 2),
        check('ram_inventory_ddr4', modules and modules[0].get('memory_type') == 'DDR4'),
        check('ram_inventory_sodimm', modules and modules[0].get('form_factor') == 'SODIMM'),
        check('ram_inventory_voltage', modules and modules[0].get('configured_voltage_v') == 1.2),
        check('ram_inventory_separates_configured_speed', modules and modules[0].get('configured_speed_mhz') == 2933),
        check('ram_policy_no_channel_inference', ram.get('policy') == 'REAL_OR_NA_NO_CHANNEL_OR_TIMING_INFERENCE'),
        check('dashboard_ram_clickable', "ram_callback = getattr(app, 'open_ram_details', None)" in dashboard),
        check('dashboard_ram_real_button', "app._ram_details_button = ctk.CTkButton" in dashboard and "text='Ver detalles'" in dashboard),
        check('internal_page_registered', "'ram_details': None" in nav and "'ram_details': 'ram_detail_panel'" in nav),
        check('main_opens_ram_page', 'def open_ram_details(self):' in main_text and 'RAMDetailPanel(self, host)' in main_text),
        check('ram_panel_uses_existing_snapshot', "getattr(self.app, 'latest_telemetry', None)" in panel),
        check('ram_panel_does_not_poll_psutil', 'import psutil' not in panel and 'psutil.virtual_memory()' not in panel),
        check('ram_panel_does_not_call_cim', '_cim(' not in panel and 'Win32_PhysicalMemory' not in panel),
        check('ram_identity_loaded_off_ui_thread', "threading.Thread(target=worker, name='CorePulseRAMIdentity'" in panel),
        check('ram_scroll_redraw_guard', 'if not self._is_scrolling():' in panel and 'StableScrollHost' in panel and 'body_scroll.is_scrolling()' not in panel),
        check('real_or_na_visible', 'CorePulse muestra datos reales o N/A' in panel),
        check('no_channel_timing_inference_copy', 'no deduce canal Single/Dual' in panel and 'timings CAS' in panel),
    ]
    ok = all(results)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
