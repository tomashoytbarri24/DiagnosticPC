"""Implementa acciones seguras de optimización de memoria sin simular resultados."""
from __future__ import annotations
# Código refactorizado: nombres estables y documentación en español.
import ctypes, gc, os, platform, statistics, time
from dataclasses import dataclass, asdict
from typing import Callable
import psutil
ENGINE_VERSION = '0.9.18.11a'
POLICY = 'SAFE_RECLAIM_ONLY'
DEEP_POLICY = 'WINDOWS_DEEP_RECLAIM_MEASURED'
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
MEMORY_PURGE_STANDBY_LIST = 4

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

def _purge_standby_list():
    if not IS_WINDOWS:
        return (False, None)
    try:
        privilege = _enable_privilege('SeProfileSingleProcessPrivilege')
        command = ctypes.c_ulong(MEMORY_PURGE_STANDBY_LIST)
        ntdll = ctypes.windll.ntdll
        ntdll.NtSetSystemInformation.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_ulong]
        ntdll.NtSetSystemInformation.restype = ctypes.c_long
        status = int(ntdll.NtSetSystemInformation(SYSTEM_MEMORY_LIST_INFORMATION, ctypes.byref(command), ctypes.sizeof(command)))
        return (status == 0, {'ntstatus': status, 'privilege_enabled': privilege})
    except Exception as exc:
        return (False, {'error': f'{type(exc).__name__}: {exc}'})

def optimize_ram_deep(*, settle_seconds=0.9, snapshot_samples=4, purge_standby=True):
    before = _stable_snapshot(snapshot_samples)
    if not IS_WINDOWS:
        return {'version': ENGINE_VERSION, 'policy': DEEP_POLICY, 'success': False, 'before': asdict(before), 'after': asdict(before), 'measured_recovered_bytes': 0, 'measured_recovered_mb': 0.0, 'working_sets_trimmed': 0, 'external_processes_modified': 0, 'administrator': False, 'target_percent': None, 'message': 'La liberación profunda está disponible únicamente en Windows.'}
    if not is_administrator():
        return {'version': ENGINE_VERSION, 'policy': DEEP_POLICY, 'success': False, 'before': asdict(before), 'after': asdict(before), 'measured_recovered_bytes': 0, 'measured_recovered_mb': 0.0, 'working_sets_trimmed': 0, 'external_processes_modified': 0, 'administrator': False, 'target_percent': None, 'message': 'La liberación profunda requiere ejecutar CorePulse como administrador.'}
    try:
        collected = int(gc.collect())
    except Exception:
        collected = 0
    trimmed, failed, external_trimmed = _trim_working_sets()
    standby_ok = False
    standby_detail = None
    if purge_standby:
        standby_ok, standby_detail = _purge_standby_list()
    time.sleep(max(0.0, settle_seconds))
    after = _stable_snapshot(snapshot_samples)
    delta = int(after.available_bytes - before.available_bytes)
    recovered = max(0, delta)
    msg = f'Liberación profunda completada: {recovered / 1024 ** 3:.2f} GB adicionales medidos.' if recovered > 0 else 'Liberación profunda ejecutada, pero no hubo memoria adicional recuperada de forma medible.'
    return {'version': ENGINE_VERSION, 'policy': DEEP_POLICY, 'success': True, 'before': asdict(before), 'after': asdict(after), 'available_delta_bytes': delta, 'measured_recovered_bytes': recovered, 'measured_recovered_mb': round(recovered / 1024 ** 2, 2), 'measured_recovered_gb': round(recovered / 1024 ** 3, 3), 'used_percent_delta': round(before.used_percent - after.used_percent, 3), 'gc_objects_collected': collected, 'working_sets_trimmed': trimmed, 'working_sets_failed': failed, 'external_processes_modified': external_trimmed, 'standby_purge_attempted': bool(purge_standby), 'standby_purge_success': standby_ok, 'standby_purge_detail': standby_detail, 'administrator': True, 'target_percent': None, 'message': msg}

def format_result_for_user(result):
    before = result.get('before') or {}
    after = result.get('after') or {}
    return f"Uso antes: {float(before.get('used_percent') or 0):.1f}%\nUso después: {float(after.get('used_percent') or 0):.1f}%\nRecuperado medido: {float(result.get('measured_recovered_mb') or 0):.1f} MB\n\n{result.get('message') or ''}"
