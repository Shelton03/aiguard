"""Registry for evaluation tests."""
from __future__ import annotations

from typing import Dict, Type

from .base_test import BaseEvaluationTest


class TestRegistry:
    def __init__(self) -> None:
        self._registry: Dict[str, Type[BaseEvaluationTest]] = {}

    def register(self, test_type: str, test_cls: Type[BaseEvaluationTest]) -> None:
        if not issubclass(test_cls, BaseEvaluationTest):
            raise TypeError("test_cls must subclass BaseEvaluationTest")
        self._registry[test_type] = test_cls

    def get(self, test_type: str) -> Type[BaseEvaluationTest]:
        if test_type not in self._registry:
            raise KeyError(f"Test type '{test_type}' is not registered")
        return self._registry[test_type]

    def available(self) -> Dict[str, Type[BaseEvaluationTest]]:
        return dict(self._registry)


test_registry = TestRegistry()


def register_test(test_type: str):
    def decorator(cls: Type[BaseEvaluationTest]) -> Type[BaseEvaluationTest]:
        test_registry.register(test_type, cls)
        return cls

    return decorator
