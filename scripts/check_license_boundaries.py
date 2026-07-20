"""Validate canonical licensing artifacts and third-party boundary documentation."""

from __future__ import annotations

import hashlib
import json
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
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


def _license_artifact_failures(root: Path) -> list[str]:
    failures: list[str] = []

    for relative in LICENSE_PATHS:
        path = root / relative
        if not path.exists():
            failures.append(f"Missing canonical license file: {relative}")
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != CANONICAL_APACHE_SHA256:
            failures.append(f"License file is not canonical Apache-2.0 text: {relative} ({digest})")

    for relative in NOTICE_PATHS:
        path = root / relative
        if not path.exists():
            failures.append(f"Missing NOTICE file: {relative}")
            continue
        text = _read(path)
        if "Fovux" not in text or "Copyright 2026 Fovux Contributors" not in text:
            failures.append(f"NOTICE attribution is incomplete: {relative}")

    pyproject_path = root / "fovux-mcp" / "pyproject.toml"
    try:
        pyproject = tomllib.loads(_read(pyproject_path))
        project = pyproject.get("project", {})
        if not isinstance(project, dict):
            raise ValueError("[project] must be a table")
        if project.get("license") != "Apache-2.0":
            failures.append("fovux-mcp project.license must be Apache-2.0")
        license_files = project.get("license-files", [])
        if not isinstance(license_files, list) or not {"LICENSE", "NOTICE"} <= {
            item for item in license_files if isinstance(item, str)
        }:
            failures.append("fovux-mcp project.license-files must include LICENSE and NOTICE")
    except (OSError, tomllib.TOMLDecodeError, ValueError) as exc:
        failures.append(f"Cannot validate fovux-mcp/pyproject.toml license metadata: {exc}")

    for relative in (Path("fovux-mcp-npm/package.json"), Path("fovux-studio/package.json")):
        try:
            manifest = _load_json(root / relative)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            failures.append(f"Cannot validate {relative} license metadata: {exc}")
            continue
        if manifest.get("license") != "Apache-2.0":
            failures.append(f"{relative} license must be Apache-2.0")
        if relative.parts[0] == "fovux-mcp-npm":
            package_files = manifest.get("files", [])
            if not isinstance(package_files, list) or not {"LICENSE", "NOTICE"} <= {
                item for item in package_files if isinstance(item, str)
            }:
                failures.append("fovux-mcp-npm package files must include LICENSE and NOTICE")

    vscodeignore_path = root / "fovux-studio" / ".vscodeignore"
    try:
        ignored_entries = {
            line.strip()
            for line in _read(vscodeignore_path).splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
        for artifact in ("LICENSE", "NOTICE"):
            if artifact in ignored_entries:
                failures.append(f"fovux-studio/.vscodeignore must not exclude {artifact}")
    except OSError as exc:
        failures.append(f"Cannot validate fovux-studio/.vscodeignore: {exc}")

    return failures


def _boundary_documentation_failures(root: Path) -> list[str]:
    failures: list[str] = []
    docs = _read(root / "docs" / "licensing-boundaries.md")
    for phrase in [
        "Apache-2.0",
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
    ]:
        if phrase not in docs:
            failures.append(f"Licensing docs missing {phrase}")
    report_code = _read(root / "fovux-mcp" / "src" / "fovux" / "core" / "doctor.py")
    for phrase in ["Ultralytics", "AGPL", "NOTICE"]:
        if phrase not in report_code:
            failures.append(f"Doctor license notice missing {phrase}")
    bundle = _read(root / "fovux-mcp" / "src" / "fovux" / "tools" / "bundles.py")
    for phrase in ["package_versions", "Ultralytics"]:
        if phrase not in bundle:
            failures.append(f"Support bundle inventory missing {phrase}")
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
