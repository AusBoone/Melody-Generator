"""Performance helpers and optional profiling utilities."""

from __future__ import annotations

import cProfile
import io
import pstats
from contextlib import contextmanager

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


def compute_base_weights(intervals, chord_mask, prev_interval):
    """Return Markov-style weights for candidate intervals.

    Parameters
    ----------
    intervals:
        Absolute interval sizes from the previous note. Can be a list or
        ``numpy.ndarray``.
    chord_mask:
        Boolean mask indicating which candidates are chord tones.
    prev_interval:
        Size of the previous melodic interval. ``-1`` means no prior interval.
    """

    if np is not None:
        arr = np.array(intervals, dtype=np.float64)
        mask = np.array(chord_mask, dtype=np.uint8)
        return _jit_weights(arr, mask, float(prev_interval if prev_interval is not None else -1)).tolist()
    return _jit_weights(intervals, chord_mask, float(prev_interval if prev_interval is not None else -1))


@contextmanager
def profile(output: io.TextIOBase | None = None):
    """Context manager that records cProfile statistics for a block."""

    pr = cProfile.Profile()
    pr.enable()
    try:
        yield pr
    finally:
        pr.disable()
        if output is not None:
            stats = pstats.Stats(pr, stream=output).strip_dirs().sort_stats("cumulative")
            stats.print_stats(20)


