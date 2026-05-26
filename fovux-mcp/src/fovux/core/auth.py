"""Local authentication helpers for the optional HTTP transport."""

from __future__ import annotations

import hashlib
import os
import secrets
from pathlib import Path

from fovux.core.paths import get_fovux_home

TOKEN_BYTES = 32


def auth_token_path(home: Path | None = None) -> Path:
    """Return the path to the local HTTP auth token."""
    base = home or get_fovux_home()
    return base / "auth.token"


def ensure_auth_token(home: Path | None = None) -> tuple[str, bool]:
    """Return the existing auth token or generate a new one."""
    path = auth_token_path(home)
    if path.exists():
        return path.read_text(encoding="utf-8").strip(), False

    token = secrets.token_hex(TOKEN_BYTES)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(token, encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return token, True


def read_auth_token(home: Path | None = None) -> str:
    """Read the persisted auth token, generating it if needed."""
    token, _ = ensure_auth_token(home)
    return token


def rotate_auth_token(home: Path | None = None) -> str:
    """Regenerate and persist a new auth token."""
    path = auth_token_path(home)
    token = secrets.token_hex(TOKEN_BYTES)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(token, encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return token


def token_fingerprint(token: str) -> str:
    """Return a short SHA-256 fingerprint for logs."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:12]
