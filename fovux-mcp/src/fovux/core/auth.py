"""Local authentication helpers for the Fovux Studio local API."""

from __future__ import annotations

import enum
import hashlib
import json
import os
import secrets
from pathlib import Path

from fovux.core.paths import get_fovux_home
from fovux.core.secure_files import atomic_write_text, resolve_under_root

TOKEN_BYTES = 32
AUTH_FILE_NAME = "auth.token"
SESSION_FILE_NAME = "auth.session"


class Scope(enum.StrEnum):
    """Access scopes for Studio local API bearer tokens."""

    READ = "read"
    DATASET_WRITE = "dataset:write"
    RUN_START = "run:start"
    EXPORT_WRITE = "export:write"
    DESTRUCTIVE = "destructive"
    ADMIN = "admin"

    @classmethod
    def from_category(cls, category: str) -> set[Scope]:
        """Map a category string to a set of Scope values."""
        return _CATEGORY_SCOPES.get(category, {cls.READ})


ALL_SCOPES = set(Scope)

_CATEGORY_SCOPES: dict[str, set[Scope]] = {
    "read_only": {Scope.READ},
    "mutating": {Scope.DATASET_WRITE, Scope.RUN_START, Scope.EXPORT_WRITE},
    "long_running": {Scope.RUN_START},
    "destructive": {Scope.DESTRUCTIVE, Scope.ADMIN},
}


def _auth_root(home: Path | None) -> Path:
    return (home or get_fovux_home()).expanduser().resolve(strict=False)


def _safe_auth_path(home: Path | None, filename: str) -> Path:
    return resolve_under_root(_auth_root(home), Path(filename))


def auth_token_path(home: Path | None = None) -> Path:
    """Return the path to the Studio local API auth token."""
    return _auth_root(home) / AUTH_FILE_NAME


def auth_session_path(home: Path | None = None) -> Path:
    """Return the path to the local session scopes file."""
    return _auth_root(home) / SESSION_FILE_NAME


def ensure_auth_token(home: Path | None = None) -> tuple[str, bool]:
    """Return the existing auth token or generate a new one."""
    root = _auth_root(home)
    path = _safe_auth_path(home, AUTH_FILE_NAME)
    if path.exists():
        token = path.read_text(encoding="utf-8").strip()
        if token:
            return token, False

    token = secrets.token_hex(TOKEN_BYTES)
    atomic_write_text(root, Path(AUTH_FILE_NAME), token, mode=0o600)
    return token, True


def read_auth_token(home: Path | None = None) -> str:
    """Read the persisted auth token, generating it if needed."""
    token, _ = ensure_auth_token(home)
    return token


def rotate_auth_token(home: Path | None = None) -> str:
    """Regenerate and persist a new auth token."""
    token = secrets.token_hex(TOKEN_BYTES)
    atomic_write_text(_auth_root(home), Path(AUTH_FILE_NAME), token, mode=0o600)
    return token


def token_fingerprint(token: str) -> str:
    """Return a short SHA-256 fingerprint for logs."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:12]


def check_token_perms(home: Path | None = None) -> tuple[bool, str]:
    """Check that the auth token file has restrictive permissions."""
    path = _safe_auth_path(home, AUTH_FILE_NAME)
    if not path.exists():
        return False, f"{AUTH_FILE_NAME} file does not exist"
    try:
        mode = os.stat(str(path)).st_mode
        world_readable = bool(mode & 0o004)
        group_readable = bool(mode & 0o040)
        if world_readable or group_readable:
            perms = oct(mode & 0o777)
            return False, f"{AUTH_FILE_NAME} has permissive mode {perms}, expected 0o600"
        return True, f"{AUTH_FILE_NAME} permissions are safe ({oct(mode & 0o777)})"
    except OSError as exc:
        return False, f"cannot stat {AUTH_FILE_NAME}: {exc}"


def _read_sessions(home: Path | None) -> dict[str, dict[str, object]]:
    path = _safe_auth_path(home, SESSION_FILE_NAME)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return {
        fingerprint: metadata
        for fingerprint, metadata in payload.items()
        if isinstance(fingerprint, str) and isinstance(metadata, dict)
    }


def _write_sessions(home: Path | None, sessions: dict[str, dict[str, object]]) -> None:
    atomic_write_text(
        _auth_root(home),
        Path(SESSION_FILE_NAME),
        json.dumps(sessions, indent=2),
        mode=0o600,
    )


def is_known_session_token(token: str, home: Path | None = None) -> bool:
    """Check whether a token fingerprint is registered in the session store."""
    return token_fingerprint(token) in _read_sessions(home)


def create_session_token(
    scopes: set[Scope] | None = None,
    home: Path | None = None,
) -> str:
    """Create a scoped bearer session token and persist it."""
    effective_scopes = scopes if scopes is not None else ALL_SCOPES
    raw = secrets.token_hex(TOKEN_BYTES)
    fingerprint = token_fingerprint(raw)
    sessions = _read_sessions(home)
    sessions[fingerprint] = {
        "fingerprint": fingerprint,
        "scopes": sorted(scope.value for scope in effective_scopes),
    }
    _write_sessions(home, sessions)
    return raw


def resolve_session_scopes(
    token: str,
    home: Path | None = None,
) -> set[Scope]:
    """Resolve the scopes for a given bearer token."""
    meta = _read_sessions(home).get(token_fingerprint(token))
    if meta is None:
        return ALL_SCOPES
    raw_scopes = meta.get("scopes")
    if not isinstance(raw_scopes, list):
        return ALL_SCOPES
    resolved: set[Scope] = set()
    for name in raw_scopes:
        if not isinstance(name, str):
            continue
        try:
            resolved.add(Scope(name))
        except ValueError:
            pass
    return resolved if resolved else ALL_SCOPES


def revoke_session_token(token: str, home: Path | None = None) -> bool:
    """Revoke a session token by removing it from the session store."""
    fingerprint = token_fingerprint(token)
    sessions = _read_sessions(home)
    if fingerprint not in sessions:
        return False
    del sessions[fingerprint]
    _write_sessions(home, sessions)
    return True


def list_session_fingerprints(home: Path | None = None) -> list[dict[str, object]]:
    """List active session metadata (fingerprints and scopes)."""
    return [
        {
            "fingerprint": fingerprint,
            "scopes": meta.get("scopes", []) if isinstance(meta, dict) else [],
        }
        for fingerprint, meta in _read_sessions(home).items()
    ]
