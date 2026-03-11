"""Evaluation queue — accumulates :class:`~pipeline.event_models.TraceCreatedEvent`
objects until :meth:`EvaluationQueue.collect_batch` drains them into a
:class:`~pipeline.batch_scheduler.BatchScheduler` run.

The queue is intentionally simple: a thread-safe list protected by a
:class:`threading.Lock`.  Draining is atomic — events collected in a batch
are removed before the caller processes them, preventing double-evaluation.
"""
from __future__ import annotations

import logging
import threading
from typing import List

from pipeline.event_models import TraceCreatedEvent

logger = logging.getLogger(__name__)


class EvaluationQueue:
    """Thread-safe accumulator for :class:`TraceCreatedEvent` objects.

    Events arrive from :class:`~pipeline.trace_queue.TraceQueue` (via the
    pipeline router consumer callback) and are held until
    :meth:`collect_batch` drains them for evaluation.
    """

    def __init__(self) -> None:
        self._events: List[TraceCreatedEvent] = []
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    def put(self, event: TraceCreatedEvent) -> None:
        """Append *event* to the queue.  Never blocks."""
        with self._lock:
            self._events.append(event)

    # ------------------------------------------------------------------
    # Consumption
    # ------------------------------------------------------------------

    def collect_batch(self, max_size: int = 500) -> List[TraceCreatedEvent]:
        """Atomically drain up to *max_size* events from the queue.

        The drained events are removed from internal storage before being
        returned, ensuring each event is processed exactly once.

        Parameters
        ----------
        max_size:
            Maximum number of events to return in one batch.

        Returns
        -------
        list[TraceCreatedEvent]
            The collected batch, oldest events first.
        """
        with self._lock:
            batch = self._events[:max_size]
            self._events = self._events[max_size:]

        if batch:
            logger.debug(
                "EvaluationQueue: collected batch of %d events (%d remaining).",
                len(batch),
                len(self._events),
            )
        return batch

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def size(self) -> int:
        """Return the current number of queued events."""
        with self._lock:
            return len(self._events)

    def __len__(self) -> int:
        return self.size()
