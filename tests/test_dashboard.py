"""Regresión estática del Dashboard y de la identidad universal del encabezado."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
dashboard = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
layout = (ROOT / 'gui' / 'dashboard_layout.py').read_text(encoding='utf-8')
sidebar = (ROOT / 'gui' / 'sidebar.py').read_text(encoding='utf-8')

checks = {
    'white_brand_asset': (ROOT / 'assets' / 'CorePulseSymbolWhite.png').exists(),
    'status_cards_present': 'app._status_cards = (health_card, alerts, coverage, uptime)' in dashboard,
    'sidebar_icons_are_assets': 'SIDEBAR_ICON_FILES' in dashboard and "'btn_overlay': 'Overlay In-Game'" in sidebar,
    'device_identity_header': 'from core.device_identity import collect_device_identity' in dashboard,
    'desktop_uses_display_model': "identity.get('display_model') or identity.get('model')" in dashboard,
    'device_model_font_13': "text='Identificando modelo…',\n        font=(FONT, 13, 'bold')" in dashboard,
    'responsive_keeps_model_readable': "font=(FONT, 12 if compact else 13, 'bold')" in layout,
    'obsolete_monitoring_label_absent': "text='EQUIPO EN MONITOREO'" not in dashboard,
}
for name, ok in checks.items():
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {bool(ok)}")
print('\nRESULTADO:', 'PASS' if all(checks.values()) else 'FAIL')
raise SystemExit(0 if all(checks.values()) else 1)
