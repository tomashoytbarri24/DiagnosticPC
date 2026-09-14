"""V113 — benchmark visual añade cargas reales de CPU y RAM."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check(name, cond):
    if not cond:
        raise AssertionError(name)
    print('[PASS]', name)


def main():
    visual = (ROOT / 'core' / 'visual_benchmark.py').read_text(encoding='utf-8')
    panel = (ROOT / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')
    bench_panel = (ROOT / 'gui' / 'benchmark_panel.py').read_text(encoding='utf-8')
    check('cpu_phase_declared', "('cpu', 'CPU / Multinúcleo')" in visual)
    check('ram_phase_declared', "('ram', 'RAM / Ancho de banda')" in visual)
    check('cpu_uses_native_sha256', 'hashlib.sha256(payload).digest()' in visual and 'libera el GIL' in visual)
    check('cpu_uses_multiple_workers', "CorePulseCPUPhase-" in visual and "cpu_worker_count" in visual)
    check('ram_uses_real_memcpy', "ctypes.CDLL('msvcrt')" in visual and 'memcpy(dst_ptr, src_ptr, length)' in visual)
    check('ram_allocates_real_buffers', 'ctypes.create_string_buffer(size)' in visual and "working_set_mb" in visual)
    check('host_load_not_counted_as_fake_fps', "sha256_mb_s" in visual and "copy_gb_s" in visual and "REAL_FRAME_TIMES_WINDOW_45" in visual)
    check('cpu_and_ram_have_visuals', 'def draw_cpu_visual' in visual and 'def draw_ram_visual' in visual)
    check('host_workers_stop_between_phases', "if active_phase_key == 'cpu':" in visual and 'stop_cpu_load()' in visual and 'stop_ram_load()' in visual)
    check('ui_reports_eight_areas', '8 áreas de hardware' in panel and 'CPU SHA-256' in panel and 'RAM copia' in panel)
    check('phase_cards_show_host_throughput', "phase_key == 'cpu'" in panel and "phase_key == 'ram'" in panel and 'MB/s' in panel and 'GB/s' in panel)
    check('benchmark_header_is_hardware_wide', "eyebrow='Rendimiento de hardware'" in bench_panel)
    print('RESULTADO: PASS')


if __name__ == '__main__':
    main()
