"""V113 — agente más abajo y botón Temas más arriba sin rediseñar el sidebar."""
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
    check('initial_theme_button_top', "app._theme_toggle_button.pack(side='top', fill='x', padx=12, pady=(8, 4))" in dash)
    check('initial_version_top', "app._sidebar_version.pack(side='top', fill='x', padx=14, pady=(0, 8))" in dash)
    check('agent_rendered_lower', "card.pack(side='top', fill='x', padx=11, pady=(20, 8))" in layout)
    check('responsive_agent_kept_lower', "card.pack(side='top', fill='x', padx=9 if compact else 11, pady=(16 if compact else 20, 8))" in layout)
    check('theme_kept_above_footer', "theme_button.pack_configure(side='top', fill='x', padx=10 if compact else 12, pady=(8 if compact else 10, 4 if compact else 5))" in layout)
    check('version_follows_theme', "ver.pack_configure(side='top', fill='x', padx=11 if compact else 14, pady=(0, 6 if compact else 8))" in layout)
    print('RESULTADO: PASS')


if __name__ == '__main__':
    main()
