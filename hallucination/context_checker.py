"""Context-grounded hallucination checker for RAG-like scenarios."""
from __future__ import annotations

from typing import Iterable, Tuple

from .scoring import ScoreBundle, clamp
from .taxonomy import HallucinationCategory


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _support_score(response: str, contexts: Iterable[str]) -> Tuple[float, float]:
    """Compute simple support/contradiction heuristics.

    - support: fraction of context passages that overlap with response tokens
    - contradiction: presence of explicit negation conflicts (very coarse)
    Deterministic, no external calls.
    """
    resp = _normalize(response)
    ctxs = [_normalize(c) for c in contexts]
    if not ctxs:
        return 0.0, 0.0

    overlaps = 0
    contradictions = 0
    for ctx in ctxs:
        if any(tok in ctx for tok in resp.split() if len(tok) > 5):
            overlaps += 1
        if "not" in ctx and "not" not in resp and any(tok in ctx for tok in resp.split()):
            contradictions += 1
    support = overlaps / len(ctxs)
    contradiction = contradictions / len(ctxs)
    return support, contradiction


def evaluate_against_context(response: str, context_documents: Iterable[str]) -> tuple[ScoreBundle, str]:
    support, contradiction = _support_score(response, context_documents)
    grounding = clamp(support * (1 - contradiction))
    overall_risk = clamp(1 - grounding)
    category = HallucinationCategory.CONTRADICTION if contradiction > 0.3 else HallucinationCategory.UNSUPPORTED_CLAIM
    reasoning = f"support={support:.2f}, contradiction={contradiction:.2f}"
    bundle = ScoreBundle(
        factual_score=None,
        grounding_score=grounding,
        consistency_score=None,
        uncertainty_score=None,
        overall_risk=overall_risk,
        confidence=0.55 + 0.3 * (grounding - contradiction),
    )
    return bundle, category.value + ": " + reasoning
