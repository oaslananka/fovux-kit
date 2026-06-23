#!/usr/bin/env python3
"""Post-release verification script for PyPI, npm, and VS Code extension registries."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any


def repo_root() -> Path:
    """Return the absolute path of the repository root."""
    return Path(__file__).resolve().parent.parent


def read_pyproject_version() -> str:
    """Read the expected version from pyproject.toml."""
    pyproject = repo_root() / "fovux-mcp" / "pyproject.toml"
    content = pyproject.read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
    if not match:
        raise ValueError("Could not find version in pyproject.toml")
    return match.group(1)


def read_npm_wrapper_version() -> str:
    """Read the expected version from fovux-mcp-npm/package.json."""
    pkg = repo_root() / "fovux-mcp-npm" / "package.json"
    data = json.loads(pkg.read_text(encoding="utf-8"))
    return str(data["version"])


def read_studio_version() -> str:
    """Read the expected version from fovux-studio/package.json."""
    pkg = repo_root() / "fovux-studio" / "package.json"
    data = json.loads(pkg.read_text(encoding="utf-8"))
    return str(data["version"])


def fetch_json(url: str, data: bytes | None = None, headers: dict[str, str] | None = None) -> Any:  # noqa: ANN401
    """Fetch JSON from a URL with custom headers and method."""
    if not url.startswith("https://"):
        raise ValueError(f"URL must start with https://: {url}")
    req = urllib.request.Request(url, data=data, headers=headers or {})  # noqa: S310
    with urllib.request.urlopen(req, timeout=30) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def verify_pypi(version: str, smoke_test: bool) -> None:
    """Verify PyPI package presence and run isolation smoke tests."""
    print(f"Verifying PyPI release for fovux-mcp v{version}...")
    url = f"https://pypi.org/pypi/fovux-mcp/{version}/json"

    # 1. Check metadata
    meta = fetch_json(url)
    info = meta.get("info", {})
    project_urls = info.get("project_urls", {})
    repo_url = project_urls.get("Homepage") or project_urls.get("Repository") or ""
    if "oaslananka/fovux-kit" not in repo_url:
        print(f"Warning: Repository URL {repo_url!r} does not match expected repository.")

    description = info.get("description", "")
    if "oaslananka/fovux-kit" not in description:
        raise ValueError("PyPI description is missing repository homepage reference.")

    print("PyPI metadata verified successfully.")

    # 2. Virtual environment install and command smoke test
    if smoke_test:
        print("Running PyPI package installation smoke test...")
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            subprocess.run(  # noqa: S603
                [sys.executable, "-m", "venv", ".venv"],
                cwd=tmp_path,
                check=True,
            )

            if os.name == "nt":
                pip_bin = tmp_path / ".venv" / "Scripts" / "pip.exe"
                fovux_bin = tmp_path / ".venv" / "Scripts" / "fovux-mcp.exe"
            else:
                pip_bin = tmp_path / ".venv" / "bin" / "pip"
                fovux_bin = tmp_path / ".venv" / "bin" / "fovux-mcp"

            # Install published package from PyPI
            subprocess.run(  # noqa: S603
                [str(pip_bin), "install", f"fovux-mcp=={version}"],
                check=True,
            )

            # Check CLI runs and prints expected version
            res = subprocess.run(  # noqa: S603
                [str(fovux_bin), "--version"],
                capture_output=True,
                text=True,
                check=True,
            )
            output = res.stdout.strip()
            print(f"Installed fovux-mcp CLI output: {output}")
            if version not in output:
                raise ValueError(f"Installed version {output!r} does not match expected {version}")

            # Run doctor
            subprocess.run([str(fovux_bin), "doctor"], check=True)  # noqa: S603
            print("PyPI smoke test passed successfully.")


def verify_npm(version: str, smoke_test: bool) -> None:
    """Verify npm package presence and run isolation wrapper smoke tests."""
    print(f"Verifying npm release for fovux-mcp v{version}...")
    url = f"https://registry.npmjs.org/fovux-mcp/{version}"

    # 1. Check metadata
    meta = fetch_json(url)
    repo = meta.get("repository", {})
    repo_url = repo.get("url") if isinstance(repo, dict) else str(repo)
    if "oaslananka/fovux-kit" not in repo_url:
        print(f"Warning: Repository URL {repo_url!r} does not match expected repository.")

    print("npm metadata verified successfully.")

    # 2. npm installation smoke test
    if smoke_test:
        print("Running npm wrapper installation smoke test...")
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            # Write dummy package.json to install locally
            pkg_json = tmp_path / "package.json"
            pkg_json.write_text(json.dumps({"name": "smoke-test-npm"}), encoding="utf-8")

            subprocess.run(  # noqa: S603
                ["npm", "install", f"fovux-mcp@{version}"],  # noqa: S607
                cwd=tmp_path,
                check=True,
            )

            js_entry = tmp_path / "node_modules" / "fovux-mcp" / "bin" / "fovux-mcp.js"
            if not js_entry.exists():
                raise FileNotFoundError(f"npm wrapper bin script not found at {js_entry}")

            # Run CLI via wrapper script
            res = subprocess.run(  # noqa: S603
                ["node", str(js_entry), "--version"],  # noqa: S607
                capture_output=True,
                text=True,
                check=True,
            )
            output = res.stdout.strip()
            print(f"Wrapper reported CLI version: {output}")
            if version not in output:
                raise ValueError(f"Wrapper version {output!r} does not match expected {version}")

            print("npm smoke test passed successfully.")


def verify_vscode_marketplace(version: str) -> None:
    """Verify VS Code Marketplace release extension presence and version match."""
    print(f"Verifying VS Code Marketplace release for fovuxstudiokit v{version}...")
    url = (
        "https://marketplace.visualstudio.com/_apis/public/gallery/extensionquery"
        "?api-version=7.1-preview.1"
    )
    body = {
        "filters": [
            {
                "criteria": [{"filterType": 7, "value": "oaslananka.fovuxstudiokit"}],
                "pageNumber": 1,
                "pageSize": 1,
                "sortBy": 0,
                "sortOrder": 0,
            }
        ],
        "assetTypes": [],
        "flags": 914,
    }
    headers = {"Content-Type": "application/json"}

    res = fetch_json(url, data=json.dumps(body).encode("utf-8"), headers=headers)
    results = res.get("results", [])
    if not results:
        raise ValueError("Empty response from VS Code Marketplace query API.")

    extensions = results[0].get("extensions", [])
    if not extensions:
        raise ValueError("Extension oaslananka.fovuxstudiokit not found on VS Code Marketplace.")

    ext = extensions[0]
    versions = [v.get("version") for v in ext.get("versions", [])]
    print(f"Marketplace versions found: {versions}")
    if version not in versions:
        raise ValueError(f"Version {version} not found in Marketplace (available: {versions}).")

    print("VS Code Marketplace release verified successfully.")


def verify_open_vsx(version: str) -> None:
    """Verify Open VSX release extension presence and version match."""
    print(f"Verifying Open VSX release for fovuxstudiokit v{version}...")
    url = "https://open-vsx.org/api/oaslananka/fovuxstudiokit"

    meta = fetch_json(url)
    current_version = meta.get("version")
    all_versions = meta.get("allVersions", {})

    print(f"Open VSX current version: {current_version}")
    if current_version != version and version not in all_versions:
        raise ValueError(
            f"Version {version} not found in Open VSX "
            f"(current: {current_version}, available: {list(all_versions.keys())})."
        )

    print("Open VSX release verified successfully.")


def run_with_retry(
    func: Callable[..., None],
    *args: Any,  # noqa: ANN401
    retries: int = 15,
    delay: int = 15,
    **kwargs: Any,  # noqa: ANN401
) -> None:
    """Run verification function with a retry mechanism for registry sync delays."""
    for attempt in range(1, retries + 1):
        try:
            func(*args, **kwargs)
            return
        except Exception as e:
            print(f"Verification attempt {attempt}/{retries} failed: {e}")
            if attempt == retries:
                raise
            time.sleep(delay)


def main() -> None:
    """Parse args and execute verified verification steps."""
    parser = argparse.ArgumentParser(description="Verify Fovux monorepo registry publications.")
    parser.add_argument(
        "--channel",
        choices=["all", "python", "npm", "studio"],
        default="all",
        help="Registry channel to verify.",
    )
    parser.add_argument(
        "--skip-smoke",
        action="store_true",
        help="Skip active package installation/smoke testing.",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=15,
        help="Maximum verification query attempts.",
    )
    parser.add_argument(
        "--delay",
        type=int,
        default=15,
        help="Verification sleep interval in seconds.",
    )
    args = parser.parse_args()

    mcp_expected = read_pyproject_version()
    npm_expected = read_npm_wrapper_version()
    studio_expected = read_studio_version()

    print(
        f"Expected Versions - PyPI: {mcp_expected}, npm: {npm_expected}, Studio: {studio_expected}"
    )

    try:
        if args.channel in ["all", "python"]:
            run_with_retry(
                verify_pypi,
                mcp_expected,
                not args.skip_smoke,
                retries=args.retries,
                delay=args.delay,
            )

        if args.channel in ["all", "npm"]:
            run_with_retry(
                verify_npm,
                npm_expected,
                not args.skip_smoke,
                retries=args.retries,
                delay=args.delay,
            )

        if args.channel in ["all", "studio"]:
            run_with_retry(
                verify_vscode_marketplace,
                studio_expected,
                retries=args.retries,
                delay=args.delay,
            )
            run_with_retry(
                verify_open_vsx,
                studio_expected,
                retries=args.retries,
                delay=args.delay,
            )

        print("\nAll registry release verifications passed successfully!")
    except Exception as e:
        print(f"\nVerification FAILED: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
