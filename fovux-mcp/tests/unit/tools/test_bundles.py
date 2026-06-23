"""Unit tests for Fovux bundles and policy mode tools."""

from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path

import pytest

from fovux.config import clear_config_cache
from fovux.core.errors import FovuxError
from fovux.core.paths import FovuxPaths
from fovux.core.runs import get_registry
from fovux.core.tooling import tool_event
from fovux.http.tool_proxy import HttpToolPolicyError, available_tools, policy_for_tool
from fovux.tools.bundles import (
    export_reproducibility_bundle,
    generate_support_bundle,
    get_policy_status,
    list_audit_events,
    set_policy_mode,
)


@pytest.fixture
def mock_fovux_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Fixture to mock FOVUX_HOME environment variable and directories."""
    home_dir = tmp_path / ".fovux"
    home_dir.mkdir()
    monkeypatch.setenv("FOVUX_HOME", str(home_dir))
    monkeypatch.setattr("fovux.core.paths.get_fovux_home", lambda: home_dir)
    monkeypatch.setattr("fovux.core.telemetry.get_fovux_home", lambda: home_dir)
    monkeypatch.setattr("fovux.config.get_fovux_home", lambda: home_dir)

    # Pre-create standard config.toml
    from fovux.config import write_default_config

    write_default_config(home_dir / "config.toml")
    clear_config_cache()

    return home_dir


def test_policy_mode_lifecycle(mock_fovux_home: Path) -> None:
    """Test policy mode status retrieval and update lifecycle."""
    status = get_policy_status()
    assert status["policy_mode"] == "developer"
    assert "fovux_doctor" in status["allowed_tools"]
    assert "run_delete" in status["allowed_tools"]
    assert status["requires_confirmation"]["run_delete"] is True
    assert status["scopes_enforced"] is True

    # 1. Test set_policy_mode to 'safe'
    updated = set_policy_mode("safe")
    assert updated["policy_mode"] == "safe"

    # Destructive tools (e.g. run_delete) should be disabled in safe mode
    assert "run_delete" not in updated["allowed_tools"]
    assert "run_delete" not in available_tools()

    with pytest.raises(HttpToolPolicyError):
        policy_for_tool("run_delete")

    # 2. Test set_policy_mode to 'automation' (disables confirmations)
    updated = set_policy_mode("automation")
    assert updated["policy_mode"] == "automation"
    assert updated["requires_confirmation"]["train_start"] is False

    # 3. Test set_policy_mode to 'lab' (disables confirmation and scopes)
    updated = set_policy_mode("lab")
    assert updated["policy_mode"] == "lab"
    assert updated["scopes_enforced"] is False

    # 4. Test invalid mode
    with pytest.raises(FovuxError):
        set_policy_mode("unsafe")


def test_audit_event_logging(mock_fovux_home: Path) -> None:
    """Test that tool calls automatically record events to SQLite audit log."""
    # Invoke a dummy tool event
    with tool_event("fovux_doctor", requested_run_id="run_123", dataset_path="test.yaml"):
        pass

    # Retrieve audit events
    audit_data = list_audit_events(limit=10)
    events = audit_data["events"]
    assert len(events) >= 1

    doctor_event = next(e for e in events if e["action"] == "fovux_doctor")
    assert doctor_event["actor"] == "client"
    assert doctor_event["entity_type"] == "tool"
    assert doctor_event["details"]["status"] == "success"
    assert any("test.yaml" in p for p in doctor_event["details"]["resolved_target_paths"])


def test_reproducibility_bundle_generation(mock_fovux_home: Path) -> None:
    """Test generating a reproducibility bundle for a run."""
    paths = FovuxPaths(mock_fovux_home)
    registry = get_registry(paths.runs_db)

    run_id = "run_test_repro"
    run_dir = paths.run_dir(run_id)
    run_dir.mkdir(parents=True)
    (run_dir / "weights").mkdir()
    (run_dir / "weights" / "best.pt").write_bytes(b"dummy_weights")

    # Create fake run in registry
    registry.reserve_run_slot(
        run_id=run_id,
        run_path=run_dir,
        model="yolov8n.pt",
        dataset_path=mock_fovux_home / "data.yaml",
        task="detect",
        epochs=10,
        max_concurrent_runs=10,
    )
    registry.add_artifact(
        artifact_id="art_1",
        run_id=run_id,
        artifact_type="checkpoint",
        path=run_dir / "weights" / "best.pt",
    )
    registry.update_status(run_id, "running")
    registry.update_status(run_id, "complete")

    # Export bundle
    zip_path = mock_fovux_home / "repro.zip"
    res = export_reproducibility_bundle(run_id=run_id, destination_path=str(zip_path))

    assert zip_path.exists()
    assert res["size_bytes"] > 0
    assert res["manifest"]["run_id"] == run_id

    # Verify zip content
    with zipfile.ZipFile(zip_path, "r") as z:
        files = z.namelist()
        assert "reproducibility_manifest.json" in files
        assert "model_card.md" in files
        assert "weights/best.pt" in files

        manifest = json.loads(z.read("reproducibility_manifest.json").decode("utf-8"))
        assert manifest["status"] == "complete"


def test_support_bundle_generation(mock_fovux_home: Path) -> None:
    """Test generating a redacted support bundle."""
    # Write some logs
    log_file = mock_fovux_home / "fovux.log"
    log_file.write_text(
        "INFO tool_start fovux_doctor\nINFO tool_end fovux_doctor\n",
        encoding="utf-8",
    )

    # Add a secret to env to test redaction
    os.environ["PYPI_TOKEN"] = "sensitive_secret_token"  # noqa: S105

    zip_path = mock_fovux_home / "support.zip"
    res = generate_support_bundle(destination_path=str(zip_path))

    assert zip_path.exists()
    assert res["size_bytes"] > 0

    with zipfile.ZipFile(zip_path, "r") as z:
        files = z.namelist()
        assert "support_manifest.json" in files
        assert "recent_logs.txt" in files

        manifest = json.loads(z.read("support_manifest.json").decode("utf-8"))
        assert "PYPI_TOKEN" in manifest["env_summary"]["env_vars"]
        assert (
            manifest["env_summary"]["env_vars"]["PYPI_TOKEN"] == "[REDACTED]"  # noqa: S105
        )

        log_content = z.read("recent_logs.txt").decode("utf-8")
        assert "fovux_doctor" in log_content
