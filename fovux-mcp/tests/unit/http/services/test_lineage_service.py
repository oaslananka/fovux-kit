"""Service-level tests for lineage, datasets, and exports."""

from __future__ import annotations

from pathlib import Path

import pytest

from fovux.core.runs import RunRegistry
from fovux.http.services.errors import ServiceError
from fovux.http.services.lineage import LineageService


def _seed_lineage(tmp_path: Path) -> tuple[RunRegistry, str]:
    registry = RunRegistry(tmp_path / "runs.db")
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    (dataset / "data.yaml").write_text("nc: 1\nnames:\n  0: object\n", encoding="utf-8")
    run_dir = tmp_path / "runs" / "run_lineage"
    record = registry.reserve_run_slot(
        run_id="run_lineage",
        run_path=run_dir,
        model="model.pt",
        dataset_path=dataset,
        task="detect",
        epochs=2,
        max_concurrent_runs=2,
    )
    artifact = tmp_path / "weights.onnx"
    artifact.write_bytes(b"onnx")
    registry.add_artifact("artifact_1", "run_lineage", "checkpoint", artifact)
    registry.record_export(
        "export_1",
        "run_lineage",
        source_checkpoint=artifact,
        artifact_path=artifact,
        format="onnx",
        duration_s=1.25,
        validation_result={"valid": True},
    )
    assert record.dataset_fingerprint is not None
    return registry, str(record.dataset_fingerprint)


def test_lineage_service_serializes_run_resources(tmp_path: Path) -> None:
    registry, fingerprint = _seed_lineage(tmp_path)
    service = LineageService(registry_provider=lambda: registry)

    lineage = service.run_lineage("run_lineage")
    events = service.run_events("run_lineage")
    datasets = service.list_datasets()
    dataset = service.get_dataset(fingerprint)
    exports = service.list_exports()

    assert lineage["run_id"] == "run_lineage"
    assert lineage["dataset_fingerprint"] == fingerprint
    assert [item["id"] for item in lineage["artifacts"]] == ["art_export_1", "artifact_1"]
    assert lineage["exports"][0]["validation_result"] == {"valid": True}
    assert events[0]["to_status"] == "pending"
    assert datasets[0]["fingerprint"] == fingerprint
    assert dataset["class_map"] == {"0": "object"}
    assert exports[0]["run_id"] == "run_lineage"


def test_lineage_service_missing_records_are_typed_errors(tmp_path: Path) -> None:
    registry = RunRegistry(tmp_path / "runs.db")
    service = LineageService(registry_provider=lambda: registry)

    with pytest.raises(ServiceError) as run_error:
        service.run_lineage("missing")
    with pytest.raises(ServiceError) as dataset_error:
        service.get_dataset("missing")

    assert run_error.value.status_code == 404
    assert dataset_error.value.status_code == 404
