# Fovux Kit Agent Instructions

These instructions apply repository-wide. A nested `AGENTS.md` may narrow or add rules for its subtree; the closest applicable file wins for local implementation details.

Nested instructions may not weaken repository-wide security, local-first privacy, tool-policy, release integrity, compatibility, evidence, or product-truth constraints unless the underlying policy is intentionally changed in the same pull request.

## Repository identity

Fovux Kit is one source repository for three coordinated release surfaces:

- `fovux-mcp` — Python CLI/core/MCP server plus the localhost HTTP/SSE API used by Studio;
- `fovux-studio` — VS Code extension and webviews;
- `fovux-mcp-npm` — npm launcher/wrapper that delegates to the matching Python package.

The repository is local-first. There is no hosted Fovux control plane by default.

## Nested boundaries

Read the root instructions plus the closest relevant file:

- `fovux-mcp/AGENTS.md` — Python core, MCP tools, local HTTP API, filesystem/process/model execution, policy/challenge behavior.
- `fovux-studio/AGENTS.md` — VS Code extension, local API client, webviews, workspace trust, packaging.
- `fovux-mcp-npm/AGENTS.md` — npm launcher compatibility/delegation boundary.
- `scripts/AGENTS.md` — repository policy-as-code, generated contracts, docs truth, release/security validation.
- `.github/AGENTS.md` — CI, security, required checks, publishing, protected environments, provenance.

Do not add one instruction file per module. Add a nested boundary only when authority, compatibility, generated-state, or security semantics materially differ from the parent.

## Read first

Before changing behavior, read the affected code/tests plus the relevant sources of truth:

- `README.md`
- `docs/architecture.md`
- `docs/development.md`
- `docs/testing.md`
- `docs/runtime-compatibility.md`
- `docs/threat-model.md`
- `docs/repository-operations.md`
- `docs/release-process.md`
- `docs/branch-protection.md`

For agent/tool safety, also read `docs/agent-training-workflow.md`, `docs/audit-event-schema.md`, and the backend security/tool policy docs.

## Product truth

- Do not claim cloud isolation, remote multi-user authorization, model accuracy, calibration, export correctness, hardware acceleration, edge suitability, or deployment readiness without evidence that actually exercises that claim.
- Local unit tests, synthetic benchmark data, packaged-VSIX smoke, GPU runs, network tests, and real exported runtime tests are different evidence classes.
- A generated support matrix or docs page must reflect the actual current tool/runtime contract.
- Do not invent training metrics, evaluation scores, dataset quality, GPU capability, benchmark latency, export compatibility, security review, release publication, or registry state.

## Local-first security model

- Fovux HTTP binds to loopback by default. Do not broaden the bind address or document reverse-proxy exposure as safe without a new threat model and authentication design.
- HTTP bearer tokens are local secrets. Never log raw tokens or include them in support bundles.
- CORS is not authentication.
- HTTP mutating/high-impact tool calls must preserve policy mode, scope, challenge/confirmation, timeout, concurrency, and audit semantics.
- Filesystem operations must remain constrained by the documented path policy and canonicalized paths.
- Process execution must use structured arguments and validated executables/paths rather than shell interpolation of untrusted values.
- Tool output, dataset/model paths, external CLI output, uploaded/imported data, and local API responses are untrusted until validated.

## Tool and agent policy

The tool registry, generated manifest/schema/docs, Studio LM-tool mappings, policy metadata, and runtime implementation are one contract.

- Do not add a tool only in one surface.
- Tool names, schemas, side effects, scope requirements, confirmation/challenge behavior, and timeout/concurrency policy must remain synchronized.
- Safe/developer/automation/lab policy modes have explicit semantics; do not convert an unknown or malformed policy state into permission.
- Lab mode is the explicit exceptional scope-bypass mode; do not create hidden bypasses elsewhere.
- Destructive/irreversible/high-impact behavior requires the documented challenge/effect contract.

## Reproducibility and generated state

- Run artifacts, export history, benchmark evidence, generated Studio LM tools, tool docs/schema snapshots, release metadata and generated package docs must be reproducible.
- Do not hand-edit generated files when an owning generator/check exists.
- Do not change quality/security thresholds, coverage floors, review evidence, release truth, version checks, export matrices, mutation policy, or security posture data merely to hide a regression.

## Local verification

Use Taskfile commands and the locked toolchains.

Representative checks:

```text
task lint
task typecheck
task test
task test:cov
task docs
task build
task security
task security:developer
task verify:required
```

Start narrow and expand according to the touched boundary. GPU/network/slow/integration/e2e tests must be reported honestly when they are not run.

## Compatibility

The Python package, npm wrapper, and Studio release/version contracts are intentionally coordinated but may have distinct versions. Do not assume version equality unless the documented compatibility/release contract requires it.

Changes to MCP transport, Studio local API, generated tool schemas, Python support, Node support, export targets, or release surfaces require the corresponding compatibility/doc checks.

## Release and supply chain

- Release Please owns release proposals; do not hand-edit generated release/version changes outside the intended process.
- Publishing occurs only through protected GitHub workflows/environments.
- Keep action pins, Trusted Publishing/OIDC, checksums, SBOMs, provenance, package verification, and marketplace evidence aligned to the same source identity.
- Do not publish locally or from a pull-request job unless the task explicitly changes the release design.
- Released tags/artifacts are immutable.

## Definition of done

A change is ready when:

1. the diff is scoped to the intended product/boundary;
2. the relevant nested instructions were followed;
3. focused tests cover the changed behavior, including failure/denial paths;
4. generated tool/docs/schema artifacts are synchronized through their generator;
5. local-first security and tool-policy semantics are not weakened;
6. docs/compatibility/release notes are updated when public contracts change;
7. exact-head CI/security/review evidence is clean, with manual/environment-dependent gaps stated explicitly.
