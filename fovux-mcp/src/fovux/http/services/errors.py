"""Typed errors shared by transport-neutral HTTP services."""

from __future__ import annotations

from typing import Any


class ServiceError(Exception):
    """A domain/service failure that a transport adapter can map explicitly."""

    def __init__(self, status_code: int, detail: Any) -> None:  # noqa: ANN401
        """Initialize the error with an HTTP-compatible status and detail value."""
        super().__init__(str(detail))
        self.status_code = status_code
        self.detail = detail
