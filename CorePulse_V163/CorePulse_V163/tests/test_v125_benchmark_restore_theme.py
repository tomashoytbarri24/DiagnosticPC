"""V125 — benchmark real/configurable, restore points visibles y Temas destacado."""
from __future__ import annotations
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION, STAGE
from core.visual_benchmark import VISUAL_PROFILES, visual_profile_info
from core.benchmark_engine import BENCHMARK_PROFILES


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print('[PASS]', name)


def main():
    ui = (ROOT/'gui'/'health_center_panel.py').read_text(encoding='utf-8')
    visual = (ROOT/'core'/'visual_benchmark.py').read_text(encoding='utf-8')
    windows = (ROOT/'core'/'windows_health.py').read_text(encoding='utf-8')
    dashboard = (ROOT/'gui'/'dashboard.py').read_text(encoding='utf-8')

    check('version', VERSION == '125')
    check('stage', STAGE == 'REAL_CONFIGURABLE_BENCHMARK_RESTORE_POINTS_THEME_VISIBILITY')
    check('profiles_keep_three_levels', set(VISUAL_PROFILES) == {'quick','standard','extended'} and set(BENCHMARK_PROFILES) == {'quick','standard','extended'})
    check('visual_load_is_stronger', visual_profile_info('extended')['fill_passes'] >= 72 and visual_profile_info('extended')['compute_buffer_mb'] >= 64)
    check('visual_accepts_selected_components', 'components=None' in visual and 'selected_components' in visual and "gpu_phase_keys" in visual)
    check('config_before_run', "values=['Rápido', 'Estándar', 'Extendido']" in ui and '2 · Qué medir' in ui and '3 · Ejecutar' in ui)
    check('all_four_components', "('gpu', 'cpu', 'ram', 'ssd')" in ui and 'run_benchmark_suite(' in ui)
    check('gpu_real_visual_path', "components=['gpu']" in ui and 'run_visual_benchmark(' in ui)
    check('prominent_start_button', "text='INICIAR BENCHMARK'" in ui and 'height=42' in ui)
    check('gpu_adapter_mismatch_is_visible', 'GPU distinta a la supervisada' in ui and 'Renderer GPU real' in ui)
    check('restore_points_not_limited_to_five', 'Select-Object -First 5' not in windows and "ToString('yyyy-MM-dd HH:mm:ss')" in windows)
    check('restore_point_count_and_refresh', "'count': len(rows)" in windows and 'Actualizar lista' in ui and 'PUNTOS DE RESTAURACIÓN DEL SISTEMA' in ui)
    check('restore_point_details_visible', "point.get('CreationTime')" in ui and "point.get('Description')" in ui and "point.get('SequenceNumber')" in ui)
    check('theme_button_prominent', "PERSONALIZACIÓN" in dashboard and "text='◉  Temas'" in dashboard and "fg_color=theme_accent" in dashboard and "height=37" in dashboard)
    print('RESULTADO: PASS')


if __name__ == '__main__':
    main()
