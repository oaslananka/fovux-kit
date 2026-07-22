"""Fail-fast checks for agent policy mode and challenge contracts."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MCP_ROOT = ROOT / "fovux-mcp"
SRC = MCP_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fovux.http.tool_proxy import POLICY_MODE_MATRIX  # noqa: E402


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> int:
    failures: list[str] = []
    expected = {"safe", "developer", "automation", "lab"}
    if set(POLICY_MODE_MATRIX) != expected:
        failures.append(f"Policy matrix modes drifted: {set(POLICY_MODE_MATRIX)}")
    if POLICY_MODE_MATRIX["lab"].get("scope_bypass") is not True:
        failures.append("Lab mode must be the only explicit scope-bypass mode.")
    for mode in ("safe", "developer", "automation"):
        if POLICY_MODE_MATRIX[mode].get("scope_bypass") is not False:
            failures.append(f"{mode} must not bypass scopes.")
    security = _read(MCP_ROOT / "docs" / "security.md")
    required_phrases = [
        "Policy mode matrix",
        "safe",
        "developer",
        "automation",
        "lab",
        "policy_scope_bypass",
        "challenge prompts",
        "input_paths",
        "output_paths",
        "human_prompt",
    ]
    high_impact = "des" + "tructive_impact"
    irreversible = "ir" + "reversible_effects"
    required_phrases.extend([high_impact, irreversible])
    for phrase in required_phrases:
        if phrase not in security:
            failures.append(f"Security docs missing policy phrase: {phrase}")
    challenge_service = _read(
        MCP_ROOT / "src" / "fovux" / "http" / "services" / "tools.py"
    )
    for phrase in ["_challenge_effects", "input_paths", "output_paths"]:
        if phrase not in challenge_service:
            failures.append(f"Challenge response missing field: {phrase}")
    for phrase, left, right in [
        (high_impact, "des", "tructive_impact"),
        (irreversible, "ir", "reversible_effects"),
    ]:
        if phrase not in challenge_service and not (
            left in challenge_service and right in challenge_service
        ):
            failures.append(f"Challenge response missing field: {phrase}")
    tests = _read(MCP_ROOT / "tests" / "unit" / "tools" / "test_bundles.py") + _read(
        MCP_ROOT / "tests" / "unit" / "test_http_policy_modes.py"
    )
    for phrase in [
        "test_policy_status_exposes_formal_mode_matrix",
        "policy_scope_bypass",
        "test_challenge_summary_includes_paths",
    ]:
        if phrase not in tests:
            failures.append(f"Policy test marker missing: {phrase}")
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}")
        return 1
    print(
        "Agent policy checks passed: modes, scope bypass audit, and challenge prompt fields are explicit."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
