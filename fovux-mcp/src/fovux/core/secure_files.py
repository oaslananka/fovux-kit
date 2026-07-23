"""Symlink-safe, atomic filesystem writes for trusted Fovux roots."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from fovux.core.errors import FovuxPathValidationError


def resolve_under_root(root: Path, relative_path: Path) -> Path:
    """Resolve a relative path below ``root`` without following an escaping symlink."""
    trusted_root = root.expanduser().resolve(strict=False)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise FovuxPathValidationError(
            str(relative_path),
            f"must be a relative path below trusted root {trusted_root}",
        )

    candidate = trusted_root / relative_path
    if candidate.is_symlink():
        raise FovuxPathValidationError(
            str(candidate),
            "final path is a symlink and cannot be used for a sensitive write",
        )

    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(trusted_root)
    except ValueError as exc:
        raise FovuxPathValidationError(
            str(candidate),
            f"resolved path escapes trusted root {trusted_root}",
        ) from exc
    return resolved


def atomic_write_text(
    root: Path,
    relative_path: Path,
    content: str,
    *,
    encoding: str = "utf-8",
    mode: int = 0o600,
) -> Path:
    """Atomically replace one text file below a trusted root."""
    trusted_root = root.expanduser().resolve(strict=False)
    trusted_root.mkdir(parents=True, exist_ok=True)
    target = resolve_under_root(trusted_root, relative_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target = resolve_under_root(trusted_root, relative_path)

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=target.parent,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding=encoding) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_path, mode)
        os.replace(temporary_path, target)  # NOSONAR -- target is validated below trusted_root.
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
    return target
