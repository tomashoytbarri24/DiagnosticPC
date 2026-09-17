"""Regresión del módulo de temas V100."""
from pathlib import Path
import json
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
    nav=(ROOT/'gui'/'internal_navigation.py').read_text(encoding='utf-8')
    panel=(ROOT/'gui'/'theme_panel.py').read_text(encoding='utf-8')
    profiles=tm.get_theme_profiles()

    with tempfile.TemporaryDirectory() as td:
        old_file=tm._THEME_FILE
        try:
            tm._THEME_FILE=Path(td)/'ui_theme.json'
            default_ok=tm.get_theme()==tm.DEFAULT_THEME
            tm.set_theme('violet')
            violet_ok=tm.get_theme()=='violet' and tm.color('#06111f') != '#06111f'
            tm._THEME_FILE.write_text(json.dumps({'theme':'light'}),encoding='utf-8')
            migration_ok=tm.get_theme()=='snow'
        finally:
            tm._THEME_FILE=old_file

    results=[
        check('version', VERSION == '103'),
        check('stage_preserved', STAGE == 'STARTUP_RESPONSIVENESS_SINGLE_LAYOUT_AUTHORITY'),
        check('exactly_10_themes', len(profiles) == 10),
        check('theme_button', '_theme_toggle_button = ctk.CTkButton' in dashboard and "text='Temas'" in dashboard),
        check('internal_module', "activate_internal_page(self, 'themes')" in mainpy and "'themes': '_theme_toggle_button'" in nav),
        check('no_toplevel', 'CTkToplevel' not in panel and 'Toplevel(' not in panel),
        check('scrollable_picker', 'CTkScrollableFrame' in panel),
        check('preview', "text='Vista previa'" in panel),
        check('apply_button', "text='Aplicar tema'" in panel and 'set_theme(self.selected_theme)' in panel),
        check('restart_for_consistency', 'restart_application()' in panel),
        check('persistent_theme_file', 'ui_theme.json' in (ROOT/'core'/'theme_manager.py').read_text(encoding='utf-8')),
        check('runtime_appearance', 'get_ctk_appearance_mode()' in mainpy),
        check('dynamic_logo', 'brand_symbol_path' in dashboard and 'brand_symbol_path' in mainpy),
        check('dynamic_sidebar_assets', 'sidebar_assets_path' in dashboard),
        check('agent_preserves_theme_button', 'theme_button.pack' in layout),
        check('default_theme', default_ok),
        check('named_theme_persistence', violet_ok),
        check('legacy_light_migration', migration_ok),
    ]
    ok=all(results)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1

if __name__ == '__main__':
    raise SystemExit(main())
