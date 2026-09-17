"""Regresión V113 — gate visual mínimo, progreso real y centrado multimonitor."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION


def check(name, cond):
    if not cond:
        raise AssertionError(name)
    print('[PASS]', name)


def main():
    main_py = (ROOT / 'main.py').read_text(encoding='utf-8')
    gate = (ROOT / 'gui' / 'startup_gate.py').read_text(encoding='utf-8')
    launcher = (ROOT / 'corepulse_launcher.py').read_text(encoding='utf-8')
    adaptive = (ROOT / 'gui' / 'adaptive_window.py').read_text(encoding='utf-8')
    profiler = (ROOT / 'core' / 'startup_profiler.py').read_text(encoding='utf-8')

    check('version', VERSION == '113')
    check('main_hidden_during_gate', 'self.withdraw()' in main_py and '_startup_gate_active = True' in main_py)
    check('gate_is_first_visible_ui', 'StartupGate(self)' in main_py and '.show()' in main_py)
    check('determinate_progress', 'CTkProgressBar' in gate and 'update_stage' in gate)
    check('real_stage_parts', all(token in main_py for token in ("'layout'", "'charts'", "'services'", "'integrity'")))
    check('release_requires_core_parts', "core_keys = ('layout', 'charts', 'services')" in main_py)
    check('main_revealed_only_after_gate', 'def _reveal_main_window' in main_py and 'self.deiconify()' in main_py)
    check('integrity_reports_progress', 'update_startup_component' in launcher and 'Validando el ejecutable autocontenido' in launcher)
    check('geometry_does_not_escape_gate', "if not getattr(app, '_startup_gate_active', False)" in adaptive)

    check('minimal_logo_only', "self.brand_label = ctk.CTkLabel" in gate and "text=''" in gate)
    check('minimal_progress_bar', 'self.progress = ctk.CTkProgressBar' in gate)
    check('visible_percentage', "self.percent = ctk.CTkLabel" in gate and "text='0%'" in gate and "value * 100.0" in gate)
    check('cereon_branding', "text='by Cereon Technologies ©'" in gate and "self.branding.place(relx=0.055, rely=0.91, anchor='w')" in gate)
    check('no_startup_status_copy', all(token not in gate for token in ('self.status =', 'self.subtitle =', 'self.detail =', 'CEREON TECHNOLOGIES', 'Sin estimaciones · sólo datos certificados')))
    check('compact_gate', 'WIDTH = 560' in gate and 'HEIGHT = 250' in gate)

    check('monitor_work_area', '_active_monitor_work_area' in gate and 'GetMonitorInfoW' in gate)
    check('native_monitor_centering', '_center_native_window_on_active_monitor' in gate and 'GetWindowRect' in gate and 'SetWindowPos' in gate)
    check('center_after_hwnd_materialized', 'self.window.update_idletasks()' in gate and 'self.window.after(80, self._center_now)' in gate)
    check('negative_coordinates_supported', "f'{width}x{height}{x:+d}{y:+d}'" in gate)

    check('startup_metrics_preserved', all(token in profiler for token in ('startup_gate_visible_ms', 'startup_gate_complete_ms', 'main_window_revealed_ms')))
    print('RESULTADO: PASS')


if __name__ == '__main__':
    main()
