"""V100 — benchmark legible sin rankings inventados."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION
from core.benchmark_presentation import benchmark_card_data, benchmark_delta_data, benchmark_overall_summary


def check(name, condition):
    print(f"[{'PASS' if condition else 'FAIL'}] {name}: {bool(condition)}")
    return bool(condition)


def main():
    panel = (ROOT / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')
    presentation = (ROOT / 'core' / 'benchmark_presentation.py').read_text(encoding='utf-8')
    suite = {
        'cpu': {'value': 5924.5, 'duration_s': 2.0},
        'ram': {'value': 4418.3, 'duration_s': 0.2, 'transferred_mb': 512},
        'ssd': {'read_mbps': 3171.5, 'write_mbps': 1094.1, 'size_mb': 96, 'duration_s': 0.2},
        'gpu': {'value': 2.0, 'status': 'OK', 'duration_s': 3.0},
    }
    cpu = benchmark_card_data('cpu', suite['cpu'])
    ram = benchmark_card_data('ram', suite['ram'])
    ssd = benchmark_card_data('ssd', suite['ssd'])
    gpu = benchmark_card_data('gpu', suite['gpu'])
    temp = benchmark_delta_data('cpu_temp', {'before': 66.0, 'after': 84.0, 'delta': 18.0})
    clock = benchmark_delta_data('cpu_ghz', {'before': 4.2, 'after': 4.2, 'delta': 0.0})
    overall = benchmark_overall_summary(suite)

    results = [
        check('version', VERSION == '103'),
        check('cpu_human_unit', cpu['headline'] == '5.924 operaciones/s'),
        check('cpu_no_fake_rating', 'Bueno' not in str(cpu) and 'Excelente' not in str(cpu)),
        check('ram_human_gbps', ram['headline'] == '4,42 GB/s' and '512 MB copiados' in ram['secondary']),
        check('ssd_read_write_clear', '3.172 MB/s de lectura' in ssd['headline'] and '1.094 MB/s de escritura' in ssd['secondary']),
        check('gpu_is_explicitly_referential', gpu['headline'] == 'Resultado orientativo de Windows' and 'no equivale a FPS' in gpu['interpretation']),
        check('human_cpu_temp_label', temp['label'] == 'Temperatura del CPU'),
        check('temperature_sentence', '66,0 °C → 84,0 °C' in temp['value'] and 'Subió 18,0 °C' in temp['change']),
        check('frequency_sentence', clock['label'] == 'Velocidad del CPU' and 'Sin cambio apreciable' in clock['change']),
        check('overall_completed', overall[0] == 'Benchmark completado'),
        check('human_results_renderer', 'def _render_benchmark_results(self):' in panel),
        check('no_raw_delta_labels_in_renderer', "self._kv(c,key" not in panel),
        check('before_after_explained_as_snapshots', 'No son máximos/mínimos del benchmark' in panel),
        check('real_or_na_preserved', 'resultados reales o N/A' in panel),
        check('no_fake_global_ranking', 'no compara este resultado contra otros PCs ni inventa rankings' in presentation),
    ]
    ok = all(results)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
