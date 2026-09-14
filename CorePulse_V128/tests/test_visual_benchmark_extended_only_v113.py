"""V113 — el benchmark principal usa solo el perfil extendido."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check(name, cond):
    if not cond:
        raise AssertionError(name)
    print('[PASS]', name)


def main():
    text = (ROOT / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')
    check('default_profile_extended', "self._benchmark_profile_key = 'extended'" in text)
    check('single_mode_header', "text='Modo de ejecución'" in text)
    check('single_mode_copy', 'No se ofrecen perfiles reducidos en la experiencia principal.' in text)
    check('main_button_execute', "'Ejecutar benchmark'" in text)
    check('run_forces_extended', "profile_key = 'extended'" in text)
    check('no_segmented_selector', "CTkSegmentedButton(" not in text or "values=['Rápido', 'Estándar', 'Extendido']" not in text)
    print('RESULTADO: PASS')


if __name__ == '__main__':
    main()
