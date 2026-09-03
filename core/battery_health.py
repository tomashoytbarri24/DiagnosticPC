"""Estado de batería con fuentes reales de Windows/LHM/psutil."""
from __future__ import annotations

import os
import platform
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict

import psutil


def _num(v):
    try:
        return float(v) if v is not None else None
    except Exception:
        return None


def _first_xml_number(root, names):
    wanted = {n.lower() for n in names}
    for node in root.iter():
        tag = node.tag.split('}')[-1].lower()
        if tag in wanted:
            text = (node.text or '').strip().replace(',', '').replace('mWh','').strip()
            try:
                return float(text)
            except Exception:
                pass
    return None


def _powercfg_battery_report():
    if platform.system() != 'Windows':
        return {}
    out = Path(tempfile.gettempdir()) / f'corepulse_battery_{os.getpid()}.xml'
    try:
        cp = subprocess.run(['powercfg', '/batteryreport', '/xml', '/output', str(out)], capture_output=True, text=True, timeout=20, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if cp.returncode != 0 or not out.exists():
            return {}
        root = ET.parse(out).getroot()
        return {
            'designed_capacity_mwh': _first_xml_number(root, ('DesignCapacity','DesignCapacitymWh')),
            'full_charge_capacity_mwh': _first_xml_number(root, ('FullChargeCapacity','FullChargeCapacitymWh')),
            'cycle_count': _first_xml_number(root, ('CycleCount',)),
            'source': 'powercfg /batteryreport /xml',
        }
    except Exception:
        return {}
    finally:
        try:
            out.unlink(missing_ok=True)
        except Exception:
            pass



def _wmi_battery_data():
    if platform.system() != 'Windows':
        return {}
    script = r"""
$ErrorActionPreference='SilentlyContinue'
$static=@(Get-CimInstance -Namespace root/WMI -ClassName BatteryStaticData | Select-Object -First 1 DesignedCapacity)
$full=@(Get-CimInstance -Namespace root/WMI -ClassName BatteryFullChargedCapacity | Select-Object -First 1 FullChargedCapacity)
$cycle=@(Get-CimInstance -Namespace root/WMI -ClassName BatteryCycleCount | Select-Object -First 1 CycleCount)
$status=@(Get-CimInstance -Namespace root/WMI -ClassName BatteryStatus | Select-Object -First 1 RemainingCapacity,Voltage,Rate,Charging,Discharging)
[pscustomobject]@{
 DesignedCapacity=if($static){$static[0].DesignedCapacity}else{$null}
 FullChargedCapacity=if($full){$full[0].FullChargedCapacity}else{$null}
 CycleCount=if($cycle){$cycle[0].CycleCount}else{$null}
 RemainingCapacity=if($status){$status[0].RemainingCapacity}else{$null}
 VoltageMv=if($status){$status[0].Voltage}else{$null}
 RateMw=if($status){$status[0].Rate}else{$null}
 Charging=if($status){$status[0].Charging}else{$null}
 Discharging=if($status){$status[0].Discharging}else{$null}
} | ConvertTo-Json -Compress
"""
    try:
        cp = subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-Command',script], capture_output=True, text=True, timeout=15, creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if cp.returncode != 0 or not (cp.stdout or '').strip():
            return {}
        import json
        obj=json.loads(cp.stdout.strip())
        if not isinstance(obj,dict): return {}
        return {
            'designed_capacity_mwh': _num(obj.get('DesignedCapacity')),
            'full_charge_capacity_mwh': _num(obj.get('FullChargedCapacity')),
            'cycle_count': _num(obj.get('CycleCount')),
            'remaining_capacity_mwh': _num(obj.get('RemainingCapacity')),
            'voltage_v': (_num(obj.get('VoltageMv'))/1000.0) if _num(obj.get('VoltageMv')) is not None else None,
            'charge_discharge_rate_w': (_num(obj.get('RateMw'))/1000.0) if _num(obj.get('RateMw')) is not None else None,
            'charging': obj.get('Charging'), 'discharging': obj.get('Discharging'),
            'source':'root/WMI Battery* classes',
        }
    except Exception:
        return {}

def collect_battery_health(telemetry: Dict[str, Any] | None = None) -> Dict[str, Any]:
    telemetry = telemetry if isinstance(telemetry, dict) else {}
    live = telemetry.get('_battery') if isinstance(telemetry.get('_battery'), dict) else {}
    wmi = _wmi_battery_data()
    report = _powercfg_battery_report()
    try:
        pbat = psutil.sensors_battery()
    except Exception:
        pbat = None

    design = _num(live.get('designed_capacity_mwh')) or _num(wmi.get('designed_capacity_mwh')) or _num(report.get('designed_capacity_mwh'))
    full = _num(live.get('full_charge_capacity_mwh')) or _num(wmi.get('full_charge_capacity_mwh')) or _num(report.get('full_charge_capacity_mwh'))
    remaining = _num(live.get('remaining_capacity_mwh')) or _num(wmi.get('remaining_capacity_mwh'))
    health = (full / design * 100.0) if design and full and design > 0 else None
    if health is not None:
        health = max(0.0, min(100.0, health))
    degradation = 100.0 - health if health is not None else _num(live.get('degradation_percent'))
    charge = _num(live.get('charge_percent'))
    if charge is None and pbat is not None:
        charge = _num(getattr(pbat, 'percent', None))
    secs = None
    plugged = None
    if pbat is not None:
        raw = getattr(pbat, 'secsleft', None)
        if isinstance(raw, (int, float)) and raw not in (psutil.POWER_TIME_UNKNOWN, psutil.POWER_TIME_UNLIMITED) and raw >= 0:
            secs = int(raw)
        plugged = bool(getattr(pbat, 'power_plugged', False))

    present = bool(live or wmi or report or pbat is not None)
    return {
        'present': present,
        'health_percent': health,
        'degradation_percent': degradation,
        'designed_capacity_mwh': design,
        'full_charge_capacity_mwh': full,
        'remaining_capacity_mwh': remaining,
        'cycle_count': int(wmi['cycle_count']) if _num(wmi.get('cycle_count')) is not None else int(report['cycle_count']) if _num(report.get('cycle_count')) is not None else None,
        'charge_percent': charge,
        'voltage_v': _num(live.get('voltage_v')) or _num(wmi.get('voltage_v')),
        'current_ma': _num(live.get('current_ma')),
        'charge_discharge_rate_w': _num(live.get('charge_discharge_rate_w')) or _num(wmi.get('charge_discharge_rate_w')),
        'power_plugged': plugged,
        'estimated_seconds_left': secs,
        'sources': [s for s in ('LibreHardwareMonitor' if live else None, wmi.get('source'), report.get('source'), 'psutil.sensors_battery' if pbat is not None else None) if s],
        'policy': 'REAL_OR_NA',
    }
