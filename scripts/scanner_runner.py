"""Shared safe subprocess handling for optional local security scanners."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path

NOT_CONFIGURED_EXIT = 2
_ALLOWED_EXECUTABLES = frozenset({"gitleaks", "osv-scanner", "sonar-scanner", "trivy"})
_MAX_ARGUMENT_LENGTH = 2048


def _validated_command(command: Sequence[str]) -> tuple[str, ...]:
    """Validate scanner executable and arguments before OS execution."""
    if not command:
        raise ValueError("Scanner command must not be empty")
    executable = command[0]
    if executable not in _ALLOWED_EXECUTABLES:
        raise ValueError(f"Scanner executable is not approved: {executable}")

    validated: list[str] = []
    for argument in command:
        if not isinstance(argument, str):
            raise TypeError("Scanner arguments must be strings")
        if not argument or len(argument) > _MAX_ARGUMENT_LENGTH:
            raise ValueError("Scanner arguments must be non-empty and reasonably sized")
        if (
            not argument.isprintable()
            or "\r" in argument
            or "\n" in argument
            or "\x00" in argument
        ):
            raise ValueError(
                "Scanner arguments must contain printable single-line text"
            )
        validated.append(argument)
    return tuple(validated)


def verify_scanner_version(
    *,
    name: str,
    executable: str,
    version_args: Sequence[str],
    expected_version: str,
    version_pattern: str,
    required: bool,
) -> int | None:
    """Reject an installed scanner when its version differs from the repository pin."""
    validated = _validated_command((executable, *version_args))
    resolved_executable = shutil.which(executable)
    if resolved_executable is None:
        return None
    result = subprocess.run(  # noqa: S603
        [resolved_executable, *validated[1:]],
        check=False,
        capture_output=True,
        text=True,
    )
    match = re.search(
        version_pattern, f"{result.stdout}\n{result.stderr}", flags=re.MULTILINE
    )
    installed = match.group(1) if match else "unknown"
    if result.returncode == 0 and installed == expected_version:
        return None
    prefix = "ERROR" if required else "SKIP"
    print(
        f"{prefix}: {name} {expected_version} is required; "
        f"installed version is {installed}"
    )
    return NOT_CONFIGURED_EXIT if required else 0


def format_command(
    command: Sequence[str],
    *,
    environ: Mapping[str, str],
    token_names: Sequence[str],
) -> str:
    """Render a JSON argument array while replacing known token values."""
    redacted = list(_validated_command(command))
    for token_name in token_names:
        token = environ.get(token_name, "")
        if token:
            redacted = [argument.replace(token, "[REDACTED]") for argument in redacted]
    return json.dumps(redacted, ensure_ascii=True)


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
    validated = _validated_command(command)
    runtime_env = dict(os.environ if environ is None else environ)
    executable = validated[0]
    resolved_executable = shutil.which(executable)
    if resolved_executable is None:
        prefix = "ERROR" if required else "SKIP"
        print(f"{prefix}: {name} executable '{executable}' is not installed")
        return NOT_CONFIGURED_EXIT if required else 0

    missing_tokens = [
        token_name for token_name in token_names if not runtime_env.get(token_name)
    ]
    if missing_tokens:
        prefix = "ERROR" if required else "SKIP"
        print(f"{prefix}: {name} requires {', '.join(missing_tokens)}")
        return NOT_CONFIGURED_EXIT if required else 0

    print(
        f"RUN: {name}: "
        + format_command(validated, environ=runtime_env, token_names=token_names)
    )
    resolved_command = [resolved_executable, *validated[1:]]
    result = subprocess.run(  # noqa: S603
        resolved_command,
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
