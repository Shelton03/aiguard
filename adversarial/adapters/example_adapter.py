"""Example dataset adapter for JSON lists."""
from __future__ import annotations

import json
from typing import Iterable
from uuid import uuid4

from .base_adapter import BaseDatasetAdapter
from .registry import register_adapter
from ..schema import Attack, AttackMetadata, AttackType, GenerationType


@register_adapter("json_list")
class JsonListAdapter(BaseDatasetAdapter):
    """Adapter for simple JSON files containing a list of attack objects."""

    @property
    def name(self) -> str:
        return self.config.get("name", "json_list_dataset")

    def load(self) -> Iterable[Attack]:
        with open(self.path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for entry in data:
            raw_type = entry.get("attack_type", AttackType.OTHER.value)
            try:
                attack_type = AttackType(raw_type)
            except ValueError:
                attack_type = AttackType.OTHER

            yield Attack(
                attack_id=str(entry.get("id") or uuid4()),
                source_dataset=self.name,
                attack_type=attack_type,
                subtype=entry.get("subtype"),
                content=entry["content"],
                severity=entry.get("severity", "medium"),
                success_criteria=entry.get("success_criteria", {}),
                metadata=AttackMetadata(
                    dataset_version=self.version,
                    multi_turn=entry.get("multi_turn", False),
                    language=entry.get("language"),
                    extra={k: v for k, v in entry.items() if k not in {"id", "content", "attack_type", "severity", "success_criteria", "subtype", "multi_turn", "language"}},
                ),
                generation_type=GenerationType.SEED,
            )
