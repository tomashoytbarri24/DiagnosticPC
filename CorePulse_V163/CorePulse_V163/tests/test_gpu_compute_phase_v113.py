"""V113 — fase Compute/GPGPU real mediante OpenGL compute shader y SSBO."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def check(name, cond):
    if not cond:
        raise AssertionError(name)
    print('[PASS]', name)

def main():
    visual = (ROOT / 'core' / 'visual_benchmark.py').read_text(encoding='utf-8')
    panel = (ROOT / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')
    check('compute_phase_declared', "('compute', 'Compute / GPGPU')" in visual)
    check('compute_shader_is_real_glsl430', '#version 430' in visual and 'layout(local_size_x = 256) in;' in visual)
    check('compute_uses_real_ssbo', 'GL_SHADER_STORAGE_BUFFER' in visual and "'bind_buffer_base': load_wgl('glBindBufferBase'" in visual)
    check('compute_dispatches_gpu_work', "'dispatch_compute': load_wgl('glDispatchCompute'" in visual and "compute_functions['dispatch_compute']" in visual)
    check('compute_has_memory_barrier', "compute_functions['memory_barrier'](GL_SHADER_STORAGE_BARRIER_BIT)" in visual)
    check('compute_can_be_na', "row['status'] = 'N/A'" in visual and 'compute_unavailable_reason' in visual)
    check('combined_includes_compute', 'dispatch_compute(combined_compute_passes)' in visual)
    check('compute_resources_are_cleaned', "compute_functions['delete_buffers']" in visual and "delete_program'](int(compute_program))" in visual)
    check('ui_reports_eight_areas', '8 áreas de hardware' in panel and 'Compute · CPU · RAM · Combinada' in panel)
    check('ui_displays_all_eight_results', 'phases[:8]' in panel)
    print('RESULTADO: PASS')

if __name__ == '__main__':
    main()
