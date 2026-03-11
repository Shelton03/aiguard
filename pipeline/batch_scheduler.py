"""Batch scheduler — triggers evaluation on a fixed time interval.

:class:`BatchScheduler` runs a daemon thread that sleeps for
``config.evaluation_batch_interval_hours`` hours, then calls
:meth:`~pipeline.evaluation_queue.EvaluationQueue.collect_batch` and passes
the batch to :class:`~pipeline.evaluation_worker.EvaluationWorker`.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Optional

from config.pipeline_config import PipelineConfig
from pipeline.evaluation_queue import EvaluationQueue
from pipeline.evaluation_worker import EvaluationWorker

logger = logging.getLogger(__name__)


class BatchScheduler:
    """Periodically drains :class:`EvaluationQueue` and runs the worker.

    Parameters
    ----------
    config:
        Pipeline configuration; controls the batch interval and max size.
    eval_queue:
        The queue to drain.
    worker:
        The worker that processes each batch.
    """

    def __init__(
        self,
        config: PipelineConfig,
        eval_queue: EvaluationQueue,
        worker: EvaluationWorker,
    ) -> None:
        self._config = config
        self._eval_queue = eval_queue
        self._worker = worker
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background scheduling thread."""
        if self._thread is not None and self._thread.is_alive():
            logger.debug("BatchScheduler already running.")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="aiguard-batch-scheduler",
            daemon=True,
        )
        self._thread.start()
        interval = self._config.evaluation_batch_interval_hours
        logger.info(
            "BatchScheduler started — will trigger every %.1f hour(s).", interval
        )

    def stop(self) -> None:
        """Signal the scheduling thread to stop after its current sleep."""
        self._stop_event.set()
        logger.info("BatchScheduler stop requested.")

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run(self) -> None:
        interval_seconds = self._config.evaluation_batch_interval_hours * 3600
        while not self._stop_event.is_set():
            # Sleep in short increments so stop() responds quickly.
            elapsed = 0.0
            while elapsed < interval_seconds and not self._stop_event.is_set():
                chunk = min(5.0, interval_seconds - elapsed)
                time.sleep(chunk)
                elapsed += chunk

            if self._stop_event.is_set():
                break

            self._trigger_batch()

    def _trigger_batch(self) -> None:
        batch = self._eval_queue.collect_batch(
            max_size=self._config.max_batch_size
        )
        if not batch:
            logger.debug("BatchScheduler: no events queued — skipping run.")
            return

        logger.info("BatchScheduler: triggering evaluation of %d traces.", len(batch))
        try:
            self._worker.process_batch(batch)
        except Exception:
            logger.exception("BatchScheduler: worker raised an unhandled exception.")
