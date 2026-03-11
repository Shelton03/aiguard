"""Sampling logic for the SDK.

Keeps the monitoring overhead proportional to ``sampling_rate``.  Only this
module contains randomness so it can be patched / seeded in tests without
touching client code.
"""
from __future__ import annotations

import random as _random
from typing import Optional


def should_sample(sampling_rate: float, *, _rng: Optional[_random.Random] = None) -> bool:
    """Return ``True`` if this request should be traced.

    Parameters
    ----------
    sampling_rate:
        A float in ``[0.0, 1.0]``.
        * ``1.0`` → always sample (100 %)
        * ``0.0`` → never sample (0 %)
        * ``0.2`` → sample ~20 % of requests
    _rng:
        Optional :class:`random.Random` instance.  Useful in tests to produce
        deterministic results without monkey-patching the module-level RNG.

    Raises
    ------
    ValueError
        If ``sampling_rate`` is outside ``[0, 1]``.
    """
    if not 0.0 <= sampling_rate <= 1.0:
        raise ValueError(
            f"sampling_rate must be in [0.0, 1.0], got {sampling_rate!r}"
        )

    # Fast-path: avoid calling random() for the common cases
    if sampling_rate >= 1.0:
        return True
    if sampling_rate <= 0.0:
        return False

    rng = _rng or _random
    return rng.random() < sampling_rate
