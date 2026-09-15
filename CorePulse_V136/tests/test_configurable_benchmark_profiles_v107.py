"""V107 — perfiles múltiples y selección de componentes del benchmark."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION, STAGE
from core.benchmark_engine import BENCHMARK_PROFILES, benchmark_profile_info


def check(name, cond):
    if not cond:
        raise AssertionError(name)
    print('[PASS]', name)


def main():
    engine=(ROOT/'core'/'benchmark_engine.py').read_text(encoding='utf-8')
    ui=(ROOT/'gui'/'health_center_panel.py').read_text(encoding='utf-8')
    presentation=(ROOT/'core'/'benchmark_presentation.py').read_text(encoding='utf-8')
    check('version', VERSION == '107')
    check('stage', STAGE == 'CONFIGURABLE_MULTI_PROFILE_BENCHMARK')
    check('three_profiles', set(BENCHMARK_PROFILES) == {'quick','standard','extended'})
    check('quick_shorter_than_standard', benchmark_profile_info('quick')['cpu_seconds'] < benchmark_profile_info('standard')['cpu_seconds'])
    check('extended_longer_than_standard', benchmark_profile_info('extended')['gpu_seconds'] > benchmark_profile_info('standard')['gpu_seconds'])
    check('component_selection_engine', 'def run_benchmark_suite(' in engine and 'selected_components' in engine)
    check('ui_profile_selector', "values=['Rápido', 'Estándar', 'Extendido']" in ui)
    check('ui_component_switches', "('cpu', 'ram', 'ssd', 'gpu')" in ui and 'Puedes ejecutar sólo CPU, GPU o cualquier combinación.' in ui)
    check('skipped_is_not_failure', "raw_status == 'SKIPPED'" in presentation and "'status': 'Omitida'" in presentation)
    print('RESULTADO: PASS')

if __name__ == '__main__':
    main()
