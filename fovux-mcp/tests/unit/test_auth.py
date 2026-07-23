"""Unit tests for local HTTP auth token helpers."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from fovux.core.auth import (
    ALL_SCOPES,
    Scope,
    auth_session_path,
    auth_token_path,
    check_token_perms,
    create_session_token,
    ensure_auth_token,
    is_known_session_token,
    list_session_fingerprints,
    resolve_session_scopes,
    revoke_session_token,
    rotate_auth_token,
    token_fingerprint,
)


def test_ensure_auth_token_creates_and_reuses_token(tmp_path: Path) -> None:
    """First-run token creation should be stable across repeated reads."""
    token, created = ensure_auth_token(tmp_path)
    reused, created_again = ensure_auth_token(tmp_path)

    assert created is True
    assert created_again is False
    assert token == reused
    assert auth_token_path(tmp_path).read_text(encoding="utf-8").strip() == token


def test_rotate_auth_token_replaces_existing_token(tmp_path: Path) -> None:
    """Token rotation should persist a new secret on disk."""
    original, _ = ensure_auth_token(tmp_path)
    rotated = rotate_auth_token(tmp_path)

    assert rotated != original
    assert auth_token_path(tmp_path).read_text(encoding="utf-8").strip() == rotated


def test_token_fingerprint_is_short_sha256_prefix() -> None:
    """Fingerprints should be deterministic short identifiers for logs."""
    first = token_fingerprint("abc123")
    second = token_fingerprint("abc123")

    assert first == second
    assert len(first) == 12
    assert re.fullmatch(r"[0-9a-f]{12}", first)


def test_is_known_session_token_false_when_no_session_file(tmp_path: Path) -> None:
    """When no auth.session file exists, any token should be unknown."""
    assert is_known_session_token("any-token", home=tmp_path) is False


def test_create_session_token_persists_and_is_known(tmp_path: Path) -> None:
    """A created session token should be recognized by is_known_session_token."""
    raw = create_session_token(scopes={Scope.READ, Scope.RUN_START}, home=tmp_path)
    assert is_known_session_token(raw, home=tmp_path) is True


def test_create_session_token_defaults_to_all_scopes(tmp_path: Path) -> None:
    """Creating a session token without explicit scopes grants all scopes."""
    raw = create_session_token(home=tmp_path)
    fp = token_fingerprint(raw)
    import json

    sessions = dict(json.loads(auth_session_path(tmp_path).read_text(encoding="utf-8")))
    meta = sessions[fp]
    assert set(meta["scopes"]) == {s.value for s in ALL_SCOPES}


def test_is_known_session_token_returns_false_for_unknown_token(tmp_path: Path) -> None:
    """Tokens not in the session store should return false."""
    create_session_token(home=tmp_path)
    assert is_known_session_token("unknown-token", home=tmp_path) is False


def test_is_known_session_token_handles_corrupt_session_file(tmp_path: Path) -> None:
    """A corrupt auth.session file should not crash the check."""
    auth_session_path(tmp_path).write_text("not-json", encoding="utf-8")
    assert is_known_session_token("any-token", home=tmp_path) is False


def test_resolve_session_scopes_returns_intersection(tmp_path: Path) -> None:
    """Resolved scopes should match what was requested during creation."""
    raw = create_session_token(scopes={Scope.READ, Scope.DATASET_WRITE}, home=tmp_path)
    resolved = resolve_session_scopes(raw, home=tmp_path)
    assert resolved == {Scope.READ, Scope.DATASET_WRITE}


def test_resolve_session_scopes_fallback_to_all_on_missing(tmp_path: Path) -> None:
    """When no session file or token is missing, fall back to all scopes."""
    assert resolve_session_scopes("unknown", home=tmp_path) == ALL_SCOPES


def test_revoke_session_token_removes_it(tmp_path: Path) -> None:
    """A revoked session token should no longer be known."""
    raw = create_session_token(home=tmp_path)
    assert revoke_session_token(raw, home=tmp_path) is True
    assert is_known_session_token(raw, home=tmp_path) is False


def test_revoke_session_token_returns_false_for_unknown(tmp_path: Path) -> None:
    """Revoking a token not in the store should return false."""
    assert revoke_session_token("unknown", home=tmp_path) is False


def test_list_session_fingerprints_empty_when_no_file(tmp_path: Path) -> None:
    """Listing fingerprints with no session file returns an empty list."""
    assert list_session_fingerprints(home=tmp_path) == []


def test_list_session_fingerprints_returns_created_sessions(tmp_path: Path) -> None:
    """Listing should return all stored session fingerprints and scopes."""
    _ = create_session_token(scopes={Scope.READ}, home=tmp_path)
    _ = create_session_token(scopes={Scope.RUN_START, Scope.ADMIN}, home=tmp_path)
    entries = list_session_fingerprints(home=tmp_path)
    assert len(entries) == 2
    for entry in entries:
        assert "fingerprint" in entry
        assert "scopes" in entry


def test_check_token_perms_fails_when_file_missing(tmp_path: Path) -> None:
    """Permission check should fail when no auth.token exists."""
    ok, detail = check_token_perms(home=tmp_path)
    assert ok is False
    assert "does not exist" in detail


def test_check_token_perms_passes_after_ensure(tmp_path: Path) -> None:
    """Permission check should pass after creating the token file (POSIX only)."""
    ensure_auth_token(home=tmp_path)
    ok, detail = check_token_perms(home=tmp_path)
    if sys.platform == "win32":
        assert ok is False
        assert "permissive" in detail
    else:
        assert ok is True
        assert "safe" in detail


def test_check_token_perms_rejects_permissive_mode(tmp_path: Path) -> None:
    """Group/world-readable token stores must fail the permission check."""
    ensure_auth_token(home=tmp_path)
    auth_token_path(tmp_path).chmod(0o644)

    ok, detail = check_token_perms(home=tmp_path)

    assert ok is False
    assert "permissive mode 0o644" in detail


def test_check_token_perms_reports_stat_failure(tmp_path: Path) -> None:
    """Unexpected stat failures should return a diagnostic rather than escape."""
    ensure_auth_token(home=tmp_path)
    token_path = auth_token_path(tmp_path)
    with (
        patch("fovux.core.auth._safe_auth_path", return_value=token_path),
        patch("fovux.core.auth.Path.exists", return_value=True),
        patch("fovux.core.auth.os.stat", side_effect=OSError("stat blocked")),
    ):
        ok, detail = check_token_perms(home=tmp_path)

    assert ok is False
    assert detail == "cannot stat auth.token: stat blocked"


def test_scope_from_category_returns_correct_scopes() -> None:
    """Scope.from_category should map known categories to their scope sets."""
    assert Scope.from_category("read_only") == {Scope.READ}
    assert Scope.from_category("destructive") == {Scope.DESTRUCTIVE, Scope.ADMIN}
    assert Scope.from_category("unknown") == {Scope.READ}


def test_create_session_token_rejects_symlinked_store_escape(tmp_path: Path) -> None:
    """Session creation must never follow auth.session outside the trusted home."""
    from fovux.core.errors import FovuxPathValidationError

    home = tmp_path / "home"
    home.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text('{"sentinel": true}', encoding="utf-8")
    (home / "auth.session").symlink_to(outside)

    with pytest.raises(FovuxPathValidationError, match="symlink|escapes"):
        create_session_token(home=home)

    assert outside.read_text(encoding="utf-8") == '{"sentinel": true}'


def test_revoke_session_token_rejects_symlinked_store_escape(tmp_path: Path) -> None:
    """Session revocation must not rewrite a symlink target outside FOVUX_HOME."""
    from fovux.core.errors import FovuxPathValidationError

    home = tmp_path / "home"
    home.mkdir()
    raw = create_session_token(home=home)
    session_path = auth_session_path(home)
    stored = session_path.read_text(encoding="utf-8")
    session_path.unlink()
    outside = tmp_path / "outside.json"
    outside.write_text(stored, encoding="utf-8")
    session_path.symlink_to(outside)

    with pytest.raises(FovuxPathValidationError, match="symlink|escapes"):
        revoke_session_token(raw, home=home)

    assert outside.read_text(encoding="utf-8") == stored


def test_session_store_uses_restrictive_permissions(tmp_path: Path) -> None:
    """The scoped-session registry should be private on POSIX hosts."""
    _ = create_session_token(home=tmp_path)
    if sys.platform != "win32":
        assert auth_session_path(tmp_path).stat().st_mode & 0o777 == 0o600
