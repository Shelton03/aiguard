"""PostgreSQL backend (Docker-hosted) implementation."""
from __future__ import annotations

import json
from typing import Any, Dict, List
from datetime import datetime

try:  # optional dependency
    import psycopg2  # type: ignore
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
except Exception as exc:  # pragma: no cover
    psycopg2 = None  # type: ignore
    ISOLATION_LEVEL_AUTOCOMMIT = None  # type: ignore

from .base_backend import BaseBackend
from .models import TestCase, Trace, EvaluationResultRecord, ReviewLabel, DatasetRegistry


TABLES = [
    """
    CREATE TABLE IF NOT EXISTS test_cases (
        project TEXT NOT NULL,
        id TEXT PRIMARY KEY,
        dataset_name TEXT,
        category TEXT,
        prompt TEXT,
        expected_behavior TEXT,
        ground_truth TEXT,
        context_documents JSONB,
        metadata JSONB
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS traces (
        project TEXT NOT NULL,
        id TEXT PRIMARY KEY,
        timestamp TIMESTAMP,
        model_name TEXT,
        model_version TEXT,
        prompt TEXT,
        response TEXT,
        latency_ms DOUBLE PRECISION,
        tokens_used INTEGER,
        environment TEXT,
        metadata JSONB
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS evaluation_results (
        project TEXT NOT NULL,
        id TEXT PRIMARY KEY,
        trace_id TEXT,
        test_case_id TEXT,
        module TEXT,
        mode TEXT,
        execution_mode TEXT,
        scores JSONB,
        category TEXT,
        risk_level TEXT,
        confidence DOUBLE PRECISION,
        created_at TIMESTAMP
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS review_labels (
        project TEXT NOT NULL,
        id TEXT PRIMARY KEY,
        evaluation_result_id TEXT,
        reviewer_id TEXT,
        label TEXT,
        severity TEXT,
        notes TEXT,
        created_at TIMESTAMP
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS dataset_registry (
        project TEXT NOT NULL,
        id TEXT PRIMARY KEY,
        name TEXT,
        version TEXT,
        source TEXT,
        schema_adapter TEXT,
        installed_at TIMESTAMP
    );
    """,
]


class PostgresBackend(BaseBackend):
    def __init__(self, dsn: str, db_name: str) -> None:
        if psycopg2 is None:
            raise ImportError("psycopg2 is required for PostgresBackend; install psycopg2-binary")
        self.dsn = dsn
        self.db_name = db_name
        self._ensure_database()
        self.init()

    def _connect(self):
        return psycopg2.connect(f"{self.dsn} dbname={self.db_name}")

    def _ensure_database(self):
        # Connect to default db and create target if missing
        with psycopg2.connect(self.dsn) as conn:
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM pg_database WHERE datname=%s", (self.db_name,))
            if cur.fetchone() is None:
                cur.execute(f"CREATE DATABASE {self.db_name};")

    def init(self) -> None:
        with self._connect() as conn:
            cur = conn.cursor()
            for stmt in TABLES:
                cur.execute(stmt)
            conn.commit()

    def save_test_case(self, project: str, case: TestCase) -> None:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO test_cases (project, id, dataset_name, category, prompt, expected_behavior, ground_truth, context_documents, metadata)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (id) DO UPDATE SET
                    dataset_name=EXCLUDED.dataset_name,
                    category=EXCLUDED.category,
                    prompt=EXCLUDED.prompt,
                    expected_behavior=EXCLUDED.expected_behavior,
                    ground_truth=EXCLUDED.ground_truth,
                    context_documents=EXCLUDED.context_documents,
                    metadata=EXCLUDED.metadata
                ;
                """,
                (
                    project,
                    case.id,
                    case.dataset_name,
                    case.category,
                    case.prompt,
                    case.expected_behavior,
                    case.ground_truth,
                    json.dumps(case.context_documents),
                    json.dumps(case.metadata),
                ),
            )
            conn.commit()

    def save_trace(self, project: str, trace: Trace) -> None:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO traces (project, id, timestamp, model_name, model_version, prompt, response, latency_ms, tokens_used, environment, metadata)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (id) DO UPDATE SET
                    timestamp=EXCLUDED.timestamp,
                    model_name=EXCLUDED.model_name,
                    model_version=EXCLUDED.model_version,
                    prompt=EXCLUDED.prompt,
                    response=EXCLUDED.response,
                    latency_ms=EXCLUDED.latency_ms,
                    tokens_used=EXCLUDED.tokens_used,
                    environment=EXCLUDED.environment,
                    metadata=EXCLUDED.metadata
                ;
                """,
                (
                    project,
                    trace.id,
                    trace.timestamp,
                    trace.model_name,
                    trace.model_version,
                    trace.prompt,
                    trace.response,
                    trace.latency_ms,
                    trace.tokens_used,
                    trace.environment,
                    json.dumps(trace.metadata),
                ),
            )
            conn.commit()

    def save_evaluation(self, project: str, result: EvaluationResultRecord) -> None:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO evaluation_results (project, id, trace_id, test_case_id, module, mode, execution_mode, scores, category, risk_level, confidence, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (id) DO UPDATE SET
                    trace_id=EXCLUDED.trace_id,
                    test_case_id=EXCLUDED.test_case_id,
                    module=EXCLUDED.module,
                    mode=EXCLUDED.mode,
                    execution_mode=EXCLUDED.execution_mode,
                    scores=EXCLUDED.scores,
                    category=EXCLUDED.category,
                    risk_level=EXCLUDED.risk_level,
                    confidence=EXCLUDED.confidence,
                    created_at=EXCLUDED.created_at
                ;
                """,
                (
                    project,
                    result.id,
                    result.trace_id,
                    result.test_case_id,
                    result.module,
                    result.mode,
                    result.execution_mode,
                    json.dumps(result.scores),
                    result.category,
                    result.risk_level,
                    result.confidence,
                    result.created_at,
                ),
            )
            conn.commit()

    def save_review(self, project: str, review: ReviewLabel) -> None:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO review_labels (project, id, evaluation_result_id, reviewer_id, label, severity, notes, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (id) DO UPDATE SET
                    evaluation_result_id=EXCLUDED.evaluation_result_id,
                    reviewer_id=EXCLUDED.reviewer_id,
                    label=EXCLUDED.label,
                    severity=EXCLUDED.severity,
                    notes=EXCLUDED.notes,
                    created_at=EXCLUDED.created_at
                ;
                """,
                (
                    project,
                    review.id,
                    review.evaluation_result_id,
                    review.reviewer_id,
                    review.label,
                    review.severity,
                    review.notes,
                    review.created_at,
                ),
            )
            conn.commit()

    def get_evaluations(self, project: str, limit: int = 100) -> List[EvaluationResultRecord]:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, trace_id, test_case_id, module, mode, execution_mode, scores, category, risk_level, confidence, created_at FROM evaluation_results WHERE project=%s ORDER BY created_at DESC LIMIT %s",
                (project, limit),
            )
            rows = cur.fetchall()
            return [
                EvaluationResultRecord(
                    id=r[0],
                    trace_id=r[1],
                    test_case_id=r[2],
                    module=r[3],
                    mode=r[4],
                    execution_mode=r[5],
                    scores=r[6] or {},
                    category=r[7],
                    risk_level=r[8],
                    confidence=float(r[9]),
                    created_at=r[10],
                )
                for r in rows
            ]

    def register_dataset(self, project: str, dataset: DatasetRegistry) -> None:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO dataset_registry (project, id, name, version, source, schema_adapter, installed_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (id) DO UPDATE SET
                    name=EXCLUDED.name,
                    version=EXCLUDED.version,
                    source=EXCLUDED.source,
                    schema_adapter=EXCLUDED.schema_adapter,
                    installed_at=EXCLUDED.installed_at
                ;
                """,
                (
                    project,
                    dataset.id,
                    dataset.name,
                    dataset.version,
                    dataset.source,
                    dataset.schema_adapter,
                    dataset.installed_at,
                ),
            )
            conn.commit()

    def list_projects(self) -> List[str]:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT DISTINCT project FROM test_cases")
            return [r[0] for r in cur.fetchall()]

    def delete_project(self, project: str) -> None:
        with self._connect() as conn:
            cur = conn.cursor()
            for table in ["test_cases", "traces", "evaluation_results", "review_labels", "dataset_registry"]:
                cur.execute(f"DELETE FROM {table} WHERE project=%s", (project,))
            conn.commit()

    def export_project(self, project: str) -> Dict[str, Any]:
        data: Dict[str, Any] = {}
        with self._connect() as conn:
            cur = conn.cursor()
            for table in ["test_cases", "traces", "evaluation_results", "review_labels", "dataset_registry"]:
                cur.execute(f"SELECT * FROM {table} WHERE project=%s", (project,))
                cols = [desc[0] for desc in cur.description]
                data[table] = [dict(zip(cols, row)) for row in cur.fetchall()]
        return data

    def migrate_to(self, dest_backend: BaseBackend, project: str) -> None:
        payload = self.export_project(project)
        for row in payload.get("test_cases", []):
            dest_backend.save_test_case(
                project,
                TestCase(
                    id=row["id"],
                    dataset_name=row["dataset_name"],
                    category=row["category"],
                    prompt=row["prompt"],
                    expected_behavior=row.get("expected_behavior"),
                    ground_truth=row.get("ground_truth"),
                    context_documents=row.get("context_documents") or [],
                    metadata=row.get("metadata") or {},
                ),
            )
        for row in payload.get("traces", []):
            dest_backend.save_trace(
                project,
                Trace(
                    id=row["id"],
                    timestamp=row["timestamp"],
                    model_name=row["model_name"],
                    model_version=row.get("model_version"),
                    prompt=row["prompt"],
                    response=row["response"],
                    latency_ms=row["latency_ms"],
                    tokens_used=row.get("tokens_used"),
                    environment=row["environment"],
                    metadata=row.get("metadata") or {},
                ),
            )
        for row in payload.get("evaluation_results", []):
            dest_backend.save_evaluation(
                project,
                EvaluationResultRecord(
                    id=row["id"],
                    trace_id=row["trace_id"],
                    test_case_id=row["test_case_id"],
                    module=row["module"],
                    mode=row["mode"],
                    execution_mode=row["execution_mode"],
                    scores=row.get("scores") or {},
                    category=row["category"],
                    risk_level=row["risk_level"],
                    confidence=float(row["confidence"]),
                    created_at=row["created_at"],
                ),
            )
        for row in payload.get("review_labels", []):
            dest_backend.save_review(
                project,
                ReviewLabel(
                    id=row["id"],
                    evaluation_result_id=row["evaluation_result_id"],
                    reviewer_id=row["reviewer_id"],
                    label=row["label"],
                    severity=row["severity"],
                    notes=row.get("notes"),
                    created_at=row["created_at"],
                ),
            )
        for row in payload.get("dataset_registry", []):
            dest_backend.register_dataset(
                project,
                DatasetRegistry(
                    id=row["id"],
                    name=row["name"],
                    version=row.get("version"),
                    source=row.get("source"),
                    schema_adapter=row.get("schema_adapter"),
                    installed_at=row["installed_at"],
                ),
            )
