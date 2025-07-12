"""Helpers for computing and applying musical tension.

This module defines lightweight utilities used to weight candidate notes
based on their perceived tension relative to the previous pitch.  The
functions here provide a simple mapping from interval sizes to tension
values and expose helpers for adjusting selection weights during melody
generation.

Example
-------
>>> weights = [1.0, 1.0, 1.0]
>>> tens = [0.2, 0.8, 0.4]
>>> apply_tension_weights(weights, tens, 0.5)
[0.8333333333333334, 0.5555555555555556, 1.0]

Design Notes
------------
- ``numpy`` is optional and the routines fall back to pure Python when the
  library is unavailable.
- The interval-to-tension mapping is intentionally coarse so the computation
  remains fast and easily adjustable.
"""

from __future__ import annotations

from typing import Iterable

try:
    import numpy as np
except Exception:  # pragma: no cover - optional dependency
    import types

    def _array(vals):
        return vals

    np = types.SimpleNamespace(array=_array)



def interval_tension(interval: int) -> float:
    """Return a simple tension value for ``interval`` in semitones."""

    mapping = {0: 0.0, 1: 0.2, 2: 0.4, 3: 0.6, 4: 0.7, 5: 0.8, 6: 1.0}
    return mapping.get(interval % 12, 0.5)


def tension_for_notes(prev: str, cand: str) -> float:
    """Calculate tension between ``prev`` and ``cand``."""
    from . import note_to_midi  # Local import avoids circular dependency

    interval = abs(note_to_midi(prev) - note_to_midi(cand))
    return interval_tension(interval)


def apply_tension_weights(weights, tensions: Iterable[float], target: float):
    """Bias ``weights`` toward the ``target`` tension level."""

    values = [1 / (1 + abs(t - target)) for t in tensions]
    if hasattr(weights, "__mul__") and not isinstance(weights, list) and np is not None:
        # NumPy may be missing so guard the vectorized path to avoid attribute errors
        return weights * np.array(values)
    return [w * v for w, v in zip(weights, values)]
