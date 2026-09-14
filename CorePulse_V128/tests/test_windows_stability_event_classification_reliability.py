"""V100 — clasificación fiable y legible de estabilidad de Windows."""
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
    ui = (ROOT / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')
    src = (ROOT / 'core' / 'windows_health.py').read_text(encoding='utf-8')
    check('version', VERSION == '103')
    check('stage', STAGE == 'STARTUP_RESPONSIVENESS_SINGLE_LAYOUT_AUTHORITY')
    check('strict_whea_provider', "'whea-logger' in provider" in src and "eid in (18, 19, 20, 46)" in src)
    check('strict_kernel_power', "eid == 41" in src and "microsoft-windows-kernel-power" in src)
    check('strict_bsod_provider', "wer-systemerrorreporting" in src and "eid == 1001" in src)
    check('application_errors_separate', "provider == 'application error'" in src and "provider == 'application hang'" in src)
    check('human_ui_title', "'Estabilidad de Windows'" in ui)
    check('human_summary_panel', "text='Qué significa'" in ui and "'Estado general'" in ui)
    check('separate_human_counts', all(x in ui for x in (
        'Pantallazos azules (BSOD)', 'Errores de hardware (WHEA)',
        'Apagados o reinicios no limpios', 'Registros de cierres/bloqueos de aplicaciones'
    )))
    check('traceability_preserved', "'Fuente de Windows'" in ui and "ProviderName" in ui)

    original = wh._json_ps
    try:
        rows = [
            {'Id': 19, 'ProviderName': 'Microsoft-Windows-WindowsUpdateClient', 'Message': 'update ok'},
            {'Id': 18, 'ProviderName': 'TPM', 'Message': 'tpm state'},
            {'Id': 20, 'ProviderName': 'Microsoft-Windows-Kernel-Boot', 'Message': 'boot info'},
            {'Id': 18, 'ProviderName': 'Microsoft-Windows-WHEA-Logger', 'Message': 'hardware error'},
            {'Id': 41, 'ProviderName': 'Microsoft-Windows-Kernel-Power', 'Message': 'unexpected restart'},
            {'Id': 1001, 'ProviderName': 'Microsoft-Windows-WER-SystemErrorReporting', 'Message': 'bugcheck'},
            {'Id': 6008, 'ProviderName': 'EventLog', 'Message': 'shutdown unexpected'},
            {'Id': 1000, 'ProviderName': 'Application Error', 'Message': 'app crash'},
            {'Id': 1002, 'ProviderName': 'Application Hang', 'Message': 'app hang'},
        ]
        wh._json_ps = lambda script, timeout=45: (rows, None)
        result = wh.analyze_crashes(days=7, max_events=120)
        c = result['counts']
        check('false_positive_ids_rejected', len(result['items']) == 6)
        check('real_whea_counted', c['whea'] == 1)
        check('real_bsod_counted', c['bsod_bugcheck'] == 1)
        check('power_events_counted', result['power_event_count'] == 2)
        check('app_events_counted_separately', result['app_issue_count'] == 2)
        check('critical_only_from_real_critical_evidence', result['severity'] == 'CRITICAL')
        check('human_labels_attached', all(x.get('user_label') and x.get('user_summary') for x in result['items']))

        false_only = [
            {'Id': 19, 'ProviderName': 'Microsoft-Windows-WindowsUpdateClient', 'Message': 'update ok'},
            {'Id': 18, 'ProviderName': 'TPM', 'Message': 'tpm'},
            {'Id': 20, 'ProviderName': 'Microsoft-Windows-Kernel-Boot', 'Message': 'boot'},
        ]
        wh._json_ps = lambda script, timeout=45: (false_only, None)
        clean = wh.analyze_crashes(days=7, max_events=120)
        check('false_only_is_not_critical', clean['severity'] == 'NORMAL' and not clean['items'])
        check('clean_summary_is_understandable', 'No se detectaron BSOD' in clean['summary'])
    finally:
        wh._json_ps = original

    print('RESULTADO: PASS (19 checks)')


if __name__ == '__main__':
    main()
