"""Project resolution utilities."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

CONFIG_FILE = "aiguard.yaml"


def sanitize_project(name: str) -> str:
    name = name.lower().replace("-", "_")
    name = re.sub(r"[^a-z0-9_]+", "", name)
    return name or "default"


def load_config(root: Path) -> dict:
    cfg_path = root / CONFIG_FILE
    if not cfg_path.exists():
        return {}
    try:
        import yaml  # type: ignore

        return yaml.safe_load(cfg_path.read_text()) or {}
    except Exception:
        return {}


def resolve_project(root: Path) -> str:
    env = os.getenv("AIGUARD_PROJECT")
    if env:
        return sanitize_project(env)
    cfg = load_config(root)
    if cfg.get("project"):
        return sanitize_project(str(cfg["project"]))
    return sanitize_project(root.name)
