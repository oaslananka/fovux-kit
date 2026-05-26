"""Unit tests for local HTTP auth token helpers."""

from __future__ import annotations

import re
from pathlib import Path

from fovux.core.auth import (
    auth_token_path,
    ensure_auth_token,
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
