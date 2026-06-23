"""bundles — tools for reproducibility, support bundles, policy mode, and audit logging."""

from __future__ import annotations

import importlib
import json
import os
import platform
import sys
import tomllib
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import tomli_w

from fovux.config import clear_config_cache, load_config
from fovux.core.doctor import collect_doctor_report
from fovux.core.errors import FovuxError
from fovux.core.paths import FovuxPaths, get_fovux_home
from fovux.core.runs import get_registry
from fovux.core.tooling import tool_event
from fovux.http.tool_proxy import HTTP_TOOL_POLICIES
from fovux.server import mcp


def get_redacted_env() -> dict[str, str]:
    """Return environment variables with sensitive keys redacted."""
    redacted = {}
    for key, val in os.environ.items():
        if any(
            sec in key.lower()
            for sec in ("key", "token", "secret", "password", "pat", "auth", "credential", "jwt")
        ):
            redacted[key] = "[REDACTED]"
        else:
            redacted[key] = val
    return redacted


def redact_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Recursively redact sensitive keys in a dictionary."""
    redacted = {}
    for key, val in data.items():
        if any(
            sec in key.lower()
            for sec in (
                "key",
                "token",
                "secret",
                "password",
                "pat",
                "auth",
                "credential",
                "endpoint",
                "url",
            )
        ):
            redacted[key] = "[REDACTED]"
        elif isinstance(val, dict):
            redacted[key] = redact_dict(val)
        elif isinstance(val, list):
            redacted[key] = [redact_dict(item) if isinstance(item, dict) else item for item in val]
        else:
            redacted[key] = val
    return redacted


def _read_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        return {}
    with config_path.open("rb") as handle:
        return dict(tomllib.load(handle))


@mcp.tool()
def get_policy_status() -> dict[str, Any]:
    """Retrieve the current local security policy status and allowed tools."""
    with tool_event("get_policy_status"):
        config = load_config()
        policy_mode = getattr(config, "policy_mode", "developer").lower()

        # Build list of allowed tools dynamically based on policy mode
        from fovux.http.tool_proxy import available_tools

        allowed_tools = available_tools()

        # Build map of which tools require confirmation
        requires_conf = {}
        for name, policy in HTTP_TOOL_POLICIES.items():
            requires_c = policy.requires_confirmation
            if policy_mode == "safe" and policy.category in (
                "mutating",
                "long_running",
                "destructive",
            ):
                requires_c = True
            elif policy_mode in ("automation", "lab"):
                requires_c = False
            requires_conf[name] = requires_c

        return {
            "policy_mode": policy_mode,
            "allowed_tools": allowed_tools,
            "requires_confirmation": requires_conf,
            "scopes_enforced": policy_mode != "lab",
        }


@mcp.tool()
def set_policy_mode(mode: str) -> dict[str, Any]:
    """Set the local security policy mode (safe, developer, automation, lab)."""
    with tool_event("set_policy_mode", mode=mode):
        mode_lower = mode.lower()
        if mode_lower not in ("safe", "developer", "automation", "lab"):
            raise ValueError(
                f"Invalid policy mode '{mode}'. Mode must be safe, developer, automation, or lab."
            )

        config_path = get_fovux_home() / "config.toml"
        raw = _read_config(config_path)
        fovux = raw.setdefault("fovux", {})
        if not isinstance(fovux, dict):
            fovux = {}
            raw["fovux"] = fovux
        fovux["policy_mode"] = mode_lower

        config_path.parent.mkdir(parents=True, exist_ok=True)
        with config_path.open("wb") as handle:
            tomli_w.dump(raw, handle)
        clear_config_cache()
        return get_policy_status()


@mcp.tool()
def list_audit_events(limit: int = 100, offset: int = 0) -> dict[str, Any]:
    """Retrieve audit event logs from the local database."""
    with tool_event("list_audit_events", limit=limit, offset=offset):
        paths = FovuxPaths(get_fovux_home())
        registry = get_registry(paths.runs_db)
        records = registry.list_audit_events(limit=limit, offset=offset)

        events = []
        for record in records:
            events.append(
                {
                    "id": record.id,
                    "actor": record.actor,
                    "action": record.action,
                    "entity_type": record.entity_type,
                    "entity_id": record.entity_id,
                    "created_at": record.created_at.isoformat() + "Z",
                    "details": json.loads(str(record.details_json or "{}")),
                }
            )
        return {"events": events}


@mcp.tool()
def export_reproducibility_bundle(
    run_id: str,
    destination_path: str | None = None,
) -> dict[str, Any]:
    """Export a reproducibility bundle zip file for a training run."""
    with tool_event("export_reproducibility_bundle", run_id=run_id):
        paths = FovuxPaths(get_fovux_home())
        registry = get_registry(paths.runs_db)
        run_record = registry.get_run(run_id)
        if run_record is None:
            raise FovuxError(f"Run '{run_id}' not found in registry.")

        # Find package versions
        package_versions = {
            "python": sys.version,
            "fovux": getattr(sys.modules.get("fovux"), "__version__", "1.2.0"),
        }
        for pkg_name in ("ultralytics", "onnxruntime", "fastmcp", "pydantic", "sqlalchemy"):
            try:
                pkg = importlib.import_module(pkg_name) if "importlib" in sys.modules else None
                package_versions[pkg_name] = getattr(pkg, "__version__", "unknown")
            except Exception:
                package_versions[pkg_name] = "not_installed"

        # Environment summary
        env_summary = {
            "os": platform.system(),
            "os_release": platform.release(),
            "architecture": platform.machine(),
            "cpu_count": os.cpu_count(),
            "env_vars": get_redacted_env(),
        }

        # Gather metrics
        metrics_records = registry.list_metrics(run_id)
        metrics = []
        for m in metrics_records:
            metrics.append(
                {
                    "epoch": m.epoch,
                    "key": m.metric_key,
                    "value": m.metric_value,
                    "created_at": m.created_at.isoformat() + "Z",
                }
            )

        # Manifest
        manifest = {
            "run_id": run_record.id,
            "status": run_record.status,
            "model": run_record.model,
            "dataset_path": run_record.dataset_path,
            "task": run_record.task,
            "epochs": run_record.epochs,
            "created_at": run_record.created_at.isoformat() + "Z",
            "started_at": (
                run_record.started_at.isoformat() + "Z" if run_record.started_at else None
            ),
            "finished_at": (
                run_record.finished_at.isoformat() + "Z" if run_record.finished_at else None
            ),
            "dataset_fingerprint": run_record.dataset_fingerprint,
            "config_hash": run_record.config_hash,
            "code_version": run_record.code_version,
            "extra": json.loads(str(run_record.extra_json or "{}")),
            "env_summary": env_summary,
            "package_versions": package_versions,
            "metrics": metrics,
        }

        # Model card
        model_card = (
            f"# Fovux Model Card: Run {run_id}\n\n"
            f"Generated on: {datetime.now(UTC).isoformat()}Z\n\n"
            f"## Run Summary\n"
            f"- **Model Architecture:** {run_record.model}\n"
            f"- **Task Type:** {run_record.task}\n"
            f"- **Dataset Path:** {run_record.dataset_path}\n"
            f"- **Dataset Fingerprint:** {run_record.dataset_fingerprint}\n"
            f"- **Epochs:** {run_record.epochs}\n"
            f"- **Status:** {run_record.status}\n\n"
            f"## Package Versions\n"
            f"- Python: {package_versions['python']}\n"
            f"- Fovux: {package_versions['fovux']}\n"
            f"- Ultralytics: {package_versions.get('ultralytics', 'N/A')}\n\n"
            f"## System Info\n"
            f"- Platform: {env_summary['os']} ({env_summary['architecture']})\n"
            f"- CPUs: {env_summary['cpu_count']}\n"
        )

        # Set up output path
        run_dir = paths.run_dir(run_id)
        if destination_path:
            out_zip = Path(destination_path).expanduser().resolve()
        else:
            out_zip = run_dir / f"reproducibility_{run_id}.zip"

        out_zip.parent.mkdir(parents=True, exist_ok=True)

        # Create zip bundle
        with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr("reproducibility_manifest.json", json.dumps(manifest, indent=2))
            zip_file.writestr("model_card.md", model_card)

            # Check if any weights exist in the run directory and include them
            weights_dir = run_dir / "weights"
            if weights_dir.exists() and weights_dir.is_dir():
                for f in weights_dir.glob("*"):
                    if f.is_file():
                        zip_file.write(f, arcname=f"weights/{f.name}")

        return {
            "bundle_path": str(out_zip),
            "size_bytes": out_zip.stat().st_size,
            "manifest": manifest,
        }


@mcp.tool()
def generate_support_bundle(destination_path: str | None = None) -> dict[str, Any]:
    """Generate a redacted support bundle zip file for diagnostics."""
    with tool_event("generate_support_bundle"):
        paths = FovuxPaths(get_fovux_home())
        registry = get_registry(paths.runs_db)

        # 1. Redacted config
        config_toml = paths.config_file
        redacted_config = {}
        if config_toml.exists():
            try:
                config_data = _read_config(config_toml)
                redacted_config = redact_dict(config_data)
            except Exception as exc:
                redacted_config = {"error": f"Failed to read config: {exc}"}

        # 2. OS/runtime summary
        env_summary = {
            "os": platform.system(),
            "os_release": platform.release(),
            "architecture": platform.machine(),
            "cpu_count": os.cpu_count(),
            "env_vars": get_redacted_env(),
        }

        # 3. Doctor report
        doctor_report = {}
        try:
            doctor_report = collect_doctor_report().model_dump(mode="json")
        except Exception as exc:
            doctor_report = {"error": f"Failed to collect doctor report: {exc}"}

        # 4. Package versions
        package_versions = {
            "python": sys.version,
            "fovux": getattr(sys.modules.get("fovux"), "__version__", "1.2.0"),
        }
        for pkg_name in ("ultralytics", "onnxruntime", "fastmcp", "pydantic", "sqlalchemy"):
            try:
                pkg = importlib.import_module(pkg_name) if "importlib" in sys.modules else None
                package_versions[pkg_name] = getattr(pkg, "__version__", "unknown")
            except Exception:
                package_versions[pkg_name] = "not_installed"

        # 5. Failed operations summaries
        failed_ops = []
        try:
            ops = registry.list_operations(limit=100)
            for op in ops:
                if op.status == "failed":
                    failed_ops.append(
                        {
                            "id": op.id,
                            "tool": op.tool,
                            "error_type": op.error_type,
                            "error": op.error,
                            "created_at": op.created_at.isoformat() + "Z"
                            if op.created_at
                            else None,
                        }
                    )
        except Exception as exc:
            failed_ops = [{"error": f"Failed to list failed operations: {exc}"}]

        # Manifest
        manifest = {
            "generated_at": datetime.now(UTC).isoformat() + "Z",
            "redacted_config": redacted_config,
            "env_summary": env_summary,
            "doctor_report": doctor_report,
            "package_versions": package_versions,
            "failed_operations": failed_ops,
        }

        # Set up output path
        if destination_path:
            out_zip = Path(destination_path).expanduser().resolve()
        else:
            out_zip = paths.home / f"support_bundle_{uuid.uuid4().hex[:8]}.zip"

        out_zip.parent.mkdir(parents=True, exist_ok=True)

        # Create zip bundle
        with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr("support_manifest.json", json.dumps(manifest, indent=2))

            # Include recent logs if they exist
            log_file = paths.home / "fovux.log"
            if log_file.exists() and log_file.is_file():
                try:
                    with log_file.open("r", encoding="utf-8") as f:
                        lines = f.readlines()
                    recent_lines = "".join(lines[-500:])
                    zip_file.writestr("recent_logs.txt", recent_lines)
                except Exception as exc:
                    zip_file.writestr("recent_logs.txt", f"Failed to read logs: {exc}")

        return {
            "bundle_path": str(out_zip),
            "size_bytes": out_zip.stat().st_size,
            "manifest": manifest,
        }
