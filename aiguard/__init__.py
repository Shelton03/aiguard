"""AIGuard orchestration package.

Usage
-----
::

    import aiguard

    # Optional one-time configuration (auto-reads aiguard.yaml if skipped)
    aiguard.configure(sampling_rate=0.2)

    response = aiguard.chat(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Explain quantum computing"}],
    )
"""
from __future__ import annotations

__version__ = "0.2.0"

# SDK public surface — imported lazily to avoid hard dependency on litellm
# when only the CLI or evaluation modules are used.
from aiguard.sdk.client import chat, configure, get_config
from aiguard.sdk.dispatcher import (
    enable_json_logging,
    register_handler,
)
from aiguard.sdk.trace import TraceEvent

__all__ = [
    "__version__",
    # SDK
    "chat",
    "configure",
    "get_config",
    "TraceEvent",
    "register_handler",
    "enable_json_logging",
]
