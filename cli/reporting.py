"""Report serialization helpers."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def write_report(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
