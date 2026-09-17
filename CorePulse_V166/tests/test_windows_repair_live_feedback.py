"""V100 — feedback inmediato del Windows Repair Center."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION


def check(name, condition):
    ok = bool(condition)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {ok}")
    return ok


def main():
    ui = (ROOT/'gui'/'health_center_panel.py').read_text(encoding='utf-8')
    diag_start = ui.index('    def _run_integrity_diagnostic(self):')
    fix_start = ui.index('    def _run_windows_repair(self):')
    hist_start = ui.index('    def _render_history(self):')
    diag = ui[diag_start:fix_start]
    fix = ui[fix_start:hist_start]

    results = [
        check('version', VERSION == '103'),
        check('live_sync_method', 'def _sync_repair_live_ui(self):' in ui),
        check('stage_progress_bar', 'self.repair_progress_bar' in ui and '_repair_progress_fraction' in ui),
        check('async_on_started', 'def _async(self,name,fn,on_done,on_started=None):' in ui),
        check('job_registered_before_feedback', "self._jobs.add(name)" in ui and 'on_started()' in ui),
        check('diagnostic_immediate_feedback', 'on_started=self._sync_repair_live_ui' in diag),
        check('repair_immediate_feedback', 'on_started=self._sync_repair_live_ui' in fix),
        check('diagnostic_no_prerender', 'self._render()' not in diag),
        check('repair_no_prerender', 'self._render()' not in fix),
        check('progress_marshaled_to_ui_thread', 'self.app.after(0, self._sync_repair_live_ui)' in ui),
        check('safe_idle_paint', 'self.app.update_idletasks()' in ui),
    ]
    ok = all(results)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
