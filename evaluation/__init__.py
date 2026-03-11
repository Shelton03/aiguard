"""Evaluation module registry and base interfaces."""
from __future__ import annotations

from evaluation.base import BaseEvaluationModule
from evaluation.registry import module_registry
from evaluation import modules  # noqa: F401 ensure module registration

__all__ = ["BaseEvaluationModule", "module_registry"]
