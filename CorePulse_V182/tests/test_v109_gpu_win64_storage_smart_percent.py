"""V109 — GPU Win64 ABI, CPU benchmark sensor fallback y SMART NVMe % real."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION, STAGE
from core.nvme_smart_windows import parse_nvme_health_log
import core.storage_summary_health as storage_summary


def check(name, cond):
    if not cond:
        raise AssertionError(name)
    print('[PASS]', name)


def main():
    bench = (ROOT/'core'/'benchmark_engine.py').read_text(encoding='utf-8')
    panel = (ROOT/'gui'/'health_center_panel.py').read_text(encoding='utf-8')
    nvme = (ROOT/'core'/'nvme_smart_windows.py').read_text(encoding='utf-8')
    storage_health = (ROOT/'core'/'storage_health.py').read_text(encoding='utf-8')

    check('version', VERSION.isdecimal())
    check('stage', bool(STAGE))
    check('createwindow_argtypes_pointer_safe', 'user32.CreateWindowExW.argtypes' in bench and 'HINSTANCE_T' in bench and 'HMENU_T' in bench)
    check('gpu_argument11_overflow_fix', 'argument 11: OverflowError' in bench)
    check('cpu_direct_lhm_fallback', 'get_lhm_provider().cpu_temperature()' in panel)
    check('nvme_device_and_adapter_queries', 'STORAGE_ADAPTER_PROTOCOL_SPECIFIC_PROPERTY = 49' in nvme and 'STORAGE_DEVICE_PROTOCOL_SPECIFIC_PROPERTY = 50' in nvme)
    check('nvme_adapter_fallback_used', 'STORAGE_ADAPTER_PROTOCOL_SPECIFIC_PROPERTY,' in nvme)
    check('direct_cim_reliability_fallback', 'MSFT_StorageReliabilityCounter' in storage_health and 'Get-CimInstance' in storage_health)

    raw = bytearray(512)
    raw[3] = 100  # available spare
    raw[4] = 10   # spare threshold
    raw[5] = 7    # Percentage Used
    parsed = parse_nvme_health_log(bytes(raw))
    check('nvme_percentage_used_parsed', parsed.get('percentage_used') == 7)

    old_health = storage_summary.get_storage_health
    old_nvme = storage_summary.query_nvme_health_log
    try:
        storage_summary.get_storage_health = lambda: []
        storage_summary.query_nvme_health_log = lambda idx: {'percentage_used': 7, 'source': 'Windows NVMe SMART/Health Log (adapter)', 'query_scope': 'adapter'}
        telemetry = {'_storage_devices': [{'name':'NVMe Test','model':'NVMe Test','life_percent':None,'os_inventory':{'disk_index':0}}]}
        row = storage_summary.collect_storage_summary_health(telemetry)[0]
        check('smart_health_percent_from_real_wear', row.get('health') == 93.0)
        check('smart_health_label_percent', row.get('health_label') == 'Salud SMART  93%')
        check('smart_health_marked_derived', row.get('health_derived') is True)
    finally:
        storage_summary.get_storage_health = old_health
        storage_summary.query_nvme_health_log = old_nvme

    print('\nRESULTADO: PASS')


if __name__ == '__main__':
    main()
