$ErrorActionPreference = "Stop"

$root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$targets = @(
    "dist",
    "build",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "htmlcov",
    "coverage.xml",
    "junit.xml",
    "fovux-mcp/dist",
    "fovux-mcp/build",
    "fovux-mcp/htmlcov",
    "fovux-mcp/coverage.xml",
    "fovux-mcp/junit.xml",
    "fovux-mcp/requirements-audit.txt",
    "fovux-studio/out"
)

foreach ($target in $targets) {
    $path = Join-Path $root $target
    if (Test-Path -LiteralPath $path) {
        $resolved = Resolve-Path -LiteralPath $path
        if (-not $resolved.Path.StartsWith($root.Path, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to remove path outside repository: $($resolved.Path)"
        }
        Remove-Item -LiteralPath $resolved.Path -Recurse -Force
    }
}

Get-ChildItem -Path (Join-Path $root "fovux-studio") -Filter "*.vsix" -File -ErrorAction SilentlyContinue |
    Remove-Item -Force
