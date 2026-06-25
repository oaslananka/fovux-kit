"""Validate MCP-specific threat model and security review coverage."""

from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> int:
    failures: list[str] = []
    threat = _read(ROOT / "docs" / "threat-model.md").lower()
    for phrase in [
        "tool poisoning",
        "prompt injection",
        "sensitive data leakage",
        "confused-deputy",
        "untrusted",
        "security review checklist",
    ]:
        if phrase not in threat:
            failures.append(f"Threat model missing {phrase}")
    for path in [
        "scripts/check_agent_policy.py",
        "scripts/check_http_security_policy.py",
        "scripts/check_audit_schema.py",
        "scripts/check_studio_lm_tools.py",
    ]:
        if not (ROOT / path).exists():
            failures.append(f"Missing MCP security gate: {path}")
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}")
        return 1
    print("MCP threat model checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
