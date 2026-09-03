"""Interfaz de bajo nivel con la memoria compartida de RTSS para leer aplicaciones y publicar el OSD."""
from __future__ import annotations
# Código refactorizado: nombres estables y documentación en español.
import ctypes
import os
import subprocess
import winreg
from collections import deque
from pathlib import Path
IS_WINDOWS = os.name == 'nt'
MAP_NAME = 'RTSSSharedMemoryV2'
FILE_MAP_WRITE = 2
FILE_MAP_READ = 4
FILE_MAP_READ_WRITE = FILE_MAP_READ | FILE_MAP_WRITE
FILE_MAP_ALL_ACCESS = 983071
OWNER = b'CorePulse'
MAX_PATH = 260
RTSS_SIGNATURE = 1381258067
DEAD_SIGNATURE = 57005
HDR_SIGNATURE = 0
HDR_VERSION = 4
HDR_APP_ENTRY_SIZE = 8
HDR_APP_ARR_OFFSET = 12
HDR_APP_ARR_SIZE = 16
HDR_OSD_ENTRY_SIZE = 20
HDR_OSD_ARR_OFFSET = 24
HDR_OSD_ARR_SIZE = 28
HDR_OSD_FRAME = 32
HDR_BUSY = 36
OSD_TEXT = 0
OSD_OWNER = 256
OSD_TEXT_EX = 512
APP_PID = 0
APP_NAME = 4
APP_FLAGS = 264
APP_TIME0 = 268
APP_TIME1 = 272
APP_FRAMES = 276
APP_FRAME_TIME_US = 280
kernel32 = None
if IS_WINDOWS:
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel32.OpenFileMappingW.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_wchar_p]
    kernel32.OpenFileMappingW.restype = ctypes.c_void_p
    kernel32.MapViewOfFile.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_size_t]
    kernel32.MapViewOfFile.restype = ctypes.c_void_p
    kernel32.UnmapViewOfFile.argtypes = [ctypes.c_void_p]
    kernel32.UnmapViewOfFile.restype = ctypes.c_int
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_int
    kernel32.GetTickCount.argtypes = []
    kernel32.GetTickCount.restype = ctypes.c_uint32

def _u32(address):
    return ctypes.c_uint32.from_address(int(address)).value

def _set_u32(address, value):
    ctypes.c_uint32.from_address(int(address)).value = int(value) & 4294967295

def _read_cstr(address, size):
    raw = ctypes.string_at(int(address), int(size))
    return raw.split(b'\x00', 1)[0].decode('mbcs', errors='replace')

def _write_cstr(address, size, data):
    if isinstance(data, str):
        data = data.encode('mbcs', errors='replace')
    data = data[:max(0, size - 1)]
    ctypes.memset(int(address), 0, int(size))
    if data:
        ctypes.memmove(int(address), data, len(data))

def _signature_text(value):
    try:
        raw = int(value).to_bytes(4, 'little', signed=False)
        ascii_text = raw.decode('ascii', errors='replace')
    except Exception:
        ascii_text = '????'
    return f'0x{int(value):08X} ({ascii_text!r})'

def find_rtss_exe():
    candidates = []
    reg_paths = [(winreg.HKEY_LOCAL_MACHINE, 'SOFTWARE\\Unwinder\\RTSS'), (winreg.HKEY_LOCAL_MACHINE, 'SOFTWARE\\WOW6432Node\\Unwinder\\RTSS'), (winreg.HKEY_CURRENT_USER, 'SOFTWARE\\Unwinder\\RTSS')]
    for root, path in reg_paths:
        try:
            with winreg.OpenKey(root, path) as key:
                install_path, _ = winreg.QueryValueEx(key, 'InstallPath')
                if install_path:
                    candidates.append(Path(install_path) / 'RTSS.exe')
        except OSError:
            pass
    candidates.extend([Path(os.environ.get('ProgramFiles', 'C:\\Program Files')) / 'RivaTuner Statistics Server' / 'RTSS.exe', Path(os.environ.get('ProgramFiles(x86)', 'C:\\Program Files (x86)')) / 'RivaTuner Statistics Server' / 'RTSS.exe'])
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None

def start_rtss():
    exe = find_rtss_exe()
    if not exe:
        return (False, 'RTSS.exe no encontrado')
    try:
        subprocess.Popen([str(exe)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        return (True, str(exe))
    except Exception as exc:
        return (False, str(exc))

class RTSSSharedMemory:

    def __init__(self):
        self.handle = None
        self.base = None
        self.slot_index = None
        self._map_access = None
        self._frametimes = deque(maxlen=600)
        self.last_stage = None
        self.last_error_code = 0
        self.last_error = None
        self.header = None

    def _fail(self, stage):
        self.last_stage = stage
        self.last_error_code = ctypes.get_last_error()
        self.last_error = ctypes.FormatError(self.last_error_code) if self.last_error_code else 'Sin código Win32 adicional'
        return False

    def open(self):
        if not IS_WINDOWS:
            self.last_stage = 'platform'
            self.last_error = 'RTSS Shared Memory solo está disponible en Windows'
            return False
        if self.base:
            return True
        access_attempts = [FILE_MAP_READ_WRITE, FILE_MAP_ALL_ACCESS]
        for desired_access in access_attempts:
            ctypes.set_last_error(0)
            handle = kernel32.OpenFileMappingW(desired_access, False, MAP_NAME)
            if not handle:
                self._fail(f'OpenFileMappingW(access=0x{desired_access:X})')
                continue
            ctypes.set_last_error(0)
            view_access = FILE_MAP_READ_WRITE if desired_access == FILE_MAP_READ_WRITE else FILE_MAP_ALL_ACCESS
            base = kernel32.MapViewOfFile(handle, view_access, 0, 0, 0)
            if not base:
                self._fail(f'MapViewOfFile(access=0x{view_access:X})')
                kernel32.CloseHandle(handle)
                continue
            try:
                signature = _u32(base + HDR_SIGNATURE)
                version = _u32(base + HDR_VERSION)
                header = {'signature': signature, 'signature_text': _signature_text(signature), 'version_raw': version, 'version_major': version >> 16, 'version_minor': version & 65535, 'app_entry_size': _u32(base + HDR_APP_ENTRY_SIZE), 'app_arr_offset': _u32(base + HDR_APP_ARR_OFFSET), 'app_arr_size': _u32(base + HDR_APP_ARR_SIZE), 'osd_entry_size': _u32(base + HDR_OSD_ENTRY_SIZE), 'osd_arr_offset': _u32(base + HDR_OSD_ARR_OFFSET), 'osd_arr_size': _u32(base + HDR_OSD_ARR_SIZE), 'osd_frame': _u32(base + HDR_OSD_FRAME)}
            except Exception as exc:
                kernel32.UnmapViewOfFile(base)
                kernel32.CloseHandle(handle)
                self.last_stage = 'read_header'
                self.last_error_code = 0
                self.last_error = f'{type(exc).__name__}: {exc}'
                continue
            if header['version_major'] != 2:
                kernel32.UnmapViewOfFile(base)
                kernel32.CloseHandle(handle)
                self.header = header
                self.last_stage = 'validate_version'
                self.last_error_code = 0
                self.last_error = f'Versión de shared memory no compatible: 0x{version:08X}'
                continue
            if signature not in (RTSS_SIGNATURE,):
                kernel32.UnmapViewOfFile(base)
                kernel32.CloseHandle(handle)
                self.header = header
                self.last_stage = 'validate_signature'
                self.last_error_code = 0
                self.last_error = 'Firma RTSS inesperada: ' + header['signature_text']
                continue
            self.handle = handle
            self.base = int(base)
            self._map_access = desired_access
            self.header = header
            self.last_stage = 'ready'
            self.last_error_code = 0
            self.last_error = None
            return True
        return False

    def raw_diagnostic(self):
        ok = self.open()
        return {'ok': ok, 'map_name': MAP_NAME, 'stage': self.last_stage, 'win32_error_code': self.last_error_code, 'win32_error': self.last_error, 'map_access': f'0x{self._map_access:X}' if self._map_access is not None else None, 'base_address': hex(self.base) if self.base else None, 'header': self.header}

    def close(self):
        try:
            self.release_osd()
        except Exception:
            pass
        if self.base:
            kernel32.UnmapViewOfFile(ctypes.c_void_p(self.base))
            self.base = None
        if self.handle:
            kernel32.CloseHandle(self.handle)
            self.handle = None

    @property
    def available(self):
        return bool(self.open())

    @property
    def version(self):
        if not self.open():
            return None
        version = _u32(self.base + HDR_VERSION)
        return f'{version >> 16}.{version & 65535}'

    def _osd_entry_address(self, index):
        osd_arr_offset = _u32(self.base + HDR_OSD_ARR_OFFSET)
        osd_entry_size = _u32(self.base + HDR_OSD_ENTRY_SIZE)
        return self.base + osd_arr_offset + index * osd_entry_size

    def _claim_slot(self):
        if not self.open():
            return None
        count = _u32(self.base + HDR_OSD_ARR_SIZE)
        for pass_index in (0, 1):
            for index in range(1, count):
                entry = self._osd_entry_address(index)
                owner = ctypes.string_at(entry + OSD_OWNER, 256).split(b'\x00', 1)[0]
                if pass_index == 0 and owner == OWNER:
                    self.slot_index = index
                    return entry
                if pass_index == 1 and (not owner):
                    _write_cstr(entry + OSD_OWNER, 256, OWNER)
                    self.slot_index = index
                    return entry
        return None

    def update_osd(self, text):
        if not self.open():
            return False
        entry = self._claim_slot()
        if not entry:
            self.last_stage = 'claim_osd_slot'
            self.last_error = 'No hay slots OSD libres en RTSS'
            return False
        version = _u32(self.base + HDR_VERSION)
        if version >= 131079:
            _write_cstr(entry + OSD_TEXT_EX, 4096, text)
        else:
            _write_cstr(entry + OSD_TEXT, 256, text)
        frame = _u32(self.base + HDR_OSD_FRAME)
        _set_u32(self.base + HDR_OSD_FRAME, frame + 1)
        return True

    def release_osd(self):
        if not self.base:
            return
        count = _u32(self.base + HDR_OSD_ARR_SIZE)
        version = _u32(self.base + HDR_VERSION)
        for index in range(1, count):
            entry = self._osd_entry_address(index)
            owner = ctypes.string_at(entry + OSD_OWNER, 256).split(b'\x00', 1)[0]
            if owner == OWNER:
                _write_cstr(entry + OSD_TEXT, 256, b'')
                if version >= 131079:
                    _write_cstr(entry + OSD_TEXT_EX, 4096, b'')
                _write_cstr(entry + OSD_OWNER, 256, b'')
        frame = _u32(self.base + HDR_OSD_FRAME)
        _set_u32(self.base + HDR_OSD_FRAME, frame + 1)
        self.slot_index = None

    def list_apps(self):
        if not self.open():
            return []
        app_offset = _u32(self.base + HDR_APP_ARR_OFFSET)
        app_size = _u32(self.base + HDR_APP_ENTRY_SIZE)
        app_count = _u32(self.base + HDR_APP_ARR_SIZE)
        if app_size < 284 or app_size > 1024 * 1024 or app_count > 4096 or (app_offset < 32):
            self.last_stage = 'validate_app_array'
            self.last_error = f'App array inválido: offset={app_offset}, size={app_size}, count={app_count}'
            return []
        now_tick = kernel32.GetTickCount()
        apps = []
        for index in range(app_count):
            addr = self.base + app_offset + index * app_size
            pid = _u32(addr + APP_PID)
            if not pid:
                continue
            name = _read_cstr(addr + APP_NAME, MAX_PATH)
            time0 = _u32(addr + APP_TIME0)
            time1 = _u32(addr + APP_TIME1)
            frames = _u32(addr + APP_FRAMES)
            frame_time_us = _u32(addr + APP_FRAME_TIME_US)
            frame_time_ms = None
            fps = None
            fps_1s = None
            if 0 < frame_time_us < 1000000:
                frame_time_ms = frame_time_us / 1000.0
                fps = 1000000.0 / frame_time_us
            delta = time1 - time0 & 4294967295
            if time0 and time1 and (delta > 0) and (frames > 0):
                fps_1s = 1000.0 * frames / delta
            age_ms = now_tick - time1 & 4294967295 if time1 else 4294967295
            apps.append({'index': index, 'pid': pid, 'name': name, 'time0': time0, 'time1': time1, 'frames': frames, 'frame_time_us': frame_time_us, 'frametime_ms': frame_time_ms, 'fps': fps, 'fps_1s': fps_1s, 'age_ms': age_ms})
        apps.sort(key=lambda x: x['age_ms'])
        return apps

    def set_app_osd_style(self, app_index, x=20, y=20, pixel=1, color=16317180, background=527639):
        if not self.open():
            return False
        if not isinstance(app_index, int) or app_index < 0:
            return False
        app_offset = _u32(self.base + HDR_APP_ARR_OFFSET)
        app_size = _u32(self.base + HDR_APP_ENTRY_SIZE)
        app_count = _u32(self.base + HDR_APP_ARR_SIZE)
        if app_index >= app_count or app_size < 604:
            return False
        addr = self.base + app_offset + app_index * app_size
        if _u32(addr + APP_PID) == 0:
            return False
        _set_u32(addr + 316, int(x))
        _set_u32(addr + 320, int(y))
        _set_u32(addr + 324, max(1, int(pixel)))
        _set_u32(addr + 328, int(color))
        _set_u32(addr + 600, int(background))
        frame = _u32(self.base + HDR_OSD_FRAME)
        _set_u32(self.base + HDR_OSD_FRAME, frame + 1)
        return True

    def active_app(self, freshness_ms=2500):
        apps = self.list_apps()
        for app in apps:
            if app['age_ms'] <= freshness_ms and app['frametime_ms'] is not None and (app['fps'] is not None):
                frame_time = app['frametime_ms']
                if 0 < frame_time < 1000:
                    self._frametimes.append(frame_time)
                low_1 = None
                if len(self._frametimes) >= 60:
                    sorted_times = sorted(self._frametimes, reverse=True)
                    count = max(1, round(len(sorted_times) * 0.01))
                    worst = sorted_times[:count]
                    mean_worst = sum(worst) / len(worst)
                    if mean_worst > 0:
                        low_1 = 1000.0 / mean_worst
                result = dict(app)
                result.update({'fps_1pct_low': low_1, 'quality': 'VALID', 'source': 'RTSS Shared Memory'})
                return result
        return {'pid': None, 'name': None, 'fps': None, 'fps_1s': None, 'frametime_ms': None, 'fps_1pct_low': None, 'quality': 'UNAVAILABLE', 'source': 'RTSS Shared Memory'}
