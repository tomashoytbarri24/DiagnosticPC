"""V100 — ruta universal por defecto + dropdowns CorePulse."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION
from core.internet_speed_test import InternetSpeedTest


def check(name, condition):
    print(f"[{'PASS' if condition else 'FAIL'}] {name}: {bool(condition)}")
    return bool(condition)


def main():
    panel = (ROOT / 'gui' / 'network_detail_panel.py').read_text(encoding='utf-8')
    engine = (ROOT / 'core' / 'internet_speed_test.py').read_text(encoding='utf-8')
    runner = InternetSpeedTest(provider='ookla')
    checks = [
        check('version', VERSION == '103'),
        check('runner_default_is_auto', runner.ip_family == 'auto'),
        check('function_default_is_auto', "ip_family='auto'" in engine),
        check('ui_state_default_is_auto', "self._speed_ip_choice = 'Automática (recomendado)'" in panel),
        check('ui_menu_default_is_auto', "self.speed_ip_menu.set('Automática (recomendado)')" in panel),
        check('manual_routes_remain_available', 'IPv4 (comparar con navegador)' in panel and 'IPv6 (avanzado)' in panel),
        check('dropdown_style_is_centralized', 'def _corepulse_option_menu' in panel),
        check('dropdown_uses_corepulse_surface', 'dropdown_fg_color=CARD_2' in panel),
        check('dropdown_uses_corepulse_hover', "dropdown_hover_color=theme_color('#164f7d')" in panel),
        check('dropdown_uses_corepulse_text', 'dropdown_text_color=TEXT' in panel),
        check('dropdown_uses_segoe_font', 'dropdown_font=(FONT, 9)' in panel),
        check('all_three_controls_use_helper', panel.count('_corepulse_option_menu(') >= 4),
        check('no_ipv4_internal_default', "ip_family: str = 'ipv4'" not in engine),
    ]
    ok = all(checks)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
