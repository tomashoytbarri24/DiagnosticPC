"""Regresión V100 — limpieza y alineación de tarjetas del Centro de Salud."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from core.version import VERSION


def check(name, cond):
    if not cond:
        raise AssertionError(name)
    print('[PASS]', name)


def main():
    panel=(ROOT/'gui/health_center_panel.py').read_text(encoding='utf-8')
    check('version', VERSION == '103')
    check('plain_icons', 'icon_label = ctk.CTkLabel(' in panel and 'badge = ctk.CTkFrame(' not in panel[panel.index('def _health_module_card'):panel.index('def _capture_scroll_fraction')])
    check('closer_header_spacing', "icon_label.pack(side='left', padx=(0, 7), pady=(3, 0))" in panel)
    check('stronger_titles', "text_col, text=title, font=(FONT, 13, 'bold')" in panel)
    check('compact_status', "pady=(5, 0)" in panel and "pady=(1, 5)" in panel)
    check('consistent_open_button', "button_text='Abrir Gaming'" not in panel)
    check('module_identity_tags_preserved', all(x in panel for x in ('Autonomía y desgaste','Inicio y servicios','DISM y SFC','Comparativas','Protección y rollback','Gaming y perfiles')))
    print('RESULTADO: PASS (7 checks)')


if __name__ == '__main__':
    main()
