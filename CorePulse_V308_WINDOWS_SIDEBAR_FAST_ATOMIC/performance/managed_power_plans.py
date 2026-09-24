"""Registro persistente y conservador de esquemas de energía administrados.

La intención se guarda antes de duplicar. El GUID de destino es estable y sólo
se considera real al verlo en /list. Un fallo ambiguo nunca genera otro GUID.
Los nombres/configuraciones compatibles permiten reutilizar, pero NO borrar.
"""
from contextlib import contextmanager
import json
import logging
import os
from pathlib import Path
import threading
import uuid

from core.runtime_paths import data_path
from core.windows_commands import friendly_failure
from .power_manager import (
    WINDOWS_MODE_SCHEMES, COREPULSE_FALLBACK_NAMES, COREPULSE_PROFILE_NAMES, COREPULSE_PROFILE_ALIASES, GUID_RE, HEX_RE,
    MAX_PROCESSOR_STATE, BOOST_MODE, PERF_EPP,
)

logger = logging.getLogger('CorePulse.Power')
_LOCK = threading.RLock()


class ManagedPowerPlans:
    def __init__(self, power, path=None, description_reader=None):
        self.power = power
        self.description_reader = description_reader or self._windows_description
        self.path = Path(path) if path is not None else data_path('managed_power_plans.json')

    @staticmethod
    def _windows_description(guid):
        # API pública de Windows: consulta de metadatos, sin activar ni modificar.
        if os.name != 'nt' or not GUID_RE.fullmatch(guid):
            return None
        try:
            import ctypes as c
            reader = c.WinDLL('powrprof').PowerReadDescription
            reader.argtypes = [c.c_void_p] * 5 + [c.POINTER(c.c_uint32)]
            reader.restype = c.c_uint32
            token = c.create_string_buffer(uuid.UUID(guid).bytes_le, 16)
            size = c.c_uint32()
            code = reader(None, token, None, None, None, c.byref(size))
            if code not in (0, 234) or not 2 <= size.value <= 65536:
                return None
            buffer = c.create_string_buffer(size.value)
            if reader(None, token, None, None, buffer, c.byref(size)) != 0:
                return None
            return buffer.raw[:size.value].decode('utf-16-le').rstrip(chr(0))
        except (OSError, ValueError, UnicodeError):
            return None

    @staticmethod
    def marker(mode):
        return f'CorePulse.ManagedPowerPlan/v1;mode={mode};base={WINDOWS_MODE_SCHEMES[mode]}'

    def _discover(self, data, schemes, mode):
        # Registro previo o marcador exacto + nombre conocido. Nunca adoptar por
        # prefijo, por contener CorePulse, ni sólo por configuración equivalente.
        for guid, row in schemes.items():
            if guid in WINDOWS_MODE_SCHEMES.values():
                continue
            existing = data['plans'].get(guid, {})
            if existing and existing.get('mode') != mode:
                continue
            if row.get('name', '').casefold() not in COREPULSE_PROFILE_ALIASES[mode]:
                continue
            if self.description_reader(guid) == self.marker(mode):
                data['plans'][guid] = {**existing, 'mode': mode,
                    'base': WINDOWS_MODE_SCHEMES[mode], 'owned': True, 'state': 'ready',
                    'identity': 'windows_description_v1'}

    def reconcile(self, *, protected_guids=()):
        try:
            with self.transaction():
                data = self.read()
                listed = self.power.list_schemes()
                if not listed.get('success'):
                    return listed
                schemes = listed['schemes']
                results = {}
                for mode in WINDOWS_MODE_SCHEMES:
                    self._discover(data, schemes, mode)
                    candidates = sorted(g for g, row in data['plans'].items()
                        if g in schemes and row.get('mode') == mode and self.owned_record(row)
                        and schemes[g]['name'].casefold() in COREPULSE_PROFILE_ALIASES[mode])
                    if not candidates:
                        continue
                    preferred = data['preferred'].get(mode)
                    keep = preferred if preferred in candidates else candidates[0]
                    data['preferred'][mode] = keep
                    self.save(data)
                    result = self._cleanup(data, mode, keep, set(protected_guids))
                    results[mode] = result
                    if not result.get('success'):
                        return {**result, 'profiles': results}
                return {'success': True, 'profiles': results}
        except Exception as exc:
            logger.exception('No se pudo reconciliar planes; se conservan los ambiguos')
            return {'success': False, 'message': str(exc)}

    @contextmanager
    def transaction(self):
        # OS lock is released even if the process crashes. No stale lock-file recovery.
        with _LOCK:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.with_suffix('.lock').open('a+b') as handle:
                handle.seek(0)
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                try:
                    yield
                finally:
                    handle.seek(0)
                    if os.name == 'nt':
                        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        fcntl.flock(handle, fcntl.LOCK_UN)

    def read(self):
        if not self.path.exists():
            return {'version': 1, 'plans': {}, 'preferred': {}}
        data = json.loads(self.path.read_text(encoding='utf-8'))
        if (data.get('version') != 1 or not isinstance(data.get('plans'), dict)
                or not isinstance(data.get('preferred'), dict)):
            raise ValueError('Registro de planes incompatible; no se crearán ni borrarán planes.')
        return data

    def save(self, data):
        temp = self.path.with_suffix('.' + uuid.uuid4().hex + '.tmp')
        try:
            temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
            os.replace(temp, self.path)
        finally:
            temp.unlink(missing_ok=True)

    @staticmethod
    def owned_record(row):
        mode = row.get('mode')
        return (mode in WINDOWS_MODE_SCHEMES and row.get('owned') is True
                and row.get('base') == WINDOWS_MODE_SCHEMES[mode])

    def owns(self, guid):
        try:
            return self.owned_record(self.read()['plans'].get(guid, {}))
        except Exception:
            logger.exception('No se pudo comprobar procedencia del plan %s', guid)
            return False

    def fingerprint(self, guid):
        """Todos los ajustes visibles/ocultos, no sólo CPU; N/A impide limpiar."""
        result = self.power._run(['powercfg', '/qh', guid])
        if not result.ok:
            logger.warning('%s', friendly_failure(result, 'comparar planes de energía'))
            return None
        matches = list(GUID_RE.finditer(result.stdout))
        values = {}
        for i, match in enumerate(matches):
            end = matches[i + 1].start() if i + 1 < len(matches) else len(result.stdout)
            block = result.stdout[match.end():end]
            if i + 1 < len(matches):
                block = block.rsplit('\n', 1)[0]
            # Los dos índices actuales se imprimen al final del bloque; no
            # confundir índices de opciones posibles con valores activos.
            lines = [line.strip() for line in block.splitlines() if line.strip()]
            if len(lines) < 2:
                continue
            pair = [HEX_RE.search(line) for line in lines[-2:]]
            if HEX_RE.search(block) and not all(pair):
                return None
            if all(pair):
                values[match.group().lower()] = tuple(int(x.group(1), 16) for x in pair)
        return values if MAX_PROCESSOR_STATE in values and BOOST_MODE in values else None

    def compatible(self, guid, mode, base_fingerprint):
        current = self.fingerprint(guid)
        if not current:
            return False
        if base_fingerprint and current == base_fingerprint:
            return True
        # Perfil aplicado por las versiones anteriores. Sólo sirve para
        # reutilizar: no convierte un nombre coincidente en prueba de propiedad.
        max_cpu, boost, epp = {
            'BALANCED': (100, 1, 50), 'HIGH_PERFORMANCE': (100, 1, 20),
            'MAXIMUM_PERFORMANCE': (100, 1, 0), 'POWER_SAVER': (80, 0, 80),
        }[mode]
        return all(current.get(key) == (value, value) for key, value in
                   ((MAX_PROCESSOR_STATE, max_cpu), (BOOST_MODE, boost), (PERF_EPP, epp)))

    def ensure(self, mode, *, protected_guids=(), require_owned=False):
        mode = str(mode or '').strip().upper()
        if mode not in WINDOWS_MODE_SCHEMES:
            return {'success': False, 'message': f'Modo de energía no soportado: {mode}'}
        try:
            with self.transaction():
                return self._ensure(mode, set(protected_guids), require_owned=require_owned)
        except Exception as exc:
            logger.exception('Gestión de planes interrumpida sin crear otra copia')
            return {'success': False, 'message': f'No se pudo gestionar el registro de energía: {exc}'}

    def _ensure(self, mode, protected, *, require_owned=False):
        data = self.read()
        listed = self.power.list_schemes()
        if not listed.get('success'):
            return listed
        schemes = listed['schemes']
        base = WINDOWS_MODE_SCHEMES[mode]
        name = COREPULSE_PROFILE_NAMES[mode]
        self._discover(data, schemes, mode)
        preferred = data['preferred'].get(mode)
        candidates = [guid for guid, record in data['plans'].items()
                      if guid in schemes and record.get('mode') == mode
                      and self.owned_record(record)]
        chosen = preferred if preferred in candidates else next(iter(sorted(candidates)), None)
        # Preferir copia propia conocida para no abandonar su identidad al cambiar parámetros.
        if not chosen:
            legacy = [guid for guid, row in schemes.items()
                      if row['name'].casefold() in COREPULSE_PROFILE_ALIASES[mode]
                      and guid not in WINDOWS_MODE_SCHEMES.values()]
            base_values = self.fingerprint(base) if legacy else None
            for guid in sorted(legacy, key=lambda g: (g != preferred, g)):
                if self.compatible(guid, mode, base_values):
                    chosen = guid
                    data['plans'][guid] = {'mode': mode, 'base': base, 'owned': False, 'state': 'ready'}
                    break
            if legacy and not chosen:
                return {'success': False, 'message': 'Existe un plan con el nombre CorePulse, pero no se pudo verificar su compatibilidad. Se conservó y no se creó otra copia.'}
        if not chosen and base in schemes and not require_owned:
            return {'success': True, 'guid': base, 'mode': mode, 'name': schemes[base]['name'],
                    'created': False, 'builtin': True}
        if not chosen and mode == 'BALANCED' and self.power.scheme_restorer is not None:
            return self.power.restore_missing_balanced()
        created = False
        if not chosen:
            # UUID de destino solicitado, no un GUID de Windows supuesto: /list
            # debe verificar que Windows realmente lo creó antes de usarlo.
            chosen = str(uuid.uuid5(uuid.NAMESPACE_URL, 'corepulse/power/' + mode))
            record = data['plans'].get(chosen, {})
            if chosen in schemes:
                return {'success': False, 'message': 'El GUID reservado ya existe sin procedencia verificable; no se modificó.'}
            if record.get('state') in ('pending', 'failed'):
                return {'success': False, 'message': record.get('error') or 'Creación anterior no confirmada; no se repetirá automáticamente.'}
            data['plans'][chosen] = {'mode': mode, 'base': base, 'owned': True, 'state': 'pending'}
            data['preferred'][mode] = chosen
            self.save(data)
            result = self.power._run(['powercfg', '/duplicatescheme', base, chosen])
            confirmed = self.power.list_schemes()
            if not result.ok or not confirmed.get('success') or chosen not in confirmed['schemes']:
                message = (friendly_failure(result, 'crear el plan de energía') if not result.ok
                           else 'Windows no confirmó el GUID creado; no se repetirá la creación.')
                data['plans'][chosen].update(state='failed', error=message)
                self.save(data)
                logger.error('%s; detalle powercfg: %s', message, result.message())
                return {'success': False, 'message': message}
            schemes = confirmed['schemes']
            created = True
        record = data['plans'][chosen]
        if self.owned_record(record) and (record.get('state') != 'ready' or schemes[chosen]['name'].casefold() not in COREPULSE_PROFILE_ALIASES[mode]):
            renamed = self.power._run(['powercfg', '/changename', chosen, name, self.marker(mode)])
            check = self.power.list_schemes() if renamed.ok else {}
            if not renamed.ok or not check.get('success') or check['schemes'].get(chosen, {}).get('name') != name:
                message = (friendly_failure(renamed, 'nombrar el plan de energía') if not renamed.ok
                           else 'No se pudo verificar el nombre del plan creado.')
                record.update(state='failed', error=message)
                self.save(data)
                logger.error('%s; detalle powercfg: %s', message, renamed.message())
                return {'success': False, 'message': message}
            schemes = check['schemes']
            record.update(state='ready')
            record.pop('error', None)
        record['settings'] = self.power.snapshot_scheme(chosen).get('settings', {})
        data['preferred'][mode] = chosen
        self.save(data)
        cleanup = self._cleanup(data, mode, chosen, protected)
        if not cleanup['success']:
            return cleanup
        return {'success': True, 'guid': chosen, 'mode': mode, 'name': schemes[chosen]['name'],
                'created': created, 'builtin': False, 'corepulse_copy': True,
                'managed_persistent': self.owned_record(record),
                'cleanup': cleanup}

    def _cleanup(self, data, mode, keep, protected):
        removed = []
        candidates = [guid for guid, row in data['plans'].items()
                      if guid != keep and guid not in protected and row.get('mode') == mode
                      and self.owned_record(row) and row.get('state') == 'ready']
        if not candidates or not self.owned_record(data['plans'].get(keep, {})):
            return {'success': True, 'removed': removed}
        listed = self.power.list_schemes()
        if not listed.get('success'):
            return listed
        if listed['schemes'].get(keep, {}).get('name', '').casefold() not in COREPULSE_PROFILE_ALIASES[mode]:
            return {'success': True, 'removed': [], 'skipped': 'Nombre canónico modificado por el usuario'}
        reference = self.fingerprint(keep)
        if not reference:
            return {'success': True, 'removed': [], 'skipped': 'Configuración no verificable'}
        for guid in candidates:
            listed = self.power.list_schemes()
            if not listed.get('success'):
                return listed
            row = listed['schemes'].get(guid, {})
            if row.get('name', '').casefold() not in COREPULSE_PROFILE_ALIASES[mode] or self.fingerprint(guid) != reference:
                continue
            active = self.power.active_scheme()
            if not active.get('success'):
                return active
            if active['guid'] == guid:
                switched = self.power.set_active(keep)
                if not switched.get('success'):
                    return switched
            deleted = self.power.delete_scheme(guid)
            if not deleted.get('success'):
                return deleted
            del data['plans'][guid]
            self.save(data)
            removed.append(guid)
        return {'success': True, 'removed': removed}
