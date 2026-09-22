import tempfile
import time
from pathlib import Path

from core.health_history import HealthHistoryStore


def main():
    with tempfile.TemporaryDirectory() as td:
        store = HealthHistoryStore(Path(td) / 'history.sqlite3')
        now = time.time()
        # período previo
        for idx in range(4):
            ts = now - 10 * 86400 + idx * 120
            store.record_snapshot({'cpu_temp': 60 + idx, 'ram_usage': 40, 'ram_available_gb': 8, 'gpu_temp': 55, 'gpu_usage': 20}, [{'health': 98, 'temperature_c': 40}], 90, ts=ts, battery_health_override=95, context={'process_count': 120})
        # período actual
        for idx in range(4):
            ts = now - 2 * 86400 + idx * 120
            store.record_snapshot({'cpu_temp': 70 + idx, 'ram_usage': 50, 'ram_available_gb': 7, 'gpu_temp': 61, 'gpu_usage': 25}, [{'health': 97, 'temperature_c': 42}], 86, ts=ts, battery_health_override=94, context={'process_count': 130})
        daily = store.daily_summary(30)
        comp = store.compare_periods(7)
        assert daily, 'daily summary missing'
        assert comp['comparable'] is True
        assert comp['metrics']['cpu_temp']['max_delta'] is not None
        store.record_stability_snapshot({'counts': {'bsod_bugcheck': 1, 'whea': 0, 'app_error': 2, 'app_hang': 1}, 'power_incident_count': 1, 'matched_total': 5}, 7)
        snaps = store.latest_stability_snapshots(period_days=7)
        assert snaps and snaps[0]['bsod_bugcheck'] == 1
    print('RESULTADO: PASS')


if __name__ == '__main__':
    main()
