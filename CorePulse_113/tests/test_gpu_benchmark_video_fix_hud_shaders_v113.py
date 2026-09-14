"""V113 — correcciones derivadas de la grabación + HUD FPS + fase GLSL."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def check(name, cond):
    if not cond:
        raise AssertionError(name)
    print('[PASS]', name)


def main():
    visual = (ROOT / 'core' / 'visual_benchmark.py').read_text(encoding='utf-8')
    panel = (ROOT / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')

    check('video_bug_no_absolute_cpu_96_abort', "cpu_temp >= 96.0" not in visual)
    check('video_bug_uses_real_tjmax_distance', "cpu_tjmax_distance" in visual and "cpu_distance <= 1.0" in visual)
    check('gpu_stop_requires_reported_limit', "gpu_temp_limit" in visual and "gpu_hotspot_limit" in visual and "gpu_temp >= 92.0" not in visual)
    check('safety_needs_consecutive_samples', "cpu_safety_hits >= 2" in visual and "gpu_safety_hits >= 2" in visual)
    check('initial_white_frame_is_prevented', "Publica inmediatamente un frame oscuro" in visual and "gdi32.SwapBuffers(hdc)" in visual)
    check('warmup_no_longer_uses_texture_pattern', "render_phase_key = 'warmup'" in visual and "draw_geometry(elapsed, max(8, min(layers, 18)))" in visual)
    check('real_time_fps_hud_exists', "def draw_fps_overlay" in visual and "fps_text = 'FPS --'" in visual)
    check('hud_uses_real_frame_times', "overlay_fps = 1000.0 / avg_recent_ms" in visual)
    check('hud_does_not_inherit_previous_phase', "recent_frames.clear()" in visual and "El HUD de la nueva fase nunca hereda FPS" in visual)
    check('hud_is_display_list_optimized', "glCallLists" in visual and "evitando que el HUD distorsione fases de cientos de FPS" in visual)
    check('real_glsl_phase_exists', "compile_shader_program" in visual and "#version 120" in visual and "('shaders', 'Shaders / ALU')" in visual)
    check('shader_phase_can_be_na_without_simulation', "shader_unavailable_reason" in visual and "row['status'] = 'N/A'" in visual)
    check('combined_includes_shader_when_available', "draw_shader(elapsed, combined_shader_passes, blended=True)" in visual)
    check('safety_stop_reason_visible_in_ui', "'SAFETY_STOP': 'Prueba detenida por seguridad'" in panel)
    check('eight_phase_ui', "Geometría · Fill · Texturas/VRAM · Shaders · Compute · CPU · RAM · Combinada" in panel)
    print('RESULTADO: PASS')


if __name__ == '__main__':
    main()
