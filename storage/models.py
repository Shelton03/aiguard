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
    label: str
    risk_level: str
    confidence: float
    created_at: datetime
    
    # NEW FIELDS - Adversarial-specific
    attack_type: Optional[str] = None
    subtype: Optional[str] = None
    
    # NEW FIELDS - Hallucination-specific
    hallucination_type: Optional[str] = None
    hallucination_subtype: Optional[str] = None
    source: Optional[str] = None
    
    # NEW FIELDS - Both modules
    compliance_status: Optional[str] = None
    explanation: Optional[str] = None
    risk_reason: Optional[str] = None
    
    metadata: Dict[str, Any] = field(default_factory=dict)


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
