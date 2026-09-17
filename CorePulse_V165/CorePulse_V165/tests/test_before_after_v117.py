import tempfile
from pathlib import Path

import core.before_after as ba


def main():
    with tempfile.TemporaryDirectory() as td:
        ba.HISTORY_PATH = Path(td) / 'ops.json'
        ba.PATH = Path(td) / 'manual.json'
        before_tele = {'cpu_usage': 60, 'ram_usage': 70, 'ram_available_gb': 4, 'cpu_temp': 75}
        after_tele = {'cpu_usage': 35, 'ram_usage': 55, 'ram_available_gb': 7, 'cpu_temp': 66}
        session = ba.start_operation('Prueba', before_tele, runtime_context={'process_count': 150, 'network_latency_ms': 30})
        row = ba.finish_operation(session, after_tele, runtime_context={'process_count': 130, 'network_latency_ms': 24})
        assert row['comparison']['available'] is True
        assert row['comparison']['deltas']['ram_usage']['delta'] == -15
        assert row['comparison']['deltas']['process_count']['delta'] == -20
        assert row['comparison']['deltas']['network_latency_ms']['delta'] == -6
        assert row['before']['fps'] is None and row['after']['fps'] is None
        pending = ba.start_operation('Requiere reinicio', before_tele)
        ba.mark_operation(pending, status='pending_restart', note='reinicio')
        rows = ba.latest_operations(10)
        assert len(rows) == 2
        assert any(x['status'] == 'pending_restart' and x['after'] is None for x in rows)
    print('RESULTADO: PASS')


if __name__ == '__main__':
    main()
