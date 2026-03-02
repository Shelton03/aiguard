"""Utilities for managing seed attacks."""
from __future__ import annotations

from typing import Iterable, List, Optional

from .schema import Attack, GenerationType
from .storage import AttackStorage


class SeedManager:
    """Retrieves and tracks seed attacks used for mutation/evolution."""

    def __init__(self, storage: AttackStorage) -> None:
        self.storage = storage

    def get_seeds(self, limit: Optional[int] = None) -> List[Attack]:
        return self.storage.list_attacks(generation_type=GenerationType.SEED, limit=limit)

    def promote_to_seed(self, attacks: Iterable[Attack]) -> int:
        seeded = []
        for attack in attacks:
            attack.generation_type = GenerationType.SEED
            seeded.append(attack)
        return self.storage.insert_attacks(seeded)
