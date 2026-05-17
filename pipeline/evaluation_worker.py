"""Evaluation worker — processes a batch of :class:`~pipeline.event_models.TraceCreatedEvent`
objects and writes results to storage.

Each trace is evaluated by :class:`~hallucination.hallucination_test.HallucinationTest`
(and optionally an adversarial scorer when ``config.enable_adversarial_eval`` is
``True``).  Results are persisted via :class:`~storage.manager.StorageManager` and
returned as :class:`~pipeline.event_models.TraceEvaluatedEvent` objects.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import List

from config.pipeline_config import PipelineConfig
from pipeline.event_models import (
    EvaluationBundle,
    ModuleEvaluationResult,
    TraceCreatedEvent,
    TraceEvaluatedEvent,
)
from storage.manager import StorageManager
from storage.models import EvaluationResultRecord, Trace

try:
    from adversarial.judge import AdversarialJudge
except ImportError:
    AdversarialJudge = None

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_RISK_LABEL_THRESHOLD = 0.5


def _risk_label(overall_risk: float) -> str:
    return "hallucinated" if overall_risk > _RISK_LABEL_THRESHOLD else "safe"


def _prompt_from_messages(messages: list) -> str:
    """Extract a plain-text prompt string from a list of message dicts."""
    parts = []
    for m in messages or []:
        role = m.get("role", "")
        content = m.get("content", "")
        parts.append(f"{role}: {content}" if role else content)
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

class EvaluationWorker:
    """Runs evaluation modules against a batch of traces and persists results.

    Parameters
    ----------
    config:
        Pipeline configuration (controls which modules are enabled).
    storage_root:
        Passed to :class:`~storage.manager.StorageManager`; defaults to
        ``None`` (auto-detect project root).
    """

    def __init__(
        self,
        config: PipelineConfig,
        storage_root: str | None = None,
    ) -> None:
        self._config = config
        self._storage = StorageManager(root=storage_root)

        # Lazy-import heavy evaluation modules so startup is fast even when
        # the optional extras are absent.
        self._hallucination_test = None  # initialised on first use
        self._adversarial_judge = None  # lazy-initialized

        # Initialize adversarial judge if enabled
        if config.enable_adversarial_eval and config.judge.enabled and AdversarialJudge is not None:
            self._adversarial_judge = AdversarialJudge(config.judge)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def process_batch(
        self,
        traces: List[TraceCreatedEvent],
        *,
        force_judge: bool = False,
    ) -> List[TraceEvaluatedEvent]:
        """Evaluate *traces* and return one :class:`TraceEvaluatedEvent` per trace.

        Failures are caught per-trace so one bad trace never aborts the batch.
        """
        if not traces:
            return []

        logger.info("EvaluationWorker: starting batch of %d traces.", len(traces))
        results: List[TraceEvaluatedEvent] = []

        for event in traces:
            try:
                evaluated = self._evaluate_trace(event, force_judge=force_judge)
                results.append(evaluated)
            except Exception:
                logger.exception(
                    "EvaluationWorker: failed to evaluate trace %s — skipping.",
                    event.trace_id,
                )

        logger.info(
            "EvaluationWorker: batch complete. %d/%d traces evaluated.",
            len(results),
            len(traces),
        )
        return results

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _evaluate_trace(self, event: TraceCreatedEvent, *, force_judge: bool = False) -> TraceEvaluatedEvent:
        bundle = EvaluationBundle()

        if self._config.enable_hallucination_eval:
            bundle.hallucination = self._run_hallucination(event, force_judge=force_judge)

        if self._config.enable_adversarial_eval:
            bundle.adversarial = self._run_adversarial(event)

        self._persist(event, bundle)
        return TraceEvaluatedEvent(
            trace_id=event.trace_id,
            project_id=event.project_id,
            evaluation=bundle,
        )

    # ---- Hallucination -----------------------------------------------

    def _run_hallucination(
        self, event: TraceCreatedEvent, *, force_judge: bool = False
    ) -> ModuleEvaluationResult:
        from hallucination.hallucination_test import HallucinationTest  # lazy

        enable_judge = bool(self._config.judge.enabled or force_judge)
        if self._hallucination_test is None or (
            force_judge and not self._hallucination_test.enable_judge
        ):
            self._hallucination_test = HallucinationTest(
                enable_judge=enable_judge,
                judge_config=self._config.judge,
            )

        prompt = _prompt_from_messages(event.input_messages)
        test_case = {
            "response": event.output_text,
            "prompt": prompt,
        }
        trace_dict = {
            "trace_id": event.trace_id,
            "model": event.model,
            "metadata": event.metadata or {},
        }

        result = self._hallucination_test.evaluate(test_case, trace_dict)
        overall_risk = result.scores.get("overall_risk", 0.0) or 0.0
        label = _risk_label(float(overall_risk))

        return ModuleEvaluationResult(
            label=label,
            score=float(overall_risk),
            confidence=float(result.confidence),
            explanation=result.reasoning or "",
            raw=result.to_dict(),
        )

    # ---- Adversarial --------------------------------------------------

    def _run_adversarial(self, event: TraceCreatedEvent) -> ModuleEvaluationResult:
        """Adversarial evaluation using heuristic patterns and optionally LLM judge.

        Runs heuristic pattern check first, then enriches with LLM judge if enabled.
        Falls back to heuristic-only if judge fails.
        """
        prompt = _prompt_from_messages(event.input_messages)
        prompt_lower = prompt.lower()

        # Run heuristic patterns (always runs)
        injection_patterns = [
            "ignore previous instructions",
            "ignore all previous",
            "disregard your instructions",
            "you are now",
            "new instructions:",
            "system prompt:",
            "forget everything",
        ]
        hits = [p for p in injection_patterns if p in prompt_lower]
        subtype_map = {
            "ignore previous instructions": "instruction_override",
            "ignore all previous": "instruction_override",
            "disregard your instructions": "instruction_override",
            "you are now": "roleplay_override",
            "new instructions:": "instruction_override",
            "system prompt:": "system_prompt_exfiltration",
            "forget everything": "instruction_override",
        }
        heuristic_subtypes = sorted({subtype_map.get(hit, "instruction_override") for hit in hits})
        heuristic_score = min(1.0, len(hits) * 0.35)
        heuristic_label = "injection_detected" if heuristic_score > 0.0 else "safe"

        heuristic_explanation = (
            f"Found {len(hits)} injection pattern(s): {', '.join(hits)}"
            if hits
            else "No common injection patterns detected."
        )

        # Default result (heuristic-only)
        label = heuristic_label
        score = heuristic_score
        confidence = 0.75 if hits else 0.90
        explanation = heuristic_explanation
        raw = {
            "patterns_found": hits,
            "score": score,
            "category": "prompt_injection" if hits else "safe",
            "subtypes": heuristic_subtypes,
            "heuristic_only": True,
        }

        # Enrich with LLM judge if available
        if self._adversarial_judge is not None:
            try:
                judge_decision = self._adversarial_judge.evaluate(
                    prompt=prompt,
                    response=event.output_text,
                )
                if judge_decision is not None:
                    # Override with judge results (enrichment)
                    label = judge_decision.label
                    # Blend scores: use heuristic as base, weight judge
                    score = (heuristic_score * 0.4 + (1.0 if judge_decision.label == "injection_detected" else 0.0) * 0.6)
                    score = min(1.0, score)
                    confidence = judge_decision.confidence

                    # Build enriched explanation
                    judge_part = f" [Judge: {judge_decision.attack_type.value}/{judge_decision.subtype} ({judge_decision.severity})]"
                    explanation = heuristic_explanation + judge_part

                    # Update raw with judge info
                    raw = {
                        "patterns_found": hits,
                        "score": score,
                        "category": judge_decision.attack_type.value if judge_decision.attack_type else "unknown",
                        "subtypes": [judge_decision.subtype] + heuristic_subtypes if judge_decision.subtype != "unknown" else heuristic_subtypes,
                        "heuristic_only": False,
                        "judge": {
                            "label": judge_decision.label,
                            "attack_type": judge_decision.attack_type.value if judge_decision.attack_type else None,
                            "subtype": judge_decision.subtype,
                            "severity": judge_decision.severity,
                            "confidence": judge_decision.confidence,
                            "rationale": judge_decision.rationale,
                        },
                    }
            except Exception:
                # Judge failed, fallback to heuristic-only
                logger.warning(
                    "EvaluationWorker: adversarial judge failed for trace %s, falling back to heuristic",
                    event.trace_id,
                )

        return ModuleEvaluationResult(
            label=label,
            score=score,
            confidence=confidence,
            explanation=explanation,
            raw=raw,
        )

    # ---- Persistence -------------------------------------------------

    def _persist(self, event: TraceCreatedEvent, bundle: EvaluationBundle) -> None:
        # ----- Trace record -----
        prompt = _prompt_from_messages(event.input_messages)
        tokens_used: int | None = None
        if event.token_usage:
            tokens_used = (event.token_usage.get("total_tokens") or
                           event.token_usage.get("prompt_tokens", 0) +
                           event.token_usage.get("completion_tokens", 0))
        trace = Trace(
            id=event.trace_id,
            timestamp=event.timestamp
            if isinstance(event.timestamp, datetime)
            else datetime.fromisoformat(str(event.timestamp)),
            model_name=event.model or "unknown",
            model_version=None,
            prompt=prompt,
            response=event.output_text or "",
            latency_ms=float(event.latency_ms or 0),
            tokens_used=tokens_used,
            environment="production",
            metadata={
                **(event.metadata or {}),
                "project_id": event.project_id,
                "provider": event.provider,
            },
        )
        try:
            self._storage.save_trace(trace)
        except Exception:
            logger.exception("EvaluationWorker: failed to persist trace %s", event.trace_id)

        # ----- EvaluationResultRecord for each module -----
        now = datetime.now(tz=timezone.utc)
        if bundle.hallucination is not None:
            r = bundle.hallucination
            raw = r.raw or {}
            try:
                self._storage.delete_evaluations(event.trace_id, "hallucination")
            except Exception:
                logger.exception(
                    "EvaluationWorker: failed to clear hallucination eval for %s",
                    event.trace_id,
                )
            rec = EvaluationResultRecord(
                id=str(uuid.uuid4()),
                trace_id=event.trace_id,
                test_case_id="",
                module="hallucination",
                mode=raw.get("mode", "unknown"),
                execution_mode=raw.get("execution_mode", "monitoring"),
                scores=raw.get("scores", {"overall_risk": r.score}),
                category=raw.get("category", "unknown"),
                risk_level=r.label,
                confidence=r.confidence,
                metadata=raw.get("metadata", {}),
                created_at=now,
            )
            try:
                self._storage.save_evaluation(rec)
            except Exception:
                logger.exception(
                    "EvaluationWorker: failed to persist hallucination eval for %s",
                    event.trace_id,
                )

        if bundle.adversarial is not None:
            r = bundle.adversarial
            try:
                self._storage.delete_evaluations(event.trace_id, "adversarial")
            except Exception:
                logger.exception(
                    "EvaluationWorker: failed to clear adversarial eval for %s",
                    event.trace_id,
                )
            rec = EvaluationResultRecord(
                id=str(uuid.uuid4()),
                trace_id=event.trace_id,
                test_case_id="",
                module="adversarial",
                mode="injection_check",
                execution_mode="monitoring",
                scores={"score": r.score},
                category="prompt_injection",
                risk_level=r.label,
                confidence=r.confidence,
                metadata=r.raw or {},
                created_at=now,
            )
            try:
                self._storage.save_evaluation(rec)
            except Exception:
                logger.exception(
                    "EvaluationWorker: failed to persist adversarial eval for %s",
                    event.trace_id,
                )
