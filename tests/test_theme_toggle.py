"""Regresión del selector de tema unificado V0.10.0.0w."""
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION, STAGE
import core.theme_manager as tm


def check(name, value):
    print(f"[{'PASS' if value else 'FAIL'}] {name}: {bool(value)}")
    return bool(value)


def main():
    dashboard=(ROOT/'gui'/'dashboard.py').read_text(encoding='utf-8')
    layout=(ROOT/'gui'/'dashboard_layout.py').read_text(encoding='utf-8')
    mainpy=(ROOT/'main.py').read_text(encoding='utf-8')
    manager=(ROOT/'core'/'theme_manager.py').read_text(encoding='utf-8')
    with tempfile.TemporaryDirectory() as td:
        old_file=tm._THEME_FILE
        try:
            tm._THEME_FILE=Path(td)/'ui_theme.json'
            dark_default=tm.get_theme()==tm.DARK
            tm.set_theme(tm.LIGHT)
            persists_light=tm.get_theme()==tm.LIGHT and tm.color('#06111f')=='#e1e6ec'
            tm.set_theme(tm.DARK)
            persists_dark=tm.get_theme()==tm.DARK and tm.color('#06111f')=='#06111f'
        finally:
            tm._THEME_FILE=old_file
    results=[
        check('version', VERSION == '0.10.0.0w'),
        check('stage', STAGE == 'HEALTH_INTELLIGENCE_RECOVERY'),
        check('theme_button', '_theme_toggle_button = ctk.CTkButton' in dashboard),
        check('theme_action_labels', "'Modo oscuro'" in manager and "'Modo claro'" in manager),
        check('persistent_theme_file', 'ui_theme.json' in manager),
        check('runtime_appearance', 'get_ctk_appearance_mode()' in mainpy),
        check('restart_on_toggle', 'restart_application()' in mainpy),
        check('dynamic_logo', 'brand_symbol_path' in dashboard and 'brand_symbol_path' in mainpy),
        check('dynamic_sidebar_assets', 'sidebar_assets_path' in dashboard),
        check('light_assets_present', (ROOT/'assets'/'CorePulseSymbolLight.png').is_file() and (ROOT/'assets'/'sidebar_light'/'summary.png').is_file()),
        check('agent_preserves_theme_button', 'theme_button.pack' in layout),
        check('dark_default', dark_default),
        check('light_persistence_and_palette', persists_light),
        check('dark_persistence_and_palette', persists_dark),
    ]
    ok=all(results)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1

if __name__ == '__main__':
    raise SystemExit(main())
