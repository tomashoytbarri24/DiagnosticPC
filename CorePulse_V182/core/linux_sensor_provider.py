"""Proveedor nativo de sensores para Linux.

Mantiene el mismo contrato de sensores que LibreHardwareMonitor para que las
capas superiores de CorePulse puedan reutilizar la UI y la lógica REAL_OR_NA.
No inventa métricas: cada fila conserva la fuente real utilizada.
"""
from __future__ import annotations

import os
import platform
from pathlib import Path
import re
import shutil
import subprocess
import threading
import time

import psutil


def _read_text(path: Path) -> str | None:
    try:
        value = path.read_text(encoding="utf-8", errors="replace").strip()
        return value or None
    except Exception:
        return None


def _read_number(path: Path, scale: float = 1.0) -> float | None:
    raw = _read_text(path)
    if raw is None:
        return None
    try:
        return float(raw) / float(scale)
    except Exception:
        return None


def _cpu_model() -> str:
    try:
        lines = Path('/proc/cpuinfo').read_text(encoding='utf-8', errors='replace').splitlines()
        pairs = []
        for line in lines:
            if ':' not in line:
                continue
            key, value = line.split(':', 1)
            pairs.append((key.strip().casefold(), value.strip()))
        for wanted in ('model name', 'hardware'):
            for key, value in pairs:
                if key == wanted and value:
                    return value
        for key, value in pairs:
            if key == 'processor' and value and not value.isdecimal():
                return value
    except Exception:
        pass
    return platform.processor() or 'CPU'


def _run(args: list[str], timeout: float = 2.5) -> str:
    try:
        cp = subprocess.run(args, capture_output=True, text=True, errors='replace', timeout=timeout)
        return (cp.stdout or '').strip() if cp.returncode == 0 else ''
    except Exception:
        return ''


def _sensor(hardware_name: str, hardware_type: str, name: str, sensor_type: str,
            value: float | int | None, source: str, identifier: str = '') -> dict | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except Exception:
        return None
    return {
        'hardware_name': hardware_name,
        'hardware_type': hardware_type,
        'sensor_name': name,
        'sensor_type': sensor_type,
        'value': number,
        'identifier': identifier,
        'timestamp': time.time(),
        'source': source,
    }


def _hwmon_temperatures(cpu_name: str) -> list[dict]:
    rows: list[dict] = []
    try:
        temperatures = psutil.sensors_temperatures(fahrenheit=False) or {}
    except Exception:
        temperatures = {}
    cpu_keys = ('coretemp', 'k10temp', 'zenpower', 'cpu_thermal', 'acpitz')
    for chip, entries in temperatures.items():
        chip_l = str(chip).casefold()
        if not any(key in chip_l for key in cpu_keys):
            continue
        for index, entry in enumerate(entries or []):
            current = getattr(entry, 'current', None)
            try:
                current = float(current)
            except Exception:
                continue
            if not -20.0 <= current <= 150.0:
                continue
            label = str(getattr(entry, 'label', '') or '').strip() or f'Temperature #{index + 1}'
            low = label.casefold()
            if ('package' in low or 'tctl' in low or 'tdie' in low):
                sensor_name = 'CPU Package'
            elif 'core' in low:
                sensor_name = label
            else:
                sensor_name = label
            row = _sensor(cpu_name, 'Cpu', sensor_name, 'Temperature', current,
                          f'Linux hwmon/psutil:{chip}', f'hwmon:{chip}:{index}')
            if row:
                rows.append(row)
    return rows


def _cpu_sensors() -> list[dict]:
    name = _cpu_model()
    rows = _hwmon_temperatures(name)
    try:
        freqs = psutil.cpu_freq(percpu=True) or []
    except Exception:
        freqs = []
    for index, freq in enumerate(freqs):
        value = getattr(freq, 'current', None)
        row = _sensor(name, 'Cpu', f'CPU Core #{index + 1}', 'Clock', value,
                      'psutil.cpu_freq', f'cpu:{index}:clock')
        if row:
            rows.append(row)
    try:
        per_core = psutil.cpu_percent(interval=None, percpu=True) or []
        total = psutil.cpu_percent(interval=None)
    except Exception:
        per_core, total = [], None
    row = _sensor(name, 'Cpu', 'CPU Total', 'Load', total, 'psutil.cpu_percent', 'cpu:total:load')
    if row:
        rows.append(row)
    for index, value in enumerate(per_core):
        row = _sensor(name, 'Cpu', f'CPU Core #{index + 1}', 'Load', value,
                      'psutil.cpu_percent', f'cpu:{index}:load')
        if row:
            rows.append(row)
    return rows


def _nvidia_sensors() -> list[dict]:
    if not shutil.which('nvidia-smi'):
        return []
    query = (
        'name,utilization.gpu,temperature.gpu,clocks.gr,clocks.mem,'
        'memory.total,memory.used,power.draw'
    )
    output = _run(['nvidia-smi', f'--query-gpu={query}', '--format=csv,noheader,nounits'], timeout=3.0)
    if not output:
        return []
    rows: list[dict] = []
    for gpu_index, line in enumerate(output.splitlines()):
        parts = [p.strip() for p in line.split(',')]
        if len(parts) < 8:
            continue
        name = parts[0] or f'NVIDIA GPU {gpu_index}'
        values: list[float | None] = []
        for raw in parts[1:]:
            try:
                values.append(float(raw))
            except Exception:
                values.append(None)
        usage, temp, core_clock, mem_clock, mem_total, mem_used, power = values
        specs = (
            ('GPU Core', 'Load', usage, 'utilization.gpu'),
            ('GPU Core', 'Temperature', temp, 'temperature.gpu'),
            ('GPU Core', 'Clock', core_clock, 'clocks.gr'),
            ('GPU Memory', 'Clock', mem_clock, 'clocks.mem'),
            ('GPU Memory Total', 'SmallData', mem_total, 'memory.total'),
            ('GPU Memory Used', 'SmallData', mem_used, 'memory.used'),
            ('GPU Power', 'Power', power, 'power.draw'),
        )
        for sensor_name, sensor_type, value, ident in specs:
            row = _sensor(name, 'GpuNvidia', sensor_name, sensor_type, value,
                          'nvidia-smi', f'nvidia:{gpu_index}:{ident}')
            if row:
                rows.append(row)
    return rows


def _drm_gpu_name(card: Path) -> tuple[str, str]:
    device = card / 'device'
    vendor = (_read_text(device / 'vendor') or '').casefold()
    vendor_name = {'0x1002': 'AMD', '0x8086': 'Intel', '0x10de': 'NVIDIA'}.get(vendor, 'GPU')
    uevent = _read_text(device / 'uevent') or ''
    pci_id = ''
    driver = ''
    for line in uevent.splitlines():
        if line.startswith('PCI_ID='):
            pci_id = line.split('=', 1)[1]
        elif line.startswith('DRIVER='):
            driver = line.split('=', 1)[1]
    label = ' '.join(x for x in (vendor_name, driver.upper() if driver else None, pci_id or None) if x)
    hw_type = 'GpuAmd' if vendor == '0x1002' else 'GpuIntel' if vendor == '0x8086' else 'GpuNvidia' if vendor == '0x10de' else 'Gpu'
    return label or card.name, hw_type


def _drm_sensors() -> list[dict]:
    rows: list[dict] = []
    drm_root = Path('/sys/class/drm')
    if not drm_root.is_dir():
        return rows
    for card in sorted(drm_root.glob('card[0-9]*')):
        device = card / 'device'
        if not device.exists():
            continue
        name, hw_type = _drm_gpu_name(card)
        # NVIDIA ya se obtiene de nvidia-smi con datos más completos.
        if hw_type == 'GpuNvidia' and shutil.which('nvidia-smi'):
            continue
        busy = _read_number(device / 'gpu_busy_percent')
        row = _sensor(name, hw_type, 'GPU Core', 'Load', busy, 'Linux DRM sysfs', f'{card.name}:busy')
        if row:
            rows.append(row)
        total_b = _read_number(device / 'mem_info_vram_total')
        used_b = _read_number(device / 'mem_info_vram_used')
        if total_b is not None:
            row = _sensor(name, hw_type, 'GPU Memory Total', 'SmallData', total_b / (1024 ** 2),
                          'Linux DRM sysfs', f'{card.name}:vram_total')
            if row: rows.append(row)
        if used_b is not None:
            row = _sensor(name, hw_type, 'GPU Memory Used', 'SmallData', used_b / (1024 ** 2),
                          'Linux DRM sysfs', f'{card.name}:vram_used')
            if row: rows.append(row)
        for hwmon in device.glob('hwmon/hwmon*'):
            temp = _read_number(hwmon / 'temp1_input', 1000.0)
            row = _sensor(name, hw_type, 'GPU Core', 'Temperature', temp,
                          'Linux DRM hwmon', f'{card.name}:temp1')
            if row:
                rows.append(row)
                break
    return rows


def _battery_sensors() -> list[dict]:
    root = Path('/sys/class/power_supply')
    if not root.is_dir():
        return []
    rows: list[dict] = []
    for bat in sorted(root.glob('BAT*')):
        if (_read_text(bat / 'type') or 'Battery').casefold() != 'battery':
            continue
        name = _read_text(bat / 'model_name') or bat.name
        # Linux power_supply usually exposes energy in uWh and voltage/current in uV/uA.
        design = _read_number(bat / 'energy_full_design', 1000.0)
        full = _read_number(bat / 'energy_full', 1000.0)
        remaining = _read_number(bat / 'energy_now', 1000.0)
        if design is None:
            charge_design_ah = _read_number(bat / 'charge_full_design', 1_000_000.0)
            voltage_v = _read_number(bat / 'voltage_now', 1_000_000.0)
            if charge_design_ah is not None and voltage_v is not None:
                design = charge_design_ah * voltage_v * 1000.0
        if full is None:
            charge_full_ah = _read_number(bat / 'charge_full', 1_000_000.0)
            voltage_v = _read_number(bat / 'voltage_now', 1_000_000.0)
            if charge_full_ah is not None and voltage_v is not None:
                full = charge_full_ah * voltage_v * 1000.0
        if remaining is None:
            charge_now_ah = _read_number(bat / 'charge_now', 1_000_000.0)
            voltage_v = _read_number(bat / 'voltage_now', 1_000_000.0)
            if charge_now_ah is not None and voltage_v is not None:
                remaining = charge_now_ah * voltage_v * 1000.0
        capacity = _read_number(bat / 'capacity')
        voltage = _read_number(bat / 'voltage_now', 1_000_000.0)
        current = _read_number(bat / 'current_now', 1_000_000.0)  # A
        power = _read_number(bat / 'power_now', 1_000_000.0)      # W
        status = (_read_text(bat / 'status') or '').casefold()
        sign = 1.0 if status == 'charging' else -1.0 if status == 'discharging' else 1.0
        if current is not None:
            current *= sign
        if power is not None:
            power *= sign
        degradation = None
        if design and full is not None and design > 0:
            degradation = max(0.0, min(100.0, 100.0 - (full / design * 100.0)))
        specs = (
            ('Designed Capacity', 'Energy', design, 'energy_full_design'),
            ('Fully-Charged Capacity', 'Energy', full, 'energy_full'),
            ('Remaining Capacity', 'Energy', remaining, 'energy_now'),
            ('Degradation Level', 'Level', degradation, 'degradation'),
            ('Charge Level', 'Level', capacity, 'capacity'),
            ('Voltage', 'Voltage', voltage, 'voltage_now'),
            ('Charge/Discharge Current', 'Current', current, 'current_now'),
            ('Charge/Discharge Rate', 'Power', power, 'power_now'),
        )
        for sensor_name, sensor_type, value, ident in specs:
            row = _sensor(name, 'Battery', sensor_name, sensor_type, value,
                          'Linux power_supply sysfs', f'{bat.name}:{ident}')
            if row:
                rows.append(row)
    return rows


class LinuxSensorProvider:
    name = 'Linux native sensors'

    def __init__(self):
        self._lock = threading.RLock()
        self._last_refresh = 0.0
        self._sensors: list[dict] = []
        self._error: str | None = None
        self._available = True
        try:
            psutil.cpu_percent(interval=None)
        except Exception:
            pass

    @property
    def available(self):
        return self._available

    @property
    def error(self):
        return self._error

    def refresh(self, min_interval=0.35):
        with self._lock:
            now = time.monotonic()
            if self._sensors and now - self._last_refresh < min_interval:
                return list(self._sensors)
            try:
                sensors = []
                sensors.extend(_cpu_sensors())
                sensors.extend(_nvidia_sensors())
                sensors.extend(_drm_sensors())
                sensors.extend(_battery_sensors())
                self._sensors = sensors
                self._last_refresh = now
                self._available = True
                self._error = None
            except Exception as exc:
                self._error = f'{type(exc).__name__}: {exc}'
            return list(self._sensors)

    def all_sensors(self):
        return self.refresh()

    def _temperatures(self, hardware_types):
        wanted = {str(x).casefold() for x in hardware_types}
        return [s for s in self.refresh() if str(s.get('sensor_type')).casefold() == 'temperature'
                and str(s.get('hardware_type')).casefold() in wanted]

    def cpu_temperature(self):
        candidates = self._temperatures({'Cpu'})
        if not candidates:
            return None
        preferred = [s for s in candidates if any(k in str(s.get('sensor_name')).casefold() for k in ('package', 'tctl', 'tdie'))]
        chosen = max(preferred or candidates, key=lambda row: float(row.get('value') or -999))
        return {'value': round(float(chosen['value']), 1), 'source': chosen.get('source'),
                'sensor': chosen.get('sensor_name'), 'hardware': chosen.get('hardware_name')}

    def gpu_temperature(self):
        candidates = [s for s in self.refresh() if str(s.get('hardware_type', '')).casefold().startswith('gpu')
                      and str(s.get('sensor_type')).casefold() == 'temperature']
        if not candidates:
            return None
        chosen = max(candidates, key=lambda row: float(row.get('value') or -999))
        return {'value': round(float(chosen['value']), 1), 'source': chosen.get('source'),
                'sensor': chosen.get('sensor_name'), 'hardware': chosen.get('hardware_name')}

    def gpu_load(self):
        candidates = [s for s in self.refresh() if str(s.get('hardware_type', '')).casefold().startswith('gpu')
                      and str(s.get('sensor_type')).casefold() == 'load']
        if not candidates:
            return None
        chosen = max(candidates, key=lambda row: float(row.get('value') or -1))
        return {'value': round(float(chosen['value']), 1), 'source': chosen.get('source'),
                'sensor': chosen.get('sensor_name'), 'hardware': chosen.get('hardware_name')}

    def storage_temperatures(self):
        return []

    def close(self):
        return None
