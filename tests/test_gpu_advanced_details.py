"""Regresión funcional de GPU Advanced Details V0.10.0.0w."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION, STAGE
from core.telemetry import _cert_gpu_details, _merge_gpu_inventory


def check(name, condition):
    print(f"[{'PASS' if condition else 'FAIL'}] {name}: {bool(condition)}")
    return bool(condition)


def sample(sensor_type, name, value, ident, ts=1000.0, gpu='GPU Prueba'):
    return {
        'hardware_type': 'GpuVendorA', 'hardware_name': gpu,
        'sensor_type': sensor_type, 'sensor_name': name,
        'value': value, 'identifier': ident, 'timestamp': ts,
        'source': 'LibreHardwareMonitorLib',
    }


def main():
    sensors = [
        sample('Temperature', 'GPU Core', 58.0, '/gpu/0/temp/0'),
        sample('Temperature', 'GPU Hot Spot', 69.0, '/gpu/0/temp/1'),
        sample('Load', 'GPU Core', 44.0, '/gpu/0/load/0'),
        sample('Load', 'GPU Memory', 21.0, '/gpu/0/load/1'),
        sample('Clock', 'GPU Core', 1845.0, '/gpu/0/clock/0'),
        sample('Clock', 'GPU Memory', 7000.0, '/gpu/0/clock/1'),
        sample('Power', 'GPU Package', 92.5, '/gpu/0/power/0'),
        sample('SmallData', 'GPU Memory Total', 8192.0, '/gpu/0/memory/0'),
        sample('SmallData', 'GPU Memory Used', 1536.0, '/gpu/0/memory/1'),
        sample('Fan', 'GPU Fan', 1450.0, '/gpu/0/fan/0'),
        sample('Control', 'GPU Fan', 36.0, '/gpu/0/control/0'),
        sample('Voltage', 'GPU Core', 0.975, '/gpu/0/voltage/0'),
    ]
    rows = _cert_gpu_details(sensors)
    gpu = rows[0] if rows else {}
    merged = _merge_gpu_inventory(rows, [
        {'name': 'GPU Prueba', 'driver_version': '1.2.3', 'vendor': 'Vendor A', 'video_processor': 'Chip X', 'adapter_ram_bytes_os': 8 * 1024**3},
        {'name': 'GPU secundaria', 'driver_version': '9.9.9', 'adapter_ram_bytes_os': 2 * 1024**3},
    ])

    main_text = (ROOT / 'main.py').read_text(encoding='utf-8')
    dashboard = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    nav = (ROOT / 'gui' / 'internal_navigation.py').read_text(encoding='utf-8')
    panel = (ROOT / 'gui' / 'gpu_detail_panel.py').read_text(encoding='utf-8')
    telemetry = (ROOT / 'core' / 'telemetry.py').read_text(encoding='utf-8')

    results = [
        check('version', VERSION == '0.10.0.0w'),
        check('stage', STAGE == 'HEALTH_INTELLIGENCE_RECOVERY'),
        check('gpu_page_registered', "'gpu_details': None" in nav and "'gpu_details': 'gpu_detail_panel'" in nav),
        check('main_opens_gpu_page', 'def open_gpu_details(self):' in main_text and "GPUDetailPanel(self, host)" in main_text),
        check('dashboard_gpu_clickable', "gpu_callback = getattr(app, 'open_gpu_details', None)" in dashboard and "app._gpu_details_button = ctk.CTkButton" in dashboard),
        check('dashboard_button_matches_cpu_language', "text='Ver detalles'" in dashboard and "theme_color('#0d2942')" in dashboard and "theme_color('#1d5278')" in dashboard),
        check('multi_gpu_selector', 'def _select_gpu(self, index):' in panel and "text=f'GPU {i} · {label}'" in panel),
        check('panel_uses_existing_snapshot', "getattr(self.app, 'latest_telemetry', None)" in panel),
        check('panel_does_not_poll_lhm_directly', 'get_lhm_provider' not in panel and 'LibreHardwareSensorProvider' not in panel),
        check('scroll_guard', '_start_scroll_watch' in panel and 'if not self._is_scrolling()' in panel),
        check('back_button_no_arrow', "text='Volver al resumen'" in panel and '←' not in panel),
        check('gpu_core_metrics', gpu.get('temperature_c') == 58.0 and gpu.get('hotspot_c') == 69.0 and gpu.get('usage_percent') == 44.0),
        check('gpu_memory_metrics', gpu.get('memory_total_mb') == 8192.0 and gpu.get('memory_used_mb') == 1536.0),
        check('gpu_advanced_metrics', gpu.get('fan_rpm') == 1450.0 and gpu.get('fan_control_percent') == 36.0 and gpu.get('core_voltage_v') == 0.975),
        check('gpu_sensor_inventory', gpu.get('sensor_count') == len(sensors) and len(gpu.get('sensors') or []) == len(sensors)),
        check('sensor_timestamp_preserved', all(row.get('timestamp') == 1000.0 for row in gpu.get('sensors') or [])),
        check('os_inventory_attached_only_to_match', isinstance(merged[0].get('os_inventory'), dict) and merged[0]['os_inventory'].get('driver_version') == '1.2.3'),
        check('inventory_only_gpu_keeps_na', len(merged) == 2 and merged[1].get('telemetry_available') is False and merged[1].get('temperature_c') is None and merged[1].get('usage_percent') is None),
        check('windows_gpu_inventory_extended', 'CurrentHorizontalResolution' in telemetry and 'CurrentRefreshRate' in telemetry and "'vendor': row.get('AdapterCompatibility')" in telemetry),
        check('real_or_na_copy', 'No deriva VRAM usada' in panel and 'REAL_OR_NA' in panel),
    ]
    ok = all(results)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
