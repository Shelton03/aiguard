"""Uncertainty estimation heuristics for hallucination risk."""
from __future__ import annotations

import re
from typing import Tuple

from .scoring import ScoreBundle, clamp
from .taxonomy import HallucinationCategory


def estimate_uncertainty(response: str) -> Tuple[ScoreBundle, str]:
    lower = response.lower()
    hedge_tokens = ["might", "could", "possibly", "uncertain", "unsure", "likely"]
    overconf_tokens = ["definitely", "certainly", "guaranteed", "always", "never"]

    hedges = sum(lower.count(tok) for tok in hedge_tokens)
    overconf = sum(lower.count(tok) for tok in overconf_tokens)

    numbers = re.findall(r"\b\d+(?:\.\d+)?\b", response)
    fabricated_specificity = len(numbers) > 3 and hedges == 0

    uncertainty_score = clamp(0.5 + 0.1 * hedges - 0.2 * overconf - 0.1 * fabricated_specificity)
    overall_risk = clamp(1 - uncertainty_score + 0.2 * fabricated_specificity)

    category = HallucinationCategory.OVERCONFIDENT if overconf > hedges else HallucinationCategory.UNKNOWN
    reasoning = f"hedges={hedges}, overconf={overconf}, fabricated_specificity={fabricated_specificity}"
    bundle = ScoreBundle(
        factual_score=None,
        grounding_score=None,
        consistency_score=None,
        uncertainty_score=uncertainty_score,
        overall_risk=overall_risk,
        confidence=0.5,
    )
    return bundle, category.value + ": " + reasoning
