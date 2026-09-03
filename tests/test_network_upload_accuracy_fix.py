"""Regresión V0.10.0.0w: el upload nunca puede inflarse por Server-Timing."""
from __future__ import annotations

from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION
import core.internet_speed_test as speed


def check(name, condition):
    print(f"[{'PASS' if condition else 'FAIL'}] {name}: {bool(condition)}")
    return bool(condition)


def main():
    engine = (ROOT / 'core' / 'internet_speed_test.py').read_text(encoding='utf-8')
    panel = (ROOT / 'gui' / 'network_detail_panel.py').read_text(encoding='utf-8')

    valid, note = speed._validate_against_link(1355.6, 2400.0)
    impossible, impossible_note = speed._validate_against_link(97285.7, 2400.0)
    no_link, no_link_note = speed._validate_against_link(800.0, None)

    # La etapa paralela debe ignorar bps individuales absurdos y usar bytes/tiempo.
    original_upload = speed._upload_one
    try:
        def fake_upload(size, timeout=30):
            time.sleep(0.08)
            return {'ok': True, 'bytes': int(size), 'seconds': 0.08, 'bps': 99_000_000_000.0}
        speed._upload_one = fake_upload
        stage = speed._parallel_stage('upload', 1_000_000, streams=4)
    finally:
        speed._upload_one = original_upload

    checks = [
        check('version', VERSION == '0.10.0.0w'),
        check('server_timing_not_upload_denominator', 'network_seconds = server_seconds if' not in engine),
        check('server_time_is_subtracted', 'duration - server_seconds' in engine),
        check('upload_waits_for_server_receive', 'response = conn.getresponse()' in engine and 'response_received = time.perf_counter()' in engine),
        check('parallel_uses_wall_clock_aggregate', 'total_bytes * 8.0 / elapsed' in engine and 'sum(stream_bps)' not in engine),
        check('physical_link_validator_exists', 'def _validate_against_link' in engine),
        check('normal_result_kept', valid == 1355.6 and note is None),
        check('impossible_97gbps_discarded', impossible is None and isinstance(impossible_note, str) and '2400.0 Mbps' in impossible_note),
        check('missing_link_does_not_invent_cap', no_link == 800.0 and no_link_note is None),
        check('parallel_result_not_stream_sum', stage.get('mbps') is not None and stage['mbps'] < 1000.0),
        check('panel_passes_negotiated_link', 'self._speed_runner.link_speed_mbps' in panel),
        check('panel_exposes_discarded_measurement', 'medición descartada' in panel and 'superar el enlace físico' in panel),
    ]
    ok = all(checks)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
