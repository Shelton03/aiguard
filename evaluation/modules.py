"""Built-in evaluation module adapters."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List

from adversarial import AttackStorage, load_datasets, load_default_dataset
from adversarial.scoring import HeuristicScorer, ResponseHeuristicScorer
from hallucination.hallucination_test import HallucinationTest

from evaluation.base import BaseEvaluationModule
from evaluation.registry import module_registry
from evaluation.model_client import LiteLLMClient, resolve_model_config


@dataclass
class _ModuleError:
    message: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


def _truncate(text: str, max_len: int = 160) -> str:
    return text if len(text) <= max_len else f"{text[:max_len]}..."


class AdversarialEvaluationModule(BaseEvaluationModule):
    module_name = "adversarial"

    def __init__(self, project_config: Dict[str, Any], mode: str, root_dir: str) -> None:
        super().__init__(project_config, mode, root_dir)
        self._report: Dict[str, Any] = {}
        self._error: _ModuleError | None = None

    def run(self) -> None:
        evaluation_cfg = self.project_config.get("evaluation", {})
        module_cfg = evaluation_cfg.get("adversarial", {})
        project = self.project_config.get("project", "default")
        threshold = module_cfg.get("threshold")
        if threshold is None:
            self._error = _ModuleError("Missing evaluation.adversarial.threshold in aiguard.yaml")
            return

        runs_per_test = int(module_cfg.get("runs_per_test", 3))
        dataset_config = module_cfg.get("dataset_config")
        use_live_model = bool(module_cfg.get("use_live_model", True))
        db_path = Path(self.root_dir) / ".aiguard" / f"{project}.db"
        storage = AttackStorage(db_path=db_path)

        model_client = None
        if use_live_model:
            try:
                model_cfg = resolve_model_config(self.project_config, self.root_dir)
                model_client = LiteLLMClient(model_cfg)
            except ValueError as exc:
                self._error = _ModuleError(str(exc))
                return

        if dataset_config:
            dataset_path = Path(self.root_dir) / dataset_config
            if dataset_path.exists():
                load_datasets(str(dataset_path), storage=storage)
            else:
                # Referenced file doesn't exist — fall back to bundled default
                load_default_dataset(storage=storage)
        else:
            # No dataset_config specified — use bundled default dataset
            load_default_dataset(storage=storage)

        attacks = storage.list_attacks()
        if not attacks:
            self._error = _ModuleError("No attacks found after dataset load")
            return

        if self.mode == "quick":
            limit = int(module_cfg.get("quick_limit", 20))
            attacks = attacks[:limit]

        static_scorer = HeuristicScorer()
        response_scorer = ResponseHeuristicScorer()
        results: List[Dict[str, Any]] = []
        for attack in attacks:
            response_text = ""
            rationale = ""
            if model_client:
                scores = []
                for _ in range(runs_per_test):
                    messages = model_client.build_messages(attack.content)
                    response_text = model_client.run(messages)
                    scored = response_scorer.score(attack, response_text)
                    scores.append(scored.score)
                    rationale = scored.rationale
            else:
                scores = [static_scorer(attack).score for _ in range(runs_per_test)]
            avg_score = sum(scores) / len(scores)
            results.append(
                {
                    "attack_id": attack.attack_id,
                    "attack_type": attack.attack_type.value,
                    "subtype": attack.subtype,
                    "avg_score": avg_score,
                    "content": attack.content,
                    "response": response_text,
                    "rationale": rationale,
                }
            )

        total = len(results)
        failed = [r for r in results if r["avg_score"] >= float(threshold)]
        global_risk = sum(r["avg_score"] for r in results) / total if total else 0.0
        failure_breakdown: Dict[str, int] = {}
        for record in failed:
            failure_breakdown[record["attack_type"]] = failure_breakdown.get(record["attack_type"], 0) + 1

        top_failing = sorted(results, key=lambda r: r["avg_score"], reverse=True)[:5]
        report = {
            "project": project,
            "module": self.module_name,
            "timestamp": _now_iso(),
            "mode": self.mode,
            "total_tests": total,
            "failed_tests": len(failed),
            "global_risk_score": round(global_risk, 6),
            "threshold": float(threshold),
            "status": "fail" if global_risk >= float(threshold) else "pass",
            "failure_breakdown_by_category": failure_breakdown,
            "top_failing_examples": [
                {
                    "attack_id": rec["attack_id"],
                    "attack_type": rec["attack_type"],
                    "subtype": rec["subtype"],
                    "avg_score": round(rec["avg_score"], 6),
                    "content_snippet": _truncate(rec["content"]),
                    "response_snippet": _truncate(rec.get("response", "")),
                    "score_rationale": rec.get("rationale", ""),
                }
                for rec in top_failing
            ],
        }
        self._report = report

    def generate_report(self) -> Dict[str, Any]:
        if self._error:
            return {
                "module": self.module_name,
                "timestamp": _now_iso(),
                "status": "error",
                "error": self._error.message,
            }
        return dict(self._report)

    def exit_code(self) -> int:
        if self._error:
            return 2
        if self._report.get("status") == "fail":
            return 1
        return 0


class HallucinationEvaluationModule(BaseEvaluationModule):
    module_name = "hallucination"

    def __init__(self, project_config: Dict[str, Any], mode: str, root_dir: str) -> None:
        super().__init__(project_config, mode, root_dir)
        self._report: Dict[str, Any] = {}
        self._error: _ModuleError | None = None

    def run(self) -> None:
        evaluation_cfg = self.project_config.get("evaluation", {})
        module_cfg = evaluation_cfg.get("hallucination", {})
        project = self.project_config.get("project", "default")
        threshold = module_cfg.get("threshold")
        test_cases = module_cfg.get("test_cases")
        use_live_model = bool(module_cfg.get("use_live_model", True))
        if threshold is None:
            self._error = _ModuleError("Missing evaluation.hallucination.threshold in aiguard.yaml")
            return
        if not test_cases:
            self._error = _ModuleError("Missing evaluation.hallucination.test_cases in aiguard.yaml")
            return

        if isinstance(test_cases, str):
            test_path = Path(self.root_dir) / test_cases
            if not test_path.exists():
                self._error = _ModuleError(
                    f"Hallucination test_cases file not found: {test_path}"
                )
                return
            test_cases = json.loads(test_path.read_text(encoding="utf-8"))
        if not isinstance(test_cases, list):
            self._error = _ModuleError("Hallucination test_cases must be a list or JSON file path")
            return

        model_client = None
        model_cfg = None
        if use_live_model:
            try:
                model_cfg = resolve_model_config(self.project_config, self.root_dir)
                model_client = LiteLLMClient(model_cfg)
            except ValueError as exc:
                self._error = _ModuleError(str(exc))
                return

        evaluator = HallucinationTest()
        results: List[Dict[str, Any]] = []
        for idx, case in enumerate(test_cases):
            case_payload = dict(case)
            if model_client:
                prompt = case_payload.get("prompt")
                messages = case_payload.get("messages")
                if messages:
                    built_messages = model_client.build_messages("", extra_messages=messages)
                elif prompt:
                    built_messages = model_client.build_messages(str(prompt))
                else:
                    self._error = _ModuleError(
                        "Hallucination test case missing 'prompt' or 'messages' for live model evaluation"
                    )
                    return
                response_text = model_client.run(built_messages)
                case_payload["response"] = response_text

            trace = case.get("trace") or module_cfg.get("default_trace") or {
                "trace_id": case.get("id", f"case-{idx}"),
                "model": model_cfg.model_name if model_cfg else module_cfg.get("model_name", "unknown"),
                "metadata": {"execution_mode": "evaluation"},
            }
            result = evaluator.evaluate(case_payload, trace)
            out = result.to_dict()
            risk = out["scores"]["overall_risk"]
            results.append(
                {
                    "case_id": case.get("id", f"case-{idx}"),
                    "category": out["category"],
                    "overall_risk": float(risk),
                    "reasoning": out.get("reasoning", ""),
                    "response_snippet": _truncate(case_payload.get("response", ""), 200),
                }
            )

        total = len(results)
        failed = [r for r in results if r["overall_risk"] >= float(threshold)]
        global_risk = sum(r["overall_risk"] for r in results) / total if total else 0.0
        failure_breakdown: Dict[str, int] = {}
        for record in failed:
            failure_breakdown[record["category"]] = failure_breakdown.get(record["category"], 0) + 1

        top_failing = sorted(results, key=lambda r: r["overall_risk"], reverse=True)[:5]
        report = {
            "project": project,
            "module": self.module_name,
            "timestamp": _now_iso(),
            "mode": self.mode,
            "total_tests": total,
            "failed_tests": len(failed),
            "global_risk_score": round(global_risk, 6),
            "threshold": float(threshold),
            "status": "fail" if global_risk >= float(threshold) else "pass",
            "failure_breakdown_by_category": failure_breakdown,
            "top_failing_examples": [
                {
                    "case_id": rec["case_id"],
                    "category": rec["category"],
                    "overall_risk": round(rec["overall_risk"], 6),
                    "reasoning": _truncate(rec["reasoning"], 200),
                    "response_snippet": _truncate(rec.get("response_snippet", ""), 200),
                }
                for rec in top_failing
            ],
        }
        self._report = report

    def generate_report(self) -> Dict[str, Any]:
        if self._error:
            return {
                "module": self.module_name,
                "timestamp": _now_iso(),
                "status": "error",
                "error": self._error.message,
            }
        return dict(self._report)

    def exit_code(self) -> int:
        if self._error:
            return 2
        if self._report.get("status") == "fail":
            return 1
        return 0


module_registry.register(AdversarialEvaluationModule.module_name, AdversarialEvaluationModule)
module_registry.register(HallucinationEvaluationModule.module_name, HallucinationEvaluationModule)
