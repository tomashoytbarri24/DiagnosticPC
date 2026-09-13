"""Control seguro, reversible y sincronizado con los planes de energía de Windows.

V0.10.2.53w:
- Cada modo visible de CorePulse activa un plan REAL de Windows con powercfg /setactive.
- Se verifica el GUID activo después de cada cambio.
- Si un plan estándar no existe, CorePulse intenta duplicar la plantilla oficial.
  En perfiles manuales confirmados esa copia permanece disponible en Windows; sólo
  una transacción incompleta/fallida utiliza rollback para eliminarla.
- Los ajustes CPU/Boost/EPP sólo se modifican cuando pudieron respaldarse en el
  plan de destino. Si el OEM no los expone, el cambio de plan sigue funcionando
  y CorePulse informa modo compatible/parcial en lugar de inventar éxito total.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, Optional

from core.windows_commands import CommandResult, friendly_failure, run_hidden

logger = logging.getLogger('CorePulse.Power')

PROCESSOR_SUBGROUP = '54533251-82be-4824-96c1-47b60b740d00'
MAX_PROCESSOR_STATE = 'bc5038f7-23e0-4960-96da-33abaf5935ec'
BOOST_MODE = 'be337238-0d82-4146-a960-4f3749d470c7'
PERF_EPP = '36687f9e-e3a5-4dbf-b1dc-15eb381c6863'

BALANCED_GUID = '381b4222-f694-41f0-9685-ff5bb260df2e'
HIGH_PERFORMANCE_GUID = '8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c'
POWER_SAVER_GUID = 'a1841308-3541-4fab-bc81-f71556f20b4a'
ULTIMATE_PERFORMANCE_GUID = 'e9a42b02-d5df-448d-aa00-03f14749eb61'
BALANCED_ALIAS = 'SCHEME_BALANCED'

WINDOWS_MODE_SCHEMES = {
    'BALANCED': BALANCED_GUID,
    'HIGH_PERFORMANCE': HIGH_PERFORMANCE_GUID,
    'MAXIMUM_PERFORMANCE': ULTIMATE_PERFORMANCE_GUID,
    'POWER_SAVER': POWER_SAVER_GUID,
}
WINDOWS_MODE_LABELS = {
    'BALANCED': 'Equilibrado',
    'HIGH_PERFORMANCE': 'Alto rendimiento',
    'MAXIMUM_PERFORMANCE': 'Máximo rendimiento',
    'POWER_SAVER': 'Ahorro de energía',
}
COREPULSE_FALLBACK_NAMES = {
    mode: f"CorePulse - {label}" for mode, label in WINDOWS_MODE_LABELS.items()
}

GUID_RE = re.compile(r'(?i)\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b')
HEX_RE = re.compile(r'(?i)0x([0-9a-f]+)')
PAREN_NAME_RE = re.compile(r'\(([^()]*)\)')


class PowerManager:
    def __init__(self, runner=run_hidden):
        self.runner = runner

    def _run(self, args, timeout=12) -> CommandResult:
        return self.runner(args, timeout=timeout, category='POWER')

    def available(self) -> bool:
        return os.name == 'nt'

    def active_scheme(self) -> Dict[str, Any]:
        if not self.available():
            return {'success': False, 'guid': None, 'message': 'powercfg sólo está disponible en Windows.'}
        result = self._run(['powercfg', '/getactivescheme'])
        if not result.ok:
            return {'success': False, 'guid': None, 'message': friendly_failure(result, 'consultar el plan de energía'), 'result': result}
        match = GUID_RE.search(result.stdout)
        if not match:
            logger.error('[POWER] No se pudo extraer GUID de /getactivescheme: %s', result.stdout[:1000])
            return {'success': False, 'guid': None, 'message': 'Windows respondió sin un GUID de plan de energía reconocible.'}
        return {'success': True, 'guid': match.group(0).lower(), 'raw': result.stdout}

    def list_schemes(self) -> Dict[str, Any]:
        """Enumera planes existentes sin depender del idioma de Windows."""
        if not self.available():
            return {'success': False, 'schemes': {}, 'message': 'Los planes de energía sólo están disponibles en Windows.'}
        result = self._run(['powercfg', '/list'])
        if not result.ok:
            return {'success': False, 'schemes': {}, 'message': friendly_failure(result, 'listar los planes de energía'), 'result': result}
        schemes: Dict[str, Dict[str, Any]] = {}
        for line in str(result.stdout or '').splitlines():
            match = GUID_RE.search(line)
            if not match:
                continue
            guid = match.group(0).lower()
            tail = line[match.end():]
            name_match = PAREN_NAME_RE.search(tail)
            name = (name_match.group(1).strip() if name_match else '').strip()
            schemes[guid] = {
                'guid': guid,
                'name': name or guid,
                'active': '*' in tail,
                'raw': line.strip(),
            }
        return {'success': True, 'schemes': schemes, 'raw': result.stdout}

    def mode_for_scheme(self, guid: Optional[str], schemes: Optional[Dict[str, Any]] = None) -> Optional[str]:
        token = str(guid or '').lower().strip()
        for mode, builtin in WINDOWS_MODE_SCHEMES.items():
            if token == builtin:
                return mode
        rows = schemes or {}
        row = rows.get(token) or {}
        name = str(row.get('name') or '').strip().casefold()
        if name:
            for mode, custom_name in COREPULSE_FALLBACK_NAMES.items():
                if name == custom_name.casefold():
                    return mode
        return None

    def active_windows_plan(self) -> Dict[str, Any]:
        active = self.active_scheme()
        if not active.get('success'):
            return active
        listed = self.list_schemes()
        schemes = listed.get('schemes') if listed.get('success') else {}
        guid = str(active.get('guid') or '').lower()
        row = (schemes or {}).get(guid) or {}
        mode = self.mode_for_scheme(guid, schemes)
        return {
            'success': True,
            'guid': guid,
            'name': row.get('name') or guid,
            'mode': mode,
            'known_mode': bool(mode),
            'list_success': bool(listed.get('success')),
        }

    def _duplicate_scheme(self, template_guid: str, display_name: str) -> Dict[str, Any]:
        result = self._run(['powercfg', '/duplicatescheme', str(template_guid)])
        if not result.ok:
            return {'success': False, 'message': friendly_failure(result, f'crear el plan {display_name}'), 'result': result}
        match = GUID_RE.search(result.stdout or '')
        if not match:
            return {'success': False, 'message': f'Windows creó el plan {display_name}, pero no devolvió un GUID verificable.'}
        guid = match.group(0).lower()
        renamed = self._run(['powercfg', '/changename', guid, display_name])
        if not renamed.ok:
            logger.warning('[POWER] El plan %s fue creado (%s) pero no pudo renombrarse', display_name, guid)
        return {'success': True, 'guid': guid, 'created': True, 'name': display_name, 'renamed': bool(renamed.ok)}

    def ensure_mode_scheme(self, mode: str) -> Dict[str, Any]:
        mode = str(mode or '').upper().strip()
        template_guid = WINDOWS_MODE_SCHEMES.get(mode)
        if not template_guid:
            return {'success': False, 'message': f'Modo de energía no soportado: {mode}'}

        listed = self.list_schemes()
        if not listed.get('success'):
            return listed
        schemes = listed.get('schemes') or {}

        # Preferir siempre el plan estándar de Windows si existe.
        if template_guid in schemes:
            row = schemes[template_guid]
            return {
                'success': True,
                'mode': mode,
                'guid': template_guid,
                'name': row.get('name') or WINDOWS_MODE_LABELS[mode],
                'created': False,
                'builtin': True,
            }

        # Reutilizar una copia CorePulse creada anteriormente para evitar duplicados.
        expected_name = COREPULSE_FALLBACK_NAMES[mode].casefold()
        for guid, row in schemes.items():
            if str(row.get('name') or '').strip().casefold() == expected_name:
                return {
                    'success': True,
                    'mode': mode,
                    'guid': guid,
                    'name': row.get('name') or COREPULSE_FALLBACK_NAMES[mode],
                    'created': False,
                    'builtin': False,
                    'corepulse_copy': True,
                }

        # Si el plan no está instalado/visible, duplicar la plantilla oficial.
        created = self._duplicate_scheme(template_guid, COREPULSE_FALLBACK_NAMES[mode])
        if not created.get('success'):
            created['message'] = (
                f"Windows no tiene disponible el plan {WINDOWS_MODE_LABELS[mode]} y CorePulse no pudo crear una copia compatible. "
                + str(created.get('message') or '')
            ).strip()
            return created
        return {
            'success': True,
            'mode': mode,
            'guid': created['guid'],
            'name': created.get('name') or COREPULSE_FALLBACK_NAMES[mode],
            'created': True,
            'builtin': False,
            'corepulse_copy': True,
        }

    @staticmethod
    def _parse_ac_dc(output: str) -> Optional[Dict[str, int]]:
        values = [int(x, 16) for x in HEX_RE.findall(str(output or ''))]
        if len(values) < 2:
            return None
        return {'ac': values[-2], 'dc': values[-1]}

    @staticmethod
    def _setting_block(output: str, setting: str) -> Optional[str]:
        raw = str(output or '')
        low = raw.lower()
        token = str(setting or '').lower()
        pos = low.find(token)
        if pos < 0:
            return None
        tail = raw[pos + len(token):]
        nxt = GUID_RE.search(tail)
        end = pos + len(token) + (nxt.start() if nxt else len(tail))
        return raw[pos:end]

    def query_setting(self, scheme: str, setting: str) -> Dict[str, Any]:
        attempts = []
        for verb in ('/qh', '/query'):
            result = self._run(['powercfg', verb, str(scheme), PROCESSOR_SUBGROUP])
            attempts.append(result)
            if not result.ok:
                continue
            block = self._setting_block(result.stdout, setting)
            if block is None:
                continue
            parsed = self._parse_ac_dc(block)
            if parsed is not None:
                return {'success': True, **parsed, 'query_mode': verb}
        last = attempts[-1] if attempts else None
        if last is not None and not last.ok:
            message = friendly_failure(last, 'consultar la configuración del procesador')
        else:
            message = 'Windows no expuso este ajuste de energía con valores AC/DC interpretables.'
        return {'success': False, 'message': message, 'attempts': attempts}

    def snapshot_scheme(self, guid: str) -> Dict[str, Any]:
        settings: Dict[str, Any] = {}
        unavailable: Dict[str, str] = {}
        for name, setting in (
            ('max_processor_state', MAX_PROCESSOR_STATE),
            ('boost_mode', BOOST_MODE),
            ('energy_performance_preference', PERF_EPP),
        ):
            row = self.query_setting(guid, setting)
            if row.get('success'):
                settings[name] = {
                    'setting_guid': setting,
                    'ac': int(row['ac']),
                    'dc': int(row['dc']),
                    'query_mode': row.get('query_mode'),
                }
            else:
                unavailable[name] = row.get('message') or 'No disponible'
        capabilities = {
            'max_processor_state': 'max_processor_state' in settings,
            'boost_mode': 'boost_mode' in settings,
            'energy_performance_preference': 'energy_performance_preference' in settings,
        }
        return {
            'success': True,
            'guid': str(guid).lower(),
            'settings': settings,
            'unavailable': unavailable,
            'capabilities': capabilities,
            'partial': not all(capabilities.values()),
        }

    def snapshot(self) -> Dict[str, Any]:
        """Guarda el plan activo exacto y, cuando sea posible, sus ajustes.

        Desde V0.10.2.53w el rollback del PLAN no depende de que el OEM exponga
        PERFBOOSTMODE/EPP: conocer el GUID activo basta para restaurar el plan.
        """
        active = self.active_scheme()
        if not active.get('success'):
            return {'success': False, 'message': active.get('message'), 'original': None}
        guid = active['guid']
        snap = self.snapshot_scheme(guid)
        return {
            'success': True,
            'partial': bool(snap.get('partial')),
            'message': (
                'Plan de energía y ajustes reversibles respaldados.'
                if not snap.get('partial')
                else 'Plan de energía respaldado; algunos ajustes avanzados no son legibles en este equipo/OEM.'
            ),
            'original': {
                'active_scheme_guid': guid,
                'settings': snap.get('settings') or {},
                'unavailable': snap.get('unavailable') or {},
                'capabilities': snap.get('capabilities') or {},
            },
        }

    def _set_value(self, scheme: str, setting: str, ac: Optional[int] = None, dc: Optional[int] = None) -> Dict[str, Any]:
        changes = []
        if ac is not None:
            r = self._run(['powercfg', '/setacvalueindex', scheme, PROCESSOR_SUBGROUP, setting, str(int(ac))])
            changes.append(('AC', r))
            if not r.ok:
                return {'success': False, 'message': friendly_failure(r, 'aplicar la configuración AC del procesador'), 'changes': changes}
        if dc is not None:
            r = self._run(['powercfg', '/setdcvalueindex', scheme, PROCESSOR_SUBGROUP, setting, str(int(dc))])
            changes.append(('DC', r))
            if not r.ok:
                return {'success': False, 'message': friendly_failure(r, 'aplicar la configuración DC del procesador'), 'changes': changes}
        return {'success': True, 'changes': changes}

    def set_active(self, scheme: str, *, verify: bool = True) -> Dict[str, Any]:
        target = str(scheme).lower().strip()
        r = self._run(['powercfg', '/setactive', target])
        if not r.ok:
            return {'success': False, 'message': friendly_failure(r, 'activar el plan de energía'), 'result': r}
        if not verify:
            return {'success': True, 'guid': target}
        current = self.active_scheme()
        if not current.get('success'):
            return {'success': False, 'message': 'Windows aceptó el cambio, pero CorePulse no pudo verificar qué plan quedó activo.'}
        if str(current.get('guid') or '').lower() != target:
            return {
                'success': False,
                'message': 'Windows no dejó activo el plan solicitado. CorePulse no marcará el cambio como aplicado.',
                'requested_guid': target,
                'active_guid': current.get('guid'),
            }
        return {'success': True, 'guid': target, 'verified': True}

    def delete_scheme(self, scheme: str) -> Dict[str, Any]:
        guid = str(scheme or '').lower().strip()
        if not GUID_RE.fullmatch(guid):
            return {'success': False, 'message': 'GUID de plan inválido; no se eliminó nada.'}
        r = self._run(['powercfg', '/delete', guid])
        if not r.ok:
            return {'success': False, 'message': friendly_failure(r, 'eliminar el plan temporal de CorePulse'), 'result': r}
        return {'success': True, 'guid': guid}

    def restore_scheme_settings(self, scheme: str, settings: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        for key in ('max_processor_state', 'boost_mode', 'energy_performance_preference'):
            item = (settings or {}).get(key) or {}
            if item.get('setting_guid') is None:
                continue
            if item.get('ac') is None and item.get('dc') is None:
                continue
            result = self._set_value(scheme, item.get('setting_guid'), item.get('ac'), item.get('dc'))
            if not result.get('success'):
                return result
        return {'success': True}

    def _apply_profile_values(
        self, scheme: str, settings: Optional[Dict[str, Any]], *,
        profile: str, label: str, max_cpu: int, boost_value: Optional[int], epp_value: Optional[int],
    ) -> Dict[str, Any]:
        """Ajusta sólo valores respaldados del plan de destino y lo activa en Windows."""
        logger.info('[PROFILE] Activando plan Windows %s (%s)', label, scheme)
        settings = settings or {}
        operations = []
        if 'max_processor_state' in settings:
            operations.append((MAX_PROCESSOR_STATE, int(max_cpu), int(max_cpu), f'Estado máximo CPU -> {int(max_cpu)}%'))
        boost_managed = 'boost_mode' in settings and boost_value is not None
        epp_managed = 'energy_performance_preference' in settings and epp_value is not None
        if boost_managed:
            operations.append((BOOST_MODE, int(boost_value), int(boost_value), f'Boost -> {int(boost_value)}'))
        if epp_managed:
            operations.append((PERF_EPP, int(epp_value), int(epp_value), f'EPP CPU -> {int(epp_value)}'))

        for setting, ac, dc, op_label in operations:
            row = self._set_value(scheme, setting, ac, dc)
            if not row.get('success'):
                logger.error('[ERROR][POWER] %s: %s', op_label, row.get('message'))
                return row

        active = self.set_active(scheme)
        if not active.get('success'):
            return active

        partial = not ('max_processor_state' in settings and (boost_value is None or boost_managed) and (epp_value is None or epp_managed))
        parts = [f'plan de Windows {label} activo y verificado']
        if 'max_processor_state' in settings:
            parts.append(f'CPU máximo {int(max_cpu)}%')
        else:
            parts.append('CPU avanzada conservada por compatibilidad')
        if boost_value is not None:
            parts.append(('Turbo Boost administrado' if boost_managed else 'Turbo Boost conservado'))
        if epp_value is not None:
            parts.append((f'EPP {int(epp_value)}' if epp_managed else 'EPP conservado'))

        return {
            'success': True,
            'profile': profile,
            'windows_plan_guid': str(scheme).lower(),
            'windows_plan_verified': True,
            'partial': bool(partial),
            'boost_managed': bool(boost_managed),
            'epp_managed': bool(epp_managed),
            'message': f'{label}: ' + ', '.join(parts) + '.',
        }

    def apply_balanced(self, scheme: str, settings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._apply_profile_values(scheme, settings, profile='BALANCED', label='Equilibrado', max_cpu=100, boost_value=1, epp_value=50)

    def apply_high_performance(self, scheme: str, settings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._apply_profile_values(scheme, settings, profile='HIGH_PERFORMANCE', label='Alto rendimiento', max_cpu=100, boost_value=1, epp_value=20)

    def apply_maximum_performance(self, scheme: str, settings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._apply_profile_values(scheme, settings, profile='MAXIMUM_PERFORMANCE', label='Máximo rendimiento', max_cpu=100, boost_value=1, epp_value=0)

    def apply_power_saver(self, scheme: str, settings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._apply_profile_values(scheme, settings, profile='POWER_SAVER', label='Ahorro de energía', max_cpu=80, boost_value=0, epp_value=80)

    def apply_gaming(self, scheme: str, settings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self.apply_maximum_performance(scheme, settings)

    def apply_cool(self, scheme: str, settings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self.apply_power_saver(scheme, settings)

    def restore(self, backup: Dict[str, Any]) -> Dict[str, Any]:
        original = (backup or {}).get('original') if isinstance(backup, dict) else None
        if not isinstance(original, dict):
            return {'success': False, 'message': 'No existe una copia de configuración válida para restaurar.'}
        original_scheme = str(original.get('active_scheme_guid') or '').lower().strip()
        if not original_scheme:
            return {'success': False, 'message': 'La copia no contiene el plan de energía original.'}

        sync = (backup or {}).get('windows_plan_sync') or {}
        snapshots = sync.get('scheme_snapshots') or {}
        created = sync.get('created_schemes') or {}

        # Restaurar ajustes de cualquier plan existente que CorePulse haya tocado.
        for guid, row in snapshots.items():
            restored = self.restore_scheme_settings(guid, (row or {}).get('settings') or {})
            if not restored.get('success'):
                return {
                    'success': False,
                    'message': f'No se pudieron restaurar los ajustes originales del plan {guid}: {restored.get("message")}',
                }

        # Compatibilidad con backups V0.10.2.53w y anteriores.
        if not snapshots and original.get('settings'):
            restored = self.restore_scheme_settings(original_scheme, original.get('settings') or {})
            if not restored.get('success'):
                return restored

        active = self.set_active(original_scheme)
        if not active.get('success'):
            return active

        # Sólo después de volver al plan original es seguro borrar copias creadas.
        cleanup_errors = []
        for guid, row in created.items():
            guid = str(guid).lower()
            if guid == original_scheme:
                continue
            deleted = self.delete_scheme(guid)
            if not deleted.get('success'):
                cleanup_errors.append(deleted.get('message') or guid)

        if cleanup_errors:
            return {
                'success': False,
                'partial': True,
                'message': 'El plan original fue restaurado, pero quedó una copia temporal de CorePulse sin eliminar: ' + ' | '.join(cleanup_errors),
            }

        logger.info('[PROFILE] Plan y configuración de energía originales restaurados')
        return {
            'success': True,
            'profile': self.mode_for_scheme(original_scheme),
            'windows_plan_guid': original_scheme,
            'windows_plan_verified': True,
            'message': 'Plan de energía y configuración anterior restaurados.',
        }

    def activate_balanced_default(self) -> Dict[str, Any]:
        ensured = self.ensure_mode_scheme('BALANCED')
        if not ensured.get('success'):
            return ensured
        active = self.set_active(ensured['guid'])
        if active.get('success'):
            return {
                'success': True,
                'profile': 'BALANCED',
                'windows_plan_guid': ensured['guid'],
                'message': 'Plan Equilibrado de Windows activado y verificado.',
            }
        return active
