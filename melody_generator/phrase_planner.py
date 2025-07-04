"""High-level phrase planning helpers for Melody-Generator.

This module provides a lightweight method for describing a phrase before
actual note generation occurs.  A phrase plan contains three components:

``length``
    Total number of notes in the phrase.

``pitch_range``
    Tuple ``(min_octave, max_octave)`` restricting all generated notes.

``tension_profile``
    List of floats roughly describing how musical tension should rise and
    fall across the phrase. Values range from ``0.0`` (relaxed) to ``1.0``
    (maximum tension).

The :func:`generate_phrase_plan` helper returns a default plan with a simple
arch-shaped tension curve but callers may construct :class:`PhrasePlan`
objects directly for custom behaviour.
"""

from dataclasses import dataclass
from typing import List, Tuple


# Re-declare octave limits locally to avoid circular imports. These values must
# stay in sync with :data:`melody_generator.MIN_OCTAVE` and
# :data:`melody_generator.MAX_OCTAVE`.
MIN_OCTAVE = 0
MAX_OCTAVE = 8


@dataclass
class PhrasePlan:
    """Container for high-level phrase information."""

    length: int
    pitch_range: Tuple[int, int]
    tension_profile: List[float]


def generate_phrase_plan(num_notes: int, base_octave: int, pitch_span: int = 2) -> PhrasePlan:
    """Create a basic :class:`PhrasePlan` for ``num_notes``.

    Parameters
    ----------
    num_notes:
        Desired number of notes in the phrase. Must be positive.
    base_octave:
        Starting octave for the phrase. The lower bound of ``pitch_range``.
    pitch_span:
        Number of additional octaves the phrase may reach above
        ``base_octave``. Must be zero or positive. Defaults to ``2`` to
        allow occasional leaps beyond the immediate octave.

    Returns
    -------
    PhrasePlan
        Object describing the phrase outline.

    Raises
    ------
    ValueError
        If ``num_notes`` is non-positive or ``pitch_span`` is negative or the
        resulting pitch range falls outside the global MIDI limits.
    """

    if num_notes <= 0:
        raise ValueError("num_notes must be positive")
    if pitch_span < 0:
        raise ValueError("pitch_span must be non-negative")

    min_oct = max(MIN_OCTAVE, base_octave)
    max_oct = min(MAX_OCTAVE, base_octave + pitch_span)
    if min_oct > max_oct:
        raise ValueError("computed pitch range is invalid")

    # Shape tension to rise toward the centre then fall back down.
    up_len = num_notes // 2
    down_len = num_notes - up_len
    rise = [i / max(1, up_len) for i in range(up_len)]
    fall = [1 - (i / max(1, down_len)) for i in range(down_len)]
    tension = (rise + fall)[: num_notes]

    return PhrasePlan(num_notes, (min_oct, max_oct), tension)
