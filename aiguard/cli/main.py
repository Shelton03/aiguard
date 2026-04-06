"""Typer-based CLI entrypoint for AIGuard."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer

from aiguard.evaluation.registry import module_registry as registry

from .config import ConfigError, load_project_config, resolve_project_name
from .exit_codes import aggregate_exit_codes
from .reporting import write_report
from .services import (
    CalibrationService,
    ProjectService,
    ReviewServer,
    ReviewService,
    StorageService,
)
from .monitor_command import monitor_app as _monitor_app_impl
from .pipeline_command import pipeline_app
from .dev_command import dev_app
from .templates import github_template, gitlab_template

app = typer.Typer(help="AIGuard CLI — orchestration for evaluation, monitoring, and review")
project_app = typer.Typer(help="Project configuration commands")
evaluate_app = typer.Typer(help="Run evaluation modules")
monitor_app = _monitor_app_impl
review_app = typer.Typer(help="Human review commands")
storage_app = typer.Typer(help="Storage backend commands")
ci_app = typer.Typer(help="CI template generator")

app.add_typer(project_app, name="project")
app.add_typer(evaluate_app, name="evaluate")
app.add_typer(monitor_app, name="monitor")
app.add_typer(pipeline_app, name="pipeline")
app.add_typer(dev_app, name="dev")
app.add_typer(review_app, name="review")
app.add_typer(storage_app, name="storage")
app.add_typer(ci_app, name="ci")


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


def _render_project_template(project: str) -> str:
    return f"""project: {project}

model:
  provider: openai
  endpoint: https://api.openai.com/v1
  model_name: gpt-4o
  api_key_env: OPENAI_API_KEY
    system_prompt_path: prompt_template.py
    tools_path: tools.py

evaluation:
  enabled_modules:
    - adversarial
    - hallucination
  adversarial:
    threshold: 0.15
    mode: quick
    runs_per_test: 3
    # dataset_config: datasets.json  # omit to use the bundled default adversarial dataset
        use_live_model: true
  hallucination:
    threshold: 0.25
        test_cases: hallucination_test_cases.json
        use_live_model: true

monitoring:
  enabled: true
  sampling_rate: 1.0
  queue_maxsize: 10000
  api:
    host: "0.0.0.0"
    port: 8080
  ui_port: 3000

pipeline:
  evaluation_batch_interval_hours: 3
  max_batch_size: 500
  enable_hallucination_eval: true
  enable_adversarial_eval: false
  project_id: ""

storage: sqlite
"""


def _run_module(module_name: str, config: dict, mode: str, root: Path):
    module_cls = registry.get(module_name)
    module = module_cls(config, mode, str(root))
    module.run()
    report = module.generate_report()
    exit_code = module.exit_code()
    return report, exit_code


def _handle_error(exc: Exception) -> None:
    typer.echo(f"ERROR: {exc}", err=True)
    raise typer.Exit(code=2)


@project_app.command("init")
def project_init(
    project: Optional[str] = typer.Option(None, "--project", help="Project name"),
    output: Path = typer.Option(Path("aiguard.yaml"), "--output", help="Output config path"),
    force: bool = typer.Option(False, "--force", help="Overwrite existing config"),
) -> None:
    root = Path.cwd()
    service = ProjectService(root)
    name = project or root.name
    content = _render_project_template(name)
    try:
        service.init_project_config(output, content, force)
    except Exception as exc:
        _handle_error(exc)
    typer.echo(f"Wrote {output}")
    typer.echo(
        "Using bundled adversarial dataset (~262k attacks). "
        "Set evaluation.adversarial.dataset_config in aiguard.yaml to use a custom dataset."
    )


@project_app.command("list")
def project_list() -> None:
    service = ProjectService(Path.cwd())
    for name in service.list_projects():
        typer.echo(name)


@project_app.command("delete")
def project_delete(project: str, force: bool = typer.Option(False, "--force")) -> None:
    if not force:
        confirmation = typer.prompt(f"Type '{project}' to confirm deletion")
        if confirmation != project:
            typer.echo("Aborted")
            raise typer.Exit(code=1)
    try:
        ProjectService(Path.cwd()).delete_project(project)
    except Exception as exc:
        _handle_error(exc)
    typer.echo(f"Deleted project {project}")


@project_app.command("export")
def project_export(
    project: str,
    output: Optional[Path] = typer.Option(None, "--output", help="Output JSON file"),
) -> None:
    try:
        data = ProjectService(Path.cwd()).export_project(project)
    except Exception as exc:
        _handle_error(exc)
    payload = json.dumps(data, indent=2)
    if output:
        output.write_text(payload)
        typer.echo(f"Exported to {output}")
    else:
        typer.echo(payload)


@evaluate_app.callback(invoke_without_command=True)
def evaluate_all(
    ctx: typer.Context,
    project: Optional[str] = typer.Option(None, "--project", help="Project name"),
    output: Optional[Path] = typer.Option(None, "--output", help="Write JSON report"),
    mode: str = typer.Option("quick", "--mode", help="Evaluation mode"),
) -> None:
    if ctx.invoked_subcommand is not None:
        return

    root = Path.cwd()
    try:
        config = load_project_config(root, project)
    except Exception as exc:
        _handle_error(exc)

    project_name = resolve_project_name(config, root, project)
    evaluation_cfg = config.get("evaluation", {})
    enabled = evaluation_cfg.get("enabled_modules") or []
    if not enabled:
        _handle_error(ConfigError("No evaluation.enabled_modules configured"))

    reports = []
    codes = []
    for name in enabled:
        try:
            report, code = _run_module(name, config, mode, root)
        except Exception as exc:
            _handle_error(exc)
        reports.append(report)
        codes.append(code)

    aggregate_code = aggregate_exit_codes(codes)
    combined = {
        "project": project_name,
        "timestamp": _now_iso(),
        "status": "error" if aggregate_code == 2 else "fail" if aggregate_code == 1 else "pass",
        "modules": reports,
    }
    if output:
        write_report(output, combined)
        typer.echo(f"Wrote {output}")
    typer.echo(json.dumps(combined, indent=2))
    raise typer.Exit(code=aggregate_code)


def _register_module_command(module_name: str) -> None:
    def _cmd(
        project: Optional[str] = typer.Option(None, "--project", help="Project name"),
        output: Optional[Path] = typer.Option(None, "--output", help="Write JSON report"),
        mode: str = typer.Option("quick", "--mode", help="Evaluation mode"),
    ) -> None:
        root = Path.cwd()
        try:
            config = load_project_config(root, project)
        except Exception as exc:
            _handle_error(exc)

        try:
            report, code = _run_module(module_name, config, mode, root)
        except Exception as exc:
            _handle_error(exc)

        if output:
            write_report(output, report)
            typer.echo(f"Wrote {output}")
        typer.echo(json.dumps(report, indent=2))
        raise typer.Exit(code=code)

    evaluate_app.command(module_name)(_cmd)


def _register_module_commands() -> None:
    for name in registry.available():
        _register_module_command(name)


_register_module_commands()


@review_app.command("serve")
def review_serve(port: Optional[int] = typer.Option(None, "--port", help="Port to listen on")) -> None:
    try:
        ReviewServer().start(port)
    except Exception as exc:
        _handle_error(exc)


@review_app.command("list")
def review_list(project: str) -> None:
    try:
        data = ReviewService(Path.cwd()).list_items(project)
    except Exception as exc:
        _handle_error(exc)
    typer.echo(json.dumps(data, indent=2))


@review_app.command("calibrate")
def review_calibrate(project: str) -> None:
    try:
        CalibrationService(Path.cwd()).force_update(project)
    except Exception as exc:
        _handle_error(exc)
    typer.echo(f"Calibration updated for {project}")


@storage_app.command("migrate")
def storage_migrate(to: str = typer.Option(..., "--to", help="Target backend: sqlite or postgres")) -> None:
    try:
        StorageService(Path.cwd()).migrate(to)
    except Exception as exc:
        _handle_error(exc)
    typer.echo(f"Migration to {to} completed")


@storage_app.command("info")
def storage_info() -> None:
    try:
        info = StorageService(Path.cwd()).info()
    except Exception as exc:
        _handle_error(exc)
    typer.echo(json.dumps(info, indent=2))


@ci_app.command("template")
def ci_template(provider: str, project: str) -> None:
    if provider == "github":
        typer.echo(github_template(project))
        return
    if provider == "gitlab":
        typer.echo(gitlab_template(project))
        return
    _handle_error(ConfigError("Provider must be 'github' or 'gitlab'"))
