from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check(name, ok):
    assert bool(ok), name


def test_pdf_button_flow():
    main = (ROOT / "main.py").read_text(encoding="utf-8")
    panel = (ROOT / "gui" / "diagnostic_view.py").read_text(encoding="utf-8")
    dialogs = (ROOT / "gui" / "dialogs.py").read_text(encoding="utf-8")

    # El flujo actual guarda en AppData; no debe exigir selector de carpeta en cada exportación.
    check("persistent_report_directory", "diagnostics_dir()" in main and "output_dir.mkdir(parents=True, exist_ok=True)" in main)
    check("single_export_guard", "self._pdf_export_in_progress" in main)
    check("worker_has_completion_signal", "def generate_worker():" in main and "job['done'].set()" in main)
    worker = main.split("def generate_worker():", 1)[1].split("threading.Thread(target=generate_worker", 1)[0]
    check("worker_does_not_call_after", "self.after(" not in worker)
    check("main_thread_polling", "def _poll_pdf_export_job(self):" in main and "self.after(100, self._poll_pdf_export_job)" in main)
    check("panel_calls_exporter_directly", "exporter()" in panel and "self.after_idle(exporter)" not in panel)
    check("pdf_is_persisted_without_auto_open", "Path(file_path).is_file()" in main and "_remember_last_pdf_report(file_path)" in main and "_open_generated_pdf(file_path)" not in main)


if __name__ == "__main__":
    test_pdf_button_flow()
    print("RESULTADO: PASS")
