from __future__ import annotations

from types import SimpleNamespace

import core.cpu_frequency as cpu_frequency


def test_psutil_frequency_is_real_and_traceable(monkeypatch):
    monkeypatch.setattr(cpu_frequency.psutil, 'cpu_freq', lambda: SimpleNamespace(current=2500.0))
    evidence = cpu_frequency.get_cpu_frequency_evidence(force=True)
    assert evidence['ghz'] == 2.5
    assert evidence['source'] == 'psutil.cpu_freq'
    assert evidence['quality'] == 'VALID'
    assert evidence['synthetic_adjustment'] is False
    assert evidence['offset_applied'] == 0.0


def test_windows_perf_frequency_derivation_uses_real_counters(monkeypatch):
    monkeypatch.setattr(cpu_frequency.psutil, 'cpu_freq', lambda: None)
    monkeypatch.setattr(cpu_frequency, '_powershell_json', lambda *a, **k: {
        'Name': '_Total', 'ProcessorFrequency': 2500, 'PercentProcessorPerformance': 107
    })
    monkeypatch.setattr(cpu_frequency.os, 'name', 'nt', raising=False)
    evidence = cpu_frequency.get_cpu_frequency_evidence(force=True)
    assert evidence['mhz'] == 2675.0
    assert evidence['ghz'] == 2.675
    assert evidence['derived_from_real'] is True
    assert 'PercentProcessorPerformance' in evidence['sensor']


def test_invalid_frequency_returns_no_fake_value(monkeypatch):
    monkeypatch.setattr(cpu_frequency.psutil, 'cpu_freq', lambda: SimpleNamespace(current=0.0))
    monkeypatch.setattr(cpu_frequency, '_from_windows_perf_cim', lambda: None)
    monkeypatch.setattr(cpu_frequency, '_from_win32_processor', lambda: None)
    evidence = cpu_frequency.get_cpu_frequency_evidence(force=True)
    assert evidence is None
