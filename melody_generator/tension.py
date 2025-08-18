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
- Weighting now explicitly checks for ``numpy.ndarray`` inputs so only true
  NumPy arrays use vectorised operations; other iterable types fall back to
  the pure Python implementation.
"""

from __future__ import annotations

from typing import Iterable

try:
    import numpy as np
except Exception:  # pragma: no cover - optional dependency
    # NumPy is optional; when it's missing ``np`` is simply set to ``None`` so
    # callers can check availability.  All functions in this module handle the
    # ``None`` case and fall back to pure Python implementations.
    np = None



def interval_tension(interval: int) -> float:
    """Return a simple tension value for ``interval`` in semitones."""

    mapping = {0: 0.0, 1: 0.2, 2: 0.4, 3: 0.6, 4: 0.7, 5: 0.8, 6: 1.0}
    return mapping.get(interval % 12, 0.5)


def tension_for_notes(prev: str, cand: str) -> float:
    """Calculate tension between ``prev`` and ``cand``."""
    from . import note_to_midi  # Local import avoids circular dependency

    interval = abs(note_to_midi(prev) - note_to_midi(cand))
    return interval_tension(interval)


def apply_tension_weights(
    weights: Iterable[float], tensions: Iterable[float], target: float
) -> Iterable[float]:
    """Bias ``weights`` toward the ``target`` tension level.

    Parameters
    ----------
    weights:
        Sequence of base weights for each candidate note. This may be a list,
        tuple or ``numpy.ndarray`` when NumPy is installed.
    tensions:
        Iterable of pre-computed tension values corresponding to each weight.
    target:
        Desired tension level to bias toward; values closer to this number will
        receive a higher weighting.

    Returns
    -------
    Iterable[float]
        Adjusted weights. If ``weights`` is a ``numpy.ndarray`` the returned
        object will also be an array; otherwise a new list is produced.

    Notes
    -----
    NumPy arrays are detected explicitly using :func:`isinstance` so that
    only genuine arrays take the fast vectorised path. All other iterable
    inputs fall back to a pure Python list comprehension.
    """

    # Compute scaling values that bias tensions toward the desired target.
    values = [1 / (1 + abs(t - target)) for t in tensions]

    # Use vectorised multiplication only when ``weights`` is a real NumPy array.
    if np is not None and isinstance(weights, np.ndarray):
        return weights * np.array(values)

    # For lists, tuples, and other iterables we fall back to a Python loop.
    return [w * v for w, v in zip(weights, values)]
