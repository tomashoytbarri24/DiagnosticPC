"""Ejecuta el enrutador real sin iniciar Tk, servicios ni hardware."""

import pytest
pytest.importorskip("customtkinter", reason="GUI dependency not installed in this validation environment")

import ast
from pathlib import Path
import types
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]


def router(namespace):
    tree = ast.parse((ROOT / 'main.py').read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'App')
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'open_health_center')
    exec(compile(ast.Module(body=[method], type_ignores=[]), 'main.py', 'exec'), namespace)
    return namespace['open_health_center']


class NavigationTests(unittest.TestCase):
    def app(self):
        return types.SimpleNamespace(is_running=True, _prime_battery_presence_cache=Mock(),
            _internal_page_cache={}, health_center_panel=None, _defer_ui_call=Mock())

    def test_audio_reaches_existing_page_from_actual_entrypoint(self):
        from gui.audio_test_panel import open_audio_test
        app = self.app()
        panel = Mock()
        app.health_center_panel = panel
        app._internal_page_cache = {'health_center': {'panel': panel}}
        namespace = {'activate_internal_page': Mock(return_value=(object(), True))}
        app.open_health_center = types.MethodType(router(namespace), app)
        open_audio_test(app)
        self.assertTrue(panel.navigate_to.call_args_list)
        for call in panel.navigate_to.call_args_list:
            self.assertEqual(call.args, ('audio', 'summary'))

    def test_audio_reaches_new_page_as_initial_destination(self):
        app = self.app()
        host = object()
        namespace = {'activate_internal_page': Mock(return_value=(host, False)),
                     'commit_internal_page': Mock(return_value=True),
                     'abort_internal_page': Mock(), 'cp_error': Mock()}
        with patch('gui.health_center_panel.HealthCenterPanel') as factory:
            router(namespace)(app, tab='audio')
        self.assertEqual(factory.call_args.kwargs['initial_tab'], 'audio')
        namespace['cp_error'].assert_not_called()

    def test_card_has_audio_identity(self):
        from gui.health_center_panel import HealthCenterPanel
        profile = HealthCenterPanel._health_module_visual_profile(None, 'Test de Audio')
        self.assertEqual(profile['icon'], '🎧')
        self.assertEqual(profile['category'], 'Sonido y micrófono')


if __name__ == '__main__':
    unittest.main()
