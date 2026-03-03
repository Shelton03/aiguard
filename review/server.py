"""FastAPI application factory for the Human Review server.

Usage (programmatic)::

    from review.server import create_app
    app = create_app()

Usage (CLI)::

    aiguard review serve --port 8123
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .routes import router

_PKG_DIR = Path(__file__).parent
_STATIC_DIR = _PKG_DIR / "static"


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Ensure the data directory exists on startup
    data_dir = Path(os.getenv("AIGUARD_DATA_DIR", str(Path.cwd() / ".aiguard")))
    data_dir.mkdir(parents=True, exist_ok=True)
    yield


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="AIGuard Human Review",
        description="Lightweight human review console for AIGuard evaluation scores.",
        version="0.2.0",
        docs_url=None,
        redoc_url=None,
        lifespan=_lifespan,
    )

    # Serve static assets (CSS, etc.)
    if _STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    # Register UI routes
    app.include_router(router)

    return app


# Module-level app instance so uvicorn can reference it directly:
#   uvicorn review.server:app
app = create_app()
