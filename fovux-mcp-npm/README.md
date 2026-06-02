# fovux-mcp npm wrapper

This package provides the `fovux-mcp` and `fovux` command shims for npm users.
It delegates to the matching Python package version through `uvx`.

## Usage

```bash
npx fovux-mcp --help
```

For persistent installs:

```bash
npm install -g fovux-mcp
fovux-mcp --help
```

The shim requires `uv` or `uvx` to be available on `PATH`. By default it runs
`fovux-mcp` from the Python package version matching this npm package. For local
development before a release is published, set `FOVUX_MCP_PYTHON_PACKAGE` to a
local package path or alternate package spec.
