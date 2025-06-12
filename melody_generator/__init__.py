#!/usr/bin/env python3
"""
Melody Generator:
A Python script that creates a random melody in a specified key with a given BPM and time signature.
Features include:
- Integrated rhythmic patterns for note durations.
- Enhanced melody generation with controlled randomness.
- Robust fallback mechanisms for note selection.
- Both GUI (tkinter) and CLI interfaces.
- Detailed logging and improved documentation.
Author: Austin Boone
Modified: February 15, 2025
"""

__version__ = "0.1.0"

import mido
from mido import Message, MidiFile, MidiTrack
import random
import sys
import logging
import argparse
from importlib import import_module
import json
from pathlib import Path
from typing import List, Tuple, Optional
import os

# Default path for storing user preferences
# The file lives in the user's home directory so settings persist
# between runs of the application.
env_path = os.environ.get("MELODY_SETTINGS_FILE")
if env_path:
    DEFAULT_SETTINGS_FILE = Path(env_path).expanduser()
else:
    DEFAULT_SETTINGS_FILE = Path.home() / ".melody_generator_settings.json"


def load_settings(path: Path = DEFAULT_SETTINGS_FILE) -> dict:
    """Load saved user settings from ``path`` if it exists."""
    # Prefer the user's saved options but fall back to an empty
    # dictionary when the settings file is missing or unreadable.
    if path.is_file():
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception as exc:  # pragma: no cover - log error but return defaults
            logging.error(f"Could not load settings: {exc}")
    return {}


def save_settings(settings: dict, path: Path = DEFAULT_SETTINGS_FILE) -> None:
    """Save user ``settings`` to ``path`` as JSON."""
    # Any IOError is logged but ignored so failing to save
    # preferences never prevents melody generation.
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(settings, fh, indent=2)
    except Exception as exc:  # pragma: no cover - log error only
        logging.error(f"Could not save settings: {exc}")


# Define note names and scales
# NOTE_TO_SEMITONE maps both sharp and flat spellings to the correct
# semitone offset within an octave so that functions like ``note_to_midi``
# can handle enharmonic notes (e.g. ``Db`` and ``C#``).
NOTE_TO_SEMITONE = {
    'C': 0,
    'B#': 0,
    'C#': 1,
    'Db': 1,
    'D': 2,
    'D#': 3,
    'Eb': 3,
    'E': 4,
    'Fb': 4,
    'E#': 5,
    'F': 5,
    'F#': 6,
    'Gb': 6,
    'G': 7,
    'G#': 8,
    'Ab': 8,
    'A': 9,
    'A#': 10,
    'Bb': 10,
    'B': 11,
    'Cb': 11,
}

# Keep a basic list of note names (using sharps) for any other logic that
# relies on it.
NOTES: List[str] = [
    'C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'
]

# Map key names to the notes that make up their diatonic scale. Functions that
# generate melodies or harmonies reference this to stay in the chosen key.
SCALE = {
    'C': ['C', 'D', 'E', 'F', 'G', 'A', 'B'],
    'C#': ['C#', 'D#', 'E#', 'F#', 'G#', 'A#', 'B#'],
    'D': ['D', 'E', 'F#', 'G', 'A', 'B', 'C#'],
    'Eb': ['Eb', 'F', 'G', 'Ab', 'Bb', 'C', 'D'],
    'E': ['E', 'F#', 'G#', 'A', 'B', 'C#', 'D#'],
    'F': ['F', 'G', 'A', 'Bb', 'C', 'D', 'E'],
    'F#': ['F#', 'G#', 'A#', 'B', 'C#', 'D#', 'E#'],
    'G': ['G', 'A', 'B', 'C', 'D', 'E', 'F#'],
    'Ab': ['Ab', 'Bb', 'C', 'Db', 'Eb', 'F', 'G'],
    'A': ['A', 'B', 'C#', 'D', 'E', 'F#', 'G#'],
    'Bb': ['Bb', 'C', 'D', 'Eb', 'F', 'G', 'A'],
    'B': ['B', 'C#', 'D#', 'E', 'F#', 'G#', 'A#'],
    # Minor keys
    'Cm': ['C', 'D', 'Eb', 'F', 'G', 'Ab', 'Bb'],
    'C#m': ['C#', 'D#', 'E', 'F#', 'G#', 'A', 'B'],
    'Dm': ['D', 'E', 'F', 'G', 'A', 'Bb', 'C'],
    'Ebm': ['Eb', 'F', 'Gb', 'Ab', 'Bb', 'Cb', 'Db'],
    'Em': ['E', 'F#', 'G', 'A', 'B', 'C', 'D'],
    'Fm': ['F', 'G', 'Ab', 'Bb', 'C', 'Db', 'Eb'],
    'F#m': ['F#', 'G#', 'A', 'B', 'C#', 'D', 'E'],
    'Gm': ['G', 'A', 'Bb', 'C', 'D', 'Eb', 'F'],
    'G#m': ['G#', 'A#', 'B', 'C#', 'D#', 'E', 'F#'],
    'Am': ['A', 'B', 'C', 'D', 'E', 'F', 'G'],
    'Bbm': ['Bb', 'C', 'Db', 'Eb', 'F', 'Gb', 'Ab'],
    'Bm': ['B', 'C#', 'D', 'E', 'F#', 'G', 'A']
}

# Programmatically extend ``SCALE`` with several common modes and pentatonic
# scales.  This keeps the list of keys manageable while providing additional
# variety when generating melodies.

def _build_scale(root: str, pattern: List[int]) -> List[str]:
    """Return a scale starting at ``root`` following ``pattern`` intervals.

    ``pattern`` is a sequence of semitone offsets from the root note that
    defines the mode.  The function walks the pattern wrapping around the
    twelve-tone chromatic scale to create the resulting list of note names.
    """
    root_idx = NOTE_TO_SEMITONE[root]
    notes = []
    for interval in pattern:
        # Step through the interval pattern building the scale one note at a time
        idx = (root_idx + interval) % 12
        notes.append(NOTES[idx])
    return notes


# Interval patterns for a few additional modes.  Values are semitone offsets
# from the root note.  Only sharps are used for simplicity.
# Mapping of mode name to the sequence of semitone steps that forms the mode.
_MODE_PATTERNS = {
    "dorian": [0, 2, 3, 5, 7, 9, 10],
    "mixolydian": [0, 2, 4, 5, 7, 9, 10],
    # Pentatonic only contains five degrees so it produces a shorter scale.
    "pentatonic": [0, 2, 4, 7, 9],
}

for note in NOTES:
    for mode, pattern in _MODE_PATTERNS.items():
        # Pre-compute common modal scales for every root note.  The resulting
        # key names take the form "C_dorian", "G_pentatonic", etc.
        SCALE[f"{note}_{mode}"] = _build_scale(note, pattern)

# ``CHORDS`` maps chord names to the notes they contain. This lookup table is
# used when constructing harmony lines and validating chord progressions.
CHORDS = {
    "C": ["C", "E", "G"],
    "Cm": ["C", "Eb", "G"],
    "C#": ["C#", "E#", "G#"],
    "C#m": ["C#", "E", "G#"],
    "D": ["D", "F#", "A"],
    "Dm": ["D", "F", "A"],
    "Eb": ["Eb", "G", "Bb"],
    "Ebm": ["Eb", "Gb", "Bb"],
    "E": ["E", "G#", "B"],
    "Em": ["E", "G", "B"],
    "F": ["F", "A", "C"],
    "Fm": ["F", "Ab", "C"],
    "F#": ["F#", "A#", "C#"],
    "F#m": ["F#", "A", "C#"],
    "G": ["G", "B", "D"],
    "Gm": ["G", "Bb", "D"],
    "G#": ["G#", "B#", "D#"],
    "G#m": ["G#", "B", "D#"],
    "Ab": ["Ab", "C", "Eb"],
    "Abm": ["Ab", "Cb", "Eb"],
    "A": ["A", "C#", "E"],
    "A#": ["A#", "D", "F"],
    "A#m": ["A#", "C#", "F"],
    "Am": ["A", "C", "E"],
    "Bb": ["Bb", "D", "F"],
    "Bbm": ["Bb", "Db", "F"],
    "B": ["B", "D#", "F#"],
    "Bm": ["B", "D", "F#"],
    "Db": ["Db", "F", "Ab"],
    "Dbm": ["Db", "E", "Ab"]
}

# ``PATTERNS`` stores common rhythmic figures. Each inner list represents a
# sequence of note durations (in fractions of a whole note) that repeat while
# creating the MIDI file.
PATTERNS: List[List[float]] = [
    # Basic march-like rhythm
    [0.25, 0.25, 0.5],    # quarter, quarter, half
    # Simple syncopation with a dotted half
    [0.25, 0.75],         # quarter, dotted half
    # Even half notes
    [0.5, 0.5],           # half, half
    # Dotted quarter pattern often found in waltzes
    [0.375, 0.375, 0.25],  # dotted quarter, dotted quarter, quarter
    # Eighth-note lead in to a half note
    [0.125, 0.125, 0.25, 0.5],  # two eighths, quarter, half
    # Continuous run of sixteenth notes
    [0.0625] * 8          # a run of sixteenth notes
]


def generate_random_chord_progression(key: str, length: int = 4) -> List[str]:
    """Return a simple chord progression for ``key``.

    The progression is chosen from a small set of common patterns in
    popular music.  Chords are derived from the selected key so the
    results fit naturally with generated melodies.
    """

    # Roman numeral progressions for major and minor keys encoded as
    # scale degrees (0 = I/i). These simple loops mimic typical pop
    # progressions and keep the harmony sounding familiar.
    major_patterns = [[0, 3, 4, 0], [0, 5, 3, 4], [0, 3, 0, 4]]
    minor_patterns = [[0, 3, 4, 0], [0, 5, 3, 4], [0, 5, 4, 0]]

    is_minor = key.endswith('m')
    notes = SCALE[key]
    patterns = minor_patterns if is_minor else major_patterns
    # Pick one pattern at random to build the progression
    degrees = random.choice(patterns)

    def degree_to_chord(idx: int) -> str:
        """Return a chord name for the given scale ``idx``.

        The chord quality is derived from the degree and key signature. If
        the computed chord does not exist in :data:`CHORDS` a random chord is
        returned as a safe fallback.
        """

        note = notes[idx % len(notes)]
        if is_minor:
            qualities = ['m', 'dim', '', 'm', 'm', '', '']
        else:
            qualities = ['', 'm', 'm', '', '', 'm', 'dim']
        # Look up the chord quality for this scale degree (major, minor or diminished)
        quality = qualities[idx % len(qualities)]
        chord = note + (quality if quality != 'dim' else '')
        if chord not in CHORDS:
            # Translate enharmonic spellings to match available chord names
            translation = {
                'A#': 'Bb',
                'A#m': 'Bbm',
                'Db': 'C#',
                'Dbm': 'C#m',
                'Ab': 'G#',
                'Abm': 'G#m',
            }
            chord = translation.get(chord, chord)
        return chord if chord in CHORDS else random.choice(list(CHORDS.keys()))

    # Convert degree numbers to concrete chord names
    # (e.g. 0 -> C, 4 -> G when key is C)
    progression = [degree_to_chord(d) for d in degrees]
    if length > len(progression):
        # Pad the progression with random chords if the requested length is longer
        extra = [degree_to_chord(random.randint(0, 5))
                 for _ in range(length - len(progression))]
        # Extend with random chords so the returned list matches ``length``
        progression.extend(extra)
    return progression[:length]


def diatonic_chords(key: str) -> List[str]:
    """Return the diatonic triads for ``key``.

    The chords mirror the quality of each scale degree. Diminished
    chords fall back to their major spelling when an exact match is not
    present in :data:`CHORDS`.
    """

    is_minor = key.endswith('m')
    notes = SCALE[key]
    qualities = ['m', 'dim', '', 'm', 'm', '', ''] if is_minor else ['', 'm', 'm', '', '', 'm', 'dim']
    chords = []
    translation = {
        'A#': 'Bb',
        'A#m': 'Bbm',
        'Db': 'C#',
        'Dbm': 'C#m',
        'Ab': 'G#',
        'Abm': 'G#m',
    }
    for note, qual in zip(notes, qualities):
        chord = note + (qual if qual != 'dim' else '')
        if chord not in CHORDS:
            chord = translation.get(chord, chord)
        if chord in CHORDS and chord not in chords:
            chords.append(chord)
    return chords


def generate_random_rhythm_pattern(length: int = 3) -> List[float]:
    """Create a random rhythmic pattern based on a repeating motif.

    A motif is chosen from a predefined set of short patterns. The motif is
    then repeated until ``length`` durations have been produced.  All note
    lengths come from the same allowed set as before so the return value is
    compatible with older callers.  To keep things from sounding too rigid, a
    small variation may be applied after the first full repetition by replacing
    one value with an eighth note (``0.125``).
    """

    allowed = [0.25, 0.5, 0.75, 0.125, 0.0625, 0]
    motifs = [
        [0.25, 0.25],
        [0.25, 0.5],
        [0.5, 0.25],
        [0.125, 0.125, 0.25],
        [0.75, 0.25],
        [0.5, 0.5],
        [0.25, 0, 0.25],
    ]

    motif = random.choice(motifs)
    pattern = (motif * (length // len(motif) + 1))[:length]

    # Optionally vary after the first full repetition of the motif to add a bit
    # of syncopation while preserving the allowed values.
    if length > len(motif) * 2 and random.random() < 0.3:
        idx = random.randrange(len(motif) * 2, length)
        pattern[idx] = random.choice(allowed)

    return pattern

def note_to_midi(note: str) -> int:
    """
    Convert a note name (with octave) to a MIDI note number.
    Example: 'C#4' -> 61 (with C4 as MIDI note 60).

    Args:
        note (str): Note name (e.g., 'C#4').

    Returns:
        int: Corresponding MIDI note number.
    """
    try:
        # MIDI octaves start at -1 so offset by +1 from the human-readable value
        octave = int(note[-1]) + 1
    except ValueError:
        logging.error(f"Invalid note format: {note}")
        raise

    # Strip the octave number to get the pitch class
    note_name = note[:-1]

    # Map flats to their enharmonic sharps before looking up the semitone index
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
        # Look up the semitone index within the octave
        note_idx = NOTE_TO_SEMITONE[note_name]
    except KeyError:
        logging.error(f"Note {note_name} not recognized.")
        raise

    # MIDI note number is calculated relative to C0 at index 12
    return note_idx + (octave * 12)

def midi_to_note(midi_note: int) -> str:
    """Convert a MIDI note number back to a note string.

    Parameters
    ----------
    midi_note : int
        MIDI note number (0-127).

    Returns
    -------
    str
        Note string using sharps (e.g. ``C#4``).
    """
    octave = midi_note // 12 - 1
    # Wrap around the NOTES list to get the pitch class
    name = NOTES[midi_note % 12]
    return f"{name}{octave}"

def get_interval(note1: str, note2: str) -> int:
    """
    Get the interval between two notes in semitones.

    Args:
        note1 (str): First note (e.g., 'C4').
        note2 (str): Second note (e.g., 'E4').

    Returns:
        int: Interval in semitones.
    """
    # Interval is the absolute difference in semitone numbers
    return abs(note_to_midi(note1) - note_to_midi(note2))

def get_chord_notes(chord: str) -> List[str]:
    """
    Retrieve the notes that make up the given chord.

    Args:
        chord (str): Chord name (e.g., 'C', 'F#m').

    Returns:
        List[str]: List of note names in the chord.
    """
    return CHORDS[chord]

def generate_motif(length: int, key: str, base_octave: int = 4) -> List[str]:
    """
    Generate a motif (short, recurring musical idea) in the specified key.

    Args:
        length (int): Number of notes in the motif.
        key (str): Musical key.
        base_octave (int, optional): Starting octave for the motif. Notes
            primarily fall within ``base_octave`` and ``base_octave + 1``.
            Defaults to ``4``.

    Returns:
        List[str]: List of note names forming the motif.
    """
    notes_in_key = SCALE[key]
    # Choose random notes within the key and place them in the requested octave range
    return [
        random.choice(notes_in_key) + str(random.randint(base_octave, base_octave + 1))
        for _ in range(length)
    ]

def generate_melody(
    key: str,
    num_notes: int,
    chord_progression: List[str],
    motif_length: int = 4,
    time_signature: Tuple[int, int] = (4, 4),
    pattern: Optional[List[float]] = None,
    base_octave: int = 4,
) -> List[str]:
    """Return a melody in ``key`` spanning ``num_notes`` notes.

    The algorithm works in several stages:

    1.  Build a short motif using :func:`generate_motif`.
    2.  Repeat that motif throughout the phrase, shifting it slightly so it does
        not sound overly mechanical.
    3.  When an octave shift occurs, the first note after the change is forced
        into the new register so the transition is audible.
    4.  For each new note, examine the current chord and pick pitches that are
        close to the previous note.  Preference is given to notes within one
        semitone of the best interval found.
    5.  If no suitable candidate exists, choose a random note from the key as a
        safe fallback.
    6.  Large leaps are tracked so the following note can "correct" the motion
        by moving back toward the starting pitch.
    7.  Strong beats (determined from ``pattern`` and ``time_signature``) are
        restricted to chord tones while weaker beats may use any scale note.

    Parameters
    ----------
    key : str
        Musical key for the melody.
    num_notes : int
        Total number of notes to generate.
    chord_progression : List[str]
        Progression to base note choices on.
    motif_length : int, optional
        Length of the initial motif, by default ``4``.
    time_signature : Tuple[int, int], optional
        ``(numerator, denominator)`` pair describing the meter. The
        denominator determines the beat unit used when evaluating
        strong versus weak beats. Defaults to ``(4, 4)``.
    pattern : List[float], optional
        Rhythmic pattern expressed as fractions of a whole note. When
        provided it is used to calculate the start beat of each note so
        downbeats can be aligned with chord tones. If ``None``, a random
        pattern is chosen.
    base_octave : int, optional
        Preferred octave for the melody. Notes typically remain within
        ``base_octave`` to ``base_octave + 1`` with rare octave shifts at
        phrase boundaries. Defaults to ``4``.

    Returns
    -------
    List[str]
        Generated melody as a list of note strings.
    """
    if num_notes < motif_length:
        raise ValueError("num_notes must be greater than or equal to motif_length")

    notes_in_key = SCALE[key]
    if pattern is None:
        pattern = random.choice(PATTERNS)

    beat_unit = 1 / time_signature[1]
    start_beat = 0.0

    # Current octave offset relative to ``base_octave``. This may shift by
    # one at phrase boundaries to vary the register slightly.
    octave_offset = 0

    # Generate the initial motif.
    melody = generate_motif(motif_length, key, base_octave + octave_offset)

    # Adjust the motif so it moves upward in a stepwise fashion.  This provides
    # a clear starting direction for the overall phrase.
    for j in range(1, motif_length):
        prev = melody[j - 1]
        curr = melody[j]
        if note_to_midi(curr) <= note_to_midi(prev):
            name, octave = prev[:-1], int(prev[-1])
            idx = notes_in_key.index(name)
            idx += 1
            if idx >= len(notes_in_key):
                idx -= len(notes_in_key)
                octave += 1
            allowed_min = base_octave + octave_offset
            allowed_max = allowed_min + 1
            octave = max(allowed_min, min(allowed_max, octave))
            melody[j] = notes_in_key[idx] + str(octave)

    # Align motif notes with the underlying harmony on strong beats
    for j in range(motif_length):
        strong = abs(start_beat - round(start_beat)) < 1e-6
        chord = chord_progression[j % len(chord_progression)]
        chord_notes = get_chord_notes(chord)
        if strong:
            name, octv = melody[j][:-1], melody[j][-1]
            if name not in chord_notes:
                closest = min(
                    chord_notes,
                    key=lambda n: abs(
                        note_to_midi(n + octv) - note_to_midi(melody[j])
                    ),
                )
                melody[j] = closest + octv
        start_beat += pattern[j % len(pattern)] / beat_unit

    # Track the direction of the previous large leap so the next note can
    # compensate by moving in the opposite direction.
    leap_dir: Optional[int] = None

    half_point = num_notes // 2

    for i in range(motif_length, num_notes):
        strong = abs(start_beat - round(start_beat)) < 1e-6
        # Determine the current overall direction based on position in the
        # melody.  The first half trends upward and the second half downward.
        direction = 1 if i < half_point else -1

        # At the start of each phrase repeat the motif but shift it by one
        # scale degree in the current direction so the line gradually moves
        # upward then downward.
        if i % motif_length == 0:
            # Occasionally shift the register by an octave to add variety
            diff = 0
            if random.random() < 0.1:
                new_off = max(-1, min(1, octave_offset + random.choice([-1, 1])))
                diff = new_off - octave_offset
                octave_offset = new_off
            elif direction < 0 and octave_offset > 0:
                octave_offset = 0
                diff = -1

            base = melody[i - motif_length]
            name, octave = base[:-1], int(base[-1])
            idx = notes_in_key.index(name)
            new_idx = idx + direction
            if new_idx < 0:
                new_idx += len(notes_in_key)
                octave -= 1
            elif new_idx >= len(notes_in_key):
                new_idx -= len(notes_in_key)
                octave += 1
            allowed_min = base_octave + octave_offset
            allowed_max = allowed_min + 1
            octave += diff
            if diff > 0:
                octave = allowed_max
            elif diff < 0:
                octave = allowed_min
            else:
                octave = max(allowed_min, min(allowed_max, octave))
            new_name = notes_in_key[new_idx]
            chord = chord_progression[i % len(chord_progression)]
            chord_notes = get_chord_notes(chord)
            if strong and new_name not in chord_notes:
                new_name = min(
                    chord_notes,
                    key=lambda n: abs(
                        note_to_midi(n + str(octave))
                        - note_to_midi(new_name + str(octave))
                    ),
                )
            melody.append(new_name + str(octave))
            start_beat += pattern[i % len(pattern)] / beat_unit
            continue
        chord = chord_progression[i % len(chord_progression)]
        chord_notes = get_chord_notes(chord)
        prev_note = melody[-1]
        candidates = []
        min_interval = None

        source_pool = chord_notes if strong else notes_in_key

        # Scan candidate pitches and keep track of which is closest to the
        # previous note. This gives a baseline for selecting smooth motion.
        for note in source_pool:
            for octave in range(base_octave + octave_offset, base_octave + octave_offset + 2):
                candidate_note = note + str(octave)
                interval = get_interval(prev_note, candidate_note)
                if min_interval is None or interval < min_interval:
                    min_interval = interval

        # Collect any notes that are within a semitone of that best interval so
        # we have a small pool of options that still move by a reasonable step.
        if min_interval is not None:
            threshold = min_interval + 1
            for note in source_pool:
                for octave in range(base_octave + octave_offset, base_octave + octave_offset + 2):
                    candidate_note = note + str(octave)
                    interval = get_interval(prev_note, candidate_note)
                    if interval <= threshold:
                        candidates.append(candidate_note)

        # Fallback: If no candidates are found, choose a random note from the key.
        if not candidates:
            logging.warning(
                f"No candidate found for chord {chord} with previous note {prev_note}. Using fallback."
            )
            pool = chord_notes if strong else notes_in_key
            fallback_note = random.choice(pool) + str(
                random.randint(base_octave + octave_offset, base_octave + octave_offset + 1)
            )
            candidates.append(fallback_note)

        # If the previous interval was a leap, favour notes that move back
        # toward the origin by a small step.
        if leap_dir is not None:
            # Bias selection toward motion opposite the previous large leap
            filtered = [c for c in candidates if (
                (note_to_midi(c) - note_to_midi(prev_note)) * leap_dir < 0
                and abs(note_to_midi(c) - note_to_midi(prev_note)) <= 2
            )]
            if filtered:
                candidates = filtered
            leap_dir = None

        # Bias overall motion toward the current direction when possible.
        directional = [
            c
            for c in candidates
            if (note_to_midi(c) - note_to_midi(prev_note)) * direction >= 0
        ]
        if directional:
            candidates = directional

        next_note = random.choice(candidates)
        melody.append(next_note)

        start_beat += pattern[i % len(pattern)] / beat_unit

        # Determine if this interval constitutes a leap so the next note can
        # compensate accordingly.
        interval = note_to_midi(next_note) - note_to_midi(prev_note)
        if abs(interval) >= 7:
            leap_dir = 1 if interval > 0 else -1

    return melody


def generate_harmony_line(melody: List[str], interval: int = 4) -> List[str]:
    """Return a simple harmony line at ``interval`` semitones from ``melody``.

    The resulting line mirrors the rhythm of ``melody`` while remaining
    within the valid MIDI range.
    """
    harmony = []
    for note in melody:
        # Shift each melody note by the specified interval while clamping the
        # value so it stays within the valid MIDI range (0-127).  When the shift
        # would exceed the range, move in the opposite direction to keep the
        # harmony line usable.
        base = note_to_midi(note)
        direction = -1 if base + interval > 120 else 1
        midi_val = max(0, min(127, base + direction * interval))
        harmony.append(midi_to_note(midi_val))
    return harmony


def generate_counterpoint_melody(melody: List[str], key: str) -> List[str]:
    """Generate a counterpoint line for ``melody`` in ``key``.

    The line favours contrary motion and consonant intervals such as thirds,
    sixths, fifths and octaves.
    """
    scale_notes = SCALE[key]
    counter: List[str] = []
    prev_note = None
    prev_base = None
    consonant = {3, 4, 7, 8, 9, 12}
    for base_note in melody:
        base_midi = note_to_midi(base_note)
        candidates: List[str] = []
        # Gather consonant pitches around the current melody note so any chosen
        # note forms a pleasant interval when played together with ``base_note``.
        for n in scale_notes:
            for octave in range(3, 7):
                cand = f"{n}{octave}"
                interval = abs(note_to_midi(cand) - base_midi)
                if interval in consonant:
                    candidates.append(cand)
        if not candidates:
            candidates.append(base_note)
        choice = random.choice(candidates)
        if prev_note and prev_base:
            base_int = note_to_midi(base_note) - note_to_midi(prev_base)
            cand_int = note_to_midi(choice) - note_to_midi(prev_note)
            # Prefer contrary motion by flipping direction if the voices are
            # moving the same way relative to their previous notes.
            if base_int * cand_int > 0:
                opposite = [c for c in candidates if (note_to_midi(c) - note_to_midi(prev_note)) * base_int < 0]
                if opposite:
                    choice = random.choice(opposite)
        counter.append(choice)
        prev_note = choice
        prev_base = base_note
    return counter

def create_midi_file(
    melody: List[str],
    bpm: int,
    time_signature: Tuple[int, int],
    output_file: str,
    harmony: bool = False,
    pattern: Optional[List[float]] = None,
    extra_tracks: Optional[List[List[str]]] = None,
) -> None:
    """
    Create a MIDI file for the given melody.

    The function converts the list of note strings into MIDI events using
    ``mido``.  A rhythmic ``pattern`` can be supplied to control note lengths
    and a basic harmony track can be toggled with ``harmony``.  Additional
    melodies may be provided in ``extra_tracks`` which are written to their own
    tracks in the output file.

    Args:
        melody (List[str]): List of note names.
        bpm (int): Beats per minute.
        time_signature (Tuple[int, int]): Time signature (numerator, denominator).
        output_file (str): Path for saving the MIDI file.
        harmony (bool, optional): Whether to include a parallel harmony line.
        pattern (List[float], optional): Rhythmic pattern as fractions of a whole note.
        extra_tracks (List[List[str]], optional): Additional melodies to write
            on separate tracks.
    """
    ticks_per_beat = 480
    mid = MidiFile(ticks_per_beat=ticks_per_beat)
    track = MidiTrack()
    mid.tracks.append(track)
    harmony_track = None
    if harmony:
        harmony_track = MidiTrack()
        mid.tracks.append(harmony_track)
    extra_midi_tracks: List[MidiTrack] = []
    if extra_tracks:
        # Pre-create MIDI tracks to mirror any additional melody lines
        for _ in extra_tracks:
            t = MidiTrack()
            mid.tracks.append(t)
            extra_midi_tracks.append(t)

    # Set tempo and time signature.
    track.append(mido.MetaMessage('set_tempo', tempo=mido.bpm2tempo(bpm)))
    track.append(mido.MetaMessage('time_signature', numerator=time_signature[0], denominator=time_signature[1]))

    # Select a rhythmic pattern and compute the duration of a whole note in ticks.
    if pattern is None:
        # Pick one of the predefined rhythms if the caller did not supply a
        # pattern. This keeps the timing interesting while still deterministic
        # for a given melody length.
        pattern = random.choice(PATTERNS)
    whole_note_ticks = ticks_per_beat * 4
    beat_fraction = 1 / time_signature[1]
    beat_ticks = int(beat_fraction * whole_note_ticks)
    beats_per_segment = time_signature[0] * 4
    beats_elapsed = 0
    rest_ticks = 0
    last_note = None
    last_velocity = 64

    # Generate MIDI events for each note using the rhythmic pattern cyclically.
    for i, note in enumerate(melody):
        # Determine how long this note should last based on the pattern
        duration_fraction = pattern[i % len(pattern)]
        velocity = int(50 + 40 * (i / max(len(melody) - 1, 1)))

        if duration_fraction == 0:
            # Treat ``0`` as a rest equal to one beat.
            rest_ticks += beat_ticks
            beats_elapsed += 1
            continue

        note_duration = int(duration_fraction * whole_note_ticks)
        midi_note = note_to_midi(note)

        note_on = Message('note_on', note=midi_note, velocity=velocity, time=rest_ticks)
        note_off = Message('note_off', note=midi_note, velocity=velocity, time=note_duration)
        track.append(note_on)
        track.append(note_off)
        if harmony_track is not None:
            harmony_note = min(midi_note + 4, 127)
            h_on = Message('note_on', note=harmony_note, velocity=max(velocity - 10, 40), time=rest_ticks)
            h_off = Message('note_off', note=harmony_note, velocity=max(velocity - 10, 40), time=note_duration)
            harmony_track.append(h_on)
            harmony_track.append(h_off)
        for line, t in zip(extra_tracks or [], extra_midi_tracks):
            if i >= len(line):
                continue
            m = note_to_midi(line[i])
            x_on = Message('note_on', note=m, velocity=velocity, time=rest_ticks)
            x_off = Message('note_off', note=m, velocity=velocity, time=note_duration)
            t.append(x_on)
            t.append(x_off)

        rest_ticks = 0
        beats_elapsed += duration_fraction / beat_fraction
        last_note = midi_note
        last_velocity = velocity

        if beats_elapsed >= beats_per_segment:
            if last_note is not None and random.random() < 0.5:
                extra_fraction = random.choice([0.5, 1.0])
                extra_ticks = int(extra_fraction * whole_note_ticks)
                on = Message('note_on', note=last_note, velocity=last_velocity, time=0)
                off = Message('note_off', note=last_note, velocity=last_velocity, time=extra_ticks)
                track.append(on)
                track.append(off)
                rest_ticks = beat_ticks
            beats_elapsed = 0

    # Write all tracks to disk
    mid.save(output_file)
    logging.info(f"MIDI file saved to {output_file}")

def run_cli() -> None:
    """Parse command line arguments and generate a melody.

    This is a thin wrapper around the core library functions that mirrors
    the options available in the GUI. It validates the provided arguments,
    invokes :func:`generate_melody` and finally writes the resulting MIDI
    file using :func:`create_midi_file`. Invalid parameters cause the
    process to exit with ``sys.exit`` so the calling shell can detect
    failures.
    """
    parser = argparse.ArgumentParser(
        description="Generate a random melody and save as a MIDI file."
    )
    parser.add_argument('--key', type=str, required=True, help="Musical key (e.g., C, Dm, etc.).")
    parser.add_argument('--chords', type=str, help="Comma-separated chord progression (e.g., C,Am,F,G).")
    parser.add_argument('--random-chords', type=int, metavar='N', help="Generate a random chord progression of N chords, ignoring --chords.")
    parser.add_argument('--bpm', type=int, required=True, help="Beats per minute (integer).")
    parser.add_argument('--timesig', type=str, required=True, help="Time signature in numerator/denominator format (e.g., 4/4).")
    parser.add_argument('--notes', type=int, required=True, help="Number of notes in the melody.")
    parser.add_argument('--output', type=str, required=True, help="Output MIDI file path.")
    parser.add_argument('--motif_length', type=int, default=4, help="Length of the initial motif (default: 4).")
    parser.add_argument('--harmony', action='store_true', help="Add a simple harmony track.")
    parser.add_argument('--random-rhythm', action='store_true', help="Generate a random rhythmic pattern.")
    parser.add_argument('--counterpoint', action='store_true', help="Generate a counterpoint line.")
    parser.add_argument('--harmony-lines', type=int, default=0, metavar='N',
                        help="Number of harmony lines to add in parallel")
    parser.add_argument('--base-octave', type=int, default=4,
                        help="Starting octave for the melody (default: 4).")
    # Parse the provided CLI arguments
    args = parser.parse_args()

    # Basic numeric sanity checks
    if args.bpm <= 0:
        logging.error("BPM must be a positive integer.")
        sys.exit(1)
    if args.notes <= 0:
        logging.error("Number of notes must be a positive integer.")
        sys.exit(1)
    if args.motif_length <= 0:
        logging.error("Motif length must be a positive integer.")
        sys.exit(1)
    if args.motif_length > args.notes:
        logging.error("Motif length cannot exceed the number of notes.")
        sys.exit(1)

    # Validate key and chord progression.
    if args.key not in SCALE:
        logging.error("Invalid key provided.")
        sys.exit(1)

    if args.random_chords:
        # Let the helper pick a progression based solely on the key
        chord_progression = generate_random_chord_progression(args.key, args.random_chords)
    else:
        if not args.chords:
            logging.error("Chord progression required unless --random-chords is used.")
            sys.exit(1)
        chord_progression = [chord.strip() for chord in args.chords.split(',')]
        # Validate that every chord exists in the chord dictionary
        for chord in chord_progression:
            if chord not in CHORDS:
                logging.error(f"Invalid chord in progression: {chord}")
                sys.exit(1)

    try:
        # Parse "numerator/denominator" into two integers
        parts = args.timesig.split('/')
        if len(parts) != 2:
            raise ValueError
        numerator, denominator = map(int, parts)
        if numerator <= 0 or denominator <= 0:
            raise ValueError
    except ValueError:
        logging.error(
            "Time signature must be two integers in the form 'numerator/denominator' with numerator > 0 and denominator > 0."
        )
        sys.exit(1)

    melody = generate_melody(
        args.key,
        args.notes,
        chord_progression,
        motif_length=args.motif_length,
        base_octave=args.base_octave,
    )
    rhythm = generate_random_rhythm_pattern() if args.random_rhythm else None
    # Collect additional harmony tracks requested on the command line
    extra: List[List[str]] = []
    for _ in range(max(0, args.harmony_lines)):
        # Generate any requested parallel harmony lines
        extra.append(generate_harmony_line(melody))
    if args.counterpoint:
        extra.append(generate_counterpoint_melody(melody, args.key))
    create_midi_file(
        melody,
        args.bpm,
        (numerator, denominator),
        args.output,
        harmony=args.harmony,
        pattern=rhythm,
        extra_tracks=extra,
    )
    logging.info("Melody generation complete.")


def main() -> None:
    """
    Main entry point. Runs the CLI if arguments are provided; otherwise, launches the GUI.
    """
    # Configure logging only when executing the application directly
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    # Decide between CLI and GUI based on whether arguments were supplied
    if len(sys.argv) > 1:
        run_cli()
    else:
        try:
            # Import the GUI lazily so tests without Tkinter can still run
            MelodyGeneratorGUI = import_module(
                "melody_generator.gui"
            ).MelodyGeneratorGUI
        except ImportError:
            logging.error(
                "Tkinter is required for the GUI. Run with CLI arguments or install Tkinter."
            )
            logging.error(
                "Tkinter is not available. Please run with CLI options or install it."
            )
            sys.exit(1)

        gui = MelodyGeneratorGUI(
            generate_melody,
            create_midi_file,
            SCALE,
            CHORDS,
            load_settings,
            save_settings,
            generate_random_chord_progression,
            generate_random_rhythm_pattern,
            generate_harmony_line,
            generate_counterpoint_melody,
        )
        # Start the Tk event loop
        gui.run()

if __name__ == '__main__':
    main()

