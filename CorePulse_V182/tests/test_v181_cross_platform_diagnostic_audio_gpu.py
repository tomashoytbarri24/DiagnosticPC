from __future__ import annotations

import threading
from unittest.mock import patch


def test_automatic_audio_probe_runs_output_and_capture():
    from core.audio_test import automatic_audio_probe

    class Provider:
        def __init__(self):
            self.played = []
            self.record_duration = None

        def devices(self):
            return {
                'output': {'available': True, 'id': 'out', 'name': 'Output', 'stereo': True},
                'input': {'available': True, 'id': 'in', 'name': 'Input'},
            }

        def play(self, channel, expected, cancel, recording=None):
            assert expected == 'out'
            assert isinstance(cancel, threading.Event)
            self.played.append(channel)

        def record(self, expected, cancel, on_level, duration_s=5.0):
            assert expected == 'in'
            self.record_duration = duration_s
            on_level(0.02)
            return [0.01] * 800, 1000

    provider = Provider()
    result = automatic_audio_probe(provider=provider)
    assert result['mode'] == 'AUTOMATIC_TECHNICAL'
    assert result['status'] == 'AUDIO TÉCNICO OK'
    assert provider.played == ['left', 'right', 'both']
    assert provider.record_duration == 0.8
    assert result['technical']['capture']['completed'] is True


def test_automatic_audio_summary_is_normal_when_technical_probe_passes():
    from core.diagnostic_summary import build_component_assessments

    result = {
        'audio_test': {
            'mode': 'AUTOMATIC_TECHNICAL', 'status': 'AUDIO TÉCNICO OK', 'errors': [],
            'devices': {'output': {'available': True}, 'input': {'available': True}},
            'technical': {
                'left': {'api_completed': True}, 'right': {'api_completed': True},
                'both': {'api_completed': True}, 'capture': {'completed': True},
            },
        },
        'complete_diagnostic': {'platform': 'Linux', 'hardware': {'battery': {}, 'storage': []}, 'benchmark': {}},
    }
    audio = next(row for row in build_component_assessments(result) if row['key'] == 'audio')
    assert audio['status'] == 'NORMAL'
    assert [value for _, value, *_ in audio['facets']] == ['OK', 'OK', 'OK']


def test_linux_suite_uses_visible_opengl_gpu_provider(monkeypatch):
    import core.benchmark_engine as be

    monkeypatch.setattr(be.platform, 'system', lambda: 'Linux')
    called = {}

    def fake_linux(seconds, progress_callback=None, stop_check=None):
        called['seconds'] = seconds
        if progress_callback:
            progress_callback(0.5, 'GPU · OpenGL visible', 'fake')
        return {
            'kind': 'GPU', 'status': 'OK', 'value': 120.0, 'unit': 'FPS',
            'benchmark_method': 'COREPULSE_GPU_OPENGL_VISIBLE_LINUX_V1',
            'renderer': 'Test GPU', 'duration_s': 1.0,
        }

    monkeypatch.setattr(be, '_benchmark_gpu_opengl_linux', fake_linux)
    result = be.run_benchmark_suite('quick', ['gpu'], telemetry_sampler=lambda: {'gpu_usage': 10})
    assert result['status'] == 'OK'
    assert result['gpu']['benchmark_method'] == 'COREPULSE_GPU_OPENGL_VISIBLE_LINUX_V1'
    assert result['gpu']['value'] == 120.0
    assert called['seconds'] > 0


def test_diagnostic_view_never_remaps_empty_evidence_card():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / 'gui' / 'diagnostic_view.py').read_text(encoding='utf-8')
    assert 'if self._evidence_open_key:' in source
    assert "status not in {'WARNING', 'CRITICAL'} or not sections" in source
    assert "sticky='nsew'" in source


def test_linux_benchmark_is_available_in_main_benchmark_ui():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')
    assert "platform.system() in {'Windows', 'Linux'}" in source
    assert 'ventana OpenGL visible' in source


def test_version_authority_remains_current():
    from core.version import VERSION, STAGE
    assert VERSION.isdecimal()
    assert STAGE
