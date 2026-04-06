"""SDK configuration — loaded from aiguard.yaml.

Priority:
  1. Explicit keyword arguments passed to configure()
  2. aiguard.yaml   (monitoring: / sdk: sections)
  3. Hard-coded defaults below

The config is a plain dataclass so it is easy to serialise, compare, and
pass around without circular imports.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

_DEFAULT_SAMPLING_RATE: float = 1.0   # monitor every request unless overridden
_DEFAULT_PROVIDER: str = "litellm"
_DEFAULT_ENABLED: bool = True


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class SdkConfig:
    """Immutable snapshot of SDK runtime configuration."""

    enabled: bool = _DEFAULT_ENABLED
    """When False the SDK is a transparent pass-through — no traces are created."""

    sampling_rate: float = _DEFAULT_SAMPLING_RATE
    """Fraction of requests to monitor, in [0.0, 1.0].
    E.g. 0.2 means roughly 1-in-5 requests are traced.
    """

    provider: str = _DEFAULT_PROVIDER
    """LLM provider abstraction layer (currently only 'litellm' is supported)."""

    queue_maxsize: int = 10_000
    """Maximum number of pending trace events in the in-memory queue before
    new events are dropped (back-pressure protection).
    """

    worker_timeout_s: float = 0.1
    """How long the background worker blocks waiting for a new queue item."""

    extra: Dict[str, Any] = field(default_factory=dict)
    """Forward-compatible bucket for future config keys."""

    ingest_url: Optional[str] = None
    """Monitoring API ingest endpoint for cross-process trace delivery."""

    ingest_timeout_s: float = 2.0
    """Timeout for HTTP ingest requests in seconds."""

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def __post_init__(self) -> None:
        if not 0.0 <= self.sampling_rate <= 1.0:
            raise ValueError(
                f"sampling_rate must be in [0, 1], got {self.sampling_rate!r}"
            )


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_sdk_config(
    root: Optional[Path] = None,
    *,
    enabled: Optional[bool] = None,
    sampling_rate: Optional[float] = None,
    provider: Optional[str] = None,
) -> SdkConfig:
    """Return an :class:`SdkConfig` by merging YAML file + explicit overrides.

    Parameters
    ----------
    root:
        Directory that contains ``aiguard.yaml``.  Defaults to ``CWD``.
    enabled / sampling_rate / provider:
        Explicit overrides; take priority over the YAML file.
    """
    raw: Dict[str, Any] = {}

    config_path = (root or Path(os.getcwd())) / "aiguard.yaml"
    if config_path.exists():
        try:
            import yaml  # type: ignore[import]

            with config_path.open() as fh:
                doc: Dict[str, Any] = yaml.safe_load(fh) or {}

            monitoring_section: Dict[str, Any] = doc.get("monitoring", {}) or {}
            sdk_section: Dict[str, Any] = doc.get("sdk", {}) or {}

            raw["enabled"] = monitoring_section.get("enabled", _DEFAULT_ENABLED)
            raw["sampling_rate"] = monitoring_section.get(
                "sampling_rate", _DEFAULT_SAMPLING_RATE
            )
            raw["provider"] = sdk_section.get("provider", _DEFAULT_PROVIDER)
            raw["queue_maxsize"] = sdk_section.get("queue_maxsize", 10_000)
            raw["worker_timeout_s"] = sdk_section.get("worker_timeout_s", 0.1)

            api_section: Dict[str, Any] = monitoring_section.get("api", {}) or {}
            api_port = api_section.get("port", 8080)
            raw["ingest_url"] = monitoring_section.get(
                "ingest_url", f"http://localhost:{api_port}/traces/ingest"
            )
            raw["ingest_timeout_s"] = monitoring_section.get("ingest_timeout_s", 2.0)

        except Exception:
            # If the YAML file is malformed / unreadable, fall back to defaults
            # silently so the SDK never crashes on import.
            pass

    # Explicit keyword overrides always win
    if enabled is not None:
        raw["enabled"] = enabled
    if sampling_rate is not None:
        raw["sampling_rate"] = sampling_rate
    if provider is not None:
        raw["provider"] = provider

    return SdkConfig(
        enabled=raw.get("enabled", _DEFAULT_ENABLED),
        sampling_rate=raw.get("sampling_rate", _DEFAULT_SAMPLING_RATE),
        provider=raw.get("provider", _DEFAULT_PROVIDER),
        queue_maxsize=raw.get("queue_maxsize", 10_000),
        worker_timeout_s=raw.get("worker_timeout_s", 0.1),
        ingest_url=raw.get("ingest_url"),
        ingest_timeout_s=raw.get("ingest_timeout_s", 2.0),
    )
