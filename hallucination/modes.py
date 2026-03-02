"""Hallucination mode selection utilities."""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional


class ExecutionMode(str, Enum):
    EVALUATION = "evaluation"
    MONITORING = "monitoring"


class HallucinationMode(str, Enum):
    GROUND_TRUTH = "ground_truth"
    CONTEXT_GROUNDED = "context_grounded"
    SELF_CONSISTENCY = "self_consistency"


def detect_execution_mode(metadata: Optional[Dict[str, Any]]) -> ExecutionMode:
    # Simple heuristic: explicit flag in metadata; default to monitoring for safety
    if metadata and metadata.get("execution_mode") == ExecutionMode.EVALUATION.value:
        return ExecutionMode.EVALUATION
    return ExecutionMode.MONITORING


def detect_hallucination_mode(test_case: Dict[str, Any]) -> HallucinationMode:
    if test_case.get("ground_truth") is not None:
        return HallucinationMode.GROUND_TRUTH
    if test_case.get("context_documents"):
        return HallucinationMode.CONTEXT_GROUNDED
    return HallucinationMode.SELF_CONSISTENCY
