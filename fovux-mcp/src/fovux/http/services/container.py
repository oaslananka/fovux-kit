"""Composition container for Studio local HTTP services."""

from __future__ import annotations

from dataclasses import dataclass

from fovux.http.services.operations import OperationRuntimeState, OperationService
from fovux.http.services.runs import RunService
from fovux.http.services.tool_runtime import ToolRuntimeState
from fovux.http.services.tools import ChallengeService, ToolInvocationService
from fovux.http.tool_proxy import HTTP_TOOL_POLICIES


@dataclass
class HttpServices:
    """Explicit service dependencies used by HTTP route adapters."""

    runs: RunService
    operations: OperationService
    operation_runtime: OperationRuntimeState
    challenges: ChallengeService
    tools: ToolInvocationService
    tool_runtime: ToolRuntimeState


def build_default_services() -> HttpServices:
    """Build production services with their default local dependencies."""
    return HttpServices(
        runs=RunService(),
        operations=OperationService(),
        operation_runtime=OperationRuntimeState(),
        challenges=ChallengeService(),
        tools=ToolInvocationService(),
        tool_runtime=ToolRuntimeState.from_policies(HTTP_TOOL_POLICIES),
    )
