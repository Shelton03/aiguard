"""Canonical adversarial attack schema and supporting types."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional
from datetime import datetime, timezone


class AttackType(str, Enum):
    """High-level categories for adversarial prompts."""

    PROMPT_INJECTION = "prompt_injection"
    JAILBREAK = "jailbreak"
    PII_EXFILTRATION = "pii_exfiltration"
    POLICY_OVERRIDE = "policy_override"
    MODEL_SPECIFIC = "model_specific"
    OTHER = "other"


class PromptInjectionSubtype(str, Enum):
    """Subtypes for prompt injection attacks."""

    INSTRUCTION_OVERRIDE = "instruction_override"
    ROLEPLAY_OVERRIDE = "roleplay_override"
    SYSTEM_PROMPT_EXFILTRATION = "system_prompt_exfiltration"
    CONTEXT_POISONING = "context_poisoning"


class JailbreakSubtype(str, Enum):
    """Subtypes for jailbreak attacks."""

    ROLE_PLAY = "role_play"
    HYPOTHETICAL = "hypothetical"
    AUTHORIZATION_BYPASS = "authorization_bypass"
    TOKEN_SMUGGLING = "token_smuggling"


class PIIExfiltrationSubtype(str, Enum):
    """Subtypes for PII exfiltration attacks."""

    DATA_EXTRACTION = "data_extraction"
    PERSONA_EXTRACTION = "persona_extraction"
    CONTEXT_LEAK = "context_leak"


class PolicyOverrideSubtype(str, Enum):
    """Subtypes for policy override attacks."""

    SYSTEM_PROMPT_OVERRIDE = "system_prompt_override"
    ROLE_OVERRIDE = "role_override"
    CAPABILITY_EXPANSION = "capability_expansion"


class GenerationType(str, Enum):
    """How an attack was produced."""

    SEED = "seed"
    MUTATED = "mutated"
    EVOLVED = "evolved"
    RUNTIME_DISCOVERED = "runtime_discovered"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@dataclass
class AttackMetadata:
    """Metadata describing context for an attack."""

    dataset_version: Optional[str] = None
    multi_turn: bool = False
    language: Optional[str] = None
    source: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset_version": self.dataset_version,
            "multi_turn": self.multi_turn,
            "language": self.language,
            "source": self.source,
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "AttackMetadata":
        data = data or {}
        return cls(
            dataset_version=data.get("dataset_version"),
            multi_turn=data.get("multi_turn", False),
            language=data.get("language"),
            source=data.get("source"),
            extra=data.get("extra", {}),
        )


@dataclass
class Attack:
    """Canonical representation of an adversarial attack sample."""

    attack_id: str
    source_dataset: str
    attack_type: AttackType
    subtype: Optional[str]
    content: str
    severity: str
    success_criteria: Dict[str, Any]
    metadata: AttackMetadata = field(default_factory=AttackMetadata)
    generation_type: GenerationType = GenerationType.SEED
    created_at: datetime = field(default_factory=_utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "attack_id": self.attack_id,
            "source_dataset": self.source_dataset,
            "attack_type": self.attack_type.value,
            "subtype": self.subtype,
            "content": self.content,
            "severity": self.severity,
            "success_criteria": self.success_criteria,
            "metadata": self.metadata.to_dict(),
            "generation_type": self.generation_type.value,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Attack":
        return cls(
            attack_id=data["attack_id"],
            source_dataset=data["source_dataset"],
            attack_type=AttackType(data["attack_type"]),
            subtype=data.get("subtype"),
            content=data["content"],
            severity=data.get("severity", "unknown"),
            success_criteria=data.get("success_criteria", {}),
            metadata=AttackMetadata.from_dict(data.get("metadata")),
            generation_type=GenerationType(data.get("generation_type", GenerationType.SEED.value)),
            created_at=datetime.fromisoformat(data.get("created_at"))
            if data.get("created_at")
            else _utcnow(),
        )
