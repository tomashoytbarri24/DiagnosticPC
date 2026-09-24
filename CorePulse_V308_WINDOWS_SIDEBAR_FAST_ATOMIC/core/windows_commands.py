"""Ejecución centralizada y silenciosa de comandos Windows para CorePulse.

Ningún consumidor debe usar ``shell=True`` para powercfg/PowerShell/CMD.  Esta
capa conserva stdout, stderr y return code para que la UI sólo confirme cambios
cuando Windows realmente los aceptó.
"""
from __future__ import annotations

from dataclasses import dataclass
import ctypes
import logging
import os
from pathlib import Path
from core.runtime_paths import executable_root, source_root
import subprocess
import sys
from typing import Iterable, Mapping, Optional, Sequence

logger = logging.getLogger('CorePulse.WindowsCommand')
IS_WINDOWS = os.name == 'nt'


@dataclass(frozen=True)
class CommandResult:
    ok: bool
    args: tuple[str, ...]
    returncode: Optional[int]
    stdout: str
    stderr: str
    error: Optional[str] = None
    timed_out: bool = False

    def message(self) -> str:
        return (self.stderr or self.stdout or self.error or '').strip()


def _startupinfo():
    if not IS_WINDOWS:
        return None
    info = subprocess.STARTUPINFO()
    info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    info.wShowWindow = getattr(subprocess, 'SW_HIDE', 0)
    return info


def hidden_creationflags() -> int:
    return getattr(subprocess, 'CREATE_NO_WINDOW', 0) if IS_WINDOWS else 0


def run_hidden(
    args: Sequence[object], *, timeout: float = 20.0, cwd: Optional[os.PathLike | str] = None,
    env: Optional[Mapping[str, str]] = None, input_text: Optional[str] = None,
    category: str = 'CORE', log_failures: bool = True,
) -> CommandResult:
    """Ejecuta una lista de argumentos sin shell ni ventana visible."""
    argv = tuple(str(x) for x in args)
    if not argv:
        return CommandResult(False, (), None, '', '', 'Comando vacío')
    try:
        cp = subprocess.run(
            list(argv), shell=False, capture_output=True, text=True,
            encoding='utf-8', errors='replace', timeout=float(timeout),
            cwd=str(cwd) if cwd is not None else None, env=dict(env) if env is not None else None,
            input=input_text, creationflags=hidden_creationflags(), startupinfo=_startupinfo(),
        )
        result = CommandResult(cp.returncode == 0, argv, cp.returncode, cp.stdout or '', cp.stderr or '')
        if (not result.ok) and log_failures:
            logger.error('[%s] comando falló rc=%s args=%r stderr=%s stdout=%s', category, cp.returncode, argv, result.stderr[:3000], result.stdout[:1000])
        return result
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout.decode('utf-8', 'replace') if isinstance(exc.stdout, bytes) else (exc.stdout or '')
        err = exc.stderr.decode('utf-8', 'replace') if isinstance(exc.stderr, bytes) else (exc.stderr or '')
        if log_failures:
            logger.error('[%s] timeout %.1fs args=%r', category, timeout, argv)
        return CommandResult(False, argv, None, out, err, f'Tiempo de espera agotado ({timeout:.0f} s)', True)
    except FileNotFoundError as exc:
        if log_failures:
            logger.error('[%s] ejecutable no encontrado: %s', category, argv[0])
        return CommandResult(False, argv, None, '', '', f'No se encontró {argv[0]}')
    except Exception as exc:
        if log_failures:
            logger.exception('[%s] fallo inesperado ejecutando %r', category, argv)
        return CommandResult(False, argv, None, '', '', f'{type(exc).__name__}: {exc}')


def run_powershell(script: str, *, timeout: float = 25.0, category: str = 'POWERSHELL') -> CommandResult:
    prefix = "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $OutputEncoding=[System.Text.Encoding]::UTF8; "
    return run_hidden(
        ['powershell.exe', '-NoLogo', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-Command', prefix + str(script)],
        timeout=timeout, category=category,
    )


def is_admin() -> bool:
    if not IS_WINDOWS:
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def looks_like_access_denied(result: CommandResult | str | None) -> bool:
    raw = result.message() if isinstance(result, CommandResult) else str(result or '')
    low = raw.lower()
    return any(token in low for token in ('access is denied', 'access denied', 'acceso denegado', 'unauthorizedaccess', 'requires elevation', 'elevación'))


def friendly_failure(result: CommandResult, action: str = 'la operación') -> str:
    if result.timed_out:
        return f'Windows tardó demasiado en completar {action}.'
    if looks_like_access_denied(result):
        return f'Windows rechazó {action} por permisos. Ejecuta CorePulse como administrador y vuelve a intentarlo.'
    if result.error:
        return f'No se pudo completar {action}: {result.error}'
    if result.returncode not in (None, 0):
        return f'Windows no pudo completar {action} (código {result.returncode}). Revisa los logs de CorePulse.'
    return f'No se pudo completar {action}. Revisa los logs de CorePulse.'


def request_elevation() -> dict:
    """Solicita relanzar CorePulse elevado. Nunca afirma éxito antes de ShellExecuteW."""
    if not IS_WINDOWS:
        return {'success': False, 'message': 'La elevación sólo está disponible en Windows.'}
    if is_admin():
        return {'success': True, 'already_admin': True, 'message': 'CorePulse ya tiene privilegios de administrador.'}
    try:
        root = executable_root() if getattr(sys, 'frozen', False) else source_root()
        if getattr(sys, 'frozen', False):
            exe = sys.executable
            params = ' '.join(f'"{a}"' for a in sys.argv[1:])
        else:
            exe = sys.executable
            launcher = root / 'corepulse_launcher.py'
            params = ' '.join([f'"{launcher}"'] + [f'"{a}"' for a in sys.argv[1:]])
        code = int(ctypes.windll.shell32.ShellExecuteW(None, 'runas', exe, params, str(root), 1))
        if code <= 32:
            return {'success': False, 'message': f'Windows no pudo iniciar la elevación (código {code}).'}
        return {'success': True, 'message': 'Se solicitó abrir CorePulse como administrador.'}
    except Exception as exc:
        logger.exception('[CORE] Falló la solicitud de elevación')
        return {'success': False, 'message': f'No se pudo solicitar elevación: {exc}'}
