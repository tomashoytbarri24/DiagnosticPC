"""Audio simulado exclusivamente: ninguna prueba abre hardware real."""
import ast
import ctypes as C
from contextlib import contextmanager
import copy
import json
import struct
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

from core.audio_test import AudioTest, recent_audio_result, summary, evidence_rows
from core.windows_audio import AudioError, WindowsAudio, tone, decode, encode, parse_format
from core.diagnostic_summary import build_component_assessments, build_component_evidence


class Provider:
    def __init__(self):
        self.info = {k: {'available': True, 'id': k + '-real-id', 'name': k + ' device', 'stereo': True}
                     for k in ('output', 'input')}
        self.calls = []
        self.failure = None
        self.signal = .2

    def devices(self):
        self.calls.append('devices')
        return copy.deepcopy(self.info)

    def default_ids(self):
        self.calls.append('ids')
        return {k: v['id'] for k, v in self.info.items()}

    def play(self, channel, expected, cancel, recording=None):
        self.calls.append('play')
        if self.failure:
            raise AudioError(self.failure)
        if cancel.is_set():
            raise AudioError('Cancelado')

    def record(self, expected, cancel, on_level):
        self.calls.append('record')
        if self.failure:
            raise AudioError(self.failure)
        on_level(self.signal)
        return [self.signal] * 500, 100


class AudioTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'result.json'
        self.provider = Provider()
        self.service = AudioTest(self.provider, self.path)
        blocker = patch('core.windows_audio.endpoint', side_effect=AssertionError('Real audio prohibited'))
        blocker.start()
        self.addCleanup(blocker.stop)

    def test_detection_does_not_play_or_record(self):
        devices = self.service.refresh()
        self.assertEqual(devices['output']['name'], 'output device')
        self.assertEqual(devices['input']['name'], 'input device')
        self.assertEqual(self.provider.calls, ['devices'])
        self.assertEqual(summary(self.service.result), 'NO EVALUADO')

    def test_output_missing(self):
        self.provider.info['output'].update(available=False, id=None, name='N/A')
        with self.assertRaises(AudioError):
            self.service.play('left')
        self.assertNotIn('play', self.provider.calls)

    def test_microphone_missing(self):
        self.provider.info['input'].update(available=False, id=None, name='N/A')
        with self.assertRaises(AudioError):
            self.service.record(lambda _: None)
        self.assertNotIn('record', self.provider.calls)

    def test_api_success_alone_is_not_verified(self):
        self.service.play('left')
        self.assertEqual(summary(self.service.result), 'NO EVALUADO')
        self.assertTrue(self.service.result['technical']['left']['api_completed'])

    def test_yes_no_unsure(self):
        for answer, expected in [('Sí', 'VERIFICADO'), ('No', 'PROBLEMA REPORTADO'), ('No estoy seguro', 'NO CONCLUYENTE')]:
            self.service.play('right')
            self.service.confirm(answer)
            self.assertEqual(self.service.result['answers']['right'], expected)

    def test_cannot_confirm_without_completed_playback(self):
        with self.assertRaises(AudioError):
            self.service.confirm('Sí')

    def test_real_sample_level_and_memory_cleanup(self):
        levels = []
        self.service.record(levels.append)
        self.assertEqual(levels, [.2])
        capture = self.service.result['technical']['capture']
        self.assertTrue(capture['signal_detected'])
        self.assertEqual(capture['duration_s'], 5)
        samples = self.service.recording[0]
        self.service.close()
        self.assertEqual(samples, [])
        self.assertIsNone(self.service.recording)
        self.assertEqual([p.name for p in self.path.parent.iterdir()], ['result.json'])
        self.assertNotIn('recording', json.loads(self.path.read_text()))

    def test_silence_does_not_invent_signal(self):
        self.provider.signal = 0.
        self.service.record(lambda _: None)
        self.assertFalse(self.service.result['technical']['capture']['signal_detected'])

    def test_recording_requires_replay_and_human_confirmation(self):
        self.service.record(lambda _: None)
        with self.assertRaises(AudioError):
            self.service.confirm('Sí')
        self.service.play('microphone')
        self.service.confirm('Sí')
        self.assertEqual(self.service.result['answers']['microphone'], 'VERIFICADO')

    def test_replay_requires_recording(self):
        with self.assertRaises(AudioError):
            self.service.play('microphone')
        self.assertNotIn('play', self.provider.calls)

    def test_failure_removes_previous_confirmation(self):
        self.service.play('left')
        self.service.confirm('Sí')
        self.provider.failure = 'Dispositivo desconectado'
        with self.assertRaises(AudioError):
            self.service.play('left')
        self.assertNotIn('left', self.service.result['answers'])
        self.assertEqual(summary(recent_audio_result(self.path, self.provider)), 'NO EVALUADO')

    def test_permission_error_and_close_cannot_start_microphone(self):
        self.provider.failure = 'Acceso denegado'
        with self.assertRaisesRegex(AudioError, 'Acceso denegado'):
            self.service.record(lambda _: None)
        self.assertIsNone(self.service.recording)
        self.service.close()
        calls = len(self.provider.calls)
        with self.assertRaises(AudioError):
            self.service.record(lambda _: None)
        self.assertEqual(len(self.provider.calls), calls)

    def test_device_change_invalidates_confirmation_and_recent_result(self):
        self.service.play('left')
        self.service.confirm('Sí')
        self.provider.info['output']['id'] = 'different'
        self.assertEqual(recent_audio_result(self.path, self.provider)['status'], 'NO EVALUADO')
        self.service.refresh()
        self.assertFalse(self.service.result['answers'])

    def test_device_change_during_confirmation(self):
        self.service.play('left')
        self.provider.info['output']['id'] = 'different'
        with self.assertRaises(AudioError):
            self.service.confirm('Sí')
        self.assertFalse(self.service.result['answers'])

    def test_diagnostic_only_reads_metadata_and_recent_confirmation(self):
        self.service.play('left')
        self.service.confirm('Sí')
        self.provider.calls.clear()
        result = recent_audio_result(self.path, self.provider)
        self.assertEqual(self.provider.calls, ['ids'])
        report = next(x for x in build_component_assessments({'audio_test': result}) if x['key'] == 'audio')
        self.assertEqual(report['status'], 'NO_EVALUABLE')
        self.assertIn('VERIFICADO', str(build_component_evidence({'audio_test': result}, 'audio')))

    def test_no_test_or_expired_is_not_evaluated(self):
        self.assertEqual(recent_audio_result(self.path, self.provider)['status'], 'NO EVALUADO')
        self.assertFalse(self.provider.calls)
        self.service.play('both')
        self.service.confirm('Sí')
        self.assertEqual(recent_audio_result(self.path, self.provider, now=time.time() + 90000)['status'], 'NO EVALUADO')

    def test_full_verified_requires_all_manual_answers(self):
        for channel in ('left', 'right', 'both'):
            self.service.play(channel)
            self.service.confirm('Sí')
        self.service.record(lambda _: None)
        self.service.play('microphone')
        self.service.confirm('Sí')
        self.assertEqual(recent_audio_result(self.path, self.provider)['status'], 'AUDIO VERIFICADO')

    def test_pipeline_never_calls_audio_actions(self):
        source = Path(__file__).resolve().parents[1] / 'core' / 'complete_diagnostic.py'
        tree = ast.parse(source.read_text(encoding='utf-8'))
        names = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
        self.assertIn('recent_audio_result', names)
        self.assertNotIn('AudioTest', names)
        self.assertNotIn('WindowsAudio', names)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                self.assertNotIn(node.func.attr, ('record', 'play'))

    def test_complete_pipeline_receives_only_previous_audio_evidence(self):
        from tests.test_v161_benchmark_diagnostic import Rig
        self.service.play('left')
        self.service.confirm('No')
        self.provider.calls.clear()
        with Rig() as rig, patch('core.complete_diagnostic.run_benchmark_suite', return_value={'status': 'OK'}), \
                patch('core.audio_test.recent_audio_result', side_effect=lambda: recent_audio_result(self.path, self.provider)):
            result = rig.run()
        self.assertEqual(result['audio_test']['status'], 'PROBLEMA REPORTADO')
        self.assertEqual(self.provider.calls, ['ids'])

    def test_hidden_gui_with_fake_provider(self):
        import tkinter as tk
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(str(exc))
        root.withdraw()
        try:
            from gui.audio_test_panel import AudioTestPanel
            window = AudioTestPanel(root, self.service)
            window.pack()
            deadline = time.monotonic() + 3
            while window.busy and time.monotonic() < deadline:
                root.update()
                time.sleep(.02)
            self.assertFalse(window.busy)
            self.assertEqual(self.provider.calls, ['devices'])
            window.destroy()
            self.assertTrue(self.service.closed)
        finally:
            root.destroy()


class NativeFormatTests(unittest.TestCase):
    def spec(self, channels=2):
        return parse_format(struct.pack('<HHIIHHH', 3, channels, 48000, 48000 * channels * 4, channels * 4, 32, 0))

    def test_left_and_right_samples_are_truly_isolated(self):
        spec = self.spec()
        for channel, silent in [('left', 1), ('right', 0)]:
            values = decode(tone(spec, channel), spec)
            self.assertTrue(all(x == 0 for x in values[silent::2]))
            self.assertGreater(max(abs(x) for x in values[1 - silent::2]), .07)
            self.assertLessEqual(max(abs(x) for x in values), .081)

    def test_mono_stereo_is_na(self):
        spec = self.spec(1)
        self.assertFalse(spec['stereo'])
        with self.assertRaises(AudioError):
            tone(spec, 'right')
        self.assertTrue(tone(spec, 'both'))
        self.assertIn(('Canal derecho', 'N/A'), evidence_rows({'devices': {'output': spec}}))

    def test_unknown_multichannel_layout_is_not_stereo(self):
        self.assertFalse(self.spec(6)['stereo'])

    def test_pcm_roundtrip_and_unsupported_is_na(self):
        for bits in (16, 24, 32):
            spec = {'bits': bits, 'tag': 1}
            actual = decode(encode([-.5, 0., .5], spec), spec)
            self.assertEqual(actual, [-.5, 0., .5])
        with self.assertRaises(AudioError):
            decode(b'\0', {'bits': 8, 'tag': 99})

    def test_cancelled_native_operation_never_opens_endpoint(self):
        cancel = threading.Event()
        cancel.set()
        with patch('core.windows_audio.endpoint', side_effect=AssertionError('Must not open')):
            with self.assertRaises(AudioError):
                WindowsAudio().record('id', cancel, lambda _: None)
            with self.assertRaises(AudioError):
                WindowsAudio().play('left', 'id', cancel)

    def test_absent_native_devices_report_na_without_crash(self):
        with patch('core.windows_audio.endpoint', side_effect=AudioError('Sin dispositivo')):
            devices = WindowsAudio().devices()
        self.assertFalse(devices['output']['available'])
        self.assertFalse(devices['input']['available'])

    def test_capture_stream_reads_buffers_and_stops_with_mocked_com(self):
        spec = self.spec(1)
        spec.update(id='input-id', rate=8000)
        buffer = C.create_string_buffer(struct.pack('<f', .125) * 40000)
        calls = []
        @contextmanager
        def fake_endpoint(flow):
            self.assertEqual(flow, 1)
            yield 101, 102, spec
        def fake_call(ptr, index, types=(), args=()):
            calls.append((ptr, index))
            if ptr == 101 and index == 14:
                args[1]._obj.value = 103
            elif getattr(ptr, 'value', ptr) == 103:
                if index == 5:
                    args[0]._obj.value = 40000
                elif index == 3:
                    args[0]._obj.value = C.addressof(buffer)
                    args[1]._obj.value = 40000
                    args[2]._obj.value = 0
        with patch('core.windows_audio.endpoint', fake_endpoint), patch('core.windows_audio.call', fake_call):
            levels = []
            samples, rate = WindowsAudio().record('input-id', threading.Event(), levels.append)
        self.assertEqual(len(samples), 40000)
        self.assertEqual(rate, 8000)
        self.assertEqual(levels, [.125])
        self.assertIn((101, 10), calls)
        self.assertIn((101, 11), calls)

    def test_render_stream_buffers_and_stops_with_mocked_com(self):
        spec = self.spec()
        buffer = C.create_string_buffer(48000 * 8)
        rendered = []
        calls = []
        def fake_call(ptr, index, types=(), args=()):
            calls.append((getattr(ptr, 'value', ptr), index))
            if ptr == 101 and index == 14:
                args[1]._obj.value = 103
            elif ptr == 101 and index == 4:
                args[0]._obj.value = 48000
            elif ptr == 101 and index == 6:
                args[0]._obj.value = 0
            elif getattr(ptr, 'value', ptr) == 103:
                if index == 3:
                    args[1]._obj.value = C.addressof(buffer)
                elif index == 4:
                    rendered.append(C.string_at(buffer, args[0] * spec['align']))
        payload = tone(spec, 'left')
        with patch('core.windows_audio.call', fake_call):
            WindowsAudio()._render(101, 102, spec, payload, threading.Event())
        self.assertEqual(b''.join(rendered), payload)
        self.assertIn((101, 10), calls)
        self.assertIn((101, 11), calls)


if __name__ == '__main__':
    unittest.main()
