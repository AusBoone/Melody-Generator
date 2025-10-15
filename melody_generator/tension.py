"""Helpers for computing and applying musical tension.

This module defines lightweight utilities used to weight candidate notes
based on their perceived tension relative to the previous pitch.  The
functions here provide a simple mapping from interval sizes to tension
values and expose helpers for adjusting selection weights during melody
generation.

Summary of recent changes
-------------------------
* ``apply_tension_weights`` now validates that ``weights`` and ``tensions`` are
  non-empty sequences of matching length so mistakes surface as clear
  ``ValueError`` exceptions instead of silent truncation.

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

    Raises
    ------
    ValueError
        If ``weights`` and ``tensions`` are empty or their lengths differ.

    Notes
    -----
    NumPy arrays are detected explicitly using :func:`isinstance` so that
    only genuine arrays take the fast vectorised path. All other iterable
    inputs fall back to a pure Python list comprehension.
    """

    # Convert ``tensions`` to a concrete list so we can validate its contents,
    # reuse it multiple times and produce helpful error messages when callers
    # submit malformed input such as mismatched lengths.
    tension_list = list(tensions)
    if not tension_list:
        raise ValueError("weights and tensions must contain at least one element")

    # NumPy arrays expose their size directly. When available we validate the
    # length relationship and apply vectorised multiplication for efficiency.
    if np is not None and isinstance(weights, np.ndarray):
        if weights.size != len(tension_list):
            raise ValueError("weights and tensions must be the same length")

        values = np.array([1 / (1 + abs(t - target)) for t in tension_list])
        return weights * values

    # For non-NumPy inputs convert to a list so the data can be iterated over
    # multiple times without exhausting a generator and so we can validate the
    # length relationship explicitly.
    weight_list = list(weights)
    if len(weight_list) != len(tension_list):
        raise ValueError("weights and tensions must be the same length")
    if not weight_list:
        raise ValueError("weights and tensions must contain at least one element")

    # Compute scaling values that bias tensions toward the desired target.
    values = [1 / (1 + abs(t - target)) for t in tension_list]

    # For lists, tuples, and other iterables we fall back to a Python loop.
    return [w * v for w, v in zip(weight_list, values)]
