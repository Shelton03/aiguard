"""Evaluation module registry."""
from __future__ import annotations

from typing import Dict, Type

from .base import BaseEvaluationModule


class ModuleRegistry:
    def __init__(self) -> None:
        self._registry: Dict[str, Type[BaseEvaluationModule]] = {}

    def register(self, name: str, module_cls: Type[BaseEvaluationModule]) -> None:
        if not issubclass(module_cls, BaseEvaluationModule):
            raise TypeError("module_cls must subclass BaseEvaluationModule")
        self._registry[name] = module_cls

    def get(self, name: str) -> Type[BaseEvaluationModule]:
        if name not in self._registry:
            raise KeyError(f"Module '{name}' is not registered")
        return self._registry[name]

    def available(self) -> Dict[str, Type[BaseEvaluationModule]]:
        return dict(self._registry)


module_registry = ModuleRegistry()
