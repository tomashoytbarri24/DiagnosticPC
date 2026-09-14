"""Game Boost seguro y reversible para procesos de juego detectados por CorePulse.

No hace overclock, no toca voltajes/BIOS y nunca utiliza prioridad Realtime.
Las acciones se aplican sólo cuando un modo de rendimiento compatible está activo.
"""
from __future__ import annotations

import copy
import ctypes
from ctypes import wintypes
import json
import logging
import os
from pathlib import Path
from core.runtime_paths import data_path
import threading
import time
from typing import Any, Callable, Dict, Iterable, Optional

import psutil

from core.ram_optimizer import purge_standby_for_game

logger = logging.getLogger('CorePulse.GameBoost')
CONFIG_PATH = data_path('game_boost_settings.json')
RUNTIME_BACKUP_PATH = data_path('game_boost_runtime_backup.json')
PROCESS_BACKUP_PATH = data_path('game_boost_process_backup.json')

DEFAULT_SETTINGS = {
    'clean_standby_memory': True,
    'high_process_priority': True,
    'disable_power_throttling': True,
    'windows_game_mode': True,
    'notifications': True,
}

IS_WINDOWS = os.name == 'nt'
PROCESS_SET_INFORMATION = 0x0200
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_POWER_THROTTLING = 4
PROCESS_POWER_THROTTLING_CURRENT_VERSION = 1
PROCESS_POWER_THROTTLING_EXECUTION_SPEED = 0x1


class PROCESS_POWER_THROTTLING_STATE(ctypes.Structure):
    _fields_ = [
        ('Version', wintypes.DWORD),
        ('ControlMask', wintypes.DWORD),
        ('StateMask', wintypes.DWORD),
    ]


def _safe_game_name(game: Dict[str, Any]) -> str:
    return str(game.get('name') or Path(str(game.get('exe') or '')).name or f"PID {game.get('pid') or '?'}")


class GameBoostOptimizer:
    def __init__(
        self, *, config_path: Path = CONFIG_PATH, runtime_backup_path: Path = RUNTIME_BACKUP_PATH,
        process_backup_path: Path = PROCESS_BACKUP_PATH,
        notifier: Optional[Callable[[str, str], None]] = None,
    ):
        self.config_path = Path(config_path)
        self.runtime_backup_path = Path(runtime_backup_path)
        self.process_backup_path = Path(process_backup_path)
        self.notifier = notifier
        self.lock = threading.RLock()
        self.settings = self._load_settings()
        self._process_state: Dict[int, Dict[str, Any]] = {}
        self._game_mode_backup: Optional[Dict[str, Any]] = None
        self._session_active = False
        self._memory_cleaned = False
        self._session_started_at: Optional[float] = None
        self._last_result: Dict[str, Any] = {}
        self._last_notification_at = 0.0
        self._recovery_status: Dict[str, Any] = {}
        self._recover_pending_runtime_backup()
        self._recover_pending_process_backup()

    def _load_settings(self) -> Dict[str, bool]:
        data = dict(DEFAULT_SETTINGS)
        try:
            if self.config_path.is_file():
                raw = json.loads(self.config_path.read_text(encoding='utf-8'))
                if isinstance(raw, dict):
                    for key in DEFAULT_SETTINGS:
                        if key in raw:
                            data[key] = bool(raw[key])
        except Exception:
            logger.exception('[GAMEBOOST] No se pudo leer configuración; se usarán valores seguros')
        return data

    def _save_settings(self) -> None:
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.config_path.with_suffix('.tmp')
            tmp.write_text(json.dumps(self.settings, ensure_ascii=False, indent=2), encoding='utf-8')
            os.replace(tmp, self.config_path)
        except Exception:
            logger.exception('[GAMEBOOST] No se pudo guardar configuración')

    def _load_runtime_backup(self) -> Optional[Dict[str, Any]]:
        try:
            if not self.runtime_backup_path.is_file():
                return None
            raw = json.loads(self.runtime_backup_path.read_text(encoding='utf-8'))
            return raw if isinstance(raw, dict) else None
        except Exception:
            logger.exception('[GAMEBOOST] No se pudo leer el backup runtime')
            return None

    def _save_runtime_backup(self, payload: Dict[str, Any]) -> bool:
        try:
            self.runtime_backup_path.parent.mkdir(parents=True, exist_ok=True)
            data = dict(payload or {})
            data.setdefault('schema_version', 1)
            data.setdefault('created_at', time.time())
            data['pending_restore'] = True
            tmp = self.runtime_backup_path.with_suffix(self.runtime_backup_path.suffix + '.tmp')
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
            os.replace(tmp, self.runtime_backup_path)
            return True
        except Exception:
            logger.exception('[GAMEBOOST] No se pudo persistir el backup runtime; no se aplicará el cambio global')
            return False

    def _clear_runtime_backup(self) -> None:
        try:
            if self.runtime_backup_path.exists():
                self.runtime_backup_path.unlink()
        except OSError:
            logger.exception('[GAMEBOOST] No se pudo eliminar el backup runtime restaurado')

    def _runtime_backup_pending(self) -> bool:
        data = self._load_runtime_backup()
        return bool(data and data.get('pending_restore', True))

    @staticmethod
    def _read_windows_game_mode() -> Dict[str, Any]:
        import winreg
        path = r'Software\Microsoft\GameBar'
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_QUERY_VALUE | winreg.KEY_SET_VALUE) as key:
            try:
                value, reg_type = winreg.QueryValueEx(key, 'AutoGameModeEnabled')
                return {'existed': True, 'value': value, 'type': int(reg_type)}
            except FileNotFoundError:
                return {'existed': False, 'value': None, 'type': int(winreg.REG_DWORD)}

    @staticmethod
    def _write_windows_game_mode(state: Dict[str, Any]) -> None:
        import winreg
        path = r'Software\Microsoft\GameBar'
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_QUERY_VALUE | winreg.KEY_SET_VALUE) as key:
            if state.get('existed'):
                winreg.SetValueEx(
                    key, 'AutoGameModeEnabled', 0,
                    int(state.get('type') or winreg.REG_DWORD), state.get('value'),
                )
            else:
                try:
                    winreg.DeleteValue(key, 'AutoGameModeEnabled')
                except FileNotFoundError:
                    pass

    @staticmethod
    def _game_mode_matches_applied(current: Dict[str, Any], applied_value: int = 1) -> bool:
        if not current.get('existed'):
            return False
        try:
            return int(current.get('value')) == int(applied_value)
        except (TypeError, ValueError):
            return False

    def _recover_pending_runtime_backup(self) -> None:
        """Recupera cambios globales de Game Boost tras un cierre no limpio.

        Sólo restaura si el valor actual sigue siendo exactamente el que CorePulse
        escribió. Si el usuario o Windows lo cambió después, CorePulse no pisa ese
        cambio y descarta el backup obsoleto.
        """
        if not IS_WINDOWS:
            return
        backup = self._load_runtime_backup()
        if not backup or not backup.get('pending_restore', True):
            return
        if backup.get('action') != 'windows_game_mode' or not isinstance(backup.get('original'), dict):
            logger.warning('[GAMEBOOST] Backup runtime desconocido; se conserva para diagnóstico')
            return
        try:
            current = self._read_windows_game_mode()
            if not self._game_mode_matches_applied(current, int(backup.get('applied_value', 1))):
                self._recovery_status = {
                    'success': True, 'restored': False, 'skipped': True,
                    'message': 'Rollback pendiente omitido: Windows Game Mode cambió fuera de CorePulse.',
                }
                logger.warning('[GAMEBOOST] Backup pendiente no coincide con el valor aplicado; no se sobrescribe el cambio externo')
                self._clear_runtime_backup()
                return
            self._write_windows_game_mode(dict(backup['original']))
            self._clear_runtime_backup()
            self._recovery_status = {
                'success': True, 'restored': True, 'skipped': False,
                'message': 'Windows Game Mode restaurado tras cierre no limpio.',
            }
            logger.info('[GAMEBOOST] Rollback pendiente de Windows Game Mode completado al iniciar')
        except Exception as exc:
            self._recovery_status = {
                'success': False, 'restored': False, 'skipped': False,
                'message': f'No se pudo recuperar Windows Game Mode: {type(exc).__name__}',
            }
            logger.exception('[GAMEBOOST] No se pudo recuperar el backup runtime pendiente')

    def _load_process_backup(self) -> Dict[str, Any]:
        try:
            if self.process_backup_path.is_file():
                raw = json.loads(self.process_backup_path.read_text(encoding='utf-8'))
                return raw if isinstance(raw, dict) else {}
        except Exception:
            logger.exception('[GAMEBOOST] No se pudo leer backup persistente de procesos')
        return {}

    def _persist_process_backup(self) -> None:
        """Persiste sólo cambios por proceso que aún necesitan rollback."""
        rows = []
        for state in self._process_state.values():
            if not isinstance(state, dict):
                continue
            if not state.get('priority_changed') and not state.get('power_throttling_changed'):
                continue
            clean = {
                'pid': int(state.get('pid') or 0), 'name': str(state.get('name') or ''),
                'create_time': state.get('create_time'),
                'priority_original': int(state.get('priority_original')) if state.get('priority_original') is not None else None,
                'priority_applied': int(state.get('priority_applied')) if state.get('priority_applied') is not None else None,
                'priority_changed': bool(state.get('priority_changed')),
                'power_throttling_original': copy.deepcopy(state.get('power_throttling_original')),
                'power_throttling_applied': copy.deepcopy(state.get('power_throttling_applied')),
                'power_throttling_changed': bool(state.get('power_throttling_changed')),
            }
            rows.append(clean)
        try:
            if not rows:
                self.process_backup_path.unlink(missing_ok=True)
                return
            self.process_backup_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {'schema_version': 1, 'pending_restore': True, 'created_at': time.time(), 'processes': rows}
            tmp = self.process_backup_path.with_suffix(self.process_backup_path.suffix + '.tmp')
            tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
            os.replace(tmp, self.process_backup_path)
        except Exception:
            logger.exception('[GAMEBOOST] No se pudo persistir rollback por proceso')

    def _recover_pending_process_backup(self) -> None:
        """Restaura prioridad/Power Throttling tras crash sin pisar cambios externos."""
        if not IS_WINDOWS:
            return
        payload = self._load_process_backup()
        rows = payload.get('processes') if isinstance(payload.get('processes'), list) else []
        if not rows:
            return
        restored = skipped = failed = 0
        remaining = []
        for state in rows:
            if not isinstance(state, dict):
                continue
            pid = int(state.get('pid') or 0)
            proc = self._same_process(pid, state.get('create_time'))
            if proc is None:
                # Si el PID ya no existe, Windows ya eliminó cualquier ajuste por proceso.
                if not psutil.pid_exists(pid):
                    skipped += 1
                    continue
                remaining.append(state); failed += 1; continue
            unresolved = False
            if state.get('priority_changed') and state.get('priority_original') is not None:
                try:
                    current = proc.nice(); applied = state.get('priority_applied')
                    if applied is None or int(current) == int(applied):
                        proc.nice(int(state['priority_original'])); restored += 1
                    elif int(current) == int(state['priority_original']):
                        skipped += 1
                    else:
                        # Otro actor cambió la prioridad después del crash. No pisarlo.
                        skipped += 1
                except Exception:
                    unresolved = True
            original = state.get('power_throttling_original')
            applied = state.get('power_throttling_applied')
            if state.get('power_throttling_changed') and isinstance(original, dict):
                try:
                    k = self._kernel32(); handle = k.OpenProcess(PROCESS_SET_INFORMATION | PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
                    if not handle:
                        unresolved = True
                    else:
                        try:
                            current = PROCESS_POWER_THROTTLING_STATE(); current.Version = PROCESS_POWER_THROTTLING_CURRENT_VERSION
                            if not k.GetProcessInformation(handle, PROCESS_POWER_THROTTLING, ctypes.byref(current), ctypes.sizeof(current)):
                                unresolved = True
                            else:
                                current_pair = (int(current.ControlMask), int(current.StateMask))
                                applied_pair = (int((applied or {}).get('control_mask') or 0), int((applied or {}).get('state_mask') or 0))
                                original_pair = (int(original.get('control_mask') or 0), int(original.get('state_mask') or 0))
                                if applied and current_pair == applied_pair:
                                    restore = PROCESS_POWER_THROTTLING_STATE()
                                    restore.Version = int(original.get('version') or PROCESS_POWER_THROTTLING_CURRENT_VERSION)
                                    restore.ControlMask = original_pair[0]; restore.StateMask = original_pair[1]
                                    if k.SetProcessInformation(handle, PROCESS_POWER_THROTTLING, ctypes.byref(restore), ctypes.sizeof(restore)):
                                        restored += 1
                                    else:
                                        unresolved = True
                                else:
                                    # Ya restaurado o cambiado externamente: no sobrescribir.
                                    skipped += 1
                        finally:
                            k.CloseHandle(handle)
                except Exception:
                    unresolved = True
            if unresolved:
                remaining.append(state); failed += 1
        try:
            if remaining:
                self.process_backup_path.parent.mkdir(parents=True, exist_ok=True)
                payload['processes'] = remaining
                tmp = self.process_backup_path.with_suffix(self.process_backup_path.suffix + '.tmp')
                tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8'); os.replace(tmp, self.process_backup_path)
            else:
                self.process_backup_path.unlink(missing_ok=True)
        except Exception:
            logger.exception('[GAMEBOOST] No se pudo actualizar backup de procesos recuperado')
        self._recovery_status['process_restore'] = {
            'restored': restored, 'skipped': skipped, 'failed': failed,
            'message': f'Rollback de procesos: {restored} restaurado(s), {skipped} omitido(s), {failed} pendiente(s).',
        }
        logger.info('[GAMEBOOST] %s', self._recovery_status['process_restore']['message'])

    def set_notifier(self, callback: Optional[Callable[[str, str], None]]) -> None:
        self.notifier = callback

    def set_option(self, key: str, value: bool) -> bool:
        if key not in DEFAULT_SETTINGS:
            return False
        with self.lock:
            self.settings[key] = bool(value)
            self._save_settings()
        logger.info('[GAMEBOOST] Opción %s -> %s', key, bool(value))
        return True

    def get_settings(self) -> Dict[str, bool]:
        with self.lock:
            return dict(self.settings)

    @staticmethod
    def _same_process(pid: int, create_time: Optional[float]) -> Optional[psutil.Process]:
        try:
            proc = psutil.Process(int(pid))
            if create_time is not None and abs(float(proc.create_time()) - float(create_time)) > 0.01:
                return None
            return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError, TypeError):
            return None

    def _set_high_priority(self, game: Dict[str, Any]) -> Dict[str, Any]:
        pid = int(game.get('pid') or 0)
        if not pid:
            return {'success': False, 'action': 'priority', 'message': 'PID no disponible.'}
        try:
            proc = psutil.Process(pid)
            create_time = float(proc.create_time())
            original = proc.nice()
            target = getattr(psutil, 'HIGH_PRIORITY_CLASS', 128)
            changed = original != target
            if changed:
                proc.nice(target)
            state = self._process_state.setdefault(pid, {'pid': pid, 'name': _safe_game_name(game), 'create_time': create_time})
            state['priority_original'] = int(original)
            state['priority_applied'] = int(target)
            state['priority_changed'] = bool(changed)
            if changed:
                self._persist_process_backup()
            logger.info('[GAMEBOOST] %s prioridad -> High', _safe_game_name(game))
            return {'success': True, 'action': 'priority', 'changed': changed, 'message': 'Prioridad del juego: Alta'}
        except psutil.AccessDenied:
            logger.warning('[GAMEBOOST] Acceso denegado al cambiar prioridad pid=%s', pid)
            return {'success': False, 'action': 'priority', 'message': 'Prioridad Alta: acceso denegado'}
        except psutil.NoSuchProcess:
            return {'success': False, 'action': 'priority', 'message': 'El proceso terminó antes de optimizarlo.'}
        except Exception as exc:
            logger.exception('[GAMEBOOST] Falló prioridad High pid=%s', pid)
            return {'success': False, 'action': 'priority', 'message': f'Prioridad Alta: {type(exc).__name__}'}

    @staticmethod
    def _kernel32():
        if not IS_WINDOWS:
            return None
        k = ctypes.WinDLL('kernel32', use_last_error=True)
        k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        k.OpenProcess.restype = wintypes.HANDLE
        k.CloseHandle.argtypes = [wintypes.HANDLE]
        k.CloseHandle.restype = wintypes.BOOL
        k.GetProcessInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        k.GetProcessInformation.restype = wintypes.BOOL
        k.SetProcessInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        k.SetProcessInformation.restype = wintypes.BOOL
        return k

    def _disable_power_throttling(self, game: Dict[str, Any]) -> Dict[str, Any]:
        if not IS_WINDOWS:
            return {'success': False, 'action': 'power_throttling', 'message': 'HighQoS sólo está disponible en Windows.'}
        pid = int(game.get('pid') or 0)
        if not pid:
            return {'success': False, 'action': 'power_throttling', 'message': 'PID no disponible.'}
        try:
            proc = psutil.Process(pid)
            create_time = float(proc.create_time())
            k = self._kernel32()
            handle = k.OpenProcess(PROCESS_SET_INFORMATION | PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not handle:
                error = ctypes.get_last_error()
                logger.warning('[GAMEBOOST] OpenProcess falló pid=%s error=%s', pid, error)
                return {'success': False, 'action': 'power_throttling', 'message': f'HighQoS: Windows rechazó acceso ({error})'}
            try:
                original = PROCESS_POWER_THROTTLING_STATE()
                original.Version = PROCESS_POWER_THROTTLING_CURRENT_VERSION
                got = bool(k.GetProcessInformation(handle, PROCESS_POWER_THROTTLING, ctypes.byref(original), ctypes.sizeof(original)))
                if not got:
                    error = ctypes.get_last_error()
                    return {'success': False, 'action': 'power_throttling', 'message': f'HighQoS: estado original no disponible ({error})'}
                target = PROCESS_POWER_THROTTLING_STATE()
                target.Version = PROCESS_POWER_THROTTLING_CURRENT_VERSION
                target.ControlMask = int(original.ControlMask) | PROCESS_POWER_THROTTLING_EXECUTION_SPEED
                target.StateMask = int(original.StateMask) & ~PROCESS_POWER_THROTTLING_EXECUTION_SPEED
                ok = bool(k.SetProcessInformation(handle, PROCESS_POWER_THROTTLING, ctypes.byref(target), ctypes.sizeof(target)))
                if not ok:
                    error = ctypes.get_last_error()
                    return {'success': False, 'action': 'power_throttling', 'message': f'HighQoS: no se pudo aplicar ({error})'}
                state = self._process_state.setdefault(pid, {'pid': pid, 'name': _safe_game_name(game), 'create_time': create_time})
                state['power_throttling_original'] = {
                    'version': int(original.Version), 'control_mask': int(original.ControlMask), 'state_mask': int(original.StateMask)
                }
                state['power_throttling_applied'] = {
                    'version': int(target.Version), 'control_mask': int(target.ControlMask), 'state_mask': int(target.StateMask)
                }
                state['power_throttling_changed'] = True
                self._persist_process_backup()
                logger.info('[GAMEBOOST] %s -> HighQoS / Power Throttling OFF', _safe_game_name(game))
                return {'success': True, 'action': 'power_throttling', 'message': 'Power Throttling: desactivado (HighQoS)'}
            finally:
                k.CloseHandle(handle)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return {'success': False, 'action': 'power_throttling', 'message': 'HighQoS: proceso no accesible'}
        except Exception as exc:
            logger.exception('[GAMEBOOST] Falló HighQoS pid=%s', pid)
            return {'success': False, 'action': 'power_throttling', 'message': f'HighQoS: {type(exc).__name__}'}

    def _enable_windows_game_mode(self) -> Dict[str, Any]:
        if not IS_WINDOWS:
            return {'success': False, 'action': 'windows_game_mode', 'message': 'Windows Game Mode no disponible.'}
        try:
            import winreg
            original = self._read_windows_game_mode()
            if self._game_mode_backup is None:
                self._game_mode_backup = dict(original)
            changed = not self._game_mode_matches_applied(original, 1)
            if changed:
                if self._runtime_backup_pending():
                    return {
                        'success': False, 'action': 'windows_game_mode',
                        'message': 'Windows Game Mode: omitido porque existe un rollback pendiente sin resolver',
                    }
                payload = {
                    'action': 'windows_game_mode',
                    'original': dict(original),
                    'applied_value': 1,
                    'created_by': 'CorePulse GameBoostOptimizer',
                }
                if not self._save_runtime_backup(payload):
                    return {
                        'success': False, 'action': 'windows_game_mode',
                        'message': 'Windows Game Mode: omitido porque no pudo asegurarse el rollback',
                    }
                path = r'Software\Microsoft\GameBar'
                with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_QUERY_VALUE | winreg.KEY_SET_VALUE) as key:
                    winreg.SetValueEx(key, 'AutoGameModeEnabled', 0, winreg.REG_DWORD, 1)
            logger.info('[GAMEBOOST] Windows Game Mode -> Enabled (temporal, rollback persistente=%s)', changed)
            return {
                'success': True, 'action': 'windows_game_mode', 'changed': changed,
                'message': 'Windows Game Mode: activado' if changed else 'Windows Game Mode: ya estaba activado',
            }
        except Exception as exc:
            logger.exception('[GAMEBOOST] No se pudo activar Windows Game Mode')
            return {'success': False, 'action': 'windows_game_mode', 'message': f'Windows Game Mode: {type(exc).__name__}'}

    def _restore_windows_game_mode(self) -> bool:
        backup = self._game_mode_backup
        self._game_mode_backup = None
        if not backup or not IS_WINDOWS:
            return True
        try:
            self._write_windows_game_mode(dict(backup))
            self._clear_runtime_backup()
            logger.info('[GAMEBOOST] Windows Game Mode restaurado')
            return True
        except Exception:
            logger.exception('[GAMEBOOST] No se pudo restaurar Windows Game Mode')
            return False

    def _restore_process(self, pid: int) -> None:
        state = self._process_state.get(int(pid))
        if not state:
            return
        proc = self._same_process(pid, state.get('create_time'))
        if proc is None:
            if not psutil.pid_exists(int(pid)):
                self._process_state.pop(int(pid), None)
                self._persist_process_backup()
            return
        ok = True
        if state.get('priority_changed') and 'priority_original' in state:
            try:
                proc.nice(state['priority_original'])
                logger.info('[GAMEBOOST] %s prioridad restaurada', state.get('name'))
            except Exception:
                ok = False
                logger.exception('[GAMEBOOST] No se pudo restaurar prioridad pid=%s', pid)
        original = state.get('power_throttling_original')
        if original and IS_WINDOWS:
            try:
                k = self._kernel32()
                handle = k.OpenProcess(PROCESS_SET_INFORMATION | PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
                if handle:
                    try:
                        restore = PROCESS_POWER_THROTTLING_STATE()
                        restore.Version = int(original.get('version') or PROCESS_POWER_THROTTLING_CURRENT_VERSION)
                        restore.ControlMask = int(original.get('control_mask') or 0)
                        restore.StateMask = int(original.get('state_mask') or 0)
                        if not k.SetProcessInformation(handle, PROCESS_POWER_THROTTLING, ctypes.byref(restore), ctypes.sizeof(restore)):
                            ok = False
                            logger.warning('[GAMEBOOST] No se pudo restaurar Power Throttling pid=%s error=%s', pid, ctypes.get_last_error())
                    finally:
                        k.CloseHandle(handle)
                else:
                    ok = False
            except Exception:
                ok = False
                logger.exception('[GAMEBOOST] Falló restauración HighQoS pid=%s', pid)
        if ok:
            self._process_state.pop(int(pid), None)
        self._persist_process_backup()


    def _notify(self, title: str, body: str) -> None:
        if not self.settings.get('notifications') or not callable(self.notifier):
            return
        try:
            self.notifier(str(title), str(body))
            self._last_notification_at = time.time()
        except Exception:
            logger.exception('[GAMEBOOST] Falló notificación')

    @staticmethod
    def _power_lines(profile_result: Optional[Dict[str, Any]], *, activated_now: bool) -> list[str]:
        if not isinstance(profile_result, dict) or not profile_result.get('success'):
            return []
        profile = str(profile_result.get('profile') or '').upper()
        label = {
            'HIGH_PERFORMANCE': 'Alto rendimiento',
            'MAXIMUM_PERFORMANCE': 'Máximo rendimiento',
            'GAMING': 'Máximo rendimiento',  # compatibilidad antigua
        }.get(profile, 'Modo de rendimiento')
        rows = [f'{label}: activado' if activated_now else f'{label}: ya estaba activo']
        if profile_result.get('boost_managed') is True:
            rows.append('Turbo Boost: activado')
        elif profile_result.get('boost_managed') is False:
            rows.append('Turbo Boost: conservado por OEM')
        if profile_result.get('epp_managed') is True:
            rows.append('EPP CPU: rendimiento')
        return rows

    def begin_session(
        self, games: Iterable[Dict[str, Any]], *, profile_result: Optional[Dict[str, Any]] = None,
        profile_activated_now: bool = False,
    ) -> Dict[str, Any]:
        games = [dict(g) for g in (games or []) if int(g.get('pid') or 0)]
        with self.lock:
            new_session = not self._session_active
            if new_session:
                self._session_active = True
                self._session_started_at = time.time()
                self._memory_cleaned = False
            actions: list[Dict[str, Any]] = []
            if self.settings.get('windows_game_mode') and self._game_mode_backup is None:
                actions.append(self._enable_windows_game_mode())
            if self.settings.get('clean_standby_memory') and not self._memory_cleaned:
                memory = purge_standby_for_game()
                actions.append({'action': 'standby_memory', **memory})
                # Una única tentativa por sesión evita purgas repetitivas cuando abre un segundo juego.
                self._memory_cleaned = True
                logger.info('[GAMEBOOST] %s', memory.get('message'))
            for game in games:
                pid = int(game.get('pid') or 0)
                if pid in self._process_state:
                    continue
                try:
                    create_time = float(psutil.Process(pid).create_time())
                except Exception:
                    create_time = None
                # Registrar el PID aunque todas las optimizaciones por proceso estén
                # desactivadas evita notificar el mismo juego en cada sondeo.
                self._process_state[pid] = {
                    'pid': pid, 'name': _safe_game_name(game), 'create_time': create_time,
                    'tracking_only': True,
                }
                if self.settings.get('high_process_priority'):
                    actions.append(self._set_high_priority(game))
                if self.settings.get('disable_power_throttling'):
                    actions.append(self._disable_power_throttling(game))
            # Sólo el primer juego de la sesión debe anunciar cambios globales.
            # Un segundo juego no vuelve a aplicar energía ni debe fingir que lo hizo.
            power_lines = self._power_lines(profile_result, activated_now=profile_activated_now) if new_session else []
            names = ', '.join(_safe_game_name(g) for g in games[:3]) or 'Juego detectado'
            body_lines = list(power_lines)
            for action in actions:
                if action.get('action') == 'standby_memory':
                    if action.get('success'):
                        mb = float(action.get('measured_recovered_mb') or 0.0)
                        body_lines.append(f'RAM standby: limpiada ({mb:.0f} MB medidos)')
                    else:
                        body_lines.append('RAM standby: omitida/no disponible')
                elif action.get('success'):
                    body_lines.append(str(action.get('message') or 'Optimización aplicada'))
                else:
                    # Una optimización opcional que falla no invalida la sesión de rendimiento, pero
                    # sí debe quedar visible para no dar una confirmación falsa.
                    body_lines.append(str(action.get('message') or 'Optimización opcional: no disponible'))
            if not body_lines:
                body_lines.append('Juego detectado · sin cambios adicionales necesarios')
            summary = {
                'success': True,
                'games': copy.deepcopy(games),
                'actions': actions,
                'profile_result': copy.deepcopy(profile_result),
                'message': ' · '.join(body_lines),
                'timestamp': time.time(),
                'applied_count': sum(1 for a in actions if a.get('success')),
                'failed_count': sum(1 for a in actions if not a.get('success')),
            }
            self._last_result = copy.deepcopy(summary)
            logger.info('[GAMEBOOST] Sesión activa para %s · %s', names, summary['message'])
            self._notify(f'CorePulse Game Boost · {names}', '\n'.join(body_lines[:6]))
            return summary

    def sync_games(
        self, games: Iterable[Dict[str, Any]], *, profile_result: Optional[Dict[str, Any]] = None,
        profile_activated_now: bool = False,
    ) -> Dict[str, Any]:
        games = [dict(g) for g in (games or []) if int(g.get('pid') or 0)]
        with self.lock:
            current_ids = {int(g.get('pid')) for g in games}
            for pid in list(self._process_state):
                if pid not in current_ids:
                    self._restore_process(pid)
            new_games = [g for g in games if int(g.get('pid')) not in self._process_state]
            if not self._session_active and games:
                return self.begin_session(games, profile_result=profile_result, profile_activated_now=profile_activated_now)
            if new_games:
                # No vuelve a purgar standby dentro de la misma sesión; sí optimiza el proceso nuevo.
                return self.begin_session(new_games, profile_result=profile_result, profile_activated_now=False)
            return self.status()

    def end_session(self) -> Dict[str, Any]:
        with self.lock:
            for pid in list(self._process_state):
                self._restore_process(pid)
            game_mode_ok = self._restore_windows_game_mode()
            was_active = self._session_active
            self._session_active = False
            self._memory_cleaned = False
            self._session_started_at = None
            if was_active:
                logger.info('[GAMEBOOST] Sesión finalizada; optimizaciones por proceso restauradas')
            return {'success': bool(game_mode_ok), 'message': 'Game Boost finalizado y ajustes temporales restaurados.'}

    def status(self) -> Dict[str, Any]:
        with self.lock:
            return {
                'session_active': bool(self._session_active),
                'session_started_at': self._session_started_at,
                'optimized_processes': len(self._process_state),
                'optimized_pids': sorted(self._process_state),
                'memory_cleaned': bool(self._memory_cleaned),
                'settings': dict(self.settings),
                'last_result': copy.deepcopy(self._last_result),
                'last_notification_at': self._last_notification_at,
                'runtime_backup_pending': self._runtime_backup_pending(),
                'recovery_status': copy.deepcopy(self._recovery_status),
            }
