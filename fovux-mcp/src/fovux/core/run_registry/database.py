"""SQLite engine, schema bootstrap, and migrations for the run registry."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from fovux.core.run_registry.models import Base, _serialize_datetime, _utcnow_naive


class RegistryDatabase:
    """Own the SQLite engine, schema bootstrap, migrations, and session factory."""

    def __init__(self, db_path: Path) -> None:
        """Initialize the database while preserving the existing SQLite behavior."""
        self.engine: Engine = create_engine(
            f"sqlite:///{db_path}",
            echo=False,
            poolclass=NullPool,
            connect_args={"check_same_thread": False},
        )
        event.listen(self.engine, "connect", self._set_sqlite_pragmas)
        Base.metadata.create_all(self.engine)
        self._run_migrations()
        self.session_factory: sessionmaker[Session] = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
        )

    @staticmethod
    def _set_sqlite_pragmas(
        dbapi_conn: sqlite3.Connection,
        _connection_record: object,
    ) -> None:
        """Enable the established SQLite durability and concurrency settings."""
        dbapi_conn.execute("PRAGMA journal_mode=WAL")
        dbapi_conn.execute("PRAGMA synchronous=NORMAL")
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    def _run_migrations(self) -> None:
        """Ensure schema migrations are executed, adding columns if needed."""
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS schema_migrations ("
                    "version INTEGER PRIMARY KEY,"
                    "applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
                    ")"
                )
            )
            row = conn.execute(text("SELECT MAX(version) FROM schema_migrations")).fetchone()
            current_version = row[0] if row and row[0] is not None else 0

        if current_version < 1:
            self._apply_migration_1()

    def _apply_migration_1(self) -> None:
        """Add columns to runs table for dataset/config tracking."""
        with self.engine.begin() as conn:
            res = conn.execute(text("PRAGMA table_info(runs)")).fetchall()
            existing_cols = {r[1] for r in res}

            new_cols = {
                "dataset_fingerprint": "TEXT",
                "config_hash": "TEXT",
                "code_version": "TEXT",
                "env_summary": "TEXT",
                "parent_run_id": "TEXT",
            }

            for col_name, col_type in new_cols.items():
                if col_name not in existing_cols:
                    conn.execute(text(f"ALTER TABLE runs ADD COLUMN {col_name} {col_type}"))

            conn.execute(
                text(
                    "INSERT OR IGNORE INTO schema_migrations (version, applied_at) "
                    "VALUES (1, :applied_at)"
                ),
                {"applied_at": _serialize_datetime(_utcnow_naive())},
            )

    def close(self) -> None:
        """Dispose the SQLite engine and release pooled connections."""
        self.engine.dispose()
