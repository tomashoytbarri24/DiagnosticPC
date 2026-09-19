"""V114 — historial de benchmark, sensores y acceso al último PDF."""
from __future__ import annotations

from pathlib import Path
import tempfile
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION, STAGE
from core.health_history import HealthHistoryStore
from core.sensor_diagnostics import build_sensor_diagnostics


def check(name, cond):
    if not cond:
        raise AssertionError(name)
    print('[PASS]', name)


def main():
    check('version', VERSION.isdecimal())
    check('stage', bool(STAGE))

    snapshot = {
        'cpu_name': 'CPU Test',
        'gpu_name': 'GPU Test',
        '_metrics': {
            'cpu_usage': {'quality': 'VALID', 'source': 'psutil.cpu_percent'},
            'cpu_temp': {'quality': 'VALID', 'source': 'LibreHardwareMonitorLib'},
            'cpu_ghz': {'quality': 'VALID', 'source': 'LibreHardwareMonitorLib'},
            'ram_usage': {'quality': 'VALID', 'source': 'psutil.virtual_memory'},
            'gpu_usage': {'quality': 'VALID', 'source': 'LibreHardwareMonitorLib'},
            'gpu_temp': {'quality': 'VALID', 'source': 'LibreHardwareMonitorLib'},
        },
        '_hardware_capability_matrix': {
            'cpu': {
                'name': 'CPU Test',
                'metrics': {
                    'package_temp_c': {'available': True, 'quality': 'VALID', 'source': 'LibreHardwareMonitorLib'},
                    'clock_avg_ghz': {'available': True, 'quality': 'VALID', 'source': 'LibreHardwareMonitorLib'},
                    'package_power_w': {'available': False, 'quality': 'UNAVAILABLE', 'reason': 'SENSOR_NOT_EXPOSED'},
                },
            },
            'gpus': [{
                'name': 'GPU Test',
                'telemetry_available': True,
                'metrics': {
                    'usage_percent': {'available': True, 'quality': 'VALID', 'source': 'LibreHardwareMonitorLib'},
                    'temperature_c': {'available': True, 'quality': 'VALID', 'source': 'LibreHardwareMonitorLib'},
                    'hotspot_c': {'available': False, 'quality': 'UNAVAILABLE', 'reason': 'SENSOR_NOT_EXPOSED'},
                    'core_clock_mhz': {'available': True, 'quality': 'VALID', 'source': 'LibreHardwareMonitorLib'},
                    'power_w': {'available': True, 'quality': 'VALID', 'source': 'LibreHardwareMonitorLib'},
                },
            }],
            'storage': [{
                'name': 'SSD Test',
                'telemetry_available': True,
                'metrics': {
                    'temperature_c': {'available': True, 'quality': 'VALID', 'source': 'LibreHardwareMonitorLib'},
                    'life_percent': {'available': False, 'quality': 'UNAVAILABLE', 'reason': 'SENSOR_NOT_EXPOSED'},
                },
            }],
            'battery': {'inventory_available': False, 'metrics': {}},
        },
    }
    diag = build_sensor_diagnostics(snapshot)
    groups = {g['key']: g for g in diag['groups']}
    check('sensor_cpu_present', groups['cpu']['available'] >= 3)
    check('sensor_gpu_partial', groups['gpu']['state'] == 'PARTIAL')
    check('sensor_storage_real_or_na', groups['storage']['available'] == 1 and groups['storage']['total'] == 2)
    check('sensor_no_extra_probe_policy', diag['source'] == 'CURRENT_TELEMETRY_SNAPSHOT')

    with tempfile.TemporaryDirectory() as td:
        store = HealthHistoryStore(Path(td) / 'history.sqlite3')
        suite = {
            'started_at': 1000.0,
            'finished_at': 1010.0,
            'profile': 'STANDARD',
            'selected_components': ['cpu', 'gpu'],
            'duration_s': 10.0,
            'cpu': {'kind': 'CPU', 'status': 'OK', 'throughput_mbps': 5000.0, 'value': 20000.0},
            'ram': {'kind': 'RAM', 'status': 'SKIPPED'},
            'ssd': {'kind': 'SSD', 'status': 'SKIPPED'},
            'gpu': {'kind': 'GPU', 'status': 'OK', 'value': 150.0, 'unit': 'Mtri/s'},
        }
        row_id = store.record_benchmark_session(
            suite, profile='standard', components=['cpu', 'gpu'],
            hardware={'cpu_name': 'CPU Test', 'gpu_name': 'GPU Test'},
        )
        sessions = store.latest_benchmark_sessions(limit=3)
        check('benchmark_session_saved', bool(row_id) and len(sessions) == 1)
        check('benchmark_profile_saved', sessions[0]['profile'] == 'STANDARD')
        check('benchmark_components_saved', sessions[0]['components'] == ['cpu', 'gpu'])
        check('benchmark_suite_saved', sessions[0]['suite']['gpu']['value'] == 150.0)

    panel = (ROOT / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')
    main_py = (ROOT / 'main.py').read_text(encoding='utf-8')
    diagnostic = (ROOT / 'gui' / 'diagnostic_view.py').read_text(encoding='utf-8')
    check('benchmark_history_ui', 'Historial de benchmarks' in panel and 'latest_benchmark_sessions' in panel)
    check('sensor_diagnostics_ui', 'Compatibilidad de sensores' in panel and 'build_sensor_diagnostics' in panel)
    check('report_open_button', 'Abrir último PDF' in diagnostic and 'open_last_pdf_report' in main_py)
    check('report_folder_button', ('Mostrar carpeta' in diagnostic or 'Abrir carpeta de informes' in diagnostic) and 'show_last_pdf_report_folder' in main_py)
    check('report_path_persisted', "last_pdf_report.txt" in main_py and '_remember_last_pdf_report' in main_py)
    print('RESULTADO: PASS')


if __name__ == '__main__':
    main()
