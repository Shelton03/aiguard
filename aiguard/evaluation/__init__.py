"""Evaluation module registry and base interfaces."""
from __future__ import annotations

from .base import BaseEvaluationModule
from .registry import module_registry
from . import modules  # noqa: F401 ensure module registration

__all__ = ["BaseEvaluationModule", "module_registry"]
