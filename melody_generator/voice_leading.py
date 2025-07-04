"""Utilities for detecting basic counterpoint issues."""

from __future__ import annotations

from . import note_to_midi


def parallel_fifth_or_octave(prev_a: str, prev_b: str, next_a: str, next_b: str) -> bool:
    """Return ``True`` if motion forms parallel fifths or octaves."""

    interval1 = abs(note_to_midi(prev_a) - note_to_midi(prev_b)) % 12
    interval2 = abs(note_to_midi(next_a) - note_to_midi(next_b)) % 12
    if interval1 in {7, 0} and interval2 == interval1:
        dir_a = note_to_midi(next_a) - note_to_midi(prev_a)
        dir_b = note_to_midi(next_b) - note_to_midi(prev_b)
        return (dir_a > 0 and dir_b > 0) or (dir_a < 0 and dir_b < 0)
    return False
