"""Regresión V103+ — limpieza profunda de RAM ejecutable directamente desde la bandeja."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION


def check(name, cond):
    ok = bool(cond)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {ok}")
    return ok


def main():
    tray = (ROOT / 'core' / 'tray_service.py').read_text(encoding='utf-8')
    app = (ROOT / 'main.py').read_text(encoding='utf-8')
    checks = [
        check('version', int(VERSION) >= 103),
        check('tray_has_direct_ram_action', "pystray.MenuItem('Limpiar RAM ahora', clean_ram)" in tray),
        check('tray_action_does_not_restore_window', "self._dispatch('clean_ram_from_tray')" in tray),
        check('app_has_direct_action', 'def clean_ram_from_tray(self):' in app),
        check('uses_deep_optimizer', 'from core.ram_optimizer import optimize_ram_deep' in app and 'result = optimize_ram_deep(' in app),
        check('does_not_use_safe_optimizer_in_tray_action', 'from core.ram_optimizer import optimize_ram_safely' not in app),
        check('background_thread', "name='CorePulse-TrayRAMDeepCleanup'" in app),
        check('no_duplicate_runs', '_tray_ram_cleanup_running' in app),
        check('measured_notification', "RAM profunda completada" in app and "recovered" in app),
        check('tray_notification_helper', 'def notify_action(self, title, message):' in tray),
    ]
    ok = all(checks)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
