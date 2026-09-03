from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
main = (ROOT / 'main.py').read_text(encoding='utf-8')
panel = (ROOT / 'gui' / 'diagnostic_view.py').read_text(encoding='utf-8')
dialogs = (ROOT / 'gui' / 'dialogs.py').read_text(encoding='utf-8')

def check(name, ok):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {bool(ok)}")
    if not ok:
        raise SystemExit(1)

check('folder_picker_is_used', 'ask_pdf_directory(self)' in main and 'def ask_pdf_directory(parent):' in dialogs)
check('automatic_report_filename', 'Reporte_CorePulse_' in main and "Path(output_dir) / default_filename" in main)
check('single_export_guard', 'self._pdf_export_in_progress' in main)
check('worker_has_no_tk_after', "def generate_worker():" in main and "job['done'].set()" in main)
worker = main.split('def generate_worker():', 1)[1].split("threading.Thread(target=generate_worker", 1)[0]
check('worker_does_not_call_after', 'self.after(' not in worker)
check('main_thread_polling', 'def _poll_pdf_export_job(self):' in main and 'self.after(100, self._poll_pdf_export_job)' in main)
check('panel_calls_exporter_directly', 'exporter()' in panel and 'self.after_idle(exporter)' not in panel)
check('pdf_open_after_file_exists', "Path(file_path).is_file()" in main and '_open_generated_pdf(file_path)' in main)
print('\nRESULTADO: PASS')
