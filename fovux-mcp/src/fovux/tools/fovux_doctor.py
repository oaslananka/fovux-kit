"""fovux_doctor — shared environment diagnostics for local Fovux installs."""

from __future__ import annotations

from typing import Any

from fovux.core.doctor import collect_doctor_report
from fovux.core.tooling import tool_event
from fovux.server import mcp


@mcp.tool()
def fovux_doctor() -> dict[str, Any]:
    """Report the local Fovux environment health, including GPU and HTTP status."""
    with tool_event("fovux_doctor"):
        return collect_doctor_report().model_dump(mode="json")
