"""Unit tests for fovux.core.errors."""

from __future__ import annotations

from fovux.core.errors import (
    FovuxCheckpointNotFoundError,
    FovuxDatasetEmptyError,
    FovuxDatasetFormatError,
    FovuxDatasetNotFoundError,
    FovuxError,
    FovuxExportParityError,
    FovuxRtspConnectionError,
)


def test_base_error_str() -> None:
    """FovuxError __str__ should include code and message."""
    err = FovuxError("something went wrong")
    assert "FOVUX_000" in str(err)
    assert "something went wrong" in str(err)


def test_base_error_with_hint() -> None:
    """FovuxError with hint should include the hint."""
    err = FovuxError("bad input", hint="try this instead")
    assert "try this instead" in str(err)


def test_dataset_not_found_code() -> None:
    """FovuxDatasetNotFoundError should have the right code."""
    err = FovuxDatasetNotFoundError("/nonexistent/path")
    assert err.code == "FOVUX_DATASET_001"
    assert "/nonexistent/path" in str(err)


def test_dataset_empty_code() -> None:
    """FovuxDatasetEmptyError should have the right code."""
    err = FovuxDatasetEmptyError("/empty/path")
    assert err.code == "FOVUX_DATASET_003"


def test_checkpoint_not_found_code() -> None:
    """FovuxCheckpointNotFoundError should have the right code."""
    err = FovuxCheckpointNotFoundError("/missing/best.pt")
    assert err.code == "FOVUX_EVAL_001"


def test_rtsp_error_code() -> None:
    """FovuxRtspConnectionError should have the right code."""
    err = FovuxRtspConnectionError("rtsp://192.168.1.1/stream")
    assert err.code == "FOVUX_INFER_001"
    assert "rtsp://" in str(err)


def test_error_hierarchy() -> None:
    """All errors should be subclasses of FovuxError."""
    for cls in [
        FovuxDatasetNotFoundError,
        FovuxDatasetFormatError,
        FovuxDatasetEmptyError,
        FovuxCheckpointNotFoundError,
        FovuxExportParityError,
        FovuxRtspConnectionError,
    ]:
        assert issubclass(cls, FovuxError)
