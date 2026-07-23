"""Filesystem-derived metadata used by registry repositories."""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class RunMetadata:
    """Metadata calculated before a run write transaction starts."""

    dataset_fingerprint: str
    config_hash: str
    code_version: str
    env_summary: str


@dataclass(frozen=True, slots=True)
class ArtifactMetadata:
    """Resolved artifact metadata calculated before persistence."""

    path: str
    sha256: str | None
    size: int | None


class RunMetadataProvider:
    """Calculate best-effort run, lineage, and artifact metadata."""

    def build(
        self,
        *,
        model: str,
        dataset_path: Path,
        task: str,
        epochs: int,
        extra: dict[str, Any] | None = None,
    ) -> RunMetadata:
        """Calculate the established automatic metadata fields for one run."""
        from fovux import __version__ as fovux_version

        try:
            from fovux.core.dataset_config import _find_yolo_yaml

            yaml_path = _find_yolo_yaml(dataset_path)
            dataset_fingerprint = hashlib.sha256(yaml_path.read_bytes()).hexdigest()
        except Exception:
            dataset_fingerprint = hashlib.sha256(
                str(dataset_path.resolve()).encode("utf-8")
            ).hexdigest()

        payload = {
            "model": model,
            "dataset_path": str(dataset_path.resolve()),
            "epochs": epochs,
            "task": task,
            "extra": extra or {},
        }
        config_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode("utf-8")
        ).hexdigest()

        summary: dict[str, Any] = {
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
        }
        try:
            import torch  # type: ignore[import-not-found]

            summary["torch_version"] = torch.__version__
            summary["cuda_available"] = torch.cuda.is_available()
        except ImportError:
            summary["torch_version"] = "not_installed"
            summary["cuda_available"] = False

        return RunMetadata(
            dataset_fingerprint=dataset_fingerprint,
            config_hash=config_hash,
            code_version=fovux_version,
            env_summary=json.dumps(summary),
        )

    def dataset_class_map(self, dataset_path: Path) -> object:
        """Read a YOLO dataset class map with the existing empty fallback."""
        try:
            from fovux.core.dataset_utils import read_yolo_data_yaml

            data = read_yolo_data_yaml(dataset_path)
            return data.get("names", {})
        except Exception:
            return {}

    def artifact_metadata(
        self,
        path: Path,
        *,
        sha256: str | None,
        size: int | None,
    ) -> ArtifactMetadata:
        """Resolve a path and calculate missing file size and digest values."""
        path_str = str(path.resolve())
        if path.exists() and path.is_file():
            if size is None:
                size = path.stat().st_size
            if sha256 is None:
                digest = hashlib.sha256()
                try:
                    with path.open("rb") as handle:
                        for chunk in iter(lambda: handle.read(65536), b""):
                            digest.update(chunk)
                    sha256 = digest.hexdigest()
                except Exception:
                    sha256 = None
        return ArtifactMetadata(path=path_str, sha256=sha256, size=size)


__all__ = ["ArtifactMetadata", "RunMetadata", "RunMetadataProvider"]
