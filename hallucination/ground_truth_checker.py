"""Ground truth checker for hallucination detection when labels are available."""
from __future__ import annotations

from typing import Any, Dict

from .scoring import ScoreBundle, clamp
from .taxonomy import HallucinationCategory


def evaluate_against_ground_truth(response: str, ground_truth: str) -> tuple[ScoreBundle, str]:
    """Simple semantic/substring heuristic for factual correctness.

    This is deterministic and avoids external APIs; can be replaced with richer logic or LLM judge in evaluation mode.
    """
    response_l = response.lower()
    truth_l = ground_truth.lower()

    match = truth_l in response_l
    score = 1.0 if match else 0.0
    category = HallucinationCategory.UNKNOWN if match else HallucinationCategory.FACTUAL_MISMATCH
    bundle = ScoreBundle(factual_score=score, grounding_score=None, consistency_score=None, uncertainty_score=None, overall_risk=clamp(1 - score), confidence=0.6 if match else 0.4)
    reasoning = "Ground truth substring match" if match else "Response does not align with provided ground truth"
    return bundle, category.value + ": " + reasoning
