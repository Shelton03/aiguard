"""Storage tests for evaluation metadata and dedupe handling."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from storage.manager import StorageManager
from storage.models import EvaluationResultRecord, Trace


@pytest.fixture
def storage_root(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    root.mkdir(parents=True, exist_ok=True)
    return root


def test_evaluation_metadata_persisted(storage_root: Path) -> None:
    storage = StorageManager(root=storage_root)

    trace = Trace(
        id="trace-1",
        timestamp=datetime.now(tz=timezone.utc),
        model_name="demo",
        model_version=None,
        prompt="hello",
        response="world",
        latency_ms=12.5,
        tokens_used=5,
        environment="test",
        metadata={"provider": "unit"},
    )
    storage.save_trace(trace)

    record = EvaluationResultRecord(
        id="eval-1",
        trace_id="trace-1",
        test_case_id="",
        module="hallucination",
        mode="context_grounded",
        execution_mode="monitoring",
        scores={"overall_risk": 0.1},
        category="factuality/overclaim",
        risk_level="safe",
        confidence=0.9,
        created_at=datetime.now(tz=timezone.utc),
        metadata={"taxonomy": {"judge_label": "safe"}},
    )
    storage.save_evaluation(record)

    export = storage.export_project()
    eval_row = export["evaluation_results"][0]
    raw_meta = eval_row.get("metadata")
    parsed_meta = json.loads(raw_meta) if isinstance(raw_meta, str) else raw_meta
    assert parsed_meta["taxonomy"]["judge_label"] == "safe"


def test_delete_evaluation_for_trace(storage_root: Path) -> None:
    storage = StorageManager(root=storage_root)
    record = EvaluationResultRecord(
        id="eval-2",
        trace_id="trace-2",
        test_case_id="",
        module="hallucination",
        mode="self_consistency",
        execution_mode="monitoring",
        scores={"overall_risk": 0.2},
        category="faithfulness/logical_inconsistency",
        risk_level="safe",
        confidence=0.8,
        created_at=datetime.now(tz=timezone.utc),
        metadata={},
    )
    storage.save_evaluation(record)
    storage.delete_evaluations_for_trace("trace-2", "hallucination")

    export = storage.export_project()
    assert len(export["evaluation_results"]) == 0
