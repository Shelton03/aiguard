"""Execution layer abstractions for model runs."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, List, Optional
import time
import uuid

from .base_test import TargetModel


@dataclass
class ExecutionStep:
    """Represents a single interaction in a (potentially multi-turn) run."""

    turn_index: int
    input_payload: Any
    output: Any
    start_time: float
    end_time: float
    metadata: dict = field(default_factory=dict)

    @property
    def latency_ms(self) -> float:
        return (self.end_time - self.start_time) * 1000


@dataclass
class ExecutionTrace:
    """Full trace for a test case execution."""

    trace_id: str
    steps: List[ExecutionStep]
    created_at: datetime
    metadata: dict = field(default_factory=dict)

    @property
    def total_latency_ms(self) -> float:
        return sum(step.latency_ms for step in self.steps)


class ExecutionRunner:
    """Centralized executor handling single- and multi-turn test runs."""

    def __init__(self, target_model: TargetModel) -> None:
        self.target_model = target_model

    def run_single(self, input_payload: Any, metadata: Optional[dict] = None) -> ExecutionTrace:
        trace_id = str(uuid.uuid4())
        metadata = metadata or {}
        start = time.time()
        output = self.target_model.run(input_payload)
        end = time.time()

        step = ExecutionStep(
            turn_index=0,
            input_payload=input_payload,
            output=output,
            start_time=start,
            end_time=end,
            metadata={},
        )
        return ExecutionTrace(trace_id=trace_id, steps=[step], created_at=datetime.utcnow(), metadata=metadata)

    def run_multi_turn(self, inputs: List[Any], metadata: Optional[dict] = None) -> ExecutionTrace:
        trace_id = str(uuid.uuid4())
        metadata = metadata or {}
        steps: List[ExecutionStep] = []

        for idx, payload in enumerate(inputs):
            start = time.time()
            output = self.target_model.run(payload)
            end = time.time()
            steps.append(
                ExecutionStep(
                    turn_index=idx,
                    input_payload=payload,
                    output=output,
                    start_time=start,
                    end_time=end,
                    metadata={},
                )
            )

        return ExecutionTrace(trace_id=trace_id, steps=steps, created_at=datetime.utcnow(), metadata=metadata)
