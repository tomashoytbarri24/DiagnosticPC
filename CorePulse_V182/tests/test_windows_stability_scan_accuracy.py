"""V100 — conteos completos y detalle entendible de estabilidad Windows."""
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
    src=(ROOT/'core/windows_health.py').read_text(encoding='utf-8')
    ui=(ROOT/'gui/health_center_panel.py').read_text(encoding='utf-8')
    check('version', VERSION.isdecimal())
    check('stage', bool(STAGE))
    check('complete_category_counts', 'Counts=[pscustomobject]' in src and 'MatchedTotal=$all.Count' in src)
    check('critical_detail_priority', '$systemItems' in src and '$remaining=' in src and '$appItems' in src)
    check('power_incident_dedupe', 'PowerIncidentCount=$powerIncidents' in src and 'TotalSeconds' in src)
    check('affected_apps_from_real_payload', 'AffectedApps=$affectedApps' in src and 'ApplicationName=$app' in src)
    check('app_payload_fields', "if($props.Count -gt 0)" in src and 'FaultingModule=$module' in src)
    check('ui_has_application_identity', "'Aplicación / componente'" in ui and "x.get('component_name')" in ui)
    check('ui_has_event_time', "'Fecha y hora'" in ui and "x.get('display_time')" in ui)
    check('ui_paginates_stability', '_set_stability_page' in ui and '_stability_page_size = 25' in ui)

    original=wh._json_ps
    try:
        payload={
            'Counts': {
                'bsod_bugcheck': 0, 'whea': 1, 'kernel_power': 1,
                'unexpected_shutdown': 1, 'app_error': 42, 'app_hang': 2,
            },
            'PowerIncidentCount': 1,
            'AffectedApps': ['CenterHotfix.exe', 'KillerProviderDataHelperService.exe'],
            'MatchedTotal': 47,
            'Truncated': True,
            'Items': [
                {
                    'TimeCreated':'2026-09-10T12:00:00-03:00','Id':18,
                    'ProviderName':'Microsoft-Windows-WHEA-Logger','Kind':'whea','RecordId':11,
                    'Message':'hardware error','ApplicationName':None,'FaultingModule':None,
                },
                {
                    'TimeCreated':'2026-09-10T11:00:00-03:00','Id':1000,
                    'ProviderName':'Application Error','Kind':'app_error','RecordId':12,
                    'Message':'app error','ApplicationName':'CenterHotfix.exe','FaultingModule':'KERNELBASE.dll',
                },
            ],
        }
        wh._json_ps=lambda script, timeout=55: ([payload], None)
        result=wh.analyze_crashes(7)
        check('counts_not_limited_by_detail_rows', result['app_issue_count'] == 44 and result['matched_total'] == 47)
        check('critical_count_survives_app_noise', result['counts']['whea'] == 1 and result['severity'] == 'CRITICAL')
        check('single_power_incident_from_two_records', result['power_event_count'] == 1 and result['power_log_records'] == 2)
        check('full_affected_app_count', result['affected_app_count'] == 2)
        app=[x for x in result['items'] if x.get('kind')=='app_error'][0]
        check('app_name_presented', app['component_name'] == 'CenterHotfix.exe')
        check('fault_module_presented', 'KERNELBASE.dll' in app['user_detail'])
        check('truncation_is_explicit', result['details_truncated'] is True)
    finally:
        wh._json_ps=original

    print('RESULTADO: PASS (17 checks)')


if __name__ == '__main__':
    main()
