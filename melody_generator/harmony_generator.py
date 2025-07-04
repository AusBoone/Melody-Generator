"""Simple chord progression and harmonic rhythm generator.

This module offers lightweight helpers for constructing a chord
progression and matching harmonic rhythm (duration of each chord).
It intentionally keeps the rules minimal so unit tests can run
without heavy dependencies.

Example
-------
>>> chords, rhythm = generate_progression("C", 4)
>>> chords
['C', 'F', 'G', 'C']
>>> rhythm
[1.0, 1.0, 2.0, 0.5]
"""

from __future__ import annotations

import random
from typing import List, Tuple

from . import CHORDS, SCALE

# Common four-chord pop progressions encoded as degrees relative to the key
_DEGREE_PATTERNS = [
    [0, 3, 4, 0],  # I-IV-V-I
    [0, 5, 3, 4],  # I-vi-IV-V
    [0, 3, 0, 4],  # I-IV-I-V
]

# Basic harmonic rhythms measured in beats per chord
_RHYTHM_PATTERNS = [
    [1.0, 1.0, 1.0, 1.0],  # change every beat
    [2.0, 1.0, 1.0],        # half-note then quarters
    [1.0, 2.0, 1.0],        # quarter-note, half-note, quarter
]


def _degree_to_chord(key: str, idx: int) -> str:
    """Return a chord name for ``idx`` scale degree within ``key``.

    Chords default to major/minor triads derived from the key signature.
    When the resulting name is unknown a random fallback from ``CHORDS`` is
    used so the output always contains valid chord symbols.
    """

    notes = SCALE[key]
    is_minor = key.endswith("m")
    if is_minor:
        qualities = ["m", "dim", "", "m", "m", "", ""]
    else:
        qualities = ["", "m", "m", "", "", "m", "dim"]
    note = notes[idx % len(notes)]
    quality = qualities[idx % len(qualities)]
    chord = note + ("" if quality == "dim" else quality)
    if chord not in CHORDS:
        chord = random.choice(list(CHORDS.keys()))
    return chord


def generate_progression(key: str, length: int = 4) -> Tuple[List[str], List[float]]:
    """Create a chord progression and harmonic rhythm for ``key``.

    Parameters
    ----------
    key:
        Musical key used to derive chord qualities. Must exist in ``SCALE``.
    length:
        Number of chords to return. Defaults to ``4``.

    Returns
    -------
    tuple(list[str], list[float])
        ``(chords, rhythm)`` where ``chords`` is a list of chord names and
        ``rhythm`` gives the duration in beats of each chord.

    Raises
    ------
    ValueError
        If ``key`` is unknown or ``length`` is non-positive.
    """

    if key not in SCALE:
        raise ValueError(f"Unknown key '{key}'")
    if length <= 0:
        raise ValueError("length must be positive")

    degrees = random.choice(_DEGREE_PATTERNS)
    chords = [_degree_to_chord(key, d) for d in degrees]
    rhythm = random.choice(_RHYTHM_PATTERNS)
    chords = (chords * (length // len(chords) + 1))[:length]
    rhythm = (rhythm * (length // len(rhythm) + 1))[:length]
    return chords, rhythm
