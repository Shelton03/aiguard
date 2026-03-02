"""Optional LLM-as-judge interface (kept deterministic by default)."""
from __future__ import annotations

from typing import Any, Dict


class Judge:
    """Placeholder judge; deterministic stub for offline use.

    In evaluation mode, this can be extended to call an internal model (no external APIs required).
    """

    def score(self, response: str, reference: Dict[str, Any]) -> float:
        # Deterministic stub: length-normalized heuristic
        return min(1.0, max(0.0, len(response) / (len(reference.get("prompt", "")) + 1)))
