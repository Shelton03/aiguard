"""Metrics routes — aggregate statistics endpoints."""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Query

from monitoring.services.metrics_service import MetricsService

router = APIRouter(prefix="/metrics", tags=["metrics"])


def _get_service() -> MetricsService:
    return MetricsService()


@router.get("/hallucination_rate")
def hallucination_rate(
    window_hours: float = Query(24.0, ge=0.1, description="Look-back window in hours"),
    service: MetricsService = Depends(_get_service),
) -> Dict[str, Any]:
    """Return the fraction of traces labelled *hallucinated* in the time window."""
    rate = service.hallucination_rate(window_hours=window_hours)
    return {"hallucination_rate": rate, "window_hours": window_hours}


@router.get("/adversarial_rate")
def adversarial_rate(
    window_hours: float = Query(24.0, ge=0.1, description="Look-back window in hours"),
    service: MetricsService = Depends(_get_service),
) -> Dict[str, Any]:
    """Return the fraction of traces labelled *injection_detected* in the window."""
    rate = service.adversarial_rate(window_hours=window_hours)
    return {"adversarial_rate": rate, "window_hours": window_hours}


@router.get("/model_usage")
def model_usage(
    service: MetricsService = Depends(_get_service),
) -> Dict[str, Any]:
    """Return ``{model_name: trace_count}`` across all stored traces."""
    return {"model_usage": service.model_usage()}


@router.get("/trace_volume")
def trace_volume(
    bucket: str = Query("hour", description="Bucket granularity: 'hour' or 'day'"),
    service: MetricsService = Depends(_get_service),
) -> List[Dict[str, Any]]:
    """Return trace volume bucketed by hour or day."""
    return service.trace_volume(bucket=bucket)
