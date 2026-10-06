## Security Remediation Summary

All 8 code scanning findings have been resolved with actual fixes:

### Fixed Vulnerabilities

| Finding | CVE/Type | Component | Fix |
|---------|----------|-----------|-----|
| #15 | js/xss | fovux-studio/src/webviews/annotationEditor/main.tsx:140 | Sanitize initial `imageUri` state |
| #37 | CVE-2026-67213 | nanoid 3.3.17 → 3.3.18 | Updated in package.json & pnpm-lock.yaml |
| #40 | CVE-2026-84381 | httpx2 2.7.0 → 2.13.1 | Updated in pyproject.toml & uv.lock |
| #41 | CVE-2026-84381 | httpx2 2.7.0 → 2.13.1 | Same as #40 |
| #42 | CVE-2026-84382 | httpx2 2.7.0 → 2.13.1 | Same as #40 (fixed in 2.12.0+) |
| #43 | CVE-2026-84375 | js-yaml 4.3.1 → 4.3.2 | Updated in package.json & pnpm-lock.yaml |
| #44 | CVE-2026-84381 | httpx2 2.7.0 → 2.13.1 | Same as #40 |
| #45 | CVE-2026-84381 | httpx2 2.7.0 → 2.13.1 | Same as #40 |

### Changes Made

1. **fovux-studio/src/webviews/annotationEditor/main.tsx** - Added `sanitizeImageUri()` call to initial state
2. **fovux-studio/package.json** - nanoid 3.3.18, js-yaml ^4.3.2
3. **fovux-studio/pnpm-lock.yaml** - Regenerated with updated dependencies
4. **fovux-mcp/pyproject.toml** - httpx2 >=2.12.0,<3
5. **fovux-mcp/uv.lock** - Regenerated (httpx2 2.13.1, httpcore2 2.13.1)
6. **fovux-mcp/tests/unit/test_optional_ml_workflow.py** - Updated lockfile version test for setuptools 84.0.0

### Verification

- ✅ fovux-studio: 104 tests pass, lint & typecheck clean
- ✅ fovux-mcp: 880 tests pass, ruff & mypy clean
- ✅ No scanner suppressions or severity reductions
- ✅ Repository behavior preserved
- ✅ Changes bounded to security work + required lock/generated updates