"""Dataset adapter base class."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterable, Mapping, Optional

from ..schema import Attack


class BaseDatasetAdapter(ABC):
    """Abstract adapter that normalizes raw datasets into canonical attacks."""

    def __init__(self, path: Path, config: Optional[Mapping[str, object]] = None) -> None:
        self.path = Path(path)
        self.config = dict(config or {})

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable dataset name."""

    @property
    def version(self) -> Optional[str]:
        return self.config.get("version") if self.config else None

    @abstractmethod
    def load(self) -> Iterable[Attack]:
        """Return iterable of canonical attacks."""
        raise NotImplementedError
