"""Fail-fast checks for public documentation/version/tool-count drift."""

from __future__ import annotations

import json
import os
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MCP_ROOT = ROOT / "fovux-mcp"
STUDIO_ROOT = ROOT / "fovux-studio"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _mcp_version() -> str:
    data = tomllib.loads(_read(MCP_ROOT / "pyproject.toml"))
    return str(data["project"]["version"])


def _json_version(path: Path) -> str:
    return str(json.loads(_read(path))["version"])


def _tool_names() -> set[str]:
    content = _read(MCP_ROOT / "src" / "fovux" / "core" / "tool_registry.py")
    return set(re.findall(r'^\s+"([a-z0-9_]+)":', content, flags=re.MULTILINE))


def _granular_lm_tool_count() -> int:
    content = _read(STUDIO_ROOT / "src" / "fovux" / "tools" / "definitions.ts")
    return len(re.findall(r'name:\s*"fovux_[^"]+"', content))


def _readme_tool_names() -> set[str]:
    content = _read(MCP_ROOT / "README.md")
    match = re.search(
        r"<!-- fovux-tools:start -->\n\n(?P<table>.*?)\n\n<!-- fovux-tools:end -->",
        content,
        flags=re.S,
    )
    if not match:
        raise AssertionError("fovux-mcp README is missing generated tool table markers")
    return set(re.findall(r"\| `([a-z0-9_]+)`", match.group("table")))


def _is_release_please_branch() -> bool:
    branch_names = {
        os.environ.get("GITHUB_HEAD_REF", ""),
        os.environ.get("GITHUB_REF_NAME", ""),
        os.environ.get("GITHUB_REF", "").removeprefix("refs/heads/"),
    }
    return "release-please--branches--main" in branch_names


def _expect(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def _with_regen(message: str, command: str) -> str:
    """Attach the exact regeneration command to a failure message."""
    return f"{message}. Regenerate/check with: `{command}`"


def main() -> int:
    """Run public documentation truth checks."""
    failures: list[str] = []
    mcp_version = _mcp_version()
    npm_wrapper_version = _json_version(ROOT / "fovux-mcp-npm" / "package.json")
    studio_version = _json_version(STUDIO_ROOT / "package.json")
    tools = _tool_names()
    lm_tool_count = _granular_lm_tool_count()

    root_readme = _read(ROOT / "README.md")
    mcp_readme = _read(MCP_ROOT / "README.md")
    architecture = _read(ROOT / "docs" / "architecture.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    release_notes = _read(ROOT / "RELEASE_NOTES.md")
    root_changelog = _read(ROOT / "CHANGELOG.md")
    release_please_branch = _is_release_please_branch()
    package_changelogs = {
        "fovux-mcp": _read(MCP_ROOT / "CHANGELOG.md"),
        "fovux-mcp-npm": _read(ROOT / "fovux-mcp-npm" / "CHANGELOG.md"),
        "fovux-studio": _read(STUDIO_ROOT / "CHANGELOG.md"),
    }
    release_docs = _read(ROOT / "docs" / "release.md") + _read(
        ROOT / "docs" / "release-process.md"
    )

    if not release_please_branch:
        _expect(
            f"Python backend package `fovux-mcp` {mcp_version}" in root_readme,
            _with_regen(
                "README.md does not state the current fovux-mcp Python package version",
                "python scripts/check_versions.py && python scripts/check_docs_truth.py",
            ),
            failures,
        )
        _expect(
            f"npm wrapper `fovux-mcp` {npm_wrapper_version}" in root_readme,
            _with_regen(
                "README.md does not state the current fovux-mcp npm wrapper version",
                "python scripts/check_versions.py && python scripts/check_docs_truth.py",
            ),
            failures,
        )
        _expect(
            f"VS Code companion `Fovux Studio` {studio_version}" in root_readme,
            _with_regen(
                "README.md does not state the current Fovux Studio version",
                "python scripts/check_versions.py && python scripts/check_docs_truth.py",
            ),
            failures,
        )
        _expect(
            f"Fovux MCP {mcp_version} exposes {len(tools)} local tools" in root_readme,
            _with_regen(
                "README.md tool count is stale",
                "python scripts/check_docs_truth.py",
            ),
            failures,
        )
        _expect(
            f"Fovux MCP {mcp_version} currently exposes {len(tools)} local tools"
            in mcp_readme,
            _with_regen(
                "fovux-mcp/README.md tool count is stale",
                "python scripts/check_docs_truth.py",
            ),
            failures,
        )

    readme_tools = _readme_tool_names()
    missing_readme_tools = sorted(tools - readme_tools)
    extra_readme_tools = sorted(readme_tools - tools)
    _expect(
        readme_tools == tools,
        _with_regen(
            "fovux-mcp/README.md tool table drift: "
            f"missing={missing_readme_tools} extra={extra_readme_tools}",
            "python scripts/check_docs_truth.py",
        ),
        failures,
    )
    _expect(
        "standardized HTTP/stdio" not in root_readme + architecture,
        _with_regen(
            "README.md or docs/architecture.md still describe the Studio HTTP API "
            "as a standardized HTTP/stdio MCP layer",
            "python scripts/check_docs_truth.py",
        ),
        failures,
    )
    _expect(
        "Studio local HTTP/SSE API" in architecture,
        _with_regen(
            "docs/architecture.md does not explicitly name the Studio local HTTP/SSE API",
            "python scripts/check_docs_truth.py",
        ),
        failures,
    )
    _expect(
        "not documented as a standards-compliant MCP Streamable HTTP endpoint"
        in architecture,
        _with_regen(
            "docs/architecture.md does not distinguish the current HTTP/SSE API "
            "from MCP Streamable HTTP",
            "python scripts/check_docs_truth.py",
        ),
        failures,
    )
    lm_tool_phrase = f"{lm_tool_count} granular tools plus 1 generic fallback"
    _expect(
        lm_tool_phrase in architecture + roadmap + release_notes,
        _with_regen(
            "LM tool count is stale in docs/architecture.md, ROADMAP.md, or RELEASE_NOTES.md",
            "python scripts/check_docs_truth.py",
        ),
        failures,
    )
    _expect(
        "1.2.0 — Q3 2026" not in roadmap and "1.3.0 — Q4 2026" not in roadmap,
        _with_regen(
            "ROADMAP.md still describes already-published versions as future milestones",
            "python scripts/check_docs_truth.py",
        ),
        failures,
    )
    if not release_please_branch:
        _expect(
            f"Fovux {mcp_version} is the current reviewed release baseline"
            in release_notes,
            _with_regen(
                "RELEASE_NOTES.md does not describe the current reviewed release baseline",
                "python scripts/check_docs_truth.py",
            ),
            failures,
        )

    for milestone_number, milestone_title in [
        (1, "v1.3.1 — Stabilization & Documentation Truth"),
        (2, "v1.4.0 — MCP Conformance & Agent Safety"),
        (3, "v1.5.0 — Studio Workflow & Dataset Intelligence"),
        (4, "v1.6.0 — Edge Export & Deployment Intelligence"),
        (5, "v2.0.0 — Extensibility, Supply Chain & Ecosystem Readiness"),
        (6, "Backlog — Research & Product Discovery"),
    ]:
        _expect(
            f"[{milestone_title}](https://github.com/oaslananka/fovux-kit/milestone/{milestone_number})"
            in roadmap,
            _with_regen(
                f"ROADMAP.md is missing the GitHub milestone link for {milestone_title}",
                "python scripts/check_docs_truth.py",
            ),
            failures,
        )

    for phrase in [
        "Released work is recorded in",
        "Planned work is tracked in the milestone sections below",
        "GitHub Releases must include package versions",
    ]:
        _expect(
            phrase in roadmap,
            _with_regen(
                f"ROADMAP.md is missing release/planning boundary phrase: {phrase}",
                "python scripts/check_docs_truth.py",
            ),
            failures,
        )

    _expect(
        "This changelog records released work only" in root_changelog,
        _with_regen(
            "CHANGELOG.md does not separate released work from planned work",
            "python scripts/check_docs_truth.py",
        ),
        failures,
    )
    for package_name, content in package_changelogs.items():
        _expect(
            "This package changelog records released" in content
            and "Planned work and target dates are tracked" in content,
            _with_regen(
                f"{package_name} changelog does not separate released work from planned work",
                "python scripts/check_docs_truth.py",
            ),
            failures,
        )

    for phrase in [
        "Package Versions and Release Evidence",
        "VSIX packaging",
        "VS Marketplace",
        "Open VSX",
        "SBOM",
        "provenance",
        "registry verification evidence",
        "smoke-test result",
    ]:
        _expect(
            phrase in release_notes,
            _with_regen(
                f"RELEASE_NOTES.md is missing release evidence phrase: {phrase}",
                "python scripts/check_docs_truth.py",
            ),
            failures,
        )

    _expect(
        "Release Evidence Checklist" in release_docs
        and "registry verification evidence JSON" in release_docs
        and "VSIX packaging status" in release_docs,
        _with_regen(
            "Release process docs do not define the required GitHub Release evidence",
            "python scripts/check_docs_truth.py",
        ),
        failures,
    )

    stale_url_files = []
    for candidate in [
        ROOT / "SUPPORT.md",
        ROOT / "scripts" / "build_node_spdx_sbom.mjs",
        ROOT / "scripts" / "build_spdx_sbom.py",
    ]:
        if "github.com/oaslananka/fovux/" in _read(candidate):
            stale_url_files.append(str(candidate.relative_to(ROOT)))
    _expect(
        not stale_url_files,
        _with_regen(
            f"Stale oaslananka/fovux repository URLs remain in {stale_url_files}",
            "python scripts/check_docs_truth.py",
        ),
        failures,
    )

    if failures:
        for failure in failures:
            print(f"ERROR: {failure}")
        return 1

    print(
        "Docs truth checks passed: "
        f"fovux-mcp={mcp_version}, npm-wrapper={npm_wrapper_version}, "
        f"studio={studio_version}, tools={len(tools)}, lm-tools={lm_tool_count}+1."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
