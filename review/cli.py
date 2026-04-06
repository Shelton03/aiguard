"""CLI entrypoint for the Human Review module.

Commands::

    aiguard review serve               # start on default port 8000
    aiguard review serve --port 8123   # explicit port
    aiguard review enqueue             # manually add a test item (dev helper)
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from uuid import uuid4


# ---------------------------------------------------------------------------
# Port resolution  (priority: CLI arg > ENV > config file > default 8000)
# ---------------------------------------------------------------------------


def _resolve_port(cli_port: int | None) -> int:
    if cli_port is not None:
        return cli_port
    env = os.getenv("AIGUARD_REVIEW_PORT")
    if env:
        return int(env)
    # Try config file
    root = Path.cwd()
    yaml_path = root / "aiguard.yaml"
    if yaml_path.exists():
        try:
            import yaml  # type: ignore[import]

            with yaml_path.open() as fh:
                data = yaml.safe_load(fh) or {}
            review_section = data.get("review", {}) or {}
            port = review_section.get("port")
            if port:
                return int(port)
        except Exception:
            pass
    try:
        import tomllib  # type: ignore
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore
        except ImportError:
            tomllib = None  # type: ignore

    if tomllib is not None:
        for candidate in [root / ".aiguard" / "review_config.toml", root / "aiguard.toml"]:
            if candidate.exists():
                try:
                    with open(candidate, "rb") as fh:
                        data = tomllib.load(fh)
                    port = data.get("review", {}).get("port")
                    if port:
                        return int(port)
                except Exception:
                    pass
    return 8000


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------


def cmd_serve(args: argparse.Namespace) -> None:
    """Start the FastAPI review server with uvicorn."""
    try:
        import uvicorn
    except ImportError:
        print(
            "ERROR: uvicorn is not installed.\n"
            "Install it with:  pip install 'aiguard[review]'",
            file=sys.stderr,
        )
        sys.exit(1)

    port = _resolve_port(getattr(args, "port", None))
    host = os.getenv("AIGUARD_REVIEW_HOST", "0.0.0.0")

    print(f"Starting AIGuard Review server on http://{host}:{port}")
    uvicorn.run("review.server:app", host=host, port=port, reload=False)


def cmd_enqueue(args: argparse.Namespace) -> None:
    """Dev helper: add a dummy review item to a project queue."""
    from review.queue import ReviewQueue
    from review.emailer import Emailer

    project = args.project or "default"
    data_dir = Path(os.getenv("AIGUARD_DATA_DIR", str(Path.cwd() / ".aiguard")))
    db_path = data_dir / f"{project}.db"

    with ReviewQueue(db_path=db_path, project=project) as q:
        item = q.enqueue(
            evaluation_id=str(uuid4()),
            module_type=args.module or "hallucination",
            model_response="[Test model response for manual review]",
            raw_score=float(args.raw_score or 0.82),
            calibrated_score=float(args.calibrated_score or 0.78),
            trigger_reason=args.trigger or "manual-cli",
        )

    print(f"Enqueued item:  {item.id}")
    print(f"Token:          {item.review_token}")
    base_url = os.getenv("AIGUARD_REVIEW_BASE_URL", "http://localhost:8000")
    print(f"Review link:    {base_url}/project/{project}/review/{item.review_token}")

    if args.email:
        emailer = Emailer()
        emailer.send_review_alert(
            project=project,
            item_id=item.id,
            module_type=item.module_type,
            trigger_reason=item.trigger_reason,
            raw_score=item.raw_score,
            token=item.review_token,
        )
        print("Email alert sent.")


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aiguard review",
        description="AIGuard Human Review CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # serve
    serve_p = sub.add_parser("serve", help="Start the review web server")
    serve_p.add_argument("--port", type=int, default=None, help="Port to listen on")
    serve_p.set_defaults(func=cmd_serve)

    # enqueue (dev helper)
    enqueue_p = sub.add_parser("enqueue", help="Manually enqueue a review item (dev)")
    enqueue_p.add_argument("--project",           default="default")
    enqueue_p.add_argument("--module",            default="hallucination")
    enqueue_p.add_argument("--raw-score",         dest="raw_score",         default="0.82")
    enqueue_p.add_argument("--calibrated-score",  dest="calibrated_score",  default="0.78")
    enqueue_p.add_argument("--trigger",           default="manual-cli")
    enqueue_p.add_argument("--email",             action="store_true", help="Send email alert")
    enqueue_p.set_defaults(func=cmd_enqueue)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
