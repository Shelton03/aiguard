"""Exit code utilities for the CLI."""
from __future__ import annotations

from typing import Iterable

PASS = 0
FAIL = 1
SYSTEM_ERROR = 2


def aggregate_exit_codes(codes: Iterable[int]) -> int:
    if any(code == SYSTEM_ERROR for code in codes):
        return SYSTEM_ERROR
    if any(code == FAIL for code in codes):
        return FAIL
    return PASS
