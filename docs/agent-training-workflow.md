# Agent Training Workflow

Agent and guided Studio training flows must call `train_preflight` before `train_start`.

## Required order

1. Build the intended training payload.
2. Call `train_preflight` with the same dataset, model, device, limits, name, and tags.
3. If `ready` is true, call `train_start` with the reviewed payload.
4. If `ready` is false, show `blockers`, `warnings`, and `next_actions` to the user.
5. Only proceed with a human-approved force launch and an explicit approval reason.

`train_preflight` returns `ready`, `blockers`, `warnings`, `next_actions`, `override_required`, and
`override_hint` so an agent can explain exactly why training is or is not safe to start.

Studio records the approval reason as `preflight_approval_reason` before it asks for the normal
`train_start` confirmation challenge.
