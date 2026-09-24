"""Implementa acciones seguras de optimización de memoria sin simular resultados."""
from __future__ import annotations
# Código refactorizado: nombres estables y documentación en español.
import ctypes, gc, os, platform, statistics, time
from dataclasses import dataclass, asdict
from typing import Callable
import psutil
ENGINE_VERSION = '0.10.2.96w'
POLICY = 'SAFE_RECLAIM_ONLY'
DEEP_POLICY = 'WINDOWS_DEEP_RECLAIM_MEMREDUCT_STYLE_MEASURED'
IS_WINDOWS = platform.system() == 'Windows'

@dataclass
class MemorySnapshot:
    timestamp: float
    total_bytes: int
    available_bytes: int
    used_bytes: int
    used_percent: float

@dataclass
class RAMOptimizationResult:
    version: str
    policy: str
    success: bool
    before: dict
    after: dict
    available_delta_bytes: int
    measured_recovered_bytes: int
    measured_recovered_mb: float
    used_percent_delta: float
    gc_objects_collected: int
    cache_callbacks_run: int
    cache_callback_errors: list
    external_processes_modified: int
    working_sets_trimmed: int
    target_percent: None
    message: str

    def to_dict(self):
        return asdict(self)
_CACHE_CLEAR_CALLBACKS = []

def register_safe_cache_clearer(callback: Callable[[], object]) -> None:
    if not callable(callback):
        raise TypeError('callback must be callable')
    if callback not in _CACHE_CLEAR_CALLBACKS:
        _CACHE_CLEAR_CALLBACKS.append(callback)

def unregister_safe_cache_clearer(callback):
    try:
        _CACHE_CLEAR_CALLBACKS.remove(callback)
    except ValueError:
        pass

def _snapshot_once():
    vm = psutil.virtual_memory()
    return MemorySnapshot(time.time(), int(vm.total), int(vm.available), int(vm.used), float(vm.percent))

def _stable_snapshot(samples=3, interval=0.12):
    samples = max(1, min(int(samples), 9))
    pts = []
    for i in range(samples):
        pts.append(_snapshot_once())
        if i + 1 < samples:
            time.sleep(max(0.0, interval))
    return MemorySnapshot(pts[-1].timestamp, int(statistics.median((x.total_bytes for x in pts))), int(statistics.median((x.available_bytes for x in pts))), int(statistics.median((x.used_bytes for x in pts))), float(statistics.median((x.used_percent for x in pts))))

def is_administrator():
    if not IS_WINDOWS:
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False

def analyze_ram():
    snap = _stable_snapshot()
    proc = psutil.Process(os.getpid())
    try:
        rss = int(proc.memory_info().rss)
    except Exception:
        rss = 0
    return {'version': ENGINE_VERSION, 'policy': POLICY, 'snapshot': asdict(snap), 'corepulse_process_rss_bytes': rss, 'corepulse_process_rss_mb': round(rss / 1024 ** 2, 2), 'administrator': is_administrator(), 'deep_cleanup_available': bool(IS_WINDOWS and is_administrator()), 'target_percent': None}

def optimize_ram_safely(*, settle_seconds=0.35, snapshot_samples=3, run_registered_cache_clearers=True):
    before = _stable_snapshot(snapshot_samples)
    errors = []
    callbacks = 0
    if run_registered_cache_clearers:
        for cb in tuple(_CACHE_CLEAR_CALLBACKS):
            callbacks += 1
            try:
                cb()
            except Exception as exc:
                errors.append(f"{getattr(cb, '__name__', repr(cb))}: {type(exc).__name__}: {exc}")
    try:
        collected = int(gc.collect())
    except Exception:
        collected = 0
    time.sleep(max(0.0, settle_seconds))
    after = _stable_snapshot(snapshot_samples)
    delta = int(after.available_bytes - before.available_bytes)
    recovered = max(0, delta)
    msg = f'Optimización normal completada: {recovered / 1024 ** 2:.1f} MB adicionales medidos.' if recovered > 0 else 'Optimización normal completada. No hubo memoria adicional recuperada de forma medible.'
    return RAMOptimizationResult(ENGINE_VERSION, POLICY, True, asdict(before), asdict(after), delta, recovered, round(recovered / 1024 ** 2, 2), round(before.used_percent - after.used_percent, 3), collected, callbacks, errors, 0, 0, None, msg).to_dict()
TOKEN_ADJUST_PRIVILEGES = 32
TOKEN_QUERY = 8
SE_PRIVILEGE_ENABLED = 2
PROCESS_SET_QUOTA = 256
PROCESS_QUERY_INFORMATION = 1024
SYSTEM_MEMORY_LIST_INFORMATION = 80
MEMORY_EMPTY_WORKING_SETS = 2
MEMORY_FLUSH_MODIFIED_LIST = 3
MEMORY_PURGE_STANDBY_LIST = 4
MEMORY_PURGE_LOW_PRIORITY_STANDBY_LIST = 5

class LUID(ctypes.Structure):
    _fields_ = [('LowPart', ctypes.c_uint32), ('HighPart', ctypes.c_long)]

class LUID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [('Luid', LUID), ('Attributes', ctypes.c_uint32)]

class TOKEN_PRIVILEGES(ctypes.Structure):
    _fields_ = [('PrivilegeCount', ctypes.c_uint32), ('Privileges', LUID_AND_ATTRIBUTES * 1)]

def _enable_privilege(name):
    if not IS_WINDOWS:
        return False
    advapi = ctypes.windll.advapi32
    kernel = ctypes.windll.kernel32
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    advapi.OpenProcessToken.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p)]
    token = ctypes.c_void_p()
    if not advapi.OpenProcessToken(kernel.GetCurrentProcess(), TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY, ctypes.byref(token)):
        return False
    try:
        luid = LUID()
        if not advapi.LookupPrivilegeValueW(None, name, ctypes.byref(luid)):
            return False
        tp = TOKEN_PRIVILEGES()
        tp.PrivilegeCount = 1
        tp.Privileges[0].Luid = luid
        tp.Privileges[0].Attributes = SE_PRIVILEGE_ENABLED
        kernel.SetLastError(0)
        advapi.AdjustTokenPrivileges(token, False, ctypes.byref(tp), 0, None, None)
        return kernel.GetLastError() == 0
    finally:
        kernel.CloseHandle(token)

def _trim_working_sets():
    if not IS_WINDOWS:
        return (0, 0, 0)
    kernel = ctypes.windll.kernel32
    psapi = ctypes.windll.psapi
    kernel.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel.CloseHandle.restype = ctypes.c_int
    psapi.EmptyWorkingSet.argtypes = [ctypes.c_void_p]
    psapi.EmptyWorkingSet.restype = ctypes.c_int
    trimmed = 0
    failed = 0
    external = 0
    current = os.getpid()
    for proc in psutil.process_iter(['pid']):
        pid = int(proc.info.get('pid') or 0)
        if pid in (0, 4):
            continue
        handle = kernel.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_SET_QUOTA, False, pid)
        if not handle:
            failed += 1
            continue
        try:
            if psapi.EmptyWorkingSet(handle):
                trimmed += 1
                if pid != current:
                    external += 1
            else:
                failed += 1
        except Exception:
            failed += 1
        finally:
            kernel.CloseHandle(handle)
    return (trimmed, failed, external)

def _memory_list_command(command_value):
    """Solicita a Windows una operación concreta sobre sus listas de memoria.

    SystemMemoryListInformation es una Native API no documentada públicamente
    como contrato estable. Por eso cada operación se trata como capacidad
    opcional: si Windows la rechaza, CorePulse lo registra y continúa sin
    simular que la limpieza ocurrió.
    """
    if not IS_WINDOWS:
        return (False, None)
    try:
        privilege = _enable_privilege('SeProfileSingleProcessPrivilege')
        command = ctypes.c_ulong(int(command_value))
        ntdll = ctypes.windll.ntdll
        fn = ntdll.NtSetSystemInformation
        fn.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_ulong]
        fn.restype = ctypes.c_long
        status = int(fn(SYSTEM_MEMORY_LIST_INFORMATION, ctypes.byref(command), ctypes.sizeof(command)))
        return (status == 0, {'ntstatus': status, 'privilege_enabled': bool(privilege), 'command': int(command_value)})
    except Exception as exc:
        return (False, {'error': f'{type(exc).__name__}: {exc}', 'command': int(command_value)})

def _empty_system_working_sets():
    return _memory_list_command(MEMORY_EMPTY_WORKING_SETS)

def _flush_modified_page_list():
    return _memory_list_command(MEMORY_FLUSH_MODIFIED_LIST)

def _purge_standby_list():
    return _memory_list_command(MEMORY_PURGE_STANDBY_LIST)

def _purge_low_priority_standby_list():
    return _memory_list_command(MEMORY_PURGE_LOW_PRIORITY_STANDBY_LIST)

def _flush_system_file_cache():
    """Solicita a Windows vaciar el file-system cache mediante API Win32.

    Microsoft documenta que SetSystemFileCacheSize(-1, -1, 0) vacía la caché
    y requiere SeIncreaseQuotaPrivilege. No deja límites persistentes: sólo
    solicita el flush y Windows vuelve a administrar la caché normalmente.
    """
    if not IS_WINDOWS:
        return (False, None)
    try:
        privilege = _enable_privilege('SeIncreaseQuotaPrivilege')
        kernel = ctypes.windll.kernel32
        fn = kernel.SetSystemFileCacheSize
        fn.argtypes = [ctypes.c_size_t, ctypes.c_size_t, ctypes.c_uint32]
        fn.restype = ctypes.c_int
        kernel.SetLastError(0)
        minus_one = ctypes.c_size_t(-1).value
        ok = bool(fn(minus_one, minus_one, 0))
        err = int(kernel.GetLastError()) if not ok else 0
        return (ok, {'winerror': err, 'privilege_enabled': bool(privilege)})
    except Exception as exc:
        return (False, {'error': f'{type(exc).__name__}: {exc}'})

def optimize_ram_deep(*, settle_seconds=1.15, snapshot_samples=5, purge_standby=True):
    """Liberación profunda comparable en alcance a un memory cleaner dedicado.

    No persigue un porcentaje objetivo. Ejecuta únicamente mecanismos reales
    expuestos por Windows/Native API y después mide el cambio físico observado.
    """
    before = _stable_snapshot(snapshot_samples)
    empty_result = {
        'version': ENGINE_VERSION, 'policy': DEEP_POLICY, 'success': False,
        'before': asdict(before), 'after': asdict(before),
        'measured_recovered_bytes': 0, 'measured_recovered_mb': 0.0,
        'working_sets_trimmed': 0, 'external_processes_modified': 0,
        'administrator': False, 'target_percent': None,
    }
    if not IS_WINDOWS:
        return {**empty_result, 'message': 'La liberación profunda está disponible únicamente en Windows.'}
    if not is_administrator():
        return {**empty_result, 'message': 'La liberación profunda requiere ejecutar CorePulse como administrador.'}

    try:
        collected = int(gc.collect())
    except Exception:
        collected = 0

    # 1) Procesos accesibles: equivalente al trim de working sets.
    trimmed, failed, external_trimmed = _trim_working_sets()

    # 2) Regiones administradas globalmente por Windows. Cada una es best effort.
    system_ws_ok, system_ws_detail = _empty_system_working_sets()
    modified_ok, modified_detail = _flush_modified_page_list()
    file_cache_ok, file_cache_detail = _flush_system_file_cache()
    low_standby_ok, low_standby_detail = (False, None)
    standby_ok, standby_detail = (False, None)
    if purge_standby:
        # Primero la lista de baja prioridad y finalmente la lista standby completa.
        # Si una versión de Windows no admite una de ellas, la otra aún puede funcionar.
        low_standby_ok, low_standby_detail = _purge_low_priority_standby_list()
        standby_ok, standby_detail = _purge_standby_list()

    time.sleep(max(0.0, settle_seconds))
    after = _stable_snapshot(snapshot_samples)
    delta = int(after.available_bytes - before.available_bytes)
    recovered = max(0, delta)
    regions = {
        'process_working_sets': bool(trimmed > 0),
        'system_working_sets': bool(system_ws_ok),
        'modified_page_list': bool(modified_ok),
        'system_file_cache': bool(file_cache_ok),
        'low_priority_standby': bool(low_standby_ok) if purge_standby else None,
        'standby_list': bool(standby_ok) if purge_standby else None,
    }
    attempted = 4 + (2 if purge_standby else 0)
    completed = sum(1 for value in regions.values() if value is True)
    msg = (
        f'Liberación profunda completada: {recovered / 1024 ** 3:.2f} GB adicionales medidos.'
        if recovered > 0
        else 'Liberación profunda ejecutada. Windows no reportó memoria adicional recuperada de forma medible.'
    )
    return {
        'version': ENGINE_VERSION, 'policy': DEEP_POLICY, 'success': True,
        'before': asdict(before), 'after': asdict(after),
        'available_delta_bytes': delta, 'measured_recovered_bytes': recovered,
        'measured_recovered_mb': round(recovered / 1024 ** 2, 2),
        'measured_recovered_gb': round(recovered / 1024 ** 3, 3),
        'used_percent_delta': round(before.used_percent - after.used_percent, 3),
        'gc_objects_collected': collected, 'working_sets_trimmed': trimmed,
        'working_sets_failed': failed, 'external_processes_modified': external_trimmed,
        'system_working_sets_success': bool(system_ws_ok),
        'system_working_sets_detail': system_ws_detail,
        'modified_page_list_success': bool(modified_ok),
        'modified_page_list_detail': modified_detail,
        'system_file_cache_success': bool(file_cache_ok),
        'system_file_cache_detail': file_cache_detail,
        'low_priority_standby_success': bool(low_standby_ok),
        'low_priority_standby_detail': low_standby_detail,
        'standby_purge_attempted': bool(purge_standby),
        'standby_purge_success': bool(standby_ok), 'standby_purge_detail': standby_detail,
        'regions_attempted': attempted, 'regions_completed': completed,
        'regions': regions, 'administrator': True, 'target_percent': None,
        'message': msg,
    }


def purge_standby_for_game(*, settle_seconds=0.45, snapshot_samples=3):
    """Purga únicamente la lista standby para una sesión de juego.

    A diferencia de :func:`optimize_ram_deep`, esta ruta NO recorta working
    sets de procesos externos ni fuerza el file cache. Windows puede recuperar
    la lista standby por sí mismo; CorePulse sólo la purga una vez al iniciar
    una sesión Game Boost cuando el usuario lo tiene habilitado.
    """
    before = _stable_snapshot(snapshot_samples)
    base = {
        'version': ENGINE_VERSION,
        'policy': 'GAME_STANDBY_PURGE_ONLY',
        'before': asdict(before),
        'administrator': is_administrator(),
        'working_sets_trimmed': 0,
        'external_processes_modified': 0,
        'standby_purge_attempted': False,
        'standby_purge_success': False,
        'measured_recovered_bytes': 0,
        'measured_recovered_mb': 0.0,
    }
    if not IS_WINDOWS:
        return {**base, 'success': False, 'after': asdict(before), 'message': 'La limpieza standby para juegos sólo está disponible en Windows.'}
    if not is_administrator():
        return {**base, 'success': False, 'after': asdict(before), 'message': 'La limpieza de RAM standby requiere ejecutar CorePulse como administrador.'}
    ok, detail = _purge_standby_list()
    time.sleep(max(0.0, float(settle_seconds)))
    after = _stable_snapshot(snapshot_samples)
    delta = int(after.available_bytes - before.available_bytes)
    recovered = max(0, delta)
    if ok:
        message = (f'RAM standby purgada · {recovered / 1024 ** 2:.0f} MB adicionales medidos.'
                   if recovered > 0 else 'RAM standby purgada · Windows no reportó memoria adicional medible.')
    else:
        message = 'Windows no permitió purgar la RAM standby.'
    return {
        **base, 'success': bool(ok), 'after': asdict(after),
        'available_delta_bytes': delta,
        'measured_recovered_bytes': recovered,
        'measured_recovered_mb': round(recovered / 1024 ** 2, 1),
        'standby_purge_attempted': True, 'standby_purge_success': bool(ok),
        'standby_purge_detail': detail, 'message': message,
    }

def format_result_for_user(result):
    before = result.get('before') or {}
    after = result.get('after') or {}
    return f"Uso antes: {float(before.get('used_percent') or 0):.1f}%\nUso después: {float(after.get('used_percent') or 0):.1f}%\nRecuperado medido: {float(result.get('measured_recovered_mb') or 0):.1f} MB\n\n{result.get('message') or ''}"
