# Repository Policy Script Instructions

These instructions apply to `scripts/**` and supplement the root instructions.

This directory is policy-as-code: docs truth, release truth, tool contracts, compatibility, review evidence, security posture, generated Studio tools, export matrices, deployment profiles, benchmark reproducibility and publishing verification are enforced here.

## Fail closed

- Missing, malformed, stale, contradictory or unverifiable required evidence must not become success.
- Do not reduce thresholds, remove required checks, broaden exceptions, add blanket suppressions or rewrite expected data merely to green CI.
- If a documented contract intentionally changes, update the checker, focused regression tests, owning docs/config, and generated state together.

## Generators

- Generated Studio LM tools, SBOMs, docs-derived state and release metadata must remain deterministic.
- Change source-of-truth inputs first, run the generator, and review semantic output.
- `--check` modes should detect drift without mutating the repository.

## External tools and supply chain

- Pinned scanner/tool versions and verified downloads are security policy.
- Preserve checksum/version verification for downloaded binaries.
- Do not print tokens, registry credentials, marketplace secrets or provider credentials.
- Credential-aware checks must fail honestly when a required protected context is unavailable; they must not fake a completed remote verification.

## Tests

Every substantive policy checker/generator change needs focused regression coverage where the repository has a test harness. Run the specific checker first, then the higher-level `task docs`, security or release gate that consumes it.
