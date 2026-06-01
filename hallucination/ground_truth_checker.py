"""Ground truth checker for hallucination detection when labels are available."""
from __future__ import annotations

import difflib
import re
import unicodedata
from typing import Iterable, Set

from .scoring import ScoreBundle, clamp
from .taxonomy import HallucinationCategory


_WORD_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "in",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "was",
    "were",
    "with",
}
_MIN_TOKEN_LEN = 2
_KEYWORD_THRESHOLD = 0.6
_FUZZY_THRESHOLD = 0.7


def _normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text or "")
    normalized = normalized.lower()
    normalized = normalized.replace("`", "").replace("*", "").replace("_", "")
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _tokenize(text: str) -> Set[str]:
    tokens = set()
    for token in _WORD_RE.findall(text):
        if len(token) < _MIN_TOKEN_LEN or token in _STOPWORDS:
            continue
        tokens.add(token)
    return tokens


def _keyword_overlap(response: str, ground_truth: str) -> float:
    truth_tokens = _tokenize(ground_truth)
    if not truth_tokens:
        return 0.0
    response_tokens = _tokenize(response)
    matched = truth_tokens.intersection(response_tokens)
    return len(matched) / len(truth_tokens)


def _fuzzy_similarity(response: str, ground_truth: str) -> float:
    if not response and not ground_truth:
        return 1.0
    return difflib.SequenceMatcher(a=response, b=ground_truth).ratio()


def evaluate_against_ground_truth(response: str, ground_truth: str) -> tuple[ScoreBundle, str]:
    """Keyword overlap + fuzzy similarity heuristic for factual correctness.

    Deterministic and avoids external APIs; can be replaced with richer logic or LLM judge in evaluation mode.
    """
    normalized_response = _normalize(response)
    normalized_truth = _normalize(ground_truth)

    overlap = _keyword_overlap(normalized_response, normalized_truth)
    similarity = _fuzzy_similarity(normalized_response, normalized_truth)

    passed = overlap >= _KEYWORD_THRESHOLD or similarity >= _FUZZY_THRESHOLD
    score = max(overlap, similarity)
    category = HallucinationCategory.UNKNOWN if passed else HallucinationCategory.FACTUAL_CONTRADICTION
    confidence = 0.7 if passed else 0.4
    bundle = ScoreBundle(
        factual_score=score,
        grounding_score=None,
        consistency_score=None,
        uncertainty_score=None,
        overall_risk=clamp(1 - score),
        confidence=confidence,
    )
    reasoning = (
        f"keyword_overlap={overlap:.2f} (threshold={_KEYWORD_THRESHOLD}), "
        f"fuzzy_similarity={similarity:.2f} (threshold={_FUZZY_THRESHOLD})"
    )
    return bundle, category.value + ": " + reasoning
