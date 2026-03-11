"""AIGuard SDK — LiteLLM wrapper with non-blocking trace emission.

Quickstart
----------
::

    import aiguard

    # Optional: customise config at start-up (reads aiguard.yaml by default)
    aiguard.configure(sampling_rate=0.5)

    response = aiguard.chat(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Explain quantum computing"}],
    )
    print(response.choices[0].message.content)

Advanced usage
--------------
Register a custom trace handler::

    from sdk.dispatcher import register_handler

    def send_to_my_backend(trace_dict):
        # forward to your monitoring service
        ...

    register_handler(send_to_my_backend)

Enable structured JSON logging::

    from sdk.dispatcher import enable_json_logging
    enable_json_logging()
"""
from __future__ import annotations

from sdk.client import chat, configure, get_config
from sdk.config import SdkConfig, load_sdk_config
from sdk.dispatcher import (
    clear_handlers,
    dispatch_trace,
    enable_json_logging,
    register_handler,
    unregister_handler,
)
from sdk.queue import dropped_event_count, enqueue, queue_size
from sdk.sampling import should_sample
from sdk.trace import TokenUsage, TraceEvent

__all__ = [
    # Primary developer API
    "chat",
    "configure",
    "get_config",
    # Config
    "SdkConfig",
    "load_sdk_config",
    # Trace schema
    "TraceEvent",
    "TokenUsage",
    # Queue
    "enqueue",
    "queue_size",
    "dropped_event_count",
    # Dispatcher
    "dispatch_trace",
    "register_handler",
    "unregister_handler",
    "clear_handlers",
    "enable_json_logging",
    # Sampling
    "should_sample",
]
