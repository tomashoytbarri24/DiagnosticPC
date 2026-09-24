"""Estado de batería con fuentes reales de Windows/LHM/psutil."""
from __future__ import annotations

import os
import math
import uuid
import platform
import subprocess
from core.cancellable_process import run as run_cancellable
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict

import psutil


def _num(v):
    try:
        number = float(v) if v is not None and not isinstance(v, bool) else None
        return number if number is not None and math.isfinite(number) else None
    except Exception:
        return None


def _first_num(*values):
    """Devuelve el primer número real disponible preservando cero."""
    for value in values:
        number = _num(value)
        if number is not None:
            return number
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



def _windows_power_status_presence():
    """Consulta presencia de batería mediante una API Win32 rápida y sin WMI.

    GetSystemPowerStatus no inicia procesos ni recorre inventarios. Se usa como
    primer nivel para decidir la geometría del Centro de Salud antes de mostrarlo.
    """
    if platform.system() != 'Windows':
        return None
    try:
        import ctypes

        class SYSTEM_POWER_STATUS(ctypes.Structure):
            _fields_ = [
                ('ACLineStatus', ctypes.c_ubyte),
                ('BatteryFlag', ctypes.c_ubyte),
                ('BatteryLifePercent', ctypes.c_ubyte),
                ('SystemStatusFlag', ctypes.c_ubyte),
                ('BatteryLifeTime', ctypes.c_uint32),
                ('BatteryFullLifeTime', ctypes.c_uint32),
            ]

        status = SYSTEM_POWER_STATUS()
        kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        fn = kernel32.GetSystemPowerStatus
        fn.argtypes = [ctypes.POINTER(SYSTEM_POWER_STATUS)]
        fn.restype = ctypes.c_int
        if not fn(ctypes.byref(status)):
            return None
        flag = int(status.BatteryFlag)
        percent = int(status.BatteryLifePercent)
        if flag == 255:
            return None
        if flag & 128:
            return False
        if percent != 255:
            return True
        if flag & (1 | 2 | 4 | 8):
            return True
    except Exception:
        return None
    return None


def probe_battery_presence(telemetry: Dict[str, Any] | None = None, device_identity: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Detecta batería de forma ligera para decidir el layout antes del render.

    La prioridad es una lectura real ya disponible, luego la API Win32/psutil.
    El factor de forma real de Windows sólo se usa si esas APIs no pueden resolver
    presencia. No hay reglas por fabricante ni por modelo.
    """
    telemetry = telemetry if isinstance(telemetry, dict) else {}
    identity = device_identity if isinstance(device_identity, dict) else {}
    live = telemetry.get('_battery') if isinstance(telemetry.get('_battery'), dict) else None
    if live:
        return {'present': True, 'resolved': True, 'source': 'telemetry._battery', 'captured_at': time.time()}

    direct = _windows_power_status_presence()
    if direct is not None:
        return {'present': bool(direct), 'resolved': True, 'source': 'GetSystemPowerStatus', 'captured_at': time.time()}

    try:
        pbat = psutil.sensors_battery()
    except Exception:
        pbat = None
    if pbat is not None:
        return {'present': True, 'resolved': True, 'source': 'psutil.sensors_battery', 'captured_at': time.time()}

    form = str(identity.get('form_factor') or '').strip().upper()
    if form == 'LAPTOP':
        return {'present': True, 'resolved': True, 'source': 'Win32_SystemEnclosure', 'captured_at': time.time(), 'portable_hint': True}
    if form == 'DESKTOP':
        return {'present': False, 'resolved': True, 'source': 'Win32_SystemEnclosure', 'captured_at': time.time()}

    return {'present': None, 'resolved': False, 'source': None, 'captured_at': time.time()}

def _powercfg_battery_report():
    if platform.system() != 'Windows':
        return {}
    out = Path(tempfile.gettempdir()) / f'corepulse_battery_{os.getpid()}_{uuid.uuid4().hex}.xml'
    try:
        cp = run_cancellable(['powercfg', '/batteryreport', '/xml', '/output', str(out)], capture_output=True, text=True, timeout=20, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if cp.returncode != 0 or not out.exists():
            return {}
        root = ET.parse(out).getroot()
        design = _first_xml_number(root, ('DesignCapacity','DesignCapacitymWh'))
        full = _first_xml_number(root, ('FullChargeCapacity','FullChargeCapacitymWh'))
        cycles = _first_xml_number(root, ('CycleCount',))
        return {
            'designed_capacity_mwh': design,
            'full_charge_capacity_mwh': full,
            'cycle_count': cycles,
            'detected': any(value is not None for value in (design, full, cycles)),
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
$status=@(Get-CimInstance -Namespace root/WMI -ClassName BatteryStatus | Select-Object -First 1 RemainingCapacity,Voltage,Rate,ChargeRate,DischargeRate,Charging,Discharging)
$win32=@(Get-CimInstance -ClassName Win32_Battery | Select-Object -First 1 DeviceID)
[pscustomobject]@{
 DesignedCapacity=if($static){$static[0].DesignedCapacity}else{$null}
 FullChargedCapacity=if($full){$full[0].FullChargedCapacity}else{$null}
 CycleCount=if($cycle){$cycle[0].CycleCount}else{$null}
 RemainingCapacity=if($status){$status[0].RemainingCapacity}else{$null}
 VoltageMv=if($status){$status[0].Voltage}else{$null}
 RateMw=if($status){$status[0].Rate}else{$null}
 ChargeRateMw=if($status){$status[0].ChargeRate}else{$null}
 DischargeRateMw=if($status){$status[0].DischargeRate}else{$null}
 Charging=if($status){$status[0].Charging}else{$null}
 Discharging=if($status){$status[0].Discharging}else{$null}
 Detected=[bool]($static.Count -or $full.Count -or $cycle.Count -or $status.Count -or $win32.Count)
} | ConvertTo-Json -Compress
"""
    try:
        cp = run_cancellable(['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-Command',script], capture_output=True, text=True, timeout=15, creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if cp.returncode != 0 or not (cp.stdout or '').strip():
            return {}
        import json
        obj=json.loads(cp.stdout.strip())
        if not isinstance(obj,dict): return {}
        voltage_mv = _num(obj.get('VoltageMv'))
        rate_mw = _num(obj.get('RateMw'))
        charge_rate_mw = _num(obj.get('ChargeRateMw'))
        discharge_rate_mw = _num(obj.get('DischargeRateMw'))
        charging = bool(obj.get('Charging')) if obj.get('Charging') is not None else None
        discharging = bool(obj.get('Discharging')) if obj.get('Discharging') is not None else None

        # Algunos proveedores exponen Rate y otros separan ChargeRate/DischargeRate.
        # Se conserva el signo cuando la dirección puede certificarse.
        if rate_mw is None:
            if charging and charge_rate_mw is not None:
                rate_mw = abs(charge_rate_mw)
            elif discharging and discharge_rate_mw is not None:
                rate_mw = -abs(discharge_rate_mw)

        voltage_v = (voltage_mv / 1000.0) if voltage_mv is not None else None
        rate_w = (rate_mw / 1000.0) if rate_mw is not None else None
        current_ma = None
        if rate_mw is not None and voltage_mv is not None and voltage_mv > 0:
            # I = P/V. Rate y Voltage son lecturas reales de Windows; sólo se
            # realiza conversión física determinística, nunca una estimación.
            current_ma = (rate_mw / voltage_mv) * 1000.0

        return {
            'designed_capacity_mwh': _num(obj.get('DesignedCapacity')),
            'full_charge_capacity_mwh': _num(obj.get('FullChargedCapacity')),
            'cycle_count': _num(obj.get('CycleCount')),
            'remaining_capacity_mwh': _num(obj.get('RemainingCapacity')),
            'voltage_v': voltage_v,
            'current_ma_derived': current_ma,
            'charge_discharge_rate_w': rate_w,
            'charging': charging, 'discharging': discharging,
            'detected': bool(obj.get('Detected')),
            'source':'root/WMI Battery* classes',
        }
    except Exception:
        return {}

def collect_battery_health(telemetry: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Recopila salud real de batería minimizando consultas redundantes.

    En escritorio, una ausencia resuelta por la API rápida evita iniciar WMI y
    powercfg. En portátil, powercfg queda como fallback de capacidad/ciclos cuando
    WMI/LHM no entregan esos campos.
    """
    telemetry = telemetry if isinstance(telemetry, dict) else {}
    live = telemetry.get('_battery') if isinstance(telemetry.get('_battery'), dict) else {}
    presence = probe_battery_presence(telemetry)

    try:
        pbat = psutil.sensors_battery()
    except Exception:
        pbat = None

    if presence.get('resolved') and presence.get('present') is False and not live and pbat is None:
        return {
            'present': False, 'health_percent': None, 'degradation_percent': None,
            'designed_capacity_mwh': None, 'full_charge_capacity_mwh': None,
            'remaining_capacity_mwh': None, 'cycle_count': None, 'charge_percent': None,
            'voltage_v': None, 'current_ma': None, 'current_source': None,
            'current_derived_from_real': False, 'charge_discharge_rate_w': None,
            'power_plugged': None, 'estimated_seconds_left': None,
            'sources': [presence.get('source')] if presence.get('source') else [],
            'presence_source': presence.get('source'), 'policy': 'REAL_OR_NA',
        }

    wmi = _wmi_battery_data() if platform.system() == 'Windows' else {}

    # El informe powercfg es comparativamente costoso. Sólo se ejecuta si las
    # fuentes ya consultadas no exponen capacidad de diseño/carga completa/ciclos.
    need_report = any(
        _first_num(live.get(key), wmi.get(key)) is None
        for key in ('designed_capacity_mwh', 'full_charge_capacity_mwh')
    )
    report = _powercfg_battery_report() if need_report else {}

    design = _first_num(live.get('designed_capacity_mwh'), wmi.get('designed_capacity_mwh'), report.get('designed_capacity_mwh'))
    full = _first_num(live.get('full_charge_capacity_mwh'), wmi.get('full_charge_capacity_mwh'), report.get('full_charge_capacity_mwh'))
    remaining = _first_num(live.get('remaining_capacity_mwh'), wmi.get('remaining_capacity_mwh'))
    health = (full / design * 100.0) if design is not None and design > 0 and full is not None and full >= 0 else None
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

    present = True if (live or wmi.get('detected') or report.get('detected') or pbat is not None or presence.get('present') is True) else False if presence.get('resolved') and presence.get('present') is False else None
    live_current = _num(live.get('current_ma'))
    wmi_current = _num(wmi.get('current_ma_derived'))
    current_ma = live_current if live_current is not None else wmi_current
    current_source = None
    current_derived = False
    if live_current is not None:
        current_source = 'LibreHardwareMonitor · sensor Current'
    elif wmi_current is not None:
        current_source = 'Windows WMI · Rate/Voltage'
        current_derived = True
    return {
        'present': present,
        'health_percent': health,
        'degradation_percent': degradation,
        'designed_capacity_mwh': design,
        'full_charge_capacity_mwh': full,
        'remaining_capacity_mwh': remaining,
        'cycle_count': _first_num(live.get('cycle_count'), wmi.get('cycle_count'), report.get('cycle_count')),
        'charge_percent': charge,
        'voltage_v': _first_num(live.get('voltage_v'), wmi.get('voltage_v')),
        'current_ma': current_ma,
        'current_source': current_source,
        'current_derived_from_real': current_derived,
        'charge_discharge_rate_w': _first_num(live.get('charge_discharge_rate_w'), wmi.get('charge_discharge_rate_w')),
        'power_plugged': plugged,
        'estimated_seconds_left': secs,
        'sources': [src for src in ('LibreHardwareMonitor' if live else None, wmi.get('source'), report.get('source'), 'psutil.sensors_battery' if pbat is not None else None) if src],
        'presence_source': presence.get('source'),
        'policy': 'REAL_OR_NA',
    }

