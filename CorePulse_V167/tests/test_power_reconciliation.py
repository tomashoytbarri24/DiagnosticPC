"""Nombres Game/Turbo, procedencia histórica y reconciliación sin Windows real."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from performance import power_manager as pm
from performance.profile_manager import PerformanceProfileManager
from tests.test_managed_power_plans import Windows, OTHER, SECOND, DISK
from tests.test_windows_power_plan_sync import Detector, Boost

THIRD = '33333333-2222-3333-4444-555555555555'
OEM = '44444444-2222-3333-4444-555555555555'
GAME = 'HIGH_PERFORMANCE'
TURBO = 'MAXIMUM_PERFORMANCE'


class MarkedWindows(Windows):
    def __init__(self):
        super().__init__()
        self.descriptions = {}

    def __call__(self, args, **kwargs):
        result = super().__call__(args, **kwargs)
        if result.ok and args[1] == '/changename' and len(args) == 5:
            self.descriptions[args[2]] = args[4]
        return result


class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'plans.json'
        self.windows = MarkedWindows()
        self.power = self.manager()
        blocker = patch('core.windows_commands.subprocess.run', side_effect=AssertionError('Real commands forbidden'))
        blocker.start()
        self.addCleanup(blocker.stop)

    def manager(self):
        power = pm.PowerManager(self.windows, registry_path=self.path,
                               description_reader=self.windows.descriptions.get)
        power.available = lambda: True
        return power

    def historical(self, guid, mode=GAME, marked=True):
        self.windows.plans[guid] = pm.COREPULSE_PROFILE_NAMES[mode]
        self.windows.settings(guid)[pm.PERF_EPP] = [20, 20] if mode == GAME else [0, 0]
        if marked:
            self.windows.descriptions[guid] = self.power.managed_plans.marker(mode)

    def test_missing_game_created_once_for_ten_activations(self):
        for _ in range(10):
            self.power = self.manager()
            ensured = self.power.ensure_owned_profile('Game')
            self.assertTrue(ensured['success'], ensured)
            self.assertTrue(self.power.set_active(ensured['guid'])['success'])
        self.assertEqual(self.windows.count('/duplicatescheme'), 1)
        self.assertEqual(list(self.windows.plans.values()).count('CorePulse Game'), 1)

    def test_existing_game_reused_without_duplicate(self):
        self.historical(OTHER, marked=False)
        result = self.power.ensure_owned_profile('CorePulse Game')
        self.assertEqual(result['guid'], OTHER)
        self.assertFalse(self.power.managed_plans.owns(OTHER))
        self.assertEqual(self.windows.count('/duplicatescheme'), 0)

    def test_three_marked_historical_copies_consolidate_without_registry(self):
        for guid in (OTHER, SECOND, THIRD):
            self.historical(guid)
        result = self.power.reconcile_owned_profiles()
        self.assertTrue(result['success'], result)
        self.assertEqual(list(self.windows.plans.values()).count('CorePulse Game'), 1)
        self.assertEqual(self.windows.count('/delete'), 2)
        self.assertEqual(self.windows.count('/duplicatescheme'), 0)

    def test_balanced_oem_and_user_survive(self):
        self.windows.plans[OEM] = 'Acer Customized'
        self.historical(OTHER)
        self.historical(SECOND)
        self.windows.plans[THIRD] = 'CorePulse Game personalizado'
        self.assertTrue(self.power.reconcile_owned_profiles()['success'])
        self.assertEqual(self.windows.plans[pm.BALANCED_GUID], 'Equilibrado')
        self.assertEqual(self.windows.plans[OEM], 'Acer Customized')
        self.assertIn(THIRD, self.windows.plans)
        self.assertEqual(list(self.windows.plans.values()).count('CorePulse Game'), 1)

    def test_active_duplicate_switched_and_verified_before_delete(self):
        self.historical(OTHER)
        self.historical(SECOND)
        self.windows.active = SECOND
        self.assertTrue(self.power.reconcile_owned_profiles()['success'])
        calls = [c[1] for c in self.windows.calls]
        self.assertLess(calls.index('/setactive'), calls.index('/delete'))
        self.assertIn('/getactivescheme', calls[calls.index('/setactive') + 1:calls.index('/delete')])
        self.assertEqual(self.windows.active, OTHER)

    def test_ambiguous_unmarked_copies_kept(self):
        self.historical(OTHER, marked=False)
        self.historical(SECOND, marked=False)
        self.assertTrue(self.power.reconcile_owned_profiles()['success'])
        self.assertEqual(self.windows.count('/delete'), 0)
        self.assertEqual(self.power.ensure_owned_profile('Game')['guid'], OTHER)
        self.assertEqual(self.windows.count('/duplicatescheme'), 0)

    def test_game_and_turbo_remain_distinct(self):
        game = self.power.ensure_owned_profile('Game')
        turbo = self.power.ensure_owned_profile('Turbo')
        self.assertNotEqual(game['guid'], turbo['guid'])
        self.assertTrue(self.power.reconcile_owned_profiles()['success'])
        self.assertEqual(self.windows.plans[game['guid']], 'CorePulse Game')
        self.assertEqual(self.windows.plans[turbo['guid']], 'CorePulse Turbo Performance')

    def test_previous_canonical_guid_is_preferred(self):
        self.historical(SECOND)
        self.assertEqual(self.power.ensure_owned_profile('Game')['guid'], SECOND)
        self.historical(OTHER)
        self.assertTrue(self.power.reconcile_owned_profiles()['success'])
        self.assertIn(SECOND, self.windows.plans)
        self.assertNotIn(OTHER, self.windows.plans)

    def test_different_settings_survive_even_with_marker(self):
        self.historical(OTHER)
        self.historical(SECOND)
        self.windows.settings(SECOND)[DISK] = [999, 888]
        self.assertTrue(self.power.reconcile_owned_profiles()['success'])
        self.assertEqual(self.windows.count('/delete'), 0)

    def test_failed_switch_prevents_deletion(self):
        self.historical(OTHER)
        self.historical(SECOND)
        self.windows.active = SECOND
        self.windows.ignore_activation = True
        self.assertFalse(self.power.reconcile_owned_profiles()['success'])
        self.assertEqual(self.windows.count('/delete'), 0)

    def test_wrong_profile_marker_is_not_ownership(self):
        self.historical(OTHER)
        self.historical(SECOND)
        self.windows.descriptions[SECOND] = self.power.managed_plans.marker(TURBO)
        self.assertTrue(self.power.reconcile_owned_profiles()['success'])
        self.assertIn(SECOND, self.windows.plans)
        self.assertFalse(self.power.managed_plans.owns(SECOND))

    def test_registered_alias_survives_without_renaming(self):
        self.historical(OTHER)
        self.windows.plans[OTHER] = pm.COREPULSE_FALLBACK_NAMES[GAME]
        ensured = self.power.ensure_owned_profile('Game')
        self.assertEqual(ensured['guid'], OTHER)
        self.assertEqual(self.windows.count('/changename'), 0)

    def test_modes_use_separate_plans_and_polling_is_throttled(self):
        manager = PerformanceProfileManager(self.power, Detector(),
            backup_path=Path(self.tmp.name) / 'backup.json', start_thread=False,
            register_atexit=False, game_boost=Boost())
        self.assertTrue(manager.set_mode(GAME)['success'])
        game = self.windows.active
        self.assertTrue(manager.set_mode(TURBO)['success'])
        turbo = self.windows.active
        self.assertNotEqual(game, turbo)
        self.windows.calls.clear()
        for _ in range(10):
            manager.poll_games_once()
        self.assertEqual(self.windows.calls, [])
        manager._last_windows_plan_poll -= 31
        manager.poll_games_once()
        self.assertEqual(self.windows.count('/getactivescheme'), 1)
        self.assertEqual(self.windows.count('/duplicatescheme'), 0)


if __name__ == '__main__':
    unittest.main()
