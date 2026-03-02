"""Base evaluation test interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Protocol

from .result import EvaluationResult
from .execution import ExecutionTrace


class TargetModel(Protocol):
    """Abstract target model interface.

    Concrete adapters wrap specific providers (OpenAI, Claude, OSS) and implement `run`.
    The evaluator stays model-agnostic.
    """

    def run(self, input_payload: Any) -> Any:
        """Execute the model with the given payload and return a raw response."""
        ...


class BaseEvaluationTest(ABC):
    """Abstract base for all evaluation tests.

    Each concrete test owns preparation, execution, and scoring/evaluation logic.
    """

    test_type: str

    @abstractmethod
    def prepare_input(self, test_case: Any, target_model: TargetModel) -> Any:
        """Prepare model-ready input from a test case."""
        raise NotImplementedError

    @abstractmethod
    def execute(self, prepared_input: Any, target_model: TargetModel) -> ExecutionTrace:
        """Run the model call(s) and return an execution trace (single or multi-turn)."""
        raise NotImplementedError

    @abstractmethod
    def evaluate(self, trace: ExecutionTrace, test_case: Any) -> EvaluationResult:
        """Compute EvaluationResult using test-specific logic."""
        raise NotImplementedError
