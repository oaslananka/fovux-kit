"""Health and Prometheus snapshot service."""

from __future__ import annotations

from collections.abc import Callable

from fovux import __version__
from fovux.core.runs import RunRegistry
from fovux.http.services.errors import ServiceError
from fovux.http.services.runs import default_registry_provider

RegistryProvider = Callable[[], RunRegistry]


class HealthService:
    """Expose process health and local registry counters."""

    def __init__(self, registry_provider: RegistryProvider = default_registry_provider) -> None:
        """Initialize with an injectable run registry provider."""
        self._registry_provider = registry_provider

    def health(self) -> dict[str, str]:
        """Return the stable public health payload."""
        return {"status": "ok", "version": __version__, "service": "fovux-mcp"}

    def prometheus_metrics(self, *, enabled: bool) -> str:
        """Return the existing Prometheus text snapshot when enabled."""
        if not enabled:
            raise ServiceError(404, "Metrics endpoint is disabled.")
        records = self._registry_provider().list_runs(limit=10000)
        active_runs = sum(1 for record in records if record.status == "running")
        lines = [
            "# HELP fovux_active_runs Number of currently running Fovux training runs.",
            "# TYPE fovux_active_runs gauge",
            f"fovux_active_runs {active_runs}",
            "# HELP fovux_runs_total Number of runs tracked by the local registry.",
            "# TYPE fovux_runs_total gauge",
            f"fovux_runs_total {len(records)}",
        ]
        return "\n".join(lines) + "\n"
