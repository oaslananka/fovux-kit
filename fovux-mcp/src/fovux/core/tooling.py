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
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, list | tuple | set):
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
    from fovux.core.path_policy import reset_active_tool, set_active_tool

    started_at = perf_counter()
    bound.info("tool_start")
    active_token, roots_token = set_active_tool(tool_name, context)
    try:
        try:
            yield bound
        except FovuxError as exc:
            bound.error(
                "tool_error",
                duration_seconds=round(perf_counter() - started_at, 6),
                error_code=exc.code,
                error_message=exc.message,
            )
            _log_audit(tool_name, run_id, context, "failed", exc.message)
            raise
        except FileNotFoundError as exc:
            checkpoint_error = FovuxCheckpointNotFoundError(str(exc))
            bound.error(
                "tool_error",
                duration_seconds=round(perf_counter() - started_at, 6),
                error_code=checkpoint_error.code,
                error_message=checkpoint_error.message,
            )
            _log_audit(tool_name, run_id, context, "failed", checkpoint_error.message)
            raise checkpoint_error from exc
        except (RuntimeError, AssertionError) as exc:
            library_error = FovuxError(f"Underlying library error in {tool_name}: {exc}")
            bound.error(
                "tool_error",
                duration_seconds=round(perf_counter() - started_at, 6),
                error_code=library_error.code,
                error_message=library_error.message,
            )
            _log_audit(tool_name, run_id, context, "failed", library_error.message)
            raise library_error from exc
        except Exception as exc:
            bound.error(
                "tool_error",
                duration_seconds=round(perf_counter() - started_at, 6),
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
            _log_audit(tool_name, run_id, context, "failed", str(exc))
            raise FovuxError(f"Unexpected error in {tool_name}: {exc}") from exc
        else:
            bound.info("tool_end", duration_seconds=round(perf_counter() - started_at, 6))
            _log_audit(tool_name, run_id, context, "success")
    finally:
        reset_active_tool(active_token, roots_token)


def _log_audit(
    tool_name: str,
    run_id: str | None,
    context: dict[str, object],
    status: str,
    error_msg: str | None = None,
) -> None:
    try:
        from fovux.core.paths import get_fovux_home, FovuxPaths
        from fovux.core.runs import get_registry
        from fovux.http.tool_proxy import HTTP_TOOL_POLICIES
        import json
        import uuid

        # Determine risk level from policy category
        policy = HTTP_TOOL_POLICIES.get(tool_name)
        risk_level = policy.category if policy else "unknown"

        # Resolve path values to absolute strings
        resolved_paths = []
        for key, value in context.items():
            if any(s in key.lower() for s in ("path", "pool", "checkpoint", "file", "dir")):
                if isinstance(value, str) and value:
                    try:
                        from pathlib import Path
                        resolved = str(Path(value).expanduser().resolve())
                        resolved_paths.append(resolved)
                    except Exception:
                        resolved_paths.append(value)

        paths = FovuxPaths(get_fovux_home())
        registry = get_registry(paths.runs_db)

        # Log to SQLite runs.db
        registry.log_audit_event(
            actor="client",
            action=tool_name,
            entity_type="tool",
            entity_id=run_id or f"op_{uuid.uuid4().hex[:8]}",
            details={
                "risk_level": risk_level,
                "resolved_target_paths": resolved_paths,
                "challenge_id": context.get("challenge_id"),
                "status": status,
                "error": error_msg,
            },
        )
    except Exception:
        pass
