"""V100 — jerarquía visual y conclusiones humanas del benchmark."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION
from core.benchmark_presentation import benchmark_card_data, benchmark_component_conclusion, benchmark_overall_summary


def check(name, condition):
    print(f"[{'PASS' if condition else 'FAIL'}] {name}: {bool(condition)}")
    return bool(condition)


def main():
    panel = (ROOT / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')
    suite = {
        'cpu': {'value': 5924.5, 'duration_s': 2.0},
        'ram': {'value': 4418.3, 'duration_s': 0.2, 'transferred_mb': 512},
        'ssd': {'read_mbps': 3171.5, 'write_mbps': 1094.1, 'size_mb': 96, 'duration_s': 0.2},
        'gpu': {'value': 2.0, 'status': 'OK', 'duration_s': 3.0},
    }
    compare = {
        'available': True,
        'deltas': {
            'cpu_temp': {'before': 66.0, 'after': 84.0, 'delta': 18.0},
            'cpu_ghz': {'before': 4.2, 'after': 4.2, 'delta': 0.0},
            'ram_usage': {'before': 56.2, 'after': 56.5, 'delta': 0.3},
            'gpu_temp': {'before': 42.0, 'after': 41.0, 'delta': -1.0},
        },
    }

    cpu = benchmark_card_data('cpu', suite['cpu'])
    ram = benchmark_card_data('ram', suite['ram'])
    ssd = benchmark_card_data('ssd', suite['ssd'])
    gpu = benchmark_card_data('gpu', suite['gpu'])
    cpu_conclusion = benchmark_component_conclusion('cpu', suite, compare)
    ram_conclusion = benchmark_component_conclusion('ram', suite, compare)
    overall = benchmark_overall_summary(suite)

    results = [
        check('version', VERSION == '103'),
        check('short_status_cpu', cpu['short_status'] == 'Medido'),
        check('short_status_ram', ram['short_status'] == 'Medida'),
        check('short_status_gpu', gpu['short_status'] == 'Referencia básica'),
        check('human_meaning_cpu', 'Muestra cuánto trabajo completó el CPU' in cpu['meaning']),
        check('human_meaning_ssd', 'transferencias secuenciales' in ssd['meaning']),
        check('gpu_not_fps', 'no representa FPS' in gpu['meaning']),
        check('cpu_hot_conclusion', cpu_conclusion[1] == 'amber' and 'terminó caliente' in cpu_conclusion[0]),
        check('ram_clear_conclusion', ram_conclusion[1] == 'green' and 'sin una alerta clara' in ram_conclusion[0]),
        check('overall_plain_language', overall[0] == 'Benchmark completado' and 'Debajo verás lo importante' in overall[1]),
        check('summary_title', "text='Resumen del benchmark'" in panel),
        check('meaning_block', "text='Qué significa'" in panel),
        check('technical_detail_secondary', 'Detalle:' in panel),
        check('component_conclusion_used', 'benchmark_component_conclusion(key, suite, compare_data)' in panel),
        check('no_repeated_completed_in_summary_row', "data.get('short_status')" in panel),
        check('real_or_na_policy_visible', 'no inventa rankings ni sustituye datos ausentes' in panel),
    ]
    ok = all(results)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
