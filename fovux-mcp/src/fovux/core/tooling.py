"""Common helpers for consistent tool-level observability."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from time import perf_counter
from typing import Protocol, cast

from fovux.core.errors import FovuxCheckpointNotFoundError, FovuxError
from fovux.core.logging import get_logger


class _BindableLogger(Protocol):
    """Logger protocol compatible with structlog-bound loggers."""

    def bind(self, **new_values: object) -> _BindableLogger:
        """Return a logger bound with extra context."""

    def info(self, event: str, **kw: object) -> object:
        """Log at INFO level."""

    def error(self, event: str, **kw: object) -> object:
        """Log at ERROR level."""


def _safe_value(value: object) -> object:
    """Convert rich objects into stable, serializable log values."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple, set)):
        return [_safe_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _safe_value(item) for key, item in value.items()}
    return str(value)


@contextmanager
def tool_event(
    tool_name: str,
    *,
    run_id: str | None = None,
    **context: object,
) -> Iterator[_BindableLogger]:
    """Emit structured tool lifecycle logs around a tool invocation."""
    logger = cast(_BindableLogger, get_logger(f"fovux.tools.{tool_name}"))
    bound = logger.bind(
        tool_name=tool_name,
        run_id=run_id,
        **{key: _safe_value(value) for key, value in context.items()},
    )
    started_at = perf_counter()
    bound.info("tool_start")
    try:
        yield bound
    except FovuxError as exc:
        bound.error(
            "tool_error",
            duration_seconds=round(perf_counter() - started_at, 6),
            error_code=exc.code,
            error_message=exc.message,
        )
        raise
    except FileNotFoundError as exc:
        checkpoint_error = FovuxCheckpointNotFoundError(str(exc))
        bound.error(
            "tool_error",
            duration_seconds=round(perf_counter() - started_at, 6),
            error_code=checkpoint_error.code,
            error_message=checkpoint_error.message,
        )
        raise checkpoint_error from exc
    except (RuntimeError, AssertionError) as exc:
        library_error = FovuxError(f"Underlying library error in {tool_name}: {exc}")
        bound.error(
            "tool_error",
            duration_seconds=round(perf_counter() - started_at, 6),
            error_code=library_error.code,
            error_message=library_error.message,
        )
        raise library_error from exc
    except Exception as exc:
        bound.error(
            "tool_error",
            duration_seconds=round(perf_counter() - started_at, 6),
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
        raise FovuxError(f"Unexpected error in {tool_name}: {exc}") from exc
    else:
        bound.info("tool_end", duration_seconds=round(perf_counter() - started_at, 6))
