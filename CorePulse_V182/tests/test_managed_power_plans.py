"""Planes simulados: ningún test ejecuta powercfg ni modifica Windows."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor

from core.windows_commands import CommandResult
from performance import power_manager as pm
from performance.profile_manager import PerformanceProfileManager
from tests.test_windows_power_plan_sync import Boost, Detector

MODE = 'MAXIMUM_PERFORMANCE'
NAME = pm.COREPULSE_FALLBACK_NAMES[MODE]
BASE = pm.ULTIMATE_PERFORMANCE_GUID
OTHER = '11111111-2222-3333-4444-555555555555'
SECOND = '22222222-2222-3333-4444-555555555555'
DISK = '6738e2c4-e8a5-4a42-b16a-e040e769756e'


class Windows:
    def __init__(self):
        self.plans = {pm.BALANCED_GUID: 'Equilibrado'}
        self.active = pm.BALANCED_GUID
        self.values = {}
        self.calls = []
        self.fail = None
        self.ambiguous = False
        self.ignore_activation = False

    def settings(self, guid):
        return self.values.setdefault(guid, {pm.MAX_PROCESSOR_STATE: [100, 100],
            pm.BOOST_MODE: [1, 1], pm.PERF_EPP: [0, 0], DISK: [1200, 600]})

    def __call__(self, args, **kwargs):
        args = tuple(args)
        self.calls.append(args)
        verb = args[1]
        def result(ok=True, out=''):
            return CommandResult(ok, args, 0 if ok else 5, out, '' if ok else 'simulated powercfg failure')
        if verb == self.fail and not (verb == '/duplicatescheme' and self.ambiguous):
            return result(False)
        if verb == '/list':
            return result(out='\n'.join(f'Power Scheme GUID: {g} ({n})' + (' *' if g == self.active else '') for g, n in self.plans.items()))
        if verb == '/getactivescheme':
            return result(out=f'Power Scheme GUID: {self.active} ({self.plans[self.active]})')
        if verb == '/duplicatescheme':
            assert len(args) == 4, 'Creation must specify a stable destination'
            base, target = args[2:]
            if target in self.plans:
                return result(False)
            self.plans[target] = 'Template'
            self.values[target] = copy.deepcopy(self.settings(base))
            return result(not self.ambiguous, f'Power Scheme GUID: {target}')
        if verb == '/changename':
            self.plans[args[2]] = args[3]
            return result()
        if verb == '/setactive':
            if args[2] not in self.plans:
                return result(False)
            if not self.ignore_activation:
                self.active = args[2]
            return result()
        if verb == '/delete':
            assert args[2] != self.active, 'Never delete active plan'
            self.plans.pop(args[2], None)
            return result()
        if verb in ('/qh', '/query'):
            return result(out=f'Power Scheme GUID: {args[2]} (Plan)\nSubgroup GUID: {pm.PROCESSOR_SUBGROUP}\n' +
                '\n'.join(f'Power Setting GUID: {g}\nPossible Setting Index: 000\nCurrent AC: 0x{v[0]:08x}\nCurrent DC: 0x{v[1]:08x}' for g, v in self.settings(args[2]).items()))
        if verb in ('/setacvalueindex', '/setdcvalueindex'):
            self.settings(args[2])[args[4]][0 if verb == '/setacvalueindex' else 1] = int(args[5])
            return result()
        raise AssertionError(f'Unexpected command {args}')

    def count(self, verb):
        return sum(c[1] == verb for c in self.calls)


class ManagedPlansTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'plans.json'
        self.windows = Windows()
        self.power = self.new_manager()
        # Guard even against accidentally using a real default runner.
        guard = patch('core.windows_commands.subprocess.run', side_effect=AssertionError('Real process forbidden'))
        guard.start()
        self.addCleanup(guard.stop)

    def new_manager(self):
        mgr = pm.PowerManager(self.windows, registry_path=self.path, description_reader=lambda _: None)
        mgr.available = lambda: True
        return mgr

    def ensure(self, **kwargs):
        return self.power.ensure_mode_scheme(MODE, **kwargs)

    def seed(self, guid, owned=True, state='ready'):
        self.windows.plans[guid] = NAME
        data = self.power.managed_plans.read()
        data['plans'][guid] = {'mode': MODE, 'base': BASE, 'owned': owned, 'state': state}
        data['preferred'].setdefault(MODE, guid)
        self.power.managed_plans.save(data)

    def test_first_creates_second_and_tenth_reuse_after_restart(self):
        first = self.ensure()
        self.assertTrue(first['success'], first)
        self.assertTrue(first['created'])
        for _ in range(9):
            self.power = self.new_manager()
            result = self.ensure()
            self.assertTrue(result['success'], result)
            self.assertEqual(result['guid'], first['guid'])
            self.assertFalse(result['created'])
        self.assertEqual(self.windows.count('/duplicatescheme'), 1)
        self.assertEqual(list(self.windows.plans.values()).count(pm.COREPULSE_PROFILE_NAMES[MODE]), 1)

    def test_valid_persisted_guid_reused_even_after_settings_change(self):
        self.seed(OTHER)
        self.windows.settings(OTHER)[pm.PERF_EPP] = [35, 60]
        self.assertEqual(self.ensure()['guid'], OTHER)
        self.assertEqual(self.windows.count('/duplicatescheme'), 0)

    def test_missing_saved_guid_searches_compatible_legacy_without_ownership(self):
        self.seed(OTHER)
        del self.windows.plans[OTHER]
        self.windows.plans[SECOND] = NAME
        self.assertEqual(self.ensure()['guid'], SECOND)
        self.assertFalse(self.power.managed_plans.owns(SECOND))
        self.assertEqual(self.windows.count('/duplicatescheme'), 0)

    def test_owned_duplicates_consolidate_after_switch_and_verify(self):
        self.seed(OTHER)
        self.seed(SECOND)
        self.windows.active = SECOND
        result = self.ensure()
        self.assertTrue(result['success'], result)
        self.assertEqual(self.windows.active, OTHER)
        self.assertNotIn(SECOND, self.windows.plans)
        verbs = [c[1] for c in self.windows.calls]
        delete = verbs.index('/delete')
        activate = verbs.index('/setactive')
        self.assertIn('/getactivescheme', verbs[activate + 1:delete])

    def test_user_oem_builtin_and_unproven_copies_survive(self):
        self.seed(OTHER)
        self.windows.plans.update({SECOND: NAME, pm.HIGH_PERFORMANCE_GUID: 'Alto rendimiento',
                                  pm.POWER_SAVER_GUID: 'Economizador', BASE: 'Acer OEM'})
        original = dict(self.windows.plans)
        self.assertTrue(self.ensure()['success'])
        self.assertEqual(self.windows.plans, original)
        self.assertFalse(self.power.delete_scheme(SECOND)['success'])
        self.assertFalse(self.power.delete_scheme(BASE)['success'])

    def test_different_disk_setting_prevents_cleanup(self):
        self.seed(OTHER)
        self.seed(SECOND)
        self.windows.settings(SECOND)[DISK] = [10, 20]
        self.assertTrue(self.ensure()['success'])
        self.assertIn(SECOND, self.windows.plans)

    def test_original_plan_protected_from_consolidation(self):
        self.seed(OTHER)
        self.seed(SECOND)
        self.windows.active = SECOND
        self.assertTrue(self.ensure(protected_guids={SECOND})['success'])
        self.assertIn(SECOND, self.windows.plans)

    def test_failed_activation_verification_never_deletes(self):
        self.seed(OTHER)
        self.seed(SECOND)
        self.windows.active = SECOND
        self.windows.ignore_activation = True
        self.assertFalse(self.ensure()['success'])
        self.assertEqual(self.windows.count('/delete'), 0)

    def test_creation_failure_does_not_repeat_even_after_restart(self):
        self.windows.fail = '/duplicatescheme'
        for _ in range(10):
            self.power = self.new_manager()
            self.assertFalse(self.ensure()['success'])
        self.assertEqual(self.windows.count('/duplicatescheme'), 1)

    def test_ambiguous_failure_recovers_actual_created_guid(self):
        self.windows.fail = '/duplicatescheme'
        self.windows.ambiguous = True
        self.assertFalse(self.ensure()['success'])
        self.power = self.new_manager()
        self.assertTrue(self.ensure()['success'])
        self.assertEqual(self.windows.count('/duplicatescheme'), 1)

    def test_failed_rename_retries_same_copy(self):
        self.windows.fail = '/changename'
        self.assertFalse(self.ensure()['success'])
        self.assertFalse(self.ensure()['success'])
        self.windows.fail = None
        self.power = self.new_manager()
        self.assertTrue(self.ensure()['success'])
        self.assertEqual(self.windows.count('/duplicatescheme'), 1)

    def test_list_failure_and_corrupt_registry_fail_closed(self):
        self.windows.fail = '/list'
        self.assertFalse(self.ensure()['success'])
        self.windows.fail = None
        self.path.write_text('{corrupt')
        self.assertFalse(self.ensure()['success'])
        self.assertEqual(self.windows.count('/duplicatescheme'), 0)

    def test_incompatible_namesake_is_preserved_without_new_copy(self):
        self.windows.plans[OTHER] = NAME
        self.windows.settings(OTHER)[pm.PERF_EPP] = [77, 77]
        self.windows.settings(BASE)[pm.PERF_EPP] = [0, 0]
        self.assertFalse(self.ensure()['success'])
        self.assertIn(OTHER, self.windows.plans)
        self.assertEqual(self.windows.count('/duplicatescheme'), 0)

    def test_concurrent_managers_only_create_one(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: self.new_manager().ensure_mode_scheme(MODE), range(10)))
        self.assertTrue(all(r['success'] for r in results), results)
        self.assertEqual(self.windows.count('/duplicatescheme'), 1)

    def test_restore_previous_guid_and_settings(self):
        backup = self.power.snapshot()
        result = self.ensure()
        guid = result['guid']
        self.assertTrue(self.power.apply_gaming(guid, self.power.snapshot_scheme(guid)['settings'])['success'])
        self.assertTrue(self.power.restore({'original': backup['original']})['success'])
        self.assertEqual(self.windows.active, pm.BALANCED_GUID)

    def test_legacy_transaction_backup_can_remove_its_own_copy(self):
        self.windows.plans[OTHER] = NAME
        self.windows.active = OTHER
        backup = {'original': {'active_scheme_guid': pm.BALANCED_GUID},
                  'windows_plan_sync': {'created_schemes': {OTHER: {'mode': MODE, 'name': NAME}}}}
        self.assertTrue(self.power.restore(backup)['success'])
        self.assertNotIn(OTHER, self.windows.plans)

    def test_profile_manual_persists_and_auto_restores(self):
        detector = Detector()
        mgr = PerformanceProfileManager(self.power, detector,
            backup_path=Path(self.tmp.name) / 'backup.json', start_thread=False,
            register_atexit=False, game_boost=Boost())
        self.assertTrue(mgr.set_mode(MODE)['success'])
        chosen = self.windows.active
        self.assertTrue(mgr.shutdown()['success'])
        self.assertEqual(self.windows.active, chosen)
        self.windows.active = pm.BALANCED_GUID
        mgr = PerformanceProfileManager(self.power, detector,
            backup_path=Path(self.tmp.name) / 'auto.json', start_thread=False,
            register_atexit=False, game_boost=Boost())
        self.assertTrue(mgr.set_mode('AUTO')['success'])
        detector.detect_active_games = lambda: [{'pid': 123, 'name': 'test'}]
        mgr.poll_games_once()
        self.assertEqual(self.windows.active, chosen)
        detector.detect_active_games = lambda: []
        mgr.poll_games_once()
        self.assertEqual(self.windows.active, pm.BALANCED_GUID)

    def test_all_modes_share_creation_path(self):
        self.windows.plans.clear()
        for mode in pm.WINDOWS_MODE_SCHEMES:
            first = self.power.ensure_mode_scheme(mode)
            second = self.power.ensure_mode_scheme(mode)
            self.assertTrue(first['success'], first)
            self.assertEqual(first['guid'], second['guid'])
        self.assertEqual(self.windows.count('/duplicatescheme'), 4)

    def test_auto_first_creation_survives_restore_and_next_session(self):
        detector = Detector()
        mgr = PerformanceProfileManager(self.power, detector,
            backup_path=Path(self.tmp.name) / 'fresh-auto.json', start_thread=False,
            register_atexit=False, game_boost=Boost())
        self.assertTrue(mgr.set_mode('AUTO')['success'])
        for _ in range(3):
            detector.detect_active_games = lambda: [{'pid': 123, 'name': 'test'}]
            mgr.poll_games_once()
            self.assertNotEqual(self.windows.active, pm.BALANCED_GUID)
            detector.detect_active_games = lambda: []
            mgr.poll_games_once()
            self.assertEqual(self.windows.active, pm.BALANCED_GUID)
        self.assertEqual(self.windows.count('/duplicatescheme'), 1)
        self.assertEqual(self.windows.count('/delete'), 0)

    def test_cleanup_error_is_not_success(self):
        self.seed(OTHER)
        self.seed(SECOND)
        self.windows.fail = '/delete'
        self.assertFalse(self.ensure()['success'])
        self.assertIn(SECOND, self.windows.plans)
        self.assertEqual(self.windows.count('/duplicatescheme'), 0)

    def test_unavailable_full_query_prevents_cleanup(self):
        self.seed(OTHER)
        self.seed(SECOND)
        self.windows.fail = '/qh'
        self.assertTrue(self.ensure()['success'])
        self.assertEqual(self.windows.count('/delete'), 0)

    def test_namesake_is_not_classified_as_owned_mode(self):
        self.windows.plans[OTHER] = NAME
        self.windows.active = OTHER
        self.assertIsNone(self.power.active_windows_plan()['mode'])


if __name__ == '__main__':
    unittest.main()
