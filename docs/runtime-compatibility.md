# Runtime Compatibility

This matrix is the repository policy for development, CI, and release builds.

## Python

`fovux-mcp` supports CPython 3.12, 3.13, and 3.14.

- `requires-python` is `>=3.12,<3.15`.
- CI runs the backend test suite across all supported Python minors.
- The nightly latest-dependency compatibility job runs on Python 3.13 and 3.14 to catch resolver or wheel regressions early.

Python 3.14 is supported because the locked dependency graph resolves and the backend test suite
passes on CPython 3.14.5 with the current ONNX, ONNX Runtime, OpenCV, NumPy, FastAPI, and FastMCP
constraints.

## Node.js

Fovux Studio and the npm wrapper support Node 22 and Node 24.

- Node 24.16.0 is the pinned local and release-build baseline in `.nvmrc`.
- Node 22 remains a supported maintenance-LTS lane and is still exercised in CI.
- Node 18 is not supported by project packages because it is end-of-life.

## pnpm

Fovux Studio uses `pnpm@10.34.1`.

The selected baseline is the latest pnpm 10 release line. pnpm 11 is stable, but it requires Node
22.13 or newer and changes package configuration handling for the `pnpm` manifest field. Keeping the
latest 10.x line preserves the current Node 22/24 support policy while avoiding package-manager
major-version churn in this compatibility update.

## Python datetime and HTTP test-client policy

The SQLite-backed run registry does not rely on Python's default `sqlite3` datetime adapters or
converters. Registry timestamp columns use an explicit SQLAlchemy `UtcDateTime` type that stores
UTC timestamps as ISO-8601 text and deserializes them back to naive UTC `datetime` objects for
backward-compatible ORM behavior. Raw migration writes serialize timestamps before binding.

HTTP route tests use Starlette's `TestClient` import path and the dev dependency set includes
`httpx2>=2.7.0,<3`, which is the non-deprecated backend expected by Starlette 1.3.x. The contract
suite asserts that Starlette selected `httpx2` rather than its deprecated `httpx` fallback, and the
matching `StarletteDeprecationWarning` is promoted to an error through the repository pytest policy.
Affected modules also run with general `DeprecationWarning` failures during compatibility review.

## MCP client compatibility

MCP client compatibility results live in [`mcp-client-compatibility.md`](mcp-client-compatibility.md).
That page tracks client, OS, transport, install method, smoke command, status, known limitations,
raw JSON-RPC coverage, and the manual GUI checklist.

## MCP stdio startup budget

The supported client command is `fovux-mcp` with no arguments. It dispatches through the lightweight
`fovux.stdio` entry point, registers release-time schemas from the packaged manifest, and imports an
implementation module only when that tool is called. Raw `initialize` must complete within 25 seconds
on supported Linux CI workers. `FOVUX_STARTUP_DIAGNOSTICS=1` writes stage timing records to stderr,
and the scheduled compatibility lane repeats initialization three times with
`scripts/check_stdio_startup.py`.

## Source Checks

This policy was refreshed against:

- Python.org release downloads for Python 3.14.5.
- Node.js release schedule and the Node.js Release Working Group schedule.
- pnpm installation and compatibility documentation.
- npm registry metadata for `pnpm@10.33.0`, `pnpm@10.34.1`, and `pnpm@11.5.1`.
