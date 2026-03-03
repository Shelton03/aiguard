"""Abstract backend interface for storage."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Iterable, List

from .models import (
    TestCase,
    Trace,
    EvaluationResultRecord,
    ReviewLabel,
    DatasetRegistry,
)


class BaseBackend(ABC):
    """Abstract storage backend."""

    @abstractmethod
    def init(self) -> None:
        ...

    @abstractmethod
    def save_test_case(self, project: str, case: TestCase) -> None:
        ...

    @abstractmethod
    def save_trace(self, project: str, trace: Trace) -> None:
        ...

    @abstractmethod
    def save_evaluation(self, project: str, result: EvaluationResultRecord) -> None:
        ...

    @abstractmethod
    def save_review(self, project: str, review: ReviewLabel) -> None:
        ...

    @abstractmethod
    def get_evaluations(self, project: str, limit: int = 100) -> List[EvaluationResultRecord]:
        ...

    @abstractmethod
    def register_dataset(self, project: str, dataset: DatasetRegistry) -> None:
        ...

    @abstractmethod
    def list_projects(self) -> List[str]:
        ...

    @abstractmethod
    def delete_project(self, project: str) -> None:
        ...

    @abstractmethod
    def export_project(self, project: str) -> Dict[str, Any]:
        ...

    @abstractmethod
    def migrate_to(self, dest_backend: "BaseBackend", project: str) -> None:
        ...
