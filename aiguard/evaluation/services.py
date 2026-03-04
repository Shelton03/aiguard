from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
import json
import sys


@dataclass
class ProjectConfig:
    project: str
    model: Dict[str, Any]
    evaluation: Dict[str, Any]

    @staticmethod
    def load(path: Path) -> "ProjectConfig":
        import yaml  # lazy import

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return ProjectConfig(
            project=data["project"],
            model=data.get("model", {}),
            evaluation=data.get("evaluation", {}),
        )


class EvaluationService:
    """Coordinates evaluation runs across modules."""

    def __init__(self, registry, stdout=None) -> None:
        self.registry = registry
        self.stdout = stdout or sys.stdout

    def run_enabled_modules(
        self,
        project_cfg: ProjectConfig,
        output: Optional[Path] = None,
    ) -> int:
        enabled = project_cfg.evaluation.get("enabled_modules", [])
        if not enabled:
            print("No enabled modules in config", file=self.stdout)
            return 0
        exit_codes: List[int] = []
        for name in enabled:
            exit_codes.append(self._run_single_module(name, project_cfg, output))
        # deterministic: highest (worst) exit code wins
        return max(exit_codes) if exit_codes else 0

    def run_single_module(
        self,
        name: str,
        project_cfg: ProjectConfig,
        output: Optional[Path] = None,
    ) -> int:
        return self._run_single_module(name, project_cfg, output)

    # internal helpers
    def _run_single_module(self, name: str, project_cfg: ProjectConfig, output: Optional[Path]) -> int:
        module = self.registry.create(name)
        mode = project_cfg.evaluation.get(name, {}).get("mode", "quick")
        try:
            module.run(project_cfg.__dict__, mode)
        except Exception as exc:  # pragma: no cover - passthrough to caller
            print(f"[error] Module '{name}' failed: {exc}", file=self.stdout)
            return 2

        report = module.generate_report()
        if output:
            self._write_report(output, report)
        else:
            print(json.dumps(report, indent=2), file=self.stdout)
        return module.exit_code()

    def _write_report(self, path: Path, report: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)


class ProjectService:
    """Stub service for project lifecycle operations."""

    def __init__(self, base_dir: Path | None = None, stdout=None) -> None:
        self.base_dir = base_dir or Path.cwd()
        self.stdout = stdout or sys.stdout

    def init(self, name: str) -> None:
        print(f"[stub] Initialize project '{name}'", file=self.stdout)

    def list(self) -> List[str]:
        print("[stub] List projects", file=self.stdout)
        return []

    def delete(self, name: str, force: bool = False) -> None:
        print(f"[stub] Delete project '{name}' force={force}", file=self.stdout)

    def export(self, name: str, dest: Path) -> None:
        print(f"[stub] Export project '{name}' to {dest}", file=self.stdout)


class MonitoringService:
    def start(self, project: str) -> None:
        print(f"[stub] Start monitoring for project '{project}'")


class ReviewService:
    def serve(self, port: int | None = None) -> None:
        print(f"[stub] Start review server on port {port or 8000}")

    def list(self, project: str | None = None) -> None:
        print(f"[stub] List reviews for project '{project or 'all'}'")

    def calibrate(self, project: str) -> None:
        print(f"[stub] Calibrate review scores for project '{project}'")


class StorageService:
    def migrate(self, project: str, target: str) -> None:
        print(f"[stub] Migrate storage for project '{project}' to {target}")

    def info(self, project: str) -> None:
        print(f"[stub] Show storage info for project '{project}'")


class CITemplateService:
    GITHUB_TEMPLATE = """name: AIGuard Evaluation

on:
  workflow_dispatch:
  pull_request:

jobs:
  evaluate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install
        run: |
          pip install .[review]
      - name: Run AIGuard
        run: |
          aiguard evaluate --project {project}
"""

    GITLAB_TEMPLATE = """stages:
  - evaluate

aiguard_evaluate:
  stage: evaluate
  image: python:3.11-slim
  script:
    - pip install .[review]
    - aiguard evaluate --project {project}
"""

    def print_template(self, provider: str, project: str) -> None:
        provider = provider.lower()
        if provider == "github":
            print(self.GITHUB_TEMPLATE.format(project=project))
        elif provider == "gitlab":
            print(self.GITLAB_TEMPLATE.format(project=project))
        else:
            raise ValueError("Unsupported provider; choose 'github' or 'gitlab'")
