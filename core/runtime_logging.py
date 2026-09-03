"""Observabilidad de ejecución para CorePulse.

Centraliza el registro de fallos sin convertirlos en datos de hardware. Los logs son
solo diagnósticos de software y nunca sustituyen la política REAL_OR_NA.
"""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import re
import sys
import threading
from typing import Optional

try:
    from platformdirs import user_log_dir
except Exception:  # pragma: no cover - fallback sin dependencia externa
    user_log_dir = None

_LOGGER_NAME = 'CorePulse'
_CONFIG_LOCK = threading.RLock()
_CONFIGURED = False
_LOG_PATH: Optional[Path] = None
_HOOKS_INSTALLED = False

_SECRET_PATTERNS = (
    re.compile(r'(?i)(GROQ_API_KEY\s*[=:]\s*)[^\s,;]+'),
    re.compile(r'(?i)(api[_-]?key\s*[=:]\s*)[^\s,;]+'),
    re.compile(r'(?i)(authorization\s*[=:]\s*bearer\s+)[^\s,;]+'),
)


def redact_sensitive_text(value) -> str:
    """Elimina secretos reconocibles antes de persistir mensajes en un log."""
    text = str(value)
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(r'\1<redacted>', text)
    return text


class _SecretRedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.msg = redact_sensitive_text(record.msg)
            if record.args:
                if isinstance(record.args, dict):
                    record.args = {k: redact_sensitive_text(v) for k, v in record.args.items()}
                else:
                    record.args = tuple(redact_sensitive_text(v) for v in record.args)
        except Exception:
            # El filtro jamás debe impedir que CorePulse continúe funcionando.
            pass
        return True


def _default_log_dir() -> Path:
    override = os.getenv('COREPULSE_LOG_DIR', '').strip()
    if override:
        return Path(override).expanduser()
    if user_log_dir is not None:
        try:
            return Path(user_log_dir('CorePulse', 'CorePulse'))
        except Exception:
            pass
    return Path.home() / '.corepulse' / 'logs'


def configure_runtime_logging(*, log_dir=None, level=None) -> Optional[Path]:
    """Configura un log rotativo e idempotente y devuelve su ruta real.

    Si el sistema no permite crear el archivo, CorePulse conserva un logger de
    consola y devuelve ``None``; un fallo de observabilidad nunca bloquea la app.
    """
    global _CONFIGURED, _LOG_PATH
    with _CONFIG_LOCK:
        if _CONFIGURED:
            return _LOG_PATH

        logger = logging.getLogger(_LOGGER_NAME)
        logger.setLevel(level or (logging.DEBUG if os.getenv('COREPULSE_DEBUG') == '1' else logging.INFO))
        logger.propagate = False
        redactor = _SecretRedactionFilter()

        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)s | %(threadName)s | %(name)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
        )

        try:
            directory = Path(log_dir).expanduser() if log_dir else _default_log_dir()
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / 'corepulse.log'
            handler = RotatingFileHandler(path, maxBytes=2 * 1024 * 1024, backupCount=3, encoding='utf-8')
            handler.setFormatter(formatter)
            handler.addFilter(redactor)
            logger.addHandler(handler)
            _LOG_PATH = path
        except Exception:
            _LOG_PATH = None

        if not logger.handlers:
            handler = logging.StreamHandler(sys.stderr)
            handler.setFormatter(formatter)
            handler.addFilter(redactor)
            logger.addHandler(handler)

        _CONFIGURED = True
        logger.info('Runtime logging initialized')
        return _LOG_PATH


def get_logger(name=None) -> logging.Logger:
    configure_runtime_logging()
    suffix = str(name or '').strip()
    return logging.getLogger(f'{_LOGGER_NAME}.{suffix}' if suffix else _LOGGER_NAME)


def get_runtime_log_path() -> Optional[str]:
    configure_runtime_logging()
    return str(_LOG_PATH) if _LOG_PATH is not None else None


def install_exception_hooks() -> None:
    """Registra excepciones no controladas del hilo principal y de workers."""
    global _HOOKS_INSTALLED
    with _CONFIG_LOCK:
        if _HOOKS_INSTALLED:
            return
        logger = get_logger('uncaught')
        previous_sys_hook = sys.excepthook
        previous_thread_hook = getattr(threading, 'excepthook', None)

        def sys_hook(exc_type, exc_value, exc_traceback):
            if exc_type is KeyboardInterrupt:
                return previous_sys_hook(exc_type, exc_value, exc_traceback)
            logger.critical('Unhandled main-thread exception', exc_info=(exc_type, exc_value, exc_traceback))
            if previous_sys_hook:
                previous_sys_hook(exc_type, exc_value, exc_traceback)

        def thread_hook(args):
            logger.critical(
                'Unhandled worker exception in %s',
                getattr(getattr(args, 'thread', None), 'name', 'unknown'),
                exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
            )
            if previous_thread_hook:
                previous_thread_hook(args)

        sys.excepthook = sys_hook
        if previous_thread_hook is not None:
            threading.excepthook = thread_hook
        _HOOKS_INSTALLED = True
