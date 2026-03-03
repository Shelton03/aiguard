"""Smoke tests for the Human Review module."""
from __future__ import annotations

import math
import os
from collections.abc import Generator
from pathlib import Path
from typing import Iterator

import pytest

from review import (
    CalibrationManager,
    ReviewDecision,
    ReviewQueue,
    ReviewStatus,
    generate_secure_token,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


@pytest.fixture
def queue(tmp_db: Path) -> Iterator[ReviewQueue]:
    q = ReviewQueue(db_path=tmp_db, project="test_proj")
    yield q
    q.close()


@pytest.fixture
def cal(tmp_db: Path) -> Iterator[CalibrationManager]:
    c = CalibrationManager(db_path=tmp_db, project="test_proj")
    yield c
    c.close()


# ---------------------------------------------------------------------------
# Token tests
# ---------------------------------------------------------------------------


def test_token_is_unique():
    tokens = {generate_secure_token() for _ in range(50)}
    assert len(tokens) == 50


def test_token_min_length():
    t = generate_secure_token()
    # URL-safe base64 of 32 bytes → ~43 chars
    assert len(t) >= 40


# ---------------------------------------------------------------------------
# ReviewQueue tests
# ---------------------------------------------------------------------------


def test_enqueue_creates_item(queue: ReviewQueue):
    item = queue.enqueue(
        evaluation_id="eval-1",
        module_type="hallucination",
        model_response="The capital of France is Berlin.",
        raw_score=0.9,
        calibrated_score=0.85,
        trigger_reason="high_raw_score",
    )
    assert item.id
    assert item.review_token
    assert item.status == ReviewStatus.PENDING
    assert item.project_name == "test_proj"


def test_pending_count(queue: ReviewQueue):
    assert queue.pending_count() == 0
    queue.enqueue(
        evaluation_id="e1",
        module_type="hallucination",
        model_response="resp",
        raw_score=0.8,
        calibrated_score=0.75,
        trigger_reason="test",
    )
    assert queue.pending_count() == 1


def test_fetch_by_token(queue: ReviewQueue):
    item = queue.enqueue(
        evaluation_id="e2",
        module_type="adversarial",
        model_response="resp",
        raw_score=0.7,
        calibrated_score=0.65,
        trigger_reason="test",
    )
    fetched = queue.fetch_by_token(item.review_token)
    assert fetched is not None
    assert fetched.id == item.id


def test_fetch_by_unknown_token(queue: ReviewQueue):
    assert queue.fetch_by_token("nonexistent-token") is None


def test_complete_marks_done(queue: ReviewQueue):
    item = queue.enqueue(
        evaluation_id="e3",
        module_type="hallucination",
        model_response="resp",
        raw_score=0.6,
        calibrated_score=0.55,
        trigger_reason="test",
    )
    token = item.review_token
    label = queue.complete(token=token, decision=ReviewDecision.CORRECT, notes="Looks good")
    assert label.decision == ReviewDecision.CORRECT

    # Pending count should now be 0
    assert queue.pending_count() == 0


def test_single_use_token(queue: ReviewQueue):
    item = queue.enqueue(
        evaluation_id="e4",
        module_type="hallucination",
        model_response="resp",
        raw_score=0.6,
        calibrated_score=0.55,
        trigger_reason="test",
    )
    original_token = item.review_token
    queue.complete(token=original_token, decision=ReviewDecision.INCORRECT)

    # Original token must no longer work
    with pytest.raises(ValueError):
        queue.complete(token=original_token, decision=ReviewDecision.CORRECT)


def test_list_all(queue: ReviewQueue):
    for i in range(3):
        queue.enqueue(
            evaluation_id=f"e{i}",
            module_type="hallucination",
            model_response=f"resp{i}",
            raw_score=0.5 + i * 0.1,
            calibrated_score=0.45 + i * 0.1,
            trigger_reason="test",
        )
    items = queue.list_all()
    assert len(items) == 3


# ---------------------------------------------------------------------------
# CalibrationManager tests
# ---------------------------------------------------------------------------


def test_apply_default_scale(cal: CalibrationManager):
    # scale_factor=1.0, raw=0.5 → calibrated ≈ 0.5
    result = cal.apply(0.5)
    assert abs(result - 0.5) < 1e-6


def test_apply_high_score(cal: CalibrationManager):
    result = cal.apply(1.0)
    assert result > 0.99


def test_apply_low_score(cal: CalibrationManager):
    result = cal.apply(0.0)
    assert result < 0.01


def test_apply_output_range(cal: CalibrationManager):
    for raw in [0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0]:
        out = cal.apply(raw)
        assert 0.0 <= out <= 1.0, f"Out of range for raw={raw}: {out}"


def test_increment_review_count(cal: CalibrationManager):
    assert cal.state.reviews_since_last_calibration == 0
    cal.increment_review_count()
    cal.increment_review_count()
    assert cal.state.reviews_since_last_calibration == 2


def test_check_and_update_no_trigger(cal: CalibrationManager):
    # Fresh state — should NOT trigger recalibration
    triggered = cal.check_and_update()
    assert triggered is False


def test_check_and_update_review_count_trigger(cal: CalibrationManager):
    # Simulate 100+ completed reviews
    cal._state.reviews_since_last_calibration = 100
    triggered = cal.check_and_update()
    assert triggered is True
    # Counter should reset
    assert cal.state.reviews_since_last_calibration == 0


def test_recalibration_resets_counter(cal: CalibrationManager):
    cal._state.reviews_since_last_calibration = 200
    cal.check_and_update()
    assert cal.state.reviews_since_last_calibration == 0


# ---------------------------------------------------------------------------
# FastAPI app smoke test
# ---------------------------------------------------------------------------


def test_fastapi_app_created():
    from review.server import create_app
    app = create_app()
    assert app.title == "AIGuard Human Review"


def test_routes_registered():
    from review.server import create_app
    app = create_app()
    paths = {r.path for r in app.routes}
    assert "/" in paths
    assert "/project/{project_name}/dashboard" in paths
    assert "/project/{project_name}/review/{token}" in paths
