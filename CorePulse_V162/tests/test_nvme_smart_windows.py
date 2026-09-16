"""Prueba offline del parser del SMART / Health Information Log NVMe."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.nvme_smart_windows import parse_nvme_health_log


def check(name, condition):
    ok = bool(condition)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {ok}")
    return ok


raw = bytearray(512)
raw[0] = 0
raw[1:3] = (319).to_bytes(2, 'little')       # ~45,9 °C
raw[3] = 100                                  # AvailableSpare
raw[4] = 10                                   # threshold
raw[5] = 4                                    # PercentageUsed
raw[32:48] = int(0x02D646B7).to_bytes(16, 'little')
raw[48:64] = int(0x02FA494C).to_bytes(16, 'little')
raw[112:128] = int(8179).to_bytes(16, 'little')
raw[128:144] = int(2234).to_bytes(16, 'little')
raw[144:160] = int(34).to_bytes(16, 'little')
raw[160:176] = int(0).to_bytes(16, 'little')
raw[176:192] = int(0x2248).to_bytes(16, 'little')
raw[200:202] = (319).to_bytes(2, 'little')
raw[202:204] = (338).to_bytes(2, 'little')

data = parse_nvme_health_log(raw)

checks = [
    check('critical_warning_is_direct', data.get('critical_warning') == 0),
    check('percentage_used_is_direct_not_health', data.get('percentage_used') == 4),
    check('available_spare_direct', data.get('available_spare_percent') == 100),
    check('power_cycles_direct', data.get('power_cycles') == 8179),
    check('power_on_hours_direct', data.get('power_on_hours') == 2234),
    check('unsafe_shutdowns_direct', data.get('unsafe_shutdowns') == 34),
    check('media_errors_real_zero', data.get('media_errors') == 0),
    check('error_log_entries_direct', data.get('error_log_entries') == 0x2248),
    check('data_read_is_converted_from_real_units', data.get('data_read_gb', 0) > 0),
    check('temperature_sensors_are_parsed', len(data.get('temperature_sensors') or []) == 2),
]

print('\nRESULTADO:', 'PASS' if all(checks) else 'FAIL')
raise SystemExit(0 if all(checks) else 1)
