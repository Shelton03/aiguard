"""Base interfaces for evaluation modules."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseEvaluationModule(ABC):
    """Base evaluation module contract used by the CLI registry."""

    module_name: str

    def __init__(self, project_config: Dict[str, Any], mode: str, root_dir: str) -> None:
        self.project_config = project_config
        self.mode = mode
        self.root_dir = root_dir

    @abstractmethod
    def run(self) -> None:
        ...

    @abstractmethod
    def generate_report(self) -> Dict[str, Any]:
        ...

    @abstractmethod
    def exit_code(self) -> int:
        ...
