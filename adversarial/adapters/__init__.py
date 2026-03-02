"""Dataset adapters package."""

from .base_adapter import BaseDatasetAdapter
from .registry import registry, register_adapter

__all__ = ["BaseDatasetAdapter", "registry", "register_adapter"]
