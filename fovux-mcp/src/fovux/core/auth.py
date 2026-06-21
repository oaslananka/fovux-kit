"""Local authentication helpers for the optional HTTP transport."""

from __future__ import annotations

import enum
import hashlib
import os
import secrets
from pathlib import Path

from fovux.core.paths import get_fovux_home

TOKEN_BYTES = 32


class Scope(enum.StrEnum):
    """Access scopes for local HTTP bearer tokens."""

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


def is_known_session_token(token: str, home: Path | None = None) -> bool:
    """Check whether a token fingerprint is registered in the session store."""
    fingerprint = token_fingerprint(token)
    session_path = auth_session_path(home)
    if not session_path.exists():
        return False
    try:
        import json

        sessions = dict(json.loads(session_path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError):
        return False
    return fingerprint in sessions


_CATEGORY_SCOPES: dict[str, set[Scope]] = {
    "read_only": {Scope.READ},
    "mutating": {Scope.DATASET_WRITE, Scope.RUN_START, Scope.EXPORT_WRITE},
    "long_running": {Scope.RUN_START},
    "destructive": {Scope.DESTRUCTIVE, Scope.ADMIN},
}


def auth_token_path(home: Path | None = None) -> Path:
    """Return the path to the local HTTP auth token."""
    base = home or get_fovux_home()
    return base / "auth.token"


def auth_session_path(home: Path | None = None) -> Path:
    """Return the path to the local session scopes file."""
    base = home or get_fovux_home()
    return base / "auth.session"


def ensure_auth_token(home: Path | None = None) -> tuple[str, bool]:
    """Return the existing auth token or generate a new one."""
    path = auth_token_path(home)
    if path.exists():
        token = path.read_text(encoding="utf-8").strip()
        if token:
            return token, False

    token = secrets.token_hex(TOKEN_BYTES)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(token, encoding="utf-8")
    _set_restrictive_perms(path)
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
    _set_restrictive_perms(path)
    return token


def token_fingerprint(token: str) -> str:
    """Return a short SHA-256 fingerprint for logs."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:12]


def _set_restrictive_perms(path: Path) -> None:
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def check_token_perms(home: Path | None = None) -> tuple[bool, str]:
    """Check that the auth token file has restrictive permissions.

    Returns (ok, detail) where ok is True when the token file has safe permissions.
    """
    path = auth_token_path(home)
    if not path.exists():
        return False, "auth.token file does not exist"
    try:
        mode = os.stat(str(path)).st_mode
        world_readable = bool(mode & 0o004)
        group_readable = bool(mode & 0o040)
        if world_readable or group_readable:
            perms = oct(mode & 0o777)
            return False, f"auth.token has permissive mode {perms}, expected 0o600"
        return True, f"auth.token permissions are safe ({oct(mode & 0o777)})"
    except OSError as exc:
        return False, f"cannot stat auth.token: {exc}"


def create_session_token(
    scopes: set[Scope] | None = None,
    home: Path | None = None,
) -> str:
    """Create a scoped bearer session token and persist it."""
    effective_scopes = scopes if scopes is not None else ALL_SCOPES
    raw = secrets.token_hex(TOKEN_BYTES)
    fingerprint = token_fingerprint(raw)
    meta: dict[str, object] = {
        "fingerprint": fingerprint,
        "scopes": sorted(s.value for s in effective_scopes),
    }
    session_path = auth_session_path(home)
    session_path.parent.mkdir(parents=True, exist_ok=True)
    import json

    sessions: dict[str, dict[str, object]] = {}
    if session_path.exists():
        try:
            sessions = dict(json.loads(session_path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            sessions = {}
    sessions[fingerprint] = meta
    session_path.write_text(json.dumps(sessions, indent=2), encoding="utf-8")
    _set_restrictive_perms(session_path)
    return raw


def resolve_session_scopes(
    token: str,
    home: Path | None = None,
) -> set[Scope]:
    """Resolve the scopes for a given bearer token."""
    fingerprint = token_fingerprint(token)
    session_path = auth_session_path(home)
    if not session_path.exists():
        return ALL_SCOPES
    try:
        import json

        sessions = dict(json.loads(session_path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError):
        return ALL_SCOPES
    meta = sessions.get(fingerprint)
    if meta is None:
        return ALL_SCOPES
    scope_names = list(meta.get("scopes", []) if isinstance(meta, dict) else [])
    resolved = set()
    for name in scope_names:
        try:
            resolved.add(Scope(name))
        except ValueError:
            pass
    return resolved if resolved else ALL_SCOPES


def revoke_session_token(token: str, home: Path | None = None) -> bool:
    """Revoke a session token by removing it from the session store."""
    fingerprint = token_fingerprint(token)
    session_path = auth_session_path(home)
    if not session_path.exists():
        return False
    try:
        import json

        sessions = dict(json.loads(session_path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError):
        return False
    if fingerprint not in sessions:
        return False
    del sessions[fingerprint]
    session_path.write_text(json.dumps(sessions, indent=2), encoding="utf-8")
    return True


def list_session_fingerprints(home: Path | None = None) -> list[dict[str, object]]:
    """List active session metadata (fingerprints and scopes)."""
    session_path = auth_session_path(home)
    if not session_path.exists():
        return []
    try:
        import json

        sessions = dict(json.loads(session_path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError):
        return []
    return [
        {"fingerprint": fp, "scopes": meta.get("scopes", []) if isinstance(meta, dict) else []}
        for fp, meta in sessions.items()
    ]
