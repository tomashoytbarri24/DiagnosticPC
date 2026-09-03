"""Regresión de V0.10.0.0w: Red avanzada debe sobrevivir al rebuild del sidebar."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
from core.version import VERSION, STAGE

def check(name, cond):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}: {bool(cond)}")
    return bool(cond)

def main():
    dashboard=(ROOT/'gui'/'dashboard.py').read_text(encoding='utf-8')
    layout=(ROOT/'gui'/'dashboard_layout.py').read_text(encoding='utf-8')
    consistency=(ROOT/'gui'/'ui_consistency.py').read_text(encoding='utf-8')
    nav=(ROOT/'gui'/'internal_navigation.py').read_text(encoding='utf-8')
    main_py=(ROOT/'main.py').read_text(encoding='utf-8')
    icon=ROOT/'assets'/'sidebar'/'network.png'
    checks=[
        check('version', VERSION=='0.10.0.0w'),
        check('stage', STAGE=='HEALTH_INTELLIGENCE_RECOVERY'),
        check('button_created', 'self.btn_network = ctk.CTkButton' in main_py),
        check('dashboard_rebuild_packs_network', "_apply_sidebar_icon(app, 'btn_network')" in dashboard and "app.btn_network.pack(fill='x', padx=13, pady=1)" in dashboard),
        check('dashboard_label', "'btn_network': 'Red avanzada'" in dashboard),
        check('dashboard_icon_mapping', "'btn_network': 'network.png'" in dashboard),
        check('responsive_nav_contains_network', "'btn_network': 'Red avanzada'" in layout),
        check('responsive_context_network', "'network': 'btn_network'" in layout),
        check('consistency_actions_network', "'btn_network'" in consistency and "'network': 'btn_network'" in consistency),
        check('dispatcher_routes_network', "'btn_network': ('network', lambda: app.open_network_details())" in consistency),
        check('internal_navigation_route', "'network': 'btn_network'" in nav),
        check('network_icon_exists', icon.exists() and icon.stat().st_size>0),
    ]
    ok=all(checks)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1

if __name__=='__main__':
    raise SystemExit(main())
