"""Pipeline configuration — loaded from the ``pipeline:`` section of ``aiguard.yaml``."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class PipelineConfig:
    """Runtime configuration for the pipeline and monitoring system."""

    # Batch scheduler
    evaluation_batch_interval_hours: float = 3.0
    """How often (in hours) the batch scheduler triggers evaluation workers."""

    max_batch_size: int = 500
    """Maximum number of traces evaluated in a single worker batch."""

    # Monitoring API
    api_host: str = "0.0.0.0"
    api_port: int = 8080
    """Host/port for the monitoring FastAPI server."""

    # UI dev server
    ui_port: int = 3000
    """Port for the Vite / React dev server."""

    # Modules to run during evaluation
    enable_hallucination_eval: bool = True
    enable_adversarial_eval: bool = False
    """Adversarial evaluation per-trace is expensive; disabled by default."""

    # Pipeline project scope
    project_id: str = ""
    """If non-empty, only traces with this project_id are evaluated."""

    extra: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.evaluation_batch_interval_hours <= 0:
            raise ValueError("evaluation_batch_interval_hours must be > 0")
        if self.max_batch_size <= 0:
            raise ValueError("max_batch_size must be > 0")


def load_pipeline_config(
    root: Optional[Path] = None,
    **overrides: Any,
) -> PipelineConfig:
    """Read ``aiguard.yaml`` and return a :class:`PipelineConfig`.

    Explicit *overrides* take the highest priority.
    """
    raw: Dict[str, Any] = {}

    config_path = (root or Path(os.getcwd())) / "aiguard.yaml"
    if config_path.exists():
        try:
            import yaml  # type: ignore[import]

            with config_path.open() as fh:
                doc: Dict[str, Any] = yaml.safe_load(fh) or {}

            pipeline_section: Dict[str, Any] = doc.get("pipeline", {}) or {}
            monitoring_section: Dict[str, Any] = doc.get("monitoring", {}) or {}

            raw["evaluation_batch_interval_hours"] = pipeline_section.get(
                "evaluation_batch_interval_hours", 3.0
            )
            raw["max_batch_size"] = pipeline_section.get("max_batch_size", 500)
            raw["enable_hallucination_eval"] = pipeline_section.get(
                "enable_hallucination_eval", True
            )
            raw["enable_adversarial_eval"] = pipeline_section.get(
                "enable_adversarial_eval", False
            )
            raw["project_id"] = pipeline_section.get("project_id", "")

            api_section: Dict[str, Any] = monitoring_section.get("api", {}) or {}
            raw["api_host"] = api_section.get("host", "0.0.0.0")
            raw["api_port"] = api_section.get("port", 8080)
            raw["ui_port"] = monitoring_section.get("ui_port", 3000)

        except Exception:
            # Malformed YAML — fall back to defaults silently
            pass

    raw.update(overrides)

    return PipelineConfig(
        evaluation_batch_interval_hours=raw.get("evaluation_batch_interval_hours", 3.0),
        max_batch_size=raw.get("max_batch_size", 500),
        enable_hallucination_eval=raw.get("enable_hallucination_eval", True),
        enable_adversarial_eval=raw.get("enable_adversarial_eval", False),
        project_id=raw.get("project_id", ""),
        api_host=raw.get("api_host", "0.0.0.0"),
        api_port=raw.get("api_port", 8080),
        ui_port=raw.get("ui_port", 3000),
    )
