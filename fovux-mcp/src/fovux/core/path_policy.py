"""Centralized path policy enforcement for Fovux tool directory access."""

from __future__ import annotations

import contextlib
import contextvars
import os
import sys
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from fovux.core.errors import FovuxPathValidationError
from fovux.core.paths import get_fovux_home

_WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}

# Context variables for tracking active tool context across thread calls
_ACTIVE_TOOL = contextvars.ContextVar[str | None]("active_tool", default=None)
_INVOCATION_ROOTS = contextvars.ContextVar[set[Path] | None]("invocation_roots", default=None)


TOOL_PATH_CATEGORIES: dict[str, str] = {
    "active_learning_select": "mutating",
    "annotation_quality_check": "read_only",
    "benchmark_latency": "long_running",
    "dataset_augment": "dataset_write",
    "dataset_convert": "dataset_write",
    "dataset_find_duplicates": "dataset_read",
    "dataset_inspect": "dataset_read",
    "dataset_split": "dataset_write",
    "dataset_validate": "dataset_read",
    "distill_model": "run_write",
    "eval_compare": "read_only",
    "eval_error_analysis": "read_only",
    "eval_per_class": "read_only",
    "eval_run": "run_write",
    "export_onnx": "export_write",
    "export_tflite": "export_write",
    "fovux_doctor": "read_only",
    "infer_ensemble": "read_only",
    "infer_batch": "run_write",
    "infer_image": "read_only",
    "infer_rtsp": "run_write",
    "model_compare_visual": "read_only",
    "model_list": "read_only",
    "model_profile": "read_only",
    "quantize_int8": "export_write",
    "quantize_report": "read_only",
    "run_archive": "destructive",
    "run_compare": "read_only",
    "run_delete": "destructive",
    "run_tag": "mutating",
    "sync_to_mlflow": "export_write",
    "train_adjust": "run_write",
    "train_preflight": "read_only",
    "train_resume": "run_write",
    "train_start": "run_write",
    "train_status": "read_only",
    "train_stop": "mutating",
}


def get_fovux_temp_dir() -> Path:
    """Return a restricted temp directory dedicated to Fovux, resolving broad temp write risks."""
    tmp = Path(tempfile.gettempdir()) / "fovux"
    tmp.mkdir(parents=True, exist_ok=True)
    return tmp


def set_active_tool(
    tool_name: str, context_args: dict[str, Any]
) -> tuple[contextvars.Token[str | None], contextvars.Token[set[Path] | None]]:
    """Set the active tool and derive invocation-specific whitelisted paths from its arguments."""
    active_token = _ACTIVE_TOOL.set(tool_name)

    # Whitelist paths passed in the arguments
    roots = set()
    for val in context_args.values():
        if isinstance(val, str | Path):
            with contextlib.suppress(Exception):
                p = Path(val).expanduser().resolve(strict=False)
                if p.is_absolute():
                    roots.add(p)

    roots_token = _INVOCATION_ROOTS.set(roots)
    return active_token, roots_token


def reset_active_tool(
    active_token: contextvars.Token[str | None],
    roots_token: contextvars.Token[set[Path] | None],
) -> None:
    """Reset the active tool context variables."""
    _ACTIVE_TOOL.reset(active_token)
    _INVOCATION_ROOTS.reset(roots_token)


def get_allowed_roots(write: bool = False) -> list[Path]:
    """Retrieve the whitelisted roots allowed by the current tool's path policy."""
    tool_name = _ACTIVE_TOOL.get()
    if tool_name is None:
        # Default to base roots when called directly outside tool event
        home = get_fovux_home()
        cwd = Path(os.getcwd())
        temp_dir = get_fovux_temp_dir()
        return [home, cwd, temp_dir]

    category = TOOL_PATH_CATEGORIES.get(tool_name or "", "read_only")

    home = get_fovux_home()
    cwd = Path(os.getcwd())
    temp_dir = get_fovux_temp_dir()

    # Base allowed roots
    roots = [home, cwd, temp_dir]
    if "pytest" in sys.modules and os.environ.get("FOVUX_TEST_ALLOW_TEMP_DIR", "1") == "1":
        roots.append(Path(tempfile.gettempdir()))

    # Add invocation specific whitelisted roots
    roots.extend(_INVOCATION_ROOTS.get() or set())

    # Filter/specialize allowed roots based on category
    if write:
        if category == "dataset_write":
            # Allowed to write to home, cwd, temp, or invocation roots (which includes inputs)
            return roots
        elif category == "run_write":
            # Restricted: write runs to runs dir or temp
            run_roots = [home / "runs", temp_dir]
            if "pytest" in sys.modules and os.environ.get("FOVUX_TEST_ALLOW_TEMP_DIR", "1") == "1":
                run_roots.append(Path(tempfile.gettempdir()))
            return run_roots
        elif category == "export_write":
            # Restricted: write exports to exports dir, cwd, or temp
            export_roots = [home / "exports", cwd, temp_dir]
            if "pytest" in sys.modules and os.environ.get("FOVUX_TEST_ALLOW_TEMP_DIR", "1") == "1":
                export_roots.append(Path(tempfile.gettempdir()))
            return export_roots
        elif category == "destructive":
            # Restricted: destructive actions to runs or archive
            return [home / "runs", home / "archive"]
        elif category in ("read_only", "dataset_read"):
            # Write is not allowed under read-only path policies
            raise FovuxPathValidationError(
                "", "Write operation is prohibited by read-only path policy for this tool."
            )

    return roots


def check_path_policy(
    path: Path,
    write: bool = False,
    extra_roots: Iterable[Path] | None = None,
) -> Path:
    """Validate a path against the current tool's path policy."""
    # 1. Resolve path (detecting traversal)
    resolved_path = path.expanduser().resolve(strict=False)

    # 2. Check Windows reserved names
    for part in resolved_path.parts:
        name_upper = part.split(".", maxsplit=1)[0].upper()
        if name_upper in _WINDOWS_RESERVED_NAMES:
            raise FovuxPathValidationError(str(path), f"uses reserved Windows device name '{part}'")

    tool_name = _ACTIVE_TOOL.get()
    if tool_name is None:
        return resolved_path

    # 3. Check allowed roots
    allowed = get_allowed_roots(write=write)
    resolved_allowed = [r.expanduser().resolve(strict=False) for r in allowed]

    if extra_roots is not None:
        for extra in extra_roots:
            with contextlib.suppress(Exception):
                resolved_allowed.append(extra.expanduser().resolve(strict=False))

    for root in resolved_allowed:
        try:
            resolved_path.relative_to(root)
            return resolved_path
        except ValueError:
            continue

    allowed_display = ", ".join(str(r) for r in resolved_allowed)
    raise FovuxPathValidationError(str(path), f"escapes allowed roots: {allowed_display}")
