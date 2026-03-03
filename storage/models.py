"""Canonical storage models represented as simple dataclasses."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class TestCase:
    id: str
    dataset_name: str
    category: str
    prompt: str
    expected_behavior: Optional[str] = None
    ground_truth: Optional[str] = None
    context_documents: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Trace:
    id: str
    timestamp: datetime
    model_name: str
    model_version: Optional[str]
    prompt: str
    response: str
    latency_ms: float
    tokens_used: Optional[int]
    environment: str  # ci | production
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EvaluationResultRecord:
    id: str
    trace_id: str
    test_case_id: str
    module: str
    mode: str
    execution_mode: str
    scores: Dict[str, Any]
    category: str
    risk_level: str
    confidence: float
    created_at: datetime


@dataclass
class ReviewLabel:
    id: str
    evaluation_result_id: str
    reviewer_id: str
    label: str
    severity: str
    notes: Optional[str]
    created_at: datetime


@dataclass
class DatasetRegistry:
    id: str
    name: str
    version: Optional[str]
    source: Optional[str]
    schema_adapter: Optional[str]
    installed_at: datetime
