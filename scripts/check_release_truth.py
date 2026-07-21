"""Validate semantic published-release and GitHub milestone truth."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
BASELINE_START = "<!-- release-baseline:start -->"
BASELINE_END = "<!-- release-baseline:end -->"


def _load_manifest(root: Path) -> dict[str, Any]:
    value = json.loads((root / "release-baseline.json").read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("release-baseline.json must contain a JSON object")
    return value


def _packages(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    value = manifest.get("packages")
    if not isinstance(value, list) or not value:
        raise ValueError("release-baseline.json packages must be a non-empty array")
    packages: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(
                f"release-baseline.json packages[{index}] must be an object"
            )
        packages.append(item)
    return packages


def render_release_table(manifest: dict[str, Any]) -> str:
    """Render the canonical package/version/channel/evidence table."""
    lines = [
        BASELINE_START,
        "| Component | Published version | Channel status | Evidence |",
        "| --- | --- | --- | --- |",
    ]
    for package in _packages(manifest):
        component = str(package.get("component", "")).strip()
        version = str(package.get("version", "")).strip()
        status = str(package.get("status", "")).strip()
        evidence_value = package.get("evidence", [])
        if not component or not version or not status:
            raise ValueError("every package requires component, version, and status")
        if not isinstance(evidence_value, list) or not evidence_value:
            raise ValueError(f"package {component} requires evidence entries")
        evidence = ", ".join(
            f"`{item}`" for item in evidence_value if isinstance(item, str)
        )
        if not evidence:
            raise ValueError(f"package {component} requires string evidence entries")
        lines.append(f"| {component} | `{version}` | {status} | {evidence} |")
    lines.append(BASELINE_END)
    return "\n".join(lines)


def _marked_block(text: str) -> str | None:
    start = text.find(BASELINE_START)
    end = text.find(BASELINE_END)
    if start < 0 or end < start:
        return None
    return text[start : end + len(BASELINE_END)]


def _validate_milestones(root: Path, manifest: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    roadmap = (root / "ROADMAP.md").read_text(encoding="utf-8")
    milestones = manifest.get("milestones", [])
    if not isinstance(milestones, list):
        return ["release-baseline.json milestones must be an array"]
    for item in milestones:
        if not isinstance(item, dict):
            failures.append("release-baseline.json milestone entries must be objects")
            continue
        number = item.get("number")
        title = str(item.get("title", ""))
        state = str(item.get("state", ""))
        if not isinstance(number, int) or not title or state not in {"open", "closed"}:
            failures.append(f"Invalid milestone entry: {item}")
            continue
        link = f"[{title}](https://github.com/oaslananka/fovux-kit/milestone/{number})"
        heading = f"## {link}"
        start = roadmap.find(heading)
        if start < 0:
            failures.append(f"ROADMAP.md is missing milestone link: {title}")
            continue
        next_heading = roadmap.find("\n## ", start + len(heading))
        section = roadmap[start : next_heading if next_heading >= 0 else len(roadmap)]
        state_phrase = f"**State:** {state.capitalize()}"
        if state_phrase not in section:
            failures.append(
                f"ROADMAP.md is missing milestone state for {title}: {state_phrase}"
            )
    return failures


def validate_release_truth(root: Path) -> list[str]:
    """Return semantic release-truth deviations for one repository root."""
    failures: list[str] = []
    try:
        manifest = _load_manifest(root)
        if manifest.get("schema_version") != 1:
            failures.append("release-baseline.json schema_version must be 1")
        published_release = str(manifest.get("published_release", "")).strip()
        if not published_release:
            failures.append("release-baseline.json published_release is required")
        expected_table = render_release_table(manifest)
    except (OSError, ValueError) as exc:
        return [f"Cannot load release baseline: {exc}"]

    documents = [
        root / "ROADMAP.md",
        root / "RELEASE_NOTES.md",
        root / "docs" / "release-notes" / f"{published_release}.md",
    ]
    for path in documents:
        try:
            block = _marked_block(path.read_text(encoding="utf-8"))
        except OSError as exc:
            failures.append(f"Cannot read {path.relative_to(root)}: {exc}")
            continue
        if block != expected_table:
            relative = path.relative_to(root)
            failures.append(
                f"{relative} generated baseline table differs from release-baseline.json"
            )

    release_note_path = root / "docs" / "release-notes" / f"{published_release}.md"
    try:
        release_note = release_note_path.read_text(encoding="utf-8")
        baseline_phrase = (
            f"Fovux {published_release} is the current reviewed release baseline"
        )
        if baseline_phrase not in release_note:
            failures.append(
                f"{release_note_path.relative_to(root)} does not identify the published baseline"
            )
        studio = next(
            package for package in _packages(manifest) if package.get("id") == "studio"
        )
        studio_status = str(studio.get("status", ""))
        if "Open VSX" not in studio_status:
            failures.append("Studio baseline must state the verified Open VSX status")
    except (OSError, StopIteration, ValueError) as exc:
        failures.append(f"Cannot validate published release note semantics: {exc}")

    failures.extend(_validate_milestones(root, manifest))
    return failures


def main() -> int:
    """Validate the checked-out repository's published release truth."""
    failures = validate_release_truth(ROOT)
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}")
        return 1
    manifest = _load_manifest(ROOT)
    print(
        "Release truth checks passed: "
        f"published={manifest['published_release']}, reviewed={manifest['reviewed_at']}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
