"""Fovux exception hierarchy.

All exceptions raised by Fovux tools are subclasses of FovuxError.
External library exceptions (ultralytics, cv2, onnx) must never bubble up raw.
"""

from __future__ import annotations


class FovuxError(Exception):
    """Base exception for all Fovux errors.

    Attributes:
        code: Stable error code string (e.g. FOVUX_DATASET_001).
        message: Human-readable description.
        hint: Optional remediation hint for the user.
    """

    code: str = "FOVUX_000"

    def __init__(self, message: str, hint: str | None = None) -> None:
        """Initialize FovuxError.

        Args:
            message: Human-readable error description.
            hint: Optional remediation hint.
        """
        super().__init__(message)
        self.message = message
        self.hint = hint

    def __str__(self) -> str:
        """Return formatted error string."""
        base = f"[{self.code}] {self.message}"
        if self.hint:
            return f"{base}\nHint: {self.hint}"
        return base


# Dataset errors (FOVUX_DATASET_*)


class FovuxDatasetError(FovuxError):
    """Base class for dataset-related errors."""

    code = "FOVUX_DATASET_000"


class FovuxDatasetNotFoundError(FovuxDatasetError):
    """Dataset path does not exist."""

    code = "FOVUX_DATASET_001"

    def __init__(self, path: str) -> None:
        """Initialize with the missing path."""
        super().__init__(
            f"Dataset path not found: {path}",
            hint="Check that the path exists and is accessible.",
        )


class FovuxDatasetFormatError(FovuxDatasetError):
    """Dataset format cannot be detected or is malformed."""

    code = "FOVUX_DATASET_002"


class FovuxDatasetEmptyError(FovuxDatasetError):
    """Dataset contains zero images."""

    code = "FOVUX_DATASET_003"

    def __init__(self, path: str, message: str | None = None) -> None:
        """Initialize with the empty dataset path."""
        super().__init__(
            message or f"Dataset at {path} contains no images.",
            hint="Ensure the dataset root contains image files (jpg, png, bmp, webp).",
        )


# Training errors (FOVUX_TRAIN_*)


class FovuxTrainingError(FovuxError):
    """Base class for training-related errors."""

    code = "FOVUX_TRAIN_000"


class FovuxTrainingRunNotFoundError(FovuxTrainingError):
    """Run ID does not exist in the registry."""

    code = "FOVUX_TRAIN_001"

    def __init__(self, run_id: str) -> None:
        """Initialize with the missing run_id."""
        super().__init__(
            f"Run not found: {run_id}",
            hint="Use `model_list` to see available runs.",
        )


class FovuxTrainingAlreadyRunningError(FovuxTrainingError):
    """Attempt to start training on an already-running run."""

    code = "FOVUX_TRAIN_002"


class FovuxTrainingSubprocessError(FovuxTrainingError):
    """Training subprocess exited with non-zero code."""

    code = "FOVUX_TRAIN_003"


# Evaluation errors (FOVUX_EVAL_*)


class FovuxEvalError(FovuxError):
    """Base class for evaluation-related errors."""

    code = "FOVUX_EVAL_000"


class FovuxCheckpointNotFoundError(FovuxEvalError):
    """Checkpoint file does not exist."""

    code = "FOVUX_EVAL_001"

    def __init__(self, path: str) -> None:
        """Initialize with the missing checkpoint path."""
        super().__init__(
            f"Checkpoint not found: {path}",
            hint="Provide a valid .pt file path or a run_id with a best.pt.",
        )


# Export errors (FOVUX_EXPORT_*)


class FovuxExportError(FovuxError):
    """Base class for export-related errors."""

    code = "FOVUX_EXPORT_000"


class FovuxExportParityError(FovuxExportError):
    """Roundtrip parity check failed after export."""

    code = "FOVUX_EXPORT_001"


# Inference errors (FOVUX_INFER_*)


class FovuxInferenceError(FovuxError):
    """Base class for inference-related errors."""

    code = "FOVUX_INFER_000"


class FovuxRtspConnectionError(FovuxInferenceError):
    """RTSP stream could not be opened."""

    code = "FOVUX_INFER_001"

    def __init__(self, url: str) -> None:
        """Initialize with the failing RTSP URL."""
        super().__init__(
            f"Could not open RTSP stream: {url}",
            hint="Verify the stream URL, network connectivity, and credentials.",
        )


# Config errors (FOVUX_CONFIG_*)


class FovuxConfigError(FovuxError):
    """Base class for configuration errors."""

    code = "FOVUX_CONFIG_000"


class FovuxPathValidationError(FovuxConfigError):
    """Raised when a filesystem path violates local safety checks."""

    code = "FOVUX_CONFIG_001"

    def __init__(self, path: str, reason: str, hint: str | None = None) -> None:
        """Initialize the path validation error."""
        super().__init__(
            f"Path validation failed for {path}: {reason}",
            hint=hint or "Use a path inside the intended project or dataset root.",
        )
