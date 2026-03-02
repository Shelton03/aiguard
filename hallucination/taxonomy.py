"""Basic taxonomy labels for hallucination outcomes."""
from __future__ import annotations

from enum import Enum


class HallucinationCategory(str, Enum):
    FACTUAL_MISMATCH = "factual_mismatch"
    UNSUPPORTED_CLAIM = "unsupported_claim"
    CONTRADICTION = "contradiction"
    SELF_CONTRADICTION = "self_contradiction"
    OVERCONFIDENT = "overconfident"
    UNKNOWN = "unknown"
