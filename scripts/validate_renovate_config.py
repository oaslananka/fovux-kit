"""Validate the repository-specific Renovate policy without network access."""

from __future__ import annotations

import fnmatch
import json
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


def load_config(path: Path) -> dict[str, Any]:
    """Load one Renovate JSON file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return data


def _label_name_from_line(line: str) -> str | None:
    """Extract one simple `- name:` value from the label catalog."""
    stripped = line.strip()
    prefix = "- name:"
    if not stripped.startswith(prefix):
        return None
    value = stripped[len(prefix) :].strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1]
    return value or None


def load_label_names(path: Path) -> set[str]:
    """Read label names from the repository label catalog."""
    return {
        label
        for line in path.read_text(encoding="utf-8").splitlines()
        if (label := _label_name_from_line(line)) is not None
    }


def _string_values(value: object) -> set[str]:
    """Return string members from a JSON-style list."""
    if not isinstance(value, list):
        return set()
    return {item for item in value if isinstance(item, str)}


def _mapping_values(value: object) -> list[dict[str, Any]]:
    """Return mapping members from a JSON-style list."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def collect_configured_labels(config: dict[str, Any]) -> set[str]:
    """Collect every label referenced by Renovate configuration."""
    labels = _string_values(config.get("labels"))
    labels.update(_string_values(config.get("dependencyDashboardLabels")))
    for rule in _mapping_values(config.get("packageRules")):
        labels.update(_string_values(rule.get("labels")))
        labels.update(_string_values(rule.get("addLabels")))
    return labels


def _matches_package(pattern: str, package: str) -> bool:
    """Match exact/glob package names; regex-only rules are irrelevant here."""
    if pattern.startswith("/") and pattern.endswith("/"):
        return False
    return fnmatch.fnmatchcase(package, pattern)


def package_is_non_automerge(config: dict[str, Any], package: str) -> bool:
    """Return whether a local package rule explicitly disables automerge."""
    for rule in _mapping_values(config.get("packageRules")):
        if rule.get("automerge") is not False:
            continue
        patterns = _string_values(rule.get("matchPackageNames"))
        if any(_matches_package(pattern, package) for pattern in patterns):
            return True
    return False


def _validate_core_policy(config: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if EXPECTED_PRESET not in _string_values(config.get("extends")):
        errors.append(f"Missing explicit shared preset: {EXPECTED_PRESET}")

    managers = _string_values(config.get("enabledManagers"))
    missing_managers = sorted(EXPECTED_MANAGERS - managers)
    unexpected_managers = sorted(managers - EXPECTED_MANAGERS)
    if missing_managers:
        errors.append(f"Missing enabled managers: {missing_managers}")
    if unexpected_managers:
        errors.append(f"Unexpected enabled managers: {unexpected_managers}")

    expected_values: tuple[tuple[str, object, str], ...] = (
        ("timezone", "Europe/Istanbul", "Renovate timezone must be Europe/Istanbul"),
        ("prHourlyLimit", 2, "prHourlyLimit must be 2"),
        ("prConcurrentLimit", 6, "prConcurrentLimit must be 6"),
        ("dependencyDashboard", True, "Dependency Dashboard must be enabled"),
    )
    for key, expected, message in expected_values:
        if config.get(key) != expected:
            errors.append(message)

    pre_commit_config = config.get("pre-commit")
    if not isinstance(pre_commit_config, dict) or pre_commit_config.get("enabled") is not True:
        errors.append("pre-commit manager must be explicitly enabled")
    return errors


def _validate_manifests(repo_root: Path) -> list[str]:
    missing = [path for path in REQUIRED_MANIFESTS if not (repo_root / path).exists()]
    return [f"Missing managed files: {missing}"] if missing else []


def _validate_labels(config: dict[str, Any], labels_path: Path) -> list[str]:
    try:
        known_labels = load_label_names(labels_path)
    except OSError as exc:
        return [f"Cannot load label catalog: {exc}"]
    unknown = sorted(collect_configured_labels(config) - known_labels)
    return [f"Unknown Renovate labels: {unknown}"] if unknown else []


def _validate_protected_packages(config: dict[str, Any]) -> list[str]:
    return [
        f"Protected dependency lacks automerge:false rule: {package}"
        for package in PROTECTED_PACKAGES
        if not package_is_non_automerge(config, package)
    ]


def validate_config(repo_root: Path) -> list[str]:
    """Return deterministic policy errors for the Fovux Renovate config."""
    try:
        config = load_config(repo_root / "renovate.json")
    except (OSError, ValueError) as exc:
        return [f"Cannot load renovate.json: {exc}"]

    return [
        *_validate_core_policy(config),
        *_validate_manifests(repo_root),
        *_validate_labels(config, repo_root / ".github" / "labels.yml"),
        *_validate_protected_packages(config),
    ]


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
