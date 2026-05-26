# Governance

## Project Model

Fovux is maintained under a **single-maintainer model**. All final decisions on
architecture, releases, and breaking changes rest with the project maintainer.

## Current Maintainer

See [MAINTAINERS.md](MAINTAINERS.md).

## Decision Process

### Non-breaking changes

Pull requests for bug fixes, documentation, and backward-compatible features
are reviewed and merged by the maintainer on a best-effort basis.

### Breaking changes (RFC process)

Any change that modifies the public API surface, removes a tool, or changes
default behavior requires:

1. A **Discussion thread** (category: RFC) open for at least 14 days.
2. An **Architecture Decision Record** (ADR) documenting the rationale and
   migration path, committed to `fovux-mcp/docs/adr/`.
3. Explicit maintainer approval before implementation begins.

### Release process

Releases follow [Semantic Versioning](https://semver.org/). The release
process is documented in [docs/release-process.md](docs/release-process.md).

## Contributor Promotion

Contributors who demonstrate sustained, high-quality contributions may be
invited to join the maintainer team. Criteria:

- At least 10 merged PRs across at least 3 months.
- Demonstrated understanding of the codebase and architecture.
- Adherence to the project's code of conduct.
- Willingness to commit to ongoing review and triage responsibilities.

The current maintainer makes all promotion decisions.
