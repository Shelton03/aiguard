"""Monitoring API — FastAPI application factory."""
from __future__ import annotations

from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from monitoring.api.routes_metrics import router as metrics_router
from monitoring.api.routes_review import router as review_router
from monitoring.api.routes_traces import router as traces_router


def create_monitoring_app(
    title: str = "AIGuard Monitoring",
    cors_origins: Optional[list] = None,
) -> FastAPI:
    """Create and return the configured FastAPI monitoring application.

    Parameters
    ----------
    title:
        OpenAPI title.
    cors_origins:
        List of allowed CORS origins.  Defaults to ``["*"]`` (suitable for
        local development).  Set explicitly to a specific origin list in
        production.
    """
    app = FastAPI(
        title=title,
        description="Real-time monitoring, metrics, and review queue for AIGuard.",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS — allow the React dev server (port 3000) and any origin by default
    origins = cors_origins if cors_origins is not None else ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(traces_router)
    app.include_router(metrics_router)
    app.include_router(review_router)

    @app.get("/health", tags=["system"])
    def health() -> dict:
        return {"status": "ok"}

    return app
