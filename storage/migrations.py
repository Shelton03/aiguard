"""Migration helpers for AIGuard storage."""
from __future__ import annotations

from typing import Literal

from .manager import StorageManager


def migrate_backend(to_backend: Literal["sqlite", "postgres"]) -> None:
    """Explicit migration entrypoint; leaves source intact."""
    mgr = StorageManager()
    mgr.migrate(dest_backend=to_backend)
