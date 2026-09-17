"""V115 — PDF persistente en AppData sin generación automática."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION, STAGE


def check(name, cond):
    if not cond:
        raise AssertionError(name)
    print('[PASS]', name)


def main():
    main_py = (ROOT / 'main.py').read_text(encoding='utf-8')
    diag = (ROOT / 'gui' / 'diagnostic_view.py').read_text(encoding='utf-8')
    check('version', VERSION == '115')
    check('stage', STAGE == 'APPDATA_REPORT_WORKFLOW_AND_DISCOVERABILITY')
    check('uses_diagnostics_dir', 'output_dir = Path(diagnostics_dir()).resolve()' in main_py)
    check('no_pdf_directory_picker', 'ask_pdf_directory' not in main_py)
    poll = main_py[main_py.find('def _poll_pdf_export_job'):main_py.find('def _show_pdf_error')]
    check('no_auto_open_after_generate', 'opened = self._open_generated_pdf(file_path)' not in poll)
    check('fallback_scan_latest_pdf', "glob('Reporte_CorePulse_*.pdf')" in main_py)
    check('folder_action_available', 'Abrir carpeta de informes' in diag and "self.btn_pdf_folder.configure(state='normal')" in diag)
    show_block = diag[diag.find('def show_diagnostic_experience'):]
    check('no_generate_on_enter', 'export_pdf_report(' not in show_block)
    check('sensor_compat_preserved', 'Compatibilidad de sensores' in (ROOT / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8'))
    check('sensor_shortcut_in_diagnostic', 'Sensores y compatibilidad' in diag and 'open_telemetry_details' in diag)
    print('RESULTADO: PASS')

if __name__ == '__main__':
    main()
