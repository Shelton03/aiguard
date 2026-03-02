"""Adapter registry to keep core logic decoupled from dataset specifics."""
from __future__ import annotations

from typing import Dict, Mapping, Type

from .base_adapter import BaseDatasetAdapter


class AdapterRegistry:
    def __init__(self) -> None:
        self._registry: Dict[str, Type[BaseDatasetAdapter]] = {}

    def register(self, key: str, adapter_cls: Type[BaseDatasetAdapter]) -> None:
        if not issubclass(adapter_cls, BaseDatasetAdapter):
            raise TypeError("adapter_cls must subclass BaseDatasetAdapter")
        self._registry[key] = adapter_cls

    def create(self, key: str, path: str, config: Mapping[str, object]) -> BaseDatasetAdapter:
        if key not in self._registry:
            raise KeyError(f"Adapter '{key}' is not registered")
        return self._registry[key](path=path, config=config)

    def available(self) -> Dict[str, Type[BaseDatasetAdapter]]:
        return dict(self._registry)


registry = AdapterRegistry()


def register_adapter(name: str):
    def decorator(cls: Type[BaseDatasetAdapter]) -> Type[BaseDatasetAdapter]:
        registry.register(name, cls)
        return cls

    return decorator
