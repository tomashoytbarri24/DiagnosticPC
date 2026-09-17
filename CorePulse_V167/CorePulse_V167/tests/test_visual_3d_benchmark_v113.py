"""V113 — benchmark visual 3D real, aislado y sin FPS simulados."""
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
    quick = visual_profile_info('quick')
    standard = visual_profile_info('standard')
    extended = visual_profile_info('extended')

    check('profiles_have_real_fixed_resolution', quick['width'] < standard['width'] < extended['width'])
    check('profiles_scale_real_geometry', quick['grid'] < standard['grid'] < extended['grid'] and quick['layers'] < standard['layers'] < extended['layers'])
    check('profiles_have_measurement_warmup', quick['warmup_seconds'] <= standard['warmup_seconds'] <= extended['warmup_seconds'])
    check('visible_fixed_win32_window', 'WS_CAPTION' in visual and 'WS_SYSMENU' in visual and 'WS_MINIMIZEBOX' in visual and 'ShowWindow' in visual)
    check('client_resolution_is_exact', 'AdjustWindowRectEx' in visual and 'GetClientRect' in visual)
    check('real_swapbuffers_loop', 'gdi32.SwapBuffers(hdc)' in visual and 'opengl32.glFinish()' in visual)
    check('real_3d_transformations', 'glFrustum' in visual and 'glRotatef' in visual and 'glTranslatef' in visual and 'glDrawArrays' in visual)
    check('real_frame_times', 'frame_times_ms.append(frame_ms)' in visual and "'one_percent_low_fps': one_low" in visual and "'frametime_avg_ms': avg_ms" in visual)
    check('one_percent_low_uses_slowest_one_percent', _one_percent_low_fps([10.0] * 99 + [40.0]) == 25.0)
    check('thermal_safety', 'cpu_tjmax_distance' in visual and 'gpu_temp_limit' in visual and "status = 'SAFETY_STOP'" in visual and 'REAL_LIMITS_ONLY' in visual)
    check('no_simulated_fps_path', 'random' not in visual.lower() and 'simulate' not in visual.lower())
    check('ui_has_visual_hardware_entry', "text='Benchmark visual de hardware'" in panel and "'Ejecutar benchmark'" in panel)
    check('ui_runs_isolated_job', "self._async('visual_benchmark', work, done)" in panel)
    check('ui_records_real_metrics', "'FPS combinado'" in panel and "'1% Low'" in panel and "'Frametime'" in panel and "'Uso GPU máx.'" in panel and "'CPU SHA-256'" in panel and "'RAM copia'" in panel)
    check('legacy_benchmark_ui_removed', 'Benchmark del sistema' not in panel and 'def _run_benchmark(' not in panel)
    print('RESULTADO: PASS')


if __name__ == '__main__':
    main()
