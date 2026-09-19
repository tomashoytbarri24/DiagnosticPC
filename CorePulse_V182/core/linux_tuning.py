"""Ajustes seguros y observables para Linux.

No aplica sysctl, governor ni cambios de kernel de forma automática. La única
acción de escritura expuesta es ``powerprofilesctl set`` cuando el sistema la
ofrece, porque usa la política/autorización del propio escritorio.
"""
from __future__ import annotations

import platform
import shutil
import subprocess
from pathlib import Path


def _run(args, timeout=4):
    try:
        cp = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
        return cp.returncode, (cp.stdout or '').strip(), (cp.stderr or '').strip()
    except Exception as exc:
        return 1, '', str(exc)


def _read(path):
    try:
        return Path(path).read_text(encoding='utf-8', errors='ignore').strip()
    except Exception:
        return ''


def collect_linux_tuning():
    if platform.system() != 'Linux':
        return {'supported': False, 'platform': platform.system()}

    tool = shutil.which('powerprofilesctl')
    profile = ''
    profiles = []
    if tool:
        rc, out, _err = _run([tool, 'get'])
        if rc == 0:
            profile = out.strip()
        rc, out, _err = _run([tool, 'list'])
        if rc == 0:
            for line in out.splitlines():
                text = line.strip().lstrip('*').strip()
                if ':' in text:
                    candidate = text.split(':', 1)[0].strip()
                    if candidate in {'power-saver', 'balanced', 'performance'} and candidate not in profiles:
                        profiles.append(candidate)

    governors = set()
    for path in Path('/sys/devices/system/cpu').glob('cpu[0-9]*/cpufreq/scaling_governor'):
        value = _read(path)
        if value:
            governors.add(value)

    swappiness = _read('/proc/sys/vm/swappiness')
    zram_devices = sorted(p.name for p in Path('/sys/block').glob('zram*')) if Path('/sys/block').exists() else []
    gamemode = bool(shutil.which('gamemoderun') or shutil.which('gamemoded'))

    return {
        'supported': True,
        'powerprofilesctl': bool(tool),
        'profile': profile or 'No disponible',
        'profiles': profiles,
        'governors': sorted(governors),
        'swappiness': swappiness or 'No disponible',
        'zram': zram_devices,
        'gamemode': gamemode,
    }


def set_power_profile(profile):
    if platform.system() != 'Linux':
        return False, 'Esta acción sólo está disponible en Linux.'
    profile = str(profile or '').strip()
    if profile not in {'power-saver', 'balanced', 'performance'}:
        return False, 'Perfil de energía no válido.'
    tool = shutil.which('powerprofilesctl')
    if not tool:
        return False, 'powerprofilesctl no está disponible en este sistema.'
    rc, _out, err = _run([tool, 'set', profile], timeout=8)
    if rc == 0:
        return True, profile
    return False, err or 'El sistema rechazó el cambio de perfil.'
