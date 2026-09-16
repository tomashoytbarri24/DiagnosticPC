"""Cancelación cooperativa de consultas de sólo lectura iniciadas por diagnóstico.

Fuera del contexto de diagnóstico conserva subprocess.run y sus contratos.
Cada contexto es local al hilo: cancelar diagnóstico no cancela otras herramientas.
"""
from contextlib import contextmanager
from contextvars import ContextVar
import subprocess
import time

_cancel_check = ContextVar('diagnostic_process_cancel', default=None)


class DiagnosticCancelled(RuntimeError):
    pass


@contextmanager
def cancellation_scope(check):
    token = _cancel_check.set(check)
    try:
        yield
    finally:
        _cancel_check.reset(token)


def run(args, **kwargs):
    check = _cancel_check.get()
    if not callable(check):
        return subprocess.run(args, **kwargs)
    if check():
        raise DiagnosticCancelled('Diagnóstico cancelado')
    timeout = kwargs.pop('timeout', None)
    enforce = kwargs.pop('check', False)
    input_data = kwargs.pop('input', None)
    if kwargs.pop('capture_output', False):
        kwargs['stdout'] = kwargs['stderr'] = subprocess.PIPE
    if input_data is not None:
        kwargs['stdin'] = subprocess.PIPE
    started = time.monotonic()
    with subprocess.Popen(args, **kwargs) as process:
        try:
            while True:
                if check():
                    raise DiagnosticCancelled('Diagnóstico cancelado')
                remaining = None if timeout is None else timeout - (time.monotonic() - started)
                if remaining is not None and remaining <= 0:
                    raise subprocess.TimeoutExpired(args, timeout)
                try:
                    out, err = process.communicate(input=input_data, timeout=min(0.1, remaining) if remaining is not None else 0.1)
                    break
                except subprocess.TimeoutExpired:
                    input_data = None
        except BaseException:
            process.kill()
            process.communicate()
            raise
    result = subprocess.CompletedProcess(args, process.returncode, out, err)
    if enforce:
        result.check_returncode()
    return result
