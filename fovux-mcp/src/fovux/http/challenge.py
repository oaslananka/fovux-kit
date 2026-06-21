"""Server-issued confirmation challenges for risky tool calls.

Replaces the plain `confirm: true` flow with a server-issued, single-use,
short-lived challenge bound to the exact tool name and argument hash.

Flow:
  1. Client calls POST /tools/{name}/challenge with the tool payload.
  2. Server returns a challenge_id and human-readable summary.
  3. User approves in Studio.
  4. Client calls POST /tools/{name} with the same payload + challenge_id.
  5. Server verifies the challenge before executing the tool.
"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field

CHALLENGE_TTL_SECONDS = 120


@dataclass
class ChallengeRecord:
    """A single-use, time-limited confirmation challenge."""

    challenge_id: str
    tool_name: str
    args_hash: str
    risk_level: str
    resolved_paths: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.monotonic)
    expires_at: float = field(default_factory=lambda: time.monotonic() + CHALLENGE_TTL_SECONDS)
    used: bool = False


def make_challenge_id() -> str:
    """Return a cryptographically random 32-hex-char challenge identifier."""
    return secrets.token_hex(16)


def create_challenge(
    *,
    tool_name: str,
    args_hash: str,
    risk_level: str,
    resolved_paths: list[str] | None = None,
) -> ChallengeRecord:
    """Create a new challenge for the given tool and argument hash."""
    return ChallengeRecord(
        challenge_id=make_challenge_id(),
        tool_name=tool_name,
        args_hash=args_hash,
        risk_level=risk_level,
        resolved_paths=resolved_paths or [],
    )


def verify_challenge(
    challenges: dict[str, ChallengeRecord],
    *,
    challenge_id: str,
    tool_name: str,
    args_hash: str,
) -> None:
    """Verify a challenge is valid, unexpired, unused, and matches the tool.

    Raises:
        HttpToolPolicyError: if the challenge is missing, expired, used,
            or does not match the tool name / argument hash.
    """
    from fovux.http.tool_proxy import HttpToolPolicyError

    record = challenges.get(challenge_id)
    if record is None:
        raise HttpToolPolicyError(
            f"Confirmation challenge '{challenge_id}' not found.",
            hint="Request a new challenge via POST /tools/{name}/challenge.",
        )

    if record.used:
        raise HttpToolPolicyError(
            f"Confirmation challenge '{challenge_id}' has already been used.",
            hint="Each challenge can only be used once. Request a new one.",
        )

    if time.monotonic() > record.expires_at:
        raise HttpToolPolicyError(
            f"Confirmation challenge '{challenge_id}' has expired.",
            hint="Request a fresh challenge and approve it before the expiry window.",
        )

    if record.tool_name != tool_name:
        raise HttpToolPolicyError(
            f"Confirmation challenge '{challenge_id}' was created for tool "
            f"'{record.tool_name}', not '{tool_name}'.",
            hint="Request a challenge for the exact tool you intend to call.",
        )

    if record.args_hash != args_hash:
        raise HttpToolPolicyError(
            f"Confirmation challenge '{challenge_id}' does not match the "
            f"current tool arguments.",
            hint="The tool arguments changed after the challenge was issued. "
            "Request a new challenge with the updated arguments.",
        )

    record.used = True


def prune_expired_challenges(challenges: dict[str, ChallengeRecord]) -> int:
    """Remove expired challenges and return the number pruned."""
    now = time.monotonic()
    expired = [cid for cid, record in challenges.items() if now > record.expires_at]
    for cid in expired:
        challenges.pop(cid, None)
    return len(expired)
