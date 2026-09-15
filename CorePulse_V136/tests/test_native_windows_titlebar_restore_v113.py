"""V113 — restauración del borde nativo de Windows para controles exactos."""
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
    main_py = (ROOT / 'main.py').read_text(encoding='utf-8')
    layout = (ROOT / 'gui' / 'dashboard_layout.py').read_text(encoding='utf-8')
    check('native_single_row_layout_restored', "self.grid_rowconfigure(0, weight=1)" in main_py and "self.sidebar.grid(row=0, column=0, sticky='nsew')" in main_py and "self.main_content.grid(row=0, column=1, sticky='nsew', padx=15, pady=15)" in main_py)
    check('custom_titlebar_builder_is_noop', 'Compatibilidad: V113 vuelve al borde nativo de Windows.' in main_py)
    check('no_forced_overrideredirect_anymore', 'self.overrideredirect(True)' not in main_py)
    check('native_controls_needed_for_exact_windows_buttons', "self.protocol('WM_DELETE_WINDOW', self.on_close)" in main_py)
    check('fullscreen_layout_no_custom_chrome_hooks', '_suspend_custom_window_chrome' not in layout and '_apply_custom_window_chrome' not in layout)
    print('RESULTADO: PASS')


if __name__ == '__main__':
    main()
