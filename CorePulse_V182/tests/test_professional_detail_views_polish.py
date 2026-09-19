"""Regresión V100 — Professional Detail Views Polish."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from core.version import VERSION, STAGE

def check(name, cond):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}: {bool(cond)}")
    return bool(cond)

def main():
    files={n:(ROOT/'gui'/n).read_text(encoding='utf-8') for n in (
        'cpu_detail_panel.py','gpu_detail_panel.py','ram_detail_panel.py','storage_detail_panel.py',
        'health_center_panel.py','overlay_config_panel.py','cleaning_center.py','alert_panel.py',
        'session_trends_panel.py','alert_history_panel.py')}
    checks=[
        check('version', VERSION.isdecimal()),
        check('stage', bool(STAGE)),
        check('cpu_professional_header', "eyebrow='Procesador · Vista avanzada'" in files['cpu_detail_panel.py']),
        check('gpu_professional_header', "eyebrow='Gráficos · Vista multi-GPU'" in files['gpu_detail_panel.py']),
        check('ram_professional_header', "eyebrow='Memoria · Inventario físico'" in files['ram_detail_panel.py']),
        check('storage_professional_header', "eyebrow='Almacenamiento · SMART y confiabilidad'" in files['storage_detail_panel.py']),
        check('health_professional_header', "eyebrow='Estado y mantenimiento preventivo'" in files['health_center_panel.py']),
        check('overlay_professional_header', "eyebrow='OSD · RTSS'" in files['overlay_config_panel.py']),
        check('cleaning_professional_header', "eyebrow='Mantenimiento seguro'" in files['cleaning_center.py']),
        check('alerts_professional_header', "eyebrow='Supervisión del agente'" in files['alert_panel.py']),
        check('trends_professional_header', "eyebrow='Comparativa de sesiones'" in files['session_trends_panel.py']),
        check('history_professional_header', "eyebrow='Registro de la sesión'" in files['alert_history_panel.py']),
        check('back_copy_standardized', all('Volver al resumen' not in (ROOT/'gui'/n).read_text(encoding='utf-8') for n in ('cpu_detail_panel.py','gpu_detail_panel.py','ram_detail_panel.py','network_detail_panel.py','windows_tweaks_panel.py','telemetry_detail_panel.py','gaming_panel.py'))),
    ]
    ok=all(checks)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1
if __name__=='__main__': raise SystemExit(main())
