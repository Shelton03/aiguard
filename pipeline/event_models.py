"""Core event schemas for the AIGuard pipeline.

These are **data-only** classes.  No business logic lives here.

Event flow:
    SDK  →  TraceCreatedEvent  →  TraceQueue  →  EvaluationQueue
                                                       ↓  (batch)
                                               TraceEvaluatedEvent
                                                       ↓
                                                    Storage
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional


# ---------------------------------------------------------------------------
# Evaluation result sub-schema
# ---------------------------------------------------------------------------

@dataclass
class ModuleEvaluationResult:
    """Output produced by one evaluation module for a single trace.

    Fields
    ------
    label:
        Human-readable classification, e.g. ``"safe"``, ``"hallucinated"``.
    score:
        Numeric risk score in ``[0, 1]``.
    confidence:
        Model/heuristic confidence in ``[0, 1]``.
    explanation:
        Free-text justification — required, never empty.
    raw:
        Original output dict from the module (preserved for debugging).
    """
    label: str
    score: float
    confidence: float
    explanation: str
    raw: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "score": round(self.score, 4),
            "confidence": round(self.confidence, 4),
            "explanation": self.explanation,
            "raw": self.raw,
        }


@dataclass
class EvaluationBundle:
    """Collection of per-module results for one trace."""

    hallucination: Optional[ModuleEvaluationResult] = None
    adversarial: Optional[ModuleEvaluationResult] = None

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        if self.hallucination is not None:
            out["hallucination"] = self.hallucination.to_dict()
        if self.adversarial is not None:
            out["adversarial"] = self.adversarial.to_dict()
        return out

    @property
    def is_empty(self) -> bool:
        return self.hallucination is None and self.adversarial is None


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

@dataclass
class TraceCreatedEvent:
    """Produced by the SDK dispatcher when a new LLM interaction is captured.

    The ``trace`` dict mirrors :class:`~aiguard.sdk.trace.TraceEvent.to_dict()`
    so no extra conversion is needed.
    """
    event_type: Literal["trace_created"] = field(default="trace_created", init=False)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Core payload
    trace_id: str = ""
    project_id: str = ""
    timestamp: str = ""          # ISO-8601 string from SDK
    model: str = ""
    provider: str = "litellm"
    input_messages: List[Dict[str, Any]] = field(default_factory=list)
    output_text: Optional[str] = None
    latency_ms: float = 0.0
    status: str = "ok"
    error: Optional[str] = None
    token_usage: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_trace_dict(
        cls,
        trace_dict: Dict[str, Any],
        *,
        project_id: str = "",
    ) -> "TraceCreatedEvent":
        """Build a :class:`TraceCreatedEvent` from a serialised
        :class:`~aiguard.sdk.trace.TraceEvent` dict."""
        return cls(
            trace_id=trace_dict.get("trace_id", str(uuid.uuid4())),
            project_id=project_id,
            timestamp=trace_dict.get("timestamp", ""),
            model=trace_dict.get("model", ""),
            provider=trace_dict.get("provider", "litellm"),
            input_messages=trace_dict.get("input_messages", []),
            output_text=trace_dict.get("output_text"),
            latency_ms=trace_dict.get("latency_ms", 0.0),
            status=trace_dict.get("status", "ok"),
            error=trace_dict.get("error"),
            token_usage=trace_dict.get("token_usage"),
            metadata=trace_dict.get("metadata", {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "event_id": self.event_id,
            "occurred_at": self.occurred_at.isoformat(),
            "trace_id": self.trace_id,
            "project_id": self.project_id,
            "timestamp": self.timestamp,
            "model": self.model,
            "provider": self.provider,
            "input_messages": self.input_messages,
            "output_text": self.output_text,
            "latency_ms": self.latency_ms,
            "status": self.status,
            "error": self.error,
            "token_usage": self.token_usage,
            "metadata": self.metadata,
        }


@dataclass
class TraceEvaluatedEvent:
    """Produced by evaluation workers after a batch is processed."""
    event_type: Literal["trace_evaluated"] = field(default="trace_evaluated", init=False)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    trace_id: str = ""
    project_id: str = ""
    evaluation: EvaluationBundle = field(default_factory=EvaluationBundle)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "event_id": self.event_id,
            "occurred_at": self.occurred_at.isoformat(),
            "trace_id": self.trace_id,
            "project_id": self.project_id,
            "evaluation": self.evaluation.to_dict(),
        }
