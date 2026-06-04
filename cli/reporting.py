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

from .pdf_report import PDFReportGenerator


# ---------------------------------------------------------------------------
# Symbol cleaning
# ---------------------------------------------------------------------------


def clean_report_text(text: str, field_type: str) -> str:
    """Clean Unicode artifacts from report text fields.
    
    Args:
        text: Raw text to clean
        field_type: One of "prompt", "response", "rationale", "explanation", "metadata"
    
    Returns:
        Cleaned text with Unicode artifacts removed
    """
    if not text:
        return text

    # Smart quotes → straight quotes
    text = text.replace('"', '"').replace('"', '"')
    text = text.replace('"', '"').replace('"', '"')
    text = text.replace('"', '"').replace('"', '"')

    # Dashes → hyphens
    text = text.replace('—', '-').replace('–', '-')

    # Remove zero-width chars, non-breaking spaces, other artifacts
    text = text.replace('\u200b', '')  # Zero-width space
    text = text.replace('\u200c', '')  # Zero-width non-joiner
    text = text.replace('\u200d', '')  # Zero-width joiner
    text = text.replace('\ufeff', '')  # BOM
    text = text.replace('\u00a0', ' ')  # Non-breaking space
    text = text.replace('\u2028', '\n')  # Line separator
    text = text.replace('\u2029', '\n')  # Paragraph separator

    # Field-specific normalization
    if field_type == "metadata":
        # Single line, strip all extra whitespace
        text = ' '.join(text.split())
    elif field_type in ("rationale", "explanation"):
        # Normalize whitespace, keep paragraph breaks
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        text = text.strip()
    # prompt/response: preserve structure, only clean artifacts

    return text


def _clean_all_text_fields(data: Dict) -> Dict:
    """Recursively clean all text fields in report data."""
    # Map field names to their cleaning type
    field_mappings = {
        'prompt': 'prompt',
        'response': 'response',
        'rationale': 'rationale',
        'explanation': 'explanation',
        'category': 'metadata',
        'id': 'metadata',
        'module': 'metadata',
        'project': 'metadata',
        'status': 'metadata',
        'version': 'metadata',
        'provider': 'metadata',
        'model_name': 'metadata',
    }
    
    def clean_recursive(obj, field_type='metadata'):
        if isinstance(obj, dict):
            return {
                k: clean_recursive(v, field_mappings.get(k, field_type))
                for k, v in obj.items()
            }
        elif isinstance(obj, list):
            return [clean_recursive(item, field_type) for item in obj]
        elif isinstance(obj, str):
            return clean_report_text(obj, field_type)
        return obj
    
    return clean_recursive(data)


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------


def write_report(
    path: Path,
    data: Dict[str, Any],
    *,
    atomic: bool = True,
    generate_pdf: bool = False,
    pdf_output: Optional[Path] = None,
) -> Path:
    """Serialise *data* as pretty-printed JSON to *path*.
    
    The parent directory is created if needed. With ``atomic=True`` (the
    default) the file is first written to ``<path>.tmp`` and then renamed
    into place so a crash never leaves a half-written report.
    
    If ``generate_pdf=True``, also generates a PDF report using ReportLab.
    
    Args:
        path: Output JSON path
        data: Report data
        atomic: Use atomic write (default True)
        generate_pdf: Also generate PDF report
        pdf_output: PDF output path (defaults to path with .pdf extension)
    
    Returns:
        Path to the JSON report file
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # Clean all text fields
    cleaned_data = _clean_all_text_fields(data)
    
    # Write JSON
    payload = json.dumps(cleaned_data, indent=2, default=str)
    if atomic:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(payload, encoding="utf-8")
        os.replace(tmp, path)
    else:
        path.write_text(payload, encoding="utf-8")
    
    # Generate PDF if requested
    if generate_pdf:
        pdf_path = pdf_output or path.with_suffix('.pdf')
        try:
            generator = PDFReportGenerator(pdf_path)
            generator.generate(cleaned_data)
        except Exception as e:
            # PDF generation failed - warn but don't fail
            import sys
            print(f"Warning: PDF generation failed: {e}", file=sys.stderr)
    
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
        # Clean the summary before output
        summary = {
            "schema_version": report.get("schema_version"),
            "project": report.get("project"),
            "timestamp": report.get("timestamp"),
            "status": report.get("status"),
            "exit_code": report.get("exit_code"),
            "modules": [_summary_for_module(m) for m in report["modules"]],
        }
        cleaned = _clean_all_text_fields(summary)
        return json.dumps(cleaned, indent=2)
    
    # Single module - clean before output
    summary = _summary_for_module(report)
    cleaned = _clean_all_text_fields(summary)
    return json.dumps(cleaned, indent=2)
