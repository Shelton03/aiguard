"""FastAPI route handlers for the Human Review UI."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from .calibration_manager import CalibrationManager
from .emailer import Emailer
from .models import ReviewDecision, ReviewStatus
from .queue import ReviewQueue

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_VERSION = "0.2.0"

# Base directory of this package — templates and static are relative to it
_PKG_DIR = Path(__file__).parent
_TEMPLATES_DIR = _PKG_DIR / "templates"

templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _db_path_for(project: str) -> Path:
    """Resolve the SQLite DB path for a given project."""
    aiguard_dir = Path(os.getenv("AIGUARD_DATA_DIR", str(Path.cwd() / ".aiguard")))
    return aiguard_dir / f"{project}.db"


def _list_projects() -> list[dict]:
    """
    Discover all project DBs from the .aiguard directory and return
    a list of {name, pending} dicts.
    """
    aiguard_dir = Path(os.getenv("AIGUARD_DATA_DIR", str(Path.cwd() / ".aiguard")))
    projects = []
    if aiguard_dir.exists():
        for db_file in sorted(aiguard_dir.glob("*.db")):
            name = db_file.stem
            try:
                with ReviewQueue(db_path=db_file, project=name) as q:
                    pending = q.pending_count()
            except Exception:
                pending = 0
            projects.append({"name": name, "pending": pending})
    return projects


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """Home page — list all projects with pending review counts."""
    projects = _list_projects()
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "projects": projects, "version": _VERSION},
    )


@router.get("/project/{project_name}/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, project_name: str) -> HTMLResponse:
    """Per-project dashboard showing pending + completed reviews."""
    db_path = _db_path_for(project_name)
    with ReviewQueue(db_path=db_path, project=project_name) as q:
        all_items = q.list_all()
    pending   = [i for i in all_items if i.status == ReviewStatus.PENDING]
    completed = [i for i in all_items if i.status == ReviewStatus.COMPLETED]

    with CalibrationManager(db_path=db_path, project=project_name) as cal:
        cal_state = cal.state

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request":         request,
            "project":         project_name,
            "pending":         pending,
            "completed":       completed,
            "pending_count":   len(pending),
            "completed_count": len(completed),
            "cal_state":       cal_state,
            "version":         _VERSION,
        },
    )


@router.get("/project/{project_name}/review/{token}", response_class=HTMLResponse)
async def review_form(
    request: Request, project_name: str, token: str
) -> HTMLResponse:
    """Display the review form for a specific (token-gated) queue item."""
    db_path = _db_path_for(project_name)
    with ReviewQueue(db_path=db_path, project=project_name) as q:
        item = q.fetch_by_token(token)

    if item is None:
        return templates.TemplateResponse(
            "review_form.html",
            {
                "request": request,
                "project": project_name,
                "item":    None,
                "token":   token,
                "error":   "This review link is invalid or has already been used.",
                "version": _VERSION,
            },
            status_code=404,
        )

    if item.status == ReviewStatus.COMPLETED:
        return templates.TemplateResponse(
            "review_form.html",
            {
                "request": request,
                "project": project_name,
                "item":    item,
                "token":   token,
                "error":   "This review link has already been used and is now expired.",
                "version": _VERSION,
            },
            status_code=410,
        )

    return templates.TemplateResponse(
        "review_form.html",
        {
            "request": request,
            "project": project_name,
            "item":    item,
            "token":   token,
            "error":   None,
            "version": _VERSION,
        },
    )


@router.post("/project/{project_name}/review/{token}", response_class=HTMLResponse)
async def submit_review(
    request: Request,
    project_name: str,
    token: str,
    decision: str = Form(...),
    notes: Optional[str] = Form(default=None),
) -> HTMLResponse:
    """Accept a submitted review decision."""
    db_path = _db_path_for(project_name)

    # Validate decision value
    try:
        review_decision = ReviewDecision(decision)
    except ValueError:
        with ReviewQueue(db_path=db_path, project=project_name) as q:
            item = q.fetch_by_token(token)
        return templates.TemplateResponse(
            "review_form.html",
            {
                "request": request,
                "project": project_name,
                "item":    item,
                "token":   token,
                "error":   f"Invalid decision '{decision}'. Choose correct, incorrect, or uncertain.",
                "version": _VERSION,
            },
            status_code=400,
        )

    # Complete the queue item (token is single-use; rotated inside complete())
    try:
        with ReviewQueue(db_path=db_path, project=project_name) as q:
            label = q.complete(token=token, decision=review_decision, notes=notes or None)
    except ValueError as exc:
        return templates.TemplateResponse(
            "review_form.html",
            {
                "request": request,
                "project": project_name,
                "item":    None,
                "token":   token,
                "error":   str(exc),
                "version": _VERSION,
            },
            status_code=409,
        )

    # Increment calibration counter + potentially trigger recalibration
    with CalibrationManager(db_path=db_path, project=project_name) as cal:
        cal.increment_review_count()
        cal.check_and_update()

    return templates.TemplateResponse(
        "submitted.html",
        {
            "request": request,
            "project": project_name,
            "label":   label,
            "version": _VERSION,
        },
    )
