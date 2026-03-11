"""Built-in evaluation module adapters."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from adversarial import AttackStorage, load_datasets
from adversarial.scoring import HeuristicScorer
from adversarial.data import builtin_datasets_json
from hallucination.hallucination_test import HallucinationTest

from evaluation.base import BaseEvaluationModule
from evaluation.registry import module_registry


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
        dataset_config = module_cfg.get("dataset_config", "datasets.json")
        dataset_path = Path(self.root_dir) / dataset_config

        if not dataset_path.exists():
            # Fall back to the built-in dataset shipped with the package.
            dataset_path = builtin_datasets_json()

        db_path = Path(self.root_dir) / ".aiguard" / f"{project}.db"
        storage = AttackStorage(db_path=db_path)
        load_datasets(str(dataset_path), storage=storage)

        attacks = storage.list_attacks()
        if not attacks:
            self._error = _ModuleError("No attacks found after dataset load")
            return

        if self.mode == "quick":
            limit = int(module_cfg.get("quick_limit", 20))
            attacks = attacks[:limit]

        scorer = HeuristicScorer()
        results: List[Dict[str, Any]] = []
        for attack in attacks:
            scores = [scorer(attack).score for _ in range(runs_per_test)]
            avg_score = sum(scores) / len(scores)
            results.append(
                {
                    "attack_id": attack.attack_id,
                    "attack_type": attack.attack_type.value,
                    "subtype": attack.subtype,
                    "avg_score": avg_score,
                    "content": attack.content,
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
        if threshold is None:
            self._error = _ModuleError("Missing evaluation.hallucination.threshold in aiguard.yaml")
            return
        if not test_cases:
            self._error = _ModuleError("Missing evaluation.hallucination.test_cases in aiguard.yaml")
            return

        evaluator = HallucinationTest()
        results: List[Dict[str, Any]] = []
        for idx, case in enumerate(test_cases):
            trace = case.get("trace") or module_cfg.get("default_trace") or {
                "trace_id": case.get("id", f"case-{idx}"),
                "model": module_cfg.get("model_name", "unknown"),
                "metadata": {"execution_mode": "evaluation"},
            }
            result = evaluator.evaluate(case, trace)
            out = result.to_dict()
            risk = out["scores"]["overall_risk"]
            results.append(
                {
                    "case_id": case.get("id", f"case-{idx}"),
                    "category": out["category"],
                    "overall_risk": float(risk),
                    "reasoning": out.get("reasoning", ""),
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
