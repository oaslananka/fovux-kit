"""Shared safe subprocess handling for optional local security scanners."""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path

NOT_CONFIGURED_EXIT = 2


def format_command(
    command: Sequence[str],
    *,
    environ: Mapping[str, str],
    token_names: Sequence[str],
) -> str:
    """Render a command while replacing known token values."""
    rendered = shlex.join(command)
    for token_name in token_names:
        token = environ.get(token_name, "")
        if token:
            rendered = rendered.replace(token, "[REDACTED]")
    return rendered


def run_scanner(
    *,
    name: str,
    command: Sequence[str],
    token_names: Sequence[str],
    required: bool,
    environ: Mapping[str, str] | None = None,
    cwd: Path | None = None,
) -> int:
    """Run one scanner command with explicit optional-local semantics."""
    if not command:
        raise ValueError("Scanner command must not be empty")

    runtime_env = dict(os.environ if environ is None else environ)
    executable = command[0]
    if shutil.which(executable) is None:
        prefix = "ERROR" if required else "SKIP"
        print(f"{prefix}: {name} executable '{executable}' is not installed")
        return NOT_CONFIGURED_EXIT if required else 0

    missing_tokens = [token_name for token_name in token_names if not runtime_env.get(token_name)]
    if missing_tokens:
        prefix = "ERROR" if required else "SKIP"
        print(f"{prefix}: {name} requires {', '.join(missing_tokens)}")
        return NOT_CONFIGURED_EXIT if required else 0

    print(f"RUN: {name}: " + format_command(command, environ=runtime_env, token_names=token_names))
    result = subprocess.run(  # noqa: S603 - fixed argument arrays, never shell input
        list(command),
        check=False,
        cwd=cwd,
        env=runtime_env,
        text=True,
    )
    if result.returncode == 0:
        print(f"PASS: {name}")
    else:
        print(f"ERROR: {name} exited with status {result.returncode}")
    return result.returncode
