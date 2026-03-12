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

    def _extract_content(self, entry: dict) -> str:
        # support multiple possible prompt field names
        for k in ("content", "prompt", "text", "instruction", "query", "input"):
            if k in entry and entry[k]:
                return entry[k]
        # fallback: try first string field
        for k, v in entry.items():
            if isinstance(v, str) and v.strip():
                return v
        raise KeyError("no content-like field found in entry")

    def load(self) -> Iterable[Attack]:
        # Support both a single JSON list and newline-delimited JSON (jsonl)
        with open(self.path, "r", encoding="utf-8") as f:
            text = f.read()

        entries = None
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                entries = parsed
        except Exception:
            entries = None

        if entries is None:
            # try jsonl: parse line by line
            entries = []
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except Exception:
                    # skip malformed lines
                    continue

        for entry in entries:
            try:
                content = self._extract_content(entry)
            except KeyError:
                continue

            raw_type = entry.get("attack_type") or entry.get("attack") or entry.get("type") or AttackType.PROMPT_INJECTION.value
            try:
                attack_type = AttackType(raw_type)
            except Exception:
                # accept string labels mapping (common fallback)
                try:
                    attack_type = AttackType(str(raw_type))
                except Exception:
                    attack_type = AttackType.PROMPT_INJECTION

            yield Attack(
                attack_id=str(entry.get("id") or uuid4()),
                source_dataset=self.name,
                attack_type=attack_type,
                subtype=entry.get("subtype"),
                content=content,
                severity=entry.get("severity", "medium"),
                success_criteria=entry.get("success_criteria", {}),
                metadata=AttackMetadata(
                    dataset_version=self.version,
                    multi_turn=entry.get("multi_turn", False),
                    language=entry.get("language"),
                    extra={k: v for k, v in entry.items() if k not in {"id", "content", "prompt", "text", "attack_type", "attack", "severity", "success_criteria", "subtype", "multi_turn", "language"}},
                ),
                generation_type=GenerationType.SEED,
            )
