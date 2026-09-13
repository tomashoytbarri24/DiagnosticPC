"""V100 — detección exacta, procedencia y evidencia por tweak."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION
from core import windows_tweaks as wt


def check(name, cond):
    ok = bool(cond)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {ok}")
    return ok


def main():
    engine = (ROOT/'core'/'windows_tweaks.py').read_text(encoding='utf-8')
    panel = (ROOT/'gui'/'windows_tweaks_panel.py').read_text(encoding='utf-8')
    checks = [
        check('version', VERSION == '103'),
        check('detailed_evidence_api', '_registry_detection_probe' in engine and "'evidence': evidence" in engine),
        check('type_aware_registry_detection', '_expected_reg_type_id' in engine and 'type_mismatch' in engine),
        check('origin_detection', "return 'corepulse' if has_rollback else 'preexisting'" in engine),
        check('single_state_read_batch', 'rollback_ids = saved_rollback_ids()' in engine and '_rollback_ids=rollback_ids' in engine),
        check('ui_corepulse_origin', 'APLICADO · COREPULSE ✓' in panel),
        check('ui_preexisting_origin', 'YA ESTABA APLICADO' in panel),
        check('ui_unknown_fail_closed', 'NO VERIFICABLE' in panel and 'CorePulse no asumirá el estado' in panel),
    ]

    originals = {
        'is_windows_11': wt.is_windows_11,
        '_availability': wt._availability,
        '_read_value': wt._read_value,
        '_detect_ps': wt._detect_ps,
        'saved_rollback_ids': wt.saved_rollback_ids,
    }
    try:
        wt.is_windows_11 = lambda: True
        wt._availability = lambda tweak: (True, '')

        # 1) DWORD exacto + tipo correcto => aplicado y preexistente sin snapshot.
        def exact_read(hive, path, name):
            if name == 'HideFileExt':
                return True, 0, 4  # REG_DWORD
            return False, None, None
        wt._read_value = exact_read
        wt.saved_rollback_ids = lambda: set()
        row = wt.detect_tweak('show_file_extensions')
        checks.append(check('exact_applied', row['status'] == 'applied' and row['applied']))
        checks.append(check('preexisting_without_snapshot', row['origin'] == 'preexisting' and not row['rollback_available']))
        checks.append(check('high_confidence_exact', row['confidence'] == 'high' and row['verified']))

        # 2) Mismo valor pero REG_SZ en vez de REG_DWORD => no falso positivo.
        wt._read_value = lambda h, p, n: (True, 0, 1)
        row = wt.detect_tweak('show_file_extensions')
        checks.append(check('wrong_registry_type_is_partial', row['status'] == 'partial' and not row['applied']))
        checks.append(check('type_mismatch_evidence', row['evidence'][0]['state'] == 'type_mismatch'))

        # 3) Exacto con snapshot => atribución CorePulse + rollback.
        wt._read_value = exact_read
        wt.saved_rollback_ids = lambda: {'show_file_extensions'}
        row = wt.detect_tweak('show_file_extensions')
        checks.append(check('corepulse_with_snapshot', row['status'] == 'applied' and row['origin'] == 'corepulse' and row['rollback_available']))

        # 4) Tweak multiobjetivo: algunos sí y otros no => PARCIAL.
        values = {
            'MinAnimate': ('0', 1),
            'TaskbarAnimations': (0, 4),
            'ListviewAlphaSelect': (1, 4),  # deseado es 0
            'ListviewShadow': (0, 4),
        }
        def multi_read(h, p, n):
            if n in values:
                v, typ = values[n]
                return True, v, typ
            return False, None, None
        wt._read_value = multi_read
        wt.saved_rollback_ids = lambda: set()
        row = wt.detect_tweak('reduce_animations')
        checks.append(check('multi_target_partial', row['status'] == 'partial' and row['matched_targets'] == 3 and row['total_targets'] == 4))

        # 5) Error de lectura => fail-closed; jamás se etiqueta aplicado.
        def broken_read(*args):
            raise PermissionError('simulado')
        wt._read_value = broken_read
        row = wt.detect_tweak('show_file_extensions')
        checks.append(check('read_failure_unknown', row['status'] == 'unknown' and not row['applied'] and row['confidence'] == 'low'))

        # 6) Un ps_detect puede informar estado aunque la acción esté bloqueada
        # por política de rollback. Se separa DETECCIÓN de APLICABILIDAD.
        wt._availability = lambda tweak: (False, 'bloqueado por prueba')
        wt._detect_ps = lambda script: (True, '')
        wt.saved_rollback_ids = lambda: set()
        row = wt.detect_tweak('remove_onedrive')
        checks.append(check('detect_blocked_external_state', row['status'] == 'applied' and not row['available'] and row['origin'] == 'preexisting'))

    finally:
        wt.is_windows_11 = originals['is_windows_11']
        wt._availability = originals['_availability']
        wt._read_value = originals['_read_value']
        wt._detect_ps = originals['_detect_ps']
        wt.saved_rollback_ids = originals['saved_rollback_ids']

    ok = all(checks)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
