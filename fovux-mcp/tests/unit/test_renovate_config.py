"""Tests for Fovux-specific Renovate policy validation."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "validate_renovate_config.py"
EXPECTED_MANAGERS = {
    "pep621",
    "npm",
    "github-actions",
    "dockerfile",
    "nvm",
    "pre-commit",
}
PROTECTED_PACKAGES = {"mcp", "fastmcp", "torch", "pillow", "onnxruntime"}


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("validate_renovate_config", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_config() -> dict[str, object]:
    data = json.loads((REPO_ROOT / "renovate.json").read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def test_repository_renovate_policy_is_valid() -> None:
    module = _load_module()

    assert module.validate_config(REPO_ROOT) == []


def test_repository_renovate_policy_has_expected_contract() -> None:
    module = _load_module()
    config = _load_config()

    assert "github>oaslananka/.github:renovate-config" in config["extends"]
    assert set(config["enabledManagers"]) == EXPECTED_MANAGERS
    assert config["timezone"] == "Europe/Istanbul"
    assert config["prHourlyLimit"] == 2
    assert config["prConcurrentLimit"] == 6

    labels = module.collect_configured_labels(config)
    assert labels <= module.load_label_names(REPO_ROOT / ".github" / "labels.yml")

    for package in PROTECTED_PACKAGES:
        assert module.package_is_non_automerge(config, package), package


def test_validator_rejects_missing_manager(tmp_path: Path) -> None:
    module = _load_module()
    config = _load_config()
    config["enabledManagers"] = [
        manager for manager in config["enabledManagers"] if manager != "pre-commit"
    ]
    _write_fixture_repo(tmp_path, config)

    errors = module.validate_config(tmp_path)

    assert any("pre-commit" in error for error in errors)


def test_validator_rejects_unknown_label(tmp_path: Path) -> None:
    module = _load_module()
    config = copy.deepcopy(_load_config())
    config["labels"] = ["dependencies", "not-a-real-label"]
    _write_fixture_repo(tmp_path, config)

    errors = module.validate_config(tmp_path)

    assert any("not-a-real-label" in error for error in errors)


def _write_fixture_repo(root: Path, config: dict[str, object]) -> None:
    (root / ".github").mkdir(parents=True)
    (root / "fovux-mcp").mkdir()
    (root / "fovux-studio").mkdir()
    (root / "fovux-mcp-npm").mkdir()
    (root / "renovate.json").write_text(json.dumps(config), encoding="utf-8")
    (root / ".github" / "labels.yml").write_text(
        "- name: dependencies\n- name: goal:supply-chain\n"
        "- name: python\n- name: python:uv\n- name: typescript\n"
        "- name: component:fovux-mcp\n- name: component:fovux-studio\n"
        "- name: component:fovux-mcp-npm\n- name: area:ci\n"
        "- name: area:security\n- name: area:compatibility\n"
        "- name: area:mcp\n- name: risk:high\n- name: major-update\n",
        encoding="utf-8",
    )
    for relative_path in (
        "fovux-mcp/pyproject.toml",
        "fovux-mcp/uv.lock",
        "fovux-studio/package.json",
        "fovux-studio/pnpm-lock.yaml",
        "fovux-mcp-npm/package.json",
        "fovux-mcp-npm/package-lock.json",
        "fovux-mcp/Dockerfile",
        ".nvmrc",
        ".pre-commit-config.yaml",
    ):
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n" if path.suffix == ".json" else "fixture\n", encoding="utf-8")
