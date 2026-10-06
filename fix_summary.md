## Fix Summary: Origin Validation for WebView Message Handlers

### Issue
SonarCloud reported a security finding in `fovux-studio/src/webviews/trainingLauncher/main.tsx:104`:
> "Verify the origin of the received message."

The same issue existed in `fovux-studio/src/webviews/annotationEditor/main.tsx`.

### Root Cause
Both webviews registered `window.addEventListener("message", ...)` handlers without validating the message origin. This could allow malicious messages from untrusted origins to be processed.

### Fix Applied
Added origin validation to both message handlers in the `useEffect` hooks:

```typescript
if (event.origin !== window.origin) {
  return;
}
```

This ensures only messages from the same origin (the VS Code webview host) are processed.

### Files Changed
1. `fovux-studio/src/webviews/trainingLauncher/main.tsx` (lines 93-95)
2. `fovux-studio/src/webviews/annotationEditor/main.tsx` (lines 69-71)

### Verification
All quality checks pass:
- ✅ `pnpm run lint` (ESLint)
- ✅ `pnpm run typecheck` (TypeScript)
- ✅ `pnpm test` (Vitest - 20 test files, 104 tests)
- ✅ `pnpm run build` (tsup)
- ✅ `semgrep scan` (security rules - 0 findings)

The changes are minimal, focused, and follow VS Code webview security best practices.
