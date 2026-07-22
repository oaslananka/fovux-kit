"""Composition container for Studio local HTTP services."""

from __future__ import annotations

from dataclasses import dataclass

from fovux.http.services.health import HealthService
from fovux.http.services.lineage import LineageService
from fovux.http.services.operations import OperationRuntimeState, OperationService
from fovux.http.services.runs import RunService
from fovux.http.services.tool_runtime import ToolRuntimeState
from fovux.http.services.tools import ChallengeService, ToolInvocationService
from fovux.http.tool_proxy import HTTP_TOOL_POLICIES


@dataclass
class HttpServices:
    """Explicit service dependencies used by HTTP route adapters."""

    health: HealthService
    lineage: LineageService
    runs: RunService
    operations: OperationService
    operation_runtime: OperationRuntimeState
    challenges: ChallengeService
    tools: ToolInvocationService
    tool_runtime: ToolRuntimeState


def build_default_services() -> HttpServices:
    """Build production services after completing the shared tool registry bootstrap."""
    from fovux import server as _server

    del _server
    return HttpServices(
        health=HealthService(),
        lineage=LineageService(),
        runs=RunService(),
        operations=OperationService(),
        operation_runtime=OperationRuntimeState(),
        challenges=ChallengeService(),
        tools=ToolInvocationService(),
        tool_runtime=ToolRuntimeState.from_policies(HTTP_TOOL_POLICIES),
    )
