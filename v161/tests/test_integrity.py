"""Prueba de regresión para contratos de integridad, estructura limpia y dependencias principales."""
from __future__ import annotations
# Código refactorizado: nombres estables y documentación en español.
from pathlib import Path
import ast
import re
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.version import VERSION, VERSION_LABEL
checks = []

def check(name, cond):
    checks.append(bool(cond))
    print(f"[{('PASS' if cond else 'FAIL')}] {name}: {bool(cond)}")
runtime = [ROOT / 'main.py'] + list((ROOT / 'core').glob('*.py')) + list((ROOT / 'gui').glob('*.py')) + list((ROOT / 'database').glob('*.py'))
ok_compile = True
for path in runtime:
    try:
        ast.parse(path.read_text(encoding='utf-8'))
    except Exception:
        ok_compile = False
        break
check('runtime_python_parses', ok_compile)
main = (ROOT / 'main.py').read_text(encoding='utf-8')
check('real_or_na_contract', 'REAL_OR_NA' in (ROOT / 'core' / 'product_contract.py').read_text(encoding='utf-8'))
check('real_fps_contract', 'REAL_FPS_OR_NA_ONLY' in (ROOT / 'core' / 'product_contract.py').read_text(encoding='utf-8'))
check('pdf_uses_current_generator', 'from core.report_generator import generate_pdf_report' in main)
panel = (ROOT / 'gui' / 'diagnostic_view.py').read_text(encoding='utf-8')
check('pdf_button_visible_handler', 'command=self._export_pdf_from_panel' in panel)
check('pdf_handler_calls_app_exporter', "getattr(self.app, 'export_pdf_report', None)" in panel or 'getattr(self.app, \"export_pdf_report\", None)' in panel)
check('main_pdf_exporter_exists', 'def export_pdf_report(self):' in main)
check('single_product_version', VERSION_LABEL == f'V{VERSION}')
check('no_patch_payload', not (ROOT / 'payload').exists())
check('no_backups', not (ROOT / '.corepulse_backups').exists() and (not (ROOT / 'backups').exists()))
check('no_real_env_in_distribution', not (ROOT / '.env').exists())
check('presentmon_bundled', (ROOT / 'tools' / 'presentmon' / 'PresentMon.exe').exists())
print('\nRESULT:', 'PASS' if all(checks) else 'FAIL')
raise SystemExit(0 if all(checks) else 1)
