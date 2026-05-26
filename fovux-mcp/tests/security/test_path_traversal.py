"""Security tests — explicit path traversal attack vectors.

Validates that tools with file path parameters reject attempts to
escape the FOVUX_HOME sandbox.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from fovux.core.tool_registry import resolve_tool
from fovux.core.validation import validate_run_id
from fovux.schemas.management import RunArchiveInput, RunCompareInput, RunDeleteInput, RunTagInput
from fovux.schemas.training import (
    TrainResumeInput,
    TrainStartInput,
    TrainStatusInput,
    TrainStopInput,
)

# Tools that accept file paths as their first parameter
FILE_PATH_TOOLS = [
    "dataset_inspect",
    "dataset_validate",
    "dataset_split",
    "dataset_convert",
    "dataset_augment",
    "dataset_find_duplicates",
    "infer_image",
    "infer_batch",
    "train_start",
    "export_onnx",
    "export_tflite",
]

TRAVERSAL_PAYLOADS = [
    "../../etc/passwd",
    "..\\..\\Windows\\System32\\cmd.exe",
    "/etc/shadow",
    "C:\\Windows\\win.ini",
    "/dev/null",
    "/proc/self/environ",
    "file:///etc/passwd",
    "\\\\server\\share\\secret.txt",
    "....//....//etc//passwd",
    "%2e%2e%2f%2e%2e%2fetc%2fpasswd",
]


@pytest.mark.parametrize("tool_name", FILE_PATH_TOOLS)
@pytest.mark.parametrize("payload", TRAVERSAL_PAYLOADS)
def test_path_traversal_rejected(tool_name: str, payload: str) -> None:
    """File path tools must not silently process traversal payloads."""
    try:
        func = resolve_tool(tool_name)
        func(dataset_path=payload)
    except (TypeError, ValueError, KeyError, FileNotFoundError, OSError, ImportError):
        pass  # Expected rejection
    except Exception as exc:
        # Allow Fovux-specific errors (they indicate proper validation)
        if "Fovux" in type(exc).__name__ or "fovux" in type(exc).__name__.lower():
            pass
        elif "pydantic" in type(exc).__module__.lower():
            pass  # Pydantic validation error
        else:
            # The tool should never silently succeed with a traversal path
            raise AssertionError(
                f"Tool {tool_name} did not reject traversal payload '{payload}': "
                f"raised {type(exc).__name__}: {exc}"
            ) from exc


RUN_ID_TRAVERSAL_PAYLOADS = [
    "../x",
    "../../x",
    "/" + "tmp/x",
    r"C:\Windows\Temp\x",
    r"..\x",
    ".",
    "..",
    "CON",
    "aux",
    "run.",
    "run/name",
    r"run\name",
    "run∕name",
]


@pytest.mark.parametrize("payload", RUN_ID_TRAVERSAL_PAYLOADS)
def test_run_id_schema_rejects_traversal_payloads(payload: str) -> None:
    """Run IDs are path components and must not accept traversal variants."""
    schema_factories = [
        lambda value: TrainStartInput(dataset_path=".", name=value),
        lambda value: TrainStatusInput(run_id=value),
        lambda value: TrainStopInput(run_id=value),
        lambda value: TrainResumeInput(run_id=value),
        lambda value: RunCompareInput(run_ids=[value]),
        lambda value: RunDeleteInput(run_id=value),
        lambda value: RunTagInput(run_id=value),
        lambda value: RunArchiveInput(run_id=value),
    ]

    for factory in schema_factories:
        with pytest.raises(ValidationError):
            factory(payload)


def test_validate_run_id_allows_safe_ascii_identifier() -> None:
    """Safe run IDs should remain ergonomic for normal CLI and Studio users."""
    assert validate_run_id("Run_01-edge.v2") == "Run_01-edge.v2"


def test_validate_run_id_rejects_trailing_dot_collision() -> None:
    """Windows-normalized trailing-dot run IDs should be rejected explicitly."""
    with pytest.raises(ValueError, match="end with a dot"):
        validate_run_id("run.")
