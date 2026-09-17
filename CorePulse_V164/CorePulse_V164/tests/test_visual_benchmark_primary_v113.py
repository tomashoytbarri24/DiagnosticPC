"""V113 — benchmark visual 3D es la prueba principal independiente."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.visual_benchmark import visual_profile_info, _one_percent_low_fps


def check(name, cond):
    if not cond:
        raise AssertionError(name)
    print('[PASS]', name)


def main():
    visual = (ROOT / 'core' / 'visual_benchmark.py').read_text(encoding='utf-8')
    panel = (ROOT / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')
    benchmark_page = (ROOT / 'gui' / 'benchmark_panel.py').read_text(encoding='utf-8')

    check('profiles_have_warmup', all(visual_profile_info(k).get('warmup_seconds', 0) > 0 for k in ('quick', 'standard', 'extended')))
    check('win32_msg_layout_complete', "('lPrivate', wintypes.DWORD)" in visual)
    check('exact_client_resolution', 'AdjustWindowRectEx' in visual and 'GetClientRect' in visual and "'requested_resolution'" in visual)
    check('fixed_benchmark_window', 'WS_MINIMIZEBOX' in visual and 'WS_OVERLAPPEDWINDOW' not in visual)
    check('vsync_state_recorded', "'vsync_disabled': vsync_disabled" in visual and "'measurement_quality':" in visual)
    check('one_percent_low_is_slowest_frames', '_one_percent_low_fps(frame_times_ms)' in visual and _one_percent_low_fps([10.0] * 99 + [40.0]) == 25.0)
    check('warmup_not_counted', 'if measurement_start is not None:' in visual and 'frame_times_ms.append(frame_ms)' in visual)
    check('legacy_benchmark_not_imported', 'run_benchmark_suite' not in panel and 'benchmark_profile_info' not in panel)
    check('legacy_benchmark_not_exposed', 'Benchmark del sistema' not in panel and 'Selecciona qué componentes medir' not in panel and 'def _run_benchmark(' not in panel)
    check('visual_benchmark_is_primary', "'Benchmark visual 3D'" in panel and "title='Benchmark'" in benchmark_page)
    check('vram_sampling_real', "'gpu_vram_used_mb': gpu_vram_used_mb" in panel and "gpu.get('memory_used_mb')" in panel)
    print('RESULTADO: PASS')


if __name__ == '__main__':
    main()
