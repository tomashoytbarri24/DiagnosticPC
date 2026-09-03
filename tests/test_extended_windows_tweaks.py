"""Cobertura del catálogo extendido y reglas de seguridad V0.10.0.0w."""
from __future__ import annotations
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from core import windows_tweaks as wt
from core.version import VERSION, STAGE


def check(name, cond):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}: {bool(cond)}")
    return bool(cond)


def main():
    items=wt.catalog(); by={x['id']:x for x in items}
    presets={k:set(wt.preset_ids(k)) for k in wt.PRESETS}
    dangerous={x['id'] for x in items if x['risk'] in ('Alto','Crítico')}
    selected=wt.selected_metadata(['disable_defender_stack','remove_edge','enable_hags'])
    checks=[
        check('version', VERSION=='0.10.0.0w'),
        check('stage', STAGE=='HEALTH_INTELLIGENCE_RECOVERY'),
        check('catalog_60_plus', len(items)>=60),
        check('unique_ids', len(by)==len(items)),
        check('all_have_risk', all(x.get('risk') in ('Bajo','Medio','Alto','Crítico') for x in items)),
        check('all_have_category', all(bool(x.get('category')) for x in items)),
        check('dangerous_not_presets', all(dangerous.isdisjoint(ids) for ids in presets.values())),
        check('defender_is_critical_admin', by['disable_defender_stack']['risk']=='Crítico' and by['disable_defender_stack']['requires_admin']),
        check('uac_is_critical_restart', by['disable_uac']['risk']=='Crítico' and by['disable_uac']['requires_restart']),
        check('edge_preserves_webview_text', 'WebView2' in by['remove_edge']['description'] or 'WebView2' in (by['remove_edge'].get('note') or '')),
        check('onedrive_does_not_delete_personal_folder', 'no elimina' in (by['remove_onedrive'].get('note') or '').lower()),
        check('security_metadata', bool(selected['critical']) and selected['requires_admin'] and selected['requires_restart']),
        check('advanced_preset_safe', all(by[i]['risk'] in ('Bajo','Medio') for i in presets['advanced'])),
    ]
    ok=all(checks)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1

if __name__=='__main__':
    raise SystemExit(main())
