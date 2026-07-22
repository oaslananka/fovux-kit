"""Run lineage, dataset, and export serialization service."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, cast

from fovux.core.runs import RunRegistry
from fovux.http.services.errors import ServiceError
from fovux.http.services.runs import default_registry_provider

RegistryProvider = Callable[[], RunRegistry]


class LineageService:
    """Query lineage-ledger resources without an HTTP transport."""

    def __init__(self, registry_provider: RegistryProvider = default_registry_provider) -> None:
        """Initialize with an injectable registry provider."""
        self._registry_provider = registry_provider

    def run_lineage(self, run_id: str) -> dict[str, Any]:
        """Return run metadata, artifacts, exports, and lifecycle events."""
        registry = self._registry_provider()
        record = registry.get_run(run_id)
        if record is None:
            raise ServiceError(404, f"Run {run_id} not found.")
        artifacts = registry.list_artifacts(run_id)
        exports = registry.list_exports(run_id)
        events = registry.list_run_events(run_id)
        return {
            "run_id": record.id,
            "dataset_path": record.dataset_path,
            "dataset_fingerprint": record.dataset_fingerprint,
            "config_hash": record.config_hash,
            "code_version": record.code_version,
            "env_summary": _decode_optional_mapping(record.env_summary),
            "parent_run_id": record.parent_run_id,
            "artifacts": [
                {
                    "id": artifact.id,
                    "type": artifact.type,
                    "path": artifact.path,
                    "sha256": artifact.sha256,
                    "size": artifact.size,
                    "created_at": artifact.created_at.isoformat() if artifact.created_at else None,
                }
                for artifact in artifacts
            ],
            "exports": [_export_payload(export, include_run_id=False) for export in exports],
            "events": [_run_event_payload(event, include_extra=False) for event in events],
        }

    def run_events(self, run_id: str) -> list[dict[str, Any]]:
        """Return all lifecycle and audit events for one run."""
        registry = self._registry_provider()
        if registry.get_run(run_id) is None:
            raise ServiceError(404, f"Run {run_id} not found.")
        return [
            _run_event_payload(event, include_extra=True)
            for event in registry.list_run_events(run_id)
        ]

    def list_datasets(self) -> list[dict[str, Any]]:
        """Return registered dataset records."""
        return [_dataset_payload(record) for record in self._registry_provider().list_datasets()]

    def get_dataset(self, fingerprint: str) -> dict[str, Any]:
        """Return one dataset record by fingerprint."""
        record = self._registry_provider().get_dataset(fingerprint)
        if record is None:
            raise ServiceError(404, f"Dataset {fingerprint} not found.")
        return _dataset_payload(record)

    def list_exports(self) -> list[dict[str, Any]]:
        """Return all recorded exports."""
        return [
            _export_payload(record, include_run_id=True)
            for record in self._registry_provider().list_exports()
        ]


def _decode_optional_mapping(value: object) -> dict[str, Any] | None:
    if not value:
        return None
    decoded = json.loads(cast(str, value))
    return cast(dict[str, Any], decoded) if isinstance(decoded, dict) else None


def _decode_mapping(value: object) -> dict[str, Any]:
    if not value:
        return {}
    decoded = json.loads(cast(str, value))
    return cast(dict[str, Any], decoded) if isinstance(decoded, dict) else {}


def _dataset_payload(record: Any) -> dict[str, Any]:  # noqa: ANN401
    return {
        "fingerprint": record.fingerprint,
        "path": record.path,
        "class_map": _decode_mapping(record.class_map_json),
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }


def _export_payload(record: Any, *, include_run_id: bool) -> dict[str, Any]:  # noqa: ANN401
    payload: dict[str, Any] = {
        "id": record.id,
        "source_checkpoint": record.source_checkpoint,
        "artifact_path": record.artifact_path,
        "format": record.format,
        "duration_s": record.duration_s,
        "validation_result": _decode_optional_mapping(record.validation_result_json),
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }
    if include_run_id:
        payload["run_id"] = record.run_id
    return payload


def _run_event_payload(record: Any, *, include_extra: bool) -> dict[str, Any]:  # noqa: ANN401
    payload: dict[str, Any] = {
        "id": record.id,
        "event_type": record.event_type,
        "from_status": record.from_status,
        "to_status": record.to_status,
        "message": record.message,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }
    if include_extra:
        payload["extra"] = _decode_optional_mapping(record.extra_json)
    return payload
