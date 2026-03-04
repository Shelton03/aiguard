"""Thin service adapters used by the CLI."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from storage.manager import StorageManager
from storage.migrations import migrate_backend


class ProjectService:
    def __init__(self, root: Path) -> None:
        self.root = root

    def list_projects(self) -> List[str]:
        return StorageManager(self.root).list_projects()

    def delete_project(self, project: str) -> None:
        StorageManager(self.root).delete_project(project)

    def export_project(self, project: str) -> Dict[str, Any]:
        return StorageManager(self.root).export_project(project)

    def init_project_config(self, config_path: Path, content: str, force: bool) -> None:
        if config_path.exists() and not force:
            raise FileExistsError(f"{config_path} already exists. Use --force to overwrite.")
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(content)


class StorageService:
    def __init__(self, root: Path) -> None:
        self.root = root

    def migrate(self, backend: str) -> None:
        migrate_backend(backend)

    def info(self) -> Dict[str, Any]:
        mgr = StorageManager(self.root)
        return {
            "project": mgr.project,
            "backend": mgr.backend.__class__.__name__,
            "root": str(self.root),
        }


class ReviewServer:
    def start(self, port: Optional[int] = None) -> None:
        try:
            import uvicorn
        except ImportError as exc:
            raise RuntimeError("uvicorn is required. Install with: pip install 'aiguard[review]'") from exc

        from review.cli import _resolve_port

        host = os.getenv("AIGUARD_REVIEW_HOST", "0.0.0.0")
        resolved = _resolve_port(port)
        uvicorn.run("review.server:app", host=host, port=resolved, reload=False)


class ReviewService:
    def __init__(self, root: Path) -> None:
        self.root = root

    def list_items(self, project: str) -> Dict[str, Any]:
        from review.queue import ReviewQueue

        data_dir = Path(os.getenv("AIGUARD_DATA_DIR", str(self.root / ".aiguard")))
        db_path = data_dir / f"{project}.db"
        with ReviewQueue(db_path=db_path, project=project) as queue:
            pending = queue.list_pending()
            completed = [item for item in queue.list_all() if item.status.value == "completed"]
        return {
            "project": project,
            "pending": [item.__dict__ for item in pending],
            "completed": [item.__dict__ for item in completed],
        }


class CalibrationService:
    def __init__(self, root: Path) -> None:
        self.root = root

    def force_update(self, project: str) -> None:
        from review.calibration_manager import CalibrationManager

        data_dir = Path(os.getenv("AIGUARD_DATA_DIR", str(self.root / ".aiguard")))
        db_path = data_dir / f"{project}.db"
        cal = CalibrationManager(db_path=db_path, project=project)
        cal.force_update()


class MonitoringService:
    def start(self, project: str) -> None:
        raise RuntimeError(
            "Monitoring service is not configured in this build. "
            "Integrate the hallucination SDK monitoring entrypoint and retry."
        )
