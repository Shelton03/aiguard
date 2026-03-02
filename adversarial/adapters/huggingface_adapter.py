"""HuggingFace datasets adapter for adversarial attacks."""
from __future__ import annotations

import json
from typing import Iterable, Mapping, Optional
from uuid import uuid4

from .base_adapter import BaseDatasetAdapter
from .registry import register_adapter
from ..schema import Attack, AttackMetadata, AttackType, GenerationType


@register_adapter("huggingface")
class HuggingFaceAdapter(BaseDatasetAdapter):
    """Adapter for datasets hosted on the HuggingFace Hub.

    Config options:
    - split: dataset split name (default: "train")
    - field_mapping: dict to map schema fields. Keys: content, attack_type, subtype, severity,
      success_criteria, multi_turn, language, id. Values: source column names.
    - attack_type_value: fallback attack_type if column missing (default: prompt_injection)
    - success_criteria_default: dict to use when field missing or unparsable
    - load_kwargs: extra kwargs to pass to `datasets.load_dataset`
    """

    def __init__(self, path, config: Optional[Mapping[str, object]] = None) -> None:  # type: ignore[override]
        super().__init__(path, config)
        self.split = self.config.get("split", "train")
        self.field_mapping: Mapping[str, str] = self.config.get("field_mapping", {})
        self.attack_type_value = self.config.get("attack_type_value", AttackType.PROMPT_INJECTION.value)
        self.success_criteria_default: Mapping[str, object] = self.config.get("success_criteria_default", {})
        self.load_kwargs: Mapping[str, object] = self.config.get("load_kwargs", {})

    @property
    def name(self) -> str:
        return self.config.get("name", str(self.path))

    def load(self) -> Iterable[Attack]:
        try:
            from datasets import load_dataset  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dependency
            raise ImportError("Install `datasets` to use the HuggingFace adapter: pip install datasets") from exc

        ds = load_dataset(str(self.path), split=self.split, **self.load_kwargs)
        mapping = self.field_mapping

        for record in ds:
            content = record.get(mapping.get("content", "content"))
            if not content:
                continue

            attack_type_raw = record.get(mapping.get("attack_type", "attack_type"), self.attack_type_value)
            try:
                attack_type = AttackType(attack_type_raw)
            except ValueError:
                attack_type = AttackType.PROMPT_INJECTION

            severity = record.get(mapping.get("severity", "severity"), "medium")
            subtype = record.get(mapping.get("subtype", "subtype")) or None

            success_value = record.get(mapping.get("success_criteria", "success_criteria"))
            success_criteria = self._normalize_success(success_value)

            metadata = AttackMetadata(
                dataset_version=self.version,
                multi_turn=bool(record.get(mapping.get("multi_turn", "multi_turn"), False)),
                language=record.get(mapping.get("language", "language")),
                extra={k: v for k, v in record.items() if k not in mapping.values()},
            )

            yield Attack(
                attack_id=str(record.get(mapping.get("id", "id")) or uuid4()),
                source_dataset=self.name,
                attack_type=attack_type,
                subtype=subtype,
                content=content,
                severity=severity,
                success_criteria=success_criteria,
                metadata=metadata,
                generation_type=GenerationType.SEED,
            )

    def _normalize_success(self, value):
        if value is None:
            return dict(self.success_criteria_default)
        if isinstance(value, (dict, list)):
            return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except Exception:
                return {"raw": value}
        return {"raw": value}
