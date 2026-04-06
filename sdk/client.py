"""SDK Client — the developer-facing entry point.

Public API
----------
::

    import aiguard

    response = aiguard.chat(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Explain quantum computing"}],
    )

``aiguard.chat`` is a thin wrapper around ``litellm.completion``.  It:

1. Checks whether monitoring is enabled and whether this request should be
   sampled.
2. Calls ``litellm.completion`` and measures wall-clock latency.
3. Constructs a :class:`~aiguard.sdk.trace.TraceEvent` from the result.
4. Enqueues the trace for **non-blocking** background processing.
5. Returns the original ``litellm`` response object **unmodified**.

If the model call raises an exception:

* A trace with ``status="error"`` is enqueued (still non-blocking).
* The original exception is re-raised so the caller is not surprised.

The SDK is configured on first import via :func:`configure`.  If no
configuration is provided the SDK reads ``aiguard.yaml`` from the current
working directory and falls back to built-in defaults.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from sdk.config import SdkConfig, load_sdk_config
from sdk.queue import configure_queue, enqueue
from sdk.dispatcher import enable_http_ingest
from sdk.sampling import should_sample
from sdk.trace import TokenUsage, TraceEvent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level config state
# ---------------------------------------------------------------------------

_config: Optional[SdkConfig] = None


def configure(
    *,
    root: Optional[Path] = None,
    enabled: Optional[bool] = None,
    sampling_rate: Optional[float] = None,
    provider: Optional[str] = None,
) -> SdkConfig:
    """Load (or reload) SDK configuration.

    Call this once at application start-up **before** the first :func:`chat`
    call.  Subsequent calls overwrite the global config.

    Parameters
    ----------
    root:
        Directory that contains ``aiguard.yaml``.  Defaults to ``CWD``.
    enabled / sampling_rate / provider:
        Explicit overrides — take priority over ``aiguard.yaml``.

    Returns
    -------
    SdkConfig
        The active configuration after applying all overrides.
    """
    global _config

    _config = load_sdk_config(
        root,
        enabled=enabled,
        sampling_rate=sampling_rate,
        provider=provider,
    )
    configure_queue(_config.queue_maxsize)
    if _config.ingest_url:
        enable_http_ingest(_config.ingest_url, _config.ingest_timeout_s)
    logger.debug(
        "AIGuard SDK configured — enabled=%s sampling_rate=%s provider=%s",
        _config.enabled,
        _config.sampling_rate,
        _config.provider,
    )
    return _config


def get_config() -> SdkConfig:
    """Return the active :class:`~aiguard.sdk.config.SdkConfig`.

    Lazily loads from ``aiguard.yaml`` (CWD) on first access.
    """
    global _config
    if _config is None:
        _config = load_sdk_config()
        configure_queue(_config.queue_maxsize)
        if _config.ingest_url:
            enable_http_ingest(_config.ingest_url, _config.ingest_timeout_s)
    return _config


# ---------------------------------------------------------------------------
# chat()
# ---------------------------------------------------------------------------

def chat(
    model: str,
    messages: List[Dict[str, Any]],
    *,
    # Optional metadata captured in the trace but NOT forwarded to the model
    user_id: Optional[str] = None,
    endpoint_name: Optional[str] = None,
    # Everything else is forwarded verbatim to litellm.completion
    **kwargs: Any,
) -> Any:
    """Call an LLM via LiteLLM and emit a trace event for monitoring.

    Parameters
    ----------
    model:
        LiteLLM model identifier, e.g. ``"gpt-4o"``, ``"claude-3-5-sonnet"``,
        ``"ollama/llama3"``.
    messages:
        OpenAI-style message list: ``[{"role": "user", "content": "..."}]``.
    user_id:
        Optional end-user identifier stored in trace metadata.
    endpoint_name:
        Optional label for the calling endpoint (e.g. ``"chat_api"``).
    **kwargs:
        Any additional keyword arguments are forwarded directly to
        ``litellm.completion`` (e.g. ``temperature``, ``max_tokens``).

    Returns
    -------
    litellm.ModelResponse
        The response object returned by LiteLLM, **unmodified**.

    Raises
    ------
    Exception
        Any exception raised by ``litellm.completion`` is re-raised after a
        trace with ``status="error"`` has been enqueued.
    """
    cfg = get_config()

    # ------------------------------------------------------------------
    # Fast-path: monitoring disabled → pure LiteLLM pass-through
    # ------------------------------------------------------------------
    if not cfg.enabled:
        return _call_litellm(model, messages, **kwargs)

    # ------------------------------------------------------------------
    # Sampling gate
    # ------------------------------------------------------------------
    trace_this_request = should_sample(cfg.sampling_rate)

    if not trace_this_request:
        return _call_litellm(model, messages, **kwargs)

    # ------------------------------------------------------------------
    # Instrumented path
    # ------------------------------------------------------------------
    # Snapshot metadata from kwargs (do not pop — forward everything)
    meta: Dict[str, Any] = {}
    for key in ("temperature", "top_p", "max_tokens"):
        if key in kwargs:
            meta[key] = kwargs[key]
    if user_id is not None:
        meta["user_id"] = user_id
    if endpoint_name is not None:
        meta["endpoint_name"] = endpoint_name

    t_start = time.perf_counter()

    try:
        response = _call_litellm(model, messages, **kwargs)
    except Exception as exc:
        latency_ms = (time.perf_counter() - t_start) * 1_000
        _enqueue_error_trace(
            model=model,
            provider=cfg.provider,
            messages=messages,
            latency_ms=latency_ms,
            exc=exc,
            metadata=meta,
        )
        raise

    latency_ms = (time.perf_counter() - t_start) * 1_000

    # ------------------------------------------------------------------
    # Build trace — synchronously but minimal work
    # ------------------------------------------------------------------
    output_text = _extract_output_text(response)
    token_usage = _extract_token_usage(response)

    trace = TraceEvent.create(
        model=model,
        provider=cfg.provider,
        input_messages=messages,
        output_text=output_text,
        latency_ms=latency_ms,
        status="ok",
        token_usage=token_usage,
        **meta,
    )

    # ------------------------------------------------------------------
    # Non-blocking enqueue — returns immediately
    # ------------------------------------------------------------------
    enqueue(trace)

    # ------------------------------------------------------------------
    # Return the unmodified model response
    # ------------------------------------------------------------------
    return response


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _call_litellm(
    model: str,
    messages: List[Dict[str, Any]],
    **kwargs: Any,
) -> Any:
    """Thin wrapper so ``litellm`` import is isolated in one place."""
    try:
        from litellm import completion  # type: ignore[import]
    except ImportError as exc:
        raise ImportError(
            "litellm is required for aiguard.chat(). "
            'Install it with: pip install "aiguard[sdk]" or pip install litellm'
        ) from exc

    return completion(model=model, messages=messages, **kwargs)


def _extract_output_text(response: Any) -> Optional[str]:
    """Best-effort extraction of the first choice text from a LiteLLM response."""
    try:
        return response.choices[0].message.content
    except (AttributeError, IndexError, TypeError):
        try:
            # Streaming or dict response fallback
            return str(response)
        except Exception:
            return None


def _extract_token_usage(response: Any) -> Optional[TokenUsage]:
    """Extract token usage from a LiteLLM response if present."""
    try:
        usage = response.usage
        return TokenUsage(
            prompt_tokens=getattr(usage, "prompt_tokens", None),
            completion_tokens=getattr(usage, "completion_tokens", None),
            total_tokens=getattr(usage, "total_tokens", None),
        )
    except AttributeError:
        return None


def _enqueue_error_trace(
    *,
    model: str,
    provider: str,
    messages: List[Dict[str, Any]],
    latency_ms: float,
    exc: Exception,
    metadata: Dict[str, Any],
) -> None:
    """Create and enqueue a trace with ``status="error"``."""
    trace = TraceEvent.create(
        model=model,
        provider=provider,
        input_messages=messages,
        output_text=None,
        latency_ms=latency_ms,
        status="error",
        error=f"{type(exc).__name__}: {exc}",
        **metadata,
    )
    enqueue(trace)
