"""``aiguard dev`` — starts the full development environment in one command.

Launches concurrently:
- The evaluation pipeline (trace queue + batch scheduler)
- The monitoring API server (FastAPI on port 8080)
- The React UI preview server (Vite on port 3000)

Usage::

    aiguard dev [--api-port PORT] [--ui-port PORT]
"""
from __future__ import annotations

import subprocess
import threading
import time
from pathlib import Path
import socket

import typer

from config.pipeline_config import load_pipeline_config
from click.core import ParameterSource
from cli.monitor_command import _start_ui_preview

dev_app = typer.Typer(
    name="dev",
    help="Start full development environment (pipeline + API + UI).",
    no_args_is_help=False,
)


@dev_app.callback(invoke_without_command=True)
def dev_start(
    ctx: typer.Context,
    api_port: int = typer.Option(8080, "--api-port", help="Monitoring API port"),
    ui_port: int = typer.Option(3000, "--ui-port", help="Monitoring UI port"),
) -> None:
    """Start pipeline + monitoring API + React UI preview server."""
    if ctx.invoked_subcommand is not None:
        return

    config = load_pipeline_config()
    if ctx.get_parameter_source("api_port") == ParameterSource.DEFAULT:
        api_port = config.api_port
    if ctx.get_parameter_source("ui_port") == ParameterSource.DEFAULT:
        ui_port = config.ui_port

    requested_api_port = api_port
    requested_ui_port = ui_port
    api_port = _pick_available_port(api_port, "0.0.0.0")
    ui_port = _pick_available_port(ui_port, "127.0.0.1")

    typer.echo("✦ AIGuard Dev Environment")
    if api_port != requested_api_port:
        typer.echo(f"  [api] port {requested_api_port} in use, using {api_port}")
    if ui_port != requested_ui_port:
        typer.echo(f"  [ui] port {requested_ui_port} in use, using {ui_port}")
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

    # ---- React UI preview server ----------------------------------------
    ui_proc = _start_ui_preview(ui_port)
    if ui_proc is not None:
        procs.append(ui_proc)

    typer.echo("\nAll services started.  Press Ctrl+C to stop.\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        typer.echo("\nShutting down…")
        for proc in procs:
            proc.terminate()


def _is_port_available(port: int, host: str) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def _pick_available_port(port: int, host: str, max_tries: int = 20) -> int:
    candidate = port
    for _ in range(max_tries):
        if _is_port_available(candidate, host):
            return candidate
        candidate += 1
    return port
