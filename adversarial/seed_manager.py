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
         """Promote attacks to seed status.

        For attacks already stored, updates their generation_type in-place.
        For attacks not yet stored, inserts them as seeds.
        Returns the total number of rows affected (updated + inserted).
        """
        attack_list = list(attacks)
        if not attack_list:
            return 0

        # Determine which attack_ids already exist in storage.
        existing_ids = {
            a.attack_id
            for a in self.storage.list_attacks()
        }

        to_update: List[str] = []
        to_insert: List[Attack] = []

        for attack in attack_list:
            if attack.attack_id in existing_ids:
                to_update.append(attack.attack_id)
            else:
                attack.generation_type = GenerationType.SEED
                to_insert.append(attack)

        updated = self.storage.update_generation_type(to_update, GenerationType.SEED)
        inserted = self.storage.insert_attacks(to_insert) if to_insert else 0
        return updated + inserted
