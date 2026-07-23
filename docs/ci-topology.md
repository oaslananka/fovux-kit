# CI Topology and Runtime Budget

This document defines the required CI lanes and records the measured cost of the previous topology.
The required `ci-required` context is an aggregate; individual implementation jobs may evolve without
changing the protected-branch contract.

## Required lanes

| Lane                      | Runtime                                   | Responsibility                                                                                   |
| ------------------------- | ----------------------------------------- | ------------------------------------------------------------------------------------------------ |
| Required quality gate     | Ubuntu, Python 3.12, Node 24              | Full install, lint, type checking, coverage, security, docs, package builds, and release dry-run |
| Python/OS compatibility   | Ubuntu, macOS, Windows × Python 3.12–3.14 | Import, filesystem/process tests, path-policy tests, shutdown behavior, and wheel build smoke    |
| Node compatibility        | Ubuntu × Node 22 and 24                   | Studio install/typecheck/unit/build and npm-wrapper syntax/package smoke                         |
| Renovate policy           | Ubuntu, Python 3.12                       | Deterministic repository-specific Renovate policy validation                                     |
| Scheduled slow validation | Ubuntu, Python 3.12                       | Slow, integration, chaos, and benchmark-marked backend tests                                     |

The scheduled mutation workflow remains separate because mutation execution has a different timeout,
artifact, and score contract. Security SAST and dependency scanners remain in the required
`security-required` workflow rather than being repeated in compatibility cells.

## Local pre-merge aggregate

`task ci` mirrors the single primary quality lane at the repository's locked Python and Node
runtimes. It intentionally does not claim full hosted parity. Run `task verify:required` before merge
to add every deterministic credential-free required local gate: Renovate policy validation, pinned
Semgrep rules and fixtures, Trivy filesystem vulnerability scanning, and OSV lockfile scanning.

The mapping lives in `required-local-gates.json` and is enforced by
`python scripts/check_required_local_gates.py`. Hosted compatibility matrices, CodeQL, Dependency
Review, Scorecard, and strict repository posture checks are explicit hosted-only boundaries rather
than silently skipped local work.

## Aggregation contract

`ci-required` succeeds only when all of these results are successful:

- `quality`;
- `compatibility-required`;
- `node-required`;
- `renovate-config`.

Cancelled or skipped required lanes are failures. Scheduled slow validation is visible and actionable,
but it is not a pull-request requirement.

## Before-change baseline

The old workflow ran `task ci` in every combination of three operating systems, three Python versions,
and two Node versions: 18 full-suite jobs per change.

| Run                                                                             | Result  | Full-suite cells | Summed matrix-job minutes | Workflow wall time |
| ------------------------------------------------------------------------------- | ------- | ---------------: | ------------------------: | -----------------: |
| [29770039085](https://github.com/oaslananka/fovux-kit/actions/runs/29770039085) | success |               18 |                      81.1 |            7.3 min |
| [29768307966](https://github.com/oaslananka/fovux-kit/actions/runs/29768307966) | success |               18 |                      85.6 |            8.0 min |
| [29760985335](https://github.com/oaslananka/fovux-kit/actions/runs/29760985335) | success |               18 |                      82.9 |           11.2 min |
| **Average**                                                                     |         |           **18** |                  **83.2** |        **8.8 min** |

These values are elapsed job minutes derived from GitHub job start/completion timestamps; they are not
billing statements.

## After-change measurement

The first fully successful pull-request run of the new topology was
[29778303542](https://github.com/oaslananka/fovux-kit/actions/runs/29778303542).

| Measurement                      | Previous average | New topology |                          Change |
| -------------------------------- | ---------------: | -----------: | ------------------------------: |
| Full quality-suite cells         |               18 |            1 |                          -94.4% |
| Focused Python/OS smoke cells    |                0 |            9 | explicit compatibility coverage |
| Focused Node smoke cells         |                0 |            2 |       explicit runtime coverage |
| Summed required-lane job minutes |         83.2 min |      9.0 min |                      **-89.2%** |
| Workflow wall time               |          8.8 min |      8.0 min |                           -9.1% |

The 8.0-minute wall time includes macOS runner queue delay: the actual required-lane execution consumed
9.0 summed job minutes, split into 3.9 minutes for the full quality gate, 4.3 minutes for nine
Python/OS compatibility jobs, and 0.7 minutes for two Node jobs. Later runs should remain within the
same lane responsibilities; regressions that move docs, security, or release work back into
compatibility cells are rejected by unit tests.

## Failure and cancellation behavior

- A quality failure blocks `ci-required` directly.
- A failed Python/OS cell fails `compatibility-required`, which blocks `ci-required`.
- A failed Node cell fails `node-required`, which blocks `ci-required`.
- Superseded pull-request runs are cancelled by the workflow concurrency group.
- Scheduled slow validation reports independently and does not mask required-lane results.
