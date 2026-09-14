"""V113 — la versión vuelve a la esquina inferior izquierda del sidebar."""
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
    dash = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    layout = (ROOT / 'gui' / 'dashboard_layout.py').read_text(encoding='utf-8')
    check('initial_version_bottom_left', "app._sidebar_version.pack(side='bottom', fill='x', padx=14, pady=(3, 10))" in dash)
    check('render_version_bottom_left', "ver.pack(side='bottom', fill='x', padx=14, pady=(3, 10))" in layout)
    check('responsive_version_bottom_left', "ver.pack_configure(side='bottom', fill='x', padx=11 if compact else 14, pady=(3, 8 if compact else 10))" in layout)
    check('themes_stay_above', "theme_button.pack_configure(side='top', fill='x', padx=10 if compact else 12, pady=(8 if compact else 10, 4 if compact else 5))" in layout)
    print('RESULTADO: PASS')


if __name__ == '__main__':
    main()
