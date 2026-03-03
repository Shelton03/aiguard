"""SQLite backend implementation."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

from .base_backend import BaseBackend
from .models import (
    TestCase,
    Trace,
    EvaluationResultRecord,
    ReviewLabel,
    DatasetRegistry,
    ReviewQueueItem,
    CalibrationState,
)

SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS test_cases (
        project TEXT NOT NULL,
        id TEXT PRIMARY KEY,
        dataset_name TEXT,
        category TEXT,
        prompt TEXT,
        expected_behavior TEXT,
        ground_truth TEXT,
        context_documents TEXT,
        metadata TEXT
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS traces (
        project TEXT NOT NULL,
        id TEXT PRIMARY KEY,
        timestamp TEXT,
        model_name TEXT,
        model_version TEXT,
        prompt TEXT,
        response TEXT,
        latency_ms REAL,
        tokens_used INTEGER,
        environment TEXT,
        metadata TEXT
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
        scores TEXT,
        category TEXT,
        risk_level TEXT,
        confidence REAL,
        created_at TEXT
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
        created_at TEXT
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS review_queue (
        project TEXT NOT NULL,
        id TEXT PRIMARY KEY,
        evaluation_id TEXT,
        module_type TEXT,
        model_response TEXT,
        raw_score REAL,
        calibrated_score REAL,
        trigger_reason TEXT,
        status TEXT,
        review_token TEXT,
        created_at TEXT,
        completed_at TEXT,
        token_used_at TEXT
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS calibration_state (
        project TEXT PRIMARY KEY,
        last_calibration_at TEXT,
        reviews_since_last_calibration INTEGER
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
        installed_at TEXT
    );
    """,
]


class SQLiteBackend(BaseBackend):
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init(self) -> None:
        with self._connect() as conn:
            for stmt in SCHEMA:
                conn.execute(stmt)

    def save_test_case(self, project: str, case: TestCase) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO test_cases (project, id, dataset_name, category, prompt, expected_behavior, ground_truth, context_documents, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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

    def save_trace(self, project: str, trace: Trace) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO traces (project, id, timestamp, model_name, model_version, prompt, response, latency_ms, tokens_used, environment, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project,
                    trace.id,
                    trace.timestamp.isoformat(),
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

    def save_evaluation(self, project: str, result: EvaluationResultRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO evaluation_results (
                    project, id, trace_id, test_case_id, module, mode, execution_mode, scores, category, risk_level, confidence, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    result.created_at.isoformat(),
                ),
            )

    def save_review(self, project: str, review: ReviewLabel) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO review_labels (project, id, evaluation_result_id, reviewer_id, label, severity, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project,
                    review.id,
                    review.evaluation_result_id,
                    review.reviewer_id,
                    review.label,
                    review.severity,
                    review.notes,
                    review.created_at.isoformat(),
                ),
            )

    def save_review_item(self, project: str, item: ReviewQueueItem) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO review_queue (
                    project, id, evaluation_id, module_type, model_response, raw_score, calibrated_score, trigger_reason, status, review_token, created_at, completed_at, token_used_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project,
                    item.id,
                    item.evaluation_id,
                    item.module_type,
                    item.model_response,
                    item.raw_score,
                    item.calibrated_score,
                    item.trigger_reason,
                    item.status,
                    item.review_token,
                    item.created_at.isoformat(),
                    item.completed_at.isoformat() if item.completed_at else None,
                    item.token_used_at.isoformat() if item.token_used_at else None,
                ),
            )

    def get_review_by_token(self, project: str, token: str) -> Optional[ReviewQueueItem]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM review_queue WHERE project = ? AND review_token = ?",
                (project, token),
            ).fetchone()
            if not row:
                return None
            return self._row_to_review_item(row)

    def list_reviews(self, project: str, status: Optional[str] = None, limit: int = 200) -> List[ReviewQueueItem]:
        with self._connect() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM review_queue WHERE project = ? AND status = ? ORDER BY created_at DESC LIMIT ?",
                    (project, status, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM review_queue WHERE project = ? ORDER BY created_at DESC LIMIT ?",
                    (project, limit),
                ).fetchall()
            return [self._row_to_review_item(row) for row in rows]

    def count_reviews(self, project: str, status: Optional[str] = None) -> int:
        with self._connect() as conn:
            if status:
                row = conn.execute(
                    "SELECT COUNT(1) as c FROM review_queue WHERE project = ? AND status = ?",
                    (project, status),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT COUNT(1) as c FROM review_queue WHERE project = ?",
                    (project,),
                ).fetchone()
            return int(row[0]) if row else 0

    def get_evaluations(self, project: str, limit: int = 100) -> List[EvaluationResultRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM evaluation_results WHERE project = ? ORDER BY created_at DESC LIMIT ?",
                (project, limit),
            ).fetchall()
            return [
                EvaluationResultRecord(
                    id=row["id"],
                    trace_id=row["trace_id"],
                    test_case_id=row["test_case_id"],
                    module=row["module"],
                    mode=row["mode"],
                    execution_mode=row["execution_mode"],
                    scores=json.loads(row["scores"] or "{}"),
                    category=row["category"],
                    risk_level=row["risk_level"],
                    confidence=row["confidence"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                )
                for row in rows
            ]

    def _row_to_review_item(self, row: sqlite3.Row) -> ReviewQueueItem:
        return ReviewQueueItem(
            id=row["id"],
            evaluation_id=row["evaluation_id"],
            project_name=row["project"],
            module_type=row["module_type"],
            model_response=row["model_response"],
            raw_score=row["raw_score"],
            calibrated_score=row["calibrated_score"],
            trigger_reason=row["trigger_reason"],
            status=row["status"],
            review_token=row["review_token"],
            created_at=datetime.fromisoformat(row["created_at"]),
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            token_used_at=datetime.fromisoformat(row["token_used_at"]) if row["token_used_at"] else None,
        )

    def register_dataset(self, project: str, dataset: DatasetRegistry) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO dataset_registry (project, id, name, version, source, schema_adapter, installed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project,
                    dataset.id,
                    dataset.name,
                    dataset.version,
                    dataset.source,
                    dataset.schema_adapter,
                    dataset.installed_at.isoformat(),
                ),
            )

    def save_calibration_state(self, project: str, state: CalibrationState) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO calibration_state (project, last_calibration_at, reviews_since_last_calibration)
                VALUES (?, ?, ?)
                """,
                (
                    project,
                    state.last_calibration_at.isoformat() if state.last_calibration_at else None,
                    state.reviews_since_last_calibration,
                ),
            )

    def get_calibration_state(self, project: str) -> CalibrationState:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM calibration_state WHERE project = ?",
                (project,),
            ).fetchone()
            if not row:
                return CalibrationState(project_name=project, last_calibration_at=None, reviews_since_last_calibration=0)
            return CalibrationState(
                project_name=row["project"],
                last_calibration_at=datetime.fromisoformat(row["last_calibration_at"]) if row["last_calibration_at"] else None,
                reviews_since_last_calibration=row["reviews_since_last_calibration"] or 0,
            )

    def list_projects(self) -> List[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT project FROM test_cases UNION SELECT DISTINCT project FROM review_queue"
            ).fetchall()
            return [row[0] for row in rows]

    def delete_project(self, project: str) -> None:
        # Non-destructive policy: we avoid DROP DATABASE. Instead, delete project rows explicitly after confirmation.
        with self._connect() as conn:
            for table in [
                "test_cases",
                "traces",
                "evaluation_results",
                "review_labels",
                "review_queue",
                "calibration_state",
                "dataset_registry",
            ]:
                conn.execute(f"DELETE FROM {table} WHERE project = ?", (project,))

    def export_project(self, project: str) -> Dict[str, Any]:
        data: Dict[str, Any] = {}
        with self._connect() as conn:
            for table in [
                "test_cases",
                "traces",
                "evaluation_results",
                "review_labels",
                "review_queue",
                "calibration_state",
                "dataset_registry",
            ]:
                rows = conn.execute(f"SELECT * FROM {table} WHERE project = ?", (project,)).fetchall()
                data[table] = [dict(row) for row in rows]
        return data

    def migrate_to(self, dest_backend: BaseBackend, project: str) -> None:
        payload = self.export_project(project)
        # Recreate objects for destination backend
        for row in payload.get("test_cases", []):
            dest_backend.save_test_case(
                project,
                TestCase(
                    id=row["id"],
                    dataset_name=row["dataset_name"],
                    category=row["category"],
                    prompt=row["prompt"],
                    expected_behavior=row["expected_behavior"],
                    ground_truth=row["ground_truth"],
                    context_documents=json.loads(row.get("context_documents") or "[]"),
                    metadata=json.loads(row.get("metadata") or "{}"),
                ),
            )
        for row in payload.get("traces", []):
            dest_backend.save_trace(
                project,
                Trace(
                    id=row["id"],
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    model_name=row["model_name"],
                    model_version=row["model_version"],
                    prompt=row["prompt"],
                    response=row["response"],
                    latency_ms=row["latency_ms"],
                    tokens_used=row["tokens_used"],
                    environment=row["environment"],
                    metadata=json.loads(row.get("metadata") or "{}"),
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
                    scores=json.loads(row.get("scores") or "{}"),
                    category=row["category"],
                    risk_level=row["risk_level"],
                    confidence=row["confidence"],
                    created_at=datetime.fromisoformat(row["created_at"]),
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
                    created_at=datetime.fromisoformat(row["created_at"]),
                ),
            )
        for row in payload.get("dataset_registry", []):
            dest_backend.register_dataset(
                project,
                DatasetRegistry(
                    id=row["id"],
                    name=row["name"],
                    version=row["version"],
                    source=row["source"],
                    schema_adapter=row["schema_adapter"],
                    installed_at=datetime.fromisoformat(row["installed_at"]),
                ),
            )

        for row in payload.get("review_queue", []):
            dest_backend.save_review_item(
                project,
                ReviewQueueItem(
                    id=row["id"],
                    evaluation_id=row.get("evaluation_id"),
                    project_name=row["project"],
                    module_type=row.get("module_type"),
                    model_response=row.get("model_response", ""),
                    raw_score=row.get("raw_score") or 0.0,
                    calibrated_score=row.get("calibrated_score"),
                    trigger_reason=row.get("trigger_reason", ""),
                    status=row.get("status", "pending"),
                    review_token=row.get("review_token", ""),
                    created_at=datetime.fromisoformat(row["created_at"]),
                    completed_at=datetime.fromisoformat(row["completed_at"]) if row.get("completed_at") else None,
                    token_used_at=datetime.fromisoformat(row["token_used_at"]) if row.get("token_used_at") else None,
                ),
            )

        for row in payload.get("calibration_state", []):
            dest_backend.save_calibration_state(
                project,
                CalibrationState(
                    project_name=row["project"],
                    last_calibration_at=datetime.fromisoformat(row["last_calibration_at"]) if row.get("last_calibration_at") else None,
                    reviews_since_last_calibration=row.get("reviews_since_last_calibration") or 0,
                ),
            )
