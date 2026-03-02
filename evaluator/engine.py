"""Evaluation engine orchestrating test runs."""
from __future__ import annotations

import time
from statistics import mean
from typing import Any, Iterable, List, Mapping, Optional

from .registry import test_registry
from .result import EvaluationResult
from .execution import ExecutionRunner
from .base_test import TargetModel


class EvaluationEngine:
    """Runs registered evaluation tests against a target model."""

    def __init__(self, target_model: TargetModel) -> None:
        self.target_model = target_model

    def run(
        self,
        test_type: str,
        test_cases: Iterable[Any],
        test_options: Optional[Mapping[str, Any]] = None,
    ) -> dict:
        test_cls = test_registry.get(test_type)
        test_instance = test_cls(**(test_options or {})) if callable(getattr(test_cls, "__init__", None)) else test_cls()

        runner = ExecutionRunner(self.target_model)
        results: List[EvaluationResult] = []
        start_time = time.time()

        for case in test_cases:
            prepared = test_instance.prepare_input(case, self.target_model)
            trace = test_instance.execute(prepared, self.target_model)
            result = test_instance.evaluate(trace, case)
            results.append(result)

        end_time = time.time()
        summary = self._summarize(test_type, results, (end_time - start_time) * 1000)
        return {"summary": summary, "results": [r.to_dict() for r in results]}

    def _summarize(self, test_type: str, results: List[EvaluationResult], elapsed_ms: float) -> dict:
        total = len(results)
        successes = sum(1 for r in results if r.success)
        avg_risk = mean([r.risk_score for r in results]) if results else 0.0
        critical = sum(1 for r in results if r.severity.lower() == "critical")

        return {
            "test_type": test_type,
            "total_cases": total,
            "success_count": successes,
            "average_risk_score": round(avg_risk, 4),
            "critical_failures": critical,
            "execution_time_ms": round(elapsed_ms, 2),
        }
