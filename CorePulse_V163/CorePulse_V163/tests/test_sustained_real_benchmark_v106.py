"""V106 — benchmark sostenido real y sin WinSAT D3D como carga gráfica."""
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION, STAGE
from core.benchmark_engine import benchmark_cpu, benchmark_ram, benchmark_ssd


def check(name, cond):
    if not cond:
        raise AssertionError(name)
    print('[PASS]', name)


def main():
    engine = (ROOT/'core'/'benchmark_engine.py').read_text(encoding='utf-8')
    panel = (ROOT/'gui'/'health_center_panel.py').read_text(encoding='utf-8')
    check('version', VERSION == '106')
    check('stage', STAGE == 'SUSTAINED_REAL_BENCHMARK_SUITE')
    check('standard_suite_present', 'def run_standard_suite(' in engine)
    check('cpu_single_and_multi', "'CPU · 1 hilo'" in engine and "'CPU · multinúcleo'" in engine)
    check('ram_sustained_window', 'min_seconds=8.0' in engine)
    check('ssd_fsync_real_io', 'os.fsync' in engine and "'SSD · escritura secuencial'" in engine)
    check('gpu_opengl_real_workload', 'def _benchmark_gpu_opengl(' in engine and 'glDrawArrays' in engine)
    check('no_winsat_d3d_benchmark', "'winsat'" not in engine.lower())
    check('thermal_safety', 'cpu_temp >= 96.0' in engine and 'gpu_temp >= 92.0' in engine)
    check('panel_uses_standard_suite', 'run_standard_suite(progress_callback=progress, telemetry_sampler=telemetry_sample)' in panel)
    check('progress_ui', 'bench_progress_bar' in panel and 'Durante la carga' in panel)

    cpu = benchmark_cpu(0.5, threads=2)
    check('cpu_smoke_real_positive', (cpu.get('value') or 0) > 0 and (cpu.get('throughput_mbps') or 0) > 0)
    ram = benchmark_ram(32, 1)
    check('ram_smoke_real_positive', (ram.get('value') or 0) > 0)
    with tempfile.TemporaryDirectory() as td:
        ssd = benchmark_ssd(td, 64)
    check('ssd_smoke_read_write', (ssd.get('read_mbps') or 0) > 0 and (ssd.get('write_mbps') or 0) > 0)
    print('\nRESULTADO: PASS')


if __name__ == '__main__':
    main()
