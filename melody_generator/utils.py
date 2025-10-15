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
"""

from __future__ import annotations

from typing import List, Optional

__all__ = ["validate_time_signature", "parse_chord_progression"]


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
        ``allow_empty`` is ``False``, or any chord name is unknown.
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
        except ValueError as exc:  # pragma: no cover - exercised via tests
            raise ValueError(f"Unknown chord: {name}") from exc

    return canonical
