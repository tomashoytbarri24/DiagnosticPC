"""V100 — la frecuencia prioriza, pero no inventa causa ni ordena reinstalar."""
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
    print(f'[PASS] {name}')


def main():
    src=(ROOT/'core/windows_health.py').read_text(encoding='utf-8')
    ui=(ROOT/'gui/health_center_panel.py').read_text(encoding='utf-8')
    check('version', VERSION.isdecimal())
    check('stage', bool(STAGE))
    check('separate_finding_and_cause', all(token in src for token in ("'finding':", "'finding_confidence':", "'cause':", "'cause_confidence':", "'escalation':")))
    check('ui_explains_layers', all(token in ui for token in ("_action_line('Qué sabemos'", "_action_line('Interpretación'", "_action_line('Causa'", "_action_line('Primero prueba'", "_action_line('Escalar sólo si'")))
    check('frequency_is_not_cause', 'La frecuencia sólo prioriza qué revisar primero' in src and 'frecuencia no identifica por sí sola la causa' in src)

    repeated = wh._application_action_guidance({
        'ApplicationName':'ExampleApp.exe', 'Total':20, 'Errors':20, 'Hangs':0,
        'TopModule':'KERNELBASE.dll', 'TopModuleCount':20,
        'TopException':'0xc0000005', 'TopExceptionCount':20,
        'ApplicationVersion':'2.4.1'
    })
    check('repeated_finding_high', repeated['finding_confidence'] == 'ALTA')
    check('repeated_cause_stays_low', repeated['cause_confidence'] == 'BAJA' and 'No determinada' in repeated['cause'])
    check('no_immediate_reinstall', 'reinstal' not in repeated['action'].lower())
    check('reinstall_is_conditional_escalation', 'reinstal' in repeated['escalation'].lower() and 'sólo si' in repeated['escalation'].lower())
    check('kernelbase_not_blamed', 'no demuestra que esa DLL de Windows esté dañada' in repeated['interpretation'])
    check('access_violation_not_ram_diagnosis', 'no demuestra RAM defectuosa' in repeated['interpretation'])

    isolated = wh._application_action_guidance({
        'ApplicationName':'OtherApp.exe', 'Total':1, 'Errors':1, 'Hangs':0,
        'TopModule':'app.dll', 'TopModuleCount':1,
    })
    check('isolated_waits_for_recurrence', 'vuelve a fallar' in isolated['action'] and 'evita reinstalar de entrada' in isolated['action'])
    check('module_evidence_not_called_repeated_without_count', 'módulo registrado: app.dll' in isolated['evidence'] and 'módulo más frecuente' not in isolated['evidence'])

    whea_plan = wh._stability_action_plan({'whea':2,'bsod_bugcheck':0}, 7, power_incidents=0, app_stats=[])[0]
    check('whea_exact_component_not_invented', whea_plan['finding_confidence']=='ALTA' and 'Componente exacto no determinado' in whea_plan['cause'])

    power_plan = wh._stability_action_plan({'whea':0,'bsod_bugcheck':0}, 7, power_incidents=2, app_stats=[])[0]
    check('power_cause_not_assumed', power_plan['cause_confidence']=='BAJA' and 'No determinada' in power_plan['cause'])

    print('RESULTADO: PASS (15 checks)')


if __name__ == '__main__':
    main()
