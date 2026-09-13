"""Comprueba que el entorno de Windows dispone de los componentes necesarios para ejecutar CorePulse."""
from __future__ import annotations
# Código refactorizado: nombres estables y documentación en español.
import ctypes
import importlib
import os
import platform
import shutil
import struct
import subprocess
import sys
import winreg
from pathlib import Path
TITLE = 'COMPROBACIÓN DE REQUISITOS DE COREPULSE'
ROOT = Path(__file__).resolve().parents[1]
PASS = '[PASS]'
WARN = '[WARN]'
FAIL = '[FAIL]'
INFO = '[INFO]'
results = []

def record(level: str, name: str, detail: str=''):
    results.append((level, name, detail))
    print(f'{level:<6} {name}')
    if detail:
        print(f'       {detail}')

def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False

def check_python():
    ver = sys.version_info
    bits = struct.calcsize('P') * 8
    if ver.major == 3 and ver.minor >= 12:
        record(PASS, 'Python 3.12+', f'{platform.python_version()} (sin limite superior artificial)')
    else:
        record(FAIL, 'Version de Python', f'{platform.python_version()} (se requiere Python 3.12 o superior)')
    if bits == 64:
        record(PASS, 'Python x64', f'{bits}-bit')
    else:
        record(FAIL, 'Python x64', f'Python actual es {bits}-bit')
    record(INFO, 'Ejecutable Python', sys.executable)

def check_windows():
    if platform.system() == 'Windows':
        record(PASS, 'Windows', f'{platform.system()} {platform.release()} ({platform.version()})')
    else:
        record(FAIL, 'Windows', f'Sistema detectado: {platform.system()}')

def check_admin():
    if is_admin():
        record(PASS, 'Permisos de administrador', 'Proceso elevado.')
    else:
        record(WARN, 'Permisos de administrador', 'No elevado. CorePulse puede funcionar, pero sensores profundos/ETW pueden requerir Administrador.')

def check_module(import_name: str, pip_name: str | None=None):
    pip_name = pip_name or import_name
    try:
        mod = importlib.import_module(import_name)
        version = getattr(mod, '__version__', None)
        detail = f"Import OK{(f' | version {version}' if version else '')}"
        record(PASS, f'Python: {pip_name}', detail)
        return True
    except Exception as exc:
        record(FAIL, f'Python: {pip_name}', f'{type(exc).__name__}: {exc} | Instalar: python -m pip install {pip_name}')
        return False

def check_python_packages():
    packages = [('psutil', 'psutil'), ('platformdirs', 'platformdirs'), ('send2trash', 'send2trash'), ('groq', 'groq'), ('dotenv', 'python-dotenv'), ('customtkinter', 'customtkinter'), ('PIL', 'Pillow'), ('matplotlib', 'matplotlib'), ('reportlab', 'reportlab'), ('wmi', 'wmi'), ('win32api', 'pywin32'), ('pythoncom', 'pywin32'), ('clr', 'pythonnet'), ('pystray', 'pystray')]
    return {pip: check_module(imp, pip) for imp, pip in packages}

def check_hardwaremonitor():
    try:
        from HardwareMonitor.Hardware import Computer
        record(PASS, 'HardwareMonitor / LibreHardwareMonitorLib', 'Import correcto.')
        try:
            c = Computer()
            for attr in ('IsCpuEnabled', 'IsGpuEnabled', 'IsMemoryEnabled', 'IsMotherboardEnabled', 'IsStorageEnabled'):
                if hasattr(c, attr):
                    setattr(c, attr, True)
            c.Open()
            record(PASS, 'LibreHardwareMonitor Open()', 'La biblioteca abrió correctamente.')
            try:
                c.Close()
            except Exception:
                pass
        except Exception as exc:
            record(WARN, 'LibreHardwareMonitor Open()', f'{type(exc).__name__}: {exc} | Revisar .NET, PawnIO y permisos.')
    except Exception as exc:
        record(WARN, 'HardwareMonitor', f'{type(exc).__name__}: {exc} | CorePulse puede arrancar, pero sensores profundos quedaran N/A. Ejecuta instalar_dependencias.bat para reintentar el stack opcional.')

def registry_display_names():
    roots = [(winreg.HKEY_LOCAL_MACHINE, 'SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall'), (winreg.HKEY_LOCAL_MACHINE, 'SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall'), (winreg.HKEY_CURRENT_USER, 'SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall')]
    entries = []
    for hive, path in roots:
        try:
            with winreg.OpenKey(hive, path) as key:
                count = winreg.QueryInfoKey(key)[0]
                for i in range(count):
                    try:
                        subname = winreg.EnumKey(key, i)
                        with winreg.OpenKey(key, subname) as sub:
                            try:
                                name = winreg.QueryValueEx(sub, 'DisplayName')[0]
                            except OSError:
                                name = ''
                            try:
                                version = winreg.QueryValueEx(sub, 'DisplayVersion')[0]
                            except OSError:
                                version = ''
                            if name:
                                entries.append((str(name), str(version)))
                    except OSError:
                        continue
        except OSError:
            continue
    return entries

def check_pawnio(entries):
    found = [(n, v) for n, v in entries if 'pawnio' in n.lower()]
    if found:
        text = '; '.join((f'{n} {v}'.strip() for n, v in found))
        record(PASS, 'PawnIO', text)
        return
    candidates = [Path(os.environ.get('WINDIR', 'C:\\Windows')) / 'System32' / 'drivers' / 'PawnIO.sys']
    existing = [str(p) for p in candidates if p.exists()]
    if existing:
        record(PASS, 'PawnIO', f'Driver encontrado: {existing[0]}')
    else:
        record(WARN, 'PawnIO', "No se detectó en aplicaciones instaladas ni en la ruta de driver esperada. Ejecuta 'winget search PawnIO' y verifica la instalación oficial.")

def check_rtss(entries):
    found = [(n, v) for n, v in entries if 'rivatuner statistics server' in n.lower()]
    common = [Path(os.environ.get('ProgramFiles(x86)', '')) / 'RivaTuner Statistics Server' / 'RTSS.exe', Path(os.environ.get('ProgramFiles', '')) / 'RivaTuner Statistics Server' / 'RTSS.exe']
    exe = next((p for p in common if str(p) and p.exists()), None)
    if found or exe:
        detail_parts = []
        if found:
            detail_parts.append('; '.join((f'{n} {v}'.strip() for n, v in found)))
        if exe:
            detail_parts.append(str(exe))
        record(PASS, 'RivaTuner Statistics Server (RTSS)', ' | '.join(detail_parts))
    else:
        record(WARN, 'RivaTuner Statistics Server (RTSS)', 'No detectado. Es necesario para el Overlay In-Game/RTSS Shared Memory.')
    running = False
    try:
        out = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq RTSS.exe'], capture_output=True, text=True, errors='ignore', timeout=5).stdout.lower()
        running = 'rtss.exe' in out
    except Exception:
        pass
    if running:
        record(PASS, 'RTSS ejecutándose', 'RTSS.exe está activo.')
    else:
        record(WARN, 'RTSS ejecutándose', 'RTSS.exe no está activo. Ábrelo antes de probar el overlay/FPS.')

def check_presentmon():
    paths = [ROOT / 'tools' / 'presentmon' / 'PresentMon.exe', ROOT / 'tools' / 'PresentMon.exe', ROOT / 'PresentMon.exe']
    found = next((p for p in paths if p.exists()), None)
    if found:
        record(PASS, 'PresentMon.exe', str(found.relative_to(ROOT)))
    else:
        record(WARN, 'PresentMon.exe', 'No encontrado en tools\\presentmon\\PresentMon.exe. Revisar el paquete de CorePulse.')

def check_dotnet():
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 'SOFTWARE\\Microsoft\\NET Framework Setup\\NDP\\v4\\Full') as key:
            release = winreg.QueryValueEx(key, 'Release')[0]
            if int(release) >= 528040:
                record(PASS, '.NET Framework 4.8+', f'Release={release}')
            else:
                record(WARN, '.NET Framework 4.x', f'Release={release}. Se recomienda .NET Framework 4.8 o superior compatible.')
            return
    except Exception:
        pass
    record(WARN, '.NET Framework 4.x', 'No se pudo confirmar mediante el registro. pythonnet/HardwareMonitor serán la prueba funcional principal.')

def check_project_files():
    required = [ROOT / 'main.py', ROOT / 'core']
    for p in required:
        if p.exists():
            record(PASS, f'Proyecto: {p.name}', str(p))
        else:
            record(FAIL, f'Proyecto: {p.name}', f'No encontrado en {ROOT}')
    archivos_clave = [
        ROOT / 'core' / 'telemetry.py',
        ROOT / 'core' / 'report_generator.py',
        ROOT / 'gui' / 'dashboard.py',
        ROOT / 'database' / 'telemetry_repository.py',
    ]
    for archivo in archivos_clave:
        if archivo.exists():
            record(PASS, f'Módulo: {archivo.name}', str(archivo.relative_to(ROOT)))
        else:
            record(FAIL, f'Módulo: {archivo.name}', f'No encontrado: {archivo.relative_to(ROOT)}')

def print_summary():
    print('\n' + '=' * 86)
    print('RESUMEN')
    print('=' * 86)
    passes = sum((1 for x in results if x[0] == PASS))
    warns = sum((1 for x in results if x[0] == WARN))
    fails = sum((1 for x in results if x[0] == FAIL))
    print(f'PASS : {passes}')
    print(f'WARN : {warns}')
    print(f'FAIL : {fails}')
    if fails:
        print('\nESTADO: FALTAN REQUISITOS O HAY ERRORES QUE DEBEN CORREGIRSE.')
    elif warns:
        print('\nESTADO: COREPULSE PUEDE ESTAR OPERATIVO, PERO HAY ELEMENTOS QUE DEBEN REVISARSE.')
    else:
        print('\nESTADO: REQUISITOS PRINCIPALES DETECTADOS CORRECTAMENTE.')
    print('\nIMPORTANTE:')
    print('- PASS no garantiza que un hardware específico exponga todos sus sensores.')
    print('- WARN no significa necesariamente fallo; puede indicar RTSS cerrado o permisos limitados.')
    print('- CorePulse debe mostrar N/A cuando no exista una fuente real.')
    print('- Este script NO instala, modifica ni desactiva nada en Windows.')

def main():
    print('=' * 86)
    print(TITLE)
    print('=' * 86)
    print(f'Carpeta: {ROOT}\n')
    check_windows()
    check_python()
    check_admin()
    print('\n--- DEPENDENCIAS PYTHON ---')
    check_python_packages()
    print('\n--- .NET / SENSORES FÍSICOS ---')
    check_dotnet()
    check_hardwaremonitor()
    print('\n--- COMPONENTES EXTERNOS ---')
    entries = registry_display_names()
    check_pawnio(entries)
    check_rtss(entries)
    check_presentmon()
    print('\n--- PROYECTO COREPULSE ---')
    check_project_files()
    print_summary()
if __name__ == '__main__':
    main()
