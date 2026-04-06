"""Trace dispatcher.

The dispatcher is the **last step** in the SDK pipeline before a trace leaves
the SDK boundary.  Its job is to forward a :class:`~aiguard.sdk.trace.TraceEvent`
to whatever monitoring back-end is configured.

Responsibilities
----------------
* Serialise the trace to a plain dict (``trace.to_dict()``).
* Hand it off to the registered handler(s).
* **Not** perform evaluation, scoring, or storage logic — those belong to the
  existing AIGuard modules.

Extension points
----------------
Handlers can be registered at runtime via :func:`register_handler`.  The
default handler logs the trace at DEBUG level so the SDK is usable out of the
box without any external service.

When the monitoring module is wired in (``aiguard monitor start``), it will
register its own handler here.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict, List, Optional
import urllib.request
import urllib.error

from sdk.trace import TraceEvent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Handler registry
# ---------------------------------------------------------------------------

# A handler is any callable that accepts a plain dict.
TraceHandler = Callable[[Dict[str, Any]], None]

_handlers: List[TraceHandler] = []
_http_ingest_handler: Optional[TraceHandler] = None


def register_handler(handler: TraceHandler) -> None:
    """Register a callable that will be invoked for every dispatched trace.

    Handlers are called in registration order.  Exceptions raised by a handler
    are caught and logged so that one broken handler cannot silence others.

    Example
    -------
    >>> from aiguard.sdk.dispatcher import register_handler
    >>> def my_handler(trace_dict):
    ...     requests.post("https://ingest.example.com/traces", json=trace_dict)
    >>> register_handler(my_handler)
    """
    _handlers.append(handler)


def unregister_handler(handler: TraceHandler) -> None:
    """Remove a previously registered handler (useful in tests)."""
    try:
        _handlers.remove(handler)
    except ValueError:
        pass


def clear_handlers() -> None:
    """Remove all registered handlers (useful in tests)."""
    _handlers.clear()


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def dispatch_trace(trace: TraceEvent) -> None:
    """Serialise *trace* and forward it to all registered handlers.

    This function is called from the background worker thread
    (:mod:`aiguard.sdk.queue`).  It must **never** re-raise an exception
    because that would crash the worker.

    Parameters
    ----------
    trace:
        The :class:`~aiguard.sdk.trace.TraceEvent` to dispatch.
    """
    trace_dict = trace.to_dict()

    if not _handlers:
        # Default behaviour: structured DEBUG log so developers see traces
        # without any setup.
        logger.debug(
            "AIGuard SDK trace | model=%s status=%s latency=%.1fms id=%s",
            trace.model,
            trace.status,
            trace.latency_ms,
            trace.trace_id,
        )
        return

    for handler in _handlers:
        try:
            handler(trace_dict)
        except Exception:
            logger.exception(
                "AIGuard SDK: handler %r raised an exception for trace %s",
                handler,
                trace.trace_id,
            )


# ---------------------------------------------------------------------------
# Built-in handlers (opt-in)
# ---------------------------------------------------------------------------

def _json_log_handler(trace_dict: Dict[str, Any]) -> None:
    """Log the full trace as a single JSON line at INFO level."""
    logger.info("aiguard_trace %s", json.dumps(trace_dict))


def enable_json_logging() -> None:
    """Register the built-in JSON-line log handler.

    Call this once at application start-up to emit a structured JSON line for
    every trace.  Useful when logs are shipped to a log-aggregation service.

    Example
    -------
    >>> from aiguard.sdk.dispatcher import enable_json_logging
    >>> enable_json_logging()
    """
    if _json_log_handler not in _handlers:
        register_handler(_json_log_handler)


def _build_http_ingest_handler(url: str, timeout_s: float) -> TraceHandler:
    def _handler(trace_dict: Dict[str, Any]) -> None:
        payload = json.dumps(trace_dict).encode("utf-8")
        req = urllib.request.Request(
            url=url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                if resp.status >= 400:
                    logger.warning("AIGuard SDK: ingest returned %s", resp.status)
        except urllib.error.HTTPError as exc:
            logger.warning("AIGuard SDK: ingest HTTP error %s", exc.code)
        except Exception as exc:
            logger.warning("AIGuard SDK: ingest failed (%s)", exc)

    return _handler


def enable_http_ingest(url: str, timeout_s: float = 2.0) -> None:
    """Register a handler that POSTs traces to the monitoring API.

    This is used for cross-process ingestion when the SDK and pipeline
    run in separate processes.
    """
    global _http_ingest_handler
    if not url:
        return
    if _http_ingest_handler is None:
        _http_ingest_handler = _build_http_ingest_handler(url, timeout_s)
        register_handler(_http_ingest_handler)
