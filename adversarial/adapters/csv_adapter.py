"""CSV dataset adapter for adversarial attacks."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable, Mapping, Optional
from uuid import uuid4

from .base_adapter import BaseDatasetAdapter
from .registry import register_adapter
from ..schema import Attack, AttackMetadata, AttackType, GenerationType


@register_adapter("csv")
class CsvAdapter(BaseDatasetAdapter):
    """Adapter for CSV files with column mapping support.

    Expected columns (configurable via `field_mapping` option):
    - content (required)
    - attack_type (optional; defaults to prompt_injection)
    - subtype (optional)
    - severity (optional; defaults to medium)
    - success_criteria (optional; JSON string or plain text)
    - language (optional)
    - multi_turn (optional; bool/int/str)
    """

    def __init__(self, path: Path, config: Optional[Mapping[str, object]] = None) -> None:
        super().__init__(path, config)
        self.field_mapping: Mapping[str, str] = self.config.get("field_mapping", {})

    @property
    def name(self) -> str:
        return self.config.get("name", self.path.stem)

    def load(self) -> Iterable[Attack]:
        with open(self.path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                mapping = self.field_mapping
                content = row.get(mapping.get("content", "content"))
                if not content:
                    continue

                attack_type_raw = row.get(mapping.get("attack_type", "attack_type"), AttackType.PROMPT_INJECTION.value)
                try:
                    attack_type = AttackType(attack_type_raw)
                except ValueError:
                    attack_type = AttackType.PROMPT_INJECTION

                subtype = row.get(mapping.get("subtype", "subtype")) or None
                severity = row.get(mapping.get("severity", "severity")) or "medium"
                success_raw = row.get(mapping.get("success_criteria", "success_criteria"))
                success_criteria = self._parse_json_safe(success_raw)

                metadata = AttackMetadata(
                    dataset_version=self.version,
                    multi_turn=self._to_bool(row.get(mapping.get("multi_turn", "multi_turn"))),
                    language=row.get(mapping.get("language", "language")),
                    extra={k: v for k, v in row.items() if k not in reader.fieldnames},
                )

                yield Attack(
                    attack_id=str(row.get(mapping.get("id", "id")) or uuid4()),
                    source_dataset=self.name,
                    attack_type=attack_type,
                    subtype=subtype,
                    content=content,
                    severity=severity,
                    success_criteria=success_criteria,
                    metadata=metadata,
                    generation_type=GenerationType.SEED,
                )

    @staticmethod
    def _parse_json_safe(value: Optional[str]):
        if value is None or value == "":
            return {}
        try:
            return json.loads(value)
        except Exception:
            return {"raw": value}

    @staticmethod
    def _to_bool(value: Optional[str]) -> bool:
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        value = str(value).strip().lower()
        return value in {"1", "true", "yes", "y"}
