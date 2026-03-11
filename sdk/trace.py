"""Trace event schema.

:class:`TraceEvent` is the single unit of data the SDK emits.  It is
intentionally minimal to keep the hot-path overhead low.  All fields are
JSON-serialisable (UUID → str, datetime → ISO-8601 str).

The ``metadata`` dict is the extension point for future fields such as
``tool_calls``, ``retrieved_documents``, ``stream_tokens``, and
``token_usage`` — they can be added without changing the class signature.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional


# Possible life-cycle statuses for a trace
TraceStatus = Literal["ok", "error"]


@dataclass
class TokenUsage:
    """Optional token-count breakdown (populated when available)."""

    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None

    def to_dict(self) -> Dict[str, Optional[int]]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass
class TraceEvent:
    """Minimal, JSON-serialisable record of a single LLM interaction.

    Fields
    ------
    trace_id:
        Globally unique identifier (UUID4 string).
    timestamp:
        UTC datetime when the request was initiated (ISO-8601 string in
        serialised form).
    model:
        Full model identifier as passed to the provider, e.g. ``"gpt-4o"``.
    provider:
        Provider/abstraction layer name, e.g. ``"litellm"``, ``"openai"``.
    input_messages:
        The list of message dicts sent to the model (``[{"role": ..., "content": ...}]``).
    output_text:
        The model's text reply.  ``None`` when ``status == "error"``.
    latency_ms:
        Wall-clock round-trip time in milliseconds.
    status:
        ``"ok"`` on success, ``"error"`` on failure.
    error:
        Exception type + message when ``status == "error"``; ``None`` otherwise.
    token_usage:
        Token breakdown when the provider returns usage data.
    metadata:
        Open-ended dict for any additional context (``temperature``, ``top_p``,
        ``max_tokens``, ``user_id``, ``endpoint_name``, future fields …).
    """

    # --- Required fields (set by client.py) ---
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    model: str = ""
    provider: str = "litellm"
    input_messages: List[Dict[str, Any]] = field(default_factory=list)
    output_text: Optional[str] = None
    latency_ms: float = 0.0
    status: TraceStatus = "ok"
    error: Optional[str] = None

    # --- Optional / extensible fields ---
    token_usage: Optional[TokenUsage] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Return a plain dict that is safe to pass to ``json.dumps``."""
        return {
            "trace_id": self.trace_id,
            "timestamp": self.timestamp.isoformat(),
            "model": self.model,
            "provider": self.provider,
            "input_messages": self.input_messages,
            "output_text": self.output_text,
            "latency_ms": round(self.latency_ms, 3),
            "status": self.status,
            "error": self.error,
            "token_usage": self.token_usage.to_dict() if self.token_usage else None,
            "metadata": self.metadata,
        }

    # ------------------------------------------------------------------
    # Factory helpers
    # ------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        *,
        model: str,
        provider: str,
        input_messages: List[Dict[str, Any]],
        output_text: Optional[str],
        latency_ms: float,
        status: TraceStatus = "ok",
        error: Optional[str] = None,
        token_usage: Optional[TokenUsage] = None,
        **metadata: Any,
    ) -> "TraceEvent":
        """Convenience constructor — keyword-only, no positional surprises."""
        return cls(
            model=model,
            provider=provider,
            input_messages=input_messages,
            output_text=output_text,
            latency_ms=latency_ms,
            status=status,
            error=error,
            token_usage=token_usage,
            metadata=metadata,
        )
