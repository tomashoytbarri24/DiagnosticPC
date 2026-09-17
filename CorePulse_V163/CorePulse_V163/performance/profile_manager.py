"""Orquestador transaccional de modos de energía de CorePulse.

Modos visibles:
- Equilibrado
- Alto rendimiento
- Máximo rendimiento
- Ahorro de energía

Los modos elegidos manualmente son persistentes: Windows conserva el plan activo
aunque CorePulse se cierre. Game Boost queda separado y sigue siendo temporal;
sus cambios se restauran al terminar la sesión o cerrar CorePulse.
"""
from __future__ import annotations

import atexit
import copy
import logging
import threading
import time
from typing import Any, Dict, Optional

from .game_detector import GameDetector
from .game_boost import GameBoostOptimizer
from .power_manager import PowerManager
from .settings_backup import STATE_PATH, has_pending_backup, load_backup, mark_restored, save_backup

logger = logging.getLogger('CorePulse.Profile')

VISIBLE_MODES = ('BALANCED', 'HIGH_PERFORMANCE', 'MAXIMUM_PERFORMANCE', 'POWER_SAVER')
VALID_MODES = set(VISIBLE_MODES) | {'GAMING', 'COOL', 'AUTO'}  # compatibilidad interna antigua
PERFORMANCE_MODES = {'HIGH_PERFORMANCE', 'MAXIMUM_PERFORMANCE'}
LEGACY_ALIASES = {
    'GAMING': 'MAXIMUM_PERFORMANCE',
    'COOL': 'POWER_SAVER',
}


class PerformanceProfileManager:
    def __init__(
        self, power_manager: Optional[PowerManager] = None, game_detector: Optional[GameDetector] = None,
        poll_seconds: float = 2.0, *, backup_path=None, start_thread: bool = True,
        register_atexit: bool = True, game_boost: Optional[GameBoostOptimizer] = None,
    ):
        self.power = power_manager or PowerManager()
        self.game_detector = game_detector or GameDetector()
        self.game_boost = game_boost or GameBoostOptimizer()
        self.poll_seconds = max(1.0, float(poll_seconds))
        self.backup_path = backup_path or STATE_PATH
        self.lock = threading.RLock()
        self.requested_mode = 'BALANCED'
        self.effective_profile = 'BALANCED'
        self.active_games = []
        self.last_error = None
        self.last_message = 'Sin cambios de energía aplicados por CorePulse.'
        self.last_capabilities = {}
        # Estado REAL del plan de energía que Windows confirma como activo.
        self.windows_plan_guid = None
        self.windows_plan_name = 'N/A'
        self.windows_plan_mode = None
        self.windows_plan_verified = False
        self._last_performance_apply_result: Dict[str, Any] = {}
        self._auto_override = False  # sólo compatibilidad con la API AUTO antigua
        self._running = True
        self._shutdown_done = False
        self._state_generation = 0
        # Última selección persistente confirmada por el usuario/Windows durante
        # esta sesión.  Guardamos el GUID exacto porque el cierre debe preservar
        # ese plan incluso si una limpieza temporal de Game Boost o cualquier
        # otro paso interno cambia momentáneamente el esquema activo.
        self._committed_manual_mode = None
        self._committed_manual_guid = None
        self._committed_manual_name = None
        # Un backup pendiente sólo representa una transacción que no alcanzó a
        # confirmarse (p. ej. cierre/crash durante powercfg). Los perfiles
        # manuales completados se confirman y eliminan este backup, por lo que
        # nunca se revierten al volver a abrir CorePulse.
        self._recover_stale_backup()
        initial_plan = self._refresh_windows_plan_state()
        self._last_windows_plan_poll = time.monotonic()
        if initial_plan.get('success') and initial_plan.get('mode') in VISIBLE_MODES:
            detected_mode = str(initial_plan.get('mode')).upper()
            self.requested_mode = detected_mode
            self.effective_profile = detected_mode
            self.last_message = f'Plan activo de Windows detectado: {self.windows_plan_name}.'
        self._status_cache = self._status_locked()
        self.thread = None
        if start_thread:
            self.thread = threading.Thread(target=self._loop, daemon=True, name='CorePulse-PerformanceProfiles')
            self.thread.start()
        if register_atexit:
            atexit.register(self._atexit_restore)

    def set_notifier(self, callback) -> None:
        self.game_boost.set_notifier(callback)

    def boost_status(self) -> Dict[str, Any]:
        return self.game_boost.status()

    def boost_settings(self) -> Dict[str, bool]:
        return self.game_boost.get_settings()

    def set_boost_option(self, key: str, value: bool) -> bool:
        ok = self.game_boost.set_option(key, value)
        if ok:
            with self.lock:
                self._state_generation += 1
        return ok

    def _recover_stale_backup(self):
        if not has_pending_backup(self.backup_path):
            return
        backup = load_backup(self.backup_path)
        if not backup:
            return
        logger.warning('[PROFILE] Se encontró una restauración pendiente de una sesión anterior')
        result = self.power.restore(backup)
        if result.get('success'):
            mark_restored(self.backup_path)
            logger.info('[PROFILE] Restauración pendiente completada al iniciar CorePulse')
        else:
            self.last_error = result.get('message')
            logger.error('[ERROR][PROFILE] No se pudo recuperar configuración anterior: %s', self.last_error)

    def _ensure_backup(self, reason: str, *, restore_policy: str = 'failure_only') -> Dict[str, Any]:
        existing = load_backup(self.backup_path)
        if existing and existing.get('pending_restore', True):
            return {'success': True, 'backup': existing, 'existing': True}
        snap = self.power.snapshot()
        if not snap.get('success'):
            return {'success': False, 'message': snap.get('message')}
        self.last_capabilities = dict((snap.get('original') or {}).get('capabilities') or {})
        payload = {
            'original': snap['original'],
            'reason': str(reason),
            'restore_policy': str(restore_policy or 'failure_only'),
            'created_by': 'CorePulse PerformanceProfileManager',
        }
        save_backup(payload, self.backup_path)
        logger.info('[POWER] Configuración original guardada antes de %s', reason)
        return {'success': True, 'backup': load_backup(self.backup_path), 'existing': False}

    def _restore_original(self) -> Dict[str, Any]:
        backup = load_backup(self.backup_path)
        if not backup:
            result = self.power.activate_balanced_default()
            if result.get('success'):
                self.effective_profile = 'BALANCED'
                self._auto_override = False
            return result
        result = self.power.restore(backup)
        if result.get('success'):
            mark_restored(self.backup_path)
            self.effective_profile = 'BALANCED'
            self._auto_override = False
        return result

    def _refresh_windows_plan_state(self) -> Dict[str, Any]:
        """Lee el plan activo real de Windows sin asumir que CorePulse tuvo éxito."""
        reader = getattr(self.power, 'active_windows_plan', None)
        if reader is None:
            return {
                'success': False,
                'message': 'El backend actual no expone detección del plan de Windows.',
            }
        try:
            row = reader() or {}
        except Exception as exc:
            logger.exception('[POWER] Falló lectura del plan activo de Windows')
            row = {'success': False, 'message': str(exc)}
        if row.get('success'):
            self.windows_plan_guid = row.get('guid')
            self.windows_plan_name = row.get('name') or row.get('guid') or 'N/A'
            self.windows_plan_mode = row.get('mode')
            self.windows_plan_verified = bool(row.get('guid'))
        else:
            self.windows_plan_verified = False
        return row

    def _commit_persistent_plan(self, mode: str, *, guid=None, name=None) -> None:
        """Recuerda el plan exacto que debe sobrevivir al cierre de CorePulse.

        Esta memoria es de sesión y NO fuerza un plan al arrancar.  Al iniciar,
        Windows sigue siendo la autoridad para respetar cualquier cambio que el
        usuario haya hecho mientras CorePulse estaba cerrado.
        """
        canonical = self._canonical_mode(mode)
        token = str(guid or self.windows_plan_guid or '').lower().strip()
        if canonical not in VISIBLE_MODES or not token:
            return
        self._committed_manual_mode = canonical
        self._committed_manual_guid = token
        self._committed_manual_name = str(name or self.windows_plan_name or canonical)

    def finalize_persistent_plan(self) -> Dict[str, Any]:
        """Deja como última operación de energía el plan persistente elegido.

        Game Boost y otros componentes temporales pueden restaurar sus propios
        cambios al cerrarse.  Esta verificación ocurre DESPUÉS de esos rollbacks
        y sólo reafirma el GUID que ya fue elegido y verificado previamente.
        No inventa un plan ni cambia nada cuando el usuario no eligió uno.
        """
        with self.lock:
            target_guid = str(self._committed_manual_guid or '').lower().strip()
            target_mode = self._committed_manual_mode
            target_name = self._committed_manual_name or target_mode or 'plan seleccionado'
            if target_mode not in VISIBLE_MODES or not target_guid:
                current = self._refresh_windows_plan_state()
                return {
                    'success': bool(current.get('success')),
                    'changed': False,
                    'message': 'No hay un plan manual de CorePulse pendiente de reafirmar.',
                    'windows_plan_guid': current.get('guid'),
                }

            current = self._refresh_windows_plan_state()
            current_guid = str((current or {}).get('guid') or '').lower().strip()
            if current.get('success') and current_guid == target_guid:
                return {
                    'success': True, 'changed': False, 'verified': True,
                    'windows_plan_guid': target_guid, 'profile': target_mode,
                    'message': f'{target_name} permanece activo en Windows.',
                }

            setter = getattr(self.power, 'set_active', None)
            if callable(setter):
                result = setter(target_guid, verify=True)
            else:
                # Compatibilidad con backends/dobles antiguos: si ni siquiera
                # exponen set_active no ejecutamos un rollback ni declaramos un
                # fallo destructivo durante el cierre. El backend Windows real
                # sí expone set_active + verificación por GUID.
                return {
                    'success': True, 'changed': False, 'verified': False,
                    'windows_plan_guid': target_guid, 'profile': target_mode,
                    'message': 'Backend legado sin reafirmación por GUID; no se modificó el plan al cerrar.',
                }

            if not result.get('success'):
                # Si la copia del plan desapareció, intentar resolver nuevamente
                # el mismo MODO; nunca caer silenciosamente a Equilibrado.
                ensure = getattr(self.power, 'ensure_mode_scheme', None)
                if callable(ensure):
                    ensured = ensure(target_mode) or {}
                    new_guid = str(ensured.get('guid') or '').lower().strip()
                    if ensured.get('success') and new_guid and callable(setter):
                        result = setter(new_guid, verify=True)
                        if result.get('success'):
                            target_guid = new_guid
                            self._commit_persistent_plan(
                                target_mode, guid=new_guid,
                                name=ensured.get('name') or target_name,
                            )
                if not result.get('success'):
                    self.last_error = result.get('message') or 'No se pudo conservar el plan persistente al cerrar.'
                    logger.error('[ERROR][PROFILE] Persistencia final falló: %s', self.last_error)
                    self._refresh_windows_plan_state()
                    return {
                        'success': False, 'changed': False,
                        'message': self.last_error, 'requested_guid': target_guid,
                    }

            verified = self._refresh_windows_plan_state()
            active_guid = str((verified or {}).get('guid') or '').lower().strip()
            ok = bool(verified.get('success') and active_guid == target_guid)
            if ok:
                self.requested_mode = target_mode
                self.effective_profile = target_mode
                self.last_error = None
                self.last_message = f'{target_name} quedó activo de forma persistente en Windows.'
                logger.info('[PROFILE] Persistencia final verificada: %s (%s)', target_mode, target_guid)
                return {
                    'success': True, 'changed': True, 'verified': True,
                    'windows_plan_guid': target_guid, 'profile': target_mode,
                    'message': self.last_message,
                }

            self.last_error = 'Windows no conservó el GUID seleccionado durante la verificación final de cierre.'
            logger.error('[ERROR][PROFILE] %s solicitado=%s activo=%s', self.last_error, target_guid, active_guid)
            return {
                'success': False, 'changed': True, 'verified': False,
                'requested_guid': target_guid, 'active_guid': active_guid,
                'message': self.last_error,
            }

    def _apply_override(self, profile: str, reason: str, *, persistent: bool = False) -> Dict[str, Any]:
        """Aplica un modo CorePulse sobre el plan equivalente REAL de Windows.

        Los cambios manuales usan una transacción de seguridad: se toma snapshot,
        se aplica/verifica el GUID real de Windows y, si todo termina bien, el
        snapshot se confirma y se elimina. Así el plan queda persistente y sólo
        existe rollback automático ante una aplicación incompleta o fallida.

        ``persistent=False`` se reserva para compatibilidad con AUTO legado, que
        sí es temporal y conserva su snapshot hasta restaurarse.
        """
        guard = self._ensure_backup(
            reason,
            restore_policy='failure_only' if persistent else 'session_restore',
        )
        if not guard.get('success'):
            return guard
        backup = guard['backup']

        original = ((backup or {}).get('original') or {})
        original_scheme = original.get('active_scheme_guid')
        if not original_scheme:
            return {'success': False, 'message': 'No se pudo identificar el plan de energía original para rollback.'}

        target_info = None
        ensure_scheme = getattr(self.power, 'ensure_mode_scheme', None)
        if isinstance(self.power, PowerManager) and profile in PERFORMANCE_MODES:
            ensure_scheme = self.power.ensure_owned_profile
        if ensure_scheme is not None:
            target_info = (ensure_scheme(profile, protected_guids={original_scheme})
                           if isinstance(self.power, PowerManager) else ensure_scheme(profile))
            if not target_info.get('success'):
                return target_info
            scheme = str(target_info.get('guid') or '').lower().strip()
        else:
            # Compatibilidad con dobles de prueba/backends antiguos.
            scheme = str(original_scheme)
            target_info = {
                'success': True, 'mode': profile, 'guid': scheme,
                'name': profile, 'created': False, 'legacy_backend': True,
            }

        if not scheme:
            return {'success': False, 'message': f'Windows no devolvió un GUID válido para el modo {profile}.'}

        # Captura transaccional del destino. Las copias registradas se conservan
        # para reutilizarlas, restaurando sus valores y el plan previo. Sólo los
        # backends/respaldos antiguos conservan su limpieza temporal histórica.
        latest = load_backup(self.backup_path) or backup
        sync = latest.setdefault('windows_plan_sync', {})
        snapshots = sync.setdefault('scheme_snapshots', {})
        created_schemes = sync.setdefault('created_schemes', {})

        snap_fn = getattr(self.power, 'snapshot_scheme', None)
        target_snapshot = None
        if snap_fn is not None:
            try:
                target_snapshot = snap_fn(scheme)
            except Exception as exc:
                logger.exception('[POWER] Falló snapshot del plan destino %s', scheme)
                target_snapshot = {'success': False, 'message': str(exc)}

        if target_info.get('created') and not target_info.get('managed_persistent'):
            created_schemes.setdefault(scheme, {
                'mode': profile,
                'name': target_info.get('name') or profile,
            })
        elif scheme not in snapshots:
            if target_snapshot and target_snapshot.get('success'):
                snapshots[scheme] = {
                    'mode': profile,
                    'name': target_info.get('name') or profile,
                    'settings': copy.deepcopy(target_snapshot.get('settings') or {}),
                    'capabilities': copy.deepcopy(target_snapshot.get('capabilities') or {}),
                }
            else:
                # El cambio de PLAN sigue siendo reversible por GUID aunque el
                # OEM no exponga sus subajustes; no tocamos lo que no leímos.
                snapshots[scheme] = {
                    'mode': profile,
                    'name': target_info.get('name') or profile,
                    'settings': {},
                    'capabilities': {},
                    'partial': True,
                }

        save_backup(latest, self.backup_path)
        backup = load_backup(self.backup_path) or latest

        backed_settings = (
            (target_snapshot or {}).get('settings')
            if target_snapshot and target_snapshot.get('success')
            else ((snapshots.get(scheme) or {}).get('settings') or {})
        ) or {}
        self.last_capabilities = dict(
            (target_snapshot or {}).get('capabilities') or
            (snapshots.get(scheme) or {}).get('capabilities') or {
                'max_processor_state': 'max_processor_state' in backed_settings,
                'boost_mode': 'boost_mode' in backed_settings,
                'energy_performance_preference': 'energy_performance_preference' in backed_settings,
            }
        )

        # Resolución perezosa: conserva compatibilidad con integraciones antiguas.
        if profile == 'BALANCED':
            apply_fn = getattr(self.power, 'apply_balanced', None)
            if apply_fn is None:
                apply_fn = lambda _scheme, _settings: self.power.activate_balanced_default()
        elif profile == 'HIGH_PERFORMANCE':
            apply_fn = getattr(self.power, 'apply_high_performance', None) or getattr(self.power, 'apply_gaming', None)
        elif profile == 'MAXIMUM_PERFORMANCE':
            apply_fn = getattr(self.power, 'apply_maximum_performance', None) or getattr(self.power, 'apply_gaming', None)
        elif profile == 'POWER_SAVER':
            apply_fn = getattr(self.power, 'apply_power_saver', None) or getattr(self.power, 'apply_cool', None)
        else:
            apply_fn = None
        if apply_fn is None:
            return {'success': False, 'message': f'Modo de energía no soportado: {profile}'}

        result = apply_fn(scheme, backed_settings)
        if not result.get('success'):
            logger.error('[ERROR][PROFILE] Falló %s; intentando rollback inmediato', profile)
            rollback = self.power.restore(backup)
            if rollback.get('success'):
                mark_restored(self.backup_path)
                self.effective_profile = 'BALANCED'
                self._auto_override = False
            result['rollback_success'] = bool(rollback.get('success'))
            result['rollback_message'] = rollback.get('message')
            self._refresh_windows_plan_state()
            return result

        result.setdefault('windows_plan_guid', scheme)
        result.setdefault('windows_plan_name', target_info.get('name') or profile)
        result.setdefault('windows_plan_created', bool(target_info.get('created')))
        result.setdefault('windows_plan_reused', bool(target_info.get('reused')))
        result.setdefault('power_plan_duplicate_guard', bool(target_info.get('duplicate_guard')))
        result.setdefault('windows_plan_verified', True)
        self.effective_profile = profile
        self.windows_plan_guid = result.get('windows_plan_guid')
        self.windows_plan_name = result.get('windows_plan_name') or profile
        self.windows_plan_mode = profile
        self.windows_plan_verified = bool(result.get('windows_plan_verified'))
        self._refresh_windows_plan_state()
        if profile in PERFORMANCE_MODES:
            self._last_performance_apply_result = copy.deepcopy(result)

        if persistent:
            # El perfil manual ya fue aplicado y verificado. Desde este punto el
            # plan pertenece al estado elegido por el usuario, no a una sesión
            # temporal de CorePulse. El snapshot sólo servía para rollback de
            # fallo durante la transacción y ya no debe provocar restauración al
            # cerrar ni al iniciar de nuevo la aplicación.
            mark_restored(self.backup_path)
            self._commit_persistent_plan(
                profile,
                guid=result.get('windows_plan_guid') or self.windows_plan_guid or scheme,
                name=result.get('windows_plan_name') or self.windows_plan_name or target_info.get('name'),
            )
            result['persistent'] = True
            result['restore_policy'] = 'failure_only'
        else:
            result['persistent'] = False
            result['restore_policy'] = 'session_restore'
        return result

    @staticmethod
    def _canonical_mode(mode: str) -> str:
        raw = str(mode or '').upper().strip()
        return LEGACY_ALIASES.get(raw, raw)

    def set_mode(self, mode: str) -> Dict[str, Any]:
        raw_mode = str(mode or '').upper().strip()
        if raw_mode not in VALID_MODES:
            return {'success': False, 'message': f'Perfil desconocido: {raw_mode}'}

        # AUTO queda sólo para compatibilidad con integraciones antiguas. No se
        # expone en la interfaz desde V0.10.2.53w.
        if raw_mode == 'AUTO':
            with self.lock:
                previous_requested = self.requested_mode
                previous_effective = self.effective_profile
                if previous_requested != 'AUTO' and previous_effective in VISIBLE_MODES:
                    restored = self._restore_original() if has_pending_backup(self.backup_path) else {'success': True}
                    if not restored.get('success'):
                        return restored
                self.requested_mode = 'AUTO'
                self.effective_profile = 'BALANCED'
                self._auto_override = False
                self.game_boost.end_session()
                self.last_error = None
                self.last_message = 'Modo Automático legado activo para compatibilidad interna.'
                self._state_generation += 1
                return {'success': True, 'profile': 'AUTO', 'message': self.last_message}

        mode = self._canonical_mode(raw_mode)
        with self.lock:
            previous_requested = self.requested_mode
            previous_effective = self.effective_profile
            result = self._apply_override(mode, f'modo {mode} manual', persistent=True)

            if result.get('success'):
                self.requested_mode = mode
                self.last_error = None
                self.last_message = result.get('message') or f'{mode} aplicado.'
                self._auto_override = False

                # Game Boost es independiente del plan de energía, pero sólo se
                # arma automáticamente en perfiles orientados a rendimiento.
                if mode not in PERFORMANCE_MODES:
                    self.game_boost.end_session()
                elif self.active_games:
                    self.game_boost.sync_games(
                        self.active_games,
                        profile_result=result,
                        profile_activated_now=True,
                    )
                self._state_generation += 1
                logger.info('[PROFILE] %s aplicado; efectivo=%s', mode, self.effective_profile)
            else:
                self.requested_mode = previous_requested
                if result.get('rollback_success'):
                    self.effective_profile = 'BALANCED'
                else:
                    self.effective_profile = previous_effective
                self.last_error = result.get('message') or 'No se pudo aplicar el perfil.'
                logger.error('[ERROR][PROFILE] %s', self.last_error)
            return copy.deepcopy(result)

    def poll_games_once(self) -> Dict[str, Any]:
        games = self.game_detector.detect_active_games()
        # Detectar cambios externos sin ejecutar powercfg en cada sondeo de juegos.
        windows_state = {}
        now = time.monotonic()
        if now - self._last_windows_plan_poll >= 30.0:
            windows_state = self._refresh_windows_plan_state()
            self._last_windows_plan_poll = now
        with self.lock:
            # Si el usuario cambió el plan desde Windows, CorePulse no lo fuerza
            # de vuelta. Adopta el modo real reconocido y actualiza su UI. Esto
            # mantiene una sola autoridad: el plan que Windows confirma activo.
            external_mode = str((windows_state or {}).get('mode') or '').upper().strip()
            if (
                self.requested_mode != 'AUTO'
                and external_mode in VISIBLE_MODES
                and external_mode != self.requested_mode
                and not has_pending_backup(self.backup_path)
            ):
                self.requested_mode = external_mode
                self.effective_profile = external_mode
                self.last_error = None
                self.last_message = f'Plan cambiado desde Windows: {self.windows_plan_name}.'
                self._commit_persistent_plan(
                    external_mode, guid=(windows_state or {}).get('guid'),
                    name=(windows_state or {}).get('name'),
                )
                self._state_generation += 1

            prev_by_pid = {int(g.get('pid') or 0): g for g in self.active_games if int(g.get('pid') or 0)}
            cur_by_pid = {int(g.get('pid') or 0): g for g in games if int(g.get('pid') or 0)}
            previous_ids = set(prev_by_pid)
            current_ids = set(cur_by_pid)
            added = [cur_by_pid[pid] for pid in sorted(current_ids - previous_ids)]
            removed = [prev_by_pid[pid] for pid in sorted(previous_ids - current_ids)]
            self.active_games = copy.deepcopy(games)
            if current_ids != previous_ids:
                self._state_generation += 1
                for game in added:
                    logger.info('[GAME] %s detectado (%s, pid=%s)', game.get('name'), game.get('source'), game.get('pid'))
                for game in removed:
                    logger.info('[GAME] %s cerrado (pid=%s)', game.get('name'), game.get('pid'))

            # Compatibilidad de la API AUTO antigua: usa Máximo rendimiento sólo
            # durante una sesión de juego y restaura al cerrar el último juego.
            if self.requested_mode == 'AUTO':
                if games and not self._auto_override:
                    result = self._apply_override('MAXIMUM_PERFORMANCE', 'juego detectado en modo Automático legado', persistent=False)
                    if result.get('success'):
                        self._auto_override = True
                        self._last_performance_apply_result = copy.deepcopy(result)
                        self.game_boost.begin_session(games, profile_result=result, profile_activated_now=True)
                        self.last_message = f'Game Boost automático legado activo · {len(games)} juego(s) detectado(s).'
                        self._state_generation += 1
                    else:
                        self.last_error = result.get('message')
                elif games and self._auto_override:
                    if added or removed:
                        self.game_boost.sync_games(
                            games,
                            profile_result=self._last_performance_apply_result,
                            profile_activated_now=False,
                        )
                elif (not games) and self._auto_override:
                    self.game_boost.end_session()
                    result = self._restore_original()
                    if result.get('success'):
                        self.last_message = 'El último juego se cerró. Game Boost y configuración anterior restaurados.'
                        self._state_generation += 1
                    else:
                        self.last_error = result.get('message')

            elif self.requested_mode in PERFORMANCE_MODES:
                if games:
                    if added or removed or not self.game_boost.status().get('session_active'):
                        self.game_boost.sync_games(
                            games,
                            profile_result=self._last_performance_apply_result,
                            profile_activated_now=False,
                        )
                        self.last_message = (
                            f'{self.requested_mode} activo · Game Boost aplicado a {len(games)} juego(s).'
                        )
                        self._state_generation += 1
                elif self.game_boost.status().get('session_active'):
                    self.game_boost.end_session()
                    self.last_message = 'Modo de rendimiento sigue activo · no hay juegos en ejecución.'
                    self._state_generation += 1
            else:
                if self.game_boost.status().get('session_active'):
                    self.game_boost.end_session()
                    self._state_generation += 1
            return self.status()

    def _loop(self):
        # El detector de juegos sigue activo en todos los modos. Game Boost se
        # vincula sólo a Alto rendimiento/Máximo rendimiento (AUTO sólo legado).
        while self._running:
            try:
                self.poll_games_once()
            except Exception:
                logger.exception('[ERROR][GAME] Fallo en el monitor de juegos')
            end = time.monotonic() + self.poll_seconds
            while self._running and time.monotonic() < end:
                time.sleep(min(0.2, max(0.0, end - time.monotonic())))

    def status(self) -> Dict[str, Any]:
        # El hilo Tk recibe el último estado mientras el worker aplica powercfg.
        if not self.lock.acquire(blocking=False):
            return copy.deepcopy(getattr(self, '_status_cache', {}))
        try:
            state = self._status_locked()
            self._status_cache = state
            return copy.deepcopy(state)
        finally:
            self.lock.release()

    def _status_locked(self) -> Dict[str, Any]:
        with self.lock:
            return {
                'requested_mode': self.requested_mode,
                'effective_profile': self.effective_profile,
                'automatic': self.requested_mode == 'AUTO',
                'auto_override': self._auto_override,
                'visible_modes': list(VISIBLE_MODES),
                'active_games': copy.deepcopy(self.active_games),
                'active_game_count': len(self.active_games),
                'last_error': self.last_error,
                'message': self.last_message,
                'generation': self._state_generation,
                'backup_pending': has_pending_backup(self.backup_path),
                'capabilities': copy.deepcopy(self.last_capabilities),
                'windows_plan_guid': self.windows_plan_guid,
                'windows_plan_name': self.windows_plan_name,
                'windows_plan_mode': self.windows_plan_mode,
                'windows_plan_verified': self.windows_plan_verified,
                'committed_manual_mode': self._committed_manual_mode,
                'committed_manual_guid': self._committed_manual_guid,
                'windows_plan_in_sync': (
                    bool(self.windows_plan_verified) and
                    self.windows_plan_mode == self._canonical_mode(self.requested_mode)
                    if self.windows_plan_mode else False
                ),
                'game_boost': self.game_boost.status(),
            }

    def _atexit_restore(self):
        try:
            # Los planes manuales son persistentes. Sólo Game Boost y cualquier
            # transacción temporal/incompleta deben finalizarse al cerrar.
            self.shutdown(restore=False)
        except Exception:
            logger.exception('[ERROR][PROFILE] Falló apagado atexit')

    def shutdown(self, restore: bool = False) -> Dict[str, Any]:
        if self._shutdown_done:
            return {'success': True, 'message': 'Gestor de rendimiento ya detenido.'}
        self._shutdown_done = True
        self._running = False
        if getattr(self, 'thread', None) and self.thread.is_alive():
            self.thread.join(timeout=max(1.0, self.poll_seconds + 0.5))
        boost_result = self.game_boost.end_session()
        if restore and has_pending_backup(self.backup_path):
            result = self._restore_original()
            if not result.get('success'):
                logger.error('[ERROR][PROFILE] No se pudo restaurar durante cierre: %s', result.get('message'))
            return result

        # MUY IMPORTANTE: Game Boost termina primero.  Sólo entonces verificamos
        # el plan manual persistente para que ningún rollback temporal sea la
        # última escritura de energía del proceso.
        persisted = self.finalize_persistent_plan()
        if not persisted.get('success'):
            return persisted
        return {
            'success': bool(boost_result.get('success', True)),
            'message': persisted.get('message') or 'Plan persistente verificado al cerrar.',
            'power_persistence': persisted,
            'game_boost': boost_result,
        }
