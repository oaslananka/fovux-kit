"""Atomic artifact and export repository tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from fovux.core.run_registry.artifact_repository import ArtifactRepository
from fovux.core.run_registry.database import RegistryDatabase
from fovux.core.run_registry.events import EventStore
from fovux.core.run_registry.metadata import RunMetadataProvider
from fovux.core.run_registry.models import AuditEventRecord


class FailingArtifactAuditStore(EventStore):
    """Force artifact audit persistence to fail inside the export transaction."""

    @staticmethod
    def append_audit_event(
        session: Session,
        *,
        actor: str,
        action: str,
        entity_type: str,
        entity_id: str,
        details: dict[str, object],
    ) -> AuditEventRecord:
        del session, actor, action, entity_type, entity_id, details
        raise RuntimeError("artifact audit unavailable")


def test_export_and_artifact_roll_back_together(tmp_path: Path) -> None:
    database = RegistryDatabase(tmp_path / "runs.db")
    repository = ArtifactRepository(
        database.session_factory,
        metadata_provider=RunMetadataProvider(),
        event_store=FailingArtifactAuditStore(database.session_factory),
    )
    checkpoint = tmp_path / "best.pt"
    checkpoint.write_bytes(b"checkpoint")
    exported = tmp_path / "best.onnx"
    exported.write_bytes(b"export")
    try:
        with pytest.raises(RuntimeError, match="artifact audit unavailable"):
            repository.record_export(
                export_id="exp_tx",
                run_id="run_tx",
                source_checkpoint=checkpoint,
                artifact_path=exported,
                format="onnx",
                duration_s=1.0,
            )

        assert repository.list_exports("run_tx") == []
        assert repository.list_artifacts("run_tx") == []
    finally:
        database.close()
