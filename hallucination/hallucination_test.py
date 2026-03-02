"""Hallucination evaluation module entrypoint."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .modes import ExecutionMode, HallucinationMode, detect_execution_mode, detect_hallucination_mode
from .ground_truth_checker import evaluate_against_ground_truth
from .context_checker import evaluate_against_context
from .consistency_checker import evaluate_self_consistency
from .uncertainty_estimator import estimate_uncertainty
from .scoring import ScoreBundle, clamp
from .taxonomy import HallucinationCategory


@dataclass
class HallucinationResult:
    module: str
    mode: str
    execution_mode: str
    scores: Dict[str, Optional[float]]
    category: str
    confidence: float
    reasoning: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "module": self.module,
            "mode": self.mode,
            "execution_mode": self.execution_mode,
            "scores": self.scores,
            "category": self.category,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "metadata": self.metadata,
        }


class HallucinationTest:
    """Main hallucination evaluator.

    Automatically selects mode (ground truth, context-grounded, self-consistency)
    and execution mode (evaluation vs monitoring) based on provided data/metadata.
    """

    module_name = "hallucination"

    def __init__(self, enable_judge: bool = False) -> None:
        self.enable_judge = enable_judge

    def evaluate(self, test_case: Dict[str, Any], trace: Dict[str, Any]) -> HallucinationResult:
        execution_mode = detect_execution_mode(trace.get("metadata"))
        mode = detect_hallucination_mode(test_case)

        response = test_case.get("response", "")
        reasoning_parts = []

        if mode == HallucinationMode.GROUND_TRUTH:
            bundle, reasoning = evaluate_against_ground_truth(response, test_case.get("ground_truth", ""))
        elif mode == HallucinationMode.CONTEXT_GROUNDED:
            bundle, reasoning = evaluate_against_context(response, test_case.get("context_documents", []))
        else:
            bundle, reasoning = evaluate_self_consistency(response)
            # In monitoring mode, avoid extra passes; in evaluation mode, optionally blend uncertainty
        reasoning_parts.append(reasoning)

        # Always run lightweight uncertainty estimator to enrich signals (no extra latency)
        unc_bundle, unc_reason = estimate_uncertainty(response)
        reasoning_parts.append(unc_reason)

        merged = self._merge_scores(bundle, unc_bundle)
        overall_risk = self._compute_overall_risk(merged, mode)
        merged.overall_risk = overall_risk

        category = self._pick_category(bundle, unc_bundle)
        confidence = merged.confidence

        return HallucinationResult(
            module=self.module_name,
            mode=mode.value,
            execution_mode=execution_mode.value,
            scores={
                "factual_score": merged.factual_score if merged.factual_score is not None else 0.0,
                "grounding_score": merged.grounding_score if merged.grounding_score is not None else 0.0,
                "consistency_score": merged.consistency_score if merged.consistency_score is not None else 0.0,
                "uncertainty_score": merged.uncertainty_score if merged.uncertainty_score is not None else 0.0,
                "overall_risk": merged.overall_risk,
            },
            category=category.value,
            confidence=confidence,
            reasoning=" | ".join(reasoning_parts),
            metadata={"trace_id": trace.get("trace_id"), "model": trace.get("model"), "mode": mode.value},
        )

    def _merge_scores(self, primary: ScoreBundle, uncertainty: ScoreBundle) -> ScoreBundle:
        return ScoreBundle(
            factual_score=primary.factual_score,
            grounding_score=primary.grounding_score,
            consistency_score=primary.consistency_score,
            uncertainty_score=uncertainty.uncertainty_score,
            overall_risk=primary.overall_risk,
            confidence=max(primary.confidence, uncertainty.confidence),
        )

    def _compute_overall_risk(self, bundle: ScoreBundle, mode: HallucinationMode) -> float:
        # Weighting tuned per mode; deterministic
        if mode == HallucinationMode.GROUND_TRUTH and bundle.factual_score is not None:
            return clamp(1 - bundle.factual_score)
        if mode == HallucinationMode.CONTEXT_GROUNDED and bundle.grounding_score is not None:
            return clamp(1 - bundle.grounding_score)
        # self-consistency: combine consistency and uncertainty
        c = 1 - (bundle.consistency_score or 0)
        u = bundle.uncertainty_score or 0.5
        return clamp(0.5 * c + 0.5 * u)

    def _pick_category(self, primary: ScoreBundle, unc: ScoreBundle):
        if primary.factual_score is not None and primary.factual_score < 0.5:
            return HallucinationCategory.FACTUAL_MISMATCH
        if primary.grounding_score is not None and primary.grounding_score < 0.5:
            return HallucinationCategory.UNSUPPORTED_CLAIM
        if primary.consistency_score is not None and primary.consistency_score < 0.5:
            return HallucinationCategory.SELF_CONTRADICTION
        if (unc.uncertainty_score or 0) < 0.4:
            return HallucinationCategory.OVERCONFIDENT
        return HallucinationCategory.UNKNOWN
