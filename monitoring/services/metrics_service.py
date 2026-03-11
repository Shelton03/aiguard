"""Metrics service — aggregated statistics over stored traces and evaluations."""
from __future__ import annotations

import json
import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from storage.manager import StorageManager

logger = logging.getLogger(__name__)


def _now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


class MetricsService:
    """Compute aggregate metrics from stored evaluation results.

    Parameters
    ----------
    storage_root:
        Forwarded to :class:`~storage.manager.StorageManager`.
    """

    def __init__(self, storage_root: Optional[str] = None) -> None:
        self._storage = StorageManager(root=storage_root)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def hallucination_rate(self, window_hours: float = 24.0) -> float:
        """Fraction of evaluated traces labelled *hallucinated* in the window."""
        return self._label_rate("hallucination", "hallucinated", window_hours)

    def adversarial_rate(self, window_hours: float = 24.0) -> float:
        """Fraction of evaluated traces labelled *injection_detected* in the window."""
        return self._label_rate("adversarial", "injection_detected", window_hours)

    def model_usage(self) -> Dict[str, int]:
        """Return ``{model_name: trace_count}`` across all stored traces."""
        export = self._storage.export_project()
        counter: Counter[str] = Counter()
        for t in export.get("traces", []):
            name = t.get("model_name") or "unknown"
            counter[name] += 1
        return dict(counter.most_common())

    def trace_volume(self, bucket: str = "hour") -> List[Dict[str, Any]]:
        """Return ``[{bucket: str, count: int}]`` ordered chronologically.

        Parameters
        ----------
        bucket:
            ``"hour"`` or ``"day"``.  All other values default to ``"hour"``.
        """
        export = self._storage.export_project()
        buckets: Counter[str] = Counter()

        for t in export.get("traces", []):
            ts = _parse_dt(t.get("timestamp"))
            if ts is None:
                continue
            if bucket == "day":
                key = ts.strftime("%Y-%m-%d")
            else:
                key = ts.strftime("%Y-%m-%dT%H:00")
            buckets[key] += 1

        return [
            {"bucket": k, "count": v}
            for k, v in sorted(buckets.items())
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _label_rate(
        self,
        module: str,
        positive_label: str,
        window_hours: float,
    ) -> float:
        cutoff = _now_utc() - timedelta(hours=window_hours)
        export = self._storage.export_project()
        total = 0
        positive = 0

        for ev in export.get("evaluation_results", []):
            if ev.get("module") != module:
                continue
            ts = _parse_dt(ev.get("created_at"))
            if ts is not None:
                # Ensure offset-aware comparison
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts < cutoff:
                    continue
            total += 1
            if ev.get("risk_level") == positive_label:
                positive += 1

        return round(positive / total, 4) if total > 0 else 0.0
