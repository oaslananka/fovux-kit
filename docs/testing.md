# Testing Guide

This document describes the Fovux test strategy for both sub-packages.

## Test Architecture

```text
fovux-mcp/tests/
├── unit/          # Fast, isolated, no GPU, no network
├── integration/   # Real server and cross-process behavior
├── security/      # Security-focused regression tests
├── bench/         # Performance regression tests
├── chaos/         # Fault injection and concurrency checks
└── contract/      # API schema and contract checks

fovux-studio/test/suite/
├── *.test.ts      # Vitest unit and integration tests
└── a11y/          # Accessibility tests
```

## Running Tests

### Full local CI parity

```bash
task ci
```

### Fast pre-push baseline

```bash
task test:fast
```

### Coverage

```bash
task test:cov
```

Coverage reports are written under `fovux-mcp/htmlcov/` and
`fovux-mcp/coverage.xml`.

### fovux-mcp only

```bash
cd fovux-mcp
uv run pytest -x --no-header -q
```

### fovux-studio only

```bash
cd fovux-studio
pnpm test --run
```

## Test Markers

| Marker | Description | Included in `task test:fast`? |
|---|---|---|
| `network` | Requires external network access | No |
| `integration` | Spawns services or crosses process boundaries | No |
| `slow` | Long-running validation | No |
| `gpu` | Requires CUDA or GPU-specific runtime | No |
| `chaos` | Fault injection and adversarial tests | No |
| `contract` | API contract tests | Yes |
| `benchmark` | Performance benchmarks | No |
| `security` | Security and pentest-style tests | No |

## Coverage Targets

| Package | Target | Current gate |
|---|---:|---:|
| `fovux-mcp` | 92% | `--cov-fail-under=92` |
| `fovux-studio` | 85% | `pnpm coverage` |

## Security Scans

```bash
task security
```

The security task runs Bandit, pip-audit, npm audit, and gitleaks.

## Local GPU Tests

```bash
cd fovux-mcp
uv run pytest -m "gpu" --no-header -v
```

GPU tests require a CUDA-capable GPU and compatible runtime packages.
