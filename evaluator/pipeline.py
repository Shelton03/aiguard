"""Pipeline helpers for batch evaluation runs."""
from __future__ import annotations

from typing import Any, Iterable, Mapping, Optional

from .engine import EvaluationEngine
from .base_test import TargetModel


def run_evaluation(
    test_type: str,
    test_cases: Iterable[Any],
    target_model: TargetModel,
    test_options: Optional[Mapping[str, Any]] = None,
) -> dict:
    """Convenience wrapper to run evaluation in one call."""
    engine = EvaluationEngine(target_model)
    return engine.run(test_type=test_type, test_cases=test_cases, test_options=test_options)
