"""Tests for run management tools."""

from __future__ import annotations

from pathlib import Path

import pytest

from fovux.core.errors import (
    FovuxPathValidationError,
    FovuxTrainingError,
    FovuxTrainingRunNotFoundError,
)
from fovux.core.paths import ensure_fovux_dirs
from fovux.core.runs import close_registry, get_registry
from fovux.schemas.management import RunArchiveInput, RunDeleteInput, RunTagInput
from fovux.tools.run_archive import _run_run_archive
from fovux.tools.run_delete import _run_delete
from fovux.tools.run_tag import _normalize_tags, _run_tag


@pytest.fixture()
def run_home(tmp_fovux_home: Path):
    """Create a registry with one completed and one running run."""
    paths = ensure_fovux_dirs(tmp_fovux_home)
    registry = get_registry(paths.runs_db)
    completed_path = paths.runs / "run_done"
    running_path = paths.runs / "run_busy"
    completed_path.mkdir(parents=True)
    running_path.mkdir(parents=True)
    completed_path.joinpath("artifact.txt").write_text("done", encoding="utf-8")
    registry.create_run(
        run_id="run_done",
        run_path=completed_path,
        model="yolov8n.pt",
        dataset_path=tmp_fovux_home / "dataset",
        task="detect",
        epochs=1,
        tags=["old"],
    )
    registry.update_status("run_done", "complete")
    registry.create_run(
        run_id="run_busy",
        run_path=running_path,
        model="yolov8n.pt",
        dataset_path=tmp_fovux_home / "dataset",
        task="detect",
        epochs=1,
    )
    registry.update_status("run_busy", "running", pid=123)
    yield paths, registry, completed_path, running_path
    close_registry(paths.runs_db)


def test_run_delete_removes_registry_and_files(run_home) -> None:
    """Deleting a completed run should remove both record and directory."""
    paths, registry, completed_path, _running_path = run_home

    out = _run_delete(RunDeleteInput(run_id="run_done", delete_files=True))

    assert out.deleted_registry is True
    assert out.deleted_files is True
    assert registry.get_run("run_done") is None
    assert not completed_path.exists()
    close_registry(paths.runs_db)


def test_run_delete_refuses_running_without_force(run_home) -> None:
    """A running run should require force before deletion."""
    _paths, _registry, _completed_path, _running_path = run_home

    with pytest.raises(FovuxTrainingError):
        _run_delete(RunDeleteInput(run_id="run_busy", delete_files=True, force=False))


def test_run_delete_unknown_run_raises(run_home) -> None:
    """Unknown run IDs should produce a stable not-found error."""
    with pytest.raises(FovuxTrainingRunNotFoundError):
        _run_delete(RunDeleteInput(run_id="missing"))


def test_run_archive_rejects_registry_path_escape(run_home, tmp_path: Path) -> None:
    """Archive must not trust registry paths that escape the configured runs root."""
    paths, registry, _completed_path, _running_path = run_home
    escaped_path = tmp_path / "escaped_run"
    escaped_path.mkdir()
    registry.create_run(
        run_id="escaped",
        run_path=escaped_path,
        model="yolov8n.pt",
        dataset_path=tmp_path / "dataset",
        task="detect",
        epochs=1,
    )
    registry.update_status("escaped", "complete")

    with pytest.raises(FovuxPathValidationError):
        _run_run_archive(RunArchiveInput(run_id="escaped"))


def test_run_tag_normalizes_and_persists_tags(run_home) -> None:
    """run_tag should trim, deduplicate, sort, and persist tags."""
    _paths, registry, _completed_path, _running_path = run_home

    out = _run_tag(RunTagInput(run_id="run_done", tags=[" edge ", "", "baseline", "edge"]))
    record = registry.get_run("run_done")

    assert out.tags == ["baseline", "edge"]
    assert record is not None
    assert record.tags_json == '["baseline", "edge"]'


def test_run_tag_unknown_run_raises(run_home) -> None:
    """Unknown runs cannot be tagged."""
    with pytest.raises(FovuxTrainingRunNotFoundError):
        _run_tag(RunTagInput(run_id="missing", tags=["x"]))


def test_normalize_tags_returns_sorted_unique_values() -> None:
    """Tag normalization should be deterministic."""
    assert _normalize_tags([" z ", "a", "", "a"]) == ["a", "z"]
