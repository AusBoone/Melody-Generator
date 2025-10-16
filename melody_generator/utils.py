"""Utility helpers shared across Melody Generator components.

This module collects lightweight functions that do not fit in more
specific modules.  Each helper is carefully documented so both the CLI
and GUI can reuse the same validation logic without duplicating code.

Usage Example
-------------
>>> from melody_generator.utils import validate_time_signature
>>> validate_time_signature("3/4")
(3, 4)
>>> parse_chord_progression("C,Am,F,G", key="C")
['C', 'Am', 'F', 'G']

Revision Summary
----------------
* Added Roman-numeral parsing to :func:`parse_chord_progression` so documented
  progressions such as ``♭VI`` and ``V/ii`` are now accepted by both the CLI and
  GUI without manual translation into chord names.
* Introduced helper utilities that normalise unicode accidentals, determine
  enharmonic preferences from the current key signature and resolve secondary
  dominants recursively. Inline comments highlight design decisions and edge
  cases for future contributors.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Sequence, Tuple

__all__ = ["validate_time_signature", "parse_chord_progression"]


# Mapping of triadic Roman numerals (without accidentals) to zero-based scale
# degrees.  Accidentals and secondary dominants are resolved separately while
# this table focuses on the base diatonic positions.
_ROMAN_DEGREES: Dict[str, int] = {
    "i": 0,
    "ii": 1,
    "iii": 2,
    "iv": 3,
    "v": 4,
    "vi": 5,
    "vii": 6,
}

# Candidate note names for each chromatic semitone (0 == C).  The order
# determines the order in which enharmonic spellings are attempted when mapping
# Roman numerals to actual chord symbols.  Including both flat and sharp spellings
# lets the parser honour the user's requested accidental as well as the key
# signature's natural tendency.
_SEMITONE_CANDIDATES: Dict[int, Sequence[str]] = {
    0: ("C",),
    1: ("C#", "Db"),
    2: ("D",),
    3: ("D#", "Eb"),
    4: ("E",),
    5: ("F",),
    6: ("F#", "Gb"),
    7: ("G",),
    8: ("G#", "Ab"),
    9: ("A",),
    10: ("A#", "Bb"),
    11: ("B",),
}

# Unicode accidentals are normalised to their ASCII equivalents before being
# applied.  Multiple characters (e.g. ``bb``) accumulate offsets so the parser
# can represent double accidentals if they ever appear in documentation.
_ACCIDENTAL_OFFSETS: Dict[str, int] = {"b": -1, "#": 1}

# Recognised suffix hints that alter chord quality.  Half-diminished ("ø") is
# treated as diminished because the project only models triads; seventh
# extensions would require new chord tables and are therefore rejected.
_DIM_SUFFIXES = ("dim", "°", "o", "ø")
_AUG_SUFFIXES = ("aug", "+")

# Keys that naturally prefer flat spellings.  Modal variants inherit the same
# behaviour via their ``_mode`` suffix.
_FLAT_KEY_PREFIXES = ("F", "Bb", "Eb", "Ab", "Db", "Gb", "Cb")


def _key_prefers_flats(key: str) -> bool:
    """Return ``True`` when ``key`` traditionally uses flat spellings."""

    base = key.split("_")[0]
    return any(base.startswith(prefix) for prefix in _FLAT_KEY_PREFIXES)


def _normalise_roman_token(token: str) -> str:
    """Replace unicode accidentals and trim surrounding whitespace."""

    return token.replace("♭", "b").replace("♯", "#").strip()


def _extract_roman_components(symbol: str) -> Tuple[str, str, str]:
    """Return ``(accidentals, numeral, suffix)`` for ``symbol``.

    The regular expression intentionally accepts only the characters used by the
    project (``b``, ``#`` and ``I/V/X``) to avoid silently accepting malformed
    input such as ``T`` or ``Lyd``.
    """

    match = re.match(r"^([b#]*)([ivxIVX]+)(.*)$", symbol)
    if not match:
        raise ValueError(f"Invalid Roman numeral: {symbol}")
    return match.group(1), match.group(2), match.group(3)


def _select_chord_root(
    semitone: int,
    *,
    prefer_flats: bool,
    explicit_flat: bool,
    explicit_sharp: bool,
    quality: str,
) -> str:
    """Return a canonical chord name for ``semitone`` and ``quality``.

    Parameters
    ----------
    semitone:
        Chromatic index of the desired chord root.
    prefer_flats:
        Whether the enclosing key naturally favours flat spellings.
    explicit_flat, explicit_sharp:
        Whether the user specifically requested a flat or sharp accidental in
        the Roman numeral. These hints take priority over ``prefer_flats``.
    quality:
        One of ``"major"``, ``"minor"`` or ``"dim"``. Augmented chords are not
        yet supported and raise ``ValueError``.
    """

    from . import canonical_chord  # Local import avoids circular dependencies

    candidates = list(_SEMITONE_CANDIDATES[semitone])
    ordered: List[str] = []

    def _append(names: Sequence[str]) -> None:
        for name in names:
            if name in candidates and name not in ordered:
                ordered.append(name)

    naturals = [n for n in candidates if "#" not in n and "b" not in n]
    flats = [n for n in candidates if "b" in n]
    sharps = [n for n in candidates if "#" in n]

    _append(naturals)
    if explicit_flat:
        _append(flats)
    if explicit_sharp:
        _append(sharps)
    if not explicit_flat and not explicit_sharp:
        if prefer_flats:
            _append(flats)
            _append(sharps)
        else:
            _append(sharps)
            _append(flats)
    _append(candidates)

    suffix_map = {"major": "", "minor": "m", "dim": "dim"}
    if quality not in suffix_map:
        raise ValueError("Augmented chords are not supported")

    suffix = suffix_map[quality]
    last_error: Optional[ValueError] = None
    for root in ordered:
        try:
            return canonical_chord(root + suffix)
        except ValueError as exc:
            last_error = exc

    if last_error is not None:
        raise last_error
    raise ValueError(f"Unable to resolve chord for semitone {semitone}")


def _roman_to_chord(symbol: str, key: str) -> str:
    """Convert ``symbol`` (Roman numeral) into a canonical chord name."""

    from . import NOTE_TO_SEMITONE, SCALE, canonical_key

    canonical_key_value = canonical_key(key)
    token = _normalise_roman_token(symbol)
    if "/" in token:
        base, target = token.split("/", 1)
        target_chord = _roman_to_chord(target, canonical_key_value)
        root = target_chord[:-3] if target_chord.endswith("dim") else target_chord.rstrip("m")
        is_minor = target_chord.endswith("m") or target_chord.endswith("dim")
        temp_key = root + ("m" if is_minor else "")
        try:
            secondary_key = canonical_key(temp_key)
        except ValueError:
            secondary_key = canonical_key(root)
        return _roman_to_chord(base, secondary_key)

    accidentals, numeral, suffix = _extract_roman_components(token)
    degree = _ROMAN_DEGREES.get(numeral.lower())
    if degree is None:
        raise ValueError(f"Unsupported Roman numeral: {symbol}")

    scale = SCALE[canonical_key_value]
    base_note = scale[degree]
    prefer_flats = _key_prefers_flats(canonical_key_value) or "b" in base_note
    explicit_flat = "b" in accidentals
    explicit_sharp = "#" in accidentals

    offset = sum(_ACCIDENTAL_OFFSETS.get(ch, 0) for ch in accidentals)
    semitone = (NOTE_TO_SEMITONE[base_note] + offset) % 12

    quality = "major" if numeral.isupper() else "minor"
    lowered_suffix = suffix.lower()
    if any(marker in lowered_suffix for marker in _DIM_SUFFIXES):
        quality = "dim"
    elif any(marker in lowered_suffix for marker in _AUG_SUFFIXES):
        raise ValueError("Augmented chords are not supported")

    return _select_chord_root(
        semitone,
        prefer_flats=prefer_flats,
        explicit_flat=explicit_flat,
        explicit_sharp=explicit_sharp,
        quality=quality,
    )


def validate_time_signature(ts: str) -> tuple[int, int]:
    """Parse and validate a time signature string.

    Parameters
    ----------
    ts:
        Time signature in ``"NUM/DEN"`` form. Whitespace around the
        separator is ignored.

    Returns
    -------
    tuple[int, int]
        ``(numerator, denominator)`` when ``ts`` is valid.

    Raises
    ------
    ValueError
        If ``ts`` is malformed or uses an unsupported denominator.
    """

    # Accept input such as "4/4" or " 3 / 8 " by trimming whitespace
    parts = ts.strip().split("/")
    if len(parts) != 2:
        raise ValueError(
            "Time signature must be in the form 'numerator/denominator'."
        )

    try:
        numerator = int(parts[0])
        denominator = int(parts[1])
    except ValueError as exc:  # non-integer values
        raise ValueError(
            "Time signature must contain integer numerator and denominator."
        ) from exc

    # Restrict denominator to common simple meter values
    valid_denominators = {1, 2, 4, 8, 16}
    if numerator <= 0 or denominator not in valid_denominators:
        raise ValueError(
            "Time signature numerator must be > 0 and denominator one of 1, 2, 4, 8 or 16."
        )

    return numerator, denominator


def parse_chord_progression(
    progression: Optional[str],
    *,
    key: str,
    random_count: Optional[int] = None,
    allow_empty: bool = True,
    force_random: bool = False,
) -> List[str]:
    """Return a canonicalised chord progression for ``key``.

    Parameters
    ----------
    progression:
        Raw comma-separated chord string supplied by the user. Whitespace is
        ignored around each entry. ``None`` behaves the same as an empty
        string.
    key:
        Musical key used when a random progression needs to be generated.
        The argument is normalised internally so callers may pass any casing.
    random_count:
        Optional positive integer indicating the number of chords to generate
        when a random progression is requested. ``ValueError`` is raised when
        the value is zero or negative. When ``None`` the helper uses the
        default length from :func:`melody_generator.generate_random_chord_progression`.
    allow_empty:
        When ``True`` and ``progression`` is empty a random progression is
        generated automatically. When ``False`` the helper raises
        ``ValueError`` so callers can surface a validation message to the
        user.
    force_random:
        When ``True`` the helper ignores ``progression`` entirely and
        generates a random sequence. This mirrors the GUI's behaviour where a
        checkbox toggles random progressions without supplying a specific
        length.

    Returns
    -------
    List[str]
        List of canonical chord names sourced from :data:`melody_generator.CHORDS`.

    Raises
    ------
    ValueError
        If ``random_count`` is non-positive, the chord list is empty while
        ``allow_empty`` is ``False``, or any chord/Roman numeral is unknown.
    """

    # Import heavy helpers lazily to avoid circular dependencies when the
    # package initialises. Only callers that actually use the progression
    # parser will incur the cost of pulling in the main generator module.
    from . import (
        canonical_chord,
        canonical_key,
        generate_random_chord_progression,
    )

    # Normalise the key once so subsequent lookups receive the canonical form.
    normalised_key = canonical_key(key)

    # Explicit random requests take precedence over any manually supplied
    # progression string. The helper validates ``random_count`` to keep error
    # reporting consistent across CLI and GUI entry points.
    if random_count is not None:
        if random_count <= 0:
            raise ValueError("Random chord count must be a positive integer.")
        return generate_random_chord_progression(normalised_key, random_count)

    if force_random:
        return generate_random_chord_progression(normalised_key)

    entries = []
    if progression:
        # Split on commas and strip whitespace from each chord token. Empty
        # tokens are discarded so trailing commas do not create blank chords.
        entries = [part.strip() for part in progression.split(",") if part.strip()]

    if not entries:
        if allow_empty:
            return generate_random_chord_progression(normalised_key)
        raise ValueError(
            "Chord progression required unless random chords are requested."
        )

    canonical: List[str] = []
    for name in entries:
        try:
            # ``canonical_chord`` raises ``ValueError`` for unknown names. The
            # error is re-raised with a short message tailored for user-facing
            # validation so CLI logging and GUI flash messages remain clear.
            canonical.append(canonical_chord(name))
        except ValueError:
            try:
                canonical.append(_roman_to_chord(name, normalised_key))
            except ValueError as exc:  # pragma: no cover - exercised via tests
                raise ValueError(f"Unknown chord: {name}") from exc

    return canonical
