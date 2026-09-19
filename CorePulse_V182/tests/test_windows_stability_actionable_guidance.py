"""V100 — orientación accionable y evidence-gated para estabilidad Windows."""
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
    src = (ROOT / 'core' / 'windows_health.py').read_text(encoding='utf-8')
    ui = (ROOT / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')

    check('version', VERSION.isdecimal())
    check('stage', bool(STAGE))
    check('app_stats_complete_period', 'AppStats=$appStats' in src and 'Group-Object ApplicationName' in src)
    check('exception_code_collected', 'ExceptionCode=$exceptionCode' in src and 'ApplicationPath=$appPath' in src)
    check('deterministic_plan', 'def _stability_action_plan(' in src and 'def _application_action_guidance(' in src)
    check('no_auto_changes', 'hallazgo confirmado != causa confirmada' in src and 'Ningún umbral convierte' in src)
    check('ui_action_box', 'Qué puedes hacer ahora' in ui)
    check('ui_confidence', "text=f'Hallazgo: {finding_confidence}'" in ui and "Confianza: {cause_confidence}" in ui)
    check('ui_evidence', "_action_line('Evidencia'" in ui)

    original = wh._json_ps
    try:
        payload = {
            'Counts': {
                'bsod_bugcheck': 0, 'whea': 0, 'kernel_power': 0,
                'unexpected_shutdown': 0, 'app_error': 12, 'app_hang': 0,
            },
            'PowerIncidentCount': 0,
            'AffectedApps': ['CenterHotfix.exe'],
            'AppStats': [{
                'ApplicationName': 'CenterHotfix.exe', 'Total': 12, 'Errors': 12, 'Hangs': 0,
                'TopModule': 'KERNELBASE.dll', 'TopModuleCount': 12, 'TopException': 'e0434352', 'TopExceptionCount': 12,
                'ApplicationVersion': '1.0.0.0', 'ApplicationPath': r'C:\\Program Files\\Vendor\\CenterHotfix.exe',
            }],
            'MatchedTotal': 12,
            'Truncated': False,
            'Items': [{
                'TimeCreated': '2026-09-10T12:00:00-03:00', 'Id': 1000,
                'ProviderName': 'Application Error', 'Kind': 'app_error', 'RecordId': 1,
                'Message': 'app error', 'ApplicationName': 'CenterHotfix.exe',
                'ApplicationVersion': '1.0.0.0', 'FaultingModule': 'KERNELBASE.dll',
                'ExceptionCode': 'e0434352', 'ApplicationPath': r'C:\\Program Files\\Vendor\\CenterHotfix.exe',
                'ModulePath': r'C:\\Windows\\System32\\KERNELBASE.dll',
            }],
        }
        wh._json_ps = lambda script, timeout=55: ([payload], None)
        result = wh.analyze_crashes(7)
        check('app_stats_returned', result['app_stats'][0]['Total'] == 12)
        check('action_plan_returned', bool(result['action_plan']))
        action = result['action_plan'][0]
        check('repeated_app_is_prioritized', action['application'] == 'CenterHotfix.exe')
        check('exception_normalized', result['app_stats'][0]['TopException'] == '0xe0434352')
        check('managed_exception_guidance', '.NET' in action['action'] and 'excepción administrada/CLR' in action['interpretation'])
        check('system_dll_not_blamed', 'no demuestra que esa DLL de Windows esté dañada' in action['interpretation'])
        check('confidence_exposed', action['finding_confidence'] == 'ALTA' and action['cause_confidence'] == 'BAJA')
        check('policy_updated', 'EVIDENCE_GATED_RECOMMENDATIONS' in result['classification_policy'])
    finally:
        wh._json_ps = original

    print('RESULTADO: PASS (17 checks)')


if __name__ == '__main__':
    main()
