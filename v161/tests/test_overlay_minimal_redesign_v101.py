"""Regresión V101 — Overlay minimalista, compacto y sin perder controles."""
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
    panel = (ROOT / 'gui' / 'overlay_config_panel.py').read_text(encoding='utf-8')
    checks = [
        check('version', VERSION == '103'),
        check('compact_header_actions', 'header_actions = ctk.CTkFrame' in panel and "text='Iniciar Overlay'" in panel),
        check('service_status_is_inline', "service = ctk.CTkFrame(self.root, fg_color='transparent')" in panel),
        check('old_big_status_card_removed', 'self.status_card = ctk.CTkFrame' not in panel),
        check('single_preview_surface', 'self.preview_card = ctk.CTkFrame' in panel),
        check('metrics_compact_rows', "height=48" in panel and "grid_propagate(False)" in panel),
        check('single_configuration_surface', "text='Configuración'" in panel and '_subcard(' not in panel),
        check('exact_hotkey_preserved', 'mods = set(self._pressed_modifiers)' in panel and 'capture_version' in panel),
        check('responsive_columns_preserved', "mode = 'stacked' if width < 960 else 'columns'" in panel),
        check('advanced_panel_remains_collapsible', 'def _toggle_advanced_settings' in panel),
    ]
    ok = all(checks)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
