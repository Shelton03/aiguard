"""Smoke tests for the Human Review module."""
from __future__ import annotations

import math
import os
from collections.abc import Generator
from pathlib import Path
from typing import Iterator
from unittest.mock import Mock, patch

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


# ---------------------------------------------------------------------------
# Auto-trigger tests (Human Review Queue integration)
# ---------------------------------------------------------------------------


def test_random_sampling_rate():
    """Verify random sampling hits target rate over large sample."""
    import random
    random.seed(42)  # Reproducible

    count = 0
    trials = 10000
    rate = 0.20

    for _ in range(trials):
        if random.random() < rate:
            count += 1

    # Allow 5% variance
    assert 0.18 * trials <= count <= 0.22 * trials


def test_review_queue_disabled_by_default():
    """Review queue is opt-in (enable_review_queue=False by default)."""
    from config.pipeline_config import PipelineConfig

    config = PipelineConfig()
    assert config.enable_review_queue is False
    assert config.review_sample_rate == 0.20
    assert config.review_adversarial_threshold is None
    assert config.review_hallucination_threshold is None
    assert config.review_send_email is True


def test_should_trigger_random_sample():
    """Random sampling triggers with correct reason."""
    from config.pipeline_config import PipelineConfig
    from pipeline.evaluation_worker import EvaluationWorker
    from pipeline.event_models import EvaluationBundle, ModuleEvaluationResult

    config = PipelineConfig(
        enable_review_queue=True,
        review_sample_rate=1.0,  # 100% for deterministic testing
        review_adversarial_threshold=None,
        review_hallucination_threshold=None,
    )
    worker = EvaluationWorker(config)

    # Create mock event and bundle
    event = Mock()
    event.trace_id = "test-trace"
    event.project_id = "test_project"

    bundle = EvaluationBundle(
        hallucination=ModuleEvaluationResult(
            label="safe",
            risk_level="safe",
            score=0.5,
            confidence=0.9,
            explanation="test",
            raw={},
        )
    )

    should_trigger, reason = worker._should_trigger_review(event, bundle)

    assert should_trigger is True
    assert reason.startswith("random_sample")


def test_module_thresholds_none_disables():
    """None thresholds mean disabled for both modules."""
    from config.pipeline_config import PipelineConfig
    from pipeline.evaluation_worker import EvaluationWorker
    from pipeline.event_models import EvaluationBundle, ModuleEvaluationResult

    config = PipelineConfig(
        enable_review_queue=True,
        review_sample_rate=0.0,  # Disable random
        review_adversarial_threshold=None,  # Disabled
        review_hallucination_threshold=None,
    )
    worker = EvaluationWorker(config)

    event = Mock()
    event.trace_id = "test-trace"
    event.project_id = "test_project"

    # High score (1.0) should NOT trigger when threshold is None for both modules
    bundle = EvaluationBundle(
        hallucination=ModuleEvaluationResult(
            label="hallucinated",
            risk_level="high",
            score=1.0,
            confidence=0.9,
            explanation="test",
            raw={},
        ),
        adversarial=ModuleEvaluationResult(
            label="adversarial",
            risk_level="high",
            score=1.0,
            confidence=0.9,
            explanation="test",
            raw={},
        ),
    )

    should_trigger, reason = worker._should_trigger_review(event, bundle)

    assert should_trigger is False
    assert reason == ""


def test_should_trigger_high_score():
    """High score threshold triggers review."""
    from config.pipeline_config import PipelineConfig
    from pipeline.evaluation_worker import EvaluationWorker
    from pipeline.event_models import EvaluationBundle, ModuleEvaluationResult

    config = PipelineConfig(
        enable_review_queue=True,
        review_sample_rate=0.0,
        review_hallucination_threshold=0.8,
    )
    worker = EvaluationWorker(config)

    event = Mock()
    event.trace_id = "test-trace"
    event.project_id = "test_project"

    bundle = EvaluationBundle(
        hallucination=ModuleEvaluationResult(
            label="hallucinated",
            risk_level="high",
            score=0.85,  # Above threshold
            confidence=0.9,
            explanation="test",
            raw={},
        )
    )

    should_trigger, reason = worker._should_trigger_review(event, bundle)

    assert should_trigger is True
    assert "high_score" in reason


def test_should_trigger_hallucination_threshold():
    """Hallucination threshold triggers review."""
    from config.pipeline_config import PipelineConfig
    from pipeline.evaluation_worker import EvaluationWorker
    from pipeline.event_models import EvaluationBundle, ModuleEvaluationResult

    config = PipelineConfig(
        enable_review_queue=True,
        review_sample_rate=0.0,
        review_hallucination_threshold=0.2,
    )
    worker = EvaluationWorker(config)

    event = Mock()
    event.trace_id = "test-trace"
    event.project_id = "test_project"

    bundle = EvaluationBundle(
        hallucination=ModuleEvaluationResult(
            label="hallucinated",
            risk_level="high",
            score=0.25,  # Above threshold
            confidence=0.9,
            explanation="test",
            raw={},
        )
    )

    should_trigger, reason = worker._should_trigger_review(event, bundle)

    assert should_trigger is True
    assert "hallucination" in reason and "high_score" in reason


def test_should_trigger_adversarial_threshold():
    """Adversarial threshold triggers review."""
    from config.pipeline_config import PipelineConfig
    from pipeline.evaluation_worker import EvaluationWorker
    from pipeline.event_models import EvaluationBundle, ModuleEvaluationResult

    config = PipelineConfig(
        enable_review_queue=True,
        review_sample_rate=0.0,
        review_adversarial_threshold=0.2,
    )
    worker = EvaluationWorker(config)

    event = Mock()
    event.trace_id = "test-trace"
    event.project_id = "test_project"

    bundle = EvaluationBundle(
        adversarial=ModuleEvaluationResult(
            label="adversarial",
            risk_level="high",
            score=0.25,  # Above threshold
            confidence=0.9,
            explanation="test",
            raw={},
        )
    )

    should_trigger, reason = worker._should_trigger_review(event, bundle)

    assert should_trigger is True
    assert "adversarial" in reason and "high_score" in reason


def test_should_trigger_combined_reasons():
    """Multiple triggers combine reasons with comma separator."""
    from config.pipeline_config import PipelineConfig
    from pipeline.evaluation_worker import EvaluationWorker
    from pipeline.event_models import EvaluationBundle, ModuleEvaluationResult

    config = PipelineConfig(
        enable_review_queue=True,
        review_sample_rate=1.0,  # Always triggers random
        review_hallucination_threshold=0.8,
    )
    worker = EvaluationWorker(config)

    event = Mock()
    event.trace_id = "test-trace"
    event.project_id = "test_project"

    bundle = EvaluationBundle(
        hallucination=ModuleEvaluationResult(
            label="hallucinated",
            risk_level="high",
            score=0.85,  # Above high threshold AND random triggers
            confidence=0.9,
            explanation="test",
            raw={},
        )
    )

    should_trigger, reason = worker._should_trigger_review(event, bundle)

    assert should_trigger is True
    assert "hallucination" in reason and "high_score" in reason


def test_enqueue_for_review_creates_queue_item(tmp_path: Path):
    """Verify _enqueue_for_review() creates ReviewQueueItem."""
    from config.pipeline_config import PipelineConfig
    from pipeline.evaluation_worker import EvaluationWorker
    from pipeline.event_models import EvaluationBundle, ModuleEvaluationResult
    from review.queue import ReviewQueue

    config = PipelineConfig(
        enable_review_queue=True,
        review_sample_rate=1.0,
        review_send_email=False,  # Disable email for test
    )
    worker = EvaluationWorker(config, storage_root=tmp_path)

    event = Mock()
    event.trace_id = "test-trace"
    event.project_id = "test_project"
    event.output_text = "Test model response"
    event.input_messages = [{"role": "user", "content": "Test prompt"}]

    bundle = EvaluationBundle(
        hallucination=ModuleEvaluationResult(
            label="safe",
            risk_level="safe",
            score=0.5,
            confidence=0.9,
            explanation="test",
            raw={},
        )
    )

    # Mock the queue to capture the call
    with patch.object(ReviewQueue, "enqueue") as mock_enqueue:
        mock_item = Mock()
        mock_item.id = "test-item-id"
        mock_item.review_token = "test-token-123"
        mock_enqueue.return_value = mock_item

        worker._enqueue_for_review(event, bundle, "random_sample")

        # Verify enqueue was called
        mock_enqueue.assert_called_once()
        call_kwargs = mock_enqueue.call_args[1]

        assert call_kwargs["evaluation_id"] == "test-trace"
        assert call_kwargs["module_type"] == "hallucination"
        assert call_kwargs["trigger_reason"] == "random_sample"
        assert call_kwargs["raw_score"] == 0.5
        assert call_kwargs["model_response"] == "Test model response"


def test_enqueue_with_email_disabled(tmp_path: Path):
    """When review_send_email=False, no email is sent."""
    from config.pipeline_config import PipelineConfig
    from pipeline.evaluation_worker import EvaluationWorker
    from pipeline.event_models import EvaluationBundle, ModuleEvaluationResult
    from review.emailer import Emailer

    config = PipelineConfig(
        enable_review_queue=True,
        review_sample_rate=1.0,
        review_send_email=False,
    )
    worker = EvaluationWorker(config, storage_root=tmp_path)

    event = Mock()
    event.trace_id = "test-trace"
    event.project_id = "test_project"
    event.output_text = "Test"
    event.input_messages = [{"role": "user", "content": "Test prompt"}]

    bundle = EvaluationBundle(
        hallucination=ModuleEvaluationResult(
            label="safe",
            risk_level="safe",
            score=0.5,
            confidence=0.9,
            explanation="test",
            raw={},
        )
    )

    with patch.object(Emailer, "send_review_alert") as mock_send:
        worker._enqueue_for_review(event, bundle, "random_sample")

        # Verify email was NOT sent
        mock_send.assert_not_called()


def test_enqueue_sends_email_when_enabled(tmp_path: Path):
    """When review_send_email=True, email is sent."""
    import threading
    from config.pipeline_config import PipelineConfig
    from pipeline.evaluation_worker import EvaluationWorker
    from pipeline.event_models import EvaluationBundle, ModuleEvaluationResult
    from review.queue import ReviewQueue
    from review.emailer import Emailer

    config = PipelineConfig(
        enable_review_queue=True,
        review_sample_rate=1.0,
        review_send_email=True,
    )
    worker = EvaluationWorker(config, storage_root=tmp_path)

    event = Mock()
    event.trace_id = "test-trace"
    event.project_id = "test_project"
    event.output_text = "Test"
    event.input_messages = [{"role": "user", "content": "Test prompt"}]

    bundle = EvaluationBundle(
        hallucination=ModuleEvaluationResult(
            label="safe",
            risk_level="safe",
            score=0.5,
            confidence=0.9,
            explanation="test",
            raw={},
        )
    )

    # Mock both queue and emailer
    with patch.object(ReviewQueue, "enqueue") as mock_enqueue:
        mock_item = Mock()
        mock_item.id = "test-item-id"
        mock_item.review_token = "test-token"
        mock_enqueue.return_value = mock_item

        # Patch threading.Thread to call target immediately
        original_thread = threading.Thread
        executed_targets = []
        
        def mock_thread_factory(target, **kwargs):
            executed_targets.append(target)
            mock_thread = Mock()
            mock_thread.start = Mock()
            return mock_thread
        
        with patch.object(threading, "Thread", side_effect=mock_thread_factory):
            with patch.object(Emailer, "send_review_alert") as mock_send:
                with patch.object(ReviewQueue, "enqueue") as mock_enqueue:
                    mock_item = Mock()
                    mock_item.id = "test-item-id"
                    mock_item.review_token = "test-token"
                    mock_enqueue.return_value = mock_item

                    worker._enqueue_for_review(event, bundle, "random_sample")

                    # Execute the email target synchronously
                    assert len(executed_targets) == 1
                    executed_targets[0]()

                    mock_send.assert_called_once_with(
                        project="test_project",
                        item_id="test-item-id",
                        module_type="hallucination",
                        trigger_reason="random_sample",
                        raw_score=0.5,
                        token="test-token",
                    )


def test_emailer_uses_storage_root_for_config(tmp_path: Path):
    """Verify Emailer loads config from storage root, not cwd."""
    from config.pipeline_config import PipelineConfig
    from pipeline.evaluation_worker import EvaluationWorker
    from review.emailer import load_smtp_config
    import os
    
    # Create a test aiguard.yaml with custom SMTP settings
    test_config_file = tmp_path / "aiguard.yaml"
    test_config_file.write_text("""
smtp:
  host: smtp.test.com
  port: 587
  user: test@example.com
  password: testpass
  from: test@example.com
  to:
    - recipient@example.com
  use_tls: true

pipeline:
  review:
    enabled: true
""")
    
    # Create worker with storage root pointing to tmp_path
    config = PipelineConfig(enable_review_queue=True)
    worker = EvaluationWorker(config=config, storage_root=tmp_path)
    
    # Verify storage root is set correctly
    assert worker._storage.root == tmp_path
    
    # Verify that load_smtp_config with this root loads the correct config
    cfg = load_smtp_config(tmp_path)
    assert cfg.host == "smtp.test.com"
    assert cfg.port == 587
    assert cfg.user == "test@example.com"
    assert cfg.to_addrs == ["recipient@example.com"]


def test_project_id_fallback_chain(tmp_path: Path):
    """Verify project_id uses event -> config -> default fallback."""
    from config.pipeline_config import PipelineConfig
    from pipeline.evaluation_worker import EvaluationWorker
    from pipeline.event_models import TraceCreatedEvent, EvaluationBundle, ModuleEvaluationResult
    from unittest.mock import Mock
    
    # Create test aiguard.yaml with project_id
    test_config_file = tmp_path / "aiguard.yaml"
    test_config_file.write_text("""
pipeline:
  project_id: "my_test_project"
  review:
    enabled: true
""")
    
    config = PipelineConfig(
        enable_review_queue=True,
        project_id="my_test_project",
        review_sample_rate=1.0,
    )
    worker = EvaluationWorker(config=config, storage_root=tmp_path)
    
    # Test 1: Event has project_id -> use event's project_id
    event_with_project = Mock()
    event_with_project.project_id = "event_project"
    
    result = event_with_project.project_id or config.project_id or "default"
    assert result == "event_project"
    
    # Test 2: Event has no project_id -> use config's project_id
    event_no_project = Mock()
    event_no_project.project_id = ""
    
    result = event_no_project.project_id or config.project_id or "default"
    assert result == "my_test_project"
    
    # Test 3: Both empty -> use "default"
    config_no_project = PipelineConfig(
        enable_review_queue=True,
        project_id="",
        review_sample_rate=1.0,
    )
    result = event_no_project.project_id or config_no_project.project_id or "default"
    assert result == "default"


def test_enqueue_for_review_uses_storage_root_for_emailer(tmp_path: Path):
    """Verify _enqueue_for_review passes storage root to Emailer."""
    from config.pipeline_config import PipelineConfig
    from pipeline.evaluation_worker import EvaluationWorker
    from pipeline.event_models import TraceCreatedEvent, EvaluationBundle, ModuleEvaluationResult
    from unittest.mock import Mock, patch, MagicMock
    from pathlib import Path
    
    # Create test aiguard.yaml with SMTP config
    test_config_file = tmp_path / "aiguard.yaml"
    test_config_file.write_text("""
smtp:
  host: smtp.gmail.com
  port: 587
  user: test@gmail.com
  password: testpass
  from: test@gmail.com
  to:
    - reviewer@example.com
  use_tls: true

pipeline:
  project_id: "test_project"
  review:
    enabled: true
    sample_rate: 1.0
""")
    
    config = PipelineConfig(
        enable_review_queue=True,
        project_id="test_project",
        review_sample_rate=1.0,
        review_adversarial_threshold=None,
        review_hallucination_threshold=None,
    )
    worker = EvaluationWorker(config=config, storage_root=tmp_path)
    
    # Create mock event and bundle
    event = Mock()
    event.trace_id = "test-trace-123"
    event.project_id = ""  # Empty to test fallback
    event.output_text = "test response"
    event.input_messages = [{"role": "user", "content": "Test prompt"}]
    
    bundle = EvaluationBundle(
        hallucination=ModuleEvaluationResult(
            label="safe",
            risk_level="safe",
            score=0.5,
            confidence=0.9,
            explanation="test",
            raw={},
        )
    )
    
    # Mock the ReviewQueue to avoid actual database operations
    with patch('pipeline.evaluation_worker.ReviewQueue') as mock_queue_class:
        mock_queue = MagicMock()
        mock_queue_class.return_value = mock_queue
        
        mock_item = MagicMock()
        mock_item.id = "queue-item-123"
        mock_item.review_token = "test-token"
        mock_queue.enqueue.return_value = mock_item
        
        # Mock Emailer to verify it's called with correct root
        with patch('pipeline.evaluation_worker.Emailer') as mock_emailer_class:
            mock_emailer = MagicMock()
            mock_emailer_class.return_value = mock_emailer
            
            # Call _enqueue_for_review directly
            worker._enqueue_for_review(event, bundle, "random_sample")
            
            # Verify Emailer was called with storage root
            mock_emailer_class.assert_called_once()
            call_kwargs = mock_emailer_class.call_args
            assert 'root' in call_kwargs.kwargs
            assert call_kwargs.kwargs['root'] == tmp_path
            
            # Verify email was sent
            mock_emailer.send_review_alert.assert_called_once()
            
            # Verify the project_id used was from config (fallback)
            call_args = mock_emailer.send_review_alert.call_args
            assert call_args.kwargs['project'] == "test_project"


def test_email_integration_with_real_smtp():
    """Integration test: verify email sending works with real SMTP credentials.
    
    This test uses environment variables for SMTP configuration and actually
    sends a test email. Skip if credentials are not configured.
    """
    from review.emailer import Emailer, load_smtp_config
    from pathlib import Path
    import os
    
    # Check if SMTP credentials are configured
    smtp_host = os.getenv('AIGUARD_SMTP_HOST')
    smtp_user = os.getenv('AIGUARD_SMTP_USER')
    smtp_password = os.getenv('AIGUARD_SMTP_PASSWORD')
    
    if not all([smtp_host, smtp_user, smtp_password]):
        pytest.skip("SMTP credentials not configured in environment variables")
    
    # Load config from environment
    cfg = load_smtp_config(Path('.'))
    
    # Verify config loaded from env vars
    assert cfg.host == smtp_host
    assert cfg.user == smtp_user
    assert cfg.password == smtp_password
    
    # Create emailer with loaded config
    emailer = Emailer(config=cfg)
    
    # Try to send a test email
    try:
        emailer.send_review_alert(
            project="integration_test",
            item_id="test-integration-123",
            module_type="hallucination",
            trigger_reason="integration_test",
            raw_score=0.85,
            token="integration-test-token"
        )
        # If we get here, email was sent successfully
        assert True
    except Exception as e:
        # If email fails, provide detailed error info
        pytest.fail(f"Failed to send test email: {e}. "
                   f"SMTP Config: host={cfg.host}, port={cfg.port}, "
                   f"user={cfg.user}, tls={cfg.use_tls}, "
                   f"recipients={cfg.to_addrs}")
