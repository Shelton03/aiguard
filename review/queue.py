"""Review queue management — enqueue, fetch, complete."""
from __future__ import annotations

import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
from uuid import uuid4

from .models import ReviewDecision, ReviewLabel, ReviewQueueItem, ReviewStatus


# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------

_TOKEN_BYTES = 32  # 256-bit → 64 hex chars


def generate_secure_token() -> str:
    """Return a cryptographically-secure URL-safe review token."""
    return secrets.token_urlsafe(_TOKEN_BYTES)


# ---------------------------------------------------------------------------
# ReviewQueue
# ---------------------------------------------------------------------------


class ReviewQueue:
    """
    Manages the per-project review queue backed by SQLite.

    Usage::

        queue = ReviewQueue(db_path=Path(".aiguard/myproject.db"), project="myproject")
        item = queue.enqueue(evaluation_id="...", ...)
        queue.complete(token=item.review_token, decision=ReviewDecision.CORRECT)
    """

    def __init__(self, db_path: Path, project: str) -> None:
        self.project = project
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._migrate()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _migrate(self) -> None:
        cur = self._conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS review_queue (
                id                 TEXT PRIMARY KEY,
                evaluation_id      TEXT NOT NULL,
                project_name       TEXT NOT NULL,
                module_type        TEXT NOT NULL,
                model_response     TEXT NOT NULL,
                raw_score          REAL NOT NULL,
                calibrated_score   REAL NOT NULL,
                trigger_reason     TEXT NOT NULL,
                status             TEXT NOT NULL DEFAULT 'pending',
                review_token       TEXT NOT NULL UNIQUE,
                created_at         TEXT NOT NULL,
                completed_at       TEXT
            );

            CREATE TABLE IF NOT EXISTS review_labels (
                id               TEXT PRIMARY KEY,
                queue_item_id    TEXT NOT NULL,
                project_name     TEXT NOT NULL,
                decision         TEXT NOT NULL,
                notes            TEXT,
                created_at       TEXT NOT NULL,
                FOREIGN KEY (queue_item_id) REFERENCES review_queue(id)
            );
            """
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def enqueue(
        self,
        *,
        evaluation_id: str,
        module_type: str,
        model_response: str,
        raw_score: float,
        calibrated_score: float,
        trigger_reason: str,
    ) -> ReviewQueueItem:
        """Add an item to the review queue and return it (with token set)."""
        item = ReviewQueueItem(
            id=str(uuid4()),
            evaluation_id=evaluation_id,
            project_name=self.project,
            module_type=module_type,
            model_response=model_response,
            raw_score=raw_score,
            calibrated_score=calibrated_score,
            trigger_reason=trigger_reason,
            review_token=generate_secure_token(),
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        cur = self._conn.cursor()
        cur.execute(
            """
            INSERT INTO review_queue
                (id, evaluation_id, project_name, module_type, model_response,
                 raw_score, calibrated_score, trigger_reason, status,
                 review_token, created_at, completed_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                item.id,
                item.evaluation_id,
                item.project_name,
                item.module_type,
                item.model_response,
                item.raw_score,
                item.calibrated_score,
                item.trigger_reason,
                item.status.value,
                item.review_token,
                item.created_at.isoformat(),
                None,
            ),
        )
        self._conn.commit()
        return item

    def fetch_by_token(self, token: str) -> Optional[ReviewQueueItem]:
        """Return the queue item for the given token (any status)."""
        row = self._conn.execute(
            "SELECT * FROM review_queue WHERE review_token = ? AND project_name = ?",
            (token, self.project),
        ).fetchone()
        return self._row_to_item(row) if row else None

    def complete(
        self,
        token: str,
        decision: ReviewDecision,
        notes: Optional[str] = None,
    ) -> ReviewLabel:
        """
        Mark a pending queue item as completed, store the review label,
        and **invalidate the token** (single-use).

        Raises ValueError if the token is unknown or already used.
        """
        item = self.fetch_by_token(token)
        if item is None:
            raise ValueError(f"Unknown review token: {token!r}")
        if item.status == ReviewStatus.COMPLETED:
            raise ValueError("Token has already been used.")

        completed_at = datetime.now(timezone.utc).replace(tzinfo=None)

        cur = self._conn.cursor()
        cur.execute(
            """
            UPDATE review_queue
               SET status = 'completed',
                   completed_at = ?,
                   review_token = ?   -- rotate token so it cannot be reused
             WHERE id = ?
            """,
            (completed_at.isoformat(), generate_secure_token(), item.id),
        )

        label = ReviewLabel(
            id=str(uuid4()),
            queue_item_id=item.id,
            project_name=self.project,
            decision=decision,
            notes=notes,
            created_at=completed_at,
        )
        cur.execute(
            """
            INSERT INTO review_labels
                (id, queue_item_id, project_name, decision, notes, created_at)
            VALUES (?,?,?,?,?,?)
            """,
            (
                label.id,
                label.queue_item_id,
                label.project_name,
                label.decision.value,
                label.notes,
                label.created_at.isoformat(),
            ),
        )
        self._conn.commit()
        return label

    def list_pending(self) -> List[ReviewQueueItem]:
        rows = self._conn.execute(
            "SELECT * FROM review_queue WHERE project_name = ? AND status = 'pending' ORDER BY created_at",
            (self.project,),
        ).fetchall()
        return [self._row_to_item(r) for r in rows]

    def list_all(self) -> List[ReviewQueueItem]:
        rows = self._conn.execute(
            "SELECT * FROM review_queue WHERE project_name = ? ORDER BY created_at DESC",
            (self.project,),
        ).fetchall()
        return [self._row_to_item(r) for r in rows]

    def pending_count(self) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) FROM review_queue WHERE project_name = ? AND status = 'pending'",
            (self.project,),
        ).fetchone()
        return row[0]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_item(row: sqlite3.Row) -> ReviewQueueItem:
        return ReviewQueueItem(
            id=row["id"],
            evaluation_id=row["evaluation_id"],
            project_name=row["project_name"],
            module_type=row["module_type"],
            model_response=row["model_response"],
            raw_score=row["raw_score"],
            calibrated_score=row["calibrated_score"],
            trigger_reason=row["trigger_reason"],
            status=ReviewStatus(row["status"]),
            review_token=row["review_token"],
            created_at=datetime.fromisoformat(row["created_at"]),
            completed_at=(
                datetime.fromisoformat(row["completed_at"])
                if row["completed_at"]
                else None
            ),
        )

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "ReviewQueue":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
