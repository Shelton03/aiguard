"""Background trace queue.

Implements a single in-process queue backed by :class:`queue.Queue` and a
daemon worker thread.  The worker drains the queue and calls
:func:`~aiguard.sdk.dispatcher.dispatch_trace` for each event.

Design decisions
----------------
* The worker thread is a **daemon** thread so it never prevents the Python
  interpreter from exiting.
* The queue is bounded (``maxsize`` from config) to provide back-pressure: if
  the dispatcher falls behind, new events are **dropped** rather than blocking
  the calling thread.  A dropped-event counter is exposed for observability.
* :func:`enqueue` is **non-blocking** — it uses ``put_nowait`` and silently
  increments the drop counter on :class:`queue.Full`.
* The worker is started lazily on the first call to :func:`enqueue` so the
  import of this module has zero side-effects.
"""
from __future__ import annotations

import logging
import queue
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aiguard.sdk.trace import TraceEvent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Module-level state (private)
# ---------------------------------------------------------------------------

_q: "queue.Queue[TraceEvent]" = queue.Queue(maxsize=10_000)
_worker_thread: threading.Thread | None = None
_worker_lock = threading.Lock()
_dropped_events: int = 0   # approximate; no lock needed for a counter


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def enqueue(trace: "TraceEvent") -> None:
    """Put *trace* onto the queue without blocking the caller.

    If the queue is full the event is dropped and the drop counter is
    incremented.  A warning is logged at most once per 100 drops to avoid
    flooding the log.
    """
    global _dropped_events

    _ensure_worker_running()

    try:
        _q.put_nowait(trace)
    except queue.Full:
        _dropped_events += 1
        if _dropped_events % 100 == 1:
            logger.warning(
                "AIGuard SDK: trace queue is full — %d events dropped so far. "
                "Consider reducing sampling_rate or increasing queue_maxsize.",
                _dropped_events,
            )


def dropped_event_count() -> int:
    """Return the cumulative number of events dropped due to a full queue."""
    return _dropped_events


def queue_size() -> int:
    """Return the approximate number of events currently waiting to be processed."""
    return _q.qsize()


def configure_queue(maxsize: int) -> None:
    """Replace the internal queue with a new one of *maxsize*.

    This must be called **before** the first :func:`enqueue` call (e.g. at
    application start-up when the SDK config is loaded).  It is a no-op if
    the worker thread has already started.
    """
    global _q
    with _worker_lock:
        if _worker_thread is None:
            _q = queue.Queue(maxsize=maxsize)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ensure_worker_running() -> None:
    """Start the background worker thread if it is not yet running."""
    global _worker_thread

    if _worker_thread is not None and _worker_thread.is_alive():
        return

    with _worker_lock:
        # Double-checked locking
        if _worker_thread is not None and _worker_thread.is_alive():
            return

        _worker_thread = threading.Thread(
            target=_worker_loop,
            name="aiguard-sdk-trace-worker",
            daemon=True,
        )
        _worker_thread.start()
        logger.debug("AIGuard SDK: background trace worker started.")


def _worker_loop() -> None:
    """Drain the queue forever, dispatching each event."""
    # Import here to avoid a circular import at module load time
    from aiguard.sdk.dispatcher import dispatch_trace  # noqa: PLC0415

    while True:
        try:
            trace = _q.get(timeout=0.1)
        except queue.Empty:
            continue

        try:
            dispatch_trace(trace)
        except Exception:
            logger.exception(
                "AIGuard SDK: unhandled error while dispatching trace %s",
                getattr(trace, "trace_id", "?"),
            )
        finally:
            _q.task_done()
