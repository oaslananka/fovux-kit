# HTTP Service Boundary Design

## Status

Accepted for implementation from issue #131.

## Context

`fovux.http.routes` currently owns FastAPI request mapping, run-registry access, metric streaming,
confirmation challenges, tool execution, background operations, lineage serialization, and resource
listing in one 1,500-line module. `fovux.http.app` imports that router while operation execution imports
`_thread_local` back from `fovux.http.app`, creating an internal cycle. This makes orchestration hard to
test without an HTTP client and makes security-sensitive behavior difficult to review in isolation.

The public Studio local API, authentication model, challenge semantics, path policy, audit events,
error payloads, timeouts, concurrency limits, SSE formats, and MCP tool contract must not change.

## Decision

### Dependency direction

The dependency direction is strictly one-way:

```text
app.py
  -> routes package
      -> services package
          -> core/runs, checkpoints, challenge, tool_proxy, validation
  -> thread_stream.py
```

No module under `fovux.http.routes` or `fovux.http.services` may import `fovux.http.app`.

### Application composition

`create_app()` creates or accepts an `HttpServices` container, stores it on `app.state.http_services`,
and includes a router assembled by `build_http_router()`. Existing state attributes such as
`challenges`, `tool_semaphores`, `tool_operations`, `tool_operation_results`,
`active_operation_tasks`, and `sse_listeners` remain aliases to service-owned state so existing
security and compatibility tests keep observing the same runtime data.

### Transport-neutral services

- `RunService` owns run listing, detail/search serialization, run-directory resolution, metric
  snapshots, and metric SSE event generation.
- `ChallengeService` owns challenge policy lookup, effect summaries, creation, pruning, and exact
  payload binding.
- `ToolInvocationService` owns idempotent timeout continuation, semaphore control, tool invocation,
  audit logging, and conversion of domain failures into typed service outcomes/errors.
- `OperationService` owns persistent operation creation, idempotency, background execution,
  cancellation, result/log retrieval, and operation-event streaming.
- `LineageService` owns run lineage, lifecycle events, dataset records, and export records.

Services do not import FastAPI or Starlette. They return Python mappings, async iterators, and typed
service exceptions/outcomes. Route modules alone map these values to `JSONResponse`,
`StreamingResponse`, `PlainTextResponse`, and `HTTPException`.

### Route organization

The previous module becomes a package:

- `routes/health.py`: `/health`, `/metrics`
- `routes/runs.py`: run list/detail/search and run metric streams
- `routes/tools.py`: challenge and direct tool invocation
- `routes/operations.py`: operation CRUD, logs/results, and `/events`
- `routes/lineage.py`: run lineage and run lifecycle events
- `routes/resources.py`: datasets and exports
- `routes/__init__.py`: router aggregation and temporary helper re-exports used by internal tests

Each route file stays under 260 source lines and each route handler under 60 lines. Service modules
stay under 520 lines and each public service method under 110 lines. Architecture tests enforce these
budgets and the no-cycle rule.

### Thread-local output capture

`ThreadLocalStream`, its thread-local storage, and installation are moved from `app.py` to
`thread_stream.py`. `app.py` installs the wrapper at import time as before. `OperationService` uses a
context manager from `thread_stream.py` to redirect one worker thread's stdout/stderr to its operation
log without importing the application factory.

### Compatibility strategy

Endpoint paths, methods, OpenAPI parameter names, response status codes, JSON shapes, SSE payloads,
headers, challenge IDs, tool audit fields, and registry writes remain unchanged. The new
`fovux.http.routes` package re-exports metric and tool-operation helpers currently imported by unit
tests while those tests migrate toward service-level coverage. No public MCP schema or Studio command
changes are introduced.

## Error handling

Services raise typed exceptions carrying domain details, not response objects. Route handlers map:

- missing records to the existing 404 details;
- challenge/policy/scope failures to the existing structured 403 payloads;
- validation failures to the existing 422 payload;
- Fovux domain failures to the existing structured 400 payload;
- tool concurrency to 429;
- request-timeout continuation to 202;
- completed background failures to 500;
- operation cancellation result to 400;
- running operation result to 202.

Unexpected background failures continue to be persisted and logged, and semaphore release remains
exception-safe.

## Testing

1. Architecture tests parse imports and source functions to enforce dependency direction and budgets.
2. Service-level tests use fake registries, fake invokers, deterministic clocks, and in-memory runtime
   state without `TestClient`.
3. Existing HTTP route, challenge, policy, lineage, shutdown, contract, integration, and security tests
   remain unchanged unless their internal patch target moves.
4. OpenAPI paths and schemas are compared before and after the refactor.
5. Full Ruff, strict mypy, backend test, docs truth, task docs, test-strategy, and tool-contract gates
   run before PR creation.

## Consequences

- Route handlers become reviewable transport adapters.
- Orchestration becomes independently testable and reusable by a future transport without adding that
  transport now.
- Runtime state is explicit and injectable.
- The refactor adds modules but removes a monolith and the application import cycle.
- Internal patch paths change; compatibility re-exports minimize churn while tests transition.

## Out of scope

- Remote/public binding changes.
- OAuth/OIDC or multi-user support.
- New endpoints or response fields.
- Public MCP tool schema changes.
