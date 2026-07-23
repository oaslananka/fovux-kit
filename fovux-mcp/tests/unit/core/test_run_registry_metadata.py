"""Focused tests for filesystem-derived registry metadata."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from fovux.core.run_registry.metadata import RunMetadataProvider


def test_run_metadata_falls_back_to_resolved_dataset_path(tmp_path: Path) -> None:
    provider = RunMetadataProvider()
    dataset_path = tmp_path / "missing-dataset"

    metadata = provider.build(
        model="yolo.pt",
        dataset_path=dataset_path,
        task="detect",
        epochs=3,
        extra={"batch": 4},
    )

    assert (
        metadata.dataset_fingerprint
        == hashlib.sha256(str(dataset_path.resolve()).encode("utf-8")).hexdigest()
    )
    assert len(metadata.config_hash) == 64
    assert metadata.code_version
    assert json.loads(metadata.env_summary)["python_version"]


def test_artifact_metadata_hashes_before_persistence(tmp_path: Path) -> None:
    provider = RunMetadataProvider()
    artifact = tmp_path / "weights.pt"
    artifact.write_bytes(b"model-bytes")

    metadata = provider.artifact_metadata(artifact, sha256=None, size=None)

    assert metadata.path == str(artifact.resolve())
    assert metadata.size == len(b"model-bytes")
    assert metadata.sha256 == hashlib.sha256(b"model-bytes").hexdigest()


def test_run_metadata_records_torch_environment_when_available(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = RunMetadataProvider()
    fake_torch = SimpleNamespace(
        __version__="2.test",
        cuda=SimpleNamespace(is_available=lambda: True),
    )
    monkeypatch.setitem(sys.modules, "torch", fake_torch)

    metadata = provider.build(
        model="yolo.pt",
        dataset_path=tmp_path / "dataset",
        task="detect",
        epochs=1,
        extra=None,
    )

    summary = json.loads(metadata.env_summary)
    assert summary["torch_version"] == "2.test"
    assert summary["cuda_available"] is True


def test_artifact_metadata_keeps_size_when_hash_read_fails(tmp_path: Path) -> None:
    provider = RunMetadataProvider()
    artifact = tmp_path / "weights.pt"
    artifact.write_bytes(b"model-bytes")

    with patch.object(Path, "open", side_effect=OSError("unreadable artifact")):
        metadata = provider.artifact_metadata(artifact, sha256=None, size=None)

    assert metadata.size == len(b"model-bytes")
    assert metadata.sha256 is None
