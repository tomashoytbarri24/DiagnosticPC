"""V140 — Wear real de Windows y claridad de benchmark."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION, STAGE
from core.storage_health import calculate_storage_health


def check(name, cond):
    if not cond:
        raise AssertionError(name)
    print('[PASS]', name)


def main():
    check('version', VERSION.isdecimal())
    check('stage', bool(STAGE))
    check('zero_wear_with_live_counter_is_100', calculate_storage_health({
        'Wear': 0, 'HealthStatus': 'Healthy', 'OperationalStatus': 'OK',
        'ReliabilityCounterLive': True,
    }) == 100.0)
    check('zero_wear_without_live_counter_stays_na', calculate_storage_health({
        'Wear': 0, 'HealthStatus': 'Healthy', 'OperationalStatus': 'OK',
        'ReliabilityCounterLive': False,
    }) is None)
    check('positive_wear_still_real', calculate_storage_health({
        'Wear': 7, 'HealthStatus': 'Healthy', 'ReliabilityCounterLive': False,
    }) == 93.0)

    storage_src = (ROOT / 'core' / 'storage_health.py').read_text(encoding='utf-8')
    for token in ('FlushLatencyMax', 'ReadLatencyMax', 'WriteLatencyMax'):
        check(f'latency_evidence_{token}', token in storage_src)

    summary_src = (ROOT / 'core' / 'storage_summary_health.py').read_text(encoding='utf-8')
    check('summary_accepts_validated_zero_wear', 'windows_health is not None' in summary_src)

    visual_src = (ROOT / 'core' / 'visual_benchmark.py').read_text(encoding='utf-8')
    check('visual_phase_results_use_selected_phase_specs', 'for key, label in phase_specs:' in visual_src)
    check('visual_denominator_uses_actual_phases', 'len(phase_specs)' in visual_src)

    ui_src = (ROOT / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')
    check('ui_gpu_phase_filter', "gpu_phase_keys = {'geometry', 'fill', 'textures', 'shaders', 'compute', 'combined'}" in ui_src)
    check('ui_combined_phase_can_be_visible', "'combined'" in ui_src)
    check('ui_gpu_transition_explained', 'GPU 3D completada' in ui_src)
    check('ui_ssd_volume_visible', 'SSD · Volumen probado' in ui_src)

    print('\nRESULTADO: PASS')


if __name__ == '__main__':
    main()
