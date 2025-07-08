"""Utility functions for translating note names to MIDI numbers.

This module groups helpers dealing with note representation conversions.
The functions are separated from the main package so they can be reused by
both the CLI and GUI without pulling in heavier dependencies.

Example
-------
>>> from melody_generator.note_utils import note_to_midi
>>> note_to_midi("C4")
60
"""

from __future__ import annotations

import logging
import re
from functools import lru_cache

from . import NOTE_TO_SEMITONE, NOTES

__all__ = ["note_to_midi", "midi_to_note", "get_interval"]


@lru_cache(maxsize=None)
def note_to_midi(note: str) -> int:
    """Convert a note string such as ``C#4`` into a MIDI number.

    Parameters
    ----------
    note:
        Note name including octave. Octaves may be negative or contain
        multiple digits.

    Returns
    -------
    int
        MIDI note number in the range ``0-127``.

    Raises
    ------
    ValueError
        If ``note`` is not properly formatted.
    """

    match = re.fullmatch(r"([A-Ga-g][#b]?)(-?\d+)", note)
    if not match:
        logging.error("Invalid note format: %s", note)
        raise ValueError(f"Invalid note format: {note}")

    note_name, octave_str = match.groups()
    octave = int(octave_str) + 1
    note_name = note_name.capitalize()

    flat_to_sharp = {
        "Db": "C#",
        "Eb": "D#",
        "Fb": "E",
        "Gb": "F#",
        "Ab": "G#",
        "Bb": "A#",
        "Cb": "B",
    }
    note_name = flat_to_sharp.get(note_name, note_name)

    try:
        note_idx = NOTE_TO_SEMITONE[note_name]
    except KeyError:
        logging.error("Note %s not recognized.", note_name)
        raise

    midi_val = note_idx + (octave * 12)
    return max(0, min(127, midi_val))


def midi_to_note(midi_note: int) -> str:
    """Convert a MIDI number back into a note string using sharps."""

    octave = midi_note // 12 - 1
    name = NOTES[midi_note % 12]
    return f"{name}{octave}"


def get_interval(note1: str, note2: str) -> int:
    """Return the interval between ``note1`` and ``note2`` in semitones."""

    return abs(note_to_midi(note1) - note_to_midi(note2))

