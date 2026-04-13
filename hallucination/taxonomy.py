"""Granular taxonomy labels for hallucination outcomes."""
from __future__ import annotations

from enum import Enum


class HallucinationFamily(str, Enum):
    FACTUALITY = "factuality"
    FAITHFULNESS = "faithfulness"


class HallucinationSubtype(str, Enum):
    FACTUAL_CONTRADICTION = "factual_contradiction"
    ENTITY_ERROR = "entity_error"
    RELATION_ERROR = "relation_error"
    FACTUAL_FABRICATION = "factual_fabrication"
    UNVERIFIABLE = "unverifiable"
    OVERCLAIM = "overclaim"
    INSTRUCTION_INCONSISTENCY = "instruction_inconsistency"
    CONTEXT_INCONSISTENCY = "context_inconsistency"
    LOGICAL_INCONSISTENCY = "logical_inconsistency"
    UNKNOWN = "unknown"


class HallucinationSource(str, Enum):
    INTRINSIC = "intrinsic"
    EXTRINSIC = "extrinsic"
    UNKNOWN = "unknown"


class HallucinationCategory(str, Enum):
    """Flat category string for compatibility (family/subtype/source)."""

    FACTUAL_CONTRADICTION = "factuality/factual_contradiction"
    ENTITY_ERROR = "factuality/entity_error"
    RELATION_ERROR = "factuality/relation_error"
    FACTUAL_FABRICATION = "factuality/factual_fabrication"
    UNVERIFIABLE = "factuality/unverifiable"
    OVERCLAIM = "factuality/overclaim"
    INSTRUCTION_INCONSISTENCY = "faithfulness/instruction_inconsistency"
    CONTEXT_INCONSISTENCY = "faithfulness/context_inconsistency"
    LOGICAL_INCONSISTENCY = "faithfulness/logical_inconsistency"
    UNKNOWN = "unknown"
