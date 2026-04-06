"""``aiguard monitor`` — starts the monitoring API server.

Usage::

    aiguard monitor [--host HOST] [--port PORT]
    aiguard monitor ui
"""
from __future__ import annotations

from pathlib import Path
import typer

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
) -> None:
    """Start the monitoring FastAPI server on *host*:*port*."""
    if ctx.invoked_subcommand is not None:
        return

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

    typer.echo(f"✦ AIGuard Monitoring API  →  http://{host}:{port}/docs")
    typer.echo("Press Ctrl+C to stop.\n")

    app = create_monitoring_app()
    uvicorn.run(app, host=host, port=port)


@monitor_app.command("ui")
def monitor_ui() -> None:
    """Print instructions for starting the Monitoring UI."""
    root = Path(__file__).resolve().parents[2]
    ui_dir = root / "monitoring" / "ui"
    if ui_dir.exists() and (ui_dir / "package.json").exists():
        typer.echo("Monitoring UI source detected.")
        typer.echo(f"Path: {ui_dir}")
        typer.echo("Run from that directory:")
        typer.echo("  npm install")
        typer.echo("  npm run dev")
    else:
        typer.echo("Monitoring UI source is not bundled in this install.")
        typer.echo("Options:")
        typer.echo("  1) Clone the repo and run 'npm install && npm run dev' in monitoring/ui")
        typer.echo("  2) Use 'aiguard dev' from the repo to start API + UI together")
