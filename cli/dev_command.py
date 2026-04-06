"""``aiguard dev`` — starts the full development environment in one command.

Launches concurrently:
- The evaluation pipeline (trace queue + batch scheduler)
- The monitoring API server (FastAPI on port 8080)
- The React UI dev server (Vite on port 3000)

Usage::

    aiguard dev [--api-port PORT] [--ui-port PORT]
"""
from __future__ import annotations

import subprocess
import sys
import threading
import time
from pathlib import Path

import typer

from config.pipeline_config import load_pipeline_config
from click.core import ParameterSource

dev_app = typer.Typer(
    name="dev",
    help="Start full development environment (pipeline + API + UI).",
    no_args_is_help=False,
)


@dev_app.callback(invoke_without_command=True)
def dev_start(
    ctx: typer.Context,
    api_port: int = typer.Option(8080, "--api-port", help="Monitoring API port"),
    ui_port: int = typer.Option(3000, "--ui-port", help="React UI dev server port"),
) -> None:
    """Start pipeline + monitoring API + React UI dev server."""
    if ctx.invoked_subcommand is not None:
        return

    config = load_pipeline_config()
    if ctx.get_parameter_source("api_port") == ParameterSource.DEFAULT:
        api_port = config.api_port
    if ctx.get_parameter_source("ui_port") == ParameterSource.DEFAULT:
        ui_port = config.ui_port

    typer.echo("✦ AIGuard Dev Environment")
    typer.echo(f"  Dashboard   →  http://localhost:{ui_port}")
    typer.echo(f"  API         →  http://localhost:{api_port}/docs")
    typer.echo("")

    threads: list[threading.Thread] = []
    procs: list[subprocess.Popen] = []

    # ---- Pipeline -------------------------------------------------------
    def _run_pipeline():
        try:
            from config.pipeline_config import load_pipeline_config
            from pipeline.pipeline_router import start_pipeline

            config = load_pipeline_config(api_port=api_port, ui_port=ui_port)
            components = start_pipeline(config=config)
            typer.echo("  [pipeline] started")
            while True:
                time.sleep(5)
        except Exception as exc:
            typer.echo(f"  [pipeline] error: {exc}", err=True)

    t = threading.Thread(target=_run_pipeline, daemon=True, name="dev-pipeline")
    t.start()
    threads.append(t)

    # ---- Monitoring API -------------------------------------------------
    def _run_api():
        try:
            import uvicorn

            from monitoring.api.server import create_monitoring_app

            typer.echo(f"  [api] starting on port {api_port}")
            uvicorn.run(
                create_monitoring_app(),
                host="0.0.0.0",
                port=api_port,
                log_level="warning",
            )
        except ImportError:
            typer.echo("  [api] uvicorn not installed — skipping", err=True)
        except Exception as exc:
            typer.echo(f"  [api] error: {exc}", err=True)

    t = threading.Thread(target=_run_api, daemon=True, name="dev-api")
    t.start()
    threads.append(t)

    # ---- React UI dev server --------------------------------------------
    ui_dir = Path(__file__).resolve().parents[2] / "monitoring" / "ui"
    if ui_dir.exists() and (ui_dir / "package.json").exists():
        npm_cmd = "npm" if sys.platform != "win32" else "npm.cmd"
        if not (ui_dir / "node_modules").exists():
            typer.echo("  [ui] installing dependencies…")
            try:
                subprocess.run([npm_cmd, "install"], cwd=str(ui_dir), check=False)
            except FileNotFoundError:
                typer.echo("  [ui] npm not found — skipping React dev server", err=True)
                npm_cmd = None
        try:
            if npm_cmd:
                proc = subprocess.Popen(
                    [npm_cmd, "run", "dev", "--", "--port", str(ui_port)],
                    cwd=str(ui_dir),
                )
                procs.append(proc)
                typer.echo(f"  [ui] dev server starting on port {ui_port}")
        except FileNotFoundError:
            typer.echo("  [ui] npm not found — skipping React dev server", err=True)
    else:
        typer.echo(
            "  [ui] monitoring/ui not built yet — run `npm install && npm run build` inside monitoring/ui/",
            err=True,
        )

    typer.echo("\nAll services started.  Press Ctrl+C to stop.\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        typer.echo("\nShutting down…")
        for proc in procs:
            proc.terminate()
