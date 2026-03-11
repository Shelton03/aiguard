"""Trace service — read-only access to stored traces and their evaluations.

Queries are built directly against the SQLite backend via
:class:`~storage.manager.StorageManager` (``export_project`` + ``get_evaluations``).
This keeps monitoring fully decoupled from the write path.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from storage.manager import StorageManager

logger = logging.getLogger(__name__)


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


class TraceService:
    """Read-only façade over stored traces.

    Parameters
    ----------
    storage_root:
        Forwarded to :class:`~storage.manager.StorageManager`.
    """

    def __init__(self, storage_root: Optional[str] = None) -> None:
        self._storage = StorageManager(root=storage_root)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_traces(
        self,
        *,
        model: Optional[str] = None,
        limit: int = 50,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        hallucination_label: Optional[str] = None,
        adversarial_label: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return a filtered list of trace dicts, newest first.

        Evaluation labels (``hallucination_label``, ``adversarial_label``)
        are joined from the evaluation_results table via the exported project
        dump so we never need raw SQL in the service layer.
        """
        export = self._storage.export_project()
        raw_traces: List[Dict[str, Any]] = export.get("traces", [])
        raw_evals: List[Dict[str, Any]] = export.get("evaluation_results", [])

        # Build a quick lookup: trace_id → {module: risk_level}
        label_map: Dict[str, Dict[str, str]] = {}
        for ev in raw_evals:
            tid = ev.get("trace_id", "")
            mod = ev.get("module", "")
            label_map.setdefault(tid, {})[mod] = ev.get("risk_level", "")

        # Parse filter datetimes once
        dt_from = _parse_dt(date_from)
        dt_to = _parse_dt(date_to)

        results: List[Dict[str, Any]] = []
        for t in raw_traces:
            ts = _parse_dt(t.get("timestamp"))

            # --- Filters ---
            if model and t.get("model_name", "") != model:
                continue
            if dt_from and ts and ts < dt_from:
                continue
            if dt_to and ts and ts > dt_to:
                continue
            labels = label_map.get(t.get("id", ""), {})
            if hallucination_label and labels.get("hallucination") != hallucination_label:
                continue
            if adversarial_label and labels.get("adversarial") != adversarial_label:
                continue

            results.append(
                {
                    **t,
                    "hallucination_label": labels.get("hallucination"),
                    "adversarial_label": labels.get("adversarial"),
                    "metadata": json.loads(t["metadata"])
                    if isinstance(t.get("metadata"), str)
                    else (t.get("metadata") or {}),
                }
            )

        # Sort newest first then apply limit
        results.sort(
            key=lambda x: str(x.get("timestamp") or ""),
            reverse=True,
        )
        return results[:limit]

    def get_trace(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """Return a single trace dict with all evaluation results embedded."""
        export = self._storage.export_project()
        trace_row = next(
            (t for t in export.get("traces", []) if t.get("id") == trace_id),
            None,
        )
        if trace_row is None:
            return None

        evals = [
            ev
            for ev in export.get("evaluation_results", [])
            if ev.get("trace_id") == trace_id
        ]
        for ev in evals:
            if isinstance(ev.get("scores"), str):
                try:
                    ev["scores"] = json.loads(ev["scores"])
                except Exception:
                    pass

        return {
            **trace_row,
            "metadata": json.loads(trace_row["metadata"])
            if isinstance(trace_row.get("metadata"), str)
            else (trace_row.get("metadata") or {}),
            "evaluations": evals,
        }
