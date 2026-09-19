"""V126 — tarjetas de Windows + Temas persistentemente visible."""
from __future__ import annotations

import hashlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION, STAGE
import textwrap


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print('[PASS]', name)


def sha256(rel):
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


def main():
    health = (ROOT / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')
    dashboard = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    layout = (ROOT / 'gui' / 'dashboard_layout.py').read_text(encoding='utf-8')
    consistency = (ROOT / 'gui' / 'ui_consistency.py').read_text(encoding='utf-8')

    check('version', VERSION.isdecimal())
    check('stage', bool(STAGE))
    check('windows_cards_2x2', "grid.grid_rowconfigure(row, minsize=238" in health and "uniform='windows_summary_cards'" in health)
    check('card_actions', "'Ejecutar análisis'" in health and "'Actualizar análisis'" in health and "actions, 'Ver más'" in health)
    check('details_gate', "if not isinstance(data, dict) or running:" in health and "more_btn.configure(state='disabled')" in health)
    check('summary_metrics_real_or_na', 'def _windows_summary_metrics(self, section):' in health and 'N/A · sin RAM medible en ejecución' in health)
    check('startup_all_items_paginated', '_startup_page_size = 30' in health and 'visible_items = items[start:end]' in health and 'def _set_startup_page(self, page):' in health)
    check('summary_is_gateway', "if section == 'summary':\n            self._render_windows_summary()\n            return" in health and "'Volver al resumen de Windows'" in health)

    # Ejecuta sólo el helper puro extraído del source, sin importar CustomTkinter.
    # Esto permite validar REAL_OR_NA en entornos CI sin GUI instalada.
    start = health.index('    def _windows_summary_metrics(self, section):')
    end = health.index('    def _windows_summary_job(self, section):', start)
    helper_src = textwrap.dedent(health[start:end])
    ns = {
        '_num': lambda v: float(v) if v is not None else None,
        '_short': lambda text, n=120: (str(text) if len(str(text)) <= n else str(text)[:n-1] + '…'),
        '_driver_status_label': lambda v: {'DEVICE_PROBLEM':'Problema de dispositivo','UNSIGNED':'No firmado','OLD':'Antiguo','OK':'Correcto'}.get(str(v or '').upper(), 'N/A'),
    }
    exec(helper_src, ns)
    summary_metrics = ns['_windows_summary_metrics']
    class Dummy:
        pass
    panel = Dummy()
    panel._startup = {
        'count': 2,
        'items': [
            {'name': 'Ligero', 'running_memory_mb': 42.0, 'impact': 'BAJO'},
            {'name': 'Pesado', 'running_memory_mb': 256.5, 'impact': 'MEDIO'},
        ],
    }
    panel._services = {
        'count': 2,
        'items': [
            {'DisplayName': 'Svc A', 'memory_mb': 12.0},
            {'DisplayName': 'Svc B', 'memory_mb': 350.25},
        ],
    }
    panel._crashes = {'matched_total': 3, 'items': [{'kind': 'app_error', 'ApplicationName': 'app.exe'}]}
    panel._drivers = {'count': 1, 'items': [{'DeviceName': 'GPU', 'status': 'DEVICE_PROBLEM', 'hardware_priority': 100}]}
    startup = summary_metrics(panel, 'startup')
    services = summary_metrics(panel, 'services')
    crashes = summary_metrics(panel, 'crashes')
    drivers = summary_metrics(panel, 'drivers')
    check('startup_heaviest_measured', startup[1] == '2' and 'Pesado' in startup[3] and '256.5 MB' in startup[3])
    check('services_heaviest_measured', services[1] == '2' and 'Svc B' in services[3] and '350.2 MB' in services[3])
    check('stability_relevant_real_event', crashes[1] == '3' and 'app.exe' in crashes[3])
    check('drivers_relevant_real_device', drivers[1] == '1' and 'GPU' in drivers[3])

    check('theme_button_larger', "text='◉  TEMAS'" in dashboard and 'height=42' in dashboard and 'border_width=2' in dashboard)
    check('theme_uses_exact_roles', "fg_color=theme_accent" in dashboard and "hover_color=theme_accent_2" in dashboard and "role_color('accent')" in layout)
    check('theme_survives_nav_refresh', "if attr == '_theme_toggle_button':" in consistency and "fg_color=role_color('accent_2') if active else role_color('accent')" in consistency)
    check('personalization_label_stays_with_cta', 'app._personalization_label = personalization' in dashboard and "personalization_label.pack(side='top'" in layout)

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
