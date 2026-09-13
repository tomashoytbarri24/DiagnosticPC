"""Regresión V102 — overlay fijo, RTSS.exe seguro y startup multi-monitor."""
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
    panel = (ROOT / 'gui' / 'overlay_config_panel.py').read_text(encoding='utf-8')
    rtss = (ROOT / 'core' / 'rtss_osd.py').read_text(encoding='utf-8')
    startup = (ROOT / 'gui' / 'startup_gate.py').read_text(encoding='utf-8')
    check('version', VERSION == '103')
    check('overlay_personalization_always_visible', "self.body.pack(fill='x', expand=False" in panel)
    check('overlay_no_hide_button', "text='Personalizar'" not in panel and "configure(text='Ocultar')" not in panel)
    check('rtss_only_exact_exe', "resolved.name.casefold() != 'rtss.exe'" in rtss)
    check('uninstall_display_icon_not_executed', "QueryValueEx(key, 'DisplayIcon')" not in rtss)
    check('startup_uses_monitor_work_area', '_active_monitor_work_area' in startup and 'GetMonitorInfoW' in startup)
    check('startup_preserves_negative_coordinates', "f'{width}x{height}{x:+d}{y:+d}'" in startup and 'max(0, (screen_w - width)' not in startup)
    print('RESULTADO: PASS')


if __name__ == '__main__':
    main()
