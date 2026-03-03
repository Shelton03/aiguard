"""Data models for the Human Review module."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional


class ReviewStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"


class ReviewDecision(str, Enum):
    CORRECT = "correct"
    INCORRECT = "incorrect"
    UNCERTAIN = "uncertain"


@dataclass
class ReviewQueueItem:
    """A single item waiting for human review."""

    id: str                          # UUID
    evaluation_id: str               # FK → evaluation_results.id
    project_name: str
    module_type: str                 # e.g. "hallucination"
    model_response: str
    raw_score: float
    calibrated_score: float
    trigger_reason: str
    status: ReviewStatus = ReviewStatus.PENDING
    review_token: str = ""           # secure random token (set on creation)
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


@dataclass
class ReviewLabel:
    """A submitted human-review decision."""

    id: str                          # UUID
    queue_item_id: str               # FK → review_queue.id
    project_name: str
    decision: ReviewDecision
    notes: Optional[str]
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class CalibrationState:
    """Per-project calibration state persisted to storage."""

    project_name: str
    last_calibration_at: datetime
    reviews_since_last_calibration: int = 0
    scale_factor: float = 1.0        # logistic scaling parameter
    extra: Dict[str, Any] = field(default_factory=dict)
