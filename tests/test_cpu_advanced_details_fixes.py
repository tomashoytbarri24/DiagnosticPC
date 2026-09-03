"""Regresión de correcciones de CPU Advanced Details para V0.9.20.1w."""
from __future__ import annotations

from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.health_engine import evaluate_current_health
from core.telemetry import _cert_cpu_details
from core.version import VERSION, STAGE


def check(name, condition):
    print(f"[{'PASS' if condition else 'FAIL'}] {name}: {bool(condition)}")
    return bool(condition)


def main():
    now = time.time()
    sensors = [
        {'hardware_type': 'Cpu', 'hardware_name': 'Example CPU', 'sensor_name': 'CPU Package', 'sensor_type': 'Temperature', 'value': 83.0, 'identifier': '/cpu/0/temp/0', 'timestamp': now, 'source': 'LibreHardwareMonitorLib'},
        {'hardware_type': 'Cpu', 'hardware_name': 'Example CPU', 'sensor_name': 'Distance to TjMax Core #1', 'sensor_type': 'Temperature', 'value': 3.0, 'identifier': '/cpu/0/temp/d1', 'timestamp': now, 'source': 'LibreHardwareMonitorLib'},
        {'hardware_type': 'Cpu', 'hardware_name': 'Example CPU', 'sensor_name': 'CPU Total', 'sensor_type': 'Load', 'value': 41.0, 'identifier': '/cpu/0/load/0', 'timestamp': now, 'source': 'LibreHardwareMonitorLib'},
        {'hardware_type': 'Cpu', 'hardware_name': 'Example CPU', 'sensor_name': 'CPU Core #1', 'sensor_type': 'Clock', 'value': 4480.0, 'identifier': '/cpu/0/clock/1', 'timestamp': now, 'source': 'LibreHardwareMonitorLib'},
        {'hardware_type': 'Cpu', 'hardware_name': 'Example CPU', 'sensor_name': 'Bus Speed', 'sensor_type': 'Clock', 'value': 99.8, 'identifier': '/cpu/0/clock/bus', 'timestamp': now, 'source': 'LibreHardwareMonitorLib'},
        {'hardware_type': 'Cpu', 'hardware_name': 'Example CPU', 'sensor_name': 'CPU Package', 'sensor_type': 'Power', 'value': 42.0, 'identifier': '/cpu/0/power/0', 'timestamp': now, 'source': 'LibreHardwareMonitorLib'},
        {'hardware_type': 'Cpu', 'hardware_name': 'Example CPU', 'sensor_name': 'CPU Core', 'sensor_type': 'Voltage', 'value': 1.125, 'identifier': '/cpu/0/voltage/0', 'timestamp': now, 'source': 'LibreHardwareMonitorLib'},
    ]
    cpu = _cert_cpu_details(sensors)
    critical = evaluate_current_health({'cpu_temp': 97.0, '_cpu': {'distance_to_tjmax_min_c': 3.0}}, [], preliminary_score=100.0)

    cpu_panel = (ROOT / 'gui' / 'cpu_detail_panel.py').read_text(encoding='utf-8')
    trace_panel = (ROOT / 'gui' / 'telemetry_detail_panel.py').read_text(encoding='utf-8')
    dashboard_layout = (ROOT / 'gui' / 'dashboard_layout.py').read_text(encoding='utf-8')
    agent_reaction = (ROOT / 'core' / 'agent_reaction.py').read_text(encoding='utf-8')
    main_text = (ROOT / 'main.py').read_text(encoding='utf-8')

    results = [
        check('version', VERSION == '0.10.0.0w'),
        check('stage', STAGE == 'HEALTH_INTELLIGENCE_RECOVERY'),
        check('certified_cpu_keeps_sensor_inventory', cpu.get('sensor_count') == len(sensors) and len(cpu.get('sensors') or []) == len(sensors)),
        check('certified_cpu_keeps_advanced_values', cpu.get('total_load_percent') == 41.0 and cpu.get('bus_clock_mhz') == 99.8 and cpu.get('core_voltage_v') == 1.125),
        check('real_sensor_timestamps_preserved', all(item.get('timestamp') == now for item in cpu.get('sensors') or [])),
        check('critical_tjmax_semantics', critical.get('severity') == 'CRITICAL' and critical.get('status') == 'TEMPERATURA CRÍTICA' and critical.get('thermal_critical') is True),
        check('wmi_frequency_renamed', 'Frecuencia nominal (Windows)' in cpu_panel and 'Frecuencia máxima WMI' not in cpu_panel),
        check('windows_capability_labels_explicit', 'Virtualización firmware (Windows)' in cpu_panel and 'SLAT (Windows)' in cpu_panel),
        check('cpu_snapshot_fallback_rows', '_aggregate_sensor_rows' in cpu_panel and 'aggregate_fallback' in cpu_panel),
        check('tjmax_distance_uses_inverse_color_semantics', '_distance_to_tjmax_color' in cpu_panel and '_sensor_value_color' in cpu_panel),
        check('trace_snapshot_timestamp_fallback', "meta.get('snapshot_timestamp')" in trace_panel and 'snapshot_timestamp,' in trace_panel),
        check('trace_prefers_sensor_timestamp', trace_panel.index("meta.get('sensor_timestamp')") < trace_panel.index("meta.get('snapshot_timestamp')")),
        check('trace_ui_understands_certified_timestamp_keys', "meta.get('sensor_timestamp')" in trace_panel and "meta.get('snapshot_timestamp')" in trace_panel),
        check('agent_card_no_false_normal_state', "display['prefix']" in dashboard_layout and 'NINGUNA SOSTENIDA' in agent_reaction and 'CRÍTICA INSTANTÁNEA' in agent_reaction),
        check('cpu_transition_loader', 'Cargando información del procesador…' in main_text and 'host.lift()' in main_text and 'update_idletasks()' in main_text),
    ]
    ok = all(results)
    print(f'\nRESULTADO: {"PASS" if ok else "FAIL"}')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
