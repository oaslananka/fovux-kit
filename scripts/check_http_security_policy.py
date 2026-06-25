"""Fail-fast checks for Studio local API security policy invariants."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MCP_ROOT = ROOT / "fovux-mcp"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _expect(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def main() -> int:
    """Verify HTTP security hardening remains explicit in code, tests, and docs."""
    failures: list[str] = []
    app = _read(MCP_ROOT / "src" / "fovux" / "http" / "app.py")
    cli = _read(MCP_ROOT / "src" / "fovux" / "cli.py")
    tests = _read(MCP_ROOT / "tests" / "security" / "test_http_security.py")
    security = _read(MCP_ROOT / "docs" / "security.md")
    threat_model = _read(ROOT / "docs" / "threat-model.md")
    adr = _read(MCP_ROOT / "docs" / "adr" / "0006-http-auth-model.md")

    for phrase in [
        "_is_allowed_origin",
        "_reject_invalid_origin",
        "Origin is not allowed",
        "nonlocal_bind_allowed",
        "Missing or invalid bearer token",
    ]:
        _expect(
            phrase in app, f"HTTP app missing security invariant: {phrase}", failures
        )

    for phrase in [
        "Refusing to bind the Fovux Studio local API",
        "--allow-nonlocal-bind",
        "is_local_bind_host",
    ]:
        _expect(phrase in cli, f"CLI missing bind-safety invariant: {phrase}", failures)

    for phrase in [
        "test_invalid_origin_rejected_before_authenticated_tool_call",
        "test_all_non_health_routes_require_authentication",
        "test_cli_refuses_nonlocal_bind_without_explicit_opt_in",
        "test_cli_allows_nonlocal_bind_only_with_prominent_warning",
        "oauth",
    ]:
        _expect(
            phrase in tests,
            f"HTTP security test coverage marker missing: {phrase}",
            failures,
        )

    for phrase in [
        "GET /health` is the only unauthenticated endpoint",
        "Origin",
        "--allow-nonlocal-bind",
        "OAuth/OIDC resource-server design",
        "audience",
        "binding",
    ]:
        _expect(
            phrase in security,
            f"Security docs missing policy phrase: {phrase}",
            failures,
        )

    for phrase in [
        "Fovux Studio Local API",
        "DNS rebinding",
        "untrusted browser `Origin`",
        "future OAuth/OIDC resource-server design",
    ]:
        _expect(
            phrase in threat_model,
            f"Threat model missing policy phrase: {phrase}",
            failures,
        )

    _expect(
        "Remote or multi-user deployments require a separate OAuth/OIDC" in adr,
        "ADR 0006 must document that local bearer auth is not remote/server auth.",
        failures,
    )

    if failures:
        for failure in failures:
            print(f"ERROR: {failure}")
        return 1

    print(
        "HTTP security policy checks passed: auth, Origin, bind, session, and remote-mode boundaries are enforced."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
