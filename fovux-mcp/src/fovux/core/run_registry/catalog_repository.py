"""Dataset, model, metric, and review-queue persistence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from fovux.core.run_registry.metadata import RunMetadataProvider
from fovux.core.run_registry.models import (
    DatasetRecord,
    MetricRecord,
    ModelRecord,
    ReviewQueueEntry,
    _utcnow_naive,
)


class CatalogRepository:
    """Own lineage catalog, metrics, and active-learning queue records."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        metadata_provider: RunMetadataProvider,
    ) -> None:
        self._session_factory = session_factory
        self._metadata_provider = metadata_provider

    def register_lineage(
        self,
        session: Session,
        *,
        run_id: str,
        model: str,
        dataset_path: Path,
        task: str,
        dataset_fingerprint: str,
    ) -> None:
        """Register dataset and model lineage in the caller's transaction."""
        del run_id  # Reserved for future run-linked catalog constraints.
        class_map = self._metadata_provider.dataset_class_map(dataset_path)
        db_dataset = session.get(DatasetRecord, dataset_fingerprint)
        if db_dataset is None:
            session.merge(
                DatasetRecord(
                    fingerprint=dataset_fingerprint,
                    path=str(dataset_path.resolve()),
                    class_map_json=json.dumps(class_map),
                )
            )

        model_name = Path(model).name
        db_model = session.get(ModelRecord, model_name)
        if db_model is None:
            session.merge(
                ModelRecord(
                    id=model_name,
                    name=model_name,
                    task=task,
                    path=model,
                )
            )

    def get_dataset(self, fingerprint: str) -> DatasetRecord | None:
        """Fetch a dataset record by fingerprint."""
        with self._session_factory() as session:
            return session.get(DatasetRecord, fingerprint)

    def list_datasets(self, limit: int = 100) -> list[DatasetRecord]:
        """List registered datasets."""
        with self._session_factory() as session:
            stmt = select(DatasetRecord).order_by(DatasetRecord.created_at.desc()).limit(limit)
            return list(session.execute(stmt).scalars().all())

    def add_metric(self, run_id: str, epoch: int, key: str, value: float) -> MetricRecord:
        """Record an epoch-level training metric."""
        with self._session_factory() as session:
            record = MetricRecord(
                run_id=run_id,
                epoch=epoch,
                metric_key=key,
                metric_value=value,
                created_at=_utcnow_naive(),
            )
            session.add(record)
            session.commit()
            return record

    def list_metrics(self, run_id: str, limit: int = 1000) -> list[MetricRecord]:
        """List metrics for a run."""
        with self._session_factory() as session:
            stmt = (
                select(MetricRecord)
                .where(MetricRecord.run_id == run_id)
                .order_by(MetricRecord.epoch.asc(), MetricRecord.created_at.asc())
                .limit(limit)
            )
            return list(session.execute(stmt).scalars().all())

    def add_review_queue_entry(
        self,
        entry_id: str,
        image_path: Path,
        dataset_path: Path,
        score: float,
        reason: str,
        predictions: list[dict[str, Any]],
    ) -> ReviewQueueEntry:
        """Add or update an active-learning review queue entry."""
        with self._session_factory() as session:
            record = ReviewQueueEntry(
                id=entry_id,
                image_path=str(image_path.resolve()),
                dataset_path=str(dataset_path.resolve()),
                score=score,
                reason=reason,
                status="pending",
                predictions_json=json.dumps(predictions),
                created_at=_utcnow_naive(),
            )
            session.merge(record)
            session.commit()
            return record

    def get_review_queue_entry(self, entry_id: str) -> ReviewQueueEntry | None:
        """Fetch a review queue entry by ID."""
        with self._session_factory() as session:
            return session.get(ReviewQueueEntry, entry_id)

    def list_review_queue_entries(
        self,
        dataset_path: Path | None = None,
        status: str = "pending",
        limit: int = 100,
    ) -> list[ReviewQueueEntry]:
        """List active-learning review entries ordered by score descending."""
        with self._session_factory() as session:
            stmt = (
                select(ReviewQueueEntry)
                .where(ReviewQueueEntry.status == status)
                .order_by(ReviewQueueEntry.score.desc())
                .limit(limit)
            )
            if dataset_path is not None:
                stmt = stmt.where(ReviewQueueEntry.dataset_path == str(dataset_path.resolve()))
            return list(session.execute(stmt).scalars().all())

    def update_review_queue_status(
        self,
        entry_id: str,
        status: str,
        corrected_labels: list[dict[str, Any]] | None = None,
    ) -> bool:
        """Update review queue status and optional corrected labels."""
        with self._session_factory() as session:
            record = session.get(ReviewQueueEntry, entry_id)
            if record is None:
                return False
            record.status = status
            if corrected_labels is not None:
                record.corrected_labels_json = json.dumps(corrected_labels)
            session.commit()
            return True


__all__ = ["CatalogRepository"]
