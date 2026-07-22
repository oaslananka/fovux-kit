"""Composition container for Studio local HTTP services."""

from __future__ import annotations

from dataclasses import dataclass

from fovux.http.services.runs import RunService


@dataclass
class HttpServices:
    """Explicit service dependencies used by HTTP route adapters."""

    runs: RunService


def build_default_services() -> HttpServices:
    """Build production services with their default local dependencies."""
    return HttpServices(runs=RunService())
