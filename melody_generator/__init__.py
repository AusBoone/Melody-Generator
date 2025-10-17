#!/usr/bin/env python3
"""Melody Generator library.

This package exposes utility functions and GUI helpers for creating
short melodies.  A typical workflow is to call :func:`generate_melody`
with a key, number of notes and chord progression, then feed the result
into :func:`create_midi_file` to produce a MIDI track.  Both a Tkinter
desktop interface and Flask web interface wrap these calls so end users
can experiment without writing code.

Underlying Algorithm
--------------------
The core algorithm repeats a small *motif* throughout the phrase. Each
subsequent note is chosen from the current chord and biased toward small
intervals from the previous pitch. Large leaps are tracked so the next
note compensates by moving in the opposite direction. When no suitable
candidate exists, a random pitch from the key acts as a safe fallback.
Rhythm patterns are selected from a small library or generated via a
dedicated :class:`RhythmGenerator` so onsets can evolve separately from
pitch choices.  This keeps results lively without requiring deep musical
knowledge.

Algorithm Pseudocode
--------------------
The following outlines the main loop executed by :func:`generate_melody`::

    motif = generate_motif(motif_length, key)
    pattern = pattern or random_choice(PATTERNS)
    for i in range(num_notes):
        chord = chord_progression[i % len(chord_progression)]
        candidate_notes = filter_scale(key, chord)
        next_note = choose_note(candidate_notes, prev_note, leap_correction)
        melody.append(next_note)
        update_leap_tracking()
        advance_rhythm(pattern)

This approach favours repetition with subtle variation so each phrase
feels related to the previous one while still moving forward.

Features include:
- Integrated rhythmic patterns for note durations.
- Enhanced melody generation with controlled randomness.
- Robust fallback mechanisms for note selection.
- Optional phrase-level planning to sketch a pitch range and tension curve
  before notes are generated.
- Lightweight LSTM integration for probabilistic weighting when PyTorch is
  installed.
- VAE-based style embeddings with thread-local ``set_style`` for genre
  interpolation.
- Multi-voice generation via ``PolyphonicGenerator`` for four-part counterpoint.
- Both GUI (Tkinter) and CLI interfaces.
- Detailed logging and improved documentation.

Author: Austin Boone
Modified: February 15, 2025
"""

__version__ = "0.1.0"

# ---------------------------------------------------------------
# Modification Summary
# ---------------------------------------------------------------
# * Added ``_open_default_player`` thread-based implementation that waits
#   for the system MIDI player before optionally deleting the file.
#   This prevents race conditions when previewing MIDI files on platforms
#   like macOS where the previous asynchronous approach removed the file
#   too early.
# * ``create_midi_file`` now merges chord and melody events using absolute
#   ticks when ``chords_separate`` is ``False`` so chords begin at measure
#   boundaries instead of after the melody.
# * ``generate_melody`` and ``create_midi_file`` validate that supplied rhythm
#   ``pattern`` lists are non-empty and raise ``ValueError`` when violated.
# * ``generate_random_chord_progression`` and ``diatonic_chords`` now check
#   for unknown ``key`` values and raise ``ValueError`` with a clear message.
# * ``generate_random_chord_progression`` rejects non-positive ``length`` values
#   and both it and ``diatonic_chords`` preserve the "dim" suffix when building
#   chord names so diminished triads remain explicit.
# * ``generate_melody`` rejects ``base_octave`` values outside the safe MIDI
#   range (``MIN_OCTAVE``-``MAX_OCTAVE``) so melodies cannot reference invalid
#   pitches.
# * ``_open_default_player`` uses ``xdg-open --wait`` on Linux so preview files
#   remain until the external player closes.
# * Documentation consolidated under ``docs/README.md`` which links to the
#   algorithm description, setup guide, FluidSynth notes and soundfont
#   resources for easy navigation.
# * `generate_motif` and `generate_melody` now validate unknown keys and raise `ValueError` when violated.
# * `generate_melody` and `create_midi_file` reject negative durations in `pattern`.
# * Applied `functools.lru_cache` to `canonical_key` and `canonical_chord` to
#   avoid repeated dictionary lookups when these helpers are used frequently in
#   batch melody generation.
# * Added `lru_cache` memoization for `scale_for_chord` and `note_to_midi`.
#   Candidate note pools are generated lazily and cached to eliminate repeated
#   computations.
# * Melody generation now weights candidate notes to favour chord tones and
#   smooth motion, filters tritone leaps and selects scales based on the active
#   chord.
# * Melody generation caches candidate note pools for each chord to avoid
#   repeated list construction and adds an optional ``structure`` parameter for
#   repeating sections.
# * Section-based generation now forwards advanced options (style, ML models,
#   phrase planning, tritone filtering and refinement) to each sub-call and
#   slices the supplied :class:`PhrasePlan` so every section respects the same
#   pitch range and tension curve.
# * Sectional generation clamps the motif length per segment and rejects
#   zero-length sections so ``structure`` patterns that divide the phrase more
#   finely than the motif no longer raise ``ValueError`` deep inside recursive
#   calls.
# * MIDI output uses a crescendo-decrescendo velocity curve with downbeat
#   accents for a more musical performance.
# * Candidate weighting now uses a simple transition matrix and the final note
#   resolves to the root of the last chord for a basic cadence.  An optional
#   plagal cadence flag now reharmonises the final bar with a IV–I gesture and
#   reshapes the soprano line to descend ^4–^3–^1 for a gospel-inspired close.
# * Sectional phrases that reuse earlier material (e.g. ``AABA``) now reapply the
#   plagal cadence adjustments after concatenation so the final repeat still
#   resolves with the intended IV–I motion even when no new notes are generated.
# * Added ``PhrasePlanner`` for hierarchical skeleton/infill planning so phrases
#   exhibit clearer A/B structure.
# * Introduced ``SequenceModel`` interface; LSTM logits now bias candidate
#   weights when provided.
# * Added style embedding VAE with thread-local ``set_style`` for genre
#   transfer.
# * Counterpoint penalty discourages parallel fifths/octaves and rewards
#   contrary motion during note selection.
# * Introduced ``RhythmGenerator`` so onset patterns are produced
#   independently of pitch selection.
# * Added ``PolyphonicGenerator`` for multi-voice counterpoint generation
#   with automatic cross-voice adjustments.
# * Added ``feedback`` module implementing Frechet Music Distance scoring
#   and a hill-climbing refinement loop for generated phrases.
# * Added data augmentation helpers and ``fine_tune_model`` for transfer
#   learning on genre-specific MIDI subsets.
# * ``compute_base_weights`` is JIT-compiled with Numba when available and a
#   simple ``profile`` context manager exposes cProfile statistics for hot
#   functions like ``pick_note``.
# * Candidate filtering and sampling now use NumPy broadcasting and
#   ``numpy.random.choice`` when available for faster vector operations.
# * Candidate note pools are created lazily on first use rather than
#   preloading every combination at import time.
# * ``create_midi_file`` accepts a ``humanize`` flag so unit tests can
#   disable timing jitter for deterministic output.
# * ``generate_melody`` and ``create_midi_file`` now canonicalise keys and
#   chords so lowercase input is accepted by the public API.
# * ``generate_random_chord_progression``, ``diatonic_chords`` and harmony
#   helpers normalise keys with :func:`canonical_key` so callers may supply
#   lowercase or mixed-case values.
# * ``generate_random_chord_progression`` samples all seven scale degrees when
#   padding progressions so the leading tone chord can be chosen.
# ---------------------------------------------------------------

import random
import logging
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Sequence
from mido import Message, MidiFile, MidiTrack  # noqa: F401
from functools import lru_cache
import os
import mido  # noqa: F401
try:
    import numpy as np
except Exception:  # pragma: no cover - optional dependency
    np = None

from .phrase_planner import PhrasePlan, PhrasePlanner, generate_phrase_plan  # noqa: F401
from .sequence_model import (
    SequenceModel,
    MelodyLSTM,  # noqa: F401
    predict_next,  # noqa: F401
    load_sequence_model,  # noqa: F401
    load_genre_sequence_model,  # noqa: F401
)  # noqa: F401
# Re-export the full module so ``melody_generator.style_embeddings`` exists for
# callers that rely on the submodule attribute.  Tests importing the web GUI
# expect this reference to be present when reloading the package.
from . import style_embeddings  # noqa: F401
from .style_embeddings import get_style_vector, set_style, get_active_style  # noqa: F401
from .tension import tension_for_notes, apply_tension_weights
from .dynamics import humanize_events  # noqa: F401
from .rhythm_engine import RhythmGenerator, generate_rhythm
from .feedback import compute_fmd, refine_with_fmd  # noqa: F401
from .augmentation import (
    transpose_sequence,  # noqa: F401
    invert_sequence,  # noqa: F401
    perturb_rhythm,  # noqa: F401
    augment_sequences,  # noqa: F401
    fine_tune_model,  # noqa: F401
)
from .performance import compute_base_weights, profile  # noqa: F401

# Default path for storing user preferences
# The file lives in the user's home directory so settings persist
# between runs of the application.
env_path = os.environ.get("MELODY_SETTINGS_FILE")
if env_path:
    DEFAULT_SETTINGS_FILE = Path(env_path).expanduser()
else:
    DEFAULT_SETTINGS_FILE = Path.home() / ".melody_generator_settings.json"

# ``MIN_OCTAVE`` and ``MAX_OCTAVE`` constrain the allowable octave range for
# generated melodies. MIDI notes span from 0 to 127 which corresponds roughly
# to C-1 through G9. Restricting the base octave to this subset keeps the
# generated pitches well within the MIDI specification.
MIN_OCTAVE = 0
MAX_OCTAVE = 8

from .polyphony import PolyphonicGenerator  # noqa: E402,F401
from .harmony_generator import HarmonyGenerator  # noqa: E402,F401


def load_settings(path: Path = DEFAULT_SETTINGS_FILE) -> dict:
    """Load saved user settings from ``path`` if it exists.

    @param path (Path): Location of the settings file.
    @returns dict: Loaded settings or an empty dictionary when unavailable.
    """
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
    """Save user ``settings`` to ``path`` as JSON.

    @param settings (dict): Options to be persisted.
    @param path (Path): Destination file path.
    @returns None: Function does not return a value.
    """
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
    "C": 0,
    "B#": 0,
    "C#": 1,
    "Db": 1,
    "D": 2,
    "D#": 3,
    "Eb": 3,
    "E": 4,
    "Fb": 4,
    "E#": 5,
    "F": 5,
    "F#": 6,
    "Gb": 6,
    "G": 7,
    "G#": 8,
    "Ab": 8,
    "A": 9,
    "A#": 10,
    "Bb": 10,
    "B": 11,
    "Cb": 11,
}

# Keep a basic list of note names (using sharps) for any other logic that
# relies on it.
NOTES: List[str] = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


# ``_SCALE_INDICES`` maps each key to a dictionary of note names to their index
# within the corresponding scale. These tables let the generator translate note
# names to scale degrees in constant time.
_SCALE_INDICES: dict[str, dict[str, int]] = {}

# ``_CANDIDATE_CACHE`` stores precomputed candidate note lists keyed by
# ``(key, chord, strong, root_octave)``. This avoids rebuilding the same
# source pools each iteration inside ``generate_melody``.
_CANDIDATE_CACHE: dict[tuple[str, str, bool, int], List[str]] = {}

# ``_TRANSITION_WEIGHTS`` encodes the relative likelihood of moving by a
# given interval in semitones. Values were chosen heuristically so that
# repeated notes and small steps are favoured over large leaps. The
# dictionary acts as a rudimentary Markov transition matrix guiding
# candidate weighting during melody generation.
_TRANSITION_WEIGHTS: dict[int, float] = {
    0: 1.2,  # repeated pitch
    1: 1.0,
    2: 0.8,
    3: 0.6,
    4: 0.4,
    5: 0.3,
    6: 0.1,  # tritone (rarely used)
}

# ``_SIMILARITY_WEIGHTS`` biases interval choices toward sizes close to the
# previous step. When the last interval was, for example, two semitones, moving
# another two semitones is slightly preferred over a much larger jump.
_SIMILARITY_WEIGHTS: dict[int, float] = {
    0: 1.0,
    1: 0.8,
    2: 0.6,
    3: 0.4,
}


# Map key names to the notes that make up their diatonic scale. Functions that
# generate melodies or harmonies reference this to stay in the chosen key.
SCALE = {
    "C": ["C", "D", "E", "F", "G", "A", "B"],
    "C#": ["C#", "D#", "E#", "F#", "G#", "A#", "B#"],
    "D": ["D", "E", "F#", "G", "A", "B", "C#"],
    "Eb": ["Eb", "F", "G", "Ab", "Bb", "C", "D"],
    "E": ["E", "F#", "G#", "A", "B", "C#", "D#"],
    "F": ["F", "G", "A", "Bb", "C", "D", "E"],
    "F#": ["F#", "G#", "A#", "B", "C#", "D#", "E#"],
    "G": ["G", "A", "B", "C", "D", "E", "F#"],
    "Ab": ["Ab", "Bb", "C", "Db", "Eb", "F", "G"],
    "A": ["A", "B", "C#", "D", "E", "F#", "G#"],
    "Bb": ["Bb", "C", "D", "Eb", "F", "G", "A"],
    "B": ["B", "C#", "D#", "E", "F#", "G#", "A#"],
    # Minor keys
    "Cm": ["C", "D", "Eb", "F", "G", "Ab", "Bb"],
    "C#m": ["C#", "D#", "E", "F#", "G#", "A", "B"],
    "Dm": ["D", "E", "F", "G", "A", "Bb", "C"],
    "Ebm": ["Eb", "F", "Gb", "Ab", "Bb", "Cb", "Db"],
    "Em": ["E", "F#", "G", "A", "B", "C", "D"],
    "Fm": ["F", "G", "Ab", "Bb", "C", "Db", "Eb"],
    "F#m": ["F#", "G#", "A", "B", "C#", "D", "E"],
    "Gm": ["G", "A", "Bb", "C", "D", "Eb", "F"],
    "G#m": ["G#", "A#", "B", "C#", "D#", "E", "F#"],
    "Am": ["A", "B", "C", "D", "E", "F", "G"],
    "Bbm": ["Bb", "C", "Db", "Eb", "F", "Gb", "Ab"],
    "Bm": ["B", "C#", "D", "E", "F#", "G", "A"],
}

# Programmatically extend ``SCALE`` with several common modes and pentatonic
# scales.  This keeps the list of keys manageable while providing additional
# variety when generating melodies.


def _build_scale(root: str, pattern: List[int]) -> List[str]:
    """Return a scale starting at ``root`` following ``pattern`` intervals.

    ``pattern`` is a sequence of semitone offsets from the root note that
    defines the mode.  The function walks the pattern wrapping around the
    twelve-tone chromatic scale to create the resulting list of note names.

    @param root (str): Root note of the scale.
    @param pattern (List[int]): Sequence of semitone offsets defining the mode.
    @returns List[str]: Computed scale as note names.
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

# Build quick-lookup dictionaries for each scale so note positions can be
# retrieved in constant time during melody generation. This avoids repeated
# ``list.index`` calls which become costly as the number of notes grows.
for name, notes in SCALE.items():
    _SCALE_INDICES[name] = {n: i for i, n in enumerate(notes)}

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
    "Dbm": ["Db", "E", "Ab"],
    # Diminished triads allow the harmony generator to output fully
    # qualified names such as ``Bdim``.
    "Cdim": ["C", "Eb", "Gb"],
    "C#dim": ["C#", "E", "G"],
    "Ddim": ["D", "F", "Ab"],
    "Ebdim": ["Eb", "Gb", "A"],
    "Edim": ["E", "G", "Bb"],
    "Fdim": ["F", "Ab", "B"],
    "F#dim": ["F#", "A", "C"],
    "Gdim": ["G", "Bb", "Db"],
    "G#dim": ["G#", "B", "D"],
    "Abdim": ["Ab", "Cb", "E"],
    "Adim": ["A", "C", "Eb"],
    "A#dim": ["A#", "C#", "E"],
    "Bbdim": ["Bb", "Db", "E"],
    "Bdim": ["B", "D", "F"],
    "Dbdim": ["Db", "E", "G"],
}

# Lookup tables mapping lowercase names to their canonical forms. These
# mappings allow command line and GUI interfaces to accept musical keys
# and chords regardless of the user's capitalization preferences.
CANONICAL_KEYS = {name.lower(): name for name in SCALE}
CANONICAL_CHORDS = {name.lower(): name for name in CHORDS}

# Enharmonic fallbacks used when a theoretically correct spelling is missing
# from :data:`CHORDS`.  Helpers that synthesise diatonic chords consult this
# mapping so progressions never devolve into random substitutions simply because
# a rarely used spelling (e.g. ``A#``) is absent from the static lookup table.
_ENHARMONIC_EQUIVALENTS: dict[str, str] = {
    "A#": "Bb",
    "A#m": "Bbm",
    "Db": "C#",
    "Dbm": "C#m",
    "Ab": "G#",
    "Abm": "G#m",
}


@lru_cache(maxsize=None)
def canonical_key(name: str) -> str:
    """Return the canonical capitalization for ``name``.

    Parameters
    ----------
    name:
        Musical key provided by the user. Case-insensitive.

    Returns
    -------
    str
        Key from :data:`SCALE` matching ``name``.

    Raises
    ------
    ValueError
        If ``name`` is not present in :data:`SCALE`.
    """

    key = CANONICAL_KEYS.get(name.strip().lower())
    if key is None:
        raise ValueError(f"Unknown key: {name}")
    return key


@lru_cache(maxsize=None)
def canonical_chord(name: str) -> str:
    """Return the canonical chord name for ``name``.

    Parameters
    ----------
    name:
        Chord name provided by the user. Case-insensitive.

    Returns
    -------
    str
        Matching chord name from :data:`CHORDS`.

    Raises
    ------
    ValueError
        If ``name`` does not correspond to a known chord.
    """

    chord = CANONICAL_CHORDS.get(name.strip().lower())
    if chord is None:
        raise ValueError(f"Unknown chord: {name}")
    return chord


# ``PATTERNS`` stores common rhythmic figures. Each inner list represents a
# sequence of note durations (in fractions of a whole note) that repeat while
# creating the MIDI file.
PATTERNS: List[List[float]] = [
    # Basic march-like rhythm
    [0.25, 0.25, 0.5],  # quarter, quarter, half
    # Simple syncopation with a dotted half
    [0.25, 0.75],  # quarter, dotted half
    # Even half notes
    [0.5, 0.5],  # half, half
    # Dotted quarter pattern often found in waltzes
    [0.375, 0.375, 0.25],  # dotted quarter, dotted quarter, quarter
    # Eighth-note lead in to a half note
    [0.125, 0.125, 0.25, 0.5],  # two eighths, quarter, half
    # Continuous run of sixteenth notes
    [0.0625] * 8,  # a run of sixteenth notes
]


def generate_random_chord_progression(key: str, length: int = 4) -> List[str]:
    """Return a simple chord progression for ``key``.

    The progression is chosen from a small set of common patterns in
    popular music.  Chords are derived from the selected key so the
    results fit naturally with generated melodies.

    The ``key`` argument is case-insensitive; it is normalised via
    :func:`canonical_key` so callers can provide lowercase or mixed-case
    values.

    @param key (str): Musical key to base the chords on. ``ValueError`` is
        raised when the key is not defined in :data:`SCALE`.
    @param length (int): Number of chords to generate. Must be positive or a
        ``ValueError`` is raised.
    @returns List[str]: Chord names forming the progression.
    """

    # Normalize and validate the supplied key so lookups into ``SCALE``
    # are always performed with canonical capitalization (e.g. ``"c"``
    # becomes ``"C"``).
    key = canonical_key(key)

    # Roman numeral progressions for major and minor keys encoded as
    # scale degrees (0 = I/i). These simple loops mimic typical pop
    # progressions and keep the harmony sounding familiar.
    major_patterns = [[0, 3, 4, 0], [0, 5, 3, 4], [0, 3, 0, 4]]
    minor_patterns = [[0, 3, 4, 0], [0, 5, 3, 4], [0, 5, 4, 0]]

    if length <= 0:
        # Guard against nonsensical requests so callers always receive at least
        # one chord. Returning an empty list would make downstream algorithms
        # such as melody generation ambiguous.
        raise ValueError("length must be positive")

    is_minor = key.endswith("m")
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
            qualities = ["m", "dim", "", "m", "m", "", ""]
        else:
            qualities = ["", "m", "m", "", "", "m", "dim"]
        # Look up the chord quality for this scale degree (major, minor or
        # diminished). Concatenate the quality directly so diminished chords keep
        # their "dim" suffix instead of being truncated to a plain triad.
        quality = qualities[idx % len(qualities)]
        chord = note + quality
        if chord not in CHORDS:
            # Translate enharmonic spellings to match available chord names.
            # Using the shared mapping keeps behaviour consistent across
            # helpers that synthesise chords from scale degrees.
            chord = _ENHARMONIC_EQUIVALENTS.get(chord, chord)
        return chord if chord in CHORDS else random.choice(list(CHORDS.keys()))

    # Convert degree numbers to concrete chord names
    # (e.g. 0 -> C, 4 -> G when key is C)
    progression = [degree_to_chord(d) for d in degrees]
    if length > len(progression):
        # Pad the progression with random chords if the requested length is longer
        # ``random.randint`` previously sampled only from degrees 0-5 which excluded
        # the leading tone chord. Sampling ``0`` through ``len(notes) - 1`` ensures
        # all scale degrees (including the seventh) are candidates for padding.
        extra = [
            degree_to_chord(random.randint(0, len(notes) - 1))
            for _ in range(length - len(progression))
        ]
        # Extend with random chords so the returned list matches ``length``
        progression.extend(extra)
    return progression[:length]


def diatonic_chords(key: str) -> List[str]:
    """Return the diatonic triads for ``key``.

    The chords mirror the quality of each scale degree. Diminished
    chords explicitly retain the ``"dim"`` suffix so callers can
    distinguish them from their major counterparts. Unknown chords fall
    back to their enharmonic equivalents when possible.

    The ``key`` argument is case-insensitive and is normalised with
    :func:`canonical_key`.

    @param key (str): Musical key whose triads are requested. ``ValueError`` is
        raised when the key is not defined in :data:`SCALE`.
    @returns List[str]: All unique chords found in the key.
    """

    # Canonicalise the key so callers can use any casing.
    key = canonical_key(key)

    is_minor = key.endswith("m")
    notes = SCALE[key]
    qualities = (
        ["m", "dim", "", "m", "m", "", ""]
        if is_minor
        else ["", "m", "m", "", "", "m", "dim"]
    )
    chords = []
    for note, qual in zip(notes, qualities):
        # Concatenate the quality directly so diminished chords retain the
        # "dim" suffix instead of collapsing to a bare major triad.
        chord = note + qual
        if chord not in CHORDS:
            chord = _ENHARMONIC_EQUIVALENTS.get(chord, chord)
        if chord in CHORDS and chord not in chords:
            chords.append(chord)
    return chords


@lru_cache(maxsize=None)
def scale_for_chord(key: str, chord: str) -> List[str]:
    """Return the preferred scale for ``chord`` within ``key``.

    The function is pure so ``lru_cache`` memoises results. Dominant chords
    use a mixolydian flavour while minor triads fall back to the natural minor
    scale of the root.
    """

    chord = canonical_chord(chord)
    root = chord.rstrip("m")
    if not chord.endswith("m") and root in SCALE and chord in CHORDS:
        # Use mixolydian when the chord acts as the dominant of the key.
        if root != canonical_key(key).rstrip("m") and f"{root}_mixolydian" in SCALE:
            scale = SCALE[f"{root}_mixolydian"]
        else:
            scale = SCALE.get(root, SCALE[key])
    elif chord.endswith("m") and f"{root}m" in SCALE:
        scale = SCALE[f"{root}m"]
    else:
        scale = SCALE[key]

    return scale


def _candidate_pool(key: str, chord: str, root_octave: int, *, strong: bool) -> List[str]:
    """Return candidate notes for ``chord`` within ``key``.

    Each pool is generated lazily and stored in ``_CANDIDATE_CACHE`` keyed by
    ``(key, chord, strong, root_octave)``.  This memoization means the list of
    possible notes for a given harmonic context only needs to be built once.

    ``root_octave`` defines the lowest octave allowed for the pool.  Notes are
    produced for ``root_octave`` and ``root_octave + 1`` which keeps the search
    within two octaves.  Callers must pass values that fall within
    ``MIN_OCTAVE`` and ``MAX_OCTAVE`` so all generated MIDI notes remain valid.

    The ``strong`` flag controls whether only chord tones are included or the
    full scale derived from ``chord``.  Reusing the cached list avoids repeated
    allocations during melody generation.
    """

    cache_key = (key, chord, strong, root_octave)
    # ``_CANDIDATE_CACHE`` is keyed by ``cache_key`` so the expensive note list
    # is computed only once for each harmonic context.
    if cache_key not in _CANDIDATE_CACHE:
        notes = get_chord_notes(chord) if strong else scale_for_chord(key, chord)
        # Build notes across two adjacent octaves so the melodic search space
        # stays small while still allowing modest leaps.
        _CANDIDATE_CACHE[cache_key] = [
            f"{n}{oct}"
            for n in notes
            for oct in range(root_octave, root_octave + 2)
        ]
    return _CANDIDATE_CACHE[cache_key]



def generate_random_rhythm_pattern(length: int = 3) -> List[float]:
    """Create a random rhythmic pattern based on a repeating motif.

    A motif is chosen from a predefined set of short patterns. The motif is
    then repeated until ``length`` durations have been produced.  All note
    lengths come from the same allowed set as before so the return value is
    compatible with older callers.  To keep things from sounding too rigid, a
    small variation may be applied after the first full repetition by replacing
    one value with an eighth note (``0.125``).

    ``ValueError`` is raised when ``length`` is ``0`` or negative so callers
    cannot request an empty pattern.

    @param length (int): Number of durations to produce. Must be positive.
    @returns List[float]: Pattern of note lengths in fractions of a whole note.
    """

    if length <= 0:
        # Guard against nonsensical or empty requests. The rhythm engine relies
        # on a positive number of durations to schedule MIDI events.
        raise ValueError("length must be positive")

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




def get_chord_notes(chord: str) -> List[str]:
    """Retrieve the notes that make up the given chord.

    @param chord (str): Chord name (e.g., ``C`` or ``F#m``).
    @returns List[str]: Note names in the chord.
    """
    # ``CHORDS`` acts as a lookup table for all supported triads. Accessing the
    # dictionary directly would raise ``KeyError`` for an unknown chord which
    # surfaces as an unhandled exception in calling code.  Validate the input so
    # that consumers receive a clear ``ValueError`` describing the issue.
    if chord not in CHORDS:
        raise ValueError(f"Unknown chord: {chord}")
    return CHORDS[chord]


def pick_note(candidates: List[str], weights: Sequence[float]) -> str:
    """Return a weighted random choice from ``candidates``.

    The function is intentionally small so it can be profiled
    separately from the rest of the generation loop. It validates that
    the two lists are non-empty and of equal length so that unexpected
    inputs raise an error early.

    Parameters
    ----------
    candidates:
        Note names to choose from.
    weights:
        Relative probabilities associated with ``candidates``.

    Returns
    -------
    str
        The selected note.
    """

    if not candidates or not weights:
        raise ValueError("candidates and weights must be non-empty")
    if len(candidates) != len(weights):
        raise ValueError("candidates and weights must have the same length")

    if np is not None:
        arr = np.asarray(weights, dtype=float)
        if arr.sum() == 0:
            arr = np.ones_like(arr)
        prob = arr / arr.sum()
        return str(np.random.choice(candidates, p=prob))
    return random.choices(list(candidates), weights=list(weights), k=1)[0]





def generate_motif(length: int, key: str, base_octave: int = 4) -> List[str]:
    """Generate a motif (short, recurring musical idea) in the specified key.

    @param length (int): Number of notes in the motif. Must be positive or a
        ``ValueError`` is raised.
    @param key (str): Musical key for the motif. A ``ValueError`` is raised if
        ``key`` is not present in :data:`SCALE` so callers receive a clear error
        instead of ``KeyError``.
    @param base_octave (int): Starting octave, usually ``4``. The value must be
        within ``MIN_OCTAVE`` and ``MAX_OCTAVE`` otherwise a ``ValueError`` is
        raised so generated notes always map to valid MIDI numbers.
    @returns List[str]: List of note names forming the motif.
    """
    if key not in SCALE:
        raise ValueError(f"Unknown key '{key}'")
    if length <= 0:
        raise ValueError("length must be positive")
    if not MIN_OCTAVE <= base_octave <= MAX_OCTAVE:
        raise ValueError(f"base_octave must be between {MIN_OCTAVE} and {MAX_OCTAVE}")
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
    structure: Optional[str] = None,
    allow_tritone: bool = False,
    phrase_plan: Optional[PhrasePlan] = None,
    sequence_model: Optional[SequenceModel] = None,
    rhythm_generator: Optional[RhythmGenerator] = None,
    style: Optional[str] = None,
    refine: bool = False,
    plagal_cadence: bool = False,
) -> List[str]:
    """Return a melody in ``key`` spanning ``num_notes`` notes.

    The algorithm works in several stages:

    1.  Build a short motif using :func:`generate_motif`.
    2.  Repeat that motif throughout the phrase, shifting it slightly so it does
        not sound overly mechanical. Onset times are supplied by a separate
        rhythm engine so the pitch contour and rhythm evolve independently.
    3.  When an octave shift occurs, the first note after the change is forced
        into the new register so the transition is audible.
    4.  For each new note, examine the current chord and pick pitches that are
        close to the previous note.
    5.  If no suitable candidate exists, choose a random note from the key.
    6.  Large leaps are tracked so the following note can correct the motion.
    7.  Strong beats are restricted to chord tones while weak beats may use any
        scale note.
    8.  Candidate notes are weighted using a small transition matrix so common
        intervals appear more frequently.
    9.  The final note is forced to the root of the last chord to create a
        simple cadence.

    @param key (str): Musical key for the melody. The value is canonicalised
        using :func:`canonical_key` so lowercase names are accepted. A
        ``ValueError`` is raised when the key does not exist in
        :data:`SCALE`.
    @param num_notes (int): Total number of notes to generate. Must be a
        positive integer otherwise ``ValueError`` is raised.
    @param chord_progression (List[str]): Chords guiding note choice. Each name
        is canonicalised via :func:`canonical_chord` to allow any casing.
    @param motif_length (int): Length of the initial motif.
    @param time_signature (Tuple[int, int]): Meter as ``(numerator, denominator)``.
        The denominator must be one of ``1, 2, 4, 8`` or ``16`` so note
        durations divide evenly into a whole note.
    @param pattern (List[float]|None): Optional rhythmic pattern. When provided,
        it must contain at least one duration value and all values must be
        non-negative. Violations raise ``ValueError`` so invalid patterns are
        caught immediately.
    @param base_octave (int): Preferred starting octave. Must fall within
        ``MIN_OCTAVE`` and ``MAX_OCTAVE`` so all generated MIDI notes remain
        valid.
    @param structure (str|None): Optional section pattern such as ``"AABA"``.
        Each unique letter generates a fresh phrase while repeated letters reuse
        and lightly mutate the earlier phrase. Only letters ``A-Z`` are allowed.
        When sections are shorter than ``motif_length`` the motif length is
        clamped to the section length automatically so recursion never fails.
        ``ValueError`` is raised if the structure would create empty sections
        (for example more section letters than requested notes).
    @param allow_tritone (bool): When ``False`` (default) melodic intervals of
        six semitones are filtered out to avoid the dissonant tritone unless no
        other options exist.
    @param phrase_plan (PhrasePlan|None): Optional high-level phrase outline.
        When supplied the ``pitch_range`` guides octave choices and the
        ``tension_profile`` is available for future weighting strategies.
    @param sequence_model (SequenceModel|None): Predictive model returning logits
        for the next scale degree. When provided its scores bias candidate
        weights; if ``None`` the heuristic transition matrix is used alone.
    @param rhythm_generator (RhythmGenerator|None): Object used to create the
        rhythmic pattern when ``pattern`` is ``None``.  Allows rhythms to be
        generated independently from pitch.  If omitted the default
        :func:`generate_rhythm` helper is used.
    @param style (str|None): Name of a style defined in
        :mod:`style_embeddings` used to nudge note selection. When ``None``,
        the thread-local vector previously stored via :func:`set_style` is used
        if present.
    @param refine (bool): When ``True`` apply a Frechet Music Distance based
        hill-climb to tweak up to five percent of notes and clamp the melody
        to the planned pitch range.
    @param plagal_cadence (bool): When ``True`` reharmonise the final two
        positions as IV→I and force the top line to resolve ^4–^3–^1. This
        mirrors the GUI's "plagal cadence" toggle and produces an
        ecclesiastical-sounding close regardless of the original chord list.
    @returns List[str]: Generated melody as note strings.
    """
    # The chord progression provides harmonic context for each note. Reject an
    # empty list so later indexing operations never fail when aligning notes to
    # chords.
    if not chord_progression:
        raise ValueError("chord_progression must contain at least one chord")

    # Normalise ``key`` and each chord so callers may pass any capitalization.
    # ``canonical_key`` and ``canonical_chord`` raise ``ValueError`` for unknown
    # values which keeps the later lookup operations safe.
    key = canonical_key(key)
    chord_progression = [canonical_chord(ch) for ch in chord_progression]

    # ``num_notes`` must be positive so the generator can actually produce a
    # melody. An explicit check keeps the error message clear for callers.
    if num_notes <= 0:
        raise ValueError("num_notes must be positive")

    # ``motif_length`` represents the number of notes in the initial idea that
    # will be repeated.  It cannot exceed the total number of notes requested or
    # the function would be unable to fill the melody.
    if num_notes < motif_length:
        raise ValueError("num_notes must be greater than or equal to motif_length")

    notes_in_key = SCALE[key]
    indices_in_key = _SCALE_INDICES[key]

    # Track optional overrides for the cadence so only the final beat pair is
    # reharmonised. ``plagal_overrides`` maps absolute note indices to chord
    # names, ensuring that earlier repetitions of the progression remain
    # untouched even when the same chords loop via modulo arithmetic.
    plagal_overrides: Dict[int, str] = {}
    tonic_override: Optional[str] = None
    if plagal_cadence:
        # ``diatonic_chords`` returns the scale's triads in order.  The tonic
        # and subdominant provide the IV–I cadence while still respecting the
        # user's chosen mode (major/minor and modal variants).
        chords_in_key = diatonic_chords(key)
        if len(chords_in_key) >= 4:
            tonic_override = canonical_chord(chords_in_key[0])
            subdominant_override = canonical_chord(chords_in_key[3])
            if num_notes >= 1:
                plagal_overrides[num_notes - 1] = tonic_override
            if num_notes >= 2:
                plagal_overrides[num_notes - 2] = subdominant_override
        else:
            # Missing chords indicate a malformed scale definition. Rather than
            # crash, disable the plagal option and proceed with the user's
            # original progression while logging the issue for diagnostics.
            logging.warning(
                "Plagal cadence unavailable for %s because diatonic chords are incomplete.",
                key,
            )
            plagal_cadence = False

    def _chord_at(index: int) -> str:
        """Return the active chord for ``index`` honouring cadence overrides."""

        override = plagal_overrides.get(index)
        return override if override is not None else chord_progression[index % len(chord_progression)]

    # Choose a rhythmic pattern when the caller does not supply one.  The
    # pattern cycles throughout the melody to give it an underlying pulse.
    if pattern is None:
        # Use the rhythm generator when provided so pitch and rhythm can be
        # controlled independently.  Fall back to the default helper otherwise.
        if rhythm_generator is not None:
            pattern = rhythm_generator.generate(num_notes)
        else:
            pattern = generate_rhythm(num_notes)
    elif not pattern:
        # An explicitly empty pattern would cause divide-by-zero errors when
        # cycling through the list. Reject this early with a clear message so
        # callers know the pattern must contain at least one duration value.
        raise ValueError("pattern must not be empty")
    elif any(p < 0 for p in pattern):
        # Negative durations would generate invalid MIDI event timing. Validate
        # that all entries are zero or positive to ensure deterministic output.
        raise ValueError("pattern durations must be non-negative")

    # Validate the provided time signature so subsequent calculations never
    # divide by zero or produce negative beat counts. ``time_signature[1]``
    # is restricted to common musical denominators to keep rhythm calculations
    # simple.
    valid_denoms = {1, 2, 4, 8, 16}
    if time_signature[0] <= 0 or time_signature[1] <= 0 or time_signature[1] not in valid_denoms:
        raise ValueError(
            "time_signature denominator must be one of 1, 2, 4, 8 or 16 and numerator must be > 0"
        )

    # ``base_octave`` controls the register of the melody. Restrict it to a
    # safe MIDI range so generated notes remain between 0 and 127.
    if not MIN_OCTAVE <= base_octave <= MAX_OCTAVE:
        raise ValueError(f"base_octave must be between {MIN_OCTAVE} and {MAX_OCTAVE}")

    # Establish a phrase outline when one is not provided. The resulting
    # ``pitch_range`` restricts subsequent octave choices during note
    # generation.
    phrase_plan = phrase_plan or generate_phrase_plan(num_notes, base_octave)
    plan_min_oct, plan_max_oct = phrase_plan.pitch_range
    base_octave = max(plan_min_oct, min(base_octave, plan_max_oct - 1))

    def _choose_resolution(
        target_name: str,
        reference_note: str,
        *,
        prefer_descending: bool,
    ) -> str:
        """Select ``target_name`` close to ``reference_note`` within plan limits."""

        reference_midi = note_to_midi(reference_note)
        best: Optional[str] = None
        best_score: Optional[tuple[float, int, int, int]] = None
        for octv in range(plan_min_oct, plan_max_oct + 1):
            candidate = f"{target_name}{octv}"
            midi_val = note_to_midi(candidate)
            distance = abs(midi_val - reference_midi)
            descent_penalty = 0 if (not prefer_descending or midi_val <= reference_midi) else 1
            octave_bias = abs(octv - base_octave)
            score = (distance, descent_penalty, octave_bias, midi_val)
            if best_score is None or score < best_score:
                best_score = score
                best = candidate
        if best is None:
            # Fallback should never trigger but provides a safe default when the
            # plan range is unexpectedly empty.
            best = f"{target_name}{max(plan_min_oct, min(plan_max_oct, base_octave))}"
        return best

    def _apply_plagal_cadence(sequence: List[str]) -> None:
        """Mutate ``sequence`` in place to realise a IV–I plagal cadence."""

        if not plagal_cadence or tonic_override is None:
            return
        # Guard against misconfigured scales. Without at least four distinct
        # scale degrees we cannot outline ^4–^3–^1 reliably.
        if len(notes_in_key) < 4:
            return

        tonic_root = get_chord_notes(tonic_override)[0]
        degree_three = notes_in_key[2]
        degree_four = notes_in_key[3]
        total = len(sequence)
        if total == 0:
            return
        if total == 1:
            sequence[-1] = _choose_resolution(tonic_root, sequence[-1], prefer_descending=True)
            return
        if total == 2:
            first = _choose_resolution(degree_four, sequence[-2], prefer_descending=False)
            second = _choose_resolution(tonic_root, first, prefer_descending=True)
            sequence[-2], sequence[-1] = first, second
            return

        anchor = sequence[-4] if total > 3 else sequence[0]
        third = _choose_resolution(degree_four, anchor, prefer_descending=False)
        second = _choose_resolution(degree_three, third, prefer_descending=True)
        final_note = _choose_resolution(tonic_root, second, prefer_descending=True)
        sequence[-3], sequence[-2], sequence[-1] = third, second, final_note

    # Style vectors may be provided directly via ``style`` or retrieved from
    # thread-local storage via :func:`set_style`. When both are absent, no
    # stylistic bias is applied.
    style_vec = get_style_vector(style) if style else get_active_style()
    from .voice_leading import (
        parallel_fifth_or_octave,
        counterpoint_penalty,
        counterpoint_penalties,
        parallel_fifths_mask,
    )

    beat_unit = 1 / time_signature[1]
    start_beat = 0.0

    if structure is not None:
        if not structure.isalpha():
            raise ValueError("structure must only contain letters A-Z")
        # Divide the requested length among the labelled sections. Any
        # remainder is distributed one note at a time from the start so the
        # phrase covers ``num_notes`` exactly.
        seg_len = num_notes // len(structure)
        remainder = num_notes % len(structure)

        def _mutate(n: str) -> str:
            """Return ``n`` shifted by one scale step about a third of the time."""

            if random.random() < 0.3:
                name, octv = n[:-1], int(n[-1])
                idx = indices_in_key[name]
                idx = (idx + random.choice([-1, 1])) % len(notes_in_key)
                name = notes_in_key[idx]
                return f"{name}{octv}"
            return n

        sections: dict[str, List[str]] = {}
        final: List[str] = []
        offset = 0
        for i, label in enumerate(structure):
            # ``length`` for this segment equals the base size plus one if any
            # leftover notes remain to be distributed.
            length = seg_len + (1 if i < remainder else 0)
            if length <= 0:
                # A structure longer than ``num_notes`` would otherwise call the
                # recursive generator with ``num_notes <= 0`` which raises a
                # confusing error. Provide a descriptive failure instead.
                raise ValueError(
                    "structure length cannot exceed the number of notes"
                )

            # When sections are shorter than the requested motif we clamp the
            # motif length so recursive calls remain valid. Without this guard a
            # structure like ``'AB'`` with ``motif_length=5`` and ``num_notes=8``
            # would recurse with ``length=4`` and immediately raise ``ValueError``.
            segment_motif = min(motif_length, length)

            # Derive a section-specific phrase plan so the recursive call keeps
            # the same pitch limits and tension profile as the parent request.
            segment_plan: Optional[PhrasePlan] = None
            if phrase_plan is not None:
                tension_slice = phrase_plan.tension_profile[offset : offset + length]
                if not tension_slice:
                    # Degenerate plans fall back to a neutral contour so the
                    # recursion still receives a usable profile.
                    tension_slice = [0.5] * length
                elif len(tension_slice) < length:
                    # Pad with the last known value when rounding causes the
                    # slice to undershoot by a few notes.
                    tension_slice = tension_slice + [tension_slice[-1]] * (
                        length - len(tension_slice)
                    )
                segment_plan = PhrasePlan(length, phrase_plan.pitch_range, tension_slice)

            if label not in sections:
                seg = generate_melody(
                    key,
                    length,
                    chord_progression,
                    motif_length=segment_motif,
                    time_signature=time_signature,
                    pattern=pattern,
                    base_octave=base_octave,
                    structure=None,
                    allow_tritone=allow_tritone,
                    phrase_plan=segment_plan,
                    sequence_model=sequence_model,
                    rhythm_generator=rhythm_generator,
                    style=style,
                    refine=refine,
                    plagal_cadence=plagal_cadence and i == len(structure) - 1,
                )
                sections[label] = seg
            else:
                seg = [_mutate(n) for n in sections[label][:length]]
            final.extend(seg)
            offset += length
        final = final[:num_notes]
        if plagal_cadence and tonic_override is not None:
            # Reapply the cadence to the concatenated melody so repeated
            # sections (e.g. ``AABA``) still conclude with the requested IV–I
            # gesture even when the last label reuses earlier material.
            _apply_plagal_cadence(final)
        return final

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
        # Ensure the opening motif ascends to establish a clear direction.
        if note_to_midi(curr) <= note_to_midi(prev):
            name, octave = prev[:-1], int(prev[-1])
            idx = indices_in_key[name]
            idx += 1
            if idx >= len(notes_in_key):
                idx -= len(notes_in_key)
                octave += 1
            allowed_min = max(plan_min_oct, base_octave + octave_offset)
            allowed_max = min(plan_max_oct, allowed_min + 1)
            octave = max(allowed_min, min(allowed_max, octave))
            melody[j] = notes_in_key[idx] + str(octave)

    # Align motif notes with the underlying harmony on strong beats so the
    # phrase begins solidly over the chord changes.
    for j in range(motif_length):
        strong = abs(start_beat - round(start_beat)) < 1e-6
        chord = _chord_at(j)
        chord_notes = get_chord_notes(chord)
        if strong:
            name, octv = melody[j][:-1], melody[j][-1]
            if name not in chord_notes:
                closest = min(
                    chord_notes,
                    key=lambda n: abs(note_to_midi(n + octv) - note_to_midi(melody[j])),
                )
                melody[j] = closest + octv
        start_beat += pattern[j % len(pattern)] / beat_unit

    # Track the direction of any large melodic leaps.  This information guides
    # the next note so the line moves back toward the centre after a big jump.
    leap_dir: Optional[int] = None
    prev_interval_size: Optional[int] = None
    prev_dir: Optional[int] = None

    if len(melody) >= 2:
        diff = note_to_midi(melody[-1]) - note_to_midi(melody[-2])
        prev_interval_size = abs(diff)
        prev_dir = 1 if diff > 0 else -1 if diff < 0 else 0

    # The overall contour rises during the first half of the melody and falls
    # during the second half. ``half_point`` marks the boundary between these
    # two sections.
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
            # Reintroduce the motif but possibly shifted in octave to keep the
            # phrase from sounding monotonous.
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
            idx = indices_in_key[name]
            new_idx = idx + direction
            if new_idx < 0:
                new_idx += len(notes_in_key)
                octave -= 1
            elif new_idx >= len(notes_in_key):
                new_idx -= len(notes_in_key)
                octave += 1
            allowed_min = max(plan_min_oct, base_octave + octave_offset)
            allowed_max = min(plan_max_oct, allowed_min + 1)
            octave += diff
            if diff > 0:
                octave = allowed_max
            elif diff < 0:
                octave = allowed_min
            else:
                octave = max(allowed_min, min(allowed_max, octave))
            new_name = notes_in_key[new_idx]
            chord = _chord_at(i)
            chord_notes = get_chord_notes(chord)
            if strong and new_name not in chord_notes:
                new_name = min(
                    chord_notes,
                    key=lambda n: abs(
                        note_to_midi(n + str(octave)) - note_to_midi(new_name + str(octave))
                    ),
                )
            melody.append(new_name + str(octave))
            start_beat += pattern[i % len(pattern)] / beat_unit
            continue
        chord = _chord_at(i)
        chord_notes = get_chord_notes(chord)
        scale_for_chord(key, chord)
        prev_note = melody[-1]
        candidates: List[str] = []
        min_interval = None

        root_octave = max(plan_min_oct, min(plan_max_oct, base_octave + octave_offset))
        source_pool = _candidate_pool(
            key,
            chord,
            root_octave,
            strong=strong,
        )
        # Constrain candidates to the planned pitch range so octave offsets do
        # not exceed ``plan_max_oct`` when ``root_octave`` equals the upper
        # boundary.
        source_pool = [n for n in source_pool if plan_min_oct <= int(n[-1]) <= plan_max_oct]

        prev_midi = note_to_midi(prev_note)
        if np is not None and source_pool:
            # Vectorised search for notes within one semitone of the smallest
            # possible leap from ``prev_note``. ``intervals_all`` holds the
            # absolute difference to every note in ``source_pool`` so the
            # minimal interval can be found in one pass.
            pool_midis = np.fromiter((note_to_midi(n) for n in source_pool), dtype=np.int16)
            intervals_all = np.abs(pool_midis - prev_midi)
            min_interval = float(intervals_all.min())
            mask = intervals_all <= (min_interval + 1)
            cand_midis = pool_midis[mask]
            # ``mask`` filters both MIDI values and strings via vectorised
            # indexing, avoiding an explicit Python loop.
            candidates = np.asarray(source_pool, dtype=object)[mask].tolist()
        else:
            # ``numpy`` is unavailable so compute the nearest interval using a
            # standard loop. Two passes are used: first to find the minimum
            # distance, then to collect all notes within one semitone of that
            # minimum.
            for candidate_note in source_pool:
                interval = get_interval(prev_note, candidate_note)
                if min_interval is None or interval < min_interval:
                    min_interval = interval
            if min_interval is not None:
                threshold = min_interval + 1
                for candidate_note in source_pool:
                    interval = get_interval(prev_note, candidate_note)
                    if interval <= threshold:
                        candidates.append(candidate_note)
            cand_midis = [note_to_midi(c) for c in candidates]

        # Fallback: if filtering removes every candidate, pick a random note
        # from the same chord pool so the melody always progresses.
        if not candidates:
            logging.warning(
                f"No candidate found for chord {chord} with previous note {prev_note}. Using fallback."
            )
            pool = _candidate_pool(
                key,
                chord,
                root_octave,
                strong=strong,
            )
            pool = [n for n in pool if plan_min_oct <= int(n[-1]) <= plan_max_oct]
            fallback_note = random.choice(pool)
            candidates.append(fallback_note)

        # Optionally remove tritone leaps unless explicitly allowed. Filtering
        # these intervals yields a smoother line for genres that avoid the
        # dissonant augmented fourth/diminished fifth.
        if not allow_tritone and candidates:
            if np is not None:
                mask = np.abs(cand_midis - prev_midi) != 6
                if mask.any():
                    cand_midis = cand_midis[mask]
                    # Filter notes using the boolean mask with vectorised indexing
                    # so rejected notes never influence subsequent weighting.
                    candidates = np.asarray(candidates, dtype=object)[mask].tolist()
            else:
                filtered = [
                    c
                    for c in candidates
                    if abs(note_to_midi(c) - prev_midi) != 6
                ]
                if filtered:
                    candidates = filtered
                cand_midis = [note_to_midi(c) for c in candidates]

        # If the previous interval was a leap, favour notes that reverse
        # direction by a small step. Resetting ``leap_dir`` after applying the
        # filter ensures only one compensating note is enforced.
        if leap_dir is not None and candidates:
            if np is not None:
                diff = cand_midis - prev_midi
                mask = (diff * leap_dir < 0) & (np.abs(diff) <= 2)
                if mask.any():
                    cand_midis = cand_midis[mask]
                    # Apply the mask directly to ``candidates`` rather than looping.
                    candidates = np.asarray(candidates, dtype=object)[mask].tolist()
            else:
                filtered = [
                    c
                    for c in candidates
                    if (
                        (note_to_midi(c) - prev_midi) * leap_dir < 0
                        and abs(note_to_midi(c) - prev_midi) <= 2
                    )
                ]
                if filtered:
                    candidates = filtered
                cand_midis = [note_to_midi(c) for c in candidates]
            leap_dir = None

        # Bias overall motion toward ``direction`` so the long-term contour
        # continues rising or falling. When no note matches the desired
        # direction during the descent, choose the lowest candidate to emphasise
        # closure.
        if candidates:
            if np is not None:
                diff = cand_midis - prev_midi
                mask = diff * direction >= 0
                if mask.any():
                    cand_midis = cand_midis[mask]
                    # ``candidates`` filtered in one step via boolean indexing.
                    candidates = np.asarray(candidates, dtype=object)[mask].tolist()
                elif direction < 0:
                    idx = int(np.argmin(cand_midis))
                    cand_midis = np.array([cand_midis[idx]])
                    candidates = [candidates[idx]]
            else:
                directional = [c for c in candidates if (note_to_midi(c) - prev_midi) * direction >= 0]
                if directional:
                    candidates = directional
                elif direction < 0:
                    candidates = [min(candidates, key=note_to_midi)]
                cand_midis = [note_to_midi(c) for c in candidates]

        # Weight candidate notes so smaller intervals and chord tones on strong
        # beats are favoured. This creates a rudimentary Markov-style bias
        # without requiring a full transition matrix learned from data.
        prev_midi_val = prev_midi
        if np is not None:
            cand_midis = np.array(cand_midis, dtype=np.float64)
            intervals = np.abs(cand_midis - prev_midi_val)
            chord_mask = np.array([c[:-1] in chord_notes for c in candidates], dtype=np.uint8) if strong else np.zeros(len(candidates), dtype=np.uint8)
        else:
            cand_midis = [note_to_midi(c) for c in candidates]
            intervals = [abs(m - prev_midi_val) for m in cand_midis]
            chord_mask = [c[:-1] in chord_notes for c in candidates] if strong else [False] * len(candidates)
        # ``compute_base_weights`` encodes interval preferences as a rudimentary
        # Markov process. Passing in the previous interval reduces the weight of
        # repeating large leaps so phrases remain singable.
        weights = compute_base_weights(
            intervals,
            chord_mask,
            prev_interval_size if prev_interval_size is not None else -1,
        )

        if sequence_model is not None:
            # Query the sequence model for logit scores of the next scale degree
            # and add them to the heuristic weights. This allows learned
            # statistics to bias the otherwise rule-based process.
            # Build a short history of scale degrees for the model. Only the
            # four most recent notes are used so predictions remain local.
            hist = [indices_in_key[n[:-1]] for n in melody[max(0, i - 4) : i]]
            if hist:
                logits = sequence_model.predict_logits(hist)
                if np is not None:
                    bias = np.array([
                        float(logits[indices_in_key[c[:-1]] % len(logits)]) for c in candidates
                    ])
                    weights = np.array(weights, dtype=float) + bias
                    weights = weights.tolist()
                else:
                    for idx, cand in enumerate(candidates):
                        deg = indices_in_key[cand[:-1]] % len(logits)
                        weights[idx] += float(logits[deg])

        if style_vec is not None:
            # Add style embedding values to each candidate weight so different
            # genres emphasise characteristic scale degrees. Vectorised indexing
            # is used when ``numpy`` is available.
            idxs = [indices_in_key[c[:-1]] % len(style_vec) for c in candidates]
            if np is not None:
                weights = np.asarray(weights, dtype=float)
                weights += style_vec[np.array(idxs)]
            else:
                weights = [w + float(style_vec[idx]) for w, idx in zip(weights, idxs)]

        # Penalize parallel fifths and octaves with the chord roots to maintain
        # smoother voice leading against the underlying harmony.
        # Evaluate counterpoint against the bass line by comparing the previous
        # and current chord roots. We only need the root note of each chord to
        # detect parallel motion.
        prev_root = get_chord_notes(_chord_at(i - 1))[0] + str(base_octave)
        curr_root = get_chord_notes(chord)[0] + str(base_octave)
        if np is not None:
            # ``parallel_fifths_mask`` returns True for candidates forming
            # parallel motion with the bass. Halve their weights so they are
            # unlikely but still possible when no alternatives exist.
            mask = parallel_fifths_mask(prev_note, prev_root, candidates, curr_root)
            if np.any(mask):
                weights = np.asarray(weights, dtype=float)
                weights[mask] *= 0.5
            # ``counterpoint_penalties`` gently discourages consecutive leaps in
            # the same direction or repeated perfect intervals.
            penalties = counterpoint_penalties(
                prev_note,
                candidates,
                prev_dir=prev_dir,
                prev_interval=prev_interval_size,
            )
            weights = np.asarray(weights, dtype=float) + penalties
        else:
            for idx, cand in enumerate(candidates):
                if parallel_fifth_or_octave(prev_note, prev_root, cand, curr_root):
                    weights[idx] *= 0.5
                weights[idx] += counterpoint_penalty(
                    prev_note,
                    cand,
                    prev_dir=prev_dir,
                    prev_interval=prev_interval_size,
                )

        target_tension = phrase_plan.tension_profile[i]
        tensions = [tension_for_notes(prev_note, c) for c in candidates]
        if np is not None:
            # Shift weights toward notes that match the planned tension curve
            # using a simple inverse-distance metric. When all weights drop to
            # zero (possible with extreme tension targets) fall back to equal
            # probabilities so the melody continues.
            weights = apply_tension_weights(np.array(weights), tensions, target_tension)
            if np.all(weights == 0):
                weights = np.ones_like(weights)
            weights = weights.astype(float)
            weights = weights.tolist()
        else:
            # Pure-Python implementation behaves the same but operates on lists
            # to avoid a mandatory numpy dependency.
            weights = apply_tension_weights(weights, tensions, target_tension)

        next_note = pick_note(candidates, weights)
        melody.append(next_note)

        start_beat += pattern[i % len(pattern)] / beat_unit

        # Determine if this interval constitutes a leap so the next note can
        # compensate accordingly.
        interval = note_to_midi(next_note) - note_to_midi(prev_note)
        prev_interval_size = abs(interval)
        if prev_interval_size >= 7:
            leap_dir = 1 if interval > 0 else -1
        prev_dir = 1 if interval > 0 else -1 if interval < 0 else 0

    if plagal_cadence and tonic_override is not None:
        # Apply the cadence helper so both the mainline generation path and the
        # sectional recursion share the same IV–I realisation logic.
        _apply_plagal_cadence(melody)
    else:
        # Resolve the phrase by forcing the last note to the root of the final
        # chord. This creates a basic cadence so melodies feel complete even
        # when the stochastic process would end on a non-resolving tone.
        final_chord = _chord_at(num_notes - 1)
        final_root = get_chord_notes(final_chord)[0]
        last_oct = melody[-1][-1]
        # Always select the root of the final chord but choose the octave that
        # yields the smallest leap from the previous note. When the melody
        # contains only a single note the previous pitch is reused so the
        # cadence calculation does not fail.
        low_oct = max(plan_min_oct, int(last_oct) - 1)
        high_oct = min(plan_max_oct, int(last_oct))
        low = f"{final_root}{low_oct}"
        high = f"{final_root}{high_oct}"
        prev_midi = note_to_midi(melody[-2]) if len(melody) >= 2 else note_to_midi(melody[-1])
        melody[-1] = low if note_to_midi(low) <= prev_midi else high

    if refine:
        # Use Frechet Music Distance to hill-climb toward the training
        # distribution. Random replacements are only kept when they reduce
        # the distance, gently nudging the phrase into a more musical space.

        melody = refine_with_fmd(
            melody,
            key,
            chord_progression,
            base_octave,
        )

    # Always clamp the final melody when refinement is active so octave shifts
    # never push notes outside the planned range.
    if refine:
        # After refinement clamp notes to the planned pitch range so the
        # sequence never wanders outside the intended register.
        low, high = phrase_plan.pitch_range
        for idx, n in enumerate(melody):
            octv = int(n[-1])
            if octv < low:
                melody[idx] = n[:-1] + str(low)
            elif octv > high:
                melody[idx] = n[:-1] + str(high)

    return melody


def generate_harmony_line(melody: List[str], interval: int = 4) -> List[str]:
    """Return a simple harmony line at ``interval`` semitones from ``melody``.

    The resulting line mirrors the rhythm of ``melody`` while remaining
    within the valid MIDI range.

    @param melody (List[str]): Base melody to harmonize.
    @param interval (int): Interval offset in semitones.
    @returns List[str]: Harmony melody line.
    """
    harmony = []
    for note in melody:
        base = note_to_midi(note)
        target = base + interval
        # Reflect intervals that fall outside the MIDI range back toward
        # the melody so the resulting notes stay valid.
        if target < 0 or target > 127:
            target = base - interval
        target = max(0, min(127, target))
        harmony.append(midi_to_note(target))
    return harmony


def generate_counterpoint_melody(melody: List[str], key: str) -> List[str]:
    """Generate a counterpoint line for ``melody`` in ``key``.

    The line favours contrary motion and consonant intervals such as thirds,
    sixths, fifths and octaves.

    @param melody (List[str]): Base melody to accompany.
    @param key (str): Musical key for scale context.
    @returns List[str]: Generated counterpoint line.
    """
    # Validate the key before attempting to index into ``SCALE`` so callers
    # receive a clear error rather than ``KeyError`` when an unknown key is
    # supplied.
    if key not in SCALE:
        raise ValueError(f"Unknown key '{key}'")

    scale_notes = SCALE[key]
    counter: List[str] = []
    prev_note = None
    prev_base = None
    consonant = {3, 4, 7, 8, 9, 12}
    # Examine each note of the melody in turn to build the accompanying line.
    for base_note in melody:
        base_midi = note_to_midi(base_note)
        candidates: List[str] = []
        # Gather consonant pitches around the current melody note so any chosen
        # note forms a pleasant interval when played together with ``base_note``.
        for n in scale_notes:
            # Test potential companion notes across a small octave range so the
            # counterpoint does not stray too far from the melody.
            for octave in range(3, 7):
                cand = f"{n}{octave}"
                interval = abs(note_to_midi(cand) - base_midi)
                if interval in consonant:
                    candidates.append(cand)
        # It is possible no candidate fits the consonant set; in that case
        # simply mirror the melody note so the line never stalls.
        if not candidates:
            candidates.append(base_note)
        choice = random.choice(candidates)
        if prev_note and prev_base:
            # Compare the motion of the melody and the tentative counterpoint
            # note. When both move in the same direction we search for an
            # alternative moving opposite to highlight contrary motion, a
            # hallmark of species counterpoint.
            base_int = note_to_midi(base_note) - note_to_midi(prev_base)
            cand_int = note_to_midi(choice) - note_to_midi(prev_note)
            if base_int * cand_int > 0:
                opposite = [
                    c
                    for c in candidates
                    if (note_to_midi(c) - note_to_midi(prev_note)) * base_int < 0
                ]
                if opposite:
                    choice = random.choice(opposite)
        counter.append(choice)
        prev_note = choice
        prev_base = base_note
    return counter

from .note_utils import note_to_midi, midi_to_note, get_interval  # noqa: E402
from . import midi_io  # noqa: F401,E402
from .midi_io import create_midi_file, _open_default_player  # noqa: F401,E402

def run_cli():
    from .cli import run_cli as _run_cli
    _run_cli()

def main():
    from .cli import main as _main
    _main()



if __name__ == "__main__":
    main()

