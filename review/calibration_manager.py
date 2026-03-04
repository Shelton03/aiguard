"""Calibration manager for periodic score recalibration.

Triggers:
- Every 30 days since last calibration, OR
- When ≥100 completed reviews have accumulated since last calibration.

Calibration logic uses simple logistic scaling::

    calibrated_score = 1 / (1 + exp(-scale_factor * (raw_score - 0.5) * 10))

The scale_factor is stored in calibration_state and updated after each
recalibration cycle.  It does NOT perform model fine-tuning.
"""
from __future__ import annotations

import logging
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .models import CalibrationState


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_RECAL_INTERVAL_DAYS = 30
_RECAL_MIN_REVIEWS = 100


# ---------------------------------------------------------------------------
# CalibrationManager
# ---------------------------------------------------------------------------


class CalibrationManager:
    """
    Per-project calibration manager.

    Usage::

        cal = CalibrationManager(db_path=Path(".aiguard/myproject.db"), project="myproject")
        score = cal.apply(raw_score=0.82)      # → calibrated score
        cal.check_and_update()                 # call after each completed review
    """

    def __init__(self, db_path: Path, project: str) -> None:
        self.project = project
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._migrate()
        self._state = self._load_or_init_state()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _migrate(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS calibration_state (
                project_name                    TEXT PRIMARY KEY,
                last_calibration_at             TEXT NOT NULL,
                reviews_since_last_calibration  INTEGER NOT NULL DEFAULT 0,
                scale_factor                    REAL NOT NULL DEFAULT 1.0
            )
            """
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------

    def _load_or_init_state(self) -> CalibrationState:
        row = self._conn.execute(
            "SELECT * FROM calibration_state WHERE project_name = ?",
            (self.project,),
        ).fetchone()
        if row:
            return CalibrationState(
                project_name=row["project_name"],
                last_calibration_at=datetime.fromisoformat(row["last_calibration_at"]),
                reviews_since_last_calibration=row["reviews_since_last_calibration"],
                scale_factor=row["scale_factor"],
            )
        # Bootstrap a fresh state
        state = CalibrationState(
            project_name=self.project,
            last_calibration_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        self._persist(state)
        return state

    def _persist(self, state: CalibrationState) -> None:
        self._conn.execute(
            """
            INSERT INTO calibration_state
                (project_name, last_calibration_at,
                 reviews_since_last_calibration, scale_factor)
            VALUES (?,?,?,?)
            ON CONFLICT(project_name) DO UPDATE SET
                last_calibration_at            = excluded.last_calibration_at,
                reviews_since_last_calibration = excluded.reviews_since_last_calibration,
                scale_factor                   = excluded.scale_factor
            """,
            (
                state.project_name,
                state.last_calibration_at.isoformat(),
                state.reviews_since_last_calibration,
                state.scale_factor,
            ),
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def state(self) -> CalibrationState:
        return self._state

    def apply(self, raw_score: float) -> float:
        """
        Apply logistic scaling to produce a calibrated score in [0, 1].

        The formula::

            logit_input = scale_factor * (raw_score - 0.5) * 10
            calibrated  = 1 / (1 + exp(-logit_input))
        """
        logit_input = self._state.scale_factor * (raw_score - 0.5) * 10.0
        return 1.0 / (1.0 + math.exp(-logit_input))

    def increment_review_count(self) -> None:
        """Increment the reviews-since-calibration counter and persist."""
        self._state.reviews_since_last_calibration += 1
        self._persist(self._state)

    def check_and_update(self) -> bool:
        """
        Check recalibration triggers and run recalibration if needed.

        Returns True if recalibration was performed, False otherwise.
        """
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        days_since = (now - self._state.last_calibration_at).days
        reviews = self._state.reviews_since_last_calibration

        if days_since >= _RECAL_INTERVAL_DAYS or reviews >= _RECAL_MIN_REVIEWS:
            self._recalibrate(now)
            return True
        return False

    def force_update(self) -> None:
        """Force recalibration immediately, regardless of thresholds."""
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        self._recalibrate(now)

    def _recalibrate(self, now: datetime) -> None:
        """
        Recompute scale_factor based on accumulated review data.

        Simple heuristic: pull recent completed reviews from the DB and
        compute a correction factor from the ratio of human-marked-correct
        to human-marked-incorrect items.  Falls back to scale_factor=1.0
        when there is not enough data.
        """
        new_scale = self._compute_scale_from_labels()
        self._state.scale_factor = new_scale
        self._state.last_calibration_at = now
        self._state.reviews_since_last_calibration = 0
        self._persist(self._state)
        logger.info(
            "Calibration updated for project=%s: scale_factor=%.4f",
            self.project,
            new_scale,
        )

    def _compute_scale_from_labels(self) -> float:
        """
        Derive a new scale factor from the review_labels table.

        Logic:
        - If fraction of 'correct' labels > 0.7  → slightly tighten (scale up)
        - If fraction of 'correct' labels < 0.3  → slightly loosen (scale down)
        - Otherwise                               → keep current scale
        """
        try:
            rows = self._conn.execute(
                """
                SELECT rl.decision, COUNT(*) as cnt
                  FROM review_labels rl
                 WHERE rl.project_name = ?
                 GROUP BY rl.decision
                """,
                (self.project,),
            ).fetchall()
        except sqlite3.OperationalError:
            # review_labels table may not exist in this DB — skip
            return self._state.scale_factor

        counts = {r["decision"]: r["cnt"] for r in rows}
        total = sum(counts.values())
        if total < 10:
            # Not enough data — keep current scale
            return self._state.scale_factor

        correct = counts.get("correct", 0)
        fraction_correct = correct / total

        current = self._state.scale_factor
        if fraction_correct > 0.7:
            new_scale = min(current * 1.05, 3.0)   # tighten: harder to reach high scores
        elif fraction_correct < 0.3:
            new_scale = max(current * 0.95, 0.2)   # loosen: soften the scaling
        else:
            new_scale = current

        return round(new_scale, 6)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "CalibrationManager":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
