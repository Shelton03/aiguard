"""Trace queue — receives :class:`~pipeline.event_models.TraceCreatedEvent` objects
from the SDK dispatcher and forwards them to the evaluation queue.

The abstraction uses a :class:`TraceQueueBackend` protocol so the in-process
``queue.Queue`` can be swapped for Redis / Kafka without changing call-sites.
"""
from __future__ import annotations

import logging
import queue
import threading
from typing import Callable, Optional, Protocol, runtime_checkable

from pipeline.event_models import TraceCreatedEvent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Backend protocol — swap in Redis/Kafka by implementing this
# ---------------------------------------------------------------------------

@runtime_checkable
class TraceQueueBackend(Protocol):
    """Minimal interface that any trace queue backend must satisfy."""

    def put(self, event: TraceCreatedEvent) -> None: ...
    def get(self, timeout: float) -> TraceCreatedEvent: ...


# ---------------------------------------------------------------------------
# In-process backend
# ---------------------------------------------------------------------------

class InProcessBackend:
    """Simple ``queue.Queue``-based backend.  Thread-safe, zero dependencies."""

    def __init__(self, maxsize: int = 50_000) -> None:
        self._q: queue.Queue[TraceCreatedEvent] = queue.Queue(maxsize=maxsize)

    def put(self, event: TraceCreatedEvent) -> None:
        try:
            self._q.put_nowait(event)
        except queue.Full:
            logger.warning(
                "TraceQueue full — dropping event %s", event.trace_id
            )

    def get(self, timeout: float = 0.1) -> TraceCreatedEvent:
        return self._q.get(timeout=timeout)


# ---------------------------------------------------------------------------
# TraceQueue
# ---------------------------------------------------------------------------

class TraceQueue:
    """Receives trace events and forwards them to a downstream consumer.

    The consumer (typically :class:`~pipeline.pipeline_router.PipelineRouter`)
    is registered via :meth:`set_consumer`.  Forwarding happens on a
    background daemon thread so :meth:`enqueue` never blocks the caller.

    Parameters
    ----------
    backend:
        An object satisfying :class:`TraceQueueBackend`.  Defaults to
        :class:`InProcessBackend`.
    """

    def __init__(self, backend: Optional[TraceQueueBackend] = None) -> None:
        self._backend = backend or InProcessBackend()
        self._consumer: Optional[Callable[[TraceCreatedEvent], None]] = None
        self._worker: Optional[threading.Thread] = None
        self._started = False
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def set_consumer(self, fn: Callable[[TraceCreatedEvent], None]) -> None:
        """Register the function called for each dequeued event."""
        self._consumer = fn

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def enqueue(self, event: TraceCreatedEvent) -> None:
        """Put *event* on the queue.  Non-blocking."""
        self._ensure_started()
        self._backend.put(event)

    def start(self) -> None:
        """Explicitly start the background forwarding thread."""
        self._ensure_started()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _ensure_started(self) -> None:
        if self._started:
            return
        with self._lock:
            if self._started:
                return
            self._worker = threading.Thread(
                target=self._forward_loop,
                name="aiguard-trace-queue-worker",
                daemon=True,
            )
            self._worker.start()
            self._started = True
            logger.debug("TraceQueue forwarding worker started.")

    def _forward_loop(self) -> None:
        while True:
            try:
                event = self._backend.get(timeout=0.1)
            except queue.Empty:
                continue

            if self._consumer is None:
                logger.debug("TraceQueue: no consumer registered, event %s dropped.", event.trace_id)
                continue

            try:
                self._consumer(event)
            except Exception:
                logger.exception(
                    "TraceQueue: consumer raised for event %s", event.trace_id
                )
