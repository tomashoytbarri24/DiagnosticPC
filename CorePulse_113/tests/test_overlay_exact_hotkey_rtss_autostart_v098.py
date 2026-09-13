"""Regresión V100 — atajo exacto, layout compacto y autoinicio RTSS."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION
from core.global_hotkeys import CAPTURE_VERSION, normalize_hotkey_config, parse_hotkey_label, hotkey_to_label
from core.overlay_preferences import normalize_preferences


def check(name, cond):
    if not cond:
        raise AssertionError(name)
    print('[PASS]', name)


def main():
    panel = (ROOT / 'gui' / 'overlay_config_panel.py').read_text(encoding='utf-8')
    hotkeys = (ROOT / 'core' / 'global_hotkeys.py').read_text(encoding='utf-8')
    rtss = (ROOT / 'core' / 'rtss_osd.py').read_text(encoding='utf-8')
    service = (ROOT / 'core' / 'rtss_overlay_service.py').read_text(encoding='utf-8')
    check('version', VERSION == '103')
    parsed = parse_hotkey_label('Ctrl+9')
    check('ctrl9_exact', parsed['modifiers'] == ['CTRL'] and parsed['key'] == '9')
    check('ctrl9_roundtrip', hotkey_to_label(parsed) == 'Ctrl+9')
    check('capture_v2', parsed.get('capture_version') == CAPTURE_VERSION == 2)
    check('no_event_state_in_capture', 'modifiers_from_tk_state' not in panel and "getattr(event, 'state'" not in panel)
    check('explicit_modifier_capture', 'mods = set(self._pressed_modifiers)' in panel)
    prefs = normalize_preferences({'toggle_hotkey': {'modifiers': ['CTRL'], 'key': '9', 'enabled': True, 'capture_version': 2}})
    check('prefs_preserve_exact_modifiers', prefs['toggle_hotkey']['modifiers'] == ['CTRL'])
    check('metrics_no_vertical_stretch', "self.metrics.grid(row=0, column=0, sticky='new'" in panel)
    check('advanced_body_compact', "self.body.pack(fill='x', expand=False" in panel)
    check('rtss_process_guard', 'def rtss_process_running()' in rtss)
    check('rtss_registry_and_common_paths', 'App Paths' in rtss and 'MSI Afterburner' in rtss and 'RTSS.exe' in rtss)
    check('rtss_autostart_retry', '_ensure_rtss_started' in service and 'RTSS iniciándose automáticamente' in service)
    check('no_alt_injection_code', "'ALT': 'ALT'" in hotkeys and 'MODIFIER_ORDER' in hotkeys)
    print('RESULTADO: PASS')


if __name__ == '__main__':
    main()
