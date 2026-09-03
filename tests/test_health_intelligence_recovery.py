"""Regresión V0.10.0.0w — Health Intelligence & Recovery."""
from __future__ import annotations

import tempfile
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))

from core.version import VERSION, STAGE
from core.health_history import HealthHistoryStore
from core.battery_health import collect_battery_health
from core.thermal_throttling import ThermalThrottlingDetector
from core.benchmark_engine import benchmark_cpu, benchmark_ram, benchmark_ssd, benchmark_gpu
from core.before_after import capture_metrics, compare
import core.windows_health as wh


def check(name,cond):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}: {bool(cond)}")
    return bool(cond)


def main():
    results=[]
    results.append(check('version',VERSION=='0.10.0.0w'))
    results.append(check('stage',STAGE=='HEALTH_INTELLIGENCE_RECOVERY'))

    with tempfile.TemporaryDirectory() as td:
        store=HealthHistoryStore(Path(td)/'health.sqlite3')
        tele={'cpu_temp':80,'cpu_usage':72,'cpu_ghz':3.8,'ram_usage':55,'gpu_temp':61,'gpu_usage':30,'_cpu':{'package_power_w':35},'_battery':{'designed_capacity_mwh':60000,'full_charge_capacity_mwh':51000}}
        store.record_snapshot(tele,[{'health':93}],88)
        q=store.query(1)
        results.append(check('history_persists_real_values',len(q)==1 and q[0]['cpu_temp']==80 and q[0]['storage_health']==93))
        results.append(check('history_battery_health',round(q[0]['battery_health'],1)==85.0))
        s=store.summary(7)
        results.append(check('history_summary',s['samples']==1 and s['metrics']['cpu_temp']['max']==80))

    batt=collect_battery_health({'_battery':{'designed_capacity_mwh':60000,'full_charge_capacity_mwh':48000,'charge_percent':70}})
    results.append(check('battery_health_calculated_from_real_capacities',round(batt.get('health_percent') or 0,1)==80.0))
    results.append(check('battery_policy',batt.get('policy')=='REAL_OR_NA'))

    det=ThermalThrottlingDetector()
    explicit={'cpu_usage':90,'cpu_temp':98,'cpu_ghz':2.2,'_cpu':{'distance_to_tjmax_min_c':2,'sensors':[{'name':'Thermal Throttling','value':1}]}}
    state=det.add_sample(explicit)
    results.append(check('throttling_explicit_confirmed',state['cpu']['state']=='CONFIRMED' and state['cpu']['reason']=='THERMAL'))
    det2=ThermalThrottlingDetector()
    for ghz in (4.3,4.2,4.1,3.9,2.8):
        st=det2.add_sample({'cpu_usage':88,'cpu_temp':97,'cpu_ghz':ghz,'_cpu':{'distance_to_tjmax_min_c':3,'sensors':[]}})
    results.append(check('throttling_without_sensor_not_false_confirmed',st['cpu']['state']!='CONFIRMED'))
    results.append(check('throttling_evidence_policy','CONFIRMED_ONLY_WITH_EXPLICIT_SENSOR' in st['policy']))

    cpu=benchmark_cpu(0.5); ram=benchmark_ram(32,1)
    results.append(check('cpu_benchmark_real_positive',(cpu.get('value') or 0)>0 and cpu.get('provider')=='CorePulse SHA-256 workload'))
    results.append(check('ram_benchmark_real_positive',(ram.get('value') or 0)>0 and ram.get('unit')=='MB/s'))
    with tempfile.TemporaryDirectory() as td:
        ssd=benchmark_ssd(td,32)
        results.append(check('ssd_benchmark_write_read',(ssd.get('write_mbps') or 0)>0 and (ssd.get('read_mbps') or 0)>0))
    gpu=benchmark_gpu(timeout=3)
    results.append(check('gpu_benchmark_degrades_or_runs',gpu.get('provider') in ('N/A','Windows WinSAT D3D')))

    before=capture_metrics({'cpu_temp':80,'cpu_ghz':3.5,'ram_usage':60},label='before')
    after=capture_metrics({'cpu_temp':70,'cpu_ghz':4.0,'ram_usage':50},label='after')
    comp=compare(before,after)
    results.append(check('before_after_delta',comp['available'] and comp['deltas']['cpu_temp']['delta']==-10))
    results.append(check('before_after_no_causality_claim','no implica causalidad' in comp['note']))

    # En no-Windows los analizadores deben degradar de forma segura; en Windows pueden devolver datos reales.
    startup=wh.analyze_startup(); services=wh.analyze_services(limit=5); crashes=wh.analyze_crashes(days=1,max_events=5); drivers=wh.analyze_drivers(limit=5)
    results.append(check('startup_contract',isinstance(startup.get('items'),list) and startup.get('policy')=='NO_AUTO_DISABLE'))
    results.append(check('services_contract',isinstance(services.get('items'),list) and services.get('policy')=='ANALYZE_ONLY'))
    results.append(check('crash_contract',isinstance(crashes.get('counts'),dict)))
    results.append(check('driver_contract',isinstance(drivers.get('items'),list)))

    with tempfile.TemporaryDirectory() as td:
        old=wh.HW_STATE; wh.HW_STATE=Path(td)/'baseline.json'
        try:
            inv={'identity':{'manufacturer':'A','model':'B'},'cpu':{'name':'CPU'},'ram':{'module_total_gb':16,'module_count':1,'modules':[]},'gpus':[{'name':'GPU'}],'storage':[{'model':'SSD'}]}
            first=wh.compare_hardware_inventory(inv)
            inv2={**inv,'ram':{'module_total_gb':32,'module_count':2,'modules':[]}}
            second=wh.compare_hardware_inventory(inv2)
            results.append(check('hardware_baseline_created',first['baseline_exists'] is False))
            results.append(check('hardware_change_detected',any(c['component']=='RAM' for c in second['changes'])))
        finally: wh.HW_STATE=old

    rp=wh.restore_point_status()
    results.append(check('restore_contract','available' in rp and 'admin' in rp))

    main_text=(ROOT/'main.py').read_text(encoding='utf-8')
    panel=(ROOT/'gui'/'health_center_panel.py').read_text(encoding='utf-8')
    dash=(ROOT/'gui'/'dashboard.py').read_text(encoding='utf-8')
    nav=(ROOT/'gui'/'internal_navigation.py').read_text(encoding='utf-8')
    results += [
        check('health_center_sidebar',"btn_health_center" in dash and "Centro de salud" in dash),
        check('health_center_navigation',"'health_center': 'btn_health_center'" in nav),
        check('history_recorded_off_ui_telemetry_thread','health_history_store.record_snapshot' in main_text),
        check('throttling_sampled_from_real_telemetry','thermal_throttling_detector.add_sample(telemetry)' in main_text),
        check('all_requested_sections',all(x in panel for x in ('Battery Health','Thermal Throttling','Benchmark integrado','Startup Analyzer','Servicios Analyzer','Crash / BSOD / WHEA','Driver Health','Hardware Changes','Antes vs Después','Restore / Rollback','Red avanzada'))),
        check('no_service_auto_disable','NO_AUTO_DISABLE' in (ROOT/'core'/'windows_health.py').read_text(encoding='utf-8')),
        check('restore_is_explicit_confirmation','askyesno' in panel and 'Checkpoint-Computer' in (ROOT/'core'/'windows_health.py').read_text(encoding='utf-8')),
    ]
    ok=all(results); print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}"); return 0 if ok else 1

if __name__=='__main__': raise SystemExit(main())
