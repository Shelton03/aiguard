"""Scoring helpers for hallucination evaluation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ScoreBundle:
    factual_score: Optional[float] = None
    grounding_score: Optional[float] = None
    consistency_score: Optional[float] = None
    uncertainty_score: Optional[float] = None
    overall_risk: float = 0.0
    confidence: float = 0.5


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))
