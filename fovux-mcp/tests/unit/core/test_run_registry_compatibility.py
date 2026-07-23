"""Compatibility tests for the public fovux.core.runs module."""

from __future__ import annotations

import inspect
from pathlib import Path

import fovux.core.runs as compatibility
from fovux.core.run_registry.facade import RunRegistry as FacadeRunRegistry
from fovux.core.run_registry.models import RunRecord as ModelRunRecord


def test_compatibility_module_reexports_identical_types() -> None:
    assert compatibility.RunRegistry is FacadeRunRegistry
    assert compatibility.RunRecord is ModelRunRecord


def test_facade_preserves_create_run_parameters() -> None:
    signature = inspect.signature(compatibility.RunRegistry.create_run)

    assert list(signature.parameters) == [
        "self",
        "run_id",
        "run_path",
        "model",
        "dataset_path",
        "task",
        "epochs",
        "tags",
        "extra",
        "dataset_fingerprint",
        "config_hash",
        "code_version",
        "env_summary",
        "parent_run_id",
    ]
    assert signature.parameters["tags"].default is None
    assert signature.parameters["parent_run_id"].default is None
    assert str(signature.return_annotation) == "RunRecord"


def test_facade_preserves_private_engine_and_session_aliases(tmp_path: Path) -> None:
    registry = compatibility.RunRegistry(tmp_path / "runs.db")
    try:
        assert registry._engine is registry._database.engine
        assert registry._Session is registry._database.session_factory
    finally:
        registry.close()


def test_internal_repository_uses_typed_run_request() -> None:
    """Internal persistence APIs should not repeat the public facade signature."""
    from fovux.core.run_registry.run_repository import RunRepository

    reserve = inspect.signature(RunRepository.reserve_run_slot)
    create = inspect.signature(RunRepository.create_run)

    assert list(reserve.parameters) == ["self", "request", "max_concurrent_runs"]
    assert list(create.parameters) == ["self", "request"]
