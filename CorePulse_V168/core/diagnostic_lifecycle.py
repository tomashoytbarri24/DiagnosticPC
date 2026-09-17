"""Identidad y buzón de una ejecución. Ningún worker toca Tk ni otra sesión."""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from enum import Enum


class DiagnosticState(str, Enum):
    IDLE = 'IDLE'
    PREPARING = 'PREPARING'
    RUNNING_BASELINE = 'RUNNING_BASELINE'
    RUNNING_HARDWARE = 'RUNNING_HARDWARE'
    RUNNING_WINDOWS = 'RUNNING_WINDOWS'
    RUNNING_STRESS_CPU = 'RUNNING_STRESS_CPU'
    RUNNING_STRESS_RAM = 'RUNNING_STRESS_RAM'
    RUNNING_STRESS_GPU = 'RUNNING_STRESS_GPU'
    COOLDOWN = 'COOLDOWN'
    RUNNING_BENCHMARK = 'RUNNING_BENCHMARK'
    ANALYZING_BENCHMARK = 'ANALYZING_BENCHMARK'
    CORRELATING = 'CORRELATING'
    COMPLETED = 'COMPLETED'
    CANCELLING = 'CANCELLING'
    CANCELLED = 'CANCELLED'
    ERROR = 'ERROR'


_ORDER = list(DiagnosticState)
_TERMINAL = {DiagnosticState.COMPLETED, DiagnosticState.CANCELLED, DiagnosticState.ERROR}


@dataclass
class DiagnosticRun:
    token: int
    cancel_event: threading.Event = field(default_factory=threading.Event)
    worker: threading.Thread | None = None
    state: DiagnosticState = DiagnosticState.PREPARING
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)
    _progress: tuple | None = None
    _result: tuple | None = None

    def transition(self, state):
        state = DiagnosticState(state)
        with self._lock:
            if self.state in _TERMINAL or self.state == DiagnosticState.CANCELLING:
                return False
            if state not in _TERMINAL and _ORDER.index(state) < _ORDER.index(self.state):
                return False
            self.state = state
            return True

    def cancel(self):
        with self._lock:
            if self.state in _TERMINAL:
                return False
            self.state = DiagnosticState.CANCELLING
            self.cancel_event.set()
            self._progress = self._result = None
            self.state = DiagnosticState.CANCELLED
            return True

    def post_progress(self, fraction, stage, detail=''):
        with self._lock:
            if not self.cancel_event.is_set() and self.state not in _TERMINAL:
                # La carga RAM produce miles de avances: conservar sólo el último.
                self._progress = (fraction, stage, detail)

    def post_result(self, result, error=None, state=None):
        with self._lock:
            if not self.cancel_event.is_set() and self.state not in _TERMINAL:
                self._result = (result, error, state)

    def drain(self):
        with self._lock:
            messages = self._progress, self._result
            self._progress = self._result = None
            return messages


def is_finalized_result(result):
    if not isinstance(result, dict):
        return False
    block = result.get('complete_diagnostic')
    return (isinstance(block, dict) and block.get('finalized') is True
            and block.get('status') in {'COMPLETE', 'PARTIAL'}
            and not block.get('cancelled_by_user'))


def is_completed_benchmark(benchmark):
    if not isinstance(benchmark, dict) or benchmark.get('cancelled') or benchmark.get('safety_stop'):
        return False
    if benchmark.get('status') not in {'OK', 'COMPLETE'}:
        return False
    selected = benchmark.get('selected_components') or ('cpu', 'ram', 'ssd', 'gpu')
    return all(isinstance(benchmark.get(k), dict) and benchmark[k].get('status') == 'OK'
               for k in selected)
