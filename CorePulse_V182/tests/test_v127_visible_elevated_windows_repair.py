"""V127 — DISM/SFC visibles en PowerShell elevado + resultados importados a CorePulse."""
from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION, STAGE
from core.windows_repair import (
    DIAGNOSTIC_STEPS,
    REPAIR_STEPS,
    VISIBLE_CONSOLE_POLICY,
    _write_visible_powershell_script,
    repair_capabilities,
)


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print('[PASS]', name)


def sha256(rel):
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


def main():
    core = (ROOT / 'core' / 'windows_repair.py').read_text(encoding='utf-8')
    ui = (ROOT / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')

    check('version', VERSION.isdecimal())
    check('stage', bool(STAGE))
    check('visible_policy', VISIBLE_CONSOLE_POLICY == 'VISIBLE_ELEVATED_POWERSHELL')
    check('shell_execute_ex', 'ShellExecuteExW' in core and "sei.lpVerb = 'runas'" in core)
    check('visible_powershell', "sei.lpFile = 'powershell.exe'" in core and 'SW_SHOWNORMAL = 1' in core)
    check('no_shell_true', 'shell=True' not in core)
    check('session_admin_probe', 'WindowsBuiltInRole]::Administrator' in core and "'powershell_admin': None" in core)
    check('real_output_import', "stdout=raw" in core and "'capture': 'POWERSHELL_VISIBLE_MERGED_STREAM'" in core)
    check('legacy_hidden_api_preserved', 'def run_integrity_diagnostic(' in core and 'def run_windows_repair(' in core)
    check('visible_api_added', 'def run_integrity_diagnostic_visible(' in core and 'def run_windows_repair_visible(' in core)
    check('capability_allows_uac', "'repair_available': IS_WINDOWS" in core and "'elevation_mode': 'ALREADY_ADMIN' if admin_now else ('UAC_POWERSHELL'" in core)

    with tempfile.TemporaryDirectory() as td:
        script = _write_visible_powershell_script('diagnostic', DIAGNOSTIC_STEPS, Path(td))
        ps = script.read_text(encoding='utf-8')
        check('script_real_commands', 'dism.exe' in ps and 'sfc.exe' in ps)
        check('script_live_console', 'Tee-Object -Variable captured | Out-Host' in ps)
        check('script_utf8_capture', 'Write-CorePulseUtf8' in ps and '.out.txt' in ps and '.meta.json' in ps)
        check('script_all_diagnostic_steps', all(step.key in ps for step in DIAGNOSTIC_STEPS))
        check('script_auto_close_after_result', 'Start-Sleep -Seconds 4' in ps and 'salida completa dentro de la pestaña Reparación' in ps)

    check('repair_steps_preserved', [x.key for x in REPAIR_STEPS] == ['dism_restorehealth', 'sfc_scannow', 'dism_post_checkhealth'])
    check('ui_uses_visible_api', 'run_integrity_diagnostic_visible' in ui and 'run_windows_repair_visible' in ui)
    check('ui_uac_without_restart', 'No necesitas reiniciar CorePulse' in ui and 'UAC AL EJECUTAR' in ui)
    check('ui_raw_output_inside_app', 'Salida real de PowerShell' in ui and 'CTkTextbox' in ui)
    check('ui_optional_full_admin', 'Abrir CorePulse completo como administrador · opcional' in ui)

    caps = repair_capabilities()
    check('capability_contract', all(k in caps for k in ('windows', 'admin', 'repair_available', 'visible_console_available', 'elevation_mode', 'visible_console_policy')))

    expected = {
        'core/runtime_venv_path.py': '263d725dc8a50ef57d2e0dd8d8827968f58d2b67dcee6b0a276ca6dd8d562e92',
        'bootstrap_corepulse.py': '925d4ef090b28c27ceffbbbba9362a8137f665212ac445e96a096c0ce5e17a0b',
        'core/source_runtime_bootstrap.py': 'bde37780c35ebc280b0b22ac6a71926051ae9fde48b65935b6af64b819f7ccfd',
        'requirements-runtime-lock.txt': '36ee044c5dab3c5c8cfecbe0456923c9f406d83a93ef04d93f9fd27f1566c706',
        'core/nvme_smart_windows.py': 'fe9481d270d5b47299b97fc97d37ee56f65bd904333f634255e4a91e63958283',
    }
    for rel, digest in expected.items():
        check(f'protected_unchanged:{rel}', sha256(rel) == digest)

    print('RESULTADO: PASS')


if __name__ == '__main__':
    main()
