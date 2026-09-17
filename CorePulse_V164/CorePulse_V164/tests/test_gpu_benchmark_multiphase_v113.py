"""V113 — benchmark GPU por áreas reales, sin etiquetar cargas no implementadas."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.visual_benchmark import visual_profile_info, _phase_result


def check(name, cond):
    if not cond:
        raise AssertionError(name)
    print('[PASS]', name)


def main():
    visual = (ROOT / 'core' / 'visual_benchmark.py').read_text(encoding='utf-8')
    panel = (ROOT / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')
    standard = visual_profile_info('standard')

    check('eight_real_phase_names', all(token in visual for token in (
        "('geometry', 'Geometría')",
        "('fill', 'Fill / fragmentos')",
        "('textures', 'Texturas / VRAM')",
        "('shaders', 'Shaders / ALU')",
        "('compute', 'Compute / GPGPU')",
        "('cpu', 'CPU / Multinúcleo')",
        "('ram', 'RAM / Ancho de banda')",
        "('combined', 'Carga combinada')",
    )))
    check('profile_has_phase_load_controls', all(k in standard for k in (
        'fill_passes', 'texture_size', 'texture_count', 'texture_passes', 'combined_texture_passes', 'shader_passes', 'combined_shader_passes', 'compute_buffer_mb', 'compute_passes', 'combined_compute_passes', 'cpu_hash_block_kb', 'cpu_worker_cap', 'ram_buffer_mb', 'ram_workers'
    )))
    check('fill_uses_real_blending_overdraw', 'glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)' in visual and 'draw_fill' in visual)
    check('textures_are_real_gl_resources', 'glGenTextures' in visual and 'glTexImage2D' in visual and 'glBindTexture' in visual)
    check('textures_are_cleaned_up', 'glDeleteTextures' in visual)
    check('phase_frametimes_are_separate', "phase_times[render_phase_key].append(frame_ms)" in visual)
    check('phase_telemetry_is_separate', "phase_samples[render_phase_key].append(row)" in visual)
    check('combined_is_primary_result', "'primary_phase': 'combined'" in visual and "primary = phase_by_key.get('combined')" in visual)
    check('ui_exposes_results_by_area', "text='Resultado por área'" in panel and "phase.get('frames_per_s')" in panel)
    check('ui_is_explicit_about_future_workloads', 'Ray Tracing seguirá en N/A hasta implementar una carga real' in panel and 'CPU multinúcleo' in panel and 'ancho de banda RAM' in panel)

    synthetic = _phase_result('x', 'X', [10.0] * 99 + [40.0])
    check('phase_fps_uses_real_frametimes', abs(synthetic['frames_per_s'] - (1000.0 / 10.3)) < 0.001)
    check('phase_1pct_low_uses_slowest_frames', synthetic['one_percent_low_fps'] == 25.0)
    check('no_random_or_simulated_path', 'random' not in visual.lower() and 'simulate' not in visual.lower())
    print('RESULTADO: PASS')


if __name__ == '__main__':
    main()
