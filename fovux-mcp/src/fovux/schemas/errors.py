"""Structured error payloads returned by Fovux HTTP and MCP boundaries."""

from __future__ import annotations

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    """Stable error shape for clients that want structured remediation data."""

    code: str
    message: str
    hint: str | None = None
