"""Trace routes — ``GET /traces`` and ``GET /traces/{trace_id}``."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from config.pipeline_config import load_pipeline_config
from monitoring.services.trace_service import TraceService
from pipeline.evaluation_worker import EvaluationWorker
from pipeline.event_models import TraceCreatedEvent

router = APIRouter(prefix="/traces", tags=["traces"])


def _get_service() -> TraceService:
    return TraceService()


@router.get("", response_model=List[Dict[str, Any]])
def list_traces(
    model: Optional[str] = Query(None, description="Filter by model name"),
    limit: int = Query(50, ge=1, le=1000, description="Max traces to return"),
    date_from: Optional[str] = Query(None, description="ISO-8601 start datetime"),
    date_to: Optional[str] = Query(None, description="ISO-8601 end datetime"),
    hallucination_label: Optional[str] = Query(None, description="'safe' or 'hallucinated'"),
    hallucination_family: Optional[str] = Query(None, description="factuality|faithfulness"),
    hallucination_subtype: Optional[str] = Query(None, description="Hallucination subtype"),
    hallucination_category: Optional[str] = Query(None, description="Hallucination category string"),
    adversarial_label: Optional[str] = Query(None, description="'safe' or 'injection_detected'"),
    service: TraceService = Depends(_get_service),
) -> List[Dict[str, Any]]:
    """Return a filtered, paginated list of traces."""
    return service.get_traces(
        model=model,
        limit=limit,
        date_from=date_from,
        date_to=date_to,
        hallucination_label=hallucination_label,
        hallucination_family=hallucination_family,
        hallucination_subtype=hallucination_subtype,
        hallucination_category=hallucination_category,
        adversarial_label=adversarial_label,
    )


@router.get("/{trace_id}", response_model=Dict[str, Any])
def get_trace(
    trace_id: str,
    service: TraceService = Depends(_get_service),
) -> Dict[str, Any]:
    """Return a single trace with all embedded evaluation results."""
    result = service.get_trace(trace_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Trace '{trace_id}' not found.")
    return result


@router.post("/{trace_id}/evaluate", response_model=Dict[str, Any])
def evaluate_trace(
    trace_id: str,
    force_judge: bool = Query(False, description="Force judge evaluation even below thresholds"),
    service: TraceService = Depends(_get_service),
) -> Dict[str, Any]:
    """Re-evaluate a stored trace and update its evaluation records."""
    trace_row = service.get_trace_record(trace_id)
    if trace_row is None:
        raise HTTPException(status_code=404, detail=f"Trace '{trace_id}' not found.")

    prompt = trace_row.get("prompt") or ""
    trace_dict = {
        "trace_id": trace_row.get("id"),
        "timestamp": trace_row.get("timestamp"),
        "model": trace_row.get("model_name"),
        "provider": trace_row.get("metadata", {}).get("provider", ""),
        "input_messages": [{"role": "user", "content": prompt}] if prompt else [],
        "output_text": trace_row.get("response"),
        "latency_ms": trace_row.get("latency_ms", 0.0),
        "token_usage": {"total_tokens": trace_row.get("tokens_used")}
        if trace_row.get("tokens_used")
        else None,
        "metadata": trace_row.get("metadata") or {},
    }

    config = load_pipeline_config()
    if force_judge:
        config.enable_hallucination_eval = True
        config.judge.enabled = True

    worker = EvaluationWorker(config=config)
    event = TraceCreatedEvent.from_trace_dict(trace_dict, project_id=config.project_id)
    evaluated = worker.process_batch([event])

    return {
        "trace_id": trace_id,
        "evaluated": len(evaluated),
        "forced_judge": force_judge,
    }


@router.post("/ingest", tags=["traces"], response_model=Dict[str, Any])
def ingest_trace(
    payload: Any = Body(..., description="Trace dict or list of trace dicts."),
) -> Dict[str, Any]:
    """Ingest one or more traces and run evaluation immediately."""
    if payload is None:
        raise HTTPException(status_code=400, detail="Missing trace payload.")

    if isinstance(payload, list):
        trace_dicts = payload
    elif isinstance(payload, dict):
        trace_dicts = [payload]
    else:
        raise HTTPException(status_code=400, detail="Payload must be a dict or list.")

    config = load_pipeline_config()
    worker = EvaluationWorker(config=config)

    events: List[TraceCreatedEvent] = []
    for trace_dict in trace_dicts:
        if not isinstance(trace_dict, dict):
            continue
        events.append(
            TraceCreatedEvent.from_trace_dict(
                trace_dict,
                project_id=config.project_id,
            )
        )

    if not events:
        raise HTTPException(status_code=400, detail="No valid trace objects provided.")

    evaluated = worker.process_batch(events)

    return {
        "received": len(events),
        "evaluated": len(evaluated),
        "trace_ids": [event.trace_id for event in events],
    }
