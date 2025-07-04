"""Utilities for detecting basic counterpoint issues."""

from __future__ import annotations

from . import note_to_midi

try:
    import numpy as np  # type: ignore
except Exception:  # pragma: no cover - optional
    np = None


def _direction(a: str, b: str) -> int:
    """Return ``1`` for upward, ``-1`` for downward and ``0`` for repeated notes."""

    diff = note_to_midi(b) - note_to_midi(a)
    if diff > 0:
        return 1
    if diff < 0:
        return -1
    return 0


def parallel_fifth_or_octave(prev_a: str, prev_b: str, next_a: str, next_b: str) -> bool:
    """Return ``True`` if motion forms parallel fifths or octaves."""

    interval1 = abs(note_to_midi(prev_a) - note_to_midi(prev_b)) % 12
    interval2 = abs(note_to_midi(next_a) - note_to_midi(next_b)) % 12
    if interval1 in {7, 0} and interval2 == interval1:
        dir_a = note_to_midi(next_a) - note_to_midi(prev_a)
        dir_b = note_to_midi(next_b) - note_to_midi(prev_b)
        return (dir_a > 0 and dir_b > 0) or (dir_a < 0 and dir_b < 0)
    return False


def counterpoint_penalty(
    prev_note: str,
    candidate: str,
    *,
    prev_dir: int | None = None,
    prev_interval: int | None = None,
) -> float:
    """Return a bias encouraging contrary motion and avoiding parallels.

    Parameters
    ----------
    prev_note:
        The previously chosen melody note.
    candidate:
        Candidate note being considered as the next step.
    prev_dir:
        Direction of the last melodic interval ``-1`` for down, ``1`` for up or
        ``0`` for a repeated note.
    prev_interval:
        Semitone distance of the last interval. Used to detect consecutive
        perfect fifths or octaves.

    Returns
    -------
    float
        Positive values reward the candidate while negative values penalise it.
    """

    current_dir = _direction(prev_note, candidate)
    current_size = abs(note_to_midi(candidate) - note_to_midi(prev_note))

    adjustment = 0.0
    if (
        prev_interval in {7, 12}
        and current_size in {7, 12}
        and prev_dir is not None
        and prev_dir == current_dir != 0
    ):
        adjustment -= 0.5

    if prev_dir is not None and current_dir * prev_dir < 0:
        adjustment += 0.2

    return adjustment


def counterpoint_penalties(
    prev_note: str,
    candidates: list[str] | tuple[str, ...],
    *,
    prev_dir: int | None = None,
    prev_interval: int | None = None,
) -> "np.ndarray | list[float]":
    """Return penalties for multiple ``candidates`` at once.

    The vectorized implementation uses :mod:`numpy` to compute motion
    directions and interval sizes in bulk. If ``numpy`` is not available the
    function falls back to a list comprehension calling
    :func:`counterpoint_penalty` for each candidate.

    Parameters
    ----------
    prev_note:
        The previously selected melody note.
    candidates:
        Possible next notes to evaluate.
    prev_dir:
        Direction of the previous interval as ``-1`` for down, ``1`` for up or
        ``0`` for a repeated note.
    prev_interval:
        Size of the previous interval in semitones.

    Returns
    -------
    numpy.ndarray | list[float]
        Per-candidate penalty adjustments.
    """

    if np is None:
        return [
            counterpoint_penalty(
                prev_note,
                cand,
                prev_dir=prev_dir,
                prev_interval=prev_interval,
            )
            for cand in candidates
        ]

    prev_m = note_to_midi(prev_note)
    cand_m = np.fromiter((note_to_midi(c) for c in candidates), dtype=np.int16)
    dirs = np.sign(cand_m - prev_m)
    sizes = np.abs(cand_m - prev_m)
    result = np.zeros(len(candidates), dtype=np.float64)

    if prev_interval in {7, 12} and prev_dir is not None:
        mask = ((sizes == 7) | (sizes == 12)) & (dirs == prev_dir) & (dirs != 0)
        result[mask] -= 0.5

    if prev_dir is not None:
        opp = dirs * prev_dir < 0
        result[opp] += 0.2

    return result


def parallel_fifths_mask(
    prev_a: str,
    prev_b: str,
    candidates: list[str] | tuple[str, ...],
    next_b: str,
) -> "np.ndarray | list[bool]":
    """Return a boolean mask for parallel fifth/octave motion.

    Each element corresponds to ``candidates`` and indicates whether that
    choice would form parallel fifths or octaves with the bass line.

    The computation is vectorized when :mod:`numpy` is available. Otherwise a
    simple list comprehension delegates to :func:`parallel_fifth_or_octave`.
    """

    if np is None:
        return [parallel_fifth_or_octave(prev_a, prev_b, c, next_b) for c in candidates]

    prev_a_m = note_to_midi(prev_a)
    prev_b_m = note_to_midi(prev_b)
    next_b_m = note_to_midi(next_b)

    interval1 = abs(prev_a_m - prev_b_m) % 12
    if interval1 not in {0, 7}:
        return np.zeros(len(candidates), dtype=bool)

    cand_m = np.fromiter((note_to_midi(c) for c in candidates), dtype=np.int16)
    interval2 = np.abs(cand_m - next_b_m) % 12
    dir_a = cand_m - prev_a_m
    dir_b = next_b_m - prev_b_m

    mask = (interval2 == interval1) & (((dir_a > 0) & (dir_b > 0)) | ((dir_a < 0) & (dir_b < 0)))
    return mask
