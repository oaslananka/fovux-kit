"""Validate the repository-specific Renovate policy without network access."""

from __future__ import annotations

import fnmatch
import json
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
EXPECTED_PRESET = "github>oaslananka/.github:renovate-config"
EXPECTED_MANAGERS = {
    "pep621",
    "npm",
    "github-actions",
    "dockerfile",
    "nvm",
    "pre-commit",
}
REQUIRED_MANIFESTS = (
    "fovux-mcp/pyproject.toml",
    "fovux-mcp/uv.lock",
    "fovux-studio/package.json",
    "fovux-studio/pnpm-lock.yaml",
    "fovux-mcp-npm/package.json",
    "fovux-mcp-npm/package-lock.json",
    "fovux-mcp/Dockerfile",
    ".nvmrc",
    ".pre-commit-config.yaml",
)
PROTECTED_PACKAGES = (
    "mcp",
    "fastmcp",
    "torch",
    "pillow",
    "onnxruntime",
)
_LABEL_LINE = re.compile(r"^\s*-\s+name:\s*[\"']?(.+?)[\"']?\s*$")


def load_config(path: Path) -> dict[str, Any]:
    """Load one Renovate JSON file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return data


def load_label_names(path: Path) -> set[str]:
    """Read label names from the repository label catalog."""
    labels: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        match = _LABEL_LINE.match(line)
        if match:
            labels.add(match.group(1))
    return labels


def collect_configured_labels(config: dict[str, Any]) -> set[str]:
    """Collect every label referenced by Renovate configuration."""
    labels: set[str] = set()
    for key in ("labels", "dependencyDashboardLabels"):
        value = config.get(key, [])
        if isinstance(value, list):
            labels.update(item for item in value if isinstance(item, str))

    package_rules = config.get("packageRules", [])
    if isinstance(package_rules, list):
        for rule in package_rules:
            if not isinstance(rule, dict):
                continue
            for key in ("labels", "addLabels"):
                value = rule.get(key, [])
                if isinstance(value, list):
                    labels.update(item for item in value if isinstance(item, str))
    return labels


def _matches_package(pattern: str, package: str) -> bool:
    if pattern.startswith("/") and pattern.endswith("/"):
        return re.search(pattern[1:-1], package) is not None
    return fnmatch.fnmatchcase(package, pattern)


def package_is_non_automerge(config: dict[str, Any], package: str) -> bool:
    """Return whether a local package rule explicitly disables automerge."""
    package_rules = config.get("packageRules", [])
    if not isinstance(package_rules, list):
        return False
    for rule in package_rules:
        if not isinstance(rule, dict) or rule.get("automerge") is not False:
            continue
        patterns = rule.get("matchPackageNames", [])
        if not isinstance(patterns, list):
            continue
        if any(
            isinstance(pattern, str) and _matches_package(pattern, package) for pattern in patterns
        ):
            return True
    return False


def validate_config(repo_root: Path) -> list[str]:
    """Return deterministic policy errors for the Fovux Renovate config."""
    errors: list[str] = []
    config_path = repo_root / "renovate.json"
    labels_path = repo_root / ".github" / "labels.yml"

    try:
        config = load_config(config_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return [f"Cannot load renovate.json: {exc}"]

    extends = config.get("extends", [])
    if not isinstance(extends, list) or EXPECTED_PRESET not in extends:
        errors.append(f"Missing explicit shared preset: {EXPECTED_PRESET}")

    managers_value = config.get("enabledManagers", [])
    managers = (
        {manager for manager in managers_value if isinstance(manager, str)}
        if isinstance(managers_value, list)
        else set()
    )
    missing_managers = sorted(EXPECTED_MANAGERS - managers)
    unexpected_managers = sorted(managers - EXPECTED_MANAGERS)
    if missing_managers:
        errors.append(f"Missing enabled managers: {missing_managers}")
    if unexpected_managers:
        errors.append(f"Unexpected enabled managers: {unexpected_managers}")

    if config.get("timezone") != "Europe/Istanbul":
        errors.append("Renovate timezone must be Europe/Istanbul")
    if config.get("prHourlyLimit") != 2:
        errors.append("prHourlyLimit must be 2")
    if config.get("prConcurrentLimit") != 6:
        errors.append("prConcurrentLimit must be 6")
    if config.get("dependencyDashboard") is not True:
        errors.append("Dependency Dashboard must be enabled")

    missing_manifests = [
        relative_path
        for relative_path in REQUIRED_MANIFESTS
        if not (repo_root / relative_path).exists()
    ]
    if missing_manifests:
        errors.append(f"Missing managed files: {missing_manifests}")

    try:
        known_labels = load_label_names(labels_path)
    except OSError as exc:
        errors.append(f"Cannot load label catalog: {exc}")
        known_labels = set()
    unknown_labels = sorted(collect_configured_labels(config) - known_labels)
    if unknown_labels:
        errors.append(f"Unknown Renovate labels: {unknown_labels}")

    for package in PROTECTED_PACKAGES:
        if not package_is_non_automerge(config, package):
            errors.append(f"Protected dependency lacks automerge:false rule: {package}")

    return errors


def main() -> int:
    """Validate the checked-out repository policy."""
    errors = validate_config(REPO_ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(
        "Renovate policy is valid: "
        f"{len(EXPECTED_MANAGERS)} managers, {len(REQUIRED_MANIFESTS)} managed files, "
        f"{len(PROTECTED_PACKAGES)} protected dependency checks."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
