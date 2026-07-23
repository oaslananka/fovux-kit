"""Focused operation repository lifecycle tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from fovux.core.run_registry.database import RegistryDatabase
from fovux.core.run_registry.operation_repository import OperationRepository


def test_operation_repository_enforces_terminal_state(tmp_path: Path) -> None:
    database = RegistryDatabase(tmp_path / "runs.db")
    repository = OperationRepository(database.session_factory)
    try:
        repository.create_operation("op_tx", "model_list", {})
        repository.update_operation_status("op_tx", "running")
        repository.update_operation_status(
            "op_tx",
            "succeeded",
            result={"ok": True},
        )

        with pytest.raises(ValueError, match="Invalid operation status transition"):
            repository.update_operation_status(
                "op_tx",
                "failed",
                error="late failure",
            )

        record = repository.get_operation("op_tx")
        assert record is not None
        assert record.status == "succeeded"
        assert record.error is None
        assert record.result_json == '{"ok": true}'
    finally:
        database.close()


def test_operation_repository_preserves_missing_update_noops(tmp_path: Path) -> None:
    database = RegistryDatabase(tmp_path / "runs.db")
    repository = OperationRepository(database.session_factory)
    try:
        repository.update_operation_status("missing", "running")
        repository.update_operation_progress("missing", 50)
        assert repository.get_operation("missing") is None
    finally:
        database.close()


def test_operation_repository_preserves_idempotency_lookup(tmp_path: Path) -> None:
    database = RegistryDatabase(tmp_path / "runs.db")
    repository = OperationRepository(database.session_factory)
    try:
        created = repository.create_operation(
            "op_key",
            "model_list",
            {},
            idempotency_key="same-request",
        )
        found = repository.get_operation_by_idempotency_key("same-request")
        assert found is not None
        assert found.id == created.id
    finally:
        database.close()
