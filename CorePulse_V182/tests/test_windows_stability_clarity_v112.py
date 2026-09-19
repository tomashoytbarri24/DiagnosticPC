from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from core.version import VERSION, STAGE

def check(name, cond):
    if not cond: raise AssertionError(name)
    print('[PASS]', name)

def main():
    ui=(ROOT/'gui'/'health_center_panel.py').read_text(encoding='utf-8')
    check('version', VERSION.isdecimal())
    check('stage', bool(STAGE))
    check('quick_summary', "'SISTEMA'" in ui and "'APLICACIONES'" in ui and "'REINICIOS'" in ui)
    check('clear_action_heading', "text='Qué conviene revisar'" in ui)
    check('simple_labels', all(x in ui for x in ("_simple_line('Qué pasó'", "_simple_line('Qué significa'", "_simple_line('Haz esto primero'", "_simple_line('Si se repite'")))
    check('technical_evidence_separated', "text='Registro técnico'" in ui and 'def _toggle_stability_technical' in ui)
    check('technical_default_collapsed', 'self._stability_show_technical = False' in ui and "f'Ver {total} evento(s)'" in ui)
    print('RESULTADO: PASS')
if __name__=='__main__': main()
