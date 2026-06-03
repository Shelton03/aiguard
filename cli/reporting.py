"""Report serialization and terminal-summary helpers for the CLI.

Every CLI run produces:

* a **detailed JSON report file** written by default under
  ``.aiguard/reports/<project>-<module>-<UTC-timestamp>.json`` (or a
  user-supplied ``--output`` path), containing every test case in full;
* a **minimal terminal summary** printed to stdout for human / CI
  consumption.

The file is written atomically (write to ``.tmp`` then ``os.replace``)
so a CI interruption cannot leave a half-written artefact. Pass
``--full`` to the CLI to also dump the full report JSON to stdout.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------


def write_report(path: Path, data: Dict[str, Any], *, atomic: bool = True) -> Path:
    """Serialise *data* as pretty-printed JSON to *path*.

    The parent directory is created if needed. With ``atomic=True`` (the
    default) the file is first written to ``<path>.tmp`` and then renamed
    into place so a crash never leaves a half-written report.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2, default=str)
    if atomic:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(payload, encoding="utf-8")
        os.replace(tmp, path)
    else:
        path.write_text(payload, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Default report path
# ---------------------------------------------------------------------------

_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_name(value: str) -> str:
    cleaned = _SAFE_NAME_RE.sub("-", value.strip())
    cleaned = cleaned.strip("-")
    cleaned = cleaned.replace("..", "-")
    return cleaned.strip("-.") or "default"


def default_report_path(
    project: str,
    module: str,
    root: Path | str,
    *,
    timestamp: Optional[datetime] = None,
    combined: bool = False,
) -> Path:
    """Return the default per-run report path.

    Layout: ``<root>/.aiguard/reports/<project>-<module>-<UTC>.json``.

    For multi-module runs (``combined=True``) the module segment is
    replaced with ``combined`` so the file is easy to find.
    """
    ts = (timestamp or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    suffix = "combined" if combined else _safe_name(module)
    filename = f"{_safe_name(project)}-{suffix}-{ts}.json"
    return Path(root) / ".aiguard" / "reports" / filename


# ---------------------------------------------------------------------------
# Combined report (multi-module)
# ---------------------------------------------------------------------------


def combined_report(
    project: str,
    module_reports: List[Dict[str, Any]],
    aggregate_code: int,
    *,
    schema_version: str = "2",
    aiguard_version: str = "unknown",
) -> Dict[str, Any]:
    """Build the multi-module combined report envelope.

    ``aggregate_code`` follows :mod:`cli.exit_codes` (``0=pass, 1=fail,
    2=error``).
    """
    status = "error" if aggregate_code == 2 else "fail" if aggregate_code == 1 else "pass"
    return {
        "schema_version": schema_version,
        "aiguard_version": aiguard_version,
        "project": project,
        "timestamp": _utcnow_iso(),
        "status": status,
        "exit_code": aggregate_code,
        "modules": module_reports,
    }


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


# ---------------------------------------------------------------------------
# Terminal summary
# ---------------------------------------------------------------------------

_SUMMARY_FIELDS = (
    "project",
    "module",
    "timestamp",
    "mode",
    "total_tests",
    "failed_tests",
    "global_risk_score",
    "threshold",
    "status",
    "failure_breakdown_by_category",
)


def _summary_for_module(report: Dict[str, Any]) -> Dict[str, Any]:
    return {key: report.get(key) for key in _SUMMARY_FIELDS if key in report}


def format_terminal_summary(report: Dict[str, Any]) -> str:
    """Format a minimal JSON summary suitable for stdout and CI logs.

    For a single-module report, returns a single-line pretty JSON object
    containing only the top-level summary fields. For a combined
    multi-module report, returns a single object with the combined
    status and one nested summary per module.
    """
    if "modules" in report and isinstance(report["modules"], list):
        return json.dumps(
            {
                "schema_version": report.get("schema_version"),
                "project": report.get("project"),
                "timestamp": report.get("timestamp"),
                "status": report.get("status"),
                "exit_code": report.get("exit_code"),
                "modules": [_summary_for_module(m) for m in report["modules"]],
            },
            indent=2,
        )
    return json.dumps(_summary_for_module(report), indent=2)
