"""Regresión V100 — corriente real de batería y UI desktop-aware."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION, STAGE
import core.battery_health as battery_health


def check(name, cond):
    if not cond:
        raise AssertionError(name)
    print('[PASS]', name)


def main():
    ui = (ROOT / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')
    telemetry = (ROOT / 'core' / 'telemetry.py').read_text(encoding='utf-8')
    telemetry_full = (ROOT / 'core' / 'telemetry_full.py').read_text(encoding='utf-8')
    battery_src = (ROOT / 'core' / 'battery_health.py').read_text(encoding='utf-8')

    check('version', VERSION.isdecimal())
    check('stage', bool(STAGE))
    check('battery_card_requires_presence', "if self._battery is not None and present:" in ui)
    check('desktop_grid_reflows', 'row_index, column_index = divmod(index, 3)' in ui)
    check('current_visible', "('Corriente', current_text" in ui or "'Corriente', current_text" in ui)
    check('derived_current_is_labeled', 'desde Rate/Voltage reales' in ui)
    check('lhm_current_normalized_a_to_ma', "curr['value'] * 1000.0" in telemetry and "curr['value'] * 1000.0" in telemetry_full)
    check('zero_values_preserved', 'def _first_num(*values):' in battery_src)
    check('wmi_presence_explicit', "'detected': bool(obj.get('Detected'))" in battery_src)

    original_wmi = battery_health._wmi_battery_data
    original_report = battery_health._powercfg_battery_report
    original_psutil = battery_health.psutil.sensors_battery
    try:
        battery_health._powercfg_battery_report = lambda: {}
        battery_health.psutil.sensors_battery = lambda: None

        # Escritorio: ninguna fuente certifica una batería física.
        battery_health._wmi_battery_data = lambda: {'detected': False, 'source': 'root/WMI Battery* classes'}
        desktop = battery_health.collect_battery_health({})
        check('desktop_battery_absent', desktop.get('present') is False)

        # WMI real: 30 W / 15 V = 2 A = 2000 mA.
        battery_health._wmi_battery_data = lambda: {
            'detected': True,
            'voltage_v': 15.0,
            'current_ma_derived': -2000.0,
            'charge_discharge_rate_w': -30.0,
            'source': 'root/WMI Battery* classes',
        }
        derived = battery_health.collect_battery_health({})
        check('derived_real_current', derived.get('current_ma') == -2000.0)
        check('derived_traceability', derived.get('current_derived_from_real') is True and derived.get('current_source') == 'Windows WMI · Rate/Voltage')

        # Un cero real de LHM no debe convertirse en N/A ni ser reemplazado por fallback.
        zero = battery_health.collect_battery_health({'_battery': {'current_ma': 0.0, 'voltage_v': 15.0}})
        check('zero_current_preserved', zero.get('current_ma') == 0.0)
        check('lhm_current_preferred', zero.get('current_source') == 'LibreHardwareMonitor · sensor Current')
    finally:
        battery_health._wmi_battery_data = original_wmi
        battery_health._powercfg_battery_report = original_report
        battery_health.psutil.sensors_battery = original_psutil

    print('RESULTADO: PASS (15 checks)')


if __name__ == '__main__':
    main()
