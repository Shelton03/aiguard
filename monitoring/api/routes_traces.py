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
