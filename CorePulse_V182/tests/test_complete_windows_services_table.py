"""V100 — todos los servicios se analizan y quedan accesibles por paginación."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION, STAGE
import core.windows_health as wh


def check(name, cond):
    if not cond:
        raise AssertionError(name)
    print(f"[PASS] {name}")


def main():
    ui=(ROOT/'gui/health_center_panel.py').read_text(encoding='utf-8')
    health=(ROOT/'core/windows_health.py').read_text(encoding='utf-8')
    check('version', VERSION.isdecimal())
    check('stage', bool(STAGE))
    check('default_query_is_uncapped', 'def analyze_services(limit: int | None = None)' in health and "limit_clause = ''" in health)
    check('old_ui_12_row_cap_removed', "data.get('items', [])[:12]" not in ui[ui.index("elif kind == 'services':"):ui.index("elif kind == 'crashes':")])
    check('service_pagination_present', '_services_page_size = 40' in ui and 'def _set_services_page(self, page):' in ui)
    check('range_is_visible', 'Mostrando {start + 1}–{end} de {total}' in ui)
    check('navigation_present', "pager, 'Anterior'" in ui and "pager, 'Siguiente'" in ui)
    check('absolute_row_numbers', 'enumerate(items, start=start + 1)' in ui)

    original=wh._json_ps
    queries=[]
    try:
        def fake(script, timeout=30):
            queries.append(script)
            return ([{'Name':'SvcA','DisplayName':'A','State':'Running','StartMode':'Auto','PathName':'','ProcessId':0},
                     {'Name':'SvcB','DisplayName':'B','State':'Stopped','StartMode':'Manual','PathName':'','ProcessId':0}], None)
        wh._json_ps=fake
        result=wh.analyze_services()
        check('default_collects_returned_services', result.get('count') == 2 and len(result.get('items') or []) == 2)
        check('default_has_no_select_first', 'Select-Object -First' not in queries[-1])
        wh.analyze_services(limit=5)
        check('explicit_test_limit_preserved', 'Select-Object -First 5' in queries[-1])
    finally:
        wh._json_ps=original
    print('RESULTADO: PASS (11 checks)')


if __name__ == '__main__':
    main()
