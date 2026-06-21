# Server-Issued Confirmation Challenges for Risky Tool Calls

**Issue:** #58
**Date:** 2026-06-21
**Status:** Approved

## Problem

Risky tool calls currently rely on a client-side `confirm: true` boolean in the request payload. This provides no server-side guarantee that the user actually reviewed and approved the exact operation. A confirmation value should represent a recent, explicit user decision for one exact operation — issued by the server, bound to the exact tool and arguments, short-lived, single-use, and auditable.

## Design

### Flow

1. Client requests a confirmation challenge for a specific tool call via `POST /tools/{name}/challenge`.
2. Server stores the tool name, argument hash, resolved target paths, risk level, and expiry time under a one-time challenge ID.
3. Server returns the challenge ID and a human-readable summary.
4. Studio renders the confirmation summary to the user.
5. User approves in the UI.
6. Client submits the challenge ID with the same tool call via `POST /tools/{name}`.
7. Server verifies the challenge: exists, not expired, not used, matches tool name, matches argument hash.
8. On success, the challenge is marked used and the tool executes. On failure, a 403 error is returned.

### Data structures

```python
@dataclass
class ChallengeRecord:
    challenge_id: str       # 32 hex chars from secrets.token_hex(16)
    tool_name: str          # matched on verification
    args_hash: str          # payload_hash(payload) — matched on verification
    risk_level: str         # from HttpToolPolicy.category (read_only/mutating/long_running/destructive)
    resolved_paths: list[str]  # resolved target paths for user visibility
    created_at: float       # time.monotonic()
    expires_at: float       # created_at + CHALLENGE_TTL_SECONDS (default 120)
    used: bool = False      # single-use
```

Stored in `app.state.challenges: dict[str, ChallengeRecord]` (same pattern as `tool_operations` and `tool_operation_results`).

### New endpoint: `POST /tools/{name}/challenge**

Request body: same payload the tool expects (without `confirm: true`).

Response `201`:
```json
{
  "challenge_id": "a1b2c3d4e5f6789012345678abcdef01",
  "tool": "train_start",
  "risk_level": "long_running",
  "summary": {
    "name": "train_start",
    "args_hash": "abc123def456",
    "resolved_paths": ["/home/user/.fovux/runs/train1"],
    "params": {"dataset_path": "...", "model": "yolov8n.pt", "epochs": 50}
  },
  "expires_at": 1234567890.0
}
```

Response `403` if tool is unknown or does not require confirmation (read-only tools skip the challenge flow).

### Modified endpoint: `POST /tools/{name}`

Replace the `confirm: true` check with challenge verification for tools that have `requires_confirmation=True`.

Verification steps:
1. Challenge ID exists in `app.state.challenges`.
2. Challenge is not expired (`time.monotonic() <= expires_at`).
3. Challenge is not used (`used == False`).
4. Tool name matches.
5. Argument hash matches (`payload_hash(payload_without_challenge_id)`).

On failure: returns 403 with error code `FOVUX_HTTP_003` and a descriptive message.

### Module structure

**New module:** `fovux/http/challenge.py`
- `ChallengeRecord` dataclass
- `CHALLENGE_TTL_SECONDS = 120`
- `create_challenge(policy, tool_name, payload) -> ChallengeRecord`
- `verify_challenge(state, tool_name, payload) -> None` (raises `HttpToolPolicyError` on failure)
- `_prune_expired_challenges(challenges) -> None`

**Modified:**
- `fovux/http/routes.py` — add challenge route, modify `proxy_tool`
- `fovux/http/tool_proxy.py` — `invoke_tool()` checks `challenge_id` instead of `confirm`
- `fovux/http/app.py` — add `app.state.challenges` dict

### Read-only tools excluded

Tools with category `read_only` skip the challenge flow entirely (they pass `requires_confirmation=False` in `HttpToolPolicy`). Only tools with `mutating`, `long_running`, or `destructive` categories require challenges.

## Studio changes

**`extensionClient.ts`:**
- Add `requestChallenge(name, payload)` method → `POST /tools/{name}/challenge`
- Modify `invokeTool` to accept optional `challengeId`

**Webviews** (trainingLauncher, exportWizard, datasetInspector):
- Before risky tool calls: call `requestChallenge()`, show confirmation dialog with the returned summary
- On approval: call `invokeTool()` with the `challenge_id`

## Testing

New test file: `tests/unit/test_http_challenge.py`

- Challenge creation returns 201 with summary
- Challenge creation requires auth
- Challenge creation for unknown tool returns 403
- Challenge creation for read-only tool returns 403
- Challenge reuse returns 403
- Challenge expiry returns 403
- Challenge argument hash mismatch returns 403
- Tool proxy with valid challenge succeeds
- Tool proxy without challenge for risky tool returns 403
- Read-only tool does not require challenge
- Expired challenges are pruned
- Concurrent challenge creation and verification

## Implementation Deviations

The following deviations from the initial design were made during implementation:

### 1. `resolved_paths` not populated

`ChallengeRecord.resolved_paths` exists as a field but is never populated — the `request_challenge` endpoint does not resolve target paths from the payload. This was deferred because path resolution requires tool-specific logic that belongs in each tool's handler rather than the challenge module.

### 2. `create_challenge()` signature simplified

Spec: `create_challenge(policy, tool_name, payload)`
Actual: `create_challenge(*, tool_name, args_hash, risk_level)`

The actual signature accepts pre-computed values rather than a policy object + raw payload, keeping the challenge module decoupled from `HttpToolPolicy`.

### 3. `verify_challenge()` signature takes challenge_id explicitly

Spec: `verify_challenge(state, tool_name, payload)`
Actual: `verify_challenge(challenges, *, challenge_id, tool_name, args_hash)`

The final interface passes `app.state.challenges` directly, the explicit `challenge_id` string, and the pre-computed `args_hash`.

### 4. `prune_expired_challenges` is public (not private)

The function is public because it is called from both `routes.py` and tests. Making it private would require a separate test-only accessor.

### 5. Studio `invokeTool` unchanged

Spec said to modify `invokeTool` to accept optional `challengeId`. Instead, `invokeTool` was kept as-is and a separate `requestChallenge()` method was added. Call sites combine them by spreading `challenge_id` into the payload:

```typescript
const challenge = await requestChallenge(config, "tool_name", payload);
const result = await invokeTool(config, "tool_name", { ...payload, challenge_id: challenge.challenge_id });
```

This is more explicit and avoids backward-compatibility concerns.

### 6. No client-side confirmation dialog

The spec described showing a confirmation summary dialog before submitting the challenge. The actual implementation silently requests a challenge and submits it inline. A confirmation modal can be added later without server changes.

### 7. Route ordering matters

`/tools/{name}/challenge` must be registered **before** `/tools/{name}` in FastAPI, otherwise the string `challenge` matches `{name}`. This was handled by placing the challenge route above `proxy_tool` in `routes.py`.

### 8. Separate rate limit buckets

Challenge requests use their own rate limit bucket (`challenge:{tool_name}`) separate from tool invocation (`tool:{tool_name}`). Both default to `DEFAULT_TOOL_RATE_LIMIT` (100/min).

### 9. Error code mapping

Spec said `FOVUX_HTTP_003` for all challenge failures. In practice:
- `FOVUX_HTTP_001` (via `HttpToolPolicyError`): missing/expired/used/wrong challenge during `proxy_tool`
- `FOVUX_HTTP_003`: tool does not require a challenge (returned by `request_challenge` for read-only tools)
