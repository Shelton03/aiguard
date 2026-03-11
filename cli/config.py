"""Project configuration loading utilities for the CLI."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from storage.project import CONFIG_FILE, load_config, sanitize_project


class ConfigError(RuntimeError):
    """Raised when project configuration is missing or invalid."""


def load_project_config(root: Path, project_override: Optional[str]) -> dict:
    cfg_path = root / CONFIG_FILE
    if not cfg_path.exists():
        raise ConfigError(
            f"Missing {CONFIG_FILE}. Run 'aiguard project init' or create {CONFIG_FILE} manually."
        )
    config = load_config(root)
    if not isinstance(config, dict):
        raise ConfigError(f"Invalid {CONFIG_FILE}: expected a mapping at the top level")
    if project_override:
        config["project"] = project_override
    return config


def resolve_project_name(config: dict, root: Path, project_override: Optional[str]) -> str:
    if project_override:
        return sanitize_project(project_override)
    if config.get("project"):
        return sanitize_project(str(config["project"]))
    return sanitize_project(root.name)
