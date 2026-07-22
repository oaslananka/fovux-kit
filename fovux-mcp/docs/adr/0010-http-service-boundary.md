# ADR 0010: Studio HTTP service boundary

## Status

Accepted

## Context

The Studio local HTTP/SSE API previously lived in one `fovux.http.routes` module with more than 1,500
lines. That module handled FastAPI request/response mapping, run registry queries, metric streaming,
confirmation challenges, tool execution, background operation persistence, lineage serialization,
dataset/export listing, and Prometheus snapshots.

Background operation logging also imported thread-local state from `fovux.http.app`, while the
application factory imported the route module. This created an internal application/routes import
cycle and made orchestration behavior difficult to test without starting an HTTP client.

The API is already consumed by Fovux Studio. Endpoint paths, methods, status codes, JSON bodies, SSE
formats, authentication, challenge binding, path policy, audit fields, timeouts, concurrency limits,
and error semantics therefore must remain backward compatible.

## Decision

Split the HTTP surface into domain route adapters and transport-neutral services with one-way
dependencies:

```text
fovux.http.app
  -> fovux.http.routes
      -> fovux.http.services
          -> fovux.core, challenge, tool_proxy
  -> fovux.http.thread_stream
```

Modules under `fovux.http.routes` and `fovux.http.services` must not import `fovux.http.app`.
Architecture tests enforce this rule.

### Application composition

`create_app()` accepts an optional `HttpServices` container. Production calls use
`build_default_services()`; tests can inject deterministic services without replacing the application
factory. The selected container is stored as `app.state.http_services`.

Historical state attributes remain aliases to service-owned runtime state:

- `challenges`
- `tool_semaphores`
- `tool_operations`
- `tool_operation_results`
- `active_operation_tasks`
- `sse_listeners`

This preserves existing middleware, shutdown, security, and compatibility observations while making
state ownership explicit.

### Route adapters

The route package is organized by domain:

- `routes/health.py`: `/health` and `/metrics`
- `routes/runs.py`: run list, detail, search, and metric streams
- `routes/tools.py`: challenges and direct tool invocation
- `routes/operations.py`: persistent operations, logs, results, cancellation, and operation SSE
- `routes/lineage.py`: run lineage and lifecycle events
- `routes/resources.py`: datasets and exports
- `routes/__init__.py`: router aggregation and temporary internal compatibility exports

Route handlers parse transport inputs, call one service boundary, and map typed service errors or
outcomes to FastAPI responses. They do not own registry access, tool execution, or background task
state machines.

### Services

- `RunService` owns run summaries/details/search, registered run-path resolution, metric snapshots,
  incremental JSONL parsing, and metric SSE orchestration.
- `ChallengeService` owns challenge creation, policy checks, exact payload binding, and effect summaries.
- `ToolInvocationService` owns timeout continuation, retained result replay, concurrency control,
  validation/domain error classification, and tool audit events.
- `OperationService` owns persistent operation creation, idempotency, background execution,
  cancellation, log/result access, and operation-event streaming.
- `LineageService` owns run lineage, lifecycle event, dataset, and export serialization.
- `HealthService` owns health metadata and Prometheus registry counters.

Services do not import FastAPI or Starlette. They return mappings, async iterators, typed
`ServiceOutcome` values, or `ServiceError` exceptions.

### Thread-local output capture

`ThreadLocalStream` and the current-thread redirection context moved to `fovux.http.thread_stream`.
The application installs stdout/stderr wrappers idempotently. `OperationService` uses
`redirect_thread_output()` to capture only the worker thread's output without importing the
application factory.

### Compatibility and lazy dependencies

Default registry providers and tool invokers resolve their underlying modules at call time. This
preserves runtime/test overrides and prevents partially initialized tool modules during cold registry
bootstrap. Public tool schemas and Studio command mappings are unchanged.

The route package temporarily re-exports internal metric and timed-tool helper names used by focused
unit tests. These are not public API guarantees and can be removed after all internal consumers use
service modules directly.

## Error mapping

Services preserve the established transport semantics:

- missing run, operation, or dataset: `404`
- disabled metrics: `404`
- policy, confirmation, or scope rejection: structured `403`
- payload validation: structured `422`
- Fovux domain failure: structured `400`
- tool concurrency exhaustion: `429`
- request timeout with one continuing worker: `202`
- operation still running: `202`
- cancelled operation result: `400`
- completed background failure: `500`

Authentication, origin validation, body limits, rate limiting, and scope enforcement remain in the
application middleware because they apply before route dispatch.

## Consequences

- The application/routes import cycle is removed.
- HTTP orchestration can be tested with fake registries and invokers without `TestClient`.
- Route and service ownership is explicit and reviewable.
- A future transport may reuse services without depending on FastAPI, but no new transport is added by
  this decision.
- More modules exist, but the former monolith is deleted and source/function budgets prevent a new
  monolith from forming.
- Internal compatibility exports add temporary maintenance cost.

## Validation

- Architecture tests reject imports from `fovux.http.app` within route/service modules.
- Route modules are limited to 260 lines and 60-line functions.
- Service modules are limited to 520 lines and 110-line functions.
- Service-level tests cover run queries/streams, challenges/tool invocation, operation persistence,
  health counters, lineage, datasets, and exports without an HTTP client.
- The historical OpenAPI path/method set is locked by a composition test.
- Existing HTTP route, challenge, policy, lineage, shutdown, security, API schema, and real-server smoke
  tests remain green.
- Ruff, strict mypy, tool contracts, docs truth, task docs, test strategy, and the repository quality
  gate validate the final branch before merge.
