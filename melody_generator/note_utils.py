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

# Modification Summary
# ---------------------
# * Improved error reporting in ``note_to_midi`` by raising a descriptive
#   ``ValueError`` when an unknown note name is encountered. Previously a bare
#   ``KeyError`` was re-raised, which obscured the cause for callers.
# * Added explicit MIDI range validation to ``note_to_midi``. Instead of
#   silently clamping values outside ``0-127``, the function now raises a
#   ``ValueError`` so callers can handle out-of-range notes knowingly.
# * Introduced validation in ``midi_to_note`` to ensure MIDI numbers lie
#   within the valid ``0-127`` range. Out-of-range values now raise a
#   descriptive ``ValueError`` rather than producing incorrect results.

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
        If ``note`` is not properly formatted or if the computed MIDI value
        falls outside the allowed ``0-127`` range.
    """

    # Validate the incoming note string. The regular expression ensures a
    # letter A–G followed by an optional accidental and a signed integer
    # octave. Examples: ``C#4``, ``Gb9``, ``C-1``.
    match = re.fullmatch(r"([A-Ga-g][#b]?)(-?\d+)", note)
    if not match:
        logging.error("Invalid note format: %s", note)
        raise ValueError(f"Invalid note format: {note}")

    note_name, octave_str = match.groups()
    # MIDI's octave numbers are offset by one relative to scientific pitch
    # notation, hence the ``+ 1`` adjustment.
    octave = int(octave_str) + 1
    note_name = note_name.capitalize()

    # Normalize flats to their enharmonic sharp equivalents so the lookup
    # table only needs sharp names. ``Db`` → ``C#`` etc.
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
        logging.error("Unknown note name: %s", note_name)
        # Convert the internal KeyError into a user-facing ValueError so that
        # callers receive a clear message about the invalid note name.
        raise ValueError(f"Unknown note name: {note_name}")

    # Compute the MIDI value by adding the semitone index to the octave offset.
    midi_val = note_idx + (octave * 12)

    # MIDI defines valid note numbers in the inclusive range 0–127. Rather than
    # silently clamping out-of-range values, raise a ``ValueError`` so calling
    # code can either correct the input or handle the issue explicitly.
    #
    # Typical cases:
    #   * ``C-1`` → 0 (valid lower boundary)
    #   * ``G9``  → 127 (valid upper boundary)
    # Edge cases triggering errors:
    #   * ``C-2`` → -12 (below range)
    #   * ``C10`` → 132 (above range)
    if not 0 <= midi_val <= 127:
        logging.error("MIDI value out of range: %s -> %d", note, midi_val)
        raise ValueError(
            f"Computed MIDI value {midi_val} out of range 0-127 for note {note}"
        )

    return midi_val


def midi_to_note(midi_note: int) -> str:
    """Convert a MIDI number into a note name using sharps.

    Parameters
    ----------
    midi_note:
        Integer representing the MIDI note number. Valid values range from
        ``0`` (``C-1``) through ``127`` (``G9``).

    Returns
    -------
    str
        Note name with octave, e.g. ``C4``. Sharps are used for accidentals
        to maintain consistency with ``note_to_midi``.

    Raises
    ------
    ValueError
        If ``midi_note`` is outside the inclusive ``0-127`` range. A
        ``TypeError`` may be raised by Python if a non-integer is supplied.

    Examples
    --------
    >>> midi_to_note(60)
    'C4'
    >>> midi_to_note(61)
    'C#4'
    >>> midi_to_note(-1)
    Traceback (most recent call last):
        ...
    ValueError: MIDI note -1 out of range 0-127
    """

    # MIDI defines 128 discrete notes; values outside 0-127 are invalid and
    # should be rejected to avoid producing nonsensical pitches.
    if not 0 <= midi_note <= 127:
        raise ValueError(f"MIDI note {midi_note} out of range 0-127")

    # Determine the octave by integer division and map the remaining semitone
    # offset to a pitch class name. The note names mirror those used in
    # ``note_to_midi`` so round-trip conversions are stable.
    octave = midi_note // 12 - 1
    name = NOTES[midi_note % 12]
    return f"{name}{octave}"


def get_interval(note1: str, note2: str) -> int:
    """Return the interval between ``note1`` and ``note2`` in semitones."""

    return abs(note_to_midi(note1) - note_to_midi(note2))

