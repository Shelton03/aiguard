"""Judge configuration — loaded from aiguard.yaml (local LLM endpoint)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class JudgeConfig:
    """Runtime config for the LLM-as-judge layer."""

    enabled: bool = False
    provider: str = "local"
    endpoint: str = "http://localhost:11434/v1"
    model: str = "llama3.1:8b"
    api_key_env: Optional[str] = None
    timeout_s: float = 8.0
    max_tokens: int = 256
    temperature: float = 0.0

    def resolve_api_key(self) -> Optional[str]:
        if not self.api_key_env:
            return None
        return os.getenv(self.api_key_env)


def load_judge_config(root: Optional[Path] = None) -> JudgeConfig:
    """Read the judge config from aiguard.yaml, falling back to defaults."""
    config_path = (root or Path(os.getcwd())) / "aiguard.yaml"
    if not config_path.exists():
        return JudgeConfig()

    try:
        import yaml  # type: ignore[import]

        with config_path.open() as fh:
            doc: Dict[str, Any] = yaml.safe_load(fh) or {}
        judge_section: Dict[str, Any] = doc.get("judge", {}) or {}

        return JudgeConfig(
            enabled=bool(judge_section.get("enabled", False)),
            provider=str(judge_section.get("provider", "local")),
            endpoint=str(judge_section.get("endpoint", "http://localhost:11434/v1")),
            model=str(judge_section.get("model", "llama3.1:8b")),
            api_key_env=judge_section.get("api_key_env"),
            timeout_s=float(judge_section.get("timeout_s", 8.0)),
            max_tokens=int(judge_section.get("max_tokens", 256)),
            temperature=float(judge_section.get("temperature", 0.0)),
        )
    except Exception:
        return JudgeConfig()
