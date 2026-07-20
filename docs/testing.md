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

| Marker        | Description                                   | Included in `task test:fast`? |
| ------------- | --------------------------------------------- | ----------------------------- |
| `network`     | Requires external network access              | No                            |
| `integration` | Spawns services or crosses process boundaries | No                            |
| `slow`        | Long-running validation                       | No                            |
| `gpu`         | Requires CUDA or GPU-specific runtime         | No                            |
| `chaos`       | Fault injection and adversarial tests         | No                            |
| `contract`    | API contract tests                            | Yes                           |
| `benchmark`   | Performance benchmarks                        | No                            |
| `security`    | Security and pentest-style tests              | No                            |

## Coverage Targets

| Package        | Target |          Current gate |
| -------------- | -----: | --------------------: |
| `fovux-mcp`    |    92% | `--cov-fail-under=92` |
| `fovux-studio` |    85% |       `pnpm coverage` |

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

## Mutation testing gate

The scheduled mutation workflow uses mutmut 3.6.0 against a focused security-critical allowlist:

- path-policy boundaries in `fovux.core.path_policy`;
- challenge creation/verification in `fovux.http.challenge`;
- central tool dispatch in `fovux.core.tool_registry`.

The initial measured baseline on 2026-07-20 evaluated **224 mutants**: **119 killed**,
**105 survived**, **0 timeout**, **0 suspicious**, and **0 without tests**, for a **53.12%**
mutation score. The enforced starting floor is **50%**, with at most **120 survivors** and
**0 timeouts**. This is an explicit improvement baseline, not a target ceiling: score/budget changes
must be justified by a fresh machine-readable run and the floor must not be lowered silently.

The workflow fails when no mutants are evaluated, when the score or survivor/timeout budgets are
missed, or when mutmut reports no-test, suspicious, interrupted, or segmentation-fault results. It
uploads `mutation-results.txt`, `mutation-summary.md`, and
`mutants/mutmut-cicd-stats.json` for review.

Run the same focused gate locally from `fovux-mcp`:

```bash
export PY_KEY_VALUE_DISABLE_BEARTYPE=true
uv run --no-sync python ../scripts/run_mutmut.py run --max-children 2
uv run --no-sync python ../scripts/run_mutmut.py results --all true
uv run --no-sync python ../scripts/run_mutmut.py export-cicd-stats
python ../scripts/check_mutation_stats.py   mutants/mutmut-cicd-stats.json   --minimum-score 50   --max-survived 120   --max-timeouts 0   --summary-output mutation-summary.md
```
