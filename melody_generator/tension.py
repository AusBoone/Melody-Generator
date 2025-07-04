"""Helpers for computing and applying musical tension."""

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
    if hasattr(weights, "__mul__") and not isinstance(weights, list):
        return weights * np.array(values)
    return [w * v for w, v in zip(weights, values)]
