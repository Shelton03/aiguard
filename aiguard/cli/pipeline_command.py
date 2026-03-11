"""``aiguard pipeline`` — starts the evaluation pipeline (no HTTP server).

Usage::

    aiguard pipeline start [--project PROJECT]
"""
from __future__ import annotations

import signal
import time

import typer

pipeline_app = typer.Typer(
    name="pipeline",
    help="Start the evaluation pipeline (trace queue + batch scheduler).",
    no_args_is_help=False,
)


@pipeline_app.callback(invoke_without_command=True)
def pipeline_start(
    ctx: typer.Context,
    project: str = typer.Option("", "--project", help="Project ID (overrides aiguard.yaml)"),
) -> None:
    """Initialise the evaluation pipeline and keep it running."""
    if ctx.invoked_subcommand is not None:
        return

    from config.pipeline_config import load_pipeline_config
    from pipeline.pipeline_router import start_pipeline

    overrides = {}
    if project:
        overrides["project_id"] = project

    config = load_pipeline_config(**overrides)
    components = start_pipeline(config=config)

    typer.echo("✦ AIGuard Evaluation Pipeline")
    typer.echo(f"  Project      : {config.project_id or '(auto)'}")
    typer.echo(f"  Batch interval: {config.evaluation_batch_interval_hours}h")
    typer.echo(f"  Hallucination eval : {'on' if config.enable_hallucination_eval else 'off'}")
    typer.echo(f"  Adversarial eval   : {'on' if config.enable_adversarial_eval else 'off'}")
    typer.echo("\nPipeline running.  Press Ctrl+C to stop.")

    stop = False

    def _handle_sigint(sig, frame):
        nonlocal stop
        stop = True
        typer.echo("\nStopping pipeline…")
        components.scheduler.stop()

    signal.signal(signal.SIGINT, _handle_sigint)
    signal.signal(signal.SIGTERM, _handle_sigint)

    while not stop:
        time.sleep(1)
