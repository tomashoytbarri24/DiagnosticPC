"""Regresión de consistencia visual/diagnóstica para V0.9.19.1w."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.health_engine import evaluate_current_health
from core.version import VERSION, STAGE


def check(name, condition):
    print(f"[{'PASS' if condition else 'FAIL'}] {name}: {bool(condition)}")
    return bool(condition)


def main():
    dashboard = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    live = (ROOT / 'gui' / 'live_health_binding.py').read_text(encoding='utf-8')
    hardware = (ROOT / 'gui' / 'hardware_storage_view.py').read_text(encoding='utf-8')
    storage = (ROOT / 'gui' / 'storage_detail_panel.py').read_text(encoding='utf-8')
    telemetry_panel = (ROOT / 'gui' / 'telemetry_detail_panel.py').read_text(encoding='utf-8')

    elevated = evaluate_current_health(
        {'cpu_temp': 83.0, 'gpu_temp': 53.0},
        [],
        preliminary_score=100.0,
    )
    normal = evaluate_current_health(
        {'cpu_temp': 65.0, 'gpu_temp': 55.0},
        [],
        preliminary_score=100.0,
    )

    results = [
        check('version', VERSION == '0.10.0.0w'),
        check('stage', STAGE == 'HEALTH_INTELLIGENCE_RECOVERY'),
        check('cpu_83_is_attention', elevated['severity'] == 'ELEVATED' and elevated['status'] == 'ATENCIÓN TÉRMICA'),
        check('attention_caps_current_index', elevated['score'] == 84.0),
        check('normal_temp_remains_normal', normal['severity'] == 'NORMAL'),
        check('dashboard_uses_current_state_title', "'ESTADO ACTUAL'" in dashboard),
        check('dashboard_translates_valid', "VÁLIDAS" in dashboard),
        check('dashboard_uses_real_snapshot_age', '_relative_update_text' in dashboard),
        check('instant_vs_sustained_copy', 'Sin alertas sostenidas' in live and 'Atención instantánea' in live),
        check('temperature_visual_semantics', '_temperature_color' in hardware),
        check('storage_interpretation', '_health_state' in storage and '_temperature_state' in storage),
        check('metric_translation', "'cpu_temp': 'Temperatura de CPU'" in telemetry_panel),
        check('quality_translation', "'VALID': 'VÁLIDA'" in telemetry_panel),
    ]

    ok = all(results)
    print(f'\nRESULTADO: {"PASS" if ok else "FAIL"}')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
