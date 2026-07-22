"""Service-level tests for health and Prometheus snapshots."""

from __future__ import annotations

from pathlib import Path

import pytest

from fovux import __version__
from fovux.core.runs import RunRegistry
from fovux.http.services.errors import ServiceError
from fovux.http.services.health import HealthService


def test_health_service_reports_version_without_http_transport(tmp_path: Path) -> None:
    registry = RunRegistry(tmp_path / "runs.db")
    service = HealthService(registry_provider=lambda: registry)

    assert service.health() == {
        "status": "ok",
        "version": __version__,
        "service": "fovux-mcp",
    }


def test_health_service_metrics_preserve_disabled_and_counts(tmp_path: Path) -> None:
    registry = RunRegistry(tmp_path / "runs.db")
    for run_id in ("active", "finished"):
        registry.create_run(
            run_id=run_id,
            run_path=tmp_path / run_id,
            model="model.pt",
            dataset_path=tmp_path / "dataset",
            task="detect",
            epochs=1,
        )
    registry.update_status("active", "running")
    registry.update_status("finished", "running")
    registry.update_status("finished", "complete")
    service = HealthService(registry_provider=lambda: registry)

    with pytest.raises(ServiceError) as exc_info:
        service.prometheus_metrics(enabled=False)
    snapshot = service.prometheus_metrics(enabled=True)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Metrics endpoint is disabled."
    assert "fovux_active_runs 1" in snapshot
    assert "fovux_runs_total 2" in snapshot
    assert snapshot.endswith("\n")
