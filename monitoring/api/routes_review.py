"""Review queue routes — delegates to the existing :class:`~review.queue.ReviewQueue`."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter

router = APIRouter(prefix="/review", tags=["review"])


def _make_queue():
    """Instantiate the review queue for the current project."""
    from storage.manager import StorageManager

    mgr = StorageManager()
    db_path = Path(mgr.root) / ".aiguard" / "aiguard.db"
    try:
        from review.queue import ReviewQueue

        return ReviewQueue(db_path=db_path, project=mgr.project)
    except ImportError:
        return None


@router.get("/queue", response_model=List[Dict[str, Any]])
def get_review_queue() -> List[Dict[str, Any]]:
    """Return all pending items from the review queue."""
    rq = _make_queue()
    if rq is None:
        return []
    items = rq.list_pending()
    return [_item_to_dict(i) for i in items]


@router.get("/queue/all", response_model=List[Dict[str, Any]])
def get_all_review_items() -> List[Dict[str, Any]]:
    """Return all items (pending + completed) from the review queue."""
    rq = _make_queue()
    if rq is None:
        return []
    items = rq.list_all()
    return [_item_to_dict(i) for i in items]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _item_to_dict(item: Any) -> Dict[str, Any]:
    """Convert a :class:`~review.models.ReviewQueueItem` to a plain dict."""
    if hasattr(item, "__dict__"):
        d = item.__dict__.copy()
        # Serialise datetime / enum fields
        for k, v in d.items():
            if hasattr(v, "isoformat"):
                d[k] = v.isoformat()
            elif hasattr(v, "value"):
                d[k] = v.value
        return d
    return {}
