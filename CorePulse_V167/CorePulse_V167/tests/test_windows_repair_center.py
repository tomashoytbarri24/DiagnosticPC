"""V100 — Windows Repair Center: DISM/SFC explícitos y separados de Tweaks."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION
from core.windows_commands import CommandResult
from core.windows_repair import (
    DIAGNOSTIC_STEPS, REPAIR_STEPS, POLICY, ROLLBACK_POLICY,
    classify_output, repair_capabilities,
)


def check(name, condition):
    ok = bool(condition)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {ok}")
    return ok


def fake(stdout='', stderr='', rc=0, error=None, timed_out=False):
    return CommandResult(
        ok=(rc == 0 and not error and not timed_out),
        args=('fake.exe',), returncode=rc,
        stdout=stdout, stderr=stderr, error=error, timed_out=timed_out,
    )


def main():
    ui = (ROOT/'gui'/'health_center_panel.py').read_text(encoding='utf-8')
    core = (ROOT/'core'/'windows_repair.py').read_text(encoding='utf-8')
    results = [
        check('version', VERSION == '103'),
        check('explicit_only_policy', POLICY == 'EXPLICIT_USER_ACTION_ONLY'),
        check('not_tweak_rollback', ROLLBACK_POLICY == 'NOT_A_TWEAK_ROLLBACK'),
        check('diagnostic_sequence', [x.key for x in DIAGNOSTIC_STEPS] == ['dism_checkhealth','dism_scanhealth','sfc_verifyonly']),
        check('repair_sequence', [x.key for x in REPAIR_STEPS] == ['dism_restorehealth','sfc_scannow','dism_post_checkhealth']),
        check('no_shell_commands', "shell=True" not in core),
        check('direct_dism_sfc', 'dism.exe' in core and 'sfc.exe' in core),
        check('admin_guard', "'ADMIN_REQUIRED'" in core and 'is_admin()' in core),
        check('logs_raw_output', "'stdout': result.stdout" in core and "'stderr': result.stderr" in core),
        check('ui_separate_tab', "('repair', 'Reparación')" in ui),
        check('ui_two_primary_actions', 'Diagnosticar integridad' in ui and 'Reparar Windows' in ui),
        check('explicit_confirmation', "messagebox.askyesno" in ui and 'DISM RestoreHealth' in ui),
        check('ui_warns_not_rollback', 'No usa DISM/SFC para revertir Tweaks de CorePulse.' in ui),
    ]

    results += [
        check('parse_dism_clean', classify_output('dism_checkhealth', fake('No component store corruption detected.'))['state'] == 'CLEAN'),
        check('parse_dism_repairable', classify_output('dism_scanhealth', fake('The component store is repairable.'))['state'] == 'REPAIRABLE'),
        check('parse_dism_repaired', classify_output('dism_restorehealth', fake('The restore operation completed successfully.'))['state'] == 'REPAIRED'),
        check('parse_sfc_clean', classify_output('sfc_verifyonly', fake('Windows Resource Protection did not find any integrity violations.'))['state'] == 'CLEAN'),
        check('parse_sfc_repaired', classify_output('sfc_scannow', fake('Windows Resource Protection found corrupt files and successfully repaired them.'))['state'] == 'REPAIRED'),
        check('parse_sfc_unrepaired', classify_output('sfc_scannow', fake('Windows Resource Protection found corrupt files but was unable to fix some of them.'))['state'] == 'UNREPAIRED'),
        check('unknown_output_fail_closed', classify_output('sfc_verifyonly', fake('Salida localizada desconocida'))['state'] == 'COMPLETED_UNCLASSIFIED'),
        check('failed_returncode', classify_output('dism_scanhealth', fake(stderr='error', rc=87))['state'] == 'FAILED'),
        check('timeout', classify_output('dism_scanhealth', fake(timed_out=True))['state'] == 'TIMEOUT'),
        check('capabilities_contract', all(k in repair_capabilities() for k in ('windows','admin','diagnostic_available','repair_available','policy','rollback_policy'))),
    ]

    ok = all(results)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
