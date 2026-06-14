"""Structured JSON logging (NFR-3). NOT a counted tool — platform capability.

Uses structlog for JSON logs when it's installed; degrades to a configured stdlib
logger otherwise, so importing this module never fails in a minimal environment.
`get_logger(name)` returns something with `.info/.warning/.error(...)` either way.
"""
from __future__ import annotations

import collections
import json
import logging
import sys
import threading
import time

_CONFIGURED = False

# ── In-memory log ring buffer ──────────────────────────────────────────────
# Everything logged (uvicorn access/error, httpx, openai retry/429, langchain,
# and our structlog events) is mirrored into this bounded deque so the API can
# serve it at GET / and GET /logs.json — visibility without tailing a terminal.
_LOG_BUFFER: "collections.deque[dict]" = collections.deque(maxlen=4000)
_LOG_LOCK = threading.Lock()


def record_log(level: str, logger: str, msg: str) -> None:
    """Append one log line to the ring buffer (thread-safe)."""
    with _LOG_LOCK:
        _LOG_BUFFER.append(
            {"ts": time.time(), "level": (level or "INFO").upper(),
             "logger": logger or "", "msg": msg}
        )


def get_log_lines(limit: int = 1000, level: str | None = None,
                  contains: str | None = None) -> list[dict]:
    """Return buffered log lines, newest last, optionally filtered."""
    with _LOG_LOCK:
        rows = list(_LOG_BUFFER)
    if level:
        order = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}
        floor = order.get(level.upper(), 0)
        rows = [r for r in rows if order.get(r["level"], 20) >= floor]
    if contains:
        needle = contains.lower()
        rows = [r for r in rows if needle in r["msg"].lower() or needle in r["logger"].lower()]
    return rows[-limit:]


class _BufferHandler(logging.Handler):
    """stdlib handler that mirrors every record into the ring buffer."""
    def emit(self, record: logging.LogRecord) -> None:
        try:
            record_log(record.levelname, record.name, record.getMessage())
        except Exception:
            pass


_buffer_handler = _BufferHandler()


def _struct_buffer_processor(logger, method_name, event_dict):
    """structlog processor: mirror the event into the buffer, pass it through unchanged."""
    try:
        ev = dict(event_dict)
        name = ev.pop("logger", "aps")
        record_log(method_name, name, json.dumps(ev, default=str))
    except Exception:
        pass
    return event_dict


def install_log_capture(level: int = logging.INFO) -> None:
    """Attach the buffer handler to root + any non-propagating loggers (uvicorn.*).
    Idempotent; safe to call from a FastAPI startup hook after uvicorn configures logging."""
    _buffer_handler.setLevel(level)
    root = logging.getLogger()
    if root.level == 0 or root.level > level:
        root.setLevel(level)
    if not any(isinstance(h, _BufferHandler) for h in root.handlers):
        root.addHandler(_buffer_handler)
    # uvicorn.access / uvicorn.error set propagate=False, so they never reach root —
    # attach the handler to every currently-registered logger that opts out of propagation.
    for name in list(logging.root.manager.loggerDict):
        lg = logging.getLogger(name)
        if not getattr(lg, "propagate", True) and \
                not any(isinstance(h, _BufferHandler) for h in lg.handlers):
            lg.addHandler(_buffer_handler)


def configure_logging(level: str = "INFO") -> None:
    """Idempotently configure JSON logging for the whole process."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    lvl = getattr(logging, level.upper(), logging.INFO)

    try:
        import structlog  # optional dependency
    except Exception:
        # stdlib fallback — still structured-ish, still single place to configure.
        logging.basicConfig(
            level=lvl,
            stream=sys.stdout,
            format='{"level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
        )
        _CONFIGURED = True
        return

    logging.basicConfig(level=lvl, stream=sys.stdout, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            _struct_buffer_processor,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(lvl),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    _CONFIGURED = True


def get_logger(name: str = "aps"):
    """Return a logger; configures logging on first use."""
    configure_logging()
    try:
        import structlog
        return structlog.get_logger(name)
    except Exception:
        return logging.getLogger(name)
