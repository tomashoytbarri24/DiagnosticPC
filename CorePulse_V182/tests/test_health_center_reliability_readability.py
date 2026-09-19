"""Regresión V100 — Health Center Reliability & Readability."""
from __future__ import annotations
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION


def check(name, condition):
    print(f"[{'PASS' if condition else 'FAIL'}] {name}: {bool(condition)}")
    return bool(condition)


def main():
    win = (ROOT/'core/windows_health.py').read_text(encoding='utf-8')
    ui = (ROOT/'gui/health_center_panel.py').read_text(encoding='utf-8')
    results = [
        check('version', VERSION.isdecimal()),
        check('json_result_wrapper', '$result = & {' in win and 'ConvertTo-Json -InputObject @($result)' in win),
        check('no_fragile_json_pipe', "{script} | ConvertTo-Json" not in win),
        check('powershell_hidden', 'CREATE_NO_WINDOW' in win and 'shell=False' in win),
        check('powershell_utf8', 'OutputEncoding' in win and "encoding='utf-8'" in win),
        check('technical_errors_logged', "logger.error('[WINDOWS_HEALTH][POWERSHELL]" in win),
        check('friendly_errors', '_friendly_ps_error' in win),
        check('analyzer_failure_stops_zero_results', 'CorePulse no mostrará ceros ni estados normales cuando la consulta haya fallado.' in ui),
        check('analyzer_states', all(x in ui for x in ('Pendiente', 'Completado', 'No disponible'))),
        check('windows_buttons_feedback', "btn.configure(text='Analizando…', state='disabled')" in ui),
        check('readable_kv_grid', "row.grid_columnconfigure(1, weight=1)" in ui and 'wraplength=760' in ui),
        check('humanized_services', '_service_state_label' in ui and '_start_mode_label' in ui),
        check('humanized_drivers', '_driver_status_label' in ui),
        check('humanized_benchmark_providers', '_bench_provider_label' in ui),
        check('bigger_line_font', "font=(FONT, 9), text_color=TEXT2" in ui),
    ]
    ok = all(results)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
