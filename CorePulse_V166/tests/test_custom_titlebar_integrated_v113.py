"""V113 — CorePulse integra su propia barra de ventana."""
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
    check('wm_close_now_real_close', "self.protocol('WM_DELETE_WINDOW', self.on_close)" in main_py)
    check('custom_titlebar_builder_exists', 'def _build_custom_titlebar(self):' in main_py)
    check('native_chrome_hidden', 'self.overrideredirect(True)' in main_py)
    check('integrated_window_buttons_exist', "self.btn_window_minimize = ctk.CTkButton" in main_py and "self.btn_window_maximize = ctk.CTkButton" in main_py and "self.btn_window_close = ctk.CTkButton" in main_py)
    check('drag_support_exists', 'def _begin_titlebar_drag(self, event=None):' in main_py and "'<B1-Motion>'" in main_py)
    check('layout_has_titlebar_row', "self.grid_rowconfigure(0, weight=0)" in main_py and "self.grid_rowconfigure(1, weight=1)" in main_py and "self.sidebar.grid(row=1, column=0" in main_py and "self.main_content.grid(row=1, column=1" in main_py)
    check('fullscreen_respects_custom_chrome', "app._suspend_custom_window_chrome()" in layout and "app._apply_custom_window_chrome()" in layout)
    print('RESULTADO: PASS')


if __name__ == '__main__':
    main()
