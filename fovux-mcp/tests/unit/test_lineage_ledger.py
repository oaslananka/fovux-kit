"""Unit tests for the experiment and artifact lineage ledger."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from fovux.core.runs import RunRegistry, close_registry
from fovux.http.app import create_app


@pytest.fixture()
def registry(tmp_path: Path) -> RunRegistry:
    """Return a fresh RunRegistry backed by a temp DB."""
    db_path = tmp_path / "test_lineage.db"
    reg = RunRegistry(db_path)
    yield reg
    reg.close()
    close_registry(db_path)


def _auth_headers(client: TestClient) -> dict[str, str]:
    token = str(client.app.state.auth_token)
    return {"Authorization": f"Bearer {token}"}


def test_migrations_and_tables_creation(registry: RunRegistry) -> None:
    """Initializing RunRegistry should run migrations and create all tables."""
    # Check that schema_migrations table is populated with version 1
    with registry._engine.connect() as conn:
        version = conn.execute(text("SELECT MAX(version) FROM schema_migrations")).scalar()
        assert version == 1

        # Check that the runs table has the new columns
        res = conn.execute(text("PRAGMA table_info(runs)")).fetchall()
        existing_cols = {r[1] for r in res}
        assert "dataset_fingerprint" in existing_cols
        assert "config_hash" in existing_cols
        assert "code_version" in existing_cols
        assert "env_summary" in existing_cols
        assert "parent_run_id" in existing_cols

        # Check other ledger tables exist
        for table in (
            "run_events",
            "datasets",
            "artifacts",
            "models",
            "exports",
            "metrics",
            "tags",
            "audit_events",
        ):
            count = conn.execute(
                text("SELECT count(*) FROM sqlite_master WHERE type='table' AND name=:table"),
                {"table": table},
            ).scalar()
            assert count == 1


def test_auto_metadata_and_lineage_population(registry: RunRegistry, tmp_path: Path) -> None:
    """reserve_run_slot should populate dataset fingerprint, config hash,
    and register dataset/model.
    """
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    yaml_file = dataset_dir / "data.yaml"
    yaml_file.write_text("names:\n  0: cat\n  1: dog\nnc: 2\n", encoding="utf-8")

    run_path = tmp_path / "runs" / "run_test_001"

    record = registry.reserve_run_slot(
        run_id="run_test_001",
        run_path=run_path,
        model="yolov8n.pt",
        dataset_path=dataset_dir,
        task="detect",
        epochs=10,
        max_concurrent_runs=1,
    )

    assert record.dataset_fingerprint is not None
    assert record.config_hash is not None
    assert record.code_version is not None
    assert record.env_summary is not None

    # Verify dataset is registered in datasets table
    db_dataset = registry.get_dataset(record.dataset_fingerprint)
    assert db_dataset is not None
    assert db_dataset.path == str(dataset_dir.resolve())
    class_map = json.loads(db_dataset.class_map_json)
    assert class_map == {"0": "cat", "1": "dog"}

    # Verify model is registered
    with registry._Session() as session:
        from fovux.core.runs import ModelRecord

        db_model = session.get(ModelRecord, "yolov8n.pt")
        assert db_model is not None
        assert db_model.task == "detect"

    # Verify initial run event is logged
    events = registry.list_run_events("run_test_001")
    assert len(events) == 1
    assert events[0].to_status == "pending"


def test_status_transitions_fsm(registry: RunRegistry, tmp_path: Path) -> None:
    """update_status must validate transitions according to the state machine."""
    registry.create_run(
        run_id="run_fsm",
        run_path=tmp_path / "run_fsm",
        model="yolov8n.pt",
        dataset_path=tmp_path / "dataset",
        task="detect",
        epochs=5,
    )

    # Valid transitions: pending -> running -> complete -> archived
    registry.update_status("run_fsm", "running")
    record = registry.get_run("run_fsm")
    assert record.status == "running"

    registry.update_status("run_fsm", "complete")
    record = registry.get_run("run_fsm")
    assert record.status == "complete"

    registry.update_status("run_fsm", "archived")
    record = registry.get_run("run_fsm")
    assert record.status == "archived"

    # Invalid transitions should raise ValueError
    registry.create_run(
        run_id="run_invalid",
        run_path=tmp_path / "run_invalid",
        model="yolov8n.pt",
        dataset_path=tmp_path / "dataset",
        task="detect",
        epochs=5,
    )

    # Cannot transition from complete to pending
    registry.update_status("run_invalid", "complete")
    with pytest.raises(ValueError, match="Invalid run status transition"):
        registry.update_status("run_invalid", "pending")


def test_artifacts_and_exports_ledgers(registry: RunRegistry, tmp_path: Path) -> None:
    """add_artifact and record_export should write to ledgers and populate properties."""
    run_id = "run_ledgers"
    registry.create_run(
        run_id=run_id,
        run_path=tmp_path / run_id,
        model="yolov8n.pt",
        dataset_path=tmp_path / "dataset",
        task="detect",
        epochs=5,
    )

    test_file = tmp_path / "best.pt"
    test_file.write_text("dummy model weights", encoding="utf-8")

    # Add artifact
    artifact = registry.add_artifact(
        artifact_id="art_best",
        run_id=run_id,
        artifact_type="checkpoint",
        path=test_file,
    )
    assert artifact.size == len("dummy model weights")
    assert artifact.sha256 is not None

    # Record export
    export_file = tmp_path / "best.onnx"
    export_file.write_text("onnx dummy", encoding="utf-8")

    export = registry.record_export(
        export_id="exp_onnx",
        run_id=run_id,
        source_checkpoint=test_file,
        artifact_path=export_file,
        format="onnx",
        duration_s=1.5,
        validation_result={"accuracy": 0.95},
    )

    assert export.format == "onnx"
    assert export.duration_s == 1.5

    # Check list methods
    artifacts = registry.list_artifacts(run_id)
    assert len(artifacts) == 2  # checkpoint and export

    exports = registry.list_exports(run_id)
    assert len(exports) == 1
    assert exports[0].id == "exp_onnx"


def test_metrics_ledger(registry: RunRegistry) -> None:
    """add_metric and list_metrics should write and query metrics correctly."""
    run_id = "run_metrics"
    registry.add_metric(run_id, 1, "map50", 0.75)
    registry.add_metric(run_id, 1, "loss", 0.25)
    registry.add_metric(run_id, 2, "map50", 0.82)

    metrics = registry.list_metrics(run_id)
    assert len(metrics) == 3
    assert metrics[0].epoch == 1
    assert metrics[0].metric_key == "map50"
    assert metrics[0].metric_value == 0.75
    assert metrics[2].epoch == 2
    assert metrics[2].metric_value == 0.82


def test_http_api_lineage_endpoints(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Lineage, datasets, and exports endpoints should return valid JSON ledger responses."""
    from fovux.core.paths import FovuxPaths

    paths = FovuxPaths(tmp_path)
    db_path = paths.runs_db
    reg = RunRegistry(db_path)

    # Mock ensure_fovux_dirs and runs_db path
    from fovux.core.paths import FovuxPaths

    monkeypatch.setattr("fovux.core.paths.ensure_fovux_dirs", lambda: FovuxPaths(tmp_path))

    reg.create_run(
        run_id="run_http",
        run_path=tmp_path / "run_http",
        model="yolov8n.pt",
        dataset_path=tmp_path / "dataset",
        task="detect",
        epochs=5,
    )

    test_file = tmp_path / "best.pt"
    test_file.write_text("model weights", encoding="utf-8")
    reg.add_artifact("art_weights", "run_http", "checkpoint", test_file)

    export_file = tmp_path / "best.onnx"
    export_file.write_text("onnx model", encoding="utf-8")
    reg.record_export("exp_onnx", "run_http", test_file, export_file, "onnx", 2.3)

    with TestClient(create_app()) as client:
        client.app.state.nonlocal_bind_allowed = True
        headers = _auth_headers(client)

        # GET /runs/{run_id}/lineage
        response = client.get("/runs/run_http/lineage", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["run_id"] == "run_http"
        assert len(data["artifacts"]) == 2
        assert len(data["exports"]) == 1
        assert len(data["events"]) == 1

        # GET /runs/{run_id}/events
        response = client.get("/runs/run_http/events", headers=headers)
        assert response.status_code == 200
        events = response.json()
        assert len(events) == 1
        assert events[0]["to_status"] == "pending"

        # GET /datasets
        response = client.get("/datasets", headers=headers)
        assert response.status_code == 200
        datasets = response.json()
        assert len(datasets) == 1

        # GET /datasets/{fingerprint}
        fingerprint = datasets[0]["fingerprint"]
        response = client.get(f"/datasets/{fingerprint}", headers=headers)
        assert response.status_code == 200
        assert response.json()["fingerprint"] == fingerprint

        # GET /exports
        response = client.get("/exports", headers=headers)
        assert response.status_code == 200
        exports = response.json()
        assert len(exports) == 1
        assert exports[0]["id"] == "exp_onnx"

    reg.close()
    close_registry(db_path)
