"""``aiguard monitor`` — starts the monitoring API server.

Usage::

    aiguard monitor [--host HOST] [--port PORT]
    aiguard monitor ui
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

monitor_app = typer.Typer(
    name="monitor",
    help="Start the AIGuard monitoring API server.",
    no_args_is_help=False,
)


@monitor_app.callback(invoke_without_command=True)
def monitor_start(
    ctx: typer.Context,
    host: str = typer.Option("0.0.0.0", "--host", help="Bind host"),
    port: int = typer.Option(8080, "--port", "-p", help="API port"),
    ui_port: int = typer.Option(3000, "--ui-port", help="Monitoring UI port"),
) -> None:
    """Start the monitoring FastAPI server on *host*:*port*."""
    if ctx.invoked_subcommand is not None:
        return

    config = load_pipeline_config()
    if ctx.get_parameter_source("host") == ParameterSource.DEFAULT:
        host = config.api_host
    if ctx.get_parameter_source("port") == ParameterSource.DEFAULT:
        port = config.api_port
    if ctx.get_parameter_source("ui_port") == ParameterSource.DEFAULT:
        ui_port = config.ui_port

    try:
        import uvicorn
    except ImportError:
        typer.echo(
            "Error: uvicorn is not installed.  Run:\n"
            "  pip install 'aiguard[monitoring]'",
            err=True,
        )
        raise typer.Exit(code=1)

    from monitoring.api.server import create_monitoring_app

    typer.echo("✦ AIGuard Monitoring")
    typer.echo(f"  Dashboard   →  http://localhost:{ui_port}")
    typer.echo(f"  API         →  http://{host}:{port}/docs")
    typer.echo("")

    procs: list[subprocess.Popen] = []

    # ---- Monitoring API -------------------------------------------------
    def _run_api() -> None:
        try:
            app = create_monitoring_app()
            uvicorn.run(app, host=host, port=port, log_level="warning")
        except Exception as exc:
            typer.echo(f"  [api] error: {exc}", err=True)

    t = threading.Thread(target=_run_api, daemon=True, name="monitor-api")
    t.start()

    # ---- Monitoring UI --------------------------------------------------
    ui_proc = _start_ui_preview(ui_port)
    if ui_proc is not None:
        procs.append(ui_proc)

    typer.echo("\nAll services started. Press Ctrl+C to stop.\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        typer.echo("\nShutting down…")
        for proc in procs:
            proc.terminate()


def _ensure_ui_ready(ui_dir: Path, build: bool) -> bool:
    if not ui_dir.exists() or not (ui_dir / "package.json").exists():
        typer.echo("  [ui] monitoring/ui not found — skipping", err=True)
        return False

    npm_cmd = "npm" if sys.platform != "win32" else "npm.cmd"
    if not (ui_dir / "node_modules").exists():
        typer.echo("  [ui] installing dependencies…")
        try:
            subprocess.run([npm_cmd, "install"], cwd=str(ui_dir), check=False)
        except FileNotFoundError:
            typer.echo("  [ui] npm not found — skipping", err=True)
            return False

    if build and not (ui_dir / "dist").exists():
        typer.echo("  [ui] building production bundle…")
        subprocess.run([npm_cmd, "run", "build"], cwd=str(ui_dir), check=False)

    return True


def _start_ui_preview(ui_port: int) -> subprocess.Popen | None:
    root = Path(__file__).resolve().parents[2]
    ui_dir = root / "monitoring" / "ui"
    if not _ensure_ui_ready(ui_dir, build=True):
        return None

    npm_cmd = "npm" if sys.platform != "win32" else "npm.cmd"
    try:
        proc = subprocess.Popen(
            [npm_cmd, "run", "preview", "--", "--port", str(ui_port)],
            cwd=str(ui_dir),
        )
        typer.echo(f"  [ui] preview server starting on port {ui_port}")
        return proc
    except FileNotFoundError:
        typer.echo("  [ui] npm not found — skipping", err=True)
        return None


@monitor_app.command("ui")
def monitor_ui(
    ui_port: int = typer.Option(3000, "--port", "--ui-port", help="Monitoring UI port"),
) -> None:
    """Start the Monitoring UI preview server."""
    config = load_pipeline_config()
    if ui_port == 3000:
        ui_port = config.ui_port

    typer.echo(f"✦ AIGuard Monitoring UI  →  http://localhost:{ui_port}")
    proc = _start_ui_preview(ui_port)
    if proc is None:
        raise typer.Exit(code=1)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        typer.echo("\nShutting down…")
        proc.terminate()
