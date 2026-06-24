#!/usr/bin/env python3
"""Post-release verification script for PyPI, npm, and VS Code extension registries."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class EvidenceRecorder:
    """Collect machine-readable release verification evidence."""

    path: Path
    expected_versions: dict[str, str]
    steps: list[dict[str, object]] = field(default_factory=list)

    def record(
        self,
        *,
        channel: str,
        check: str,
        status: str,
        details: dict[str, object] | None = None,
    ) -> None:
        """Append one verification step result."""
        self.steps.append(
            {
                "channel": channel,
                "check": check,
                "status": status,
                "details": details or {},
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
        )

    def write(self) -> None:
        """Write the evidence file."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": 1,
            "expected_versions": self.expected_versions,
            "steps": self.steps,
            "summary": {
                "passed": sum(step["status"] == "passed" for step in self.steps),
                "failed": sum(step["status"] == "failed" for step in self.steps),
            },
        }
        self.path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )


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


def fetch_json(
    url: str, data: bytes | None = None, headers: dict[str, str] | None = None
) -> Any:  # noqa: ANN401
    """Fetch JSON from a URL with custom headers and method."""
    if not url.startswith("https://"):
        raise ValueError(f"URL must start with https://: {url}")
    req = urllib.request.Request(url, data=data, headers=headers or {})  # noqa: S310
    with urllib.request.urlopen(req, timeout=30) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def _run(
    command: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run a fixed verification command and capture useful failure output."""
    try:
        return subprocess.run(  # noqa: S603
            command,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            check=check,
        )
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()[-2000:]
        stdout = (exc.stdout or "").strip()[-2000:]
        raise RuntimeError(
            f"Command {command[0]!r} failed with exit code {exc.returncode}. "
            f"stdout={stdout!r} stderr={stderr!r}"
        ) from exc


def _uv_bin() -> str:
    """Return uv executable path or raise a clear release-smoke error."""
    uv = shutil.which("uv")
    if not uv:
        raise RuntimeError(
            "uv is required for PyPI smoke tests so verification does not depend on ensurepip. "
            "Install uv or add astral-sh/setup-uv before running this script."
        )
    return uv


def _python_for_uv_venv(uv: str) -> str:
    """Return a uv-discovered Python interpreter that can build isolated smoke venvs."""
    desired = f"{sys.version_info.major}.{sys.version_info.minor}"
    for candidate_cmd in (
        [uv, "python", "find", desired],
        [uv, "python", "find"],
    ):
        try:
            candidate = _run(candidate_cmd).stdout.strip()
        except RuntimeError:
            continue
        if candidate:
            return candidate
    return sys.executable


def _venv_bin_dir(venv: Path) -> Path:
    """Return a virtualenv executable directory for the current platform."""
    if os.name == "nt":
        return venv / "Scripts"
    return venv / "bin"


def _venv_cli(venv: Path, command_name: str) -> Path:
    """Return a virtualenv command path for the current platform."""
    suffix = ".exe" if os.name == "nt" else ""
    return _venv_bin_dir(venv) / f"{command_name}{suffix}"


def _venv_env(venv: Path) -> dict[str, str]:
    """Return an environment that makes uv target the isolated virtualenv."""
    env = os.environ.copy()
    env["VIRTUAL_ENV"] = str(venv)
    env["PATH"] = f"{_venv_bin_dir(venv)}{os.pathsep}{env.get('PATH', '')}"
    return env


def verify_pypi(version: str, smoke_test: bool, evidence: EvidenceRecorder) -> None:
    """Verify PyPI package presence and run isolation smoke tests."""
    print(f"Verifying PyPI release for fovux-mcp v{version}...")
    url = f"https://pypi.org/pypi/fovux-mcp/{version}/json"

    try:
        meta = fetch_json(url)
        info = meta.get("info", {})
        project_urls = info.get("project_urls", {})
        repo_url = project_urls.get("Homepage") or project_urls.get("Repository") or ""
        if "oaslananka/fovux-kit" not in repo_url:
            print(
                f"Warning: Repository URL {repo_url!r} does not match expected repository."
            )

        description = info.get("description", "")
        if "oaslananka/fovux-kit" not in description:
            raise ValueError(
                "PyPI description is missing repository homepage reference."
            )

        evidence.record(
            channel="python",
            check="pypi_package",
            status="passed",
            details={"package": "fovux-mcp", "version": version, "url": url},
        )
        print("PyPI metadata verified successfully.")
    except Exception as exc:
        evidence.record(
            channel="python",
            check="pypi_package",
            status="failed",
            details={"package": "fovux-mcp", "version": version, "error": str(exc)},
        )
        raise

    if smoke_test:
        print("Running PyPI package installation smoke test with uv...")
        try:
            uv = _uv_bin()
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = Path(tmpdir)
                venv = tmp_path / ".venv"
                smoke_python = _python_for_uv_venv(uv)
                _run([uv, "venv", "--python", smoke_python, str(venv)], cwd=tmp_path)
                _run(
                    [uv, "pip", "install", f"fovux-mcp=={version}"],
                    cwd=tmp_path,
                    env=_venv_env(venv),
                )

                fovux_bin = _venv_cli(venv, "fovux-mcp")
                if not fovux_bin.exists():
                    raise FileNotFoundError(
                        f"fovux-mcp executable not found at {fovux_bin}"
                    )

                res = _run([str(fovux_bin), "--version"])
                output = res.stdout.strip()
                print(f"Installed fovux-mcp CLI output: {output}")
                evidence.record(
                    channel="python",
                    check="pypi_cli_smoke",
                    status="passed",
                    details={"command": "fovux-mcp --version", "output": output},
                )
                if version not in output:
                    raise ValueError(
                        f"Installed version {output!r} does not match expected {version}"
                    )
                evidence.record(
                    channel="python",
                    check="python_version_parity",
                    status="passed",
                    details={"expected": version, "actual_output": output},
                )

                doctor = _run([str(fovux_bin), "doctor"], check=False)
                evidence.record(
                    channel="python",
                    check="pypi_doctor_probe",
                    status="passed",
                    details={
                        "exit_code": doctor.returncode,
                        "stdout_tail": doctor.stdout[-1000:],
                        "stderr_tail": doctor.stderr[-1000:],
                    },
                )
                print("PyPI smoke test passed successfully.")
        except Exception as exc:
            evidence.record(
                channel="python",
                check="pypi_cli_smoke",
                status="failed",
                details={"package": "fovux-mcp", "version": version, "error": str(exc)},
            )
            raise


def verify_npm(version: str, smoke_test: bool, evidence: EvidenceRecorder) -> None:
    """Verify npm package presence and run isolation wrapper smoke tests."""
    print(f"Verifying npm release for fovux-mcp v{version}...")
    url = f"https://registry.npmjs.org/fovux-mcp/{version}"

    try:
        meta = fetch_json(url)
        repo = meta.get("repository", {})
        repo_url = repo.get("url") if isinstance(repo, dict) else str(repo)
        if "oaslananka/fovux-kit" not in repo_url:
            print(
                f"Warning: Repository URL {repo_url!r} does not match expected repository."
            )
        evidence.record(
            channel="npm",
            check="npm_wrapper",
            status="passed",
            details={"package": "fovux-mcp", "version": version, "url": url},
        )
        print("npm metadata verified successfully.")
    except Exception as exc:
        evidence.record(
            channel="npm",
            check="npm_wrapper",
            status="failed",
            details={"package": "fovux-mcp", "version": version, "error": str(exc)},
        )
        raise

    if smoke_test:
        print("Running npm wrapper installation smoke test...")
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = Path(tmpdir)
                pkg_json = tmp_path / "package.json"
                pkg_json.write_text(
                    json.dumps({"name": "smoke-test-npm"}), encoding="utf-8"
                )

                _run(["npm", "install", f"fovux-mcp@{version}"], cwd=tmp_path)  # noqa: S607

                js_entry = (
                    tmp_path / "node_modules" / "fovux-mcp" / "bin" / "fovux-mcp.js"
                )
                if not js_entry.exists():
                    raise FileNotFoundError(
                        f"npm wrapper bin script not found at {js_entry}"
                    )

                res = _run(["node", str(js_entry), "--version"])  # noqa: S607
                output = res.stdout.strip()
                print(f"Wrapper reported CLI version: {output}")
                evidence.record(
                    channel="npm",
                    check="npm_cli_smoke",
                    status="passed",
                    details={
                        "command": "node node_modules/fovux-mcp/bin/fovux-mcp.js --version",
                        "output": output,
                    },
                )
                if version not in output:
                    raise ValueError(
                        f"Wrapper version {output!r} does not match expected {version}"
                    )
                evidence.record(
                    channel="npm",
                    check="npm_version_parity",
                    status="passed",
                    details={"expected": version, "actual_output": output},
                )

                print("npm smoke test passed successfully.")
        except Exception as exc:
            evidence.record(
                channel="npm",
                check="npm_cli_smoke",
                status="failed",
                details={"package": "fovux-mcp", "version": version, "error": str(exc)},
            )
            raise


def verify_vscode_marketplace(version: str, evidence: EvidenceRecorder) -> None:
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

    try:
        res = fetch_json(url, data=json.dumps(body).encode("utf-8"), headers=headers)
        results = res.get("results", [])
        if not results:
            raise ValueError("Empty response from VS Code Marketplace query API.")

        extensions = results[0].get("extensions", [])
        if not extensions:
            raise ValueError(
                "Extension oaslananka.fovuxstudiokit not found on VS Code Marketplace."
            )

        ext = extensions[0]
        versions = [v.get("version") for v in ext.get("versions", [])]
        print(f"Marketplace versions found: {versions}")
        if version not in versions:
            raise ValueError(
                f"Version {version} not found in Marketplace (available: {versions})."
            )

        evidence.record(
            channel="studio",
            check="vscode_marketplace_package",
            status="passed",
            details={
                "extension": "oaslananka.fovuxstudiokit",
                "version": version,
                "versions": versions,
            },
        )
        print("VS Code Marketplace release verified successfully.")
    except Exception as exc:
        evidence.record(
            channel="studio",
            check="vscode_marketplace_package",
            status="failed",
            details={
                "extension": "oaslananka.fovuxstudiokit",
                "version": version,
                "error": str(exc),
            },
        )
        raise


def verify_open_vsx(version: str, evidence: EvidenceRecorder) -> None:
    """Verify Open VSX release extension presence and version match."""
    print(f"Verifying Open VSX release for fovuxstudiokit v{version}...")
    url = "https://open-vsx.org/api/oaslananka/fovuxstudiokit"

    try:
        meta = fetch_json(url)
        current_version = meta.get("version")
        all_versions = meta.get("allVersions", {})

        print(f"Open VSX current version: {current_version}")
        if current_version != version and version not in all_versions:
            raise ValueError(
                f"Version {version} not found in Open VSX "
                f"(current: {current_version}, available: {list(all_versions.keys())})."
            )

        evidence.record(
            channel="studio",
            check="open_vsx_package",
            status="passed",
            details={
                "extension": "oaslananka.fovuxstudiokit",
                "version": version,
                "current_version": str(current_version),
            },
        )
        print("Open VSX release verified successfully.")
    except Exception as exc:
        evidence.record(
            channel="studio",
            check="open_vsx_package",
            status="failed",
            details={
                "extension": "oaslananka.fovuxstudiokit",
                "version": version,
                "error": str(exc),
            },
        )
        raise


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


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Verify Fovux monorepo registry publications."
    )
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
    parser.add_argument(
        "--evidence-path",
        type=Path,
        default=Path("out/registry-verification-report.json"),
        help="Path for machine-readable verification evidence.",
    )
    return parser.parse_args()


def main() -> None:
    """Parse args and execute verified verification steps."""
    args = parse_args()

    mcp_expected = read_pyproject_version()
    npm_expected = read_npm_wrapper_version()
    studio_expected = read_studio_version()
    evidence = EvidenceRecorder(
        path=args.evidence_path,
        expected_versions={
            "pypi": mcp_expected,
            "npm": npm_expected,
            "studio": studio_expected,
        },
    )

    print(
        f"Expected Versions - PyPI: {mcp_expected}, npm: {npm_expected}, Studio: {studio_expected}"
    )

    exit_code = 0
    try:
        if args.channel in ["all", "python"]:
            run_with_retry(
                verify_pypi,
                mcp_expected,
                not args.skip_smoke,
                evidence,
                retries=args.retries,
                delay=args.delay,
            )

        if args.channel in ["all", "npm"]:
            run_with_retry(
                verify_npm,
                npm_expected,
                not args.skip_smoke,
                evidence,
                retries=args.retries,
                delay=args.delay,
            )

        if args.channel in ["all", "studio"]:
            run_with_retry(
                verify_vscode_marketplace,
                studio_expected,
                evidence,
                retries=args.retries,
                delay=args.delay,
            )
            run_with_retry(
                verify_open_vsx,
                studio_expected,
                evidence,
                retries=args.retries,
                delay=args.delay,
            )

        print("\nAll registry release verifications passed successfully!")
    except Exception as e:
        print(f"\nVerification FAILED: {e}", file=sys.stderr)
        exit_code = 1
    finally:
        evidence.write()
        print(f"Wrote registry verification evidence to {evidence.path}")

    if exit_code:
        sys.exit(exit_code)


if __name__ == "__main__":
    main()
