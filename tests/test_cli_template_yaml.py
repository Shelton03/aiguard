"""Regression tests for generated `aiguard.yaml` template validity."""
from __future__ import annotations

import yaml

from cli.main import _render_project_template


def test_rendered_project_template_is_valid_yaml() -> None:
    rendered = _render_project_template("demo-project")
    data = yaml.safe_load(rendered)

    assert isinstance(data, dict)
    assert data["project"] == "demo-project"


def test_rendered_project_template_has_expected_nested_keys() -> None:
    data = yaml.safe_load(_render_project_template("demo-project"))

    assert data["model"]["api_key_env"] == "OPENAI_API_KEY"
    assert data["model"]["system_prompt_path"] == "prompt_template.py"
    assert data["evaluation"]["adversarial"]["use_live_model"] is True
    assert data["evaluation"]["hallucination"]["test_cases"] == "hallucination_test_cases.json"
    assert data["monitoring"]["api"]["port"] == 8080
    assert data["review"]["port"] == 8000
    assert data["judge"]["endpoint"] == "http://localhost:11434/v1"
