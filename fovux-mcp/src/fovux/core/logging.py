"""Structured logger backed by structlog for production-grade observability.

Respects:
  FOVUX_LOG_LEVEL  — DEBUG | INFO | WARNING | ERROR (default: INFO)
  FOVUX_LOG_FORMAT — json | pretty (default: pretty)
  NO_COLOR         — disable ANSI colours when set to any non-empty value
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any, Protocol, cast


class _Logger(Protocol):
    """Minimal logger protocol compatible with both structlog and stdlib."""

    def bind(self, **kw: object) -> _Logger:
        """Bind structured context to the logger."""
        ...

    def debug(self, event: str, **kw: object) -> object:
        """Log at DEBUG level."""
        ...

    def info(self, event: str, **kw: object) -> object:
        """Log at INFO level."""
        ...

    def warning(self, event: str, **kw: object) -> object:
        """Log at WARNING level."""
        ...

    def error(self, event: str, **kw: object) -> object:
        """Log at ERROR level."""
        ...


class _DynamicPrintLoggerFactory:
    """Create structlog print loggers bound to the current stderr stream."""

    def __call__(self, *args: object) -> object:
        del args
        import structlog

        return structlog.PrintLogger(sys.stderr)


def configure_logging(
    level: str | None = None,
    fmt: str | None = None,
) -> None:
    """Configure structured logging for the Fovux process.

    Safe to call multiple times — subsequent calls reconfigure in-place.

    Args:
        level: Override for FOVUX_LOG_LEVEL.
        fmt: Override for FOVUX_LOG_FORMAT (``"json"`` or ``"pretty"``).
    """
    log_level_name = (level or os.environ.get("FOVUX_LOG_LEVEL", "INFO")).upper()
    log_fmt = fmt or os.environ.get("FOVUX_LOG_FORMAT", "pretty")
    level_num = getattr(logging, log_level_name, logging.INFO)

    logging.basicConfig(
        level=level_num,
        stream=sys.stderr,
        format="%(message)s",
        force=True,
    )

    try:
        import structlog

        _configure_structlog(structlog, level_num, log_fmt)
    except ImportError:
        pass


def _configure_structlog(structlog: Any, level_num: int, log_fmt: str) -> None:  # noqa: ANN401
    if log_fmt == "json":
        processors: list[object] = [
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
    else:
        use_colors = not os.environ.get("NO_COLOR") and sys.stderr.isatty()
        processors = [
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="%H:%M:%S"),
            structlog.dev.ConsoleRenderer(colors=use_colors),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level_num),
        context_class=dict,
        logger_factory=_DynamicPrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )


def get_logger(name: str) -> _Logger:
    """Return a structured logger for the given module name.

    Uses structlog when available, falls back to stdlib ``logging.Logger``.

    Args:
        name: Typically ``__name__`` of the calling module.

    Returns:
        A logger compatible with ``log.info("event", key=value)`` style.
    """
    try:
        import structlog

        return cast(_Logger, structlog.get_logger(name))
    except ImportError:
        return cast(_Logger, logging.getLogger(name))
