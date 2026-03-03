"""Human Review module for AIGuard.

Provides:
- ReviewQueue      — manage the per-project review queue
- Emailer          — send SMTP review-alert emails
- CalibrationManager — periodic score recalibration
- ReviewQueueItem, ReviewLabel, CalibrationState, ReviewDecision, ReviewStatus
"""
from __future__ import annotations

from .calibration_manager import CalibrationManager
from .emailer import Emailer, SMTPConfig, load_smtp_config
from .models import (
    CalibrationState,
    ReviewDecision,
    ReviewLabel,
    ReviewQueueItem,
    ReviewStatus,
)
from .queue import ReviewQueue, generate_secure_token

__all__ = [
    # Core classes
    "ReviewQueue",
    "Emailer",
    "CalibrationManager",
    # Models
    "ReviewQueueItem",
    "ReviewLabel",
    "CalibrationState",
    "ReviewDecision",
    "ReviewStatus",
    # Config / helpers
    "SMTPConfig",
    "load_smtp_config",
    "generate_secure_token",
]
