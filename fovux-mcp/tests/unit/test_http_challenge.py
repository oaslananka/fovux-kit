"""Tests for server-issued confirmation challenge flow (Issue #58)."""

from __future__ import annotations

import os
import tempfile
import time
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from fovux.http.app import create_app
from fovux.http.challenge import (
    CHALLENGE_TTL_SECONDS,
    create_challenge,
    make_challenge_id,
    prune_expired_challenges,
    verify_challenge,
)
from fovux.http.tool_proxy import HttpToolPolicyError


def _auth_headers(client: TestClient) -> dict[str, str]:
    token = str(client.app.state.auth_token)
    return {"Authorization": f"Bearer {token}"}


class TestChallengeUnit:
    """Unit tests for challenge data structures and logic."""

    def test_make_challenge_id_is_hex(self) -> None:
        cid = make_challenge_id()
        assert len(cid) == 32
        int(cid, 16)

    def test_create_challenge_sets_expected_fields(self) -> None:
        path = os.path.join(tempfile.gettempdir(), "dataset")
        record = create_challenge(
            tool_name="train_start",
            args_hash="abc123",
            risk_level="long_running",
            resolved_paths=[path],
        )
        assert record.tool_name == "train_start"
        assert record.args_hash == "abc123"
        assert record.risk_level == "long_running"
        assert record.resolved_paths == [path]
        assert record.used is False
        assert record.expires_at > record.created_at
        assert record.expires_at - record.created_at == pytest.approx(CHALLENGE_TTL_SECONDS, abs=1)

    def test_verify_challenge_succeeds(self) -> None:
        record = create_challenge(tool_name="echo", args_hash="hash1", risk_level="mutating")
        challenges = {record.challenge_id: record}
        verify_challenge(
            challenges,
            challenge_id=record.challenge_id,
            tool_name="echo",
            args_hash="hash1",
        )
        assert record.used is True

    def test_verify_missing_challenge(self) -> None:
        with pytest.raises(HttpToolPolicyError, match="not found"):
            verify_challenge({}, challenge_id="nonexistent", tool_name="echo", args_hash="h")

    def test_verify_used_challenge(self) -> None:
        record = create_challenge(tool_name="echo", args_hash="h", risk_level="mutating")
        record.used = True
        with pytest.raises(HttpToolPolicyError, match="already been used"):
            verify_challenge(
                {record.challenge_id: record},
                challenge_id=record.challenge_id,
                tool_name="echo",
                args_hash="h",
            )

    def test_verify_expired_challenge(self) -> None:
        record = create_challenge(tool_name="echo", args_hash="h", risk_level="mutating")
        record.expires_at = time.monotonic() - 1.0
        with pytest.raises(HttpToolPolicyError, match="expired"):
            verify_challenge(
                {record.challenge_id: record},
                challenge_id=record.challenge_id,
                tool_name="echo",
                args_hash="h",
            )

    def test_verify_wrong_tool(self) -> None:
        record = create_challenge(tool_name="train_start", args_hash="h", risk_level="mutating")
        with pytest.raises(HttpToolPolicyError, match="not .*train_stop"):
            verify_challenge(
                {record.challenge_id: record},
                challenge_id=record.challenge_id,
                tool_name="train_stop",
                args_hash="h",
            )

    def test_verify_wrong_args_hash(self) -> None:
        record = create_challenge(tool_name="echo", args_hash="hash1", risk_level="mutating")
        with pytest.raises(HttpToolPolicyError, match="arguments"):
            verify_challenge(
                {record.challenge_id: record},
                challenge_id=record.challenge_id,
                tool_name="echo",
                args_hash="hash2",
            )

    def test_prune_expired_challenges(self) -> None:
        fresh = create_challenge(tool_name="echo", args_hash="a", risk_level="mutating")
        stale = create_challenge(tool_name="echo", args_hash="b", risk_level="mutating")
        stale.expires_at = time.monotonic() - 1.0
        challenges = {fresh.challenge_id: fresh, stale.challenge_id: stale}
        pruned = prune_expired_challenges(challenges)
        assert pruned == 1
        assert fresh.challenge_id in challenges
        assert stale.challenge_id not in challenges


class TestChallengeAPI:
    """Integration tests for the challenge HTTP endpoints."""

    def test_challenge_creation_returns_201(self) -> None:
        with TestClient(create_app()) as client:
            response = client.post(
                "/tools/train_start/challenge",
                json={"dataset_path": "/some/data"},
                headers=_auth_headers(client),
            )
        assert response.status_code == 201
        body = response.json()
        assert "challenge_id" in body
        assert body["tool"] == "train_start"
        assert body["risk_level"] == "long_running"
        assert "summary" in body
        assert body["summary"]["name"] == "train_start"
        assert body["summary"]["params"]["dataset_path"] == "/some/data"
        assert "expires_at" in body

    def test_challenge_requires_auth(self) -> None:
        with TestClient(create_app()) as client:
            response = client.post(
                "/tools/train_start/challenge",
                json={"dataset_path": "/some/data"},
            )
        assert response.status_code == 401

    def test_challenge_unknown_tool_returns_403(self) -> None:
        with TestClient(create_app()) as client:
            response = client.post(
                "/tools/ghost_tool/challenge",
                json={},
                headers=_auth_headers(client),
            )
        assert response.status_code == 403

    def test_challenge_readonly_tool_returns_403(self) -> None:
        with TestClient(create_app()) as client:
            response = client.post(
                "/tools/model_list/challenge",
                json={},
                headers=_auth_headers(client),
            )
        assert response.status_code == 403
        detail = response.json()["detail"]
        assert detail["code"] == "FOVUX_HTTP_003"

    def test_tool_proxy_requires_challenge_for_risky_tool(self) -> None:
        with TestClient(create_app()) as client:
            response = client.post(
                "/tools/train_start",
                json={"dataset_path": "/some/data"},
                headers=_auth_headers(client),
            )
        assert response.status_code == 403
        detail = response.json()["detail"]
        assert "challenge" in detail["message"].lower()

    @patch("fovux.http.tool_proxy.invoke_tool", return_value={"status": "ok"})
    def test_tool_proxy_with_valid_challenge_succeeds(self, mock_invoke: object) -> None:
        with TestClient(create_app()) as client:
            headers = _auth_headers(client)
            challenge_resp = client.post(
                "/tools/train_start/challenge",
                json={"dataset_path": "/some/data"},
                headers=headers,
            )
            assert challenge_resp.status_code == 201
            cid = challenge_resp.json()["challenge_id"]

            response = client.post(
                "/tools/train_start",
                json={"dataset_path": "/some/data", "challenge_id": cid},
                headers=headers,
            )
        assert response.status_code == 200

    @patch("fovux.http.tool_proxy.invoke_tool", return_value={"status": "ok"})
    def test_tool_proxy_reuses_challenge(self, mock_invoke: object) -> None:
        with TestClient(create_app()) as client:
            headers = _auth_headers(client)
            challenge_resp = client.post(
                "/tools/train_start/challenge",
                json={"dataset_path": "/some/data"},
                headers=headers,
            )
            assert challenge_resp.status_code == 201
            cid = challenge_resp.json()["challenge_id"]

            client.post(
                "/tools/train_start",
                json={"dataset_path": "/some/data", "challenge_id": cid},
                headers=headers,
            )

            second = client.post(
                "/tools/train_start",
                json={"dataset_path": "/some/data", "challenge_id": cid},
                headers=headers,
            )
        assert second.status_code == 403
        assert "already been used" in second.json()["detail"]["message"]

    def test_readonly_tool_does_not_require_challenge(self) -> None:
        with TestClient(create_app()) as client:
            response = client.post(
                "/tools/model_list",
                json={},
                headers=_auth_headers(client),
            )
        assert response.status_code == 200

    def test_challenge_with_expired_monotonic_clock(self) -> None:
        record = create_challenge(tool_name="echo", args_hash="h", risk_level="mutating")
        challenges = {record.challenge_id: record}
        original = CHALLENGE_TTL_SECONDS

        try:
            import fovux.http.challenge as ch
            ch.CHALLENGE_TTL_SECONDS = -1
            record.expires_at = time.monotonic() + ch.CHALLENGE_TTL_SECONDS
            time.sleep(0.01)
            with pytest.raises(HttpToolPolicyError, match="expired"):
                verify_challenge(
                    challenges,
                    challenge_id=record.challenge_id,
                    tool_name="echo",
                    args_hash="h",
                )
        finally:
            ch.CHALLENGE_TTL_SECONDS = original
