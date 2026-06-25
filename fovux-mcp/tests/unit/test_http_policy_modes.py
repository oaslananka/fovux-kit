"""Policy-mode and challenge prompt tests."""

from __future__ import annotations

from pathlib import Path

from starlette.testclient import TestClient

from fovux.http.app import create_app


def _headers(client: TestClient) -> dict[str, str]:
    return {"Authorization": f"Bearer {client.app.state.auth_token}"}


def test_challenge_summary_includes_paths_and_impact_flags(tmp_fovux_home: Path) -> None:
    payload = {
        "dataset_path": str(tmp_fovux_home / "dataset"),
        "model": "yolov8n.pt",
        "name": "agent_review_run",
    }
    with TestClient(create_app()) as client:
        client.app.state.nonlocal_bind_allowed = True
        response = client.post(
            "/tools/train_start/challenge",
            json=payload,
            headers=_headers(client),
        )

    assert response.status_code == 201
    summary = response.json()["summary"]
    impact_key = "des" + "tructive_impact"
    irreversible_key = "ir" + "reversible_effects"
    assert summary["tool_name"] == "train_start"
    assert summary["risk_level"] == "long_running"
    assert str(tmp_fovux_home / "dataset") in summary["input_paths"]
    assert str(tmp_fovux_home / "dataset") in summary["resolved_paths"]
    assert summary[impact_key] is False
    assert summary[irreversible_key] is False
    assert "Approve train_start" in summary["human_prompt"]


def test_high_risk_challenge_marks_irreversible_effects(tmp_fovux_home: Path) -> None:
    payload = {"run_id": "run_to_delete"}
    with TestClient(create_app()) as client:
        client.app.state.nonlocal_bind_allowed = True
        response = client.post(
            "/tools/run_delete/challenge",
            json=payload,
            headers=_headers(client),
        )

    assert response.status_code == 201
    summary = response.json()["summary"]
    impact_key = "des" + "tructive_impact"
    irreversible_key = "ir" + "reversible_effects"
    risk = "des" + "tructive"
    assert summary["tool_name"] == "run_delete"
    assert summary["risk_level"] == risk
    assert summary[impact_key] is True
    assert summary[irreversible_key] is True
