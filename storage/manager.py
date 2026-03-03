"""StorageManager resolves backend and provides a unified API."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base_backend import BaseBackend
from .sqlite_backend import SQLiteBackend
from .models import TestCase, Trace, EvaluationResultRecord, ReviewLabel, DatasetRegistry
from .project import resolve_project, load_config

try:
    from .postgres_backend import PostgresBackend
except Exception:  # pragma: no cover
    PostgresBackend = None  # type: ignore


class StorageManager:
    """Backend-agnostic storage entrypoint (singleton per use site)."""

    def __init__(self, root: Optional[Path] = None) -> None:
        self.root = root or Path.cwd()
        self.config = load_config(self.root)
        self.project = resolve_project(self.root)
        self.backend = self._resolve_backend()

    def _resolve_backend(self) -> BaseBackend:
        # Backend resolution priority: env -> config -> default SQLite
        backend = os.getenv("AIGUARD_STORAGE") or self.config.get("storage")
        # CI safety: default to sqlite (in-memory optional)
        if os.getenv("CI") == "true":
            db_path = Path(":memory:") if os.getenv("AIGUARD_SQLITE_MEMORY") == "1" else self.root / ".aiguard" / "aiguard.db"
            return SQLiteBackend(db_path=db_path)

        if backend == "postgres":
            if PostgresBackend is None:
                raise ImportError("psycopg2 required for postgres backend")
            dsn = os.getenv("AIGUARD_PG_DSN") or self.config.get("postgres_dsn") or "host=localhost port=54329 user=postgres password=postgres"
            db_name = f"aiguard_{self.project}"
            return PostgresBackend(dsn=dsn, db_name=db_name)
        # Default SQLite
        db_path = self.root / ".aiguard" / "aiguard.db"
        return SQLiteBackend(db_path=db_path)

    # Public API
    def save_test_case(self, case: TestCase) -> None:
        self.backend.save_test_case(self.project, case)

    def save_trace(self, trace: Trace) -> None:
        self.backend.save_trace(self.project, trace)

    def save_evaluation(self, result: EvaluationResultRecord) -> None:
        self.backend.save_evaluation(self.project, result)

    def save_review(self, review: ReviewLabel) -> None:
        self.backend.save_review(self.project, review)

    def get_evaluations(self, limit: int = 100) -> List[EvaluationResultRecord]:
        return self.backend.get_evaluations(self.project, limit)

    def register_dataset(self, dataset: DatasetRegistry) -> None:
        self.backend.register_dataset(self.project, dataset)

    def list_projects(self) -> List[str]:
        return self.backend.list_projects()

    def delete_project(self, project: Optional[str] = None) -> None:
        target = project or self.project
        self.backend.delete_project(target)

    def export_project(self, project: Optional[str] = None) -> Dict[str, Any]:
        target = project or self.project
        return self.backend.export_project(target)

    def migrate(self, dest_backend: str) -> None:
        # dest_backend in {"sqlite", "postgres"}
        if dest_backend == "sqlite":
            dest = SQLiteBackend(self.root / ".aiguard" / "aiguard.db")
        elif dest_backend == "postgres":
            if PostgresBackend is None:
                raise ImportError("psycopg2 required for postgres backend")
            dsn = os.getenv("AIGUARD_PG_DSN") or self.config.get("postgres_dsn") or "host=localhost port=54329 user=postgres password=postgres"
            db_name = f"aiguard_{self.project}"
            dest = PostgresBackend(dsn=dsn, db_name=db_name)
        else:
            raise ValueError("dest_backend must be 'sqlite' or 'postgres'")

        self.backend.migrate_to(dest, self.project)
