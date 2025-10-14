"""Performance helpers and optional profiling utilities.

This file defines ``compute_base_weights`` which generates Markov-style
transition weights for melody intervals and a :func:`profile` context manager
for collecting ``cProfile`` statistics.  ``NumPy`` and ``Numba`` are detected
at runtime so the algorithms can accelerate themselves transparently when
available without adding hard dependencies.

Summary of recent changes
-------------------------
* ``compute_base_weights`` validates that ``intervals`` and ``chord_mask`` are
  aligned sequences of equal length and rejects negative interval magnitudes so
  misuse surfaces as descriptive ``ValueError`` exceptions rather than obscure
  ``IndexError`` failures inside the weighting loop.
* ``profile`` accepts ``sort_by`` and ``limit`` keyword arguments so callers can
  tailor how profiling results are presented, and both parameters are validated
  eagerly for clearer error handling.

Example
-------
>>> compute_base_weights([2, 4], [True, False], 2)
[1.7999999999999998, 0.48]

Design Notes
------------
- The Numba ``jit`` function is optional; pure Python fallbacks are used when
  the import fails so unit tests remain fast.
- Transition and similarity lookup tables are stored as arrays for speed but
  plain lists are substituted when ``numpy`` is missing.
"""

from __future__ import annotations

import cProfile
import io
import pstats
from contextlib import contextmanager
from typing import Optional

try:
    import numpy as np  # type: ignore
except Exception:  # pragma: no cover - optional
    np = None

try:
    from numba import njit  # type: ignore
except Exception:  # pragma: no cover - optional
    def njit(*args, **kwargs):  # type: ignore
        def wrapper(func):
            return func
        if args:
            return args[0]
        return wrapper


# Transition weights and similarity weights as arrays for JIT consumption.
# Indices beyond the array length fall back to a constant default value.
_TRANSITION_LOOKUP = np.array([1.2, 1.0, 0.8, 0.6, 0.4, 0.3, 0.1]) if np is not None else [1.2, 1.0, 0.8, 0.6, 0.4, 0.3, 0.1]
_SIMILARITY_LOOKUP = np.array([1.0, 0.8, 0.6, 0.4]) if np is not None else [1.0, 0.8, 0.6, 0.4]
_TRANSITION_DEFAULT = 0.2
_SIMILARITY_DEFAULT = 0.2
_CHORD_WEIGHT = 1.5


if np is not None:

    @njit  # pragma: no cover - compiled path
    def _jit_weights(intervals: np.ndarray, mask: np.ndarray, prev_interval: float) -> np.ndarray:
        """Return base weights for each interval using Numba."""
        result = np.empty(len(intervals), dtype=np.float64)
        for i in range(len(intervals)):
            idx = int(intervals[i])
            if idx < _TRANSITION_LOOKUP.shape[0]:
                w = _TRANSITION_LOOKUP[idx]
            else:
                w = _TRANSITION_DEFAULT
            if prev_interval >= 0:
                diff = abs(intervals[i] - prev_interval)
                d_idx = int(diff)
                if d_idx < _SIMILARITY_LOOKUP.shape[0]:
                    w *= _SIMILARITY_LOOKUP[d_idx]
                else:
                    w *= _SIMILARITY_DEFAULT
            if mask[i]:
                w *= _CHORD_WEIGHT
            result[i] = w
        return result
else:
    def _jit_weights(intervals, mask, prev_interval):  # pragma: no cover - fallback
        result = []
        for idx, val in enumerate(intervals):
            i = int(val)
            w = _TRANSITION_LOOKUP[i] if i < len(_TRANSITION_LOOKUP) else _TRANSITION_DEFAULT
            if prev_interval >= 0:
                diff = abs(val - prev_interval)
                d = int(diff)
                w *= _SIMILARITY_LOOKUP[d] if d < len(_SIMILARITY_LOOKUP) else _SIMILARITY_DEFAULT
            if mask[idx]:
                w *= _CHORD_WEIGHT
            result.append(w)
        return result


def compute_base_weights(intervals, chord_mask, prev_interval=None):
    """Return Markov-style weights for candidate intervals.

    Parameters
    ----------
    intervals:
        Absolute interval sizes from the previous note. Can be a list or
        ``numpy.ndarray``. Values must be non-negative and the collection must
        remain aligned with ``chord_mask``.
    chord_mask:
        Boolean mask indicating which candidates are chord tones. Values are
        coerced to integers so any truthy/falsy objects are acceptable.
    prev_interval:
        Size of the previous melodic interval. ``None`` or ``-1`` signal the
        absence of context.
    """

    # Normalise the ``prev_interval`` input so downstream weighting logic only
    # needs to handle a single sentinel value. ``None`` is equivalent to ``-1``
    # (meaning “no previous interval”). Any other negative values are rejected
    # as they would imply impossible interval sizes.
    if prev_interval is None:
        prev_interval = -1
    try:
        prev_interval_val = float(prev_interval)
    except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
        raise ValueError("prev_interval must be numeric or None") from exc
    if prev_interval_val < 0 and prev_interval_val != -1:
        raise ValueError("prev_interval must be -1 or non-negative")

    if np is not None:
        # ``np.asarray`` ensures generators are fully realised and provides a
        # consistent ``ndarray`` interface for validation and JIT execution.
        interval_seq = list(intervals)
        mask_seq = list(chord_mask)
        arr = np.asarray(interval_seq, dtype=np.float64)
        mask = np.asarray(mask_seq, dtype=np.uint8)

        if arr.ndim != 1 or mask.ndim != 1:
            raise ValueError("intervals and chord_mask must be one-dimensional sequences")
        if arr.shape[0] != mask.shape[0]:
            raise ValueError("intervals and chord_mask must be the same length")
        if (arr < 0).any():
            raise ValueError("interval values must be non-negative")

        return _jit_weights(arr, mask, prev_interval_val).tolist()

    # Without NumPy we perform equivalent validation using pure Python lists so
    # behaviour remains consistent across optional dependency configurations.
    interval_list = list(intervals)
    mask_list = [bool(val) for val in chord_mask]
    if len(interval_list) != len(mask_list):
        raise ValueError("intervals and chord_mask must be the same length")
    if any(val < 0 for val in interval_list):
        raise ValueError("interval values must be non-negative")

    return _jit_weights(interval_list, mask_list, prev_interval_val)


@contextmanager
def profile(
    output: Optional[io.TextIOBase] = None,
    *,
    sort_by: str = "cumulative",
    limit: Optional[int] = 20,
):
    """Context manager that records cProfile statistics for a block.

    Parameters
    ----------
    output:
        File-like object that receives the profiling report. When ``None`` the
        report is suppressed but the caller still receives the raw
        :class:`cProfile.Profile` object for manual inspection.
    sort_by:
        Sort key forwarded to :meth:`pstats.Stats.sort_stats`. Common values are
        ``"cumulative"`` and ``"time"``.
    limit:
        Optional cap on how many functions are displayed in the printed report.
        ``None`` prints the entire table. Values must be positive when
        provided.
    """

    if limit is not None and limit <= 0:
        raise ValueError("limit must be None or a positive integer")
    if not isinstance(sort_by, str) or not sort_by:
        raise ValueError("sort_by must be a non-empty string")

    pr = cProfile.Profile()
    pr.enable()
    try:
        yield pr
    finally:
        pr.disable()
        if output is not None:
            stats = pstats.Stats(pr, stream=output).strip_dirs().sort_stats(sort_by)
            if limit is None:
                stats.print_stats()
            else:
                stats.print_stats(limit)


