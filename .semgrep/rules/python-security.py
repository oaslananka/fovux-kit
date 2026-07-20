"""Semgrep fixtures; this file is not executed."""

import subprocess
import yaml


def unsafe_shell(command: str) -> None:
    # ruleid: fovux.python.subprocess-shell-true
    subprocess.run(command, shell=True, check=True)


def safe_subprocess(arguments: list[str]) -> None:
    # ok: fovux.python.subprocess-shell-true
    subprocess.run(arguments, check=True)


def unsafe_dynamic_code(source: str) -> object:
    # ruleid: fovux.python.dynamic-code-execution
    return eval(source)


def unsafe_exec(source: str) -> None:
    # ruleid: fovux.python.dynamic-code-execution
    exec(source)


def safe_literal() -> int:
    # ok: fovux.python.dynamic-code-execution
    return int("42")


def unsafe_yaml(document: str) -> object:
    # ruleid: fovux.python.unsafe-yaml-load
    return yaml.unsafe_load(document)


def unsafe_yaml_loader(document: str) -> object:
    # ruleid: fovux.python.unsafe-yaml-load
    return yaml.load(document, Loader=yaml.Loader)


def safe_yaml(document: str) -> object:
    # ok: fovux.python.unsafe-yaml-load
    return yaml.safe_load(document)
