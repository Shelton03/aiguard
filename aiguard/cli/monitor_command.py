"""``aiguard monitor`` — starts the monitoring API server.

Usage::

    aiguard monitor start [--host HOST] [--port PORT]
"""
from __future__ import annotations

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
