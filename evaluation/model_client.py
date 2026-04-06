"""LiteLLM-backed model client used by CLI evaluations."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import os

from sdk.client import _call_litellm, _extract_output_text


@dataclass
class ModelConfig:
    provider: str
    endpoint: Optional[str]
    model_name: str
    api_key_env: str
    system_prompt: Optional[str]


def resolve_system_prompt(model_cfg: Dict[str, Any], root_dir: str) -> Optional[str]:
    prompt = model_cfg.get("system_prompt")
    prompt_path = model_cfg.get("system_prompt_path")
    if prompt_path:
        path = Path(root_dir) / prompt_path
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
    if isinstance(prompt, str) and prompt.strip():
        return prompt.strip()
    return None


def resolve_model_config(project_config: Dict[str, Any], root_dir: str) -> ModelConfig:
    model_cfg = project_config.get("model", {})
    provider = str(model_cfg.get("provider", "openai"))
    endpoint = model_cfg.get("endpoint")
    model_name = model_cfg.get("model_name")
    api_key_env = model_cfg.get("api_key_env")
    if not model_name:
        raise ValueError("Missing model.model_name in aiguard.yaml")
    if not api_key_env:
        raise ValueError("Missing model.api_key_env in aiguard.yaml")
    system_prompt = resolve_system_prompt(model_cfg, root_dir)
    return ModelConfig(
        provider=provider,
        endpoint=str(endpoint) if endpoint else None,
        model_name=str(model_name),
        api_key_env=str(api_key_env),
        system_prompt=system_prompt,
    )


class LiteLLMClient:
    def __init__(self, config: ModelConfig) -> None:
        self.config = config
        api_key = os.getenv(config.api_key_env)
        if not api_key:
            raise ValueError(
                f"Missing API key: env var '{config.api_key_env}' is not set"
            )
        self.api_key = api_key

    def build_messages(self, user_prompt: str, extra_messages: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        messages: List[Dict[str, Any]] = []
        if self.config.system_prompt:
            messages.append({"role": "system", "content": self.config.system_prompt})
        if extra_messages:
            messages.extend(extra_messages)
        if user_prompt:
            messages.append({"role": "user", "content": user_prompt})
        return messages

    def run(self, messages: List[Dict[str, Any]]) -> str:
        kwargs: Dict[str, Any] = {"api_key": self.api_key}
        if self.config.endpoint:
            kwargs["api_base"] = self.config.endpoint
        response = _call_litellm(self.config.model_name, messages, **kwargs)
        text = _extract_output_text(response)
        return text or ""
