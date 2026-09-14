"""Regresión V100 — portada del Centro de Salud más compacta y coherente."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION, STAGE


def check(name, cond):
    if not cond:
        raise AssertionError(name)
    print('[PASS]', name)


def main():
    panel=(ROOT/'gui/health_center_panel.py').read_text(encoding='utf-8')
    check('version', VERSION == '103')
    check('stage', STAGE == 'STARTUP_RESPONSIVENESS_SINGLE_LAYOUT_AUTHORITY')
    check('header_is_compact', "header.pack(fill='x', padx=20, pady=(12, 4))" in panel)
    check('hero_badges_removed', 'badges=(),' in panel)
    check('hero_copy_shorter', 'Mantenimiento, estabilidad y recuperación en un solo lugar.' in panel)
    check('summary_intro_removed', "intro = ctk.CTkFrame(self.body, fg_color='transparent')" not in panel)
    check('cards_moved_up', "modules.pack(fill='x', padx=5, pady=(2, 8))" in panel)
    check('footer_removed', 'Centro de salud interpreta y organiza evidencia; el monitoreo en vivo permanece en Resumen.' not in panel)
    print('RESULTADO: PASS (8 checks)')


if __name__ == '__main__':
    main()
