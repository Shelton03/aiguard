"""Evaluation result schema."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class EvaluationResult:
    """Universal result structure returned by test modules."""

    test_type: str
    case_id: str
    success: bool
    risk_score: float
    severity: str
    confidence: float
    category: str
    trace_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_type": self.test_type,
            "case_id": self.case_id,
            "success": self.success,
            "risk_score": self.risk_score,
            "severity": self.severity,
            "confidence": self.confidence,
            "category": self.category,
            "trace_id": self.trace_id,
            "metadata": self.metadata,
        }
