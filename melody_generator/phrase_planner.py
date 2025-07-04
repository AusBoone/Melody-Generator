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


class PhrasePlanner:
    """Hierarchical planner generating a phrase skeleton then filling it in."""

    def plan_skeleton(self, chords: List[str], tension_curve: List[float]) -> List[tuple[int, str]]:
        """Return bar-level anchor notes for ``chords``.

        Parameters
        ----------
        chords:
            Sequence of chord names aligning with the phrase bars.
        tension_curve:
            Tension values per bar used to locate peaks and valleys.

        Returns
        -------
        List[Tuple[int, str]]
            ``(index, note)`` pairs marking structural pivots.

        Raises
        ------
        ValueError
            If input lists are empty or lengths do not match.
        """

        if not chords:
            raise ValueError("chords must not be empty")
        if len(tension_curve) < len(chords):
            raise ValueError("tension_curve must cover every chord")

        anchors: List[tuple[int, str]] = []
        for i, chord in enumerate(chords):
            from . import CHORDS, canonical_chord  # Local import avoids circular
            # dependency when ``melody_generator`` imports this module during
            # package initialization.
            prev = tension_curve[i - 1] if i > 0 else tension_curve[i]
            curr = tension_curve[i]
            nxt = tension_curve[i + 1] if i + 1 < len(tension_curve) else tension_curve[i]

            is_peak = curr >= prev and curr >= nxt
            is_valley = curr <= prev and curr <= nxt
            if i == 0 or i == len(chords) - 1 or is_peak or is_valley:
                root = CHORDS[canonical_chord(chord)][0]
                anchors.append((i, root))
        return anchors

    def infill_skeleton(self, skeleton: List[tuple[int, str]], motif: List[str]) -> List[str]:
        """Fill notes between ``skeleton`` anchors using ``motif``.

        Parameters
        ----------
        skeleton:
            Ordered list of ``(index, note)`` pairs starting at ``0``.
        motif:
            Short sequence repeated to fill the gaps. Must not be empty.

        Returns
        -------
        List[str]
            Full melody including anchor notes and interpolated motif notes.

        Raises
        ------
        ValueError
            If ``skeleton`` or ``motif`` is empty or indices are not ascending
            from ``0``.
        """

        if not skeleton:
            raise ValueError("skeleton must not be empty")
        if not motif:
            raise ValueError("motif must not be empty")

        indices = [idx for idx, _ in skeleton]
        if indices[0] != 0 or indices != sorted(indices):
            raise ValueError("skeleton indices must start at 0 and be ascending")

        melody: List[str] = []
        motif_pos = 0
        for i, (idx, note) in enumerate(skeleton):
            melody.append(note)
            next_idx = skeleton[i + 1][0] if i + 1 < len(skeleton) else idx
            gap = next_idx - idx - 1
            for _ in range(gap):
                melody.append(motif[motif_pos % len(motif)])
                motif_pos += 1
        return melody
