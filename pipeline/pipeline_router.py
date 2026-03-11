"""Pipeline router — wires the SDK dispatcher to the evaluation pipeline.

Calling :func:`start_pipeline` registers a handler with
:func:`aiguard.sdk.dispatcher.register_handler` so that every trace emitted
by :func:`aiguard.chat` flows through:

    SDK dispatcher → TraceQueue → EvaluationQueue → BatchScheduler → EvaluationWorker → Storage

Returns the live pipeline components so callers (CLI, tests) can inspect or
stop them.
"""
from __future__ import annotations

import logging
from typing import NamedTuple, Optional

from config.pipeline_config import PipelineConfig
from pipeline.batch_scheduler import BatchScheduler
from pipeline.evaluation_queue import EvaluationQueue
from pipeline.evaluation_worker import EvaluationWorker
from pipeline.event_models import TraceCreatedEvent
from pipeline.trace_queue import TraceQueue

logger = logging.getLogger(__name__)


class PipelineComponents(NamedTuple):
    """Holds the live pipeline objects returned by :func:`start_pipeline`."""

    trace_queue: TraceQueue
    eval_queue: EvaluationQueue
    worker: EvaluationWorker
    scheduler: BatchScheduler


def start_pipeline(
    config: Optional[PipelineConfig] = None,
    storage_root: Optional[str] = None,
) -> PipelineComponents:
    """Initialise and start the full evaluation pipeline.

    This function is idempotent when called from the CLI or SDK bootstrap:
    subsequent calls create independent pipelines (useful in tests).

    Parameters
    ----------
    config:
        Pipeline configuration.  If *None*, :func:`~config.pipeline_config.load_pipeline_config`
        is called to auto-detect the config.
    storage_root:
        Forwarded to :class:`~pipeline.evaluation_worker.EvaluationWorker` and
        then to :class:`~storage.manager.StorageManager`.

    Returns
    -------
    PipelineComponents
        Named tuple with all live pipeline objects.
    """
    if config is None:
        from config.pipeline_config import load_pipeline_config  # lazy

        config = load_pipeline_config()

    # --- Build pipeline components ------------------------------------
    eval_queue = EvaluationQueue()
    worker = EvaluationWorker(config=config, storage_root=storage_root)
    scheduler = BatchScheduler(config=config, eval_queue=eval_queue, worker=worker)

    # TraceQueue forwards events to EvaluationQueue
    trace_queue = TraceQueue()
    trace_queue.set_consumer(_make_consumer(eval_queue, config.project_id))
    trace_queue.start()

    # Wire SDK dispatcher → TraceQueue
    _register_sdk_handler(trace_queue, config)

    # Start the batch scheduler
    scheduler.start()

    logger.info(
        "Pipeline started — project_id=%r, batch_interval=%.1fh, "
        "hallucination=%s, adversarial=%s",
        config.project_id,
        config.evaluation_batch_interval_hours,
        config.enable_hallucination_eval,
        config.enable_adversarial_eval,
    )
    return PipelineComponents(
        trace_queue=trace_queue,
        eval_queue=eval_queue,
        worker=worker,
        scheduler=scheduler,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _make_consumer(eval_queue: EvaluationQueue, project_id: str):
    """Return a callable that converts TraceCreatedEvent → EvaluationQueue."""
    def consumer(event: TraceCreatedEvent) -> None:
        event.project_id = event.project_id or project_id
        eval_queue.put(event)
        logger.debug(
            "PipelineRouter: queued trace %s for evaluation (queue_size=%d).",
            event.trace_id,
            eval_queue.size(),
        )
    return consumer


def _register_sdk_handler(trace_queue: TraceQueue, config: PipelineConfig) -> None:
    """Register a handler with the SDK dispatcher that feeds the TraceQueue."""
    try:
        from aiguard.sdk.dispatcher import register_handler  # lazy — SDK is optional

        def _sdk_handler(trace_dict: dict) -> None:
            try:
                event = TraceCreatedEvent.from_trace_dict(
                    trace_dict, project_id=config.project_id
                )
                trace_queue.enqueue(event)
            except Exception:
                logger.exception(
                    "PipelineRouter SDK handler: failed to enqueue trace_dict."
                )

        register_handler(_sdk_handler)
        logger.debug("PipelineRouter: SDK dispatcher handler registered.")
    except ImportError:
        logger.warning(
            "PipelineRouter: aiguard.sdk not available — SDK traces will not be "
            "forwarded to the evaluation pipeline."
        )
