"""Validate canonical licensing artifacts and third-party boundary documentation."""

from __future__ import annotations

import hashlib
import json
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SPDX_LICENSE = "Apache-2.0"
CANONICAL_APACHE_SHA256 = "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30"
LICENSE_PATHS = (
    Path("LICENSE"),
    Path("fovux-mcp/LICENSE"),
    Path("fovux-mcp-npm/LICENSE"),
    Path("fovux-studio/LICENSE"),
)
NOTICE_PATHS = (
    Path("NOTICE"),
    Path("fovux-mcp/NOTICE"),
    Path("fovux-mcp-npm/NOTICE"),
    Path("fovux-studio/NOTICE"),
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(_read(path))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return value


def _canonical_license_failures(root: Path) -> list[str]:
    failures: list[str] = []
    for relative in LICENSE_PATHS:
        path = root / relative
        if not path.exists():
            failures.append(f"Missing canonical license file: {relative}")
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != CANONICAL_APACHE_SHA256:
            failures.append(
                f"License file is not canonical {SPDX_LICENSE} text: {relative} ({digest})"
            )
    return failures


def _notice_failures(root: Path) -> list[str]:
    failures: list[str] = []
    for relative in NOTICE_PATHS:
        path = root / relative
        if not path.exists():
            failures.append(f"Missing NOTICE file: {relative}")
            continue
        text = _read(path)
        if "Fovux" not in text or "Copyright 2026 Fovux Contributors" not in text:
            failures.append(f"NOTICE attribution is incomplete: {relative}")
    return failures


def _python_manifest_failures(root: Path) -> list[str]:
    path = root / "fovux-mcp" / "pyproject.toml"
    try:
        pyproject = tomllib.loads(_read(path))
        project = pyproject.get("project", {})
        if not isinstance(project, dict):
            raise ValueError("[project] must be a table")
    except (OSError, ValueError) as exc:
        return [f"Cannot validate fovux-mcp/pyproject.toml license metadata: {exc}"]

    failures: list[str] = []
    if project.get("license") != SPDX_LICENSE:
        failures.append(f"fovux-mcp project.license must be {SPDX_LICENSE}")
    license_files = project.get("license-files", [])
    declared_files = (
        {item for item in license_files if isinstance(item, str)}
        if isinstance(license_files, list)
        else set()
    )
    if not {"LICENSE", "NOTICE"} <= declared_files:
        failures.append("fovux-mcp project.license-files must include LICENSE and NOTICE")
    return failures


def _node_manifest_failures(root: Path) -> list[str]:
    failures: list[str] = []
    manifests = (
        Path("fovux-mcp-npm/package.json"),
        Path("fovux-studio/package.json"),
    )
    for relative in manifests:
        try:
            manifest = _load_json(root / relative)
        except (OSError, ValueError) as exc:
            failures.append(f"Cannot validate {relative} license metadata: {exc}")
            continue
        if manifest.get("license") != SPDX_LICENSE:
            failures.append(f"{relative} license must be {SPDX_LICENSE}")
        if relative.parts[0] == "fovux-mcp-npm":
            package_files = manifest.get("files", [])
            declared_files = (
                {item for item in package_files if isinstance(item, str)}
                if isinstance(package_files, list)
                else set()
            )
            if not {"LICENSE", "NOTICE"} <= declared_files:
                failures.append("fovux-mcp-npm package files must include LICENSE and NOTICE")
    return failures


def _vscodeignore_failures(root: Path) -> list[str]:
    path = root / "fovux-studio" / ".vscodeignore"
    try:
        ignored_entries = {
            line.strip()
            for line in _read(path).splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
    except OSError as exc:
        return [f"Cannot validate fovux-studio/.vscodeignore: {exc}"]
    return [
        f"fovux-studio/.vscodeignore must not exclude {artifact}"
        for artifact in ("LICENSE", "NOTICE")
        if artifact in ignored_entries
    ]


def _license_artifact_failures(root: Path) -> list[str]:
    failures = _canonical_license_failures(root)
    failures.extend(_notice_failures(root))
    failures.extend(_python_manifest_failures(root))
    failures.extend(_node_manifest_failures(root))
    failures.extend(_vscodeignore_failures(root))
    return failures


def _missing_phrases(text: str, phrases: list[str], prefix: str) -> list[str]:
    return [f"{prefix} {phrase}" for phrase in phrases if phrase not in text]


def _boundary_documentation_failures(root: Path) -> list[str]:
    docs = _read(root / "docs" / "licensing-boundaries.md")
    failures = _missing_phrases(
        docs,
        [
            SPDX_LICENSE,
            "Ultralytics",
            "ONNX",
            "TensorRT",
            "CoreML",
            "OpenVINO",
            "TFLite",
            "NCNN",
            "RKNN",
            "W&B",
            "Hugging Face",
            "no-telemetry",
        ],
        "Licensing docs missing",
    )
    report_code = _read(root / "fovux-mcp" / "src" / "fovux" / "core" / "doctor.py")
    failures.extend(
        _missing_phrases(
            report_code, ["Ultralytics", "AGPL", "NOTICE"], "Doctor license notice missing"
        )
    )
    bundle = _read(root / "fovux-mcp" / "src" / "fovux" / "tools" / "bundles.py")
    failures.extend(
        _missing_phrases(
            bundle, ["package_versions", "Ultralytics"], "Support bundle inventory missing"
        )
    )
    return failures


def main() -> int:
    """Validate canonical distributed artifacts and documented license boundaries."""
    failures = _license_artifact_failures(ROOT)
    failures.extend(_boundary_documentation_failures(ROOT))
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}")
        return 1
    print("License artifact and boundary checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
