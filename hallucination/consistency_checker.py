"""Self-consistency checker for hallucination when no ground truth or context is available."""
from __future__ import annotations

import re
from typing import Tuple, Optional

from .scoring import ScoreBundle, clamp
from .taxonomy import HallucinationCategory
from .language_utils import get_contradiction_keywords
from adversarial.language_detection import detect_language


def _detect_internal_contradiction(text: str, cues_positive: list, cues_negative: list) -> bool:
    if not text:
        return False
    text_l = text.lower()
    return any(neg in text_l and pos in text_l for neg in cues_negative for pos in cues_positive)


def _detect_fabricated_specificity(text: str) -> bool:
    numbers = re.findall(r"\b\d+(?:\.\d+)?\b", text)
    return len(numbers) >= 2


def evaluate_self_consistency(response: str, target_lang: Optional[str] = None) -> Tuple[ScoreBundle, str]:
    if target_lang is None:
        target_lang = detect_language(response)

    keywords = get_contradiction_keywords(target_lang)
    cues_positive = keywords["positive"]
    cues_negative = keywords["negative"]

    has_contradiction = _detect_internal_contradiction(response, cues_positive, cues_negative)
    fabricated = _detect_fabricated_specificity(response)

    consistency_score = clamp(1 - 0.5 * has_contradiction - 0.3 * fabricated)
    uncertainty_score = clamp(0.3 + 0.4 * fabricated + 0.2 * has_contradiction)
    overall_risk = clamp(1 - consistency_score + uncertainty_score * 0.5)

    if has_contradiction:
        category = HallucinationCategory.LOGICAL_INCONSISTENCY
    elif fabricated:
        category = HallucinationCategory.FACTUAL_FABRICATION
    else:
        category = HallucinationCategory.UNKNOWN
    reasoning = f"contradiction={has_contradiction}, fabricated_specificity={fabricated}, lang={target_lang}"
    bundle = ScoreBundle(
        factual_score=None,
        grounding_score=None,
        consistency_score=consistency_score,
        uncertainty_score=uncertainty_score,
        overall_risk=overall_risk,
        confidence=0.5,
    )
    return bundle, category.value + ": " + reasoning
