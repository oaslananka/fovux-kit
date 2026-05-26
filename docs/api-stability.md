# API Stability

## Public vs Internal API

### Public API (stable)
- All tools registered in `core/tool_registry._TOOL_SPECS`.
- All HTTP endpoints defined in `http/routes.py`.
- The `fovux` and `fovux-mcp` CLI commands.
- Pydantic schemas exported from `fovux.schemas`.
- The `FOVUX_HOME` directory structure contract.

### Internal API (unstable)
- Functions prefixed with `_` (private by convention).
- Module-level helpers in `core/` not re-exported via `__init__.py`.
- FastMCP server internals in `server.py`.
- Test fixtures and helpers.

## Deprecation Policy

1. **Minor release N:** Feature is marked with `DeprecationWarning` at call site.
   Documentation updated with migration guidance.
2. **Minor release N+1:** Warning escalated to a structured log at `WARNING` level.
   Feature still functional but discouraged.
3. **Major release N+1:** Feature removed. Import or invocation raises `ImportError`
   or `AttributeError`.

## Versioning

Fovux follows [Semantic Versioning 2.0.0](https://semver.org/):
- **MAJOR:** Breaking changes to the public API.
- **MINOR:** New features, backward-compatible.
- **PATCH:** Bug fixes, backward-compatible.
